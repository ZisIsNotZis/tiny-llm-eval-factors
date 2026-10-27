#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""家族效应与家族×量化档交互：从 `pairs.py` 的清单算，不碰库。

输入是 `analysis/pairs.json`（`pairs.py` 产出，一行一个受控格），输出人读文本 + `analysis/effects.json`。
本脚本自己不做筛选，只做算术；但**读法分三层**，每个数字都标明它落在哪一层：

  * `label_matched`：16 个身份栏相等（`__quant` 可以是 NULL，NULL==NULL 也算相等）。名字只说明标签
    相同，**不说明同一比特预算**——`__quant` 为 NULL 的格里，两侧位宽差最大到 3.9 bpw。这一层只作清单。
  * `bpw_matched`：|bpw_a − bpw_b| ≤ `ledger.bpw_match_tol`（= `level_width_bpw` 的一半；数值只有
    `pairs.py` 一处定义，本脚本从清单里读）。位宽是实测的 GGUF 张量
    bpw。**家族差、可分辨数、可读家族对、翻转计数全部只在这一层上算。**
  * `family`（家族层）＝ `bpw_matched` 且**两侧实测参数量不同**：家族标签由 `mktables.family_of` 给，
    但同参数量意味着同一套张量形状（同一架构脚手架），那样的对子是「换权重/换配方」，不是架构对比，
    单独成表（`same_scaffold`），不进家族计数。

口径：

* `delta_pp` = (score_b − score_a) × 100，单位百分点；a/b 是清单里的两个模型文件（`family_a`/`family_b`
  是它们各自的 `family_of`）。
* 每个分数按它自己的 `n_items` 给一个 95% Wilson 区间；两区间不相交才算 `resolvable`。**区间是单跑的二项
  区间**：它只覆盖抽样误差，不覆盖重测误差，也不代表这些格互相独立（`(g)` 段给出逐 (家族对, 基准) 的格数）。
* **规模对固定**：交互分析的分组键是 (bench, 其余身份栏, family_a, n_params_a, family_b, n_params_b)——
  同一个基座模型在不同量化档上真参数量不变，所以「同一对规模」是算出来的，不是按文件名猜的。
  组内只用 `bpw_matched` 的格当「档」，相邻两档的 Δ 符号相反记一次翻转。
* **家族差与量化差同单位**：同一组里，家族 Δ 与「同族跨量化档的分数差」（`quant_effect_pp`）都是 pp。

退出码：0 算完；2 输入不可得（清单缺、清单里没有受控格）。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEFAULT_LEDGER = HERE / "pairs.json"
DEFAULT_OUT = HERE / "effects.json"

Z = 1.959963984540054  # 95%
CTX_COLS: list[str] = []


def wilson(p: float, n: int, z: float = Z) -> tuple[float, float]:
    """二项比例的 Wilson 区间（不是正态近似：小 n 与接近 0/1 时正态区间会跑出 [0,1]）。"""
    if n <= 0:
        return (0.0, 1.0)
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z / denom * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return (round(max(0.0, centre - half), 6), round(min(1.0, centre + half), 6))


def disjoint(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[1] < b[0] or b[1] < a[0]


def ctx_key(p: dict) -> str:
    sig = p["ctx_sig"]
    return "|".join(f"{c}={sig[c]}" for c in CTX_COLS)


def decode(ledger: dict) -> tuple[list[dict], list[dict]]:
    """把清单里的 `cells` / `recipe_controls` 展开（落盘时家族名与 ctx 是压缩存的）。"""
    fam = ledger["families"]
    out = []
    for name in ("cells", "recipe_controls"):
        rows = []
        for p in ledger[name]:
            q = dict(p)
            q["family_a"] = fam[p["model_a"]]
            q["family_b"] = fam[p["model_b"]]
            q["ctx_sig"] = dict(zip(CTX_COLS, p["ctx"]))
            q["protocol"] = q["ctx_sig"].get("protocol")
            rows.append(q)
        out.append(rows)
    return out[0], out[1]


def measure(p: dict) -> dict:
    """一格 → 带区间与 Δ 的记录。`bpw_matched` 等闸门字段由 `pairs.py` 给，这里不重算。"""
    n = p["n_items"]
    ca = wilson(p["score_a"], n) if n else None
    cb = wilson(p["score_b"], n) if n else None
    return {
        "id": p["id"],
        "bench": p["bench"],
        "quant": p["quant"],
        "family_a": p["family_a"],
        "family_b": p["family_b"],
        "model_a": p["model_a"],
        "model_b": p["model_b"],
        "score_a": p["score_a"],
        "score_b": p["score_b"],
        "n_items": n,
        "ci_a": ca,
        "ci_b": cb,
        "delta_pp": round((p["score_b"] - p["score_a"]) * 100.0, 4),
        "resolvable": bool(ca and cb and disjoint(ca, cb)),
        "n_items_missing": n is None,
        "bpw_a": p["bpw_a"],
        "bpw_b": p["bpw_b"],
        "bpw_gap": p["bpw_gap"],
        "bpw_mean": round((p["bpw_a"] + p["bpw_b"]) / 2.0, 4),
        "bpw_matched": p["bpw_matched"],
        "quant_label_missing": p["quant_label_missing"],
        "same_n_params": p.get("same_n_params", False),
        "size_delta": p["size_delta"],
        "protocol": p["protocol"],
    }


def analyse(ledger: dict) -> dict:
    global CTX_COLS
    CTX_COLS = list(ledger["ctx_columns"])
    tol = ledger["bpw_match_tol"]
    raw_cells, raw_recipe = decode(ledger)
    cells = [measure(p) for p in raw_cells]
    recipe = [measure(p) for p in raw_recipe]

    family_all = [c for c in cells if not c["same_n_params"]]
    family = [c for c in family_all if c["bpw_matched"]]
    scaffold = [c for c in cells if c["same_n_params"]]
    scaffold_readable = [c for c in scaffold if c["bpw_matched"]]
    ctx_of = {p["id"]: ctx_key(p) for p in raw_cells}

    # ---- (b)(c)(d) 交互：只吃 family 层 + bpw_matched ------------------------------------
    family_raw = {p["id"]: p for p in raw_cells if not p["same_n_params"]}
    sized: dict[tuple, list[dict]] = defaultdict(list)
    for c in family:
        r = family_raw[c["id"]]
        sized[(c["bench"], ctx_of[c["id"]], c["family_a"], r["n_params_a"],
               c["family_b"], r["n_params_b"])].append(c)

    # 一个「档」= 平均 bpw 的 `level_width_bpw` 宽的桶：同一档上「换了配方但落在同一位宽」的两个文件
    # 落进同一个桶，不会被当成两个相邻档。桶内符号不统一时该档记 `sign=None`（不可判），不猜。
    level_w = ledger["level_width_bpw"]
    interaction = []
    for key, cs in sorted(sized.items(), key=lambda kv: tuple(str(v) for v in kv[0])):
        bench, ck, fa, npa, fb, npb = key
        buckets: dict[int, list[dict]] = defaultdict(list)
        for c in cs:
            buckets[int(c["bpw_mean"] // level_w)].append(c)
        levels = []
        for b in sorted(buckets):
            bc = sorted(buckets[b], key=lambda c: c["id"])
            signs_in = {0 if c["delta_pp"] == 0 else (1 if c["delta_pp"] > 0 else -1) for c in bc}
            levels.append({
                "ids": [c["id"] for c in bc],
                "quant_labels": sorted({str(c["quant"]) for c in bc}),
                "bpw_min": min(c["bpw_mean"] for c in bc),
                "bpw_max": max(c["bpw_mean"] for c in bc),
                "bpw_mean": round((min(c["bpw_mean"] for c in bc)
                                   + max(c["bpw_mean"] for c in bc)) / 2.0, 4),
                "bpw_gap": round(sum(c["bpw_gap"] for c in bc) / len(bc), 4),
                "delta_pp": round(sum(c["delta_pp"] for c in bc) / len(bc), 4),
                "score_a": bc[0]["score_a"],
                "score_b": bc[0]["score_b"],
                "resolvable": all(c["resolvable"] for c in bc),
                "sign": signs_in.pop() if len(signs_in) == 1 else None,
            })
        levels.sort(key=lambda l: l["bpw_mean"])
        signs = [l["sign"] for l in levels]
        flips = [i for i in range(len(levels) - 1)
                 if signs[i] is not None and signs[i + 1] is not None
                 and signs[i] * signs[i + 1] < 0]
        lo, hi = levels[0], levels[-1]
        interaction.append({
            "bench": bench,
            "ctx_key": ck,
            "family_a": fa,
            "family_b": fb,
            "n_params_a": npa,
            "n_params_b": npb,
            "n_levels": len(levels),
            "levels": levels,
            "signs": signs,
            "flips": len(flips),
            "flip_cells": [[levels[i]["ids"], levels[i + 1]["ids"]] for i in flips],
            "family_delta_pp_low": lo["delta_pp"],
            "family_delta_pp_high": hi["delta_pp"],
            "quant_effect_pp_a": (round((hi["score_a"] - lo["score_a"]) * 100.0, 4)
                                  if len(levels) > 1 else None),
            "quant_effect_pp_b": (round((hi["score_b"] - lo["score_b"]) * 100.0, 4)
                                  if len(levels) > 1 else None),
            "quant_span_bpw": round(hi["bpw_mean"] - lo["bpw_mean"], 4) if len(levels) > 1 else None,
        })

    # ---- (d) 每个基准上的家族排序（family 层 + bpw_matched） -------------------------------
    by_bench_ctx_level: dict[tuple, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for c in family:
        lvl = c["quant"] if c["quant"] is not None else "unlabelled"
        by_bench_ctx_level[(c["bench"], ctx_of[c["id"]], lvl)][c["family_a"]].add(round(c["score_a"], 12))
        by_bench_ctx_level[(c["bench"], ctx_of[c["id"]], lvl)][c["family_b"]].add(round(c["score_b"], 12))
    by_bench_ctx: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for (bench, ck, lvl), fams in by_bench_ctx_level.items():
        ambiguous = sorted(f for f, s in fams.items() if len(s) > 1)
        if ambiguous:
            by_bench_ctx[(bench, ck)][lvl] = {"ambiguous_families": ambiguous}
            continue
        if len(fams) < 2:
            continue
        ranked = sorted(((f, next(iter(s))) for f, s in fams.items()), key=lambda kv: (-kv[1], kv[0]))
        by_bench_ctx[(bench, ck)][lvl] = {"ranking": [f for f, _ in ranked],
                                          "scores": {f: s for f, s in ranked}}
    orderings = []
    for (bench, ck), per_level in sorted(by_bench_ctx.items()):
        good = {lvl: v for lvl, v in per_level.items() if "ranking" in v}
        bad = {lvl: v for lvl, v in per_level.items() if "ranking" not in v}
        by_set: dict[frozenset, dict[str, dict]] = defaultdict(dict)
        for lvl, v in good.items():
            by_set[frozenset(v["ranking"])][lvl] = v
        comparable = {lvl: v for grp in by_set.values() if len(grp) >= 2 for lvl, v in grp.items()}
        changed = []
        for fams, grp in by_set.items():
            if len(grp) < 2:
                continue
            if len({tuple(v["ranking"]) for v in grp.values()}) > 1:
                changed.append(sorted(grp))
        orderings.append({
            "bench": bench,
            "ctx_key": ck,
            "levels": good,
            "skipped_levels": {lvl: v["ambiguous_families"] for lvl, v in bad.items()},
            "comparable_levels": sorted(comparable),
            "not_comparable_levels": sorted(lvl for lvl in good if lvl not in comparable),
            "changed_groups": changed,
            "stable": (not changed) if len(comparable) >= 2 else None,
        })

    # ---- (g) 独立性：逐 (家族对, 基准) 的格数 -------------------------------------------
    per_pair_bench: dict[tuple, dict] = {}
    for c in family_all:
        k = (c["family_a"], c["family_b"], c["bench"])
        d = per_pair_bench.setdefault(k, {"cells": 0, "bpw_matched": 0, "resolvable": 0,
                                          "n_items": set(), "contexts": set()})
        d["cells"] += 1
        d["bpw_matched"] += 1 if c["bpw_matched"] else 0
        d["resolvable"] += 1 if (c["resolvable"] and c["bpw_matched"]) else 0
        d["n_items"].add(c["n_items"])
        d["contexts"].add(ctx_of[c["id"]])
    independence = [{"family_a": k[0], "family_b": k[1], "bench": k[2],
                     "cells": v["cells"], "bpw_matched": v["bpw_matched"],
                     "resolvable_cells": v["resolvable"],
                     "distinct_contexts": len(v["contexts"]),
                     "n_items": sorted(x for x in v["n_items"] if x is not None)}
                    for k, v in sorted(per_pair_bench.items())]

    steps = []
    for g in interaction:
        lv = g["levels"]
        for i in range(len(lv) - 1):
            steps.append(lv[i + 1]["bpw_mean"] - lv[i]["bpw_mean"])
    warnings = []
    if not family:
        warnings.append("no family cell is bpw_matched: the family axis has no readable cell")
    if any(s <= 0 for s in steps):
        warnings.append("interaction levels do not increase in bpw")

    def counts_of(group: list[dict]) -> dict:
        return {
            "cells": len(group),
            "cells_with_intervals": sum(1 for c in group if c["ci_a"] is not None),
            "n_items_missing": sum(1 for c in group if c["n_items_missing"]),
            "resolvable": sum(1 for c in group if c["resolvable"]),
        }

    return {
        "what": ("家族效应、家族×量化档交互、家族排序；家族 = mktables.family_of，"
                 "家族差一律在 bpw_matched 且两侧实测参数量不同的格上算"),
        "generated_by": "docs/subprojects/a15-模型家族/analysis/effects.py",
        "bpw_match_tol": tol,
        "wilson_z": Z,
        "counts": {
            "label_matched_cells": counts_of(cells),
            "family_label_matched": counts_of(family_all),
            "family_bpw_matched": counts_of(family),
            "same_scaffold_label_matched": counts_of(scaffold),
            "same_scaffold_bpw_matched": counts_of(scaffold_readable),
            "recipe_controls": counts_of(recipe),
            "quant_label_missing_cells": sum(1 for c in cells if c["quant_label_missing"]),
            "quant_label_missing_family_bpw_matched": sum(1 for c in family if c["quant_label_missing"]),
            "family_pairs_with_cells": len({(c["family_a"], c["family_b"]) for c in family_all}),
            "family_pairs_readable": len({(c["family_a"], c["family_b"]) for c in family}),
            "family_pairs_unreadable": sorted(
                f"{a} | {b}" for a, b in
                {(c["family_a"], c["family_b"]) for c in family_all}
                - {(c["family_a"], c["family_b"]) for c in family}),
            "interaction_groups": len(interaction),
            "groups_with_two_levels": sum(1 for g in interaction if g["n_levels"] >= 2),
            "sign_flips": sum(g["flips"] for g in interaction),
            "flip_groups": sum(1 for g in interaction if g["flips"]),
            "ambiguous_levels": sum(1 for g in interaction for l in g["levels"] if l["sign"] is None),
            "orderings": len(orderings),
            "orderings_comparable": sum(1 for o in orderings if o["stable"] is not None),
            "orderings_unstable": sum(1 for o in orderings if o["stable"] is False),
        },
        "warnings": warnings,
        "cells": cells,
        "recipe": recipe,
        "interaction": interaction,
        "orderings": orderings,
        "independence": independence,
    }


def fmt_ci(ci) -> str:
    if ci is None:
        return "     n/a     "
    return f"[{ci[0]:.3f},{ci[1]:.3f}]"


def cell_line(c: dict) -> str:
    return (f"  {c['id']:<8} {c['bench']:<22} {(c['family_a'] + ' — ' + c['family_b'])[:41]:<42} "
            f"{str(c['quant']):<12} {c['bpw_mean']:>5.2f} {c['bpw_gap']:>5.3f} "
            f"{c['delta_pp']:>+8.2f} {fmt_ci(c['ci_a']):<17} {fmt_ci(c['ci_b']):<17} "
            f"{'yes' if c['resolvable'] else 'no'}")


CELL_HEAD = (f"  {'id':<8} {'bench':<22} {'family_a — family_b':<42} {'quant':<12} "
             f"{'bpw':>5} {'gap':>5} {'Δpp':>8} {'ci_a':<17} {'ci_b':<17} RES")
FILE_HEAD = (f"  {'id':<8} {'bench':<18} {'model_a':<34} {'model_b':<34} "
             f"{'bpw':>5} {'gap':>5} {'Δpp':>8} {'ci_a':<17} {'ci_b':<17} RES")


def file_line(c: dict) -> str:
    """(e)/(f) 两段的家族名相同或无信息，所以按文件名印。"""
    return (f"  {c['id']:<8} {c['bench']:<18} {c['model_a'][:33]:<34} {c['model_b'][:33]:<34} "
            f"{c['bpw_mean']:>5.2f} {c['bpw_gap']:>5.3f} {c['delta_pp']:>+8.2f} "
            f"{fmt_ci(c['ci_a']):<17} {fmt_ci(c['ci_b']):<17} "
            f"{'yes' if c['resolvable'] else 'no'}")


def report(res: dict) -> None:
    c = res["counts"]
    lm, fb = c["family_label_matched"], c["family_bpw_matched"]
    print("family effects (from analysis/pairs.json; family = mktables.family_of)")
    print(f"  bpw gate                     : |bpw_a − bpw_b| <= {res['bpw_match_tol']} bpw "
          f"(half a {res['bpw_match_tol'] * 2} bpw quant level, measured tensor bpw)")
    print(f"  label_matched cells (tier 1) : {c['label_matched_cells']['cells']} "
          f"(quant label NULL on {c['quant_label_missing_cells']} of them)")
    print(f"  family cells, label_matched  : {lm['cells']} → resolvable {lm['resolvable']} "
          f"[inventory only: bits not matched]")
    print(f"  family cells, bpw_matched    : {fb['cells']} → resolvable {fb['resolvable']} "
          f"({fb['cells_with_intervals']} carry intervals, n_items missing {fb['n_items_missing']}) "
          f"← the family claim lives here")
    print(f"  same-scaffold cells (same n_params, different family name): "
          f"{c['same_scaffold_label_matched']['cells']} label_matched, "
          f"{c['same_scaffold_bpw_matched']['cells']} bpw_matched → not family, see (e)")
    print(f"  recipe controls (same family, same weights, bpw-matched): "
          f"{c['recipe_controls']['cells']} cells → see (f)")
    print(f"  family pairs with cells      : {c['family_pairs_with_cells']} "
          f"(readable: {c['family_pairs_readable']}, not readable: "
          f"{len(c['family_pairs_unreadable'])})")
    for w in res["warnings"]:
        print(f"  WARN {w}")

    print("\n(a) family cells at matched effective bpw (Δ = b − a, percentage points; "
          "* = the two Wilson intervals are disjoint)")
    print(CELL_HEAD)
    for cell in sorted(res["cells"], key=lambda x: (x["bench"], x["family_a"], x["bpw_mean"])):
        if cell["same_n_params"] or not cell["bpw_matched"]:
            continue
        print(cell_line(cell))

    print("\n(b) sign of Δ across quant levels, fixed size pair + fixed context "
          f"— {c['interaction_groups']} groups ({c['groups_with_two_levels']} with >= 2 levels); "
          f"sign flips: {c['sign_flips']}")
    for g in sorted(res["interaction"], key=lambda g: (-g["n_levels"], g["bench"], g["family_a"])):
        if g["n_levels"] < 2:
            continue
        lv = " ".join(f"{'+' if l['sign'] > 0 else ('-' if l['sign'] < 0 else ('0' if l['sign'] == 0 else '?'))}"
                      f"@{l['bpw_mean']:.2f}" for l in g["levels"])
        print(f"    {g['bench']:<22} {g['family_a']:<38} vs {g['family_b']:<38} "
              f"n_levels={g['n_levels']} signs {lv} → {'FLIP' if g['flips'] else 'same'}")
        if g["flips"]:
            for i in range(len(g["levels"]) - 1):
                a, b = g["levels"][i], g["levels"][i + 1]
                if a["sign"] is not None and b["sign"] is not None and a["sign"] * b["sign"] < 0:
                    print(f"        {','.join(a['ids'])} ({a['delta_pp']:+.1f}pp @{a['bpw_mean']:.2f})"
                          f" → {','.join(b['ids'])} ({b['delta_pp']:+.1f}pp @{b['bpw_mean']:.2f})")

    print("\n(c) family Δ vs same-cluster quant Δ, same unit (pp), same fixed size pair")
    print(f"    {'bench':<22} {'family pair':<56} {'lvls':>4} {'Δfam@low':>9} {'Δfam@high':>10} "
          f"{'quantΔa':>8} {'quantΔb':>8} {'bpw span':>9}")
    for g in sorted(res["interaction"], key=lambda g: (g["bench"], g["family_a"], g["family_b"])):
        if g["n_levels"] < 2:
            continue
        print(f"    {g['bench']:<22} {(g['family_a'] + ' vs ' + g['family_b'])[:55]:<56} "
              f"{g['n_levels']:>4} {g['family_delta_pp_low']:>+9.2f} {g['family_delta_pp_high']:>+10.2f} "
              f"{g['quant_effect_pp_a']:>+8.2f} {g['quant_effect_pp_b']:>+8.2f} {g['quant_span_bpw']:>9.3f}")

    print(f"\n(d) family ordering per bench (family cells at bpw_matched) — {c['orderings']} "
          f"bench×context groups, {c['orderings_comparable']} comparable (same family set at >= 2 "
          f"levels), {c['orderings_unstable']} change order")
    for o in sorted(res["orderings"], key=lambda o: (o["bench"], o["ctx_key"])):
        lvls = ", ".join(f"{lvl}: {' > '.join(v['ranking'])}" for lvl, v in sorted(o["levels"].items()))
        state = ("STABLE" if o["stable"] else ("CHANGES" if o["stable"] is False else "n/a"))
        print(f"    {o['bench']:<22} {state:<8} {lvls}")
        if o["not_comparable_levels"]:
            print(f"        not comparable (different family set): {o['not_comparable_levels']}")
        if o["skipped_levels"]:
            print(f"        skipped (family has >1 model at this level): {o['skipped_levels']}")

    sc = [c for c in res["cells"] if c["same_n_params"] and c["bpw_matched"]]
    print(f"\n(e) same-scaffold cells (identical true n_params ⇒ same tensor shapes; the difference is "
          f"weights/recipe, not architecture) — {len(sc)} bpw_matched, NOT in family counts")
    print(FILE_HEAD)
    for cell in sorted(sc, key=lambda x: (x["bench"], x["model_a"], x["bpw_mean"])):
        print(file_line(cell))

    print(f"\n(f) recipe controls (same family_of, same true n_params, |Δbpw| <= "
          f"{res['bpw_match_tol']} — 'same weights, same effective bits, different file')")
    print(FILE_HEAD)
    for cell in sorted(res["recipe"], key=lambda x: (x["bench"], x["id"])):
        print(file_line(cell))

    print(f"\n(g) independence: {len(res['independence'])} (family pair, bench) groups; "
          "cells are NOT independent samples — this is the per-group count")
    print(f"    {'family_a':<38} {'family_b':<38} {'bench':<22} {'cells':>6} {'bpwOK':>6} "
          f"{'resolv':>7} {'ctxs':>5}")
    for g in res["independence"]:
        print(f"    {g['family_a']:<38} {g['family_b']:<38} {g['bench']:<22} {g['cells']:>6} "
              f"{g['bpw_matched']:>6} {g['resolvable_cells']:>7} {g['distinct_contexts']:>5}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--quiet", action="store_true", help="只打印结论行")
    ap.add_argument("--key-cells", action="store_true",
                    help="只打印家族层 bpw_matched 的逐格表，供文档引用")
    ap.add_argument("--all-cells", action="store_true",
                    help="再打印 label_matched 的家族格全集（清单，不可当家族结论读）")
    args = ap.parse_args(argv)

    if not args.ledger.is_file():
        print(f"BLOCKED: ledger not found: {args.ledger} (run pairs.py first)", file=sys.stderr)
        return 2
    with open(args.ledger, encoding="utf-8") as fh:
        ledger = json.load(fh)
    if not ledger.get("cells"):
        print("BLOCKED: ledger carries zero controlled cells — nothing to analyse", file=sys.stderr)
        return 2

    res = analyse(ledger)
    if args.key_cells:
        print("family cells at matched effective bpw "
              f"(|bpw_a − bpw_b| <= {res['bpw_match_tol']} bpw, different measured n_params)")
        print(CELL_HEAD)
        for cell in sorted(res["cells"], key=lambda x: (x["bench"], x["family_a"], x["bpw_mean"])):
            if cell["same_n_params"] or not cell["bpw_matched"]:
                continue
            print(cell_line(cell))
        return 0
    if args.all_cells:
        print(f"label_matched family cells (inventory; {res['counts']['quant_label_missing_cells']} "
              "of all cells have a NULL quant label, so bits are NOT matched here)")
        print(CELL_HEAD)
        for cell in sorted(res["cells"], key=lambda x: (x["bench"], x["family_a"], x["bpw_mean"])):
            if cell["same_n_params"]:
                continue
            print(cell_line(cell) + ("" if cell["bpw_matched"] else "  (bits not matched)"))
        return 0
    if not args.quiet:
        report(res)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, separators=(",", ":"))
            fh.write("\n")
        if not args.quiet:
            shown = args.out.relative_to(REPO) if REPO in args.out.parents else args.out
            print(f"\n  effects written: {shown}")
    c = res["counts"]
    fb = c["family_bpw_matched"]
    print(f"SUMMARY label_matched={c['label_matched_cells']['cells']} "
          f"family_bpw_matched={fb['cells']} family_resolvable={fb['resolvable']} "
          f"readable_pairs={c['family_pairs_readable']}/{c['family_pairs_with_cells']} "
          f"flips={c['sign_flips']} groups={c['interaction_groups']} "
          f"unstable_orderings={c['orderings_unstable']} "
          f"same_scaffold_bpw_matched={c['same_scaffold_bpw_matched']['cells']} "
          f"recipe_controls={c['recipe_controls']['cells']} warnings={len(res['warnings'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
