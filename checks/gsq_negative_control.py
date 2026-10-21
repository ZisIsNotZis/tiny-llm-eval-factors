#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：§11「有 1 格分得开」由计数决定。两例：基线说「值得记下的信号」；改成 0 则说「全部测不出」。"""
from __future__ import annotations
import json, shutil, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import make_report
BASE = REPO / "report_inputs" / "gsq.json"

def rendered(path):
    saved = make_report.GSQ
    make_report.GSQ = str(path)
    try:
        return make_report.gsq_html()
    finally:
        make_report.GSQ = saved

def main():
    base = rendered(BASE)
    if not ("只有 1 个分得开" in base and "不是方案红利" in base):
        print("FAIL: 基线没有按 1/32 来写"); return 1
    print("1) baseline (1 of 32 resolved) : says 信号不是红利: True")
    tmp = Path(tempfile.mkdtemp(prefix="gsq-negative-control-"))
    try:
        d = json.loads(BASE.read_text(encoding="utf-8"))
        d["significant"]["resolved"] = 0
        p = tmp / "zero.json"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        t = rendered(p)
        changed = ("全部测不出差异" in t and "不是方案红利" not in t)
        print(f"2) resolved set to 0           : says 全部测不出: {changed}")
        if not changed:
            print("FAIL: 把 1 改成 0 后正文仍说分得开"); print(t[:400]); return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: 分得开/全部测不出的措辞由计数决定")
    return 0

if __name__ == "__main__":
    sys.exit(main())
