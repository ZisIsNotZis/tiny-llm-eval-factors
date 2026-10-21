#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MMLU 逐科目对照（a01 WP5 / plan7b）：12B 原生档的 MMLU 跳是均匀平移还是少数科目崩坏？

读 lm-eval 落盘的 `lmeval_mmlu_*.json`（**没有** `--log_samples`，所以只有聚合），比较两次运行
在 61 个科目上的 `acc,none`：上升科目数、中位/平均科目差、有没有全对或全错的科目。

    python3 "docs/subprojects/a01-量化位宽/analysis/mmlu_subjects.py" m105-gemma-12b-q3kxl m141-native-gemma12b-q4

两个参数是 run_tag；不给就用 12B 的 Q3 与原生 Q4 那一对。退出 0 = 跑完（断言在 `run_all.py`）。
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))


def subjects(tag):
    paths = sorted(glob.glob(os.path.join(REPO, ".wrapup", "mres", tag, "lmeval_mmlu_*.json")))
    if not paths:
        return None, None
    d = json.load(open(paths[-1], encoding="utf-8"))
    acc = {k: v.get("acc,none") for k, v in d["results"].items() if k.startswith("mmlu_")}
    return acc, paths[-1]


def main(argv):
    a_tag, b_tag = (argv + ["m105-gemma-12b-q3kxl", "m141-native-gemma12b-q4"])[:2]
    A, fa = subjects(a_tag)
    B, fb = subjects(b_tag)
    if A is None or B is None:
        print(f"缺落盘的 mmlu json：{a_tag}={fa} {b_tag}={fb}")
        return 2
    common = sorted(set(A) & set(B))
    diffs = sorted((B[k] - A[k], k, A[k], B[k]) for k in common)
    up = sum(1 for d, *_ in diffs if d > 0)
    down = sum(1 for d, *_ in diffs if d < 0)
    flat = len(diffs) - up - down
    print(f"A = {a_tag}   ({fa})")
    print(f"B = {b_tag}   ({fb})")
    print(f"科目数 {len(common)}  上升 {up}  下降 {down}  持平 {flat}")
    print(f"整体 acc：A = {statistics.mean(A.values()):.4f}  B = {statistics.mean(B.values()):.4f}  "
          f"差 {statistics.mean(B.values())-statistics.mean(A.values()):+.4f}")
    vals = [d for d, *_ in diffs]
    print(f"科目差：中位 {statistics.median(vals):+.4f}  均值 {statistics.mean(vals):+.4f}  "
          f"差域 [{min(vals):+.4f}, {max(vals):+.4f}]")
    print(f"B 里 1.0 的科目 {sum(1 for v in B.values() if v == 1.0)}，0.0 的科目 {sum(1 for v in B.values() if v == 0.0)}；"
          f"A 里 1.0 的科目 {sum(1 for v in A.values() if v == 1.0)}，0.0 的科目 {sum(1 for v in A.values() if v == 0.0)}")
    print("差最小的 5 个科目（掉得最多）：")
    for d, k, av, bv in diffs[:5]:
        print(f"  {d:+.4f}  {k[5:]:<34} A={av:.4f} B={bv:.4f}")
    print("差最大的 5 个科目（涨得最多）：")
    for d, k, av, bv in diffs[-5:]:
        print(f"  {d:+.4f}  {k[5:]:<34} A={av:.4f} B={bv:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
