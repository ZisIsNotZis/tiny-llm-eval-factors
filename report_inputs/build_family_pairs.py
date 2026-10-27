#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 a15「模型家族」的两份确定性产物抽成报告用的派生索引。

来源（都随仓库分发，且由 `docs/subprojects/a15-模型家族/analysis/run_all.py` 当场重算）：
  * `analysis/pairs.json`   —— 受控对清单（label_matched / bpw_matched 两层）
  * `analysis/effects.json` —— 效应、交互与边界计数

报告只读这里生成的那一份；不读子项目文档、不自己再判一次家族。抽不到或关系式不成立就报错，
绝不填 0。

    python3 report_inputs/build_family_pairs.py           # 重写 family_pairs.json
    python3 report_inputs/build_family_pairs.py --check   # 只比对，不重写；rc=1 表示漂移
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "family_pairs.json")
A15 = os.path.join(REPO, "docs", "subprojects", "a15-模型家族", "analysis")
PAIRS = os.path.join(A15, "pairs.json")
EFFECTS = os.path.join(A15, "effects.json")

CELL_FIELDS = [
    "id", "bench", "quant", "family_a", "family_b", "arm_a", "arm_b",
    "model_a", "model_b", "score_a", "score_b", "n_items", "ci_a", "ci_b",
    "delta_pp", "resolvable", "bpw_a", "bpw_b", "bpw_gap", "bpw_mean",
    "quant_label_missing", "size_delta",
]


def build() -> dict:
    with open(EFFECTS, encoding="utf-8") as fh:
        eff = json.load(fh)
    with open(PAIRS, encoding="utf-8") as fh:
        pairs = json.load(fh)

    # 家族层：只取 bpw_matched 且不属于同一组张量形状（same_n_params）的格。
    cells = [c for c in eff["cells"] if c["bpw_matched"] and not c["same_n_params"]]
    fam_counts = eff["counts"]["family_bpw_matched"]
    if len(cells) != fam_counts["cells"]:
        raise SystemExit(f"family cells 不一致：effects.json 计 {fam_counts['cells']}，筛出 {len(cells)}")
    if pairs["counts"].get("bpw_matched_cells") != fam_counts["cells"]:
        raise SystemExit("pairs.json 与 effects.json 的家族 bpw_matched 计数不一致")

    # 逐家族对汇总（报告表格用）。
    by_pair = {}
    for c in cells:
        key = (c["family_a"], c["family_b"])
        d = by_pair.setdefault(key, {"family_a": key[0], "family_b": key[1],
                                     "cells": 0, "resolvable": 0, "benches": set(),
                                     "models": set(), "deltas": []})
        d["cells"] += 1
        d["resolvable"] += 1 if c["resolvable"] else 0
        d["benches"].add(c["bench"])
        d["models"].add(c["model_a"])
        d["models"].add(c["model_b"])
        d["deltas"].append(c["delta_pp"])
    pairs_out = []
    for key in sorted(by_pair):
        d = by_pair[key]
        pairs_out.append({
            "family_a": d["family_a"], "family_b": d["family_b"],
            "cells": d["cells"], "resolvable": d["resolvable"],
            "benches": sorted(d["benches"]),
            "delta_min": min(d["deltas"]), "delta_max": max(d["deltas"]),
            "models": sorted(d["models"]),
        })

    # 翻转组：只保留真正翻的交互组，逐档给出位宽与 Δ。
    flips = []
    for g in eff["interaction"]:
        if not g["flips"]:
            continue
        flips.append({
            "bench": g["bench"], "family_a": g["family_a"], "family_b": g["family_b"],
            "levels": [{
                "quant_labels": lv["quant_labels"],
                "bpw_mean": round(lv["bpw_mean"], 4),
                "delta_pp": lv["delta_pp"],
                "resolvable": lv["resolvable"],
            } for lv in g["levels"]],
        })
    flips.sort(key=lambda f: (f["family_a"], f["family_b"], f["bench"]))

    orderings = [{
        "bench": o["bench"], "comparable_levels": o["comparable_levels"],
        "changed_groups": o["changed_groups"], "stable": o["stable"],
    } for o in eff["orderings"] if o["comparable_levels"]]

    recipe = eff["recipe"]
    recipe_res = [r for r in recipe if r["resolvable"]]
    out = {
        "what": "a15 模型家族轴：bpw_matched（|Δbpw|≤0.25）且不同实测参数量的受控格",
        "generated_by": "report_inputs/build_family_pairs.py",
        "source": {
            "pairs": "docs/subprojects/a15-模型家族/analysis/pairs.json",
            "effects": "docs/subprojects/a15-模型家族/analysis/effects.json",
        },
        "acceptance": "python3 \"docs/subprojects/a15-模型家族/analysis/run_all.py\" --selftest",
        "counts": {
            "family_cells": fam_counts["cells"],
            "family_cells_with_intervals": fam_counts["cells_with_intervals"],
            "family_resolvable": fam_counts["resolvable"],
            "family_pairs_with_cells": eff["counts"]["family_pairs_with_cells"],
            "family_pairs_readable": eff["counts"]["family_pairs_readable"],
            "label_matched_cells": eff["counts"]["label_matched_cells"]["cells"],
            "bpw_matched_cells": eff["counts"]["family_bpw_matched"]["cells"] +
                                 eff["counts"]["same_scaffold_bpw_matched"]["cells"],
            "quant_label_missing_cells": eff["counts"]["quant_label_missing_cells"],
            "quant_label_missing_family_cells": eff["counts"]["quant_label_missing_family_bpw_matched"],
            "sign_flips": eff["counts"]["sign_flips"],
            "interaction_groups": eff["counts"]["interaction_groups"],
            "groups_with_two_levels": eff["counts"]["groups_with_two_levels"],
            "orderings": eff["counts"]["orderings"],
            "orderings_comparable": eff["counts"]["orderings_comparable"],
            "orderings_unstable": eff["counts"]["orderings_unstable"],
            "recipe_controls": eff["counts"]["recipe_controls"]["cells"],
            "recipe_resolvable": eff["counts"]["recipe_controls"]["resolvable"],
        },
        "cells": [{k: c[k] for k in CELL_FIELDS} for c in cells],
        "pairs": pairs_out,
        "flips": flips,
        "orderings": orderings,
        "recipe": {
            "cells": len(recipe),
            "resolvable": len(recipe_res),
            "delta_min": min((r["delta_pp"] for r in recipe), default=None),
            "delta_max": max((r["delta_pp"] for r in recipe), default=None),
            "resolvable_delta_min": min((r["delta_pp"] for r in recipe_res), default=None),
            "resolvable_delta_max": max((r["delta_pp"] for r in recipe_res), default=None),
        },
        "bounds": [
            "家族 = 架构 + 训练配方 + tokenizer 的整包；Δ 只读成家族包效应，不能读成架构效应。",
            "单跑、无逐题产物；可分辨 = 两条 Wilson 区间不相交，不是重测稳定。",
            "同一份权重在同比特预算下换配方就能挪动分数（recipe 块）；跨家族无法匹配配方。",
            "1542/1454 个 label 格（家族层 144/152）的量化标签是 NULL，位宽由 GGUF 张量实测，不靠档位名。",
        ],
    }
    return out


def main() -> int:
    out = build()
    text = json.dumps(out, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    if "--check" in sys.argv:
        if not os.path.exists(OUT):
            print(f"FAIL: {OUT} 不在场")
            return 1
        cur = open(OUT, encoding="utf-8").read()
        if cur != text:
            print(f"FAIL: {OUT} 与 a15 的效应产物不一致；跑 python3 report_inputs/build_family_pairs.py 重生成")
            return 1
        print(f"PASS: family_pairs.json 与 a15 产物一致（{len(out['cells'])} 格 / {len(out['pairs'])} 对）")
        return 0
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {OUT}: {len(out['cells'])} family cells, {len(out['pairs'])} readable pairs, "
          f"{len(out['flips'])} flip groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
