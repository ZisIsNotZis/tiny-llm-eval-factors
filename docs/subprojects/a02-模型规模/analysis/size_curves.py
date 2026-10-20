#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP4：每家族的规模曲线——把「同族、同配方、同基准、同协议、同语言」的格子串成一条线。

规矩（缺一条就不成线，宁可记「无曲线」）：

  * X 用**实测总参数量**（`size_provenance.py` 从 GGUF 张量求和）。没有实测值的格子不进曲线，
    在 `skipped` 里按数量记，不拿文件名标签顶替（`size-axis-verdict` 已证标签会错到 88%）。
  * 分母一律用该行自己的 `n_items`；`n_items` 为 NULL 的格子不进曲线。
  * 协议固定：每个基准只认一个协议（`PROTOCOL_OF`），多语言只在 cpp 与 py 都测过时产出标准列，
    单语言分别是两条独立的线（a12）。
  * 区间用逐题 Wilson（n = `n_items`）。判「反例」时看区间是否重叠：重叠即「测不出」。
  * 判分通道的已知缺陷随基准一起打印（i01 的 `res26`–`res28`），不写在结论外面。

    python3 "docs/subprojects/a02-模型规模/analysis/size_curves.py"
    python3 "docs/subprojects/a02-模型规模/analysis/size_curves.py" --check
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DB = REPO / "experiments.sqlite"
PROV = HERE / "size_provenance.json"
OUT = HERE / "size_curves.json"

sys.path.insert(0, str(REPO / ".wrapup"))
from mktables import lineage_and_size, recipe_of  # noqa: E402

# 每个基准只认一个协议：换协议就是换 X，不能同线。
PROTOCOL_OF = {
    "humaneval": "evalplus-0.3.1-openai-chat-greedy-base",
    "humaneval-plus": "evalplus-0.3.1-openai-chat-greedy-plus",
    "mbpp": "evalplus-0.3.1-openai-chat-greedy-base",
    "mbpp-plus": "evalplus-0.3.1-openai-chat-greedy-plus",
    "mmlu": "lmeval-0.4.13-chat-reasoning-off",
    "arc_challenge": "lmeval-0.4.13-chat-reasoning-off",
    "truthfulqa_mc2": "lmeval-0.4.13-chat-reasoning-off",
    "gsm8k": "lmeval-0.4.13-chat-reasoning-off",
    "ifeval": "lmeval-0.4.13-chat-reasoning-off",
    "humaneval-cpp": "multipl-e-raw-greedy-768",
    "humaneval-py": "multipl-e-raw-greedy-768",
}

# i01 的判分审计：这些通道的分数不能当无损测量读。
CAVEAT = {
    "truthfulqa_mc2": "acc 不是命中率，是归一化后的真答案概率质量（地板 0.4484）",
    "gsm8k": "入库用 flexible-extract（取完成物里最后一个数字）",
    "ifeval": "prompt_level_strict_acc，通用废话地板约 9%",
    "mmlu": "似然打平静默取下标 0；无逐题样本",
    "arc_challenge": "入库是 acc_norm；似然打平静默取下标 0",
    "humaneval": "EvalPlus 不做后处理（围栏不过即判错）",
    "humaneval-plus": "EvalPlus 不做后处理；全部超时的格与真 0 在库里不可区分",
    "mbpp": "MBPP+ 有 1 题可被 `return None` 通过（属 plus 集）",
    "mbpp-plus": "有 1 题可被 `return None` 通过",
    "humaneval-cpp": "MultiPL-E 判分是「程序退出码 0」，`exit(0)` 可白拿（历史语料 0 发生）",
    "humaneval-py": "MultiPL-E 判分是「程序退出码 0」，`sys.exit(0)` 可白拿（历史语料 0 发生）",
}


# MultiPL-E 的 raw 补全协议上，gemma-4 这两个文件是已记录的 harness 失败（模型不写代码、写
# markdown 推理散文，实测 0/40 探针），它们的低分不是模型能力。来源：
# `.wrapup/moe_structure_analysis.py::HARNESS_INVALID` 与 i01 的 `res18`/`res19`。
HARNESS_FAILURE = {
    "gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf",
    "gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf",
}


def wilson(p, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def truth_map():
    prov = json.loads(PROV.read_text(encoding="utf-8"))
    out = {}
    for r in prov["rows"]:
        if r["gguf"] and r["truth_params"] is not None and r["model"] not in out:
            out[r["model"]] = r["gguf"]["n_params"]
    return out


def cells():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    got = defaultdict(list)
    for r in con.execute(
            """select model, _bench, protocol, language, _score, n_items
                 from experiments
                where _score is not null and n_items is not null and n_items > 0"""):
        if PROTOCOL_OF.get(r["_bench"]) != r["protocol"]:
            continue
        got[(r["model"], r["_bench"], r["language"])].append((r["_score"], r["n_items"]))
    return got


def build():
    truth = truth_map()
    raw = cells()
    curves = defaultdict(list)
    skipped = defaultdict(int)
    for (model, bench, lang), vals in raw.items():
        if model not in truth:
            skipped["no measured params"] += 1
            continue
        lin, label = lineage_and_size(model)
        rec = recipe_of(model)
        if rec is None:
            skipped["no recipe"] += 1
            continue
        p = sum(s for s, _ in vals) / len(vals)
        n = min(n for _, n in vals)
        lo, hi = wilson(p, n)
        harness_bad = model in HARNESS_FAILURE and bench.startswith("humaneval-")
        curves[(lin, rec, bench, lang or "python")].append({
            "model": model, "label": label, "harness_suspect": harness_bad,
            "params_b": round(truth[model] / 1e9, 4),
            "score": round(p, 4), "n_items": n, "ci": [round(lo, 4), round(hi, 4)],
            "replicates": len(vals),
        })
    out = {}
    for key, pts in curves.items():
        pts.sort(key=lambda d: d["params_b"])
        # 同一参数量的重复模型（同名不同路径）只留一个，避免假阶梯
        dedup, seen = [], set()
        for p in pts:
            if p["params_b"] in seen:
                continue
            seen.add(p["params_b"])
            dedup.append(p)
        out["|".join(key)] = dedup
    return out, dict(skipped)


def verdict(pts):
    """单调性裁决：线内按参数量升序，逐对看是否下降，并看区间是否重叠。

    `ci_overlap` 为假 = 差得动；为真 = 测不出。`harness_explained` 为真 = 这一对里至少一端
    落在已知的 harness 失败文件上，所以这个反例不能读成规模效应。
    """
    bad = []
    for a, b in zip(pts, pts[1:]):
        if b["score"] < a["score"]:
            overlap = not (b["ci"][1] < a["ci"][0] or a["ci"][1] < b["ci"][0])
            bad.append({"from_b": a["params_b"], "to_b": b["params_b"],
                        "from": a["model"], "to": b["model"],
                        "drop_pp": round(100 * (b["score"] - a["score"]), 2),
                        "ci_overlap": overlap,
                        "harness_explained": bool(a.get("harness_suspect") or b.get("harness_suspect"))})
    return {"monotone": not bad, "inversions": bad}


def main(argv):
    curves, skipped = build()
    rows, thin = [], []
    for key, pts in sorted(curves.items()):
        lin, rec, bench, lang = key.split("|")
        if len(pts) < 2:
            # 只有一个 rung 的组也是结论（「这个族在这个基准上没有规模曲线」），因此记录下来
            # 而不是丢掉；丢弃口径写在这里，读者可以数得回来。
            thin.append({"lineage": lin, "recipe": rec, "bench": bench, "language": lang,
                         "n": len(pts), "reason": "only one measured-parameter rung",
                         "model": pts[0]["model"], "params_b": pts[0]["params_b"],
                         "score": pts[0]["score"]})
            continue
        v = verdict(pts)
        rows.append({"lineage": lin, "recipe": rec, "bench": bench, "language": lang,
                     "n": len(pts), "points": pts, **v})
    out = {"curves": rows, "thin_curves": thin, "skipped_cells": skipped,
           "group_counts": {"with_recipe": len(curves), "curve_ge2": len(rows),
                            "thin_lt2": len(thin)},
           "protocol_of": PROTOCOL_OF, "caveat": CAVEAT}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"groups with a recipe: {len(curves)}  ->  curves >=2 rungs: {len(rows)}, "
          f"no-curve (1 rung): {len(thin)}   (cells skipped before grouping: {skipped})")
    print(f"{'lineage':20s} {'recipe':14s} {'bench':16s} {'lang':7s} n  verdict")
    for r in rows:
        tag = "monotone" if r["monotone"] else (
            f"{len(r['inversions'])} inv, "
            + ("all CI-overlap" if all(i["ci_overlap"] for i in r["inversions"])
               else f"{sum(not i['ci_overlap'] and not i['harness_explained'] for i in r['inversions'])} beyond noise"
                    + (f", {sum(i['harness_explained'] for i in r['inversions'])} harness")))
        print(f"{r['lineage'][:20]:20s} {r['recipe'][:14]:14s} {r['bench'][:16]:16s} "
              f"{r['language'][:7]:7s} {r['n']}  {tag}")
    print("\n判分通道的已知限制（i01）：")
    for b in sorted({r["bench"] for r in rows}):
        print(f"  {b:16s} {CAVEAT.get(b, '无已记录缺陷')}")
    print(f"\nwrote {OUT.relative_to(REPO)}")

    if "--check" in argv:
        ok = fail = 0

        def want(c, label):
            nonlocal ok, fail
            if c:
                ok += 1
            else:
                fail += 1
                print(f"  FAIL  {label}")

        want(len(rows) >= 10, f"至少 10 条可画曲线（实际 {len(rows)}）")
        want(len(rows) + len(thin) == len(curves),
             f"每条组都被计数：曲线 {len(rows)} + 无曲线 {len(thin)} = 组 {len(curves)}")
        want(len(thin) >= 200, f"「无曲线」的组被记录而不是丢掉（实际 {len(thin)}）")
        want(all(t["reason"] for t in thin), "每个无曲线的组都带原因")
        want(all(r["n"] >= 2 for r in rows), "每条曲线至少 2 个 rung")
        want(all(p["n_items"] > 0 for r in rows for p in r["points"]), "每个点都有自己的 n_items")
        want(not any("|" in r["bench"] for r in rows), "基准名里没有协议串（说明匹配上了 PROTOCOL_OF）")
        langs = {r["language"] for r in rows}
        want("python" in langs, "语言列已填（不是空）")
        # 每条曲线的点必须按参数量升序且无重复
        want(all([p["params_b"] for p in r["points"]] == sorted({p["params_b"] for p in r["points"]})
                 for r in rows), "每条曲线的参数量严格升序且无重复")
        # 已知反例必须在：gemma-4 @ Q2_K_XL 的 humaneval 线有 12B 那一处
        gem = [r for r in rows if r["lineage"] == "gemma-4" and r["recipe"] == "Q2_K_XL"
               and r["bench"] == "humaneval"]
        want(bool(gem) and any(not i["ci_overlap"] and not i["harness_explained"]
                               for i in gem[0]["inversions"]),
             "gemma-4 Q2_K_XL 的 humaneval 线上有一处超出噪声的反例")
        print(f"  {ok} expected true, {fail} false")
        return 0 if fail == 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
