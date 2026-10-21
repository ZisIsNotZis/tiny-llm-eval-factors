#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据库完整性与清洁度检查（只读，不写库）。

`PRAGMA integrity_check` 只说文件结构没坏，不说数据合不合规：必填字段为空、取值越界、
同一测量身份重复入库，都是结构完好但数据脏。这里把两者一起查，并给出规模数字。

    python3 checks/db_check.py            # 全部检查，任一失败退出 1
    python3 checks/db_check.py --quiet    # 只打印结论与规模

`DB_CHECK_DB` 只给负控用（指向一份故意弄脏的副本）；默认检查仓库里那个库。

退出码：0 全绿；1 有违规；2 库不存在。
"""
from __future__ import annotations

import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("DB_CHECK_DB") or os.path.join(REPO, "experiments.sqlite")

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

    have_cols = {r[1] for r in con.execute("PRAGMA table_info(experiments)")}
    if "superseded_by" not in have_cols:
        problems.append("schema 未迁移：缺 superseded_by 列（跑 python3 migrate_db.py）")
        print("FAIL:")
        for p in problems:
            print("  -", p)
        return 1

    # `superseded_by` 是**指针**，不是自由文本：它要么为空，要么指向本表已存在的一行的
    # protocol 串。悬空指针等于「某格被一个不存在的测量取代了」，比没有指针更坏。
    # 指向是**按行**认的：协议串（如 `multipl-e-raw-greedy-768;corpus=…`）在多个模型上重复
    # 出现，所以判据是「同一 model + _bench + language 下，存在一行协议串等于它、且自己没被
    # 取代」；单看协议串在不在表里会被多个模型同时满足，等于没查。
    dangling = con.execute(
        "SELECT count(*) FROM experiments AS a WHERE a.superseded_by IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM experiments AS b WHERE b.model=a.model "
        "AND b._bench=a._bench AND b.language IS a.language "
        "AND b.protocol=a.superseded_by AND b.superseded_by IS NULL)").fetchone()[0]
    if dangling:
        problems.append(f"superseded_by: {dangling} 行指向的取代行不存在（悬空指针）")
    n_superseded = con.execute(
        "SELECT count(*) FROM experiments WHERE superseded_by IS NOT NULL").fetchone()[0]

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
    print(f"  superseded       : {n_superseded} row(s) point at the measurement that replaced them")
    if problems:
        print("FAIL:")
        for p in problems:
            print("  -", p)
        return 1
    print("PASS: integrity and cleanliness")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
