#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `a01` 的「两档配对差」事实抽成派生索引，供报告的第一节引用。

报告里那句「Qwen3.5-2B 在 3.96→4.11 掉点，因为两个方案不同」原先是一段写死的因果叙述；实测的
配对区间否定了一半（只有 HumanEval+ 的区间不含 0，其余跨 0）。派生数字是引用而不是存储事实，
所以这里只从 `docs/subprojects/a01-量化位宽/RESULT.md` 的事实 `b1-heplus-only` 里取数，报告据此
生成文字——把那条事实的区间改成跨 0，报告就会改口说「无显著差异」。

    python3 report_inputs/build_paired_deltas.py           # 重写 paired_deltas.json
    python3 report_inputs/build_paired_deltas.py --check   # 与现有 json 比对
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "paired_deltas.json")
FACT_ID = "b1-heplus-only"
SOURCE_GLOB = os.path.join(REPO, "docs", "subprojects", "a01-*", "RESULT.md")

# 报告里的基准名（含 a01 事实里的写法）
METRIC_KEYS = {
    "HumanEval+": "humaneval_plus", "HumanEval": "humaneval",
    "MBPP+": "mbpp_plus", "MBPP": "mbpp", "MMLU": "mmlu", "ARC-c": "arc_challenge",
    "TruthfulQA": "truthfulqa_mc2", "GSM8K": "gsm8k", "IFEval": "ifeval",
}
PAIR_RE = re.compile(r"([0-9.]+)（UD-([A-Za-z0-9_]+)）")
CI_RE = re.compile(r"\[([+−-]?[0-9.]+)[,，]\s*([+−-]?[0-9.]+)\]")
FACT_RE = re.compile(r"^#{2,6}\s+" + FACT_ID + r"\s*::\s*(.+)$")


def num(tok):
    return float(tok.replace("−", "-").replace("+", ""))


def parse(text):
    """从该条事实的正文里取：两档位宽 + 每个基准的 (delta, lo, hi) 与是否显著。"""
    pairs = PAIR_RE.findall(text)
    if len(pairs) < 2:
        return None
    low = {"bpw": num(pairs[0][0]), "quant": "UD-" + pairs[0][1]}
    high = {"bpw": num(pairs[1][0]), "quant": "UD-" + pairs[1][1]}

    metrics = []
    for segment in re.split(r"[；;、]", text):
        names = [n for n in METRIC_KEYS if n in segment]
        if not names:
            continue
        name = max(names, key=len)             # 「HumanEval+」优先于「HumanEval」
        ci = CI_RE.search(segment)
        if not ci:
            continue
        lo, hi = num(ci.group(1)), num(ci.group(2))
        before = segment[:ci.start()]
        deltas = re.findall(r"[+−-][0-9.]+", before)
        if not deltas:
            continue
        delta = num(deltas[-1])
        metrics.append({
            "metric": name, "key": METRIC_KEYS[name],
            "delta": delta, "lo": lo, "hi": hi,
            "significant": not (lo <= 0.0 <= hi),
        })
    return low, high, metrics


def scan():
    paths = sorted(glob.glob(SOURCE_GLOB))
    if not paths:
        return None, None
    path = paths[0]
    for line in open(path, encoding="utf-8"):
        m = FACT_RE.match(line.rstrip("\n"))
        if m:
            parsed = parse(m.group(1))
            if not parsed:
                return None, None
            low, high, metrics = parsed
            return {
                "source": os.path.relpath(path, REPO),
                "fact": FACT_ID,
                "pair": {"family": "Qwen3.5-2B", "low": low, "high": high},
                "metrics": metrics,
            }, None
    return None, path


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    doc, missing = scan()
    if doc is None:
        print(f"FAIL: {missing or SOURCE_GLOB} 里没有可解析的事实 {FACT_ID}", file=sys.stderr)
        return 1
    text = dump(doc)
    if "--check" in argv:
        try:
            have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is missing", file=sys.stderr)
            return 1
        if have != text:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is stale; rerun without --check",
                  file=sys.stderr)
            return 1
        print(f"paired_deltas.json: up to date ({len(doc['metrics'])} metrics, "
              f"{sum(1 for m in doc['metrics'] if m['significant'])} significant)")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    sig = [m["metric"] for m in doc["metrics"] if m["significant"]]
    print(f"wrote {os.path.relpath(OUT, REPO)}: {len(doc['metrics'])} metrics, "
          f"significant: {sig or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
