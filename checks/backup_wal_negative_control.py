#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：WAL 里有未检查点数据时，`migrate_db.numbered_backup()` 的备份必须是变更前状态。

库是 WAL 模式，改动的行先落在 `-wal` 里。只 `shutil.copy2` 主文件会漏掉那一段：备份能打开、
`integrity_check` 也 ok，但行数比变更前少——回滚就回到一个从来没存在过的状态。这个负控在库副本上
制造「主文件之外还有一条已提交的行」，然后同时用两种做法各备份一次：

  * `copy2`  → 行数少一（旧做法的缺陷，必须能看见）
  * `numbered_backup` → 行数与变更前一致（现在的做法）

    python3 checks/backup_wal_negative_control.py
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import migrate_db  # noqa: E402


def main():
    tmp = Path(tempfile.mkdtemp(prefix="backup-wal-negative-control-"))
    try:
        db = tmp / "experiments.sqlite"
        shutil.copyfile(REPO / "experiments.sqlite", db)
        con = sqlite3.connect(db)
        con.execute("PRAGMA journal_mode=wal")
        con.execute("PRAGMA wal_autocheckpoint=0")     # 让写入留在 -wal 里
        before = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
        con.execute("INSERT INTO experiments(model,_bench,_score,run_tag,protocol) "
                    "VALUES('wal-probe.gguf','humaneval',0.5,'wal-probe','p')")
        con.commit()
        want = before + 1
        wal = Path(str(db) + "-wal")
        assert wal.exists() and wal.stat().st_size > 0, "没有形成 -wal，负控无效"
        print(f"rows while the row lives in -wal: {want} (wal {wal.stat().st_size} bytes)")

        # 旧做法：只复制主文件
        naive = tmp / "naive.sqlite"
        shutil.copy2(db, naive)
        got_naive = sqlite3.connect(naive).execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
        print(f"shutil.copy2 of the main file      : {got_naive} rows")

        # 现在的做法：在线备份 + 断言
        dst, got = migrate_db.numbered_backup(str(db))
        print(f"numbered_backup                    : {got} rows -> {os.path.basename(dst)}")

        ok = True
        if got_naive == want:
            print("FAIL: copy2 竟然也拿到了完整内容，这个负控没有暴露任何东西")
            ok = False
        if got != want:
            print(f"FAIL: 在线备份行数 {got} != 变更前 {want}")
            ok = False
        con.close()
        if ok:
            print("PASS: 只复制主文件会漏掉 -wal 里已提交的行；在线备份拿到的是变更前状态")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
