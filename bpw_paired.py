#!/usr/bin/env python3
"""Paired within-family comparison of per-benchmark bpw sensitivity.

The pooled ranking in bpw_sensitivity.py compares slopes across DIFFERENT families, so a
benchmark could look sensitive merely because sensitive models happen to be in its sample.
The clean test is paired: inside one model family, compute the slope for benchmark A and for
benchmark B over the SAME bpw ladder, then take the difference.  Family-level variance
cancels, and the only thing left is the benchmark.

Reported for every pair of benchmark families:
  n        = families that have a usable ladder in both benchmarks
  mean d   = mean(slope_A - slope_B)
  wins     = d > 0
  CI       = t-style 95% CI on the paired mean (df = n-1)
"""
from __future__ import annotations

import collections
import itertools
import math
import sqlite3
import sys

sys.path.insert(0, ".")
from bpw_sensitivity import BENCH, BPW, family_of, load  # noqa: E402

KIND = {b: k for b, k, _ in BENCH}


def slopes_by_family():
    data = load()
    out = collections.defaultdict(dict)          # family -> bench -> slope
    spans = collections.defaultdict(dict)
    for (fam, bench), pts in data.items():
        bpws = sorted(pts)
        if len(bpws) < 2:
            continue
        lo, hi = bpws[0], bpws[-1]
        if hi - lo < 0.05:
            continue
        out[fam][bench] = (pts[hi][0] - pts[lo][0]) / (hi - lo)
        spans[fam][bench] = (lo, hi)
    return out, spans


def t_crit(df: int) -> float:
    # two-sided 95% t quantiles, df 1..30
    tbl = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
           8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
           15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
    return tbl.get(df, 1.96)


def main():
    fam_slopes, spans = slopes_by_family()
    benches = [b for b, _, _ in BENCH]
    print("=" * 104)
    print("PAIRED WITHIN-FAMILY SENSITIVITY DIFFERENCES  "
          "(d = slope_A - slope_B, per +1 effective bpw)")
    print("=" * 104)
    print(f"{'A':16s} {'B':16s} {'n':>3s} {'mean d':>9s} {'wins':>5s} {'95% CI':>22s}  verdict")
    res = []
    for a, b in itertools.combinations(benches, 2):
        ds = [fa[a] - fa[b] for fa in fam_slopes.values() if a in fa and b in fa]
        if len(ds) < 3:
            continue
        n = len(ds)
        mean = sum(ds) / n
        var = sum((d - mean) ** 2 for d in ds) / (n - 1)
        se = math.sqrt(var / n)
        half = t_crit(n - 1) * se
        lo, hi = mean - half, mean + half
        wins = sum(1 for d in ds if d > 0)
        verdict = "A more sensitive" if lo > 0 else ("B more sensitive" if hi < 0 else "ns")
        res.append((mean, a, b, n, wins, lo, hi, verdict))
        print(f"{a:16s} {b:16s} {n:3d} {mean:+9.4f} {wins:>3d}/{n:<2d} "
              f"[{lo:+.4f},{hi:+.4f}]  {verdict}")

    print("\n" + "=" * 104)
    print("CONFIRMED ORDERINGS (95% CI excludes 0), most sensitive first")
    print("=" * 104)
    for mean, a, b, n, wins, lo, hi, verdict in sorted(res, key=lambda x: -x[0]):
        if verdict != "ns":
            print(f"  {a:16s} > {b:16s}   +{mean:.4f}/bpw   n={n}  wins {wins}/{n}")

    print("\n" + "=" * 104)
    print("GROUPED: code+instruct+reasoning vs knowledge+truth (one paired test per family)")
    print("=" * 104)
    hot = ["humaneval-plus", "mbpp-plus", "ifeval", "gsm8k"]
    cold = ["mmlu", "arc_challenge", "truthfulqa_mc2"]
    ds = []
    for fam, sl in fam_slopes.items():
        hv = [sl[b] for b in hot if b in sl]
        cv = [sl[b] for b in cold if b in sl]
        if hv and cv:
            ds.append(sum(hv) / len(hv) - sum(cv) / len(cv))
    n = len(ds)
    mean = sum(ds) / n
    var = sum((d - mean) ** 2 for d in ds) / (n - 1)
    se = math.sqrt(var / n)
    half = t_crit(min(n - 1, 20)) * se
    print(f"  n={n} families   mean difference {mean:+.4f}/bpw   "
          f"95% CI [{mean - half:+.4f}, {mean + half:+.4f}]")
    print(f"  families where the 'hot' group is more sensitive: "
          f"{sum(1 for d in ds if d > 0)}/{n}")


if __name__ == "__main__":
    main()
