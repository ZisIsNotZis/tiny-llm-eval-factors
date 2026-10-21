#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：第四节「多数对无法放在同一总比特上」由计数决定，不是写死的。

两例：1) 忠实 → 说 18/22 对超界、预算比较；2) 把 over_bound 改成 0 → 必须改口成「都能钉住、可以读成分配比较」。
"""
from __future__ import annotations
import json, shutil, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import make_report

BASE = REPO / "report_inputs" / "moe_feasibility.json"

def rendered(path):
    saved = make_report.MOE_FEASIBILITY
    make_report.MOE_FEASIBILITY = str(path)
    try:
        return make_report.moe_feasibility_html()
    finally:
        make_report.MOE_FEASIBILITY = saved

def main():
    base = rendered(BASE)
    if not ("18 对无法放在同一总比特上" in base and "预算比较" in base):
        print("FAIL: 基线没有按 18 对超界来写"); return 1
    print("1) baseline (18 over bound) : says 预算比较: True")
    tmp = Path(tempfile.mkdtemp(prefix="moe-negative-control-"))
    try:
        d = json.loads(BASE.read_text(encoding="utf-8"))
        d["over_bound"] = 0
        p = tmp / "zero.json"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        t = rendered(p)
        changed = ("都能放在同一总比特上" in t and "无法放在同一总比特上" not in t
                   and "预算比较" not in t)
        print(f"2) over_bound set to 0     : text flips to 分配比较: {changed}")
        if not changed:
            print("FAIL: 把 18 改成 0 后正文仍说预算比较——说明这段写死了"); print(t[:400]); return 1
        # 3) 把 HumanEval+ 的第三臂差改成「预算项」的 0.0086 → 文字必须说「差异可由预算解释」/不再是分配效应
        d3 = json.loads(BASE.read_text(encoding="utf-8"))
        for x in d3["third_arm"]["deltas"]:
            if x["bench"] == "HumanEval+":
                x["delta"] = d3["third_arm"]["budget_humaneval_plus"]
        p3 = tmp / "budget.json"
        p3.write_text(json.dumps(d3, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        t3 = rendered(p3)
        changed = ("不是预算能解释的" in base and "不是预算能解释的" not in t3
                   and "可由预算解释" in t3)
        print(f"3) HumanEval+ set to budget : text says 可由预算解释: {changed}")
        if not changed:
            print("FAIL: 把 +0.4695 改成 0.0086 后正文仍说「不是预算能解释的」"); print(t3[:500]); return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: 预算比较/分配比较与「预算能否解释」的措辞都由索引里的数字决定")
    return 0

if __name__ == "__main__":
    sys.exit(main())
