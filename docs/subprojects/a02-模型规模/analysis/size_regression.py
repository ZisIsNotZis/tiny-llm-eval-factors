#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP3（plan5）：`score = f(总参, 激活参)` 这组双变量回归在本库的模型集里是否可识别。

判据先写死，再跑数（避免事后挑解释）：

  * 共线性：两个回归量的 log 相关 |r| > 0.95，或 VIF > 10，或中心化设计矩阵的条件数
    > 30，即判「不可识别」；
  * 结构：稠密模型的激活参等于总参（对角线上的一条线），它们不提供任何区分两个变量的
    信息。可识别性只来自 MoE 点。所以脚本数出「同总参不同激活」与「同激活不同总参」的
    点对数；两类都缺 ⇒ 不可识别；
  * 稳定性：把（a）全部点、（b）去掉稠密点、（c）去掉 MoE 点 三种拟合的系数符号列出来。
    若「总参」系数在三种子集里翻号，则这个系数不是被数据定住的，判「不可识别」。

X 用**实测参数量**（`size_provenance.py` 从 GGUF 张量求和得到），不用库里的
`__size`/`__activation_size`：前者是文件名标签，`moe-active-params-measured` 已证它与实测
值差到 69%。Y 用报告 §2 那一列（`_bench='humaneval'` + `evalplus-0.3.1-openai-chat-greedy-base`，
164 题），每个模型文件一行，权重用二项方差。

    python3 "docs/subprojects/a02-模型规模/analysis/size_regression.py"
    python3 "docs/subprojects/a02-模型规模/analysis/size_regression.py" --check
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
OUT = HERE / "size_regression.json"

sys.path.insert(0, str(REPO / ".wrapup"))
from mktables import lineage_and_size  # noqa: E402

BENCH, PROTOCOL = "humaneval", "evalplus-0.3.1-openai-chat-greedy-base"
VIF_MAX, R_MAX, COND_MAX = 10.0, 0.95, 30.0


def load_points():
    prov = json.loads(PROV.read_text(encoding="utf-8"))
    meta, seen = {}, set()
    for r in prov["rows"]:
        key = (r["model"],)
        g = r["gguf"]
        if not g or r["truth_params"] is None:
            continue
        if r["model"] in seen:
            continue
        seen.add(r["model"])
        family, label = lineage_and_size(r["model"])
        meta[r["model"]] = {
            "model": r["model"], "family": family, "label": label,
            "size": g["n_params"] / 1e9, "active": g["active_params"] / 1e9,
            "is_moe": bool(g["expert_count"] > 0),
            "experts": f"{g['expert_used']}/{g['expert_count']}" if g["expert_count"] else "",
        }
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cells = defaultdict(list)
    for r in con.execute(
            """select model, _score, n_items from experiments
                where _bench=? and protocol=? and _score is not null
                  and n_items is not null""", (BENCH, PROTOCOL)):
        cells[r["model"]].append((r["_score"], r["n_items"]))
    pts = []
    for m, cs in cells.items():
        if m not in meta:
            continue
        p = sum(s for s, _ in cs) / len(cs)
        n = min(n for _, n in cs)
        pts.append({**meta[m], "score": p, "n": n})
    pts.sort(key=lambda d: d["size"])
    return pts


def ols_wls(y, X, w):
    """加权最小二乘（w = 1/var），返回系数、SE、adjR²。"""
    n, k = len(y), len(X[0])
    sw = [math.sqrt(x) for x in w]
    A = [[x * s for x in row] for row, s in zip(X, sw)]
    b = [yy * s for yy, s in zip(y, sw)]
    # 正规方程（3 列以内，手解足够）
    AtA = [[sum(A[i][r] * A[i][c] for i in range(n)) for c in range(k)] for r in range(k)]
    Atb = [sum(A[i][r] * b[i] for i in range(n)) for r in range(k)]
    inv = invert(AtA)
    beta = [sum(inv[r][c] * Atb[c] for c in range(k)) for r in range(k)]
    resid = [b[i] - sum(A[i][c] * beta[c] for c in range(k)) for i in range(n)]
    rss = sum(r * r for r in resid)
    dof = n - k
    sigma2 = rss / dof if dof > 0 else float("nan")
    cov = [[sigma2 * inv[r][c] for c in range(k)] for r in range(k)]
    se = [math.sqrt(max(cov[i][i], 0.0)) for i in range(k)]
    ybar = sum(b) / n
    tss = sum((yy - ybar) ** 2 for yy in b)
    r2 = 1 - rss / tss if tss else float("nan")
    adj = 1 - (1 - r2) * (n - 1) / dof if dof > 0 else float("nan")
    return {"beta": beta, "se": se, "r2": r2, "adj_r2": adj, "n": n, "k": k, "rss": rss}


def invert(M):
    k = len(M)
    A = [row[:] + [1.0 if i == j else 0.0 for j in range(k)] for i, row in enumerate(M)]
    for col in range(k):
        piv = max(range(col, k), key=lambda r: abs(A[r][col]))
        if abs(A[piv][col]) < 1e-15:
            raise ValueError("singular design matrix")
        A[col], A[piv] = A[piv], A[col]
        d = A[col][col]
        A[col] = [x / d for x in A[col]]
        for r in range(k):
            if r != col and A[r][col]:
                f = A[r][col]
                A[r] = [x - f * y for x, y in zip(A[r], A[col])]
    return [row[k:] for row in A]


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return float("nan")
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def condition_number(rows):
    """中心化 + 标准化后的设计矩阵条件数（用 2 列的 Gram 矩阵特征值比）。"""
    k = len(rows[0])
    means = [sum(r[c] for r in rows) / len(rows) for c in range(k)]
    sd = []
    for c in range(k):
        s = math.sqrt(sum((r[c] - means[c]) ** 2 for r in rows) / len(rows))
        sd.append(s if s > 0 else 1.0)
    Z = [[(r[c] - means[c]) / sd[c] for c in range(k)] for r in rows]
    G = [[sum(Z[i][r] * Z[i][c] for i in range(len(Z))) / len(Z) for c in range(k)] for r in range(k)]
    # 2x2 的解析特征值
    tr, det = G[0][0] + G[1][1], G[0][0] * G[1][1] - G[0][1] * G[1][0]
    disc = max(tr * tr / 4 - det, 0.0)
    l1, l2 = tr / 2 + math.sqrt(disc), tr / 2 - math.sqrt(disc)
    return math.sqrt(l1 / l2) if l2 > 1e-12 else float("inf")


def structural_pairs(pts, tol_total=0.05, tol_active=0.05):
    """同总参不同激活 / 同激活不同总参 的点对数（对数刻度上 5% 视为同）。"""
    same_total, same_active, offdiag = 0, 0, 0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dt = abs(math.log(pts[i]["size"]) - math.log(pts[j]["size"]))
            da = abs(math.log(pts[i]["active"]) - math.log(pts[j]["active"]))
            if dt <= tol_total and da > tol_active:
                same_total += 1
            if da <= tol_active and dt > tol_total:
                same_active += 1
            if dt > tol_total and da > tol_active:
                offdiag += 1
    return {"same_total_diff_active": same_total,
            "same_active_diff_total": same_active,
            "both_differ": offdiag}


def fit_set(pts, feats, name):
    X, y, w = [], [], []
    for p in pts:
        X.append([1.0] + [f(p) for f in feats])
        y.append(p["score"])
        var = max(p["score"] * (1 - p["score"]) / p["n"], 1e-6)
        w.append(1.0 / var)
    try:
        m = ols_wls(y, X, w)
    except ValueError as exc:
        # 秩亏就是结论本身：稠密点上 log(激活) 与 log(总参) 是同一列。
        return {"name": name, "singular": True, "reason": str(exc), "n": len(y)}
    m["name"] = name
    m["features"] = ["const"] + [f.__name__ for f in feats]
    return m


def ln_size(p):
    return math.log(p["size"])


def ln_active(p):
    return math.log(p["active"])


def is_moe(p):
    return 1.0 if p["is_moe"] else 0.0


def ln_experts(p):
    return math.log(1 + (int(p["experts"].split("/")[1]) if p["experts"] else 0))


def main(argv):
    pts = load_points()
    dense = [p for p in pts if not p["is_moe"]]
    moe = [p for p in pts if p["is_moe"]]
    log_s = [ln_size(p) for p in pts]
    log_a = [ln_active(p) for p in pts]
    r = pearson(log_s, log_a)
    vif = 1.0 / (1.0 - r * r) if abs(r) < 1 else float("inf")
    cond = condition_number([[ln_size(p), ln_active(p)] for p in pts])
    pairs = structural_pairs(pts)
    # 子集内的共线性：稠密点上是 1.0（激活≡总参），MoE 点上是 reviewer 要求补的那一格。
    r_dense = pearson([ln_size(p) for p in dense], [ln_active(p) for p in dense]) if len(dense) > 2 else float("nan")
    r_moe = pearson([ln_size(p) for p in moe], [ln_active(p) for p in moe]) if len(moe) > 2 else float("nan")
    vif_moe = 1.0 / (1.0 - r_moe ** 2) if abs(r_moe) < 1 else float("inf")

    fits = [
        fit_set(pts, [ln_size], "total_only"),
        fit_set(pts, [ln_active], "active_only"),
        fit_set(pts, [ln_size, ln_active], "total+active"),
        # 加上「是否 MoE」这个指示变量后两个系数会翻号：这就是两团点云的假象，也是
        # reviewer 复核时用的同一个检验。
        fit_set(pts, [ln_size, ln_active, is_moe], "total+active+moe_dummy"),
    ]
    # 稳定性：三种点集上的系数
    stab = {
        "all": fit_set(pts, [ln_size, ln_active], "total+active@all"),
        "drop_dense": fit_set(moe, [ln_size, ln_active], "total+active@moe_only") if len(moe) > 2 else None,
        "drop_moe": fit_set(dense, [ln_size, ln_active], "total+active@dense_only") if len(dense) > 2 else None,
    }


    # 留一族：每一族单独去掉后重拟，看两个系数是不是被一族定住的
    fams = sorted({p["family"] for p in pts})
    loo = {}
    for fam in fams:
        sub = [p for p in pts if p["family"] != fam]
        if len(sub) < 8:
            continue
        try:
            m = fit_set(sub, [ln_size, ln_active], f"total+active@drop-{fam}")
        except ValueError:
            continue
        if not m.get("singular"):
            loo[fam] = {"n": m["n"], "total": round(m["beta"][1], 4), "active": round(m["beta"][2], 4),
                        "total_se": round(m["se"][1], 4), "active_se": round(m["se"][2], 4)}
    base_total, base_active = stab["all"]["beta"][1], stab["all"]["beta"][2]
    swings = []
    for fam, v in loo.items():
        if (v["total"] > 0) != (base_total > 0):
            swings.append(f"去掉 {fam} 后总参系数翻号（{v['total']:+.3f}）")
        if (v["active"] > 0) != (base_active > 0):
            swings.append(f"去掉 {fam} 后激活系数翻号（{v['active']:+.3f}）")
        if abs(v["active"] - base_active) > abs(base_active):
            swings.append(f"去掉 {fam} 后激活系数变化超过自身量级（{base_active:+.3f}→{v['active']:+.3f}）")

    # 判定
    reasons = []
    if abs(r) > R_MAX:
        reasons.append(f"|r(log total, log active)| = {abs(r):.3f} > {R_MAX}")
    if vif > VIF_MAX:
        reasons.append(f"VIF = {vif:.1f} > {VIF_MAX}")
    if cond > COND_MAX:
        reasons.append(f"中心化条件数 = {cond:.1f} > {COND_MAX}")
    if pairs["same_active_diff_total"] < 3:
        reasons.append(f"同激活不同总参的点对只有 {pairs['same_active_diff_total']} 对")
    if pairs["same_total_diff_active"] < 1:
        reasons.append("没有一对『同总参不同激活』的受控点")
    if abs(r_moe) > R_MAX:
        reasons.append(f"MoE 子集内 |r(log总参, log激活)| = {abs(r_moe):.3f}，VIF = {vif_moe:.1f} > {VIF_MAX}"
                       "（两个变量在 MoE 内部也锁在一起）")
    signs = {}
    for k, m in stab.items():
        if m and not m.get("singular"):
            signs[k] = [round(b, 4) for b in m["beta"]]
    if stab.get("drop_moe") and stab["drop_moe"].get("singular"):
        reasons.append("去掉 MoE 点后设计矩阵秩亏（稠密点上 激活≡总参），两个变量无法分开")
    tot_betas = [v[1] for v in signs.values() if len(v) > 1]
    reasons.extend(swings)
    if tot_betas and (max(tot_betas) > 0 > min(tot_betas)):
        reasons.append(f"总参系数在子集间翻号：{ {k: v[1] for k, v in signs.items()} }")
    identified = not reasons

    out = {
        "bench": BENCH, "protocol": PROTOCOL,
        "n_points": len(pts), "n_dense": len(dense), "n_moe": len(moe),
        "points": pts,
        "log_corr": r, "vif": vif, "cond": cond, "pairs": pairs,
        "log_corr_dense": r_dense, "log_corr_moe": r_moe, "vif_moe": vif_moe,
        "fits": fits, "stability": signs, "leave_one_family_out": loo,
        "identified": identified, "blocking_reasons": reasons,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"points: {len(pts)}  (dense {len(dense)}, MoE {len(moe)})   "
          f"bench={BENCH}/{PROTOCOL} n=164")
    print(f"log(total) vs log(active): r = {r:.3f}   VIF = {vif:.2f}   cond = {cond:.2f}")
    print(f"  dense-only r = {r_dense:.4f}（激活≡总参，秩亏）   MoE-only r = {r_moe:.3f}  "
          f"VIF_moe = {vif_moe:.1f}")
    print(f"pairs: {pairs}")
    print("\nfits (WLS, weights = 1/binomial var):")
    for m in fits:
        print(f"  {m['name']:14s} adjR²={m['adj_r2']:.3f}  " +
              "  ".join(f"{nm}={b: .4f}±{se:.4f}" for nm, b, se in zip(m["features"], m["beta"], m["se"])))
    print("\nstability of total+active across subsets (beta):")
    for k, v in signs.items():
        print(f"  {k:12s} {v}")
    if len(moe) > 2:
        rm = stab["drop_dense"]
        print(f"\nMoE-only fit: total={rm['beta'][1]: .4f}±{rm['se'][1]:.4f}  "
              f"active={rm['beta'][2]: .4f}±{rm['se'][2]:.4f}  adjR²={rm['adj_r2']:.3f} n={rm['n']}")
    if stab.get("drop_moe") and stab["drop_moe"].get("singular"):
        print("\ndense-only fit: SINGULAR — 稠密点上 log(激活) 与 log(总参) 是同一列")
    print("\nleave-one-family-out (total+active):")
    for fam, v in loo.items():
        print(f"  drop {fam[:30]:32s} n={v['n']:3d} total={v['total']:+.4f}±{v['total_se']:.4f}"
              f"  active={v['active']:+.4f}±{v['active_se']:.4f}")
    if swings:
        print("  swings:")
        for x in swings:
            print(f"    {x}")
    print(f"\nidentified: {identified}")
    for x in reasons:
        print(f"  blocking: {x}")
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

        want(len(pts) == len(dense) + len(moe), "点数 = 稠密点 + MoE 点")
        want(len(dense) > 0 and len(moe) > 0, f"稠密点与 MoE 点都非空（{len(dense)} / {len(moe)}）")
        want(abs(pearson([ln_size(p) for p in dense], [ln_active(p) for p in dense])) > 0.999
             if len(dense) > 2 else True,
             "稠密点的 log 总参与 log 激活完全共线（激活=总参）")
        want(pairs == structural_pairs(pts), "结构计数可由原始点重算（关系式，不是快照）")

        # 判定与理由必须一致
        want(out["identified"] == (not reasons), "identified 与 blocking_reasons 一致")
        want(out["identified"] is False, "plan5 的判定是「不可识别」")
        want(out["vif_moe"] > VIF_MAX, f"MoE 子集内 VIF > {VIF_MAX}（实际 {out['vif_moe']:.1f}）")
        want(abs(out["log_corr_dense"] - 1.0) < 1e-9, "稠密子集内 log 总参与 log 激活的 r = 1")
        want(any("秩亏" in x for x in reasons), "不可识别的理由里含「稠密点秩亏」")
        # 陷阱：合并拟合的两个系数都显著为正，只看这个会得出「两个变量都有效」的错误结论。
        both = [m for m in fits if m["name"] == "total+active"][0]
        want(both["beta"][1] > 2 * both["se"][1] and both["beta"][2] > 2 * both["se"][2],
             "合并拟合的两个系数都显著为正（这正是陷阱）")
        dummy = [m for m in fits if m["name"] == "total+active+moe_dummy"][0]
        want(dummy["beta"][2] < 0 < both["beta"][2],
             f"加 MoE 指示变量后激活系数翻号（{both['beta'][2]:+.4f} → {dummy['beta'][2]:+.4f}）")
        rm = stab.get("drop_dense")
        want(rm and abs(rm["beta"][1]) < 2 * rm["se"][1],
             "只看 MoE 点时总参系数与 0 不可分（MoE 内部也无法分离两个变量）")
        print(f"  {ok} expected true, {fail} false")
        return 0 if fail == 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
