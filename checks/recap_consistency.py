#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结论索引（报告末尾的 recap 表）必须与各节一一对应，且不得复述已撤回的说法。

背景：这张表曾经是手写的，a03 撤回「同大小下方案有差」、a10 修正「全部差值都测不出」、
a05 补了长上下文、a07 证明输出逐字节变了之后，表还停在旧值上。事实的家在各节与分析节点，
表只是索引；所以这里检查三件事：

  1. recap 有且只有 16 行，行数与报告里带编号的 `<h2>` 节数相同；
  2. 每行的「详见 §N」都能在报告里找到对应编号的节，且 16 个编号一个不缺；
  3. 表里不出现已撤回 / 已被推翻的措辞（下面 FORBIDDEN）。

空扫描判 FAIL：解析不到 recap 或编号节，说明解析假设坏了，不是「全都对」。

    python3 checks/recap_consistency.py
    exit 0 = 一致；exit 1 = 不一致（逐条点名）；exit 2 = report.html 不在场
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REPORT = os.path.join(REPO, "report.html")

CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
      "九": 9, "十": 10, "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
      "十六": 16, "十七": 17, "十八": 18}
SEC_RE = re.compile(r"<h2>([一二三四五六七八九十]+)、")
RECAP_RE = re.compile(r"<table class='recap'>(.*?)</table>", re.S)
ROW_RE = re.compile(r"<tr><td>.*?</td><td.*?>.*?</td><td.*?>.*?</td><td.*?>.*?</td><td>§(\d+)</td></tr>", re.S)
CELL_RE = re.compile(r"<tr><td>(.*?)</td>", re.S)
FORBIDDEN = [
    "同大小下方案有差",
    "全部差值都测不出",
    "所有深度分数无差别",
]


def main() -> int:
    if not os.path.exists(REPORT):
        print(f"BLOCKED report.html 不在场：{os.path.relpath(REPORT, REPO)}")
        return 2
    text = open(REPORT, encoding="utf-8").read()
    secs = [CN.get(m) for m in SEC_RE.findall(text)]
    secs = [x for x in secs if x]
    # 报告里还有别的 recap 表（QAT 配置）；结论索引是「结论与显著性总结」之后的第一个 recap。
    tail = text.split("<h2>结论与显著性总结</h2>", 1)[-1]
    m = RECAP_RE.search(tail) if "<h2>结论与显著性总结</h2>" in text else None
    if not m:
        print("FAIL 报告里找不到结论索引表（结论与显著性总结之后的 table class='recap'）")
        return 1
    body = m.group(1)
    rows = ROW_RE.findall(body)
    names = CELL_RE.findall(body)
    errors = []
    if not secs:
        errors.append("解析不到任何带中文编号的 <h2> 节（空扫描不算通过）")
    if len(rows) != len(secs):
        errors.append(f"结论索引 {len(rows)} 行，编号节 {len(secs)} 个：行数与节数不等")
    refs = [int(x) for x in rows]
    if sorted(refs) != list(range(1, len(secs) + 1)):
        errors.append(f"“详见”编号不是 1..{len(secs)} 各一次：{sorted(refs)}")
    for phrase in FORBIDDEN:
        if phrase in body:
            errors.append(f"结论索引里仍有已撤回/被推翻的措辞：{phrase!r}")
    print(f"编号节 {len(secs)} 个；结论索引 {len(rows)} 行；详见编号 {len(set(refs))} 个不同值")
    if errors:
        for e in errors:
            print(f"  - {e}")
        print(f"FAIL 结论索引与各节不一致：{len(errors)} 处")
        return 1
    print("PASS 结论索引与 16 个编号节一一对应，且不含已撤回措辞")
    return 0


if __name__ == "__main__":
    sys.exit(main())
