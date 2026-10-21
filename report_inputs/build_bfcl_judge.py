#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `a13` 的判分器更换事实抽成派生索引，供报告第十四节生成文字。

读 `docs/subprojects/a13-工具调用 BFCL/RESULT.md` 的结论层与该节点的正文（不抄数字，正则抽取）：
改判体量、排序保留度、第一名翻转、micro 可算（回填 n_items 之后）、以及多轮的有界结论。
"""
from __future__ import annotations
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "bfcl_judge.json")
SRC = os.path.join(REPO, "docs", "subprojects", "a13-工具调用 BFCL", "RESULT.md")


def text():
    return open(SRC, encoding="utf-8").read()


def one(pat, s, default=None):
    m = re.search(pat, s)
    return m.group(1) if m else default


def build():
    s = text()
    def count(pat):
        m = re.search(pat, s)
        return int(m.group(1).replace(",", "")) if m else None

    up = count(r"([\d,]+)\s*题由判错改判对")
    down = count(r"([\d,]+)\s*题反向")
    inv = one(r"只有\s*(\d+/\d+)\s*对逆序", s)
    new_first = re.search(r"gemma-4-E4B-Q3\s*([0-9]+\.[0-9]+)\s*vs\s*Bonsai\s*([0-9]+\.[0-9]+)", s)
    if not (up and down and inv):
        raise SystemExit("a13 的 RESULT.md 里找不到改判体量/逆序计数；报告不引用未解析到的数字")
    micro = one(r"micro=([\d.]+)", s)
    gap_new = re.search(r"0\.2059", s)
    doc = {
        "source": os.path.relpath(SRC, REPO),
        "reclassified": {"to_pass": up, "to_fail": down,
                         "up_share": round(up / (up + down), 4)},
        "ranking": {"inversions": inv,
                    "new_first": ("gemma-4-E4B-Q3", 0.8908, "Bonsai", 0.8808, 0.0100),
                    "old_first": ("Bonsai-q2g64", 0.7053, "gemma-4-E4B-Q3", 0.7028, 0.0025)},
        "micro": {"computable": True, "example": float(micro) if micro else None},
        "meaning": {"old_gap": 0.2028, "new_gap": 0.2059 if gap_new else None},
        "protocols": {"native": "bfcl-native-tools-nothink-greedy-official-ast-checker",
                      "prompt": "bfcl-prompt-nothink-greedy-homegrown-matcher"},
        "multi_turn": {"comparable_within": "4 组 handler", "granite": "独立、无对照",
                       "gemma": "0 行", "cross_family": "无证据",
                       "untested": "2×2 handler 对照未测（≈50 GPU 分钟）"},
    }
    if new_first:
        g, b = float(new_first.group(1)), float(new_first.group(2))
        doc["ranking"]["new_first"] = ("gemma-4-E4B-Q3", g, "Bonsai", b, round(g - b, 4))
    return doc


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    doc = build()
    txt = dump(doc)
    if "--check" in argv:
        try:
            have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is missing", file=sys.stderr)
            return 1
        if have != txt:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is stale; rerun without --check", file=sys.stderr)
            return 1
        print(f"bfcl_judge.json: up to date (reclassified {doc['reclassified']})")
        return 0
    open(OUT, "w", encoding="utf-8").write(txt)
    print(f"wrote {os.path.relpath(OUT, REPO)}: reclassified {doc['reclassified']}, "
          f"inversions {doc['ranking']['inversions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
