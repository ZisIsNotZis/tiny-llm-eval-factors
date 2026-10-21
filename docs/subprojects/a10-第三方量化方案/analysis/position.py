#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a10 第三方量化方案：第三方档在原生阶梯上的位置（逐基准差 + 区间 + 插值参照）。

X = 「这个文件是不是第三方方案」（文件名带 `GSQ-RCO`）；Y = 9 列基准分数。
同一族（`Qwen3.8-27B`）里本库有 3 个原生档（2.878 / 3.850 / 4.173 比特/权重）与 2 个第三方档
（3.058 / 3.549）。**没有任何一对是同字节的**，所以本装置不假装它们是同字节：

  * 「最近原生档」：位宽差绝对值最小的那一档，逐基准报 `Δ = 第三方 − 原生` 与 Newcombe 区间，
    并把位宽缺口乘上位宽尺子（`a03::slopes`）得到的「缺口值多少分」与残差并列——
    让读者一眼看到这个差里有几分是比特买来的。
  * 「插值档」：把该第三方档的位宽夹在两个原生档之间做线性插值，报 `Δ = 第三方 − 插值`。
    插值的区间是**保守合成**（两侧 95% 半宽相加），因为两个点给不出插值误差；这条比两比例差区间宽，
    所以它判「跨 0」时真结论一定也跨 0。
  * 「原生阶梯自己的段差」：插值的分母就是它。本族的原生阶梯**不单调**（见 `RESULT.md::ladder-own-step`），
    不把这一步打印出来，就等于把一条不单调的阶梯当成直线。

只读 `experiments.sqlite`、`.wrapup/bpw_map.json` 与入库夹具；不加载权重、不占 GPU、不写库。

用法：
    python3 "docs/subprojects/a10-第三方量化方案/analysis/position.py"
    python3 ".../position.py" --bench humaneval-plus
    python3 ".../position.py" --json
"""
from __future__ import annotations

import argparse
import json
import sys

import panel


def slopes():
    """位宽尺子：同族内每 +1 比特/权重的分数变化（`a03::pairs.slopes` 是唯一 home）。"""
    cells, _dups = panel.a03.load()
    return panel.a03.slopes(cells)


def ladder_steps(cells):
    """原生阶梯每一步的逐基准段差与段斜率：插值用的就是这些数。"""
    lad = panel.native_ladder()
    out = []
    for (b0, m0), (b1, m1) in zip(lad, lad[1:]):
        rec = {"low": m0, "high": m1, "bpw_low": b0, "bpw_high": b1, "dbpw": b1 - b0, "cells": {}}
        for bench in panel.BENCH:
            c0, c1 = cells[m0].get(bench), cells[m1].get(bench)
            if c0 is None or c1 is None:
                continue
            d, ci = panel.cell_diff(c1, c0, bench)
            rec["cells"][bench] = {"delta": d, "ci": ci, "slope": d / (b1 - b0),
                                   "n_low": c0["n_items"], "n_high": c1["n_items"]}
        out.append(rec)
    return out


def position_of(tp, cells, sl):
    """第三方档相对最近原生档与插值档的逐基准位置。"""
    x = panel.BPW[tp]
    ties = panel.nearest_native(x)
    br = panel.bracket(x)
    rec = {"file": tp, "bpw": x, "nearest": [], "interp": None}
    for bpw_n, nat in ties:
        near = {"file": nat, "bpw": bpw_n, "dbpw": x - bpw_n, "cells": {}}
        for bench in panel.BENCH:
            a, b = cells[tp].get(bench), cells[nat].get(bench)
            if a is None or b is None:
                near["cells"][bench] = {"missing": "缺一侧的格（未测，不是 0）"}
                continue
            d, ci = panel.cell_diff(a, b, bench)
            s = sl[bench][0]
            near["cells"][bench] = {"delta": d, "ci": ci, "n": a["n_items"],
                                    "budget": s * (x - bpw_n)}
        rec["nearest"].append(near)
    if br is not None:
        (b_lo, m_lo), (b_hi, m_hi) = br
        ir = {"low": m_lo, "high": m_hi, "bpw_low": b_lo, "bpw_high": b_hi, "cells": {}}
        for bench in panel.BENCH:
            a, c_lo, c_hi = cells[tp].get(bench), cells[m_lo].get(bench), cells[m_hi].get(bench)
            if a is None or c_lo is None or c_hi is None:
                ir["cells"][bench] = {"missing": "缺一侧的格（未测，不是 0）"}
                continue
            n = a["n_items"]
            p_tp = a["score"]
            p_i = panel.interp(x, b_lo, b_hi, c_lo["score"], c_hi["score"])
            lo2 = min(panel.wilson(panel.k_of(c_lo, bench), c_lo["n_items"])[0],
                      panel.wilson(panel.k_of(c_hi, bench), c_hi["n_items"])[0])
            hi2 = max(panel.wilson(panel.k_of(c_lo, bench), c_lo["n_items"])[1],
                      panel.wilson(panel.k_of(c_hi, bench), c_hi["n_items"])[1])
            ci = None if bench in panel.NON_COUNT else panel.sumwidth_ci(
                panel.k_of(a, bench), n, lo2, hi2)
            rung_lo, rung_hi = c_lo["score"], c_hi["score"]
            side = ("高于两档" if p_tp > max(rung_lo, rung_hi) else
                    "低于两档" if p_tp < min(rung_lo, rung_hi) else "落在两档之间")
            ir["cells"][bench] = {"delta": p_tp - p_i, "ci": ci, "n": n,
                                  "p_interp": p_i, "p_tp": p_tp, "side": side,
                                  "bracket": [min(rung_lo, rung_hi), max(rung_lo, rung_hi)]}
        rec["interp"] = ir
    return rec


def resolved(ci):
    return ci is not None and ci[0] * ci[1] > 0


def report(cells, sl, bench_filter=None):
    steps = ladder_steps(cells)
    print("== 原生阶梯自己的每一步（插值的分母；本族阶梯不单调，这一步必须看）")
    for st in steps:
        line = [f"  {st['low']} {st['bpw_low']:.3f} → {st['high']} {st['bpw_high']:.3f} "
                f"Δbpw={st['dbpw']:+.3f}"]
        print(line[0])
        for bench in panel.BENCH:
            c = st["cells"].get(bench)
            if not c:
                print(f"      {panel.SHORT[bench]:<7} 缺")
                continue
            ci = c["ci"]
            txt = "无区间（概率质量列）" if ci is None else f"[{ci[0]:+.4f},{ci[1]:+.4f}]"
            flag = "" if ci is None else (" 区间不含0" if resolved(ci) else " 跨0")
            print(f"      {panel.SHORT[bench]:<7} Δ={c['delta']:+.4f} {txt} n={c['n_low']}"
                  f" 段斜率={c['slope']:+.4f}/比特{flag}")

    print("\n== 位宽尺子（同族内每 +1 比特/权重的分数变化，`a03::pairs.slopes`）")
    for bench in panel.BENCH:
        s, se, n = sl[bench]
        print(f"  {panel.SHORT[bench]:<7} {s:+.4f} ± {1.96 * se:.4f}  (n={n} 格)")

    print("\n== 分辨率：这一族上多小的差才可能读出来（无匹配对时的门槛）")
    seg = steps[0]["dbpw"]
    print(f"  ① 原生段宽：2.878→3.850 这一步本身就值 {seg:.3f} 比特/权重，乘尺子就是「同一段阶梯内的分数幅度」")
    print(f"  {'列':<7} {'段宽×尺子':>10} {'二项半宽(n=164)':>14} {'(n=378)':>9} {'(n=912)':>9} {'(n=100)':>9}")
    for bench in panel.BENCH:
        s = sl[bench][0]
        def half(n):
            k = round(0.5 * n)
            lo, hi = panel.wilson(k, n)
            return (hi - lo) / 2
        print(f"  {panel.SHORT[bench]:<7} {seg * s:>10.3f} {half(164):>14.3f} {half(378):>9.3f}"
              f" {half(912):>9.3f} {half(100):>9.3f}")
    print("  （二项半宽在 p=0.5 处取最大；实际格按自己的 p 与 n 算。TruthfulQA 不套二项区间。）")

    print("\n== 第三方方案自己的阶梯（同上传者、同一套分配策略，只变比特预算）")
    tps = sorted(panel.THIRD_PARTY, key=lambda m: panel.BPW[m])
    for lo, hi in zip(tps, tps[1:]):
        b_lo, b_hi = panel.BPW[lo], panel.BPW[hi]
        print(f"  {lo} {b_lo:.3f} → {hi} {b_hi:.3f}  Δbpw={b_hi - b_lo:+.3f}")
        for bench in panel.BENCH:
            c_lo, c_hi = cells[lo].get(bench), cells[hi].get(bench)
            if c_lo is None or c_hi is None:
                print(f"      {panel.SHORT[bench]:<7} 缺一侧的格（未测，不是 0）")
                continue
            d, ci = panel.cell_diff(c_hi, c_lo, bench)
            txt = "无区间（概率质量列）" if ci is None else f"[{ci[0]:+.4f},{ci[1]:+.4f}]"
            flag = "不可分辨" if ci is None or not resolved(ci) else "该列分得开"
            budget = sl[bench][0] * (b_hi - b_lo)
            print(f"      {panel.SHORT[bench]:<7} Δ={d:+.4f} {txt} n={c_hi['n_items']}"
                  f"  比特预算={budget:+.4f}  {flag}")

    out = {}
    for tp in panel.THIRD_PARTY:
        x = panel.BPW[tp]
        rec = position_of(tp, cells, sl)
        out[tp] = rec
        print(f"\n== 第三方档 {tp}\n   有效位宽 {x:.3f} 比特/权重")
        for near in rec["nearest"]:
            print(f"   最近原生档 {near['file']} {near['bpw']:.3f}（Δbpw={near['dbpw']:+.3f}）")
            for bench in panel.BENCH:
                if bench_filter and bench != bench_filter:
                    continue
                c = near["cells"][bench]
                if "missing" in c:
                    print(f"      {panel.SHORT[bench]:<7} {c['missing']}")
                    continue
                ci = c["ci"]
                txt = "无区间（概率质量列）" if ci is None else f"[{ci[0]:+.4f},{ci[1]:+.4f}]"
                flag = "不可分辨" if ci is None or not resolved(ci) else "该列分得开"
                print(f"      {panel.SHORT[bench]:<7} Δ={c['delta']:+.4f} {txt} n={c['n']}"
                      f"  比特预算={c['budget']:+.4f}  {flag}")
        ir = rec["interp"]
        if ir is None:
            print("   插值档：该档位宽落在原生阶梯之外，不外推（未测）")
            continue
        print(f"   插值档：{ir['bpw_low']:.3f}/{ir['bpw_high']:.3f} 之间插到 {x:.3f}"
              f"（{ir['low']} / {ir['high']}）")
        for bench in panel.BENCH:
            if bench_filter and bench != bench_filter:
                continue
            c = ir["cells"][bench]
            if "missing" in c:
                print(f"      {panel.SHORT[bench]:<7} {c['missing']}")
                continue
            ci_txt = ("无区间（概率质量列）" if c["ci"] is None
                      else f"[{c['ci'][0]:+.4f},{c['ci'][1]:+.4f}](保守合成)")
            flag = "不可分辨" if not resolved(c["ci"]) else "该列分得开"
            print(f"      {panel.SHORT[bench]:<7} Δ={c['delta']:+.4f} {ci_txt} n={c['n']}"
                  f"  插值={c['p_interp']:.4f} 实测={c['p_tp']:.4f}  {c['side']}  {flag}")
    multiplicity(out, cells)
    return out


def multiplicity(out, cells):
    """多重比较的分母与 p 值。

    分母不是「格数」：对每个 (tier, 列)，`nearest` 与 `interp` 共用**同一次第三方 run**
    （`d_near = p_tp − p_nat`、`d_interp = p_tp − (w·p₂ + (1−w)·p₃)` 里的 `p_tp` 是同一个数），
    所以独立比较的上界是 `tiers × 列 = 2 × 9 = 18`，不是 36；再按采集单位压一层
    （HE/HE⁺ 与 MBPP/MBPP⁺ 各来自同一次 evalplus run，9 列只对应 7 次 run）就是 14。
    期望计数把这些差异抹平，所以这里直接报 p 值。
    """
    tiers = len(panel.THIRD_PARTY)
    n_col = tiers * len(panel.BENCH)
    n_run = tiers * len({b.split("-")[0] for b in panel.BENCH})
    print("\n== 多重比较：独立比较的上界与 p 值")
    print(f"  独立比较上界 = tiers × 列 = {tiers} × {len(panel.BENCH)} = {n_col}"
          f"（同一 tier 的 nearest 与 interp 共用同一次第三方 run）")
    print(f"  按采集单位 = {n_run}（HE/HE⁺ 与 MBPP/MBPP⁺ 各来自同一次 evalplus run）")
    print(f"  Bonferroni 门槛：0.05/{n_col} = {0.05 / n_col:.4f}；0.05/{n_run} = {0.05 / n_run:.4f}")
    found = []
    for tp, rec in out.items():
        near = rec["nearest"][0]
        for bench in panel.BENCH:
            c = near["cells"].get(bench, {})
            if c.get("ci") and resolved(c["ci"]):
                pp = panel.cell_p(cells[tp][bench], cells[near["file"]][bench], bench)
                found.append((tp, "nearest", near["file"], bench, c["delta"], c["ci"], pp))
        for bench in panel.BENCH:
            c = rec["interp"]["cells"].get(bench, {}) if rec["interp"] else {}
            if c.get("ci") and resolved(c["ci"]):
                found.append((tp, "interp", None, bench, c["delta"], c["ci"], None))
    print(f"  区间不含 0 的格：{len(found)} 个")
    for tp, mode, other, bench, d, ci, pp in found:
        if pp is None:
            print(f"    {panel.TIER.get(tp, tp)} / {mode} / {panel.SHORT[bench]} Δ={d:+.4f}"
                  "  —— 插值档不是比例，没有 p 值，按保守合成区间判")
            continue
        pz, pf = pp
        print(f"    {panel.TIER.get(tp, tp)} / {mode} / {panel.SHORT[bench]} Δ={d:+.4f}"
              f"  p(pooled z)={pz:.4f}  p(Fisher)={pf:.4f}"
              f"  Bonferroni {n_col} 过不了: {pf > 0.05 / n_col}"
              f"  ；未校正 0.05 也只有 z 侧过: {(pz < 0.05) and (pf >= 0.05)}")


def main(argv=()):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bench", default=None, help="只打印某一列")
    ap.add_argument("--json", action="store_true", help="打印机器可读记录")
    a = ap.parse_args(list(argv) or None)
    if a.bench and a.bench not in panel.BENCH:
        sys.exit(f"未知基准 {a.bench}；可选：{panel.BENCH}")
    cells, dups = panel.cells()
    sl = slopes()
    if dups:
        print(f"同格多行（取 n_items 最大者）：{len(dups)} 处")
        for d in dups:
            print("   ", d)
        print()
    rec = report(cells, sl, a.bench)
    if a.json:
        print(json.dumps(rec, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
