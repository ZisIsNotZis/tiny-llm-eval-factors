#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：§6「厂商档是绝对丢题」由逐格丢题数决定；全改成 0 必须改口成「与固定协议无差」。"""
from __future__ import annotations
import json, shutil, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import make_report
BASE = REPO / "report_inputs" / "sampling_collapse.json"

def rendered(path):
    saved = make_report.SAMPLING_COLLAPSE
    make_report.SAMPLING_COLLAPSE = str(path)
    try: return make_report.sampling_collapse_html()
    finally: make_report.SAMPLING_COLLAPSE = saved

def main():
    base = rendered(BASE)
    if not ("绝对丢题" in base and "不是常数" in base):
        print("FAIL: 基线没有按丢题数来写"); return 1
    print("1) baseline (losses -17..-36) : says 绝对丢题: True")
    tmp = Path(tempfile.mkdtemp(prefix="sampling-collapse-neg-"))
    try:
        d = json.loads(BASE.read_text(encoding="utf-8"))
        for x in d["mpl_losses"]: x["lost"] = 0; x["to"] = x["from"]
        p = tmp / "zero.json"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        t = rendered(p)
        changed = ("差距为零" in t and "绝对丢题" not in t)
        print(f"2) losses set to 0            : says 无差: {changed}")
        if not changed:
            print("FAIL: 丢题数改成 0 后正文仍说绝对丢题"); print(t[:300]); return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: 措辞由逐格丢题数决定")
    return 0

if __name__ == "__main__":
    sys.exit(main())
