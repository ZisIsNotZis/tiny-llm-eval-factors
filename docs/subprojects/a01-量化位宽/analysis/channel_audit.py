#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EvalPlus 判分通道审计（a01 WP3::T2）：判分通道能不能解释 Qwen3.5-2B 那一对文件的分数差。

对每个面板的落盘完成物，量三件事，都不需要重跑模型：
  1. 原始完成物里带 markdown 围栏的条数（围栏只有在 sanitize 之后才可能被判对）；
  2. sanitize 之后的完成物里还有多少条带着围栏、有多少条语法错、有多少条连 `def`/`class` 都没有
     ——这是「判分前的抽取有没有把这一格弄坏」的直接量；
  3. `_eval_results.json` 的逐题状态直方图（`base_status` / `plus_status`）——有没有 timeout。

用法：
    python3 "docs/subprojects/a01-量化位宽/analysis/channel_audit.py" [面板...]
不给面板参数时跑 Qwen3.5-2B 那一列（m61–m67）。
退出 0 表示脚本跑完；它不断言预期（断言在 `run_all.py` 里），因为它输出的是可核对的数字。
"""
from __future__ import annotations

import ast
import collections
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))
DEFAULT = ["m61-qwen-2b-iq2xxs", "m62-qwen-2b-iq2m", "m63-qwen-2b-iq3xxs",
           "m64-qwen-2b-q2kxl", "m65-qwen-2b-q3kxl", "m66-qwen-2b-q4kxl", "m67-qwen-2b-q5kxl"]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def audit(panel, dataset):
    base = os.path.join(REPO, ".wrapup", "mres", panel, "codegen", dataset)
    san = glob.glob(base + "/*temp_0.0.jsonl")
    raw = glob.glob(base + "/*temp_0.0.raw.jsonl")
    ev = glob.glob(base + "/*_eval_results.json")
    if not (san and raw and ev):
        return None
    S, R = load(san[0]), load(raw[0])
    E = json.load(open(ev[0], encoding="utf-8"))
    plus = collections.Counter(i["plus_status"] for v in E["eval"].values() for i in v)
    basest = collections.Counter(i["base_status"] for v in E["eval"].values() for i in v)
    bad = nodef = 0
    for a in S:
        sol = a["solution"]
        try:
            ast.parse(sol)
        except SyntaxError:
            bad += 1
        if not any(l.strip().startswith(("def ", "class ")) for l in sol.split("\n")):
            nodef += 1
    return {"panel": panel, "dataset": dataset, "n": len(S),
            "fence_raw": sum(1 for b in R if "```" in b["solution"]),
            "fence_san": sum(1 for a in S if "```" in a["solution"]),
            "empty_san": sum(1 for a in S if not a["solution"].strip()),
            "syntax_err_san": bad, "no_def_san": nodef,
            "plus_status": dict(plus), "base_status": dict(basest),
            "plus_pass": plus.get("pass", 0), "base_pass": basest.get("pass", 0)}


def main(argv):
    panels = argv or DEFAULT
    print(f"{'面板':<22}{'集':<10}{'n':>5}{'围栏raw':>8}{'围栏san':>8}{'空san':>6}"
          f"{'语法错':>7}{'无def':>6}{'plus通过':>9}{'base通过':>9}  状态")
    rows = []
    for p in panels:
        for ds in ("humaneval", "mbpp"):
            r = audit(p, ds)
            if r is None:
                print(f"{p:<22}{ds:<10}  缺落盘文件（未测）")
                continue
            rows.append(r)
            print(f"{r['panel']:<22}{ds:<10}{r['n']:>5}{r['fence_raw']:>8}{r['fence_san']:>8}"
                  f"{r['empty_san']:>6}{r['syntax_err_san']:>7}{r['no_def_san']:>6}"
                  f"{r['plus_pass']:>9}{r['base_pass']:>9}  plus={r['plus_status']} base={r['base_status']}")
    return 0 if rows else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
