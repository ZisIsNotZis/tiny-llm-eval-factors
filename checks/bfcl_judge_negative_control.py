#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：§14「换判分器会改结论」由改判计数决定，不是写死的。

两例：1) 忠实（2788 改判）→ 说第一名换人、间距不可沿用；
      2) 把改判计数改成 0 → 必须改口成「两套判分器给出相同判定、与判分器无关」。
"""
from __future__ import annotations
import json, shutil, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import make_report

BASE = REPO / "report_inputs" / "bfcl_judge.json"

def rendered(path):
    saved = make_report.BFCL_JUDGE
    make_report.BFCL_JUDGE = str(path)
    try:
        return make_report.bfcl_judge_html()
    finally:
        make_report.BFCL_JUDGE = saved

def main():
    base = rendered(BASE)
    if not ("换判分器会改结论" in base and "不可沿用" in base):
        print("FAIL: 基线没有按改判计数来写"); return 1
    print("1) baseline (2788 reclassified) : says 换判分器会改结论: True")
    tmp = Path(tempfile.mkdtemp(prefix="bfcl-judge-negative-control-"))
    try:
        d = json.loads(BASE.read_text(encoding="utf-8"))
        d["reclassified"] = {"to_pass": 0, "to_fail": 0, "up_share": 0.0}
        p = tmp / "zero.json"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        t = rendered(p)
        changed = ("与判分器无关" in t and "换判分器会改结论" not in t)
        print(f"2) counts set to 0             : says 与判分器无关: {changed}")
        if not changed:
            print("FAIL: 改判计数改成 0 后正文仍说换判分器会改结论"); print(t[:400]); return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: 「会改结论 / 与判分器无关」的措辞由改判计数决定")
    return 0

if __name__ == "__main__":
    sys.exit(main())
