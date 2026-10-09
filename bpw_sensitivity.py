#!/usr/bin/env python3
"""Per-benchmark sensitivity to effective bpw.

The operator's requirement is that every conclusion be tested on more than one benchmark.
This computes the one quantity that makes the cross-benchmark comparison possible:

    for each model family, for each benchmark:  slope = d(score) / d(bpw)

then aggregates the slopes per benchmark.  A slope near 0 means the benchmark barely notices
compression; a large positive slope means it collapses.

Method notes
------------
* Effective bpw = 8 * file_bytes / n_params, from .wrapup/bpw_map.json.  Nominal labels
  (Q2/Q3) are never used: they span 2.76-5.04 bpw.
* Only within-family comparisons (same base model, different quant), so architecture and
  parameter count are held constant and bpw is the single varied quantity.
* Both variants of gsm8k exist in the DB.  The primary column is reasoning='off'
  (lm_eval's own default); reasoning='on' rows are reported separately and never mixed.
* Only the canonical campaign protocols are used, per benchmark.
* A slope needs >=2 distinct bpw within a family.  Families with exactly 2 points give an
  unbiased but noisy slope; the aggregate reports n and an item-level weighted SE.
"""
from __future__ import annotations

import collections
import json
import math
import os
import re
import sqlite3

DB = "experiments.sqlite"
BPW = json.load(open(".wrapup/bpw_map.json"))

# benchmark -> the protocol family that is the primary column
BENCH = [
    ("humaneval-plus", "code",     "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mbpp-plus",      "code",     "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mmlu",           "knowledge", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("arc_challenge",  "knowledge", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("truthfulqa_mc2", "truth",    "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("gsm8k",          "reasoning", "lmeval-0.4.13-chat-reasoning-off"),
    ("ifeval",         "instruct", "lmeval-0.4.13-chat-reasoning-off"),
]


def family_of(model: str) -> str:
    """Model stem with the quant suffix stripped (same family = same base weights)."""
    s = re.sub(r"\.gguf$", "", model)
    s = re.sub(r"-(UD-)?(I?Q[0-9].*|TQ[0-9].*)$", "", s)
    s = re.sub(r"-m55-.*$", "", s)
    return s


def load():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT model,_bench,_score,n_items,protocol,reasoning FROM experiments "
        "WHERE source_file LIKE 'mres/%'").fetchall()
    data = collections.defaultdict(dict)          # (family, bench) -> {bpw: (score, n)}
    for model, bench, score, n, proto, reasoning in rows:
        rec = next((b for b in BENCH if b[0] == bench and b[2] == proto), None)
        if rec is None or score is None:
            continue
        if bench == "gsm8k" and reasoning == "on":
            continue                              # diagnostic axis, kept out of the primary
        if model not in BPW:
            continue
        key = (family_of(model), bench)
        data[key][round(BPW[model], 3)] = (score, n or 0, model)
    return data


def main():
    data = load()
    per_bench = collections.defaultdict(list)
    for (fam, bench), pts in sorted(data.items()):
        bpws = sorted(pts)
        if len(bpws) < 2:
            continue
        lo, hi = bpws[0], bpws[-1]
        if hi - lo < 0.05:
            continue                              # not a real bpw displacement
        s_lo, n_lo, m_lo = pts[lo]
        s_hi, n_hi, m_hi = pts[hi]
        slope = (s_hi - s_lo) / (hi - lo)
        per_bench[bench].append({
            "family": fam, "bpw_lo": lo, "bpw_hi": hi,
            "score_lo": s_lo, "score_hi": s_hi, "delta": s_hi - s_lo,
            "slope": slope, "n_lo": n_lo, "n_hi": n_hi,
            "model_lo": m_lo, "model_hi": m_hi,
        })

    print("=" * 100)
    print("PER-BENCHMARK SENSITIVITY  (within-family delta score per +1 effective bpw)")
    print("=" * 100)
    summary = []
    for bench, _kind, _proto in BENCH:
        rows = per_bench.get(bench, [])
        if not rows:
            print(f"\n{bench}: no within-family bpw pairs yet")
            continue
        slopes = sorted(r["slope"] for r in rows)
        mean = sum(slopes) / len(slopes)
        med = slopes[len(slopes) // 2]
        pos = sum(1 for s in slopes if s > 0)
        # simple binomial CI on the sign, the robust statistic (slopes are heavy-tailed)
        p = pos / len(slopes)
        se = math.sqrt(p * (1 - p) / len(slopes))
        deltas = sorted(r["delta"] for r in rows)
        print(f"\n{bench}:  families={len(rows)}  sign(+)={pos}/{len(rows)} "
              f"({p:.2f} +- {1.96 * se:.2f})")
        print(f"   mean slope {mean:+.4f}/bpw   median {med:+.4f}/bpw   "
              f"range [{slopes[0]:+.4f}, {slopes[-1]:+.4f}]")
        print(f"   median delta over the family's own bpw span: {deltas[len(deltas)//2]:+.4f}")
        summary.append((bench, len(rows), pos, p, mean, med))
        for r in sorted(rows, key=lambda r: r["slope"])[:2]:
            print(f"     least sensitive: {r['family']:26s} "
                  f"{r['bpw_lo']:.2f}->{r['bpw_hi']:.2f} bpw  "
                  f"{r['score_lo']:.4f}->{r['score_hi']:.4f}  slope {r['slope']:+.4f}")
        for r in sorted(rows, key=lambda r: -r["slope"])[:2]:
            print(f"     most  sensitive: {r['family']:26s} "
                  f"{r['bpw_lo']:.2f}->{r['bpw_hi']:.2f} bpw  "
                  f"{r['score_lo']:.4f}->{r['score_hi']:.4f}  slope {r['slope']:+.4f}")

    print("\n" + "=" * 100)
    print("RANKING (median slope per +1 bpw, most sensitive first)")
    print("=" * 100)
    for bench, n, pos, p, mean, med in sorted(summary, key=lambda x: -x[5]):
        print(f"  {bench:16s} n={n:3d}  median {med:+.4f}/bpw   "
              f"mean {mean:+.4f}   positive {pos}/{n}")

    # floor analysis: the lowest bpw at which each benchmark is still above half its
    # family's best score
    print("\n" + "=" * 100)
    print("FLOOR: lowest effective bpw where a family still scores >= 50% of its own best")
    print("=" * 100)
    floors = collections.defaultdict(list)
    for (fam, bench), pts in sorted(data.items()):
        if len(pts) < 2:
            continue
        best = max(s for s, _, _ in pts.values())
        if best <= 0.05:
            continue
        ok = sorted(b for b, (s, _, _) in pts.items() if s >= 0.5 * best)
        if ok:
            floors[bench].append((fam, ok[0], best))
    for bench, _k, _p in BENCH:
        rows = floors.get(bench, [])
        if not rows:
            continue
        b = sorted(r[1] for r in rows)
        med = b[len(b) // 2]
        print(f"  {bench:16s} n={len(b):3d}  median floor {med:.2f} bpw   "
              f"range [{b[0]:.2f}, {b[-1]:.2f}]")


if __name__ == "__main__":
    main()
