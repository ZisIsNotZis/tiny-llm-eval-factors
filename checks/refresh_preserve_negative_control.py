#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：一轮完整 refresh 只能动自己的行，别人的行逐字不变。

造三行，分属三个 ingester 的地盘，但都不是它们这一轮会重建的产物：

  A. `source_file='mres/i02-probe-campaign/lmeval_panel.json#probe'`，带 `n_items=7`
     —— 属于 campaign 的命名空间，但盘上没有这个面板，**不该被删**（旧的宽前缀删除会删掉它）；
  B. `protocol='variant-i02probe-lmeval'`，`source_file='mres/i02-probe-variant/variant_panel.json'`
     —— 属于 variant 的命名空间，同样盘上没有面板；
  C. `source_file='i02_probe_c.jsonl'`（不在 mres/ 下），带 `n_items=13`
     —— 谁都不该碰；`n_items` 也不能被抹掉（那是 a13 那类「别人补过的列」）。

然后在该库的**副本**上完整跑两次 `migrate_db.py`，断言：
  1. 三行逐字未变（全列比对，含 n_items / protocol / source_file）；
  2. 第二次运行净改动 0 行（全库逐行摘要相同，行数相同）。

任何一条不成立就 FAIL：探针 A 会死，正说明「refresh 又用到了跨 ingester 的宽条件」。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "experiments.sqlite"

PROBES = [
    dict(model="Qwen3.5-2B-UD-Q3_K_XL.gguf", _bench="i02-probe-campaign",
         run_tag="i02-probe-campaign", protocol="i02-probe-campaign-protocol",
         source_file="mres/i02-probe-campaign/lmeval_panel.json#probe",
         n_items=7, _score=0.5, language="python"),
    dict(model="Qwen3.5-2B-UD-Q3_K_XL.gguf", _bench="i02-probe-variant",
         run_tag="i02-probe-variant", protocol="variant-i02probe-lmeval",
         source_file="mres/i02-probe-variant/variant_panel.json",
         n_items=None, _score=0.25, language=None),
    dict(model="Qwen3.5-2B-UD-Q3_K_XL.gguf", _bench="i02-probe-plain",
         run_tag="i02-probe-plain", protocol="i02-probe-plain-protocol",
         source_file="i02_probe_c.jsonl",
         n_items=13, _score=0.75, language="python"),
]


def copy_db(src: Path, dst: Path):
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(dst)
    with d:
        s.backup(d)
    d.close()
    s.close()


def insert_probes(con):
    for p in PROBES:
        con.execute(
            "INSERT INTO experiments (model, _bench, _score, run_tag, protocol, language, "
            "source_file, n_items) VALUES (?,?,?,?,?,?,?,?)",
            (p["model"], p["_bench"], p["_score"], p["run_tag"], p["protocol"],
             p["language"], p["source_file"], p["n_items"]))
    con.commit()


def probe_rows(con):
    out = {}
    for p in PROBES:
        out[p["run_tag"]] = con.execute(
            "SELECT * FROM experiments WHERE run_tag=? AND source_file=?",
            (p["run_tag"], p["source_file"])).fetchall()
    return out


def db_digest(con):
    h = hashlib.sha256()
    cur = con.execute("SELECT * FROM experiments")
    cols = [d[0] for d in cur.description]
    rows = sorted(tuple("" if v is None else str(v) for v in r) for r in cur.fetchall())
    h.update(",".join(cols).encode())
    for r in rows:
        h.update("\x1f".join(r).encode())
    return h.hexdigest(), len(rows)


def run_migrate(db_path: Path):
    env = dict(os.environ, MIGRATE_DB=str(db_path))
    return subprocess.run([sys.executable, "migrate_db.py"], cwd=str(REPO), env=env,
                          capture_output=True, text=True)


def main() -> int:
    if not DB.exists():
        print(f"FAIL: 数据库不存在：{DB}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="refresh-preserve-control-"))
    copy = tmp / "experiments.sqlite"
    try:
        copy_db(DB, copy)
        con = sqlite3.connect(copy)
        insert_probes(con)
        first = probe_rows(con)
        con.close()
        if any(len(v) != 1 for v in first.values()):
            print(f"FAIL: 探针没插进去：{ {k: len(v) for k, v in first.items()} }")
            return 1
        print(f"0) 库副本 {copy.name} 上插入 3 行探针（campaign / variant / 普通三种地盘）")

        r1 = run_migrate(copy)
        if r1.returncode not in (0, 2):
            print(f"FAIL: 第一次 migrate 退出 {r1.returncode}：{(r1.stdout + r1.stderr)[-400:]}")
            return 1
        con = sqlite3.connect(copy)
        after1 = probe_rows(con)
        digest1, n1 = db_digest(con)
        con.close()

        changed = [tag for tag in first if first[tag] != after1[tag]]
        print(f"1) 第一次 refresh       : 三行逐字未变 {not changed}；全库 {n1} 行"
              + (f"；变了的是 {changed}" if changed else ""))
        if changed:
            for tag in changed:
                print(f"   {tag}: 跑前 {first[tag][0] if first[tag] else None}")
                print(f"   {tag}: 跑后 {after1[tag]}")
            print("FAIL: 探针行被 refresh 改写了——这就是「动别人的行」")
            return 1

        r2 = run_migrate(copy)
        if r2.returncode not in (0, 2):
            print(f"FAIL: 第二次 migrate 退出 {r2.returncode}：{(r2.stdout + r2.stderr)[-400:]}")
            return 1
        con = sqlite3.connect(copy)
        after2 = probe_rows(con)
        digest2, n2 = db_digest(con)
        con.close()
        again = [tag for tag in first if first[tag] != after2[tag]]
        print(f"2) 第二次 refresh       : 三行仍逐字未变 {not again}；"
              f"净改动 {n2 - n1} 行、全库摘要相同 {digest1 == digest2}")
        if again:
            print(f"FAIL: 第二次 refresh 改写了 {again}")
            return 1
        if n2 != n1 or digest1 != digest2:
            print("FAIL: 第二次运行不是净改动 0 行（REFRESH 不幂等）")
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
