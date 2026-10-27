#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""家族效应与家族×量化档交互：从 `pairs.py` 的清单算，不碰库。

输入是 `analysis/pairs.json`（`pairs.py` 产出，一行一个受控格），输出人读文本 + `analysis/effects.json`。
本脚本自己不做任何筛选：受控集由 `pairs.py` 决定，这里只做算术。

口径（每个数都从这份清单里算，没有一个是手抄的）：

* `delta_pp` = (score_b − score_a) × 100，单位百分点；a/b 是清单里的 `family_a`/`family_b`。
* 每个分数按它自己的 `n_items` 给一个 95% Wilson 区间；两区间不相交才算 `resolvable`（差异可分辨）。
* 位宽是**测出来**的（GGUF 张量 bpw），不是标签：`bpw_gap = |bpw_a − bpw_b|`。
  一个「量化档」= 平均 bpw 的 `LEVEL_W`（0.5 bpw）宽的桶；`bpw_matched` = 两侧位宽差 ≤ `BPW_MATCH_TOL`
  （= `LEVEL_W/2` = 0.25 bpw）。前者用于把两个文件当成同一个档位，后者是唯一的可读性闸门：差超过半档的格
  把比特预算也混了进来，不能读成家族效应。
* **规模对固定**：交互分析的分组键是 (bench, 其余身份栏, family_a, n_params_a, family_b, n_params_b)——
  同一个基座模型在不同量化档上真参数量不变，所以「同一对规模」是算出来的，不是按文件名猜的。
  组内按档位（bpw 桶）排序，相邻两档的 Δ 符号相反记一次翻转；还把「翻转是否可比」分两层：
  `sign_flips_all` 是全部翻转，`sign_flips_readable` 只数两档的位宽 handicap 相差 ≤ 半档的（即两侧的
  比特差被提成了常数，符号变化才能归给交互），`sign_flips_zero_gap` 再严一层，要求两档都位宽相等。
* **家族差与量化差同单位**：同一组里，家族 Δ 与「同族跨量化档的分数差」（`quant_effect_pp`）都是 pp。

`BPW_MATCH_TOL` 的自检：它必须不大于本清单里测到的**最小档间距**（按档中位 bpw 算），否则脚本打印
`WARN` 并把它算进 `warnings`（`run_all.py` 因此判红）。这不是承诺，是每次运行都算一遍的检查。

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
LEVEL_W = 0.5     # bpw；一个「量化档」的宽度（本库相邻 Q 档相距 0.5–1.0 bpw）
BPW_MATCH_TOL = LEVEL_W / 2.0  # bpw；两侧位宽差在半个档宽之内才算「同一档」
CTX_COLS = None        # 由清单自报的键序填充


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


def ctx_key(cell: dict) -> str:
    sig = cell["ctx_sig"]
    return "|".join(f"{c}={sig[c]}" for c in CTX_COLS)


def decode(ledger: dict) -> list[dict]:
    """把清单里的 `cells` 展开成带家族名与 `ctx_sig` 字典的格子（落盘时这些是压缩存的）。"""
    fam = ledger["families"]
    cols = ledger["ctx_columns"]
    out = []
    for p in ledger["cells"]:
        q = dict(p)
        q["family_a"] = fam[p["model_a"]]
        q["family_b"] = fam[p["model_b"]]
        q["ctx_sig"] = dict(zip(cols, p["ctx"]))
        q["protocol"] = q["ctx_sig"].get("protocol")
        out.append(q)
    return out


def analyse(ledger: dict) -> dict:
    global CTX_COLS
    CTX_COLS = list(ledger["ctx_columns"])

    raw = decode(ledger)
    cells = []
    for p in raw:
        n = p["n_items"]
        ca = wilson(p["score_a"], n) if n else None
        cb = wilson(p["score_b"], n) if n else None
        gap = abs(p["bpw_a"] - p["bpw_b"])
        cells.append({
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
            "bpw_gap": round(gap, 4),
            "bpw_mean": round((p["bpw_a"] + p["bpw_b"]) / 2.0, 4),
            "bpw_matched": gap <= BPW_MATCH_TOL,
            "size_delta": p["size_delta"],
            "protocol": p["protocol"],
        })

    # ---- 分组：同一对规模 + 同一批其余身份栏 -------------------------------------------
    # 上下文签名不存进 `cells`（它的 SSOT 是 `pairs.json` 的 `ctx`，这里按 `id` 引用），但分组要用。
    ctx_of = {p["id"]: ctx_key(p) for p in raw}
    # 同一 (bench, ctx, family pair) 下还可能对应不同的规模对（gemma-4 有 E2B 与 E4B），所以
    # 分组键里带 (n_params_a, n_params_b)：同一基座模型换量化档时真参数量不变，这个键把「同一对
    # 规模的两档」与「不同规模对」机械地分开，不靠文件名里的 size 标签。
    npar = {p["id"]: (p["n_params_a"], p["n_params_b"]) for p in ledger["cells"]}
    sized: dict[tuple, list[dict]] = defaultdict(list)
    for c in cells:
        npa, npb = npar[c["id"]]
        sized[(c["bench"], ctx_of[c["id"]], c["family_a"], npa, c["family_b"], npb)].append(c)

    interaction = []
    for key, cs in sorted(sized.items(), key=lambda kv: tuple(str(v) for v in kv[0])):
        bench, ck, fa, npa, fb, npb = key
        # 档 = 平均 bpw 的 0.5 bpw 宽的桶（`LEVEL_W`）：同一档上「换了配方但落在同一位宽」的两个
        # 文件会落进同一个桶，而不是被当成两个「相邻档」。桶内符号不统一时把该档记为不可判。
        buckets: dict[int, list[dict]] = defaultdict(list)
        for c in cs:
            buckets[int(c["bpw_mean"] // LEVEL_W)].append(c)
        levels = []
        for b in sorted(buckets):
            bc = sorted(buckets[b], key=lambda c: c["id"])
            signs_in = {0 if c["delta_pp"] == 0 else (1 if c["delta_pp"] > 0 else -1) for c in bc}
            levels.append({
                "bucket": b,
                "ids": [c["id"] for c in bc],
                "quant_labels": sorted({str(c["quant"]) for c in bc}),
                "bpw_min": min(c["bpw_mean"] for c in bc),
                "bpw_max": max(c["bpw_mean"] for c in bc),
                "bpw_matched": all(c["bpw_matched"] for c in bc),
                "bpw_gap": round(sum(c["bpw_gap"] for c in bc) / len(bc), 4),
                "delta_pp": round(sum(c["delta_pp"] for c in bc) / len(bc), 4),
                "delta_pp_range": [min(c["delta_pp"] for c in bc), max(c["delta_pp"] for c in bc)],
                "score_a": bc[0]["score_a"],
                "score_b": bc[0]["score_b"],
                "resolvable": all(c["resolvable"] for c in bc),
                "sign": signs_in.pop() if len(signs_in) == 1 else None,
            })
        levels.sort(key=lambda l: ((l["bpw_min"] + l["bpw_max"]) / 2.0, l["bucket"]))
        signs = [l["sign"] for l in levels]
        flips = [i for i in range(len(levels) - 1)
                 if signs[i] is not None and signs[i + 1] is not None
                 and signs[i] * signs[i + 1] < 0]
        # 交互读法（翻转）要把两侧的「位宽 handicap」提成常数：两档的 |bpw_a − bpw_b| 相差不超过
        # 半个档宽，则两档上家族差可比，符号变化可以归给交互而不是位宽漂移。
        flips_readable = [i for i in flips
                          if abs(levels[i]["bpw_gap"] - levels[i + 1]["bpw_gap"]) <= BPW_MATCH_TOL]
        flips_zero_gap = [i for i in flips
                          if levels[i]["bpw_matched"] and levels[i + 1]["bpw_matched"]]
        undefined = [i for i in range(len(levels) - 1)
                     if signs[i] is None or signs[i + 1] is None]
        lo, hi = levels[0], levels[-1]
        interaction.append({
            "bench": bench,
            "ctx_key": ck,
            "family_a": fa,
            "family_b": fb,
            "n_params_a": npa,
            "n_params_b": npb,
            "levels": levels,
            "n_levels": len(levels),
            "signs": signs,
            "flips": len(flips),
            "flips_readable": len(flips_readable),
            "flips_zero_gap": len(flips_zero_gap),
            "undefined_adjacent_pairs": len(undefined),
            "flip_cells": [[levels[i]["ids"], levels[i + 1]["ids"]] for i in flips],
            "flip_cells_readable": [[levels[i]["ids"], levels[i + 1]["ids"]] for i in flips_readable],
            "flip_cells_zero_gap": [[levels[i]["ids"], levels[i + 1]["ids"]] for i in flips_zero_gap],
            "family_delta_pp_low": lo["delta_pp"],
            "family_delta_pp_high": hi["delta_pp"],
            "quant_effect_pp_a": (round((hi["score_a"] - lo["score_a"]) * 100.0, 4)
                                  if len(levels) > 1 else None),
            "quant_effect_pp_b": (round((hi["score_b"] - lo["score_b"]) * 100.0, 4)
                                  if len(levels) > 1 else None),
            "quant_span_bpw": (round((hi["bpw_min"] + hi["bpw_max"]) / 2.0
                                     - (lo["bpw_min"] + lo["bpw_max"]) / 2.0, 4)
                               if len(levels) > 1 else None),
        })

    # ---- 每个基准上的家族排序 ---------------------------------------------------------
    orderings = []
    by_bench_ctx_level: dict[tuple, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for c in cells:
        if not c["bpw_matched"]:
            continue
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
    for (bench, ck), per_level in sorted(by_bench_ctx.items()):
        good = {lvl: v for lvl, v in per_level.items() if "ranking" in v}
        bad = {lvl: v for lvl, v in per_level.items() if "ranking" not in v}
        # 只有**同一批家族**的两个档才能比排序：家族的集合不同，排序差别只是集合差的假象。
        by_set: dict[frozenset, dict[str, dict]] = defaultdict(dict)
        for lvl, v in good.items():
            by_set[frozenset(v["ranking"])][lvl] = v
        comparable = {lvl: v for grp in by_set.values() if len(grp) >= 2 for lvl, v in grp.items()}
        changed = []
        for fams, grp in by_set.items():
            if len(grp) < 2:
                continue
            rankings = {tuple(v["ranking"]) for v in grp.values()}
            if len(rankings) > 1:
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

    # ---- 自检：容差必须小于最小的相邻档间距 --------------------------------------------
    steps = []
    for g in interaction:
        lv = g["levels"]
        for i in range(len(lv) - 1):
            mid_lo = (lv[i]["bpw_min"] + lv[i]["bpw_max"]) / 2.0
            mid_hi = (lv[i + 1]["bpw_min"] + lv[i + 1]["bpw_max"]) / 2.0
            steps.append(mid_hi - mid_lo)
    min_step = min(steps) if steps else None
    warnings = []
    if min_step is None:
        warnings.append("no two-level group in the ledger: BPW_MATCH_TOL is unverified")
    elif BPW_MATCH_TOL > min_step:
        warnings.append(f"BPW_MATCH_TOL={BPW_MATCH_TOL} > min_level_step={min_step:.4f}")
    if any(l["sign"] is None for g in interaction for l in g["levels"]):
        # 不是错误：同一档位上两套配方分数方向相反，本身是分辨率边界的一部分，见 counts。
        pass

    readable = [c for c in cells if c["bpw_matched"]]
    # 逐家族对：有格子、但没有一格两方位宽相差 ≤ 半档的，就是「这一对读不出家族差」。
    fp_readable = sorted({f"{c['family_a']} | {c['family_b']}" for c in readable})
    fp_all = sorted({f"{c['family_a']} | {c['family_b']}" for c in cells})
    fp_unreadable = [fp for fp in fp_all if fp not in set(fp_readable)]
    return {
        "what": "受控对的家族效应、家族×量化档交互、家族排序（全部由 pairs.json 算出）",
        "generated_by": "docs/subprojects/a15-模型家族/analysis/effects.py",
        "bpw_match_tol": BPW_MATCH_TOL,
        "wilson_z": Z,
        "counts": {
            "controlled_cells": len(cells),
            "cells_with_intervals": sum(1 for c in cells if c["ci_a"] is not None),
            "n_items_missing": sum(1 for c in cells if c["n_items_missing"]),
            "resolvable_all": sum(1 for c in cells if c["resolvable"]),
            "bpw_matched_cells": len(readable),
            "resolvable_bpw_matched": sum(1 for c in readable if c["resolvable"]),
            "bpw_gap_min": min((c["bpw_gap"] for c in cells), default=None),
            "bpw_gap_max": max((c["bpw_gap"] for c in cells), default=None),
            "min_quant_step_bpw": round(min_step, 4) if min_step is not None else None,
            "undefined_adjacent_pairs": sum(g["undefined_adjacent_pairs"] for g in interaction),
            "ambiguous_levels": sum(1 for g in interaction for l in g["levels"] if l["sign"] is None),
            "sign_flips_zero_gap": sum(g["flips_zero_gap"] for g in interaction),
            "interaction_groups": len(interaction),
            "groups_with_two_levels": sum(1 for g in interaction if g["n_levels"] >= 2),
            "sign_flips_all": sum(g["flips"] for g in interaction),
            "sign_flips_readable": sum(g["flips_readable"] for g in interaction),
            "family_pairs_with_cells": len(fp_all),
            "family_pairs_readable": len(fp_readable),
            "family_pairs_unreadable": fp_unreadable,
            "orderings": len(orderings),
            "orderings_comparable": sum(1 for o in orderings if o["stable"] is not None),
            "orderings_unstable": sum(1 for o in orderings if o["stable"] is False),
        },
        "warnings": warnings,
        "cells": cells,
        "interaction": interaction,
        "orderings": orderings,
    }


def fmt_ci(ci) -> str:
    if ci is None:
        return "     n/a     "
    return f"[{ci[0]:.3f},{ci[1]:.3f}]"


def report(res: dict) -> None:
    c = res["counts"]
    print("family effects (from analysis/pairs.json)")
    print(f"  controlled cells            : {c['controlled_cells']}")
    print(f"  cells with Wilson intervals : {c['cells_with_intervals']} "
          f"(n_items missing: {c['n_items_missing']})")
    print(f"  resolvable (all cells)      : {c['resolvable_all']}")
    print(f"  bpw_matched cells (<= {res['bpw_match_tol']} bpw) : {c['bpw_matched_cells']} "
          f"→ resolvable {c['resolvable_bpw_matched']}")
    print(f"  bpw gap range               : {c['bpw_gap_min']:.3f} … {c['bpw_gap_max']:.3f} bpw")
    print(f"  family pairs with cells     : {c['family_pairs_with_cells']} "
          f"(readable: {c['family_pairs_readable']}, not readable: {c['family_pairs_unreadable']})")
    print(f"  smallest level step seen    : {c['min_quant_step_bpw']} bpw"
          f" (level width {LEVEL_W} bpw, tolerance {BPW_MATCH_TOL} bpw)")
    for w in res["warnings"]:
        print(f"  WARN {w}")

    print("\n(a) per-cell deltas (b − a, percentage points; * = resolvable, q = bpw_matched)")
    hdr = (f"  {'id':<8} {'bench':<22} {'quant':<12} {'a':<38} {'b':<38} "
           f"{'Δpp':>8}  {'ci_a':<17} {'ci_b':<17} {'bpw':>6} {'gap':>6} FL")
    print(hdr)
    for cell in sorted(res["cells"], key=lambda x: (x["bench"], x["family_a"], x["family_b"], x["bpw_mean"])):
        flags = ("*" if cell["resolvable"] else " ") + ("q" if cell["bpw_matched"] else " ")
        print(f"  {cell['id']:<8} {cell['bench']:<22} {str(cell['quant']):<12} "
              f"{cell['model_a'][:37]:<38} {cell['model_b'][:37]:<38} "
              f"{cell['delta_pp']:>+8.2f}  {fmt_ci(cell['ci_a']):<17} {fmt_ci(cell['ci_b']):<17} "
              f"{cell['bpw_mean']:>6.2f} {cell['bpw_gap']:>6.3f} {flags}")

    print("\n(b) sign of Δ across quant levels, within a fixed size pair + fixed context"
          f" — {c['interaction_groups']} groups, {c['groups_with_two_levels']} with >= 2 levels")
    print(f"    sign flips: {c['sign_flips_all']} (constant bit-width handicap: "
          f"{c['sign_flips_readable']}; both levels bpw_matched: {c['sign_flips_zero_gap']}); "
          f"adjacent level pairs with an undefined level: {c['undefined_adjacent_pairs']} "
          f"(levels with two disagreeing cells: {c['ambiguous_levels']})")
    for g in sorted(res["interaction"], key=lambda g: (-g["flips_readable"], -g["n_levels"],
                                                       g["bench"], g["family_a"])):
        if g["n_levels"] < 2:
            continue
        lv = " ".join(f"{'?' if l['sign'] is None else ('+' if l['sign'] > 0 else ('-' if l['sign'] < 0 else '0'))}"
                      f"@{l['bpw_min']:.2f}-{l['bpw_max']:.2f}" for l in g["levels"])
        tag = "FLIP" if g["flips"] else "same"
        if g["flips"] != g["flips_readable"]:
            tag += f" ({g['flips'] - g['flips_readable']} of them move the bit-width handicap)"
        print(f"    {g['bench']:<22} {g['family_a']:<22} vs {g['family_b']:<22} "
              f"n_levels={g['n_levels']} signs {lv} → {tag}")
        if g["flips"]:
            for i in range(len(g["levels"]) - 1):
                a, b = g["levels"][i], g["levels"][i + 1]
                if a["sign"] is not None and b["sign"] is not None and a["sign"] * b["sign"] < 0:
                    print(f"        {','.join(a['ids'])} ({a['delta_pp']:+.1f}pp @{a['bpw_min']:.2f}, "
                          f"gap {a['bpw_gap']:.2f}) → "
                          f"{','.join(b['ids'])} ({b['delta_pp']:+.1f}pp @{b['bpw_min']:.2f}, "
                          f"gap {b['bpw_gap']:.2f})")

    print("\n(c) family Δ vs same-cluster quant Δ, same unit (pp), same fixed size pair")
    print(f"    {'bench':<22} {'family pair':<44} {'levels':>6} {'Δfam@low':>9} {'Δfam@high':>10} "
          f"{'quantΔa':>8} {'quantΔb':>8} {'bpw span':>9}")
    for g in sorted(res["interaction"], key=lambda g: (g["bench"], g["family_a"], g["family_b"])):
        if g["n_levels"] < 2:
            continue
        print(f"    {g['bench']:<22} {g['family_a'] + ' vs ' + g['family_b']:<44} "
              f"{g['n_levels']:>6} {g['family_delta_pp_low']:>+9.2f} {g['family_delta_pp_high']:>+10.2f} "
              f"{g['quant_effect_pp_a']:>+8.2f} {g['quant_effect_pp_b']:>+8.2f} {g['quant_span_bpw']:>9.3f}")

    print(f"\n(d) family ordering per bench (bpw_matched cells only) — "
          f"{c['orderings']} bench×context groups, {c['orderings_comparable']} comparable "
          f"(same family set at >= 2 quant levels), {c['orderings_unstable']} change order")
    for o in sorted(res["orderings"], key=lambda o: (o["bench"], o["ctx_key"])):
        lvls = ", ".join(f"{lvl}: {' > '.join(v['ranking'])}" for lvl, v in sorted(o["levels"].items()))
        state = ("STABLE" if o["stable"] else ("CHANGES" if o["stable"] is False else "n/a"))
        print(f"    {o['bench']:<22} {state:<8} {lvls}")
        if o["not_comparable_levels"]:
            print(f"        not comparable (different family set): {o['not_comparable_levels']}")
        if o["skipped_levels"]:
            print(f"        skipped (family has >1 model at this level): {o['skipped_levels']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--quiet", action="store_true", help="只打印结论行")
    ap.add_argument("--key-cells", action="store_true",
                    help="只打印可读子集（两侧位宽差 ≤ 半档）的逐格表，供文档引用")
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
        print("bpw_matched cells only (|bpw_a − bpw_b| <= "
              f"{res['bpw_match_tol']} bpw = half a quant level)")
        print(f"  {'id':<8} {'bench':<22} {'family_a — family_b':<42} {'quant':<12} "
              f"{'bpw':>5} {'gap':>5} {'Δpp':>8} {'ci_a':<17} {'ci_b':<17} RES")
        for c in sorted((c for c in res["cells"] if c["bpw_matched"]),
                        key=lambda x: (x["bench"], x["family_a"], x["bpw_mean"])):
            print(f"  {c['id']:<8} {c['bench']:<22} "
                  f"{(c['family_a'] + ' — ' + c['family_b'])[:41]:<42} {str(c['quant']):<12} "
                  f"{c['bpw_mean']:>5.2f} {c['bpw_gap']:>5.3f} {c['delta_pp']:>+8.2f} "
                  f"{fmt_ci(c['ci_a']):<17} {fmt_ci(c['ci_b']):<17} "
                  f"{'yes' if c['resolvable'] else 'no'}")
        return 0
    if not args.quiet:
        report(res)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            # 派生产物按一行存：人读的部分是 report()/--key-cells 打印的表，文件本身只给脚本与审计用。
            json.dump(res, fh, ensure_ascii=False, separators=(",", ":"))
            fh.write("\n")
        if not args.quiet:
            shown = args.out.relative_to(REPO) if REPO in args.out.parents else args.out
            print(f"\n  effects written: {shown}")
    c = res["counts"]
    print(f"SUMMARY cells={c['controlled_cells']} resolvable={c['resolvable_all']} "
          f"bpw_matched={c['bpw_matched_cells']} resolvable_bpw_matched={c['resolvable_bpw_matched']} "
          f"flips={c['sign_flips_all']} flips_constant_gap={c['sign_flips_readable']} "
          f"flips_zero_gap={c['sign_flips_zero_gap']} "
          f"groups={c['interaction_groups']} unstable_orderings={c['orderings_unstable']}"
          f" warnings={len(res['warnings'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
