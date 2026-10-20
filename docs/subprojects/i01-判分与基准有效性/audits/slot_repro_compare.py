#!/usr/bin/env python3
"""Adjudicate plan15: is the 6/161 cross-run difference in the same cell from
batching, from the slot count, or is generation reproducible at all?

Reads the artefacts written by `slot_repro_run.sh` and answers with the rule that
was fixed in PLAN.md *before* the run, so the verdict cannot be chosen after the
numbers are known:

  1. np1 reproducible, np4 not            -> batching: the 6/161 is explained by
                                             the 4-slot greedy batch, and the
                                             noise floor has to be per-slot-count
  2. each arm internally reproducible but np1 != np4
                                          -> the slot count is an input change
                                             that was not recorded as one
  3. every arm identical                  -> generation is reproducible here; the
                                             surviving explanation is the prompt
                                             set, which cannot be tested because
                                             the old one is deleted
  4. anything else                        -> reported as observed, no forced mapping

Besides the score it reports the primary quantity: how many problems changed
verdict between two passes, and which ones.  A score difference of 6/161 can come
from 6 problems flipping or from 12 flipping in both directions, and only the
per-problem counts distinguish those.

Run from the repository root:

    python3 "docs/subprojects/i01-判分与基准有效性/audits/slot_repro_compare.py"

Exit 0 = every arm present and adjudicated; 2 = an arm's artefacts are missing
(unmeasured is not a verdict).
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MRES = os.path.join(REPO, ".wrapup", "mres")
ARMS = ["np1-p1", "np1-p2", "np4-p1", "np4-p2", "np4b-p1"]


def load(arm):
    path = os.path.join(MRES, "i01-slot-%s-py-chat_eval.json" % arm)
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    passed = {x["name"] for x in d["details"] if x["pass"]}
    status = {}
    for x in d["details"]:
        status[x["status"]] = status.get(x["status"], 0) + 1
    meta_path = os.path.join(MRES, "i01-slot-%s-meta.json" % arm.replace("-p1", "").replace("-p2", ""))
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    return {"n": d["n"], "pass": d["pass"], "score": d["score"], "passed": passed,
            "status": status, "meta": meta}


def compare(a_name, b_name, a, b):
    only_a = sorted(a["passed"] - b["passed"])
    only_b = sorted(b["passed"] - a["passed"])
    union = a["passed"] | b["passed"]
    jaccard = (len(a["passed"] & b["passed"]) / len(union)) if union else 1.0
    return {"a": a_name, "b": b_name, "flipped": len(only_a) + len(only_b),
            "pass_a_only": only_a, "pass_b_only": only_b,
            "identical": not only_a and not only_b,
            "jaccard": round(jaccard, 4),
            "delta_pass": b["pass"] - a["pass"]}


def verdict(rows):
    np1_same = next(r for r in rows if {r["a"], r["b"]} == {"np1-p1", "np1-p2"})["identical"]
    np4_same = next(r for r in rows if {r["a"], r["b"]} == {"np4-p1", "np4-p2"})["identical"]
    np4b_same = next(r for r in rows if {r["a"], r["b"]} == {"np4-p1", "np4b-p1"})["identical"]
    np1_vs_np4 = next(r for r in rows if {r["a"], r["b"]} == {"np1-p1", "np4-p1"})["identical"]
    if np1_same and not (np4_same and np4b_same):
        return ("batching", "4 槽贪心批处理不可复现：np1 内两次逐题相同，np4 内/跨实例出现翻转；"
                            "plan15 的 6/161 由生成侧批处理解释，噪声地板必须按槽位数分别定。")
    if np1_same and np4_same and np4b_same and np1_vs_np4:
        return ("prompt-set", "四个臂逐题完全相同：当前配置下生成可复现，残余差异只能来自提示集或其他未记录的输入；"
                              "旧提示集已删除，无法逐字节比对，(a) 是唯一存活解释但不可证。")
    if np1_same and np4_same and np4b_same and not np1_vs_np4:
        return ("slot-count", "各臂内部可复现、跨槽位数不同：槽位数是未被记录成输入的配置差，"
                              "plan15 的差不能归给模型，必须写进协议串。")
    return ("observed", "组合不落在预先写死的三种形态里，按观测如实记录，不硬套归因。")


def main() -> int:
    data = {}
    missing = []
    for arm in ARMS:
        d = load(arm)
        if d is None:
            missing.append(arm)
        else:
            data[arm] = d
    if missing:
        print("MISSING arms (a missing arm is unmeasured, not a pass): %s" % ", ".join(missing))
        for arm in sorted(data):
            d = data[arm]
            print("  %s n=%d pass=%d score=%.4f statuses=%s" % (arm, d["n"], d["pass"], d["score"], d["status"]))
        return 2

    print("arms")
    for arm in ARMS:
        d = data[arm]
        print("  %-8s n=%d pass=%d score=%.4f statuses=%s meta=%s"
              % (arm, d["n"], d["pass"], d["score"], d["status"],
                 d["meta"].get("llama_reports", "?")))

    pairs = [("np1-p1", "np1-p2"), ("np4-p1", "np4-p2"), ("np4-p1", "np4b-p1"), ("np1-p1", "np4-p1")]
    rows = [compare(a, b, data[a], data[b]) for a, b in pairs]
    print("pairwise per-problem comparison")
    for r in rows:
        print("  %s vs %s: flipped=%d delta_pass=%+d jaccard=%.4f identical=%s"
              % (r["a"], r["b"], r["flipped"], r["delta_pass"], r["jaccard"], r["identical"]))
        if r["pass_a_only"]:
            print("    pass only in %s: %s" % (r["a"], " ".join(r["pass_a_only"])))
        if r["pass_b_only"]:
            print("    pass only in %s: %s" % (r["b"], " ".join(r["pass_b_only"])))

    kind, text = verdict(rows)
    print("verdict: %s" % kind)
    print("  %s" % text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
