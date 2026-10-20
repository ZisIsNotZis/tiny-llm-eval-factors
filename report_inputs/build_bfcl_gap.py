#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「BFCL 汇总里 micro 与 macro 的最大差」做成随仓库分发的派生索引。

为什么不在报告里现算：`.wrapup/*_summary.jsonl` 是**持续变动**的输入（各子项目随跑随提交），
报告若直接读它，任何一次新 summary 入库都会改变 `report.html` 的字节，干净 clone 于是与提交的
报告不一致。派生索引把这一步冻结在提交里：summary 变了要显式重建索引，报告本身不跟着动。

    python3 report_inputs/build_bfcl_gap.py           # 重写 bfcl_gap.json
    python3 report_inputs/build_bfcl_gap.py --check   # 与现有 json 比对
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "bfcl_gap.json")


def build():
    best = None
    for path in sorted(glob.glob(os.path.join(REPO, ".wrapup", "*_summary.jsonl"))):
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            per = r.get("per_category")
            if not isinstance(per, dict) or not per or r.get("score") is None:
                continue
            accs = [v["acc"] for v in per.values()
                    if isinstance(v, dict) and v.get("acc") is not None]
            if not accs:
                continue
            macro = sum(accs) / len(accs)
            gap = abs(r["score"] - macro)
            if best is None or gap > best["gap"]:
                best = {"gap": round(gap, 6), "micro": r["score"], "macro": round(macro, 6),
                        "model": r.get("model"), "file": os.path.basename(path),
                        "categories": len(accs)}
    if best is None:
        raise SystemExit("没有任何 BFCL summary 带 per_category；报告不印这一项")
    return best


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    doc = build()
    text = dump(doc)
    if "--check" in argv:
        try:
            have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is missing", file=sys.stderr)
            return 1
        if have != text:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is stale against the summaries; "
                  f"rerun without --check", file=sys.stderr)
            return 1
        print(f"bfcl_gap.json: up to date (gap {doc['gap']:.4f})")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}: gap {doc['gap']:.4f} "
          f"({doc['model']} micro {doc['micro']:.4f} vs macro {doc['macro']:.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
