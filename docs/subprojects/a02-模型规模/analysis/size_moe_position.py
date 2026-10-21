#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP5：同样激活参数量下，MoE 站在稠密曲线的哪个位置。

做法：只在稠密点上拟 `score ~ log(实测总参)`，再对每个 MoE 反解
`S_eff = exp((score - b0) / b1)`——即「等效稠密规模」，然后给出 `S_eff / 激活参` 与
`S_eff / 总参`。若激活参数就是全部，两个比值应分别贴近 1 与 0。

边界（写死在结论里）：这是**跨家族**比较，tokenizer、训练数据、代数都不同，所以结论只能
是「MoE 锚点落在稠密曲线的哪一侧、差多少」，不能是「MoE 架构带来多少增益」。库内没有
「同家族同权重的稠密/MoE 对」——这正是 `plan5` 不可识别的原因，也不是本脚本能补的。

    python3 "docs/subprojects/a02-模型规模/analysis/size_moe_position.py"
    python3 "docs/subprojects/a02-模型规模/analysis/size_moe_position.py" --check
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = HERE / "moe_position.json"

sys.path.insert(0, str(HERE))
from size_regression import load_points, ln_size, ols_wls  # noqa: E402  同一个估计器，不复制


def main(argv):
    pts = load_points()
    dense = [p for p in pts if not p["is_moe"]]
    moe = [p for p in pts if p["is_moe"]]
    X, y, w = [], [], []
    for p in dense:
        X.append([1.0, ln_size(p)])
        y.append(p["score"])
        var = max(p["score"] * (1 - p["score"]) / p["n"], 1e-6)
        w.append(1.0 / var)
    fit = ols_wls(y, X, w)
    b0, b1 = fit["beta"]

    rows = []
    for p in moe:
        eff = math.exp((p["score"] - b0) / b1)
        rows.append({
            "model": p["model"], "family": p["family"],
            "total_b": round(p["size"], 3), "active_b": round(p["active"], 3),
            "score": round(p["score"], 4), "n_items": p["n"],
            "effective_dense_b": round(eff, 2),
            "eff_over_active": round(eff / p["active"], 2),
            "eff_over_total": round(eff / p["size"], 2),
        })
    rows.sort(key=lambda d: d["active_b"])

    print(f"dense curve: score = {b0:.4f} + {b1:.4f}·ln(params_b)   n={fit['n']}  adjR²={fit['adj_r2']:.3f}")
    print(f"\n{'MoE':44s} {'total':>6s} {'active':>7s} {'score':>6s} {'S_eff':>7s} "
          f"{'S_eff/active':>12s} {'S_eff/total':>11s}")
    for r in rows:
        print(f"{r['model'][:44]:44s} {r['total_b']:6.2f} {r['active_b']:7.2f} {r['score']:6.3f} "
              f"{r['effective_dense_b']:7.2f} {r['eff_over_active']:12.2f} {r['eff_over_total']:11.2f}")

    above = [r for r in rows if r["eff_over_active"] > 1.0]
    print(f"\n落在稠密曲线之上（等效稠密规模 > 激活参）的 MoE：{len(above)}/{len(rows)}")
    print("跨家族比较：tokenizer 与训练数据都不同，不能读成架构增益。库里没有同家族稠密/MoE 对。")

    OUT.write_text(json.dumps({"dense_curve": {"b0": b0, "b1": b1, "n": fit["n"],
                                               "adj_r2": fit["adj_r2"]},
                               "moe": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")

    if "--check" in argv:
        ok = fail = 0

        def want(c, label):
            nonlocal ok, fail
            if c:
                ok += 1
            else:
                fail += 1
                print(f"  FAIL  {label}")

        want(len(moe) > 0 and len(moe) + len(dense) == len(pts), "MoE 点非空且点数闭合")
        want(fit["beta"][1] > 2 * fit["se"][1], "稠密曲线的斜率显著为正")
        want(all(r["eff_over_total"] < 3.0 for r in rows), "等效稠密规模不超过总参的 3 倍（反解没有失控）")
        want(all(0.2 < r["eff_over_active"] < 50 for r in rows), "S_eff/active 落在合理量级")
        print(f"  {ok} expected true, {fail} false")
        return 0 if fail == 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
