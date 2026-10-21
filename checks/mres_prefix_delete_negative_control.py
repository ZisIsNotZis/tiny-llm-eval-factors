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

跑完删掉探针，再跑一次 `db_check` 确认库回到干净状态。探针是本控制自己造的行，删除它不算改别人的数据。
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "experiments.sqlite"
PROBE_SOURCE = "mres/probe-survive/control.json"
PROBE_TAG = "i02-probe-survive"

IDENTITY = ("model, _bench, protocol, language, run_tag, source_file, _score")


def numbered_backup() -> Path:
    n = 0
    for p in REPO.glob("experiments.sqlite.bak[0-9]*"):
        tail = p.name.split(".bak", 1)[1]
        if tail.isdigit():
            n = max(n, int(tail))
    dst = REPO / f"experiments.sqlite.bak{n + 1}"
    shutil.copy2(DB, dst)
    return dst


def mres_rows(con):
    return set(con.execute(
        f"SELECT {IDENTITY} FROM experiments WHERE source_file LIKE 'mres/%'").fetchall())


def count(con):
    return con.execute("SELECT count(*) FROM experiments").fetchone()[0]


def run_migrate():
    r = subprocess.run([sys.executable, "migrate_db.py"], cwd=str(REPO),
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
    backup = numbered_backup()
    print(f"0) 编号备份            : {backup.name}（{count(sqlite3.connect(DB))} 行）")

    con = sqlite3.connect(DB)
    insert_probe(con)
    before, before_n = mres_rows(con), count(con)
    con.close()
    print(f"1) 探针已插入          : {PROBE_SOURCE}；此时 mres/% 行 {len(before)}，全库 {before_n} 行")

    try:
        run_migrate()
        con = sqlite3.connect(DB)
        alive = probe_present(con)
        after, after_n = mres_rows(con), count(con)
        lost = before - after
        run1_n = after_n
        con.close()
        print(f"2) 跑完一次 migrate     : 探针存活 {alive}（要 True）；"
              f"mres/% 行 {len(before)} → {len(after)}，丢失 {len(lost)} 行（要 0）")
        if not alive:
            print("FAIL: 探针被某个 ingester 的 REFRESH 删掉了——删除范围又变宽了")
            return 1
        if lost:
            sample = sorted(lost)[:3]
            print(f"FAIL: 有 {len(lost)} 行 mres/% 记录在跑前跑后不一致，例如：{sample}")
            return 1

        run_migrate()
        con = sqlite3.connect(DB)
        run2_n = count(con)
        still_alive = probe_present(con)
        con.close()
        print(f"3) 再跑一次             : {run1_n} → {run2_n} 行（要相等）；探针存活 {still_alive}")
        if run2_n != run1_n or not still_alive:
            print("FAIL: 连跑两次行数不同或探针消失——REFRESH 不幂等或删除范围过宽")
            return 1
        return 0
    finally:
        con = sqlite3.connect(DB)
        delete_probe(con)
        n = count(con)
        con.close()
        print(f"4) 探针已清除          : 全库 {n} 行")
        r = subprocess.run([sys.executable, "checks/db_check.py", "--quiet"],
                           cwd=str(REPO), capture_output=True, text=True)
        if r.returncode != 0:
            print(f"FAIL: 清掉探针后 db_check 未通过：{r.stdout.strip()[-300:]}")
            sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
