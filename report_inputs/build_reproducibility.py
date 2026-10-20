#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `i01` 的「可复现性边界」两条事实抽成派生索引，供报告生成那一节。

两条事实是严格分开的、极易被混成一个数：

  * `res32`：**输入相同**（同一提示集哈希 + 同一后处理版本）时，贪心 chat 的跨 run 地板是 0 道题
    （MultiPL-E 161/161 相同、翻转 0、Jaccard 1.0；EvalPlus 164/164 相同）。
  * `res29`：**输入变了**（提示集被重建/删除）时，同一个 cell 能出现 16 题双向翻转、±16/161≈0.10。

报告要按这两条分别写，所以这里只从 `i01/RESULT.md` 的事实正文里抽数（不手抄），抽不到就报错，
绝不填 0 或默认值。

    python3 report_inputs/build_reproducibility.py           # 重写 reproducibility.json
    python3 report_inputs/build_reproducibility.py --check   # 与现有 json 比对
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "reproducibility.json")
SOURCE_GLOB = os.path.join(REPO, "docs", "subprojects", "i01-*", "RESULT.md")

HEAD_RE = re.compile(r"^#{2,6}\s+(res\d+)\b\s*(.*)$")
# 适用条件：任何两次 run 只有在提示集哈希与后处理版本都被钉住时才可比
CONDITION_RE = re.compile(r"只有在?\*{0,2}提示集哈希\s*\+\s*后处理版本\*{0,2}都")
FLOOR_RE = re.compile(r"\*\*(\d+)/\1 题完全相同、上翻 (\d+)、下翻 (\d+)、分数摆动 ([\d.]+)、Jaccard ([\d.]+)\*\*")
# EvalPlus 那句是「（46/164 三次，上翻 0 下翻 0，Jaccard 1.0）」：46 是通过数，164 才是题数，
# 所以 identical 取分母。
EVALPLUS_RE = re.compile(r"（(\d+)/(\d+) 三次，上翻 (\d+) 下翻 (\d+)，Jaccard ([\d.]+)）")
FLOOR_RULE_RE = re.compile(r"同一提示集哈希 \+ 同一后处理版本下，任何非零跨 run 差异都不是噪声")
FLIPS_RE = re.compile(r"\*\*(\d+) 题翻转（(\d+) 上 / (\d+) 下，净 \+(\d+)）\*\*")
AMP_RE = re.compile(r"\*\*±(\d+)/(\d+)（≈([\d.]+)）\*\*")
TEXT_DIFF_RE = re.compile(r"\*\*(\d+)/(\d+)\*\* 题上文本不同")
TOKEN_DIFF_RE = re.compile(r"\*\*(\d+) 题是 token 不同\*\*")


def read_facts(path):
    """{fact_id: 正文} —— 只按标题切段，不做别的解释。"""
    facts, cur = {}, None
    for line in open(path, encoding="utf-8"):
        m = HEAD_RE.match(line)
        if m:
            cur = m.group(1)
            facts[cur] = ""
            continue
        if line.startswith("# "):
            cur = None
            continue
        if cur:
            facts[cur] += line
    return facts


def parse(floor_text, change_text, all_text):
    if not CONDITION_RE.search(change_text):
        raise SystemExit("i01 的事实里找不到适用条件（「只有提示集哈希 + 后处理版本都…才可比」）；"
                         "报告不能在没有条件的情况下引用这个幅度")
    m_floor = FLOOR_RE.search(floor_text)
    m_eval = EVALPLUS_RE.search(floor_text)
    if not (m_floor and m_eval):
        raise SystemExit("i01 的 res32 里找不到两族地板数字（「N/N 题完全相同、上翻 0…」）")
    rule = FLOOR_RULE_RE.search(floor_text)
    if not rule:
        raise SystemExit("i01 的 res32 里找不到判读规则（「同一提示集哈希 + 同一后处理版本下…」）")
    m_flips = FLIPS_RE.search(change_text)
    m_amp = AMP_RE.search(change_text)
    m_text = TEXT_DIFF_RE.search(change_text)
    m_tok = TOKEN_DIFF_RE.search(change_text)
    if not (m_flips and m_amp and m_text and m_tok):
        raise SystemExit("i01 的 res29 里找不到翻转/幅度/文本差数字")
    n = int(m_amp.group(2))
    return {
        "source": None,
        "floor": {
            "fact": "res32",
            "harnesses": [
                {"name": "MultiPL-E chat", "n": int(m_floor.group(1)),
                 "identical": int(m_floor.group(1)), "flips_up": int(m_floor.group(2)),
                 "flips_down": int(m_floor.group(3)),
                 "score_swing": float(m_floor.group(4)),
                 "jaccard": float(m_floor.group(5))},
                {"name": "EvalPlus chat", "n": int(m_eval.group(2)),
                 "identical": int(m_eval.group(2)), "passed": int(m_eval.group(1)),
                 "flips_up": int(m_eval.group(3)), "flips_down": int(m_eval.group(4)),
                 "jaccard": float(m_eval.group(5))},
            ],
            "rule": "同一提示集哈希 + 同一后处理版本下，任何非零跨 run 差异都不是噪声",
        },
        "input_change": {
            "fact": "res29",
            "flips_up": int(m_flips.group(2)), "flips_down": int(m_flips.group(3)),
            "net": int(m_flips.group(4)),
            "amplitude": int(m_amp.group(1)), "n": n,
            "amplitude_ratio": round(int(m_amp.group(1)) / n, 4),
            "text_diff": int(m_text.group(1)), "token_diff": int(m_tok.group(1)),
        },
        "condition": "任何两次 run 只有在提示集哈希 + 后处理版本都被钉住并记录时才可比",
    }


def scan():
    paths = sorted(glob.glob(SOURCE_GLOB))
    if not paths:
        raise SystemExit(f"找不到 i01 的 RESULT.md：{SOURCE_GLOB}")
    path = paths[0]
    facts = read_facts(path)
    missing = [f for f in ("res29", "res32") if f not in facts]
    if missing:
        raise SystemExit(f"{os.path.relpath(path, REPO)} 缺少事实 {missing}")
    doc = parse(facts["res32"], facts["res29"], "".join(facts.values()))
    doc["source"] = os.path.relpath(path, REPO)
    return doc


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    doc = scan()
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
        print(f"reproducibility.json: up to date (floor=0 on "
              f"{len(doc['floor']['harnesses'])} harnesses, amplitude "
              f"±{doc['input_change']['amplitude']}/{doc['input_change']['n']})")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}: floor 0 on "
          f"{len(doc['floor']['harnesses'])} harnesses; input-change amplitude "
          f"±{doc['input_change']['amplitude']}/{doc['input_change']['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
