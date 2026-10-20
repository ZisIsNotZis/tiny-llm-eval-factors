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
# 适用条件：任何两次 run 只有在提示集哈希与后处理版本都被钉住时才可比（措辞可变，判据是这两处同时出现）
CONDITION_RE = re.compile(r"提示集哈希\s*\+\s*后处理版本")
CONDITION_CUE_RE = re.compile(r"不可相加|才可比")
# res32 的实测是张表：| 族 | cell 与配置 | n | 相同题数 | 上翻/下翻 | 分数摆动 | Jaccard |
TABLE_ROW_RE = re.compile(r"^\|([^|]+)\|([^|]+)\|\s*(\d+)\s*\|\s*(\d+)\s*\|([^|]+)\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|")
FLIP_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
# 采样解码那一档：Jaccard 只有 0.53–0.67、上翻 8–15 题、下翻 6–12 题、分数只在 37→43（6/164）之间
SAMP_JACCARD_RE = re.compile(r"Jaccard 只有 ([\d.]+)–([\d.]+)")
SAMP_FLIP_RE = re.compile(r"上翻 (\d+)–(\d+) 题、下翻 (\d+)–(\d+) 题")
SAMP_SWING_RE = re.compile(r"分数只在 (\d+)→(\d+)（(\d+)/(\d+)）之间摆动")
SAMP_TEMP_RE = re.compile(r"temp=([\d.]+) 的 (\d+) 次重复")
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
    if not (CONDITION_RE.search(all_text) and CONDITION_CUE_RE.search(all_text)):
        raise SystemExit("i01 的事实里找不到适用条件（提示集哈希 + 后处理版本 + 不可相加/才可比）；"
                         "报告不能在没有条件的情况下引用这个幅度")
    harnesses = []
    for line in floor_text.split("\n"):
        m = TABLE_ROW_RE.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        n = int(m.group(3))
        identical = int(m.group(4))
        fl = FLIP_RE.search(m.group(5))
        if not fl:
            continue
        harnesses.append({"name": name, "cell": m.group(2).strip(), "n": n,
                          "identical": identical,
                          "flips_up": int(fl.group(1)), "flips_down": int(fl.group(2)),
                          "score_swing": float(m.group(6)), "jaccard": float(m.group(7))})
    if len(harnesses) < 2:
        raise SystemExit("i01 的 res32 里没有可解析的重复测量表（| 族 | cell | n | 相同 | 翻转 | 摆动 | Jaccard |）")

    js = SAMP_JACCARD_RE.search(all_text)
    fs = SAMP_FLIP_RE.search(all_text)
    sw = SAMP_SWING_RE.search(all_text)
    tp = SAMP_TEMP_RE.search(all_text)
    if not (js and fs and sw and tp):
        raise SystemExit("i01 的事实里找不到采样解码那一档（Jaccard 区间 / 上翻下翻 / 分数摆动 / temp 与重复次数）")
    sampling = {
        "fact": "res32",
        "temp": float(tp.group(1)), "repeats": int(tp.group(2)),
        "jaccard_min": float(js.group(1)), "jaccard_max": float(js.group(2)),
        "flips_up_min": int(fs.group(1)), "flips_up_max": int(fs.group(2)),
        "flips_down_min": int(fs.group(3)), "flips_down_max": int(fs.group(4)),
        "score_min": int(sw.group(1)), "score_max": int(sw.group(2)),
        "n": int(sw.group(4)),
        "score_swing_items": int(sw.group(2)) - int(sw.group(1)),
        "understates": True,
    }

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
            "harnesses": harnesses,
            "rule": "同一提示集哈希 + 同一后处理版本下、且解码是确定性的（greedy/temp=0）时，"
                    "任何非零跨 run 差异都不是噪声",
        },
        "sampling": sampling,
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
