#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 refresh 抹掉的修正值从一份旧库副本里回填（一次性修复，可重跑）。

背景：REFRESH 类的 ingester 是「删了重插」，而重插只写它自己读到的字段。`n_items` 是 `a13`
从 BFCL 官方台账的 `total_count` 回填出来的修正值，重插把它抹回 NULL——一个人补、一个人抹，
两边都没错，错在这张表没有「这一列不属于重插」的说法。

    python3 migrations/restore_refresh_losses.py --from experiments.sqlite.bak30          # 只看差异
    python3 migrations/restore_refresh_losses.py --from experiments.sqlite.bak30 --apply  # 回填

判据是**测量身份**（`migrate_db.MEASUREMENT_IDENTITY`，23 列），不比 rowid：rowid 会随
删插漂走。只写「现值是 NULL 且旧值不是 NULL」的格子；现有值一律不动（不覆盖别人的判断）。
回填前后各做一次带 WAL 的编号备份，并打印行数对账。
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from migrate_db import MEASUREMENT_IDENTITY, numbered_backup  # noqa: E402  同一份定义，不另抄

DB = os.path.join(REPO, "experiments.sqlite")


def load(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    sel = ",".join(MEASUREMENT_IDENTITY) + ",n_items"
    out = {}
    for row in con.execute(f"SELECT {sel} FROM experiments"):
        key, n_items = tuple(row[:-1]), row[-1]
        if n_items is not None:
            out.setdefault(key, n_items)
    con.close()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default=os.path.join(REPO, "experiments.sqlite.bak30"))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.exists(a.src):
        print(f"FAIL: 旧库副本不存在：{a.src}", file=sys.stderr)
        return 2
    if not os.path.exists(DB):
        print(f"FAIL: 数据库不存在：{DB}", file=sys.stderr)
        return 2

    old = load(a.src)
    con = sqlite3.connect(DB)
    sel = "rowid," + ",".join(MEASUREMENT_IDENTITY) + ",n_items"
    todo = []
    for row in con.execute(f"SELECT {sel} FROM experiments").fetchall():
        rowid = row[0]
        key = tuple(row[1:1 + len(MEASUREMENT_IDENTITY)])
        n_items = row[1 + len(MEASUREMENT_IDENTITY)]
        if n_items is None and key in old:
            todo.append((rowid, key, old[key]))

    print(f"旧库 {os.path.basename(a.src)}: {len(old)} 行带 n_items；"
          f"现库需要回填 {len(todo)} 行")
    for rowid, key, val in todo:
        print(f"  rowid {rowid}: {key[0]} / {key[13]} / {key[19][:46]} → n_items={val}")
    if not todo:
        print("无需回填")
        return 0
    if not a.apply:
        print("（只看差异；加 --apply 才写库）")
        return 0

    numbered_backup(DB)
    before = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    for rowid, _key, val in todo:
        con.execute("UPDATE experiments SET n_items=? WHERE rowid=? AND n_items IS NULL",
                    (val, rowid))
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    print(f"回填 {len(todo)} 行；行数 {before} -> {after}（必须相等：只补列，不增删行）")
    if before != after:
        print("FAIL: 回填改了行数——这一列的修复不该增删行", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
