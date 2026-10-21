#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：第七、八节的句子由 a07 的派生索引决定，不是写死的。

两例（都在内存里改索引，不碰文件）：
  1. 忠实：索引说什么就写什么——地板 7 对全 164/164、投机臂 91/164 相同 / 73 不同、
     分数 52 → 49、速度 423.45 → 534.88（+26.3%）；且**不许**再出现已撤回的说法
     （「不伤质量」「分数随草稿深度几乎不变」）。
  2. 改数：把「差异 73」改成 0、把两臂通过题数改成相等 → 正文必须改口成「逐字节相同」
     且不再说「必须每次重测」；把地板改成有差异 → 构建必须直接失败（不是降级成一句话）。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import make_report

BASE = REPO / "report_inputs" / "spec_decode.json"
RETRACTED = ["不伤质量", "分数随草稿深度几乎不变", "可以放心开"]


def with_index(doc):
    """临时把索引换成 doc，渲染两节，再换回来。"""
    saved = make_report._spec
    make_report._spec = lambda: doc
    try:
        return make_report.spec_speed_html() + make_report.spec_quality_html()
    finally:
        make_report._spec = saved


def main() -> int:
    doc = json.loads(BASE.read_text(encoding="utf-8"))
    base = with_index(doc)
    e = doc["spec_effect"]

    checks = [
        ("地板 164/164 且差异 0", "164/164" in base and f"差异 {doc['byte_floor']['differing_total']}" in base),
        (f"投机效应 {e['identical']}/{e['n_items']} 相同、{e['differing']} 不同",
         f"{e['identical']} 条逐字节相同" in base and f"{e['differing']} 条不同" in base),
        (f"分数 {e['pass_none']} → {e['pass_spec']}", f"{e['pass_none']}/{e['items_none']}" in base
         and f"{e['pass_spec']}/{e['items_spec']}" in base),
        ("速度 n0→n2 与百分比",
         f"{doc['speed_08b']['depth0_tok_s']:.2f}" in base and f"{doc['speed_08b']['depth2_tok_s']:.2f}" in base
         and f"+{doc['speed_08b']['depth2_pct']:.1f}%" in base),
        ("两种显存口径都在", str(doc["memory"]["head_bytes_08b"]) in base.replace(",", "")
         and "+96 MiB" in base and "+376 MiB" in base),
        ("说清质量列不能照抄", "必须每次重测" in base),
        ("撤回的说法一个都不在", not any(x in base for x in RETRACTED)),
    ]
    for name, ok in checks:
        print(f"1) {name}: {ok}")
    if not all(ok for _n, ok in checks):
        print("FAIL: 基线正文与索引不一致")
        return 1

    # 2a) 把分歧改成 0：正文必须改口
    same = copy.deepcopy(doc)
    same["spec_effect"]["differing"] = 0
    same["spec_effect"]["identical"] = same["spec_effect"]["n_items"]
    same["spec_effect"]["pass_spec"] = same["spec_effect"]["pass_none"]
    t2 = with_index(same)
    flipped = ("逐字节相同" in t2 and "0 条不同" in t2 and "必须每次重测" not in t2)
    print(f"2) 差异改成 0 → 改口成「逐字节相同」且不再说必须重测: {flipped}")
    if not flipped:
        print("FAIL: 差异改成 0 后正文仍说 73 条不同——这一节写死了")
        return 1

    # 2b) 地板改成有差异：构建必须失败
    dirty = copy.deepcopy(doc)
    dirty["byte_floor"]["all_identical"] = False
    try:
        with_index(dirty)
    except SystemExit as exc:
        print(f"3) 地板改成「有差异」→ 构建失败并点名: True（{str(exc)[:60]}…）")
        return 0
    print("FAIL: 地板不为 0 时构建没有失败——「地板 0」这句话没有守卫")
    return 1


if __name__ == "__main__":
    sys.exit(main())
