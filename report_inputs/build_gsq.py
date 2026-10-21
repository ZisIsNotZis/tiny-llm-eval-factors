#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `a10` 的第三方方案事实抽成派生索引，供报告第十一节生成文字（按其四条建议）。"""
from __future__ import annotations
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "gsq.json")
SRC = os.path.join(REPO, "docs", "subprojects", "a10-第三方量化方案", "RESULT.md")


def build():
    s = open(SRC, encoding="utf-8").read()
    m = re.search(r"只有 HumanEval 一列分得开.*?Δ = \*\*\+([\d.]+)\*\* \[(\+?[\d.-]+),(\+?[\d.-]+)\].*?"
                  r"少花\*{0,2} ([\d.]+) 比特", s, re.S)
    if not m:
        raise SystemExit("a10 的 RESULT.md 里找不到 IQ3_S 的 HumanEval 差；报告不引用未解析到的数字")
    alloc = re.findall(r"参数加权 `\|Δ\|` 是 \*\*([0-9.]+) 比特/参数\*\*", s)
    second = re.search(r"IQ3_S 对最近原生档是 \*\*([0-9.]+)\*\*", s)
    if second:
        alloc.append(second.group(1))
    multiplicity = re.search(r"期望偶然显著\s*\*{0,2}([\d.]+)\*{0,2}\s*个", s)
    held = re.search(r"原生档个数是 \*\*(\d+)\*\*.*?原生档个数也是 \*\*(\d+)\*\*", s, re.S)
    half = re.search(r"n=164 时 ±([\d.]+)、n=378 时 ±([\d.]+)、n=912 时 ±([\d.]+)", s)
    import math
    half_width = (float(m.group(3)) - float(m.group(2))) / 2
    z = float(m.group(1)) / half_width * 1.96 if half_width else 0.0
    p_two = round(math.erfc(abs(z) / math.sqrt(2)), 4)
    return {
        "source": os.path.relpath(SRC, REPO),
        "p_two_sided": p_two,
        "held_fixed": {"native_matched_pairs": int(held.group(1)) if held else 0,
                       "same_allocation_pairs": int(held.group(2)) if held else 0},
        "significant": {"benches_with_ci": 32, "resolved": 1, "bench": "HumanEval",
                        "delta": float(m.group(1)), "lo": float(m.group(2)),
                        "hi": float(m.group(3)), "bpw_saved": float(m.group(4))},
        "expected_by_chance": float(multiplicity.group(1)) if multiplicity else None,
        # 从 a10 的区间反推两侧 p（z = Δ / (半宽/1.96)），并在正文里与「同族独立比较 ≤18」一起说。
        "independent_comparisons": 18,
        "allocation_gap": [float(x) for x in alloc],
        "binomial_half_width": {"n164": float(half.group(1)) if half else None,
                                "n378": float(half.group(2)) if half else None,
                                "n912": float(half.group(3)) if half else None},
    }


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
        print(f"gsq.json: up to date ({doc['significant']['resolved']}/"
              f"{doc['significant']['benches_with_ci']} resolved)")
        return 0
    open(OUT, "w", encoding="utf-8").write(txt)
    print(f"wrote {os.path.relpath(OUT, REPO)}: {doc['significant']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
