#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：报告必须过滤被取代的行，否则同一个格会以两个分数出现两次。

判据用 mktables 自己的查询（`query_cells_by`），不另抄一份 SQL，并且**按协议串分组**
（`extra="protocol"`）：默认的 `extra=""` 把一个模型的同一个格按 (model, bench) 收敛成一个键，
后读到的行直接盖掉先读到的——旧语料的值会**静默**压掉新值，看不出重复。所以这里必须
把协议串留在键里才能观测到「同一格两个分数」。
过滤后同 (model, 语言, 协议) 只能有一个分数；`MKT_NO_SUPERSEDED_FILTER=1` 时同一个
(model, 语言) 必然多于一个分数——这说明那条 `superseded_by IS NULL` 在承重，不是装饰。
报告层的对应守卫是 `checks/report_check.py` 的行标签唯一性与多值检查。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PROBE = """
import sys
sys.path.insert(0, ".wrapup")
import mktables
cells = mktables.query_cells_by("bench_family='humaneval-multipl-e'", extra="protocol")
for (model, proto), per_lang in cells.items():
    for lang in per_lang:
        print(model + "\\t" + lang + "\\t" + proto)
"""


def probe(no_filter: bool):
    env = dict(os.environ)
    env.pop("MKT_NO_SUPERSEDED_FILTER", None)
    if no_filter:
        env["MKT_NO_SUPERSEDED_FILTER"] = "1"
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=str(REPO), env=env,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stderr.strip()[:300]
    return {tuple(ln.split("\t")) for ln in r.stdout.splitlines() if ln.strip()}, ""


def superseded_py_cells():
    """库里被取代的 py 行：(model, 协议串)。它们是过滤后必须消失的那些键。"""
    import sqlite3
    con = sqlite3.connect(f"file:{REPO / 'experiments.sqlite'}?mode=ro", uri=True)
    out = {(m, p) for m, p in con.execute(
        "SELECT model, protocol FROM experiments WHERE superseded_by IS NOT NULL "
        "AND language='py'")}
    return out


def main() -> int:
    superseded = superseded_py_cells()
    if not superseded:
        print("FAIL: 库里没有 superseded 的 py 行，这条控制没有观测对象")
        return 1

    filtered, err = probe(no_filter=False)
    if filtered is None:
        print(f"FAIL: 过滤模式下查询失败：{err}")
        return 1
    kept = {k for k in filtered if k[1] == "multipl_e_py"}
    if not kept:
        print("FAIL: 过滤后一个 py 格都没有，这条控制没有观测对象")
        return 1
    leaked = {k for k in kept if (k[0], k[2]) in superseded}
    print(f"1) 过滤 superseded       : {len(kept)} 个 py 格，其中属于被取代行的 {len(leaked)} 个（要 0）")
    if leaked:
        print(f"FAIL: 过滤后仍有被取代的 py 行出现在表里，例如 {sorted(leaked)[0]}")
        return 1

    unfiltered, err = probe(no_filter=True)
    if unfiltered is None:
        print(f"FAIL: 不过滤模式下查询失败：{err}")
        return 1
    present = {k for k in unfiltered if k[1] == "multipl_e_py" and (k[0], k[2]) in superseded}
    print(f"2) 不过滤（负控）        : 被取代的行出现 {len(present)} 个（要 {len(superseded)}）")
    if len(present) != len(superseded):
        print(f"FAIL: 去掉过滤后被取代的行没有全部回到表里（{len(present)}/{len(superseded)}）"
              f"——说明这条过滤不是在承重，或者键的粒度不对")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
