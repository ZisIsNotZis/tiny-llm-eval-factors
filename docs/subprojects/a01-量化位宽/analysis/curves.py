#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a01 量化位宽：有效位宽 → 基准分数 的曲线、配对差与拐点。

只读 `experiments.sqlite`，不改库、不改报告。所有输出都能被一条命令重跑。

口径（`docs/subprojects/a01-量化位宽/AGENTS.md`）：
  * X = 有效位宽 = 8 × 文件字节数 ÷ 参数量，取自 `.wrapup/bpw_map.json`（gguf 元数据算出的精确参数量）。
  * 一格 = (模型文件, 基准) 在**该基准的规范协议**下的一行；同一 (模型, 基准, 协议) 有多行时取
    `n_items` 最大的那行，并在 `warn` 里报出来——静默取一行会让两条不同面板看起来像一个测量。
  * 区间 = 逐题二项区间（Clopper–Pearson）；配对差的区间 = Newcombe 混合得分区间（method 10）。

拐点定义（写死，避免事后挑定义）：把家族内按位宽排好的点算成段斜率
`s_i = (p_{i+1} - p_i) / (bpw_{i+1} - bpw_i)`，取 `s_max`；**拐点 = 第一个位宽点，使从它起的
所有段斜率都低于 `0.5 × s_max`**（即曲线从此走平并不再抬升）。取「此后全部低于」而不是「第一个低于」，
是为了不让单次下凹（例如 Qwen3.5-2B 在 3.96→4.11 的下掉）被当成拐点。
区间用参数自举：每个点按 `Binomial(n_i, p_i)` 重抽、重算拐点，取 2.5/97.5 分位。
点少于 4 个、或 `s_max <= 0`（全程不升）、或不存在满足条件的点（观测范围内从未走平）时不估拐点，打印原因。
**分辨率就是阶梯的位宽间距**（拐点只能落在实测点上），所以区间常常只有一两档宽，这是数据的性质，不是算法的问题。

用法：
    python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --panel qwen3.5-2b
    python3 ".../curves.py" --pair qwen3.5-2b/IQ3_XXS/Q2_K_XL
    python3 ".../curves.py" --adjacent
    python3 ".../curves.py" --all          # 每家族点数、位宽范围、逐基准拐点或不可估
    python3 ".../curves.py" --panel qwen3.5-2b --bench mmlu --json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from pathlib import Path

import numpy as np
from scipy.stats import beta

HERE = Path(__file__).resolve()
REPO = HERE
for _ in range(6):                       # docs/subprojects/<id>/analysis/curves.py → 仓库根
    REPO = REPO.parent
    if (REPO / "experiments.sqlite").is_file():
        break
else:
    sys.exit("找不到仓库根（experiments.sqlite）")

DB = REPO / "experiments.sqlite"
BPW_MAP = json.loads((REPO / ".wrapup" / "bpw_map.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(REPO / ".wrapup"))

BENCH = {                                # 与 make_report.py::BENCH 同一份规范协议
    "humaneval-plus": "evalplus-0.3.1-openai-chat-greedy-plus",
    "mbpp-plus": "evalplus-0.3.1-openai-chat-greedy-plus",
    "mmlu": "lmeval-0.4.13-gguf-shim-reasoning-off",
    "arc_challenge": "lmeval-0.4.13-gguf-shim-reasoning-off",
    "truthfulqa_mc2": "lmeval-0.4.13-gguf-shim-reasoning-off",
    "gsm8k": "lmeval-0.4.13-chat-reasoning-off",
    "ifeval": "lmeval-0.4.13-chat-reasoning-off",
}
BENCH_ORDER = list(BENCH)
# truthfulqa_mc2 的 `acc` 不是命中率，而是归一化后的真答案概率质量均值（`i01::res26`），
# 所以它不是伯努利计数：这一列分数照报，但逐题二项区间与两比例差在这里不适用。
NON_COUNT = {"truthfulqa_mc2"}
SHORT = {"humaneval-plus": "HE+", "mbpp-plus": "MBPP+", "mmlu": "MMLU",
         "arc_challenge": "ARC-c", "truthfulqa_mc2": "TQA", "gsm8k": "GSM8K", "ifeval": "IFEval"}


def con():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def bpw_of(model):
    base = model if model.endswith(".gguf") else model + ".gguf"
    return BPW_MAP.get(base)


def family_of(model):
    import mktables
    return mktables.family_of(model)


def scheme_class(model):
    """供应商方案大类（UD 动态 / 原生 K / QAT），直接复用 mktables 那一份定义。"""
    import mktables
    return mktables.scheme_class(model)


def series_key(model):
    return (family_of(model), scheme_class(model))


def quant_of(model):
    import mktables
    base = model if model.endswith(".gguf") else model + ".gguf"
    stem, quant = mktables.split_quant(base)
    return quant or "—"


def cp_interval(k, n, alpha=0.05):
    """逐题二项区间（Clopper–Pearson）。"""
    if n <= 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


def wilson(k, n, z=1.959963984540054):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def newcombe_diff(k1, n1, k2, n2):
    """两比例差的 95% 区间（Newcombe method 10）。"""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    a = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    b = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (a, b)


def rows_for(cc, model, bench):
    proto = BENCH[bench]
    rs = cc.execute(
        "SELECT _score, n_items, run_tag, ctx_size, parallel_slots, temp, reasoning, protocol FROM experiments"
        " WHERE model=? AND _bench=? AND protocol=? AND _score IS NOT NULL", (model, bench, proto)).fetchall()
    if not rs:
        return None, []
    rs.sort(key=lambda r: (-(r[1] or 0), r[2] or ""))
    best = rs[0]
    return {"score": best[0], "n_items": best[1], "run_tag": best[2],
            "ctx_size": best[3], "parallel_slots": best[4], "temp": best[5],
            "reasoning": best[6], "protocol": best[7]}, rs[1:]


def panel(cc, needle, bench_filter=None):
    """一个家族（或一个模型文件）的全部位宽点。"""
    models = sorted({r[0] for r in cc.execute(
        "SELECT DISTINCT model FROM experiments WHERE model LIKE ?", (f"%{needle}%",))})
    fams = {}
    warns = []
    for m in models:
        b = bpw_of(m)
        if b is None:
            warns.append(f"{m}: bpw_map 里没有这一项，跳过")
            continue
        fams.setdefault(series_key(m), []).append((b, m))
    out = {"needle": needle, "families": {}, "warn": warns}
    for fam, items in sorted(fams.items()):
        fam = fam[0] if fam[1] == "UD 动态" else f"{fam[0]} · {fam[1]}"
        pts = {}
        for b, m in sorted(items):
            cell = {"bpw": b, "model": m, "quant": quant_of(m), "scores": {}}
            for bench in BENCH_ORDER:
                if bench_filter and bench != bench_filter:
                    continue
                r, dup = rows_for(cc, m, bench)
                if r is None:
                    continue
                if bench in NON_COUNT:
                    lo = hi = float("nan")
                else:
                    lo, hi = cp_interval(round(r["score"] * r["n_items"]), r["n_items"]) \
                        if r["n_items"] else (float("nan"), float("nan"))
                cell["scores"][bench] = dict(r, ci=[lo, hi])
                if dup:
                    warns.append(f"{m} / {bench}: {1 + len(dup)} 行，取 n_items 最大者 "
                                 f"({r['run_tag']}, n={r['n_items']})，其余 "
                                 f"{[(d[2], d[1]) for d in dup]}")
            if cell["scores"]:
                pts[m] = cell
        if pts:
            out["families"][fam] = [pts[m] for _, m in sorted((v["bpw"], m) for m, v in pts.items())]
    return out


def knee(points, rng, reps=2000):
    """拐点 = 此后所有段斜率都低于峰值一半的那个位宽点。返回 (点估计, (lo, hi) 或原因字符串)。"""
    xs = np.array([p[0] for p in points], float)
    ks = np.array([p[1] for p in points], float)
    ns = np.array([p[2] for p in points], float)
    if len(xs) < 4:
        return None, f"只有 {len(xs)} 个位宽点（<4），不估拐点"

    def est(xs, ps):
        slopes = np.diff(ps) / np.diff(xs)
        smax = slopes.max()
        if smax <= 0:
            return None
        flat = slopes < 0.5 * smax
        for i in range(len(slopes)):        # 第一个「从它起全部走平」的段起点
            if flat[i:].all():
                return float(xs[i])
        return float("nan")

    ps = ks / ns
    point = est(xs, ps)
    if point is None:
        return None, "全程没有上升段（峰值段斜率 ≤ 0），不估拐点"
    if math.isnan(point):
        return None, "没有「从它起全部走平」的点（观测范围内从未走平），不估拐点"
    draws = rng.binomial(ns.astype(int), np.clip(ps, 0, 1), size=(reps, len(xs))) / ns
    boots = []
    for row in draws:
        v = est(xs, row)
        if v is not None and not math.isnan(v):
            boots.append(v)
    if len(boots) < reps * 0.5:
        return point, f"自举有效样本 {len(boots)}/{reps} 太少，区间不可信"
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, (float(lo), float(hi))


def fmt(x, w=7, p=4):
    return f"{x:{w}.{p}f}" if isinstance(x, float) and not math.isnan(x) else f"{'—':>{w}}"


def show_panel(res, bench_filter=None, as_json=False):
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=1, default=float))
        return
    benches = [bench_filter] if bench_filter else BENCH_ORDER
    for fam, pts in res["families"].items():
        print(f"\n== {fam}  ({len(pts)} 个位宽点)")
        print(f"{'量化':<14}{'位宽':>7}  " + " ".join(f"{SHORT[b]:>13}" for b in benches))
        for p in pts:
            cells = []
            for b in benches:
                s = p["scores"].get(b)
                if not s:
                    cells.append(f"{'—':>13}")
                    continue
                half = (s["ci"][1] - s["ci"][0]) / 2
                cells.append(f"{s['score']:6.4f}±{half:5.3f}" if not math.isnan(half)
                             else f"{s['score']:6.4f}±{'n/a':>5}")
            print(f"{p['quant']:<14}{p['bpw']:7.3f}  " + " ".join(f"{c:>13}" for c in cells))
        rng = np.random.default_rng(20261020)
        for b in benches:
            ser = [(p["bpw"], round(p["scores"][b]["score"] * p["scores"][b]["n_items"]),
                    p["scores"][b]["n_items"]) for p in pts if b in p["scores"]]
            if len(ser) < 2:
                continue
            if b in NON_COUNT:
                print(f"  拐点 {SHORT[b]:>7}: 不可估 — 该列 acc 是概率质量均值，不是逐题计数（i01::res26）")
                continue
            k, why = knee(ser, rng)
            if k is None:
                print(f"  拐点 {SHORT[b]:>7}: 不可估 — {why}")
            elif isinstance(why, str):
                print(f"  拐点 {SHORT[b]:>7}: {k:.3f} 比特/权重（{why}）")
            else:
                print(f"  拐点 {SHORT[b]:>7}: {k:.3f} 比特/权重  95% 区间 [{why[0]:.3f}, {why[1]:.3f}]")
    for w in res["warn"]:
        print(f"[warn] {w}", file=sys.stderr)


def show_pair(cc, needle, qa, qb, as_json=False):
    res = panel(cc, needle)
    target = None
    for fam, pts in res["families"].items():
        qs = [p["quant"] for p in pts]
        if any(qa.lower() in q.lower() for q in qs) and any(qb.lower() in q.lower() for q in qs):
            target = (fam, pts)
            break
    if target is None:
        sys.exit(f"家族里找不到量化 {qa} / {qb}：{ {f: [p['quant'] for p in v] for f, v in res['families'].items()} }")
    fam, pts = target
    A = next(p for p in pts if qa.lower() in p["quant"].lower())
    B = next(p for p in pts if qb.lower() in p["quant"].lower())
    out = {"family": fam, "A": {"quant": A["quant"], "bpw": A["bpw"]},
           "B": {"quant": B["quant"], "bpw": B["bpw"]}, "benches": {}}
    print(f"{fam}: A = {A['quant']} ({A['bpw']:.3f} 比特/权重)  B = {B['quant']} ({B['bpw']:.3f})  Δbpw = {A['bpw']-B['bpw']:+.3f}")
    print(f"{'基准':<16}{'A 分数(n)':>16}{'B 分数(n)':>16}{'A−B':>8}{'A−B 95%':>20}{'题数差':>8}")
    for bench in BENCH_ORDER:
        sa, sb = A["scores"].get(bench), B["scores"].get(bench)
        if not sa and not sb:
            print(f"{SHORT[bench]:<16}{'未测':>16}{'未测':>16}  （两个文件都没测这一列）")
            continue
        if not sa or not sb:
            print(f"{SHORT[bench]:<16}{'未测':>16}{'未测':>16}  （只有一侧有值，不是比较）")
            continue
        if bench in NON_COUNT:
            va, vb = sa["score"], sb["score"]
            print(f"{SHORT[bench]:<16}{va:>16.4f}{vb:>16.4f}{va-vb:+8.4f}   {'不适用（非伯努利）':>18}{'':>8}")
            out["benches"][bench] = {"A": va, "B": vb, "diff": va - vb, "ci": None}
            continue
        ka, na = round(sa["score"] * sa["n_items"]), sa["n_items"]
        kb, nb = round(sb["score"] * sb["n_items"]), sb["n_items"]
        lo, hi = newcombe_diff(ka, na, kb, nb)
        rec = {"A": [ka, na], "B": [kb, nb], "diff": (ka / na) - (kb / nb), "ci": [lo, hi]}
        out["benches"][bench] = rec
        print(f"{SHORT[bench]:<16}{f'{ka}/{na} = {ka/na:.4f}':>16}{f'{kb}/{nb} = {kb/nb:.4f}':>16}"
              f"{rec['diff']:+8.4f}   [{lo:+.4f}, {hi:+.4f}]{ka-kb:>8}")
    print("（区间是两比例差的 Newcombe 95% 区间；跨 0 = 这一列分不开）")
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1, default=float))


def show_all(cc, min_points=2, as_json=False):
    """全部家族的位宽点数与拐点可估性（轴 AC 的第一条：每家族一条曲线 + 拐点或「不可估」）。"""
    models = sorted({r[0] for r in cc.execute("SELECT DISTINCT model FROM experiments")})
    fams = {}
    for m in models:
        b = bpw_of(m)
        if b is not None:
            fams.setdefault(series_key(m), set()).add(round(b, 3))
    rng = np.random.default_rng(20261020)
    out = {}
    print(f"{'家族':<26}{'点数':>5}{'位宽范围':>20}  拐点（按基准，估不出就写原因）")
    for key, bs in sorted(fams.items()):
        bs = sorted(bs)
        if len(bs) < min_points:
            continue
        fam = key[0] if key[1] == "UD 动态" else f"{key[0]} · {key[1]}"
        res = panel(cc, key[0])
        pts = res["families"].get(fam, [])
        knees = {}
        for bench in BENCH_ORDER:
            ser = [(p["bpw"], round(p["scores"][bench]["score"] * p["scores"][bench]["n_items"]),
                    p["scores"][bench]["n_items"]) for p in pts if bench in p["scores"]]
            if len(ser) < 2:
                continue
            if bench in NON_COUNT:
                knees[bench] = {"knee": None, "reason": "acc 是概率质量均值，不是逐题计数"}
                continue
            k, why = knee(ser, rng)
            if k is None:
                knees[bench] = {"knee": None, "reason": why}
            elif isinstance(why, str):
                knees[bench] = {"knee": k, "reason": why}
            else:
                knees[bench] = {"knee": k, "ci": [why[0], why[1]]}
        out[fam] = {"n_points": len(bs), "bpw": bs, "knees": knees}
        cells = []
        for b in BENCH_ORDER:
            if b not in knees:
                continue
            v = knees[b]
            cells.append(f"{SHORT[b]}={v['knee']:.2f}[{v['ci'][0]:.2f},{v['ci'][1]:.2f}]"
                         if v["knee"] is not None and "ci" in v else f"{SHORT[b]}=—")
        print(f"{fam:<26}{len(bs):>5}{f'{bs[0]:.2f}–{bs[-1]:.2f}':>20}  " + " ".join(cells))
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1, default=float))


def show_adjacent(cc, as_json=False):
    """每个家族每个基准：相邻位宽档之间的分数变化（res1 的重算）。"""
    models = sorted({r[0] for r in cc.execute("SELECT DISTINCT model FROM experiments")})
    fams = {}
    for m in models:
        b = bpw_of(m)
        if b is not None:
            fams.setdefault(series_key(m), []).append((b, m))
    stat = {b: {"pos": 0, "neg": 0, "zero": 0, "deltas": [], "per_bit": []} for b in BENCH_ORDER}
    detail = []
    for fam_key, items in sorted(fams.items()):
        fam = fam_key[0] if fam_key[1] == "UD 动态" else f"{fam_key[0]} · {fam_key[1]}"
        items.sort()
        for (b1, m1), (b2, m2) in zip(items, items[1:]):
            for bench in BENCH_ORDER:
                r1, _ = rows_for(cc, m1, bench)
                r2, _ = rows_for(cc, m2, bench)
                if not r1 or not r2:
                    continue
                d = r2["score"] - r1["score"]
                s = stat[bench]
                s["deltas"].append(d)
                if b2 > b1:
                    s["per_bit"].append(d / (b2 - b1))
                s["pos" if d > 0 else ("neg" if d < 0 else "zero")] += 1
                detail.append({"family": fam, "bench": bench,
                               "from": [m1, round(b1, 3), round(r1["score"], 4)],
                               "to": [m2, round(b2, 3), round(r2["score"], 4)], "delta": d})
    print(f"{'基准':<16}{'升':>4}{'降':>4}{'平':>4}{'中位 Δ':>10}{'中位 Δ/比特':>14}")
    for bench in BENCH_ORDER:
        s = stat[bench]
        d = np.array(s["deltas"])
        pb = np.array(s["per_bit"]) if s["per_bit"] else np.array([float("nan")])
        note = "  非伯努利，仅供参考" if bench in NON_COUNT else ""
        print(f"{SHORT[bench]:<16}{s['pos']:>4}{s['neg']:>4}{s['zero']:>4}"
              f"{np.median(d):>10.4f}{np.median(pb):>14.4f}{note}")
    if as_json:
        print(json.dumps({"stat": stat, "detail": detail}, ensure_ascii=False, indent=1, default=float))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel")
    ap.add_argument("--pair", help="<家族关键字>/<量化 A>/<量化 B>")
    ap.add_argument("--bench", choices=BENCH_ORDER)
    ap.add_argument("--adjacent", action="store_true")
    ap.add_argument("--all", action="store_true", help="全部家族的曲线点数与拐点可估性")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    cc = con()
    if a.all:
        show_all(cc, as_json=a.json)
    elif a.pair:
        needle, qa, qb = a.pair.split("/")
        show_pair(cc, needle, qa, qb, a.json)
    elif a.adjacent:
        show_adjacent(cc, a.json)
    elif a.panel:
        show_panel(panel(cc, a.panel, a.bench), a.bench, a.json)
    else:
        ap.error("需要 --panel / --pair / --adjacent / --all 之一")
    return 0


if __name__ == "__main__":
    sys.exit(main())
