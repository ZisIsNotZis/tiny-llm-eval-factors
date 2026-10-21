#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：`superseded_by` 是**指针**，悬空指针必须让 `db_check` 变红。

两例：
  1. 忠实副本：库原样复制 → `db_check` 必须 PASS；
  2. 污染副本：把某一行的 `superseded_by` 改成表里不存在的协议串 → 必须 FAIL 并点名悬空指针。
     「指向一个不存在的测量」比没有指针更坏：读的人会以为那一格已被取代，而被取代到的东西不存在。
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "experiments.sqlite"
CHECK = REPO / "checks" / "db_check.py"


def db_check(db: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, DB_CHECK_DB=str(db))
    return subprocess.run([sys.executable, str(CHECK), "--quiet"],
                          capture_output=True, text=True, cwd=str(REPO), env=env)


def main() -> int:
    if not DB.exists():
        print(f"FAIL: 数据库不存在：{DB}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="superseded-pointer-control-"))
    try:
        copy = tmp / "experiments.sqlite"
        # WAL 里未落盘的页也要带上，否则副本读到的可能不是主库看到的那些行
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(DB) + suffix)
            if src.exists():
                shutil.copy2(src, str(copy) + suffix)
        honest = db_check(copy)
        if honest.returncode != 0:
            print(f"FAIL: 忠实副本上 db_check 就没过（第 1 例不成立）：{honest.stdout.strip()[:300]}")
            return 1
        print("1) 忠实副本            : db_check PASS: True")

        con = sqlite3.connect(copy)
        rowid = con.execute("SELECT rowid FROM experiments WHERE superseded_by IS NOT NULL "
                            "LIMIT 1").fetchone()[0]
        con.execute("UPDATE experiments SET superseded_by=? WHERE rowid=?",
                    ("mpl-raw-greedy-768;corpus=deadbeef0000;gen_corpus=nowhere", rowid))
        con.commit()
        con.close()

        dirty = db_check(copy)
        named = "悬空指针" in dirty.stdout
        ok = dirty.returncode == 1 and named
        print(f"2) 悬空指针写进去       : 退出码 {dirty.returncode}（要 1）且点名「悬空指针」: {named}")
        if not ok:
            print(f"FAIL: 悬空指针没有被抓到：{dirty.stdout.strip()[:400]}")
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
