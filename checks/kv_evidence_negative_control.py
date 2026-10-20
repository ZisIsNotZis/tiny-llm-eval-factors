#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：第五节「逐题在翻」由丢/得计数决定，不是写死的。

两例：
  1. 忠实：f16→q4_0 丢 15 / 得 11 → 正文必须说「逐题判定在双向翻动」且给出两个数；
  2. 把四类计数全改成 0 → 正文必须改口成「逐题判定完全相同（丢 0 / 得 0）」，不得再声称翻动。
"""
from __future__ import annotations
import json, shutil, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import make_report

BASE = REPO / "report_inputs" / "kv_evidence.json"

def rendered(path):
    saved = make_report.KV_EVIDENCE
    make_report.KV_EVIDENCE = str(path)
    try:
        return make_report.kv_evidence_html()
    finally:
        make_report.KV_EVIDENCE = saved

def main():
    base = rendered(BASE)
    if not ("丢 15 / 得 11" in base and "双向翻动" in base):
        print("FAIL: 基线没有按逐题丢/得来写"); return 1
    print("1) baseline (lose15/gain11) : says 逐题在翻 with the counts: True")
    tmp = Path(tempfile.mkdtemp(prefix="kv-negative-control-"))
    try:
        d = json.loads(BASE.read_text(encoding="utf-8"))
        for k in d["pairs"]:
            d["pairs"][k] = {"lose": 0, "gain": 0}
        p = tmp / "zero.json"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        t = rendered(p)
        changed = ("丢 0 / 得 0" in t and "双向翻动" not in t
                   and "测不到 KV 精度的影响" in t)
        print(f"2) all counts set to 0     : says 无差异 and drops 翻动: {changed}")
        if not changed:
            print("FAIL: 计数改成 0 后正文仍说逐题在翻——说明这段写死了"); print(t[:400]); return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: 逐题翻动/无差异的措辞由丢/得计数决定")
    return 0

if __name__ == "__main__":
    sys.exit(main())
