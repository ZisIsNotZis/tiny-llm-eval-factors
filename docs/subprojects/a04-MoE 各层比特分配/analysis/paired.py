#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两臂的**配对**检验：逐题判定直接来自入库的 EvalPlus 逐题产物，不从分数反推。

    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/paired.py"
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/paired.py" --bench humaneval
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/paired.py" --selftest

为什么要有这一条：`alloc_pairs.py` 的区间是**非配对**的（它只知道两个比例），因为本层的
分数来自 `experiments.sqlite` 的聚合行。但两臂的逐题判定（`base_status` / `plus_status`）
在盘上存在，并且已作为 `_eval.json` 随仓库走——于是同一批题可以在**同一题上**比较，
用 McNemar 精确检验，power 远高于两比例区间。这是本层唯一允许的配对检验，别处仍用非配对口径。

判据：

  * plus 判分 = `base_status == "pass" and plus_status == "pass"`（EvalPlus 自己的 pass@1 定义）；
  * `b` = A 通过而 B 不通过的题数，`c` = 反之；双向精确检验 p 用二项分布（p=0.5）；
  * 差值 `d = (b - c) / n`；区间给两个：
    - **Wald 配对**：`d ± 1.96·sqrt((b + c - (b - c)²/n)) / n`
    - **条件精确**（Clopper–Pearson 于 `b/(b+c)`，再乘 `(b+c)/n`）：`c = 0` 时上端退化到 `d`，
      这是它的正常行为，不是 bug。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE
for _ in range(5):
    REPO = REPO.parent
    if (REPO / "experiments.sqlite").is_file():
        break
else:
    sys.exit("找不到仓库根（experiments.sqlite）")

EV = REPO / ".wrapup" / "mres"
ARMS = {
    "uni45": {"humaneval": EV / "a04-arm-uni45-humaneval-evalplus_eval.json",
              "mbpp": EV / "a04-arm-uni45-mbpp-evalplus_eval.json"},
    "exq4": {"humaneval": EV / "a04-arm-exq4-humaneval-evalplus_eval.json",
             "mbpp": EV / "a04-arm-exq4-mbpp-evalplus_eval.json"},
}
Z = 1.959963984540054


def load_pass(path, plus=True):
    """{task_id: bool}；只取该文件里第一个 solution 的判定（EvalPlus 单样本）。"""
    doc = json.loads(path.read_text(encoding="utf-8"))
    # 这个 build 的 eval_results.json 顶层是 {date, hash, eval}，逐题结果在 `eval` 下面；
    # 早期产物直接是 {task: [rows]}，两种都收。
    doc = doc.get("eval", doc) if isinstance(doc, dict) else doc
    out = {}
    for task, rows in doc.items():
        if not rows:
            continue
        r = rows[0]
        ok = r.get("base_status") == "pass"
        if plus:
            ok = ok and r.get("plus_status") == "pass"
        out[task] = ok
    return out


def binom_two_sided(k, n, p=0.5):
    """精确二项双向 p（两侧尾概率相加后截到 1）。"""
    if n == 0:
        return 1.0
    def pmf(i):
        return math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    lo = sum(pmf(i) for i in range(0, k + 1))
    hi = sum(pmf(i) for i in range(k, n + 1))
    return min(1.0, 2 * min(lo, hi))


def clopper_pearson(k, n, alpha=0.05):
    """二项比例的精确区间（用 Beta 分位数的等价级数，无 scipy 依赖）。"""
    if n == 0:
        return (0.0, 1.0)
    lo = 0.0 if k == 0 else _beta_ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else _beta_ppf(1 - alpha / 2, k + 1, n - k)
    return (lo, hi)


def _beta_ppf(q, a, b, iters=200):
    """Beta(a,b) 分位数的二分求解（只需 1e-9 精度，够写进一张表）。"""
    lo, hi = 0.0, 1.0
    for _ in range(iters):
        mid = (lo + hi) / 2
        if _betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _betainc(a, b, x):
    """正则化不完全 Beta（连分式，Numerical Recipes betacf）。"""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def _betacf(a, b, x, itmax=200, eps=3e-12):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < eps:
            break
    return h


def compare(a_name, b_name, bench, plus=True):
    pa = load_pass(ARMS[a_name][bench], plus)
    pb = load_pass(ARMS[b_name][bench], plus)
    tasks = sorted(set(pa) & set(pb))
    missing = sorted(set(pa) ^ set(pb))
    n = len(tasks)
    ka = sum(pa[t] for t in tasks)
    kb = sum(pb[t] for t in tasks)
    b = sum(1 for t in tasks if pa[t] and not pb[t])
    c = sum(1 for t in tasks if pb[t] and not pa[t])
    d = (ka - kb) / n if n else float("nan")
    disc = b + c
    var = (disc - (b - c) ** 2 / n) / (n * n) if n else float("nan")
    sd = math.sqrt(var) if var >= 0 else float("nan")
    wald = (d - Z * sd, d + Z * sd)
    if disc:
        lo, hi = clopper_pearson(b, disc)
        exact = ((2 * lo - 1) * disc / n, (2 * hi - 1) * disc / n)
    else:
        exact = (0.0, 0.0)
    return {"a": a_name, "b": b_name, "bench": bench, "plus": plus, "n": n,
            "tasks_unmatched": missing, "k_a": ka, "k_b": kb, "b_only_a": b, "c_only_b": c,
            "delta": d, "p_mcnemar_exact": binom_two_sided(b, disc),
            "ci_wald": wald, "ci_exact_conditional": exact}


def show(r):
    plus = "plus" if r["plus"] else "base"
    print("%s vs %s · %s (%s): n=%d  A=%d/%d=%.4f  B=%d/%d=%.4f"
          % (r["a"], r["b"], r["bench"], plus, r["n"], r["k_a"], r["n"], r["k_a"] / r["n"],
             r["k_b"], r["n"], r["k_b"] / r["n"]))
    print("    discordant  A只过 %d : B只过 %d   Δ=%+.4f"
          % (r["b_only_a"], r["c_only_b"], r["delta"]))
    print("    McNemar 精确 p = %.3g" % r["p_mcnemar_exact"])
    print("    Wald 配对 95%% CI = [%+.4f, %+.4f]" % r["ci_wald"])
    print("    条件精确 95%% CI = [%+.4f, %+.4f]" % r["ci_exact_conditional"])
    if r["tasks_unmatched"]:
        print("    [warn] 两臂题号不一致：%s" % r["tasks_unmatched"][:5])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default=None, choices=["humaneval", "mbpp"])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        # 负控：自己和自己比，discordant 必须是 0、p 必须是 1、Δ 必须是 0；
        # 再对调两侧，Δ 必须反号。任一条不成立就说明这条装置判不出东西。
        same = compare("uni45", "uni45", "humaneval")
        flip = compare("exq4", "uni45", "humaneval")
        ok = (same["b_only_a"] == 0 and same["c_only_b"] == 0 and same["delta"] == 0
              and same["p_mcnemar_exact"] == 1.0
              and abs(flip["delta"] + compare("uni45", "exq4", "humaneval")["delta"]) < 1e-12)
        print("[%s] selftest: 自比无差、对调反号" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    benches = [args.bench] if args.bench else ["humaneval", "mbpp"]
    for bench in benches:
        for plus in (True, False):
            r = compare("uni45", "exq4", bench, plus=plus)
            show(r)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
