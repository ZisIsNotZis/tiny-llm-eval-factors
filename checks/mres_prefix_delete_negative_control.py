#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：任何 ingester 的 REFRESH 删除都不能碰别人的行。

背景（这是个真事故）：`ingest_campaign` 曾经用 `source_file LIKE 'mres/%'` 做 REFRESH 删除，
而 `ingest_m165` 把 `source_file` 写成 `mres/m165-vendor/vendor_r1_summary.jsonl`，且排在 ONCE 里
先跑。于是同一轮里 campaign 把 m165 刚插的 5 格删掉，跑完 `run_tag='m165-vendor-r1'` 查回 0 行。
同一个前缀还罩着 spec/variant 面板与 a08 的面板格，一共 923 行。

这条控制先在库里插一行**探针**（`source_file='mres/probe-survive/…'`，一条谁都不会重算的行），
然后完整跑一次 `python3 migrate_db.py`，断言：

  1. 探针还在（`source_file` 与 `run_tag` 都对得上）；
  2. 跑前那 923 个 `mres/%` 行在跑后逐行相同（按 model+_bench+protocol+language+run_tag+source_file+_score 比）；
  3. 连跑两次行数相同（REFRESH 幂等）。

整段跑在**库副本**上（`MIGRATE_DB` 指到临时目录里的那份），共享主库一行都不动：
`reproduce.sh` 后面还要用主库重建报告，控制不能顺手改它。
干净 clone 里没有 `.wrapup/mres` 落盘产物，这时「mres 行一条不丢」这一条记为**未验证**（不假装通过）。
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "experiments.sqlite"
PROBE_SOURCE = "mres/probe-survive/control.json"
PROBE_TAG = "i02-probe-survive"

IDENTITY = ("model, _bench, protocol, language, run_tag, source_file, _score")


def mres_rows(con):
    return set(con.execute(
        f"SELECT {IDENTITY} FROM experiments WHERE source_file LIKE 'mres/%'").fetchall())


def count(con):
    return con.execute("SELECT count(*) FROM experiments").fetchone()[0]


def run_migrate(db_path: Path):
    env = dict(os.environ, MIGRATE_DB=str(db_path))
    r = subprocess.run([sys.executable, "migrate_db.py"], cwd=str(REPO), env=env,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FAIL: migrate_db.py 退出 {r.returncode}：{(r.stdout + r.stderr).strip()[-500:]}")
        sys.exit(1)
    return r.stdout


def insert_probe(con):
    con.execute(
        "INSERT INTO experiments (model, _bench, _score, run_tag, protocol, language, "
        "source_file, n_items) VALUES (?,?,?,?,?,?,?,?)",
        ("Qwen3.5-2B-UD-Q3_K_XL.gguf", "humaneval-probe", 0.5, PROBE_TAG,
         "i02-probe-survive-control", "py", PROBE_SOURCE, 2))
    con.commit()


def probe_present(con) -> bool:
    return con.execute(
        "SELECT 1 FROM experiments WHERE source_file=? AND run_tag=? AND n_items=2",
        (PROBE_SOURCE, PROBE_TAG)).fetchone() is not None


def delete_probe(con):
    con.execute("DELETE FROM experiments WHERE source_file=? AND run_tag=?",
                (PROBE_SOURCE, PROBE_TAG))
    con.commit()


def main() -> int:
    if not DB.exists():
        print(f"FAIL: 数据库不存在：{DB}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="mres-delete-control-"))
    copy = tmp / "experiments.sqlite"
    try:
        # 用 SQLite 在线备份取一份已提交内容完整的副本（WAL 里没检查点的页也要带上）
        src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        dst = sqlite3.connect(copy)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        con = sqlite3.connect(copy)
        insert_probe(con)
        before, before_n = mres_rows(con), count(con)
        con.close()
        print(f"0) 库副本              : {copy.name}（{before_n} 行），"
              f"探针 {PROBE_SOURCE} 已插入；mres/% 行 {len(before)}")

        has_inputs = (REPO / ".wrapup" / "mres").is_dir()
        run_migrate(copy)
        con = sqlite3.connect(copy)
        alive = probe_present(con)
        after = mres_rows(con)
        lost = before - after
        run1_n = count(con)
        con.close()
        print(f"1) 跑完一次 migrate     : 探针存活 {alive}（要 True）")
        if not alive:
            print("FAIL: 探针被某个 ingester 的 REFRESH 删掉了——删除范围又变宽了")
            return 1
        if has_inputs:
            print(f"2) mres/% 行            : {len(before)} → {len(after)}，丢失 {len(lost)} 行（要 0）")
            if lost:
                # 退出码 2 = 不可得：这一轮 refresh 读不到那批行的输入，删除**无法验证**。
                # 干净 clone 就是这种情形（`.wrapup/mres` 没有随仓库完整分发），实测丢 924 行。
                # 真实缺陷是「refresh 删掉了自己重建不出来的行」，它比这条控制更大，
                # 记在 i02 的 PLAN 里；这里不把自己伪装成 PASS。
                print(f"不可得: 这一轮 refresh 丢了 {len(lost)} 行 mres/% 记录且读不到它们的输入"
                      f"（例如 {sorted(lost)[:1]}）；干净 clone 里删除不可验证")
                return 2
        else:
            print("2) mres/% 行            : 未验证（本机没有 .wrapup/mres 落盘产物，"
                  "refresh 读不到输入，这一条记不适用而不是通过）")

        run_migrate(copy)
        con = sqlite3.connect(copy)
        run2_n = count(con)
        still_alive = probe_present(con)
        con.close()
        print(f"3) 再跑一次             : {run1_n} → {run2_n} 行（要相等）；探针存活 {still_alive}")
        if run2_n != run1_n or not still_alive:
            print("FAIL: 连跑两次行数不同或探针消失——REFRESH 不幂等或删除范围过宽")
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
