#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据库完整性与清洁度检查（只读，不写库）。

`PRAGMA integrity_check` 只说文件结构没坏，不说数据合不合规：必填字段为空、取值越界、
同一测量身份重复入库，都是结构完好但数据脏。这里把两者一起查，并给出规模数字。

    python3 checks/db_check.py            # 全部检查，任一失败退出 1
    python3 checks/db_check.py --quiet    # 只打印结论与规模

退出码：0 全绿；1 有违规；2 库不存在。
"""
from __future__ import annotations

import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "experiments.sqlite")

sys.path.insert(0, REPO)
from migrate_db import MEASUREMENT_IDENTITY  # noqa: E402  同一份测量身份定义，不另抄一份

# 必填文本字段：空字符串或纯空白都是缺失
REQUIRED_TEXT = ["model", "cache_type_k", "cache_type_v", "reasoning", "spec_type",
                 "temp", "top_p", "top_k", "min_p", "presence_penalty", "_bench"]

# 取值域：列为 None 的表达式表示「非 NULL 时必须满足」
RANGES = [
    ("_score 必须落在 [0,1]", "_score IS NOT NULL AND (_score < 0 OR _score > 1)"),
    ("_bad_rate 必须在 [0,1)", "_bad_rate IS NOT NULL AND (_bad_rate < 0 OR _bad_rate >= 1)"),
    ("_score+_bad_rate 不得超过 1", "_bad_rate IS NOT NULL AND _score IS NOT NULL "
                                   "AND _score > 1 - _bad_rate + 1e-9"),
    ("_wall_time 不得为负", "_wall_time IS NOT NULL AND _wall_time < 0"),
    ("__quant_ratio 必须落在 [0,1]", "__quant_ratio IS NOT NULL AND (__quant_ratio < 0 "
                                     "OR __quant_ratio > 1 + 1e-9)"),
    ("__activation_size 不得超过 __size", "__activation_size IS NOT NULL AND __size IS NOT NULL "
                                          "AND __activation_size > __size + 1e-9"),
    ("布尔列只能取 0/1", " OR ".join(f"{c} NOT IN (0,1)" for c in
                                     ("__mtp", "__qat", "__instruct", "__omni", "__think",
                                      "__flash", "__code"))),
]


def main(argv):
    if not os.path.exists(DB):
        print(f"FAIL: 数据库不存在：{DB}", file=sys.stderr)
        return 2
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    quiet = "--quiet" in argv
    problems = []

    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        problems.append(f"integrity_check: {integrity}")
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        problems.append(f"foreign_key_check: {len(fk)} 行")

    for col in REQUIRED_TEXT:
        n = con.execute(f"SELECT count(*) FROM experiments "
                        f"WHERE {col} IS NULL OR length(trim({col})) = 0").fetchone()[0]
        if n:
            problems.append(f"{col}: {n} 行缺失")

    for label, cond in RANGES:
        n = con.execute(f"SELECT count(*) FROM experiments WHERE {cond}").fetchone()[0]
        if n:
            problems.append(f"{label}: {n} 行越界")

    ident = ", ".join(MEASUREMENT_IDENTITY)
    dup_groups, dup_rows = con.execute(
        f"SELECT count(*), coalesce(sum(c - 1), 0) FROM ("
        f" SELECT count(*) AS c FROM experiments GROUP BY {ident} HAVING count(*) > 1)"
    ).fetchone()

    rows = con.execute("SELECT count(*) FROM experiments").fetchone()[0]
    n_mpl = con.execute("SELECT count(DISTINCT model || '|' || protocol || '|' || language) "
                        "FROM experiments WHERE bench_family='humaneval-multipl-e' "
                        "AND _score IS NOT NULL").fetchone()[0]
    print(f"db: {os.path.relpath(DB, REPO)}")
    print(f"  integrity        : {integrity}")
    print(f"  foreign keys     : {len(fk)} issue(s)")
    print(f"  required fields  : {len(REQUIRED_TEXT)} columns checked")
    print(f"  value ranges     : {len(RANGES)} rules checked")
    print(f"  duplicate cells  : {dup_groups} group(s), {dup_rows} extra row(s) "
          f"(identity = {len(MEASUREMENT_IDENTITY)} columns)")
    print(f"  size             : {rows} rows, {n_mpl} MultiPL-E cells "
          f"(model|protocol|language)")
    if problems:
        print("FAIL:")
        for p in problems:
            print("  -", p)
        return 1
    print("PASS: integrity and cleanliness")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
