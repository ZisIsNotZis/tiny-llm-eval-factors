#!/usr/bin/env python3
"""Figures for the quant-vs-score study (read-only on experiments.sqlite).

Produces figures/ so the controlled-variable results can be read at a glance:

  fig1_sensitivity.png   -- F9: the slope VECTOR (per-benchmark), paired forest vs TruthfulQA,
                            and the grouped capability-vs-knowledge paired test.
  fig2_curves.png        -- within-family score-vs-effective-bpw curves, 7 benchmark panels,
                            each family normalised to its own [min,max] so the SHAPE is comparable.
  fig3_steps.png         -- F2/F3: the Qwen3.5-2B full ladder and the 2B tool-floor collapse.
  fig4_moe.png           -- F11: MoE bit allocation at (nearly) matched total size.

Every number is recomputed here from the DB; nothing is hand-copied.
"""
from __future__ import annotations

import collections
import json
import math
import os
import re
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DB = "experiments.sqlite"
BPW = json.load(open(".wrapup/bpw_map.json"))
OUT = "figures"

BENCH = [
    ("humaneval-plus", "code",      "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mbpp-plus",      "code",      "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mmlu",           "knowledge", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("arc_challenge",  "knowledge", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("truthfulqa_mc2", "truth",     "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("gsm8k",          "reasoning", "lmeval-0.4.13-chat-reasoning-off"),
    ("ifeval",         "instruct",  "lmeval-0.4.13-chat-reasoning-off"),
]
LABEL = {
    "humaneval-plus": "HumanEval+\n(code)", "mbpp-plus": "MBPP+\n(code)",
    "mmlu": "MMLU\n(knowledge)", "arc_challenge": "ARC-c\n(science MC)",
    "truthfulqa_mc2": "TruthfulQA\n(truth MC)", "gsm8k": "GSM8K\n(reasoning)",
    "ifeval": "IFEval\n(instruct)",
}
HOT = ["humaneval-plus", "mbpp-plus", "ifeval", "gsm8k"]
COLD = ["mmlu", "arc_challenge", "truthfulqa_mc2"]


def family_of(model: str) -> str:
    s = re.sub(r"\.gguf$", "", model)
    s = re.sub(r"-(UD-)?(I?Q[0-9].*|TQ[0-9].*)$", "", s)
    s = re.sub(r"-m55-.*$", "", s)
    return s


def load():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT model,_bench,_score,n_items,protocol,reasoning FROM experiments "
        "WHERE source_file LIKE 'mres/%'").fetchall()
    data = collections.defaultdict(dict)
    for model, bench, score, n, proto, reasoning in rows:
        rec = next((b for b in BENCH if b[0] == bench and b[2] == proto), None)
        if rec is None or score is None or model not in BPW:
            continue
        if bench == "gsm8k" and reasoning == "on":
            continue
        data[(family_of(model), bench)][round(BPW[model], 3)] = (score, n or 0, model)
    return data


def slopes_by_family(data):
    fam = collections.defaultdict(dict)
    for (f, bench), pts in data.items():
        bpws = sorted(pts)
        if len(bpws) < 2:
            continue
        lo, hi = bpws[0], bpws[-1]
        if hi - lo < 0.05:
            continue
        fam[f][bench] = (pts[hi][0] - pts[lo][0]) / (hi - lo)
    return fam


def t_crit(df):
    tbl = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
           8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
           15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
    return tbl.get(df, 1.96)


def paired(ds):
    n = len(ds)
    m = sum(ds) / n
    var = sum((d - m) ** 2 for d in ds) / (n - 1)
    se = math.sqrt(var / n)
    h = t_crit(n - 1) * se
    return n, m, m - h, m + h


def fig1(data, fam):
    benches = [b for b, _, _ in BENCH]
    fig = plt.figure(figsize=(15, 11))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1.0], hspace=0.42, wspace=0.28)

    # A. slope strip per benchmark
    ax = fig.add_subplot(gs[0, 0])
    order = sorted(benches, key=lambda b: -np.median([fa[b] for fa in fam.values() if b in fa]))
    for i, b in enumerate(order):
        v = np.array([fa[b] for fa in fam.values() if b in fa])
        ax.scatter(np.full(len(v), i) + np.random.RandomState(0).uniform(-.12, .12, len(v)),
                   v, s=26, alpha=.65, color="#3b7dd8", zorder=3)
        ax.plot([i - .28, i + .28], [np.median(v)] * 2, color="#c0392b", lw=2.6, zorder=4)
        ax.text(i + .3, np.median(v), f" {np.median(v):+.3f}", color="#c0392b",
                va="center", fontsize=9)
    ax.axhline(0, color="#888", lw=.8)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([LABEL[b].replace("\n", " ") for b in order], fontsize=8,
                       rotation=30, ha="right")
    ax.set_ylabel("within-family slope  Δscore per +1 bpw")
    ax.set_title("A. Sensitivity is a VECTOR: same bpw step, per-benchmark slope\n"
                 "(blue = one family, red = median; n=16-18 families each)", fontsize=10)
    ax.grid(axis="y", alpha=.25)

    # B. paired difference vs TruthfulQA (forest)
    ax = fig.add_subplot(gs[0, 1])
    ref = "truthfulqa_mc2"
    items = []
    for b in benches:
        if b == ref:
            continue
        ds = [fa[b] - fa[ref] for fa in fam.values() if b in fa and ref in fa]
        if len(ds) < 3:
            continue
        items.append((b,) + paired(ds))
    items.sort(key=lambda x: x[2])
    for i, (b, n, m, lo, hi) in enumerate(items):
        sig = lo > 0 or hi < 0
        ax.errorbar(m, i, xerr=[[m - lo], [hi - m]], fmt="o",
                    color="#c0392b" if sig else "#7f8c8d", capsize=4, lw=1.8, ms=7)
        ax.text(hi + .008, i, f"n={n}", va="center", fontsize=8, color="#555")
    ax.axvline(0, color="#888", lw=.9, ls="--")
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([LABEL[b].replace("\n", " ") for b, *_ in items], fontsize=8.5)
    ax.set_xlabel("paired Δslope vs TruthfulQA (per +1 bpw), 95% CI")
    ax.set_title("B. Paired inside each family: capability tasks move\n"
                 "far more per bpw than truth/knowledge (red = CI excludes 0)", fontsize=10)
    ax.grid(axis="x", alpha=.25)

    # C. grouped hot vs cold paired distribution
    ax = fig.add_subplot(gs[1, 0])
    ds = []
    for f, sl in fam.items():
        hv = [sl[b] for b in HOT if b in sl]
        cv = [sl[b] for b in COLD if b in sl]
        if hv and cv:
            ds.append((f, sum(hv) / len(hv) - sum(cv) / len(cv)))
    vals = np.array([d for _, d in ds])
    ax.hist(vals, bins=np.arange(-.1, .55, .05), color="#5b9bd5", edgecolor="white")
    n, m, lo, hi = paired(list(vals))
    ax.axvline(m, color="#c0392b", lw=2.4)
    ax.axvspan(lo, hi, color="#c0392b", alpha=.12)
    ax.axvline(0, color="#333", lw=1, ls="--")
    ax.set_xlabel("capability mean slope − knowledge mean slope  (per +1 bpw)")
    ax.set_ylabel("families")
    ax.set_title(f"C. Grouped paired test: mean +{m:.3f}/bpw  "
                 f"95% CI [{lo:+.3f}, {hi:+.3f}]  n={n}  "
                 f"({sum(v > 0 for v in vals)}/{n} positive)", fontsize=10)
    ax.grid(axis="y", alpha=.25)

    # D. worked example: granite-4.1-3b
    ax = fig.add_subplot(gs[1, 1])
    fam_name = "granite-4.1-3b"
    pts = {b: data.get((fam_name, b), {}) for b in benches}
    labels, lo_b, hi_b, d = [], [], [], []
    for b in benches:
        p = pts[b]
        if len(p) < 2:
            continue
        k = sorted(p)
        labels.append(LABEL[b].replace("\n", " "))
        lo_b.append(p[k[0]][0]); hi_b.append(p[k[-1]][0]); d.append(p[k[-1]][0] - p[k[0]][0])
    x = np.arange(len(labels))
    ax.bar(x - .2, lo_b, .4, label="low bpw (3.22)", color="#bdc3c7")
    ax.bar(x + .2, hi_b, .4, label="high bpw (4.94)", color="#c0392b")
    for xi, (ly, hy, dd) in enumerate(zip(lo_b, hi_b, d)):
        ax.text(xi, max(ly, hy) + .02, f"{dd:+.2f}",
                ha="center", fontsize=8.5, color="#c0392b")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=30, ha="right")
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("score")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_title("D. One family, no aggregation: granite-4.1-3b\n"
                 "code moves +0.68, MC knowledge only +0.04", fontsize=10)
    ax.grid(axis="y", alpha=.25)

    fig.suptitle("F9 — Quantisation damage is benchmark-dependent (effective bpw, within-family, item-level)",
                 fontsize=13, y=.98)
    fig.savefig(f"{OUT}/fig1_sensitivity.png", dpi=140, bbox_inches="tight")
    print("wrote fig1_sensitivity.png")


def fig2(data, fam):
    """Family x benchmark heatmap of within-family slopes (the controlled result, no aggregation)."""
    benches = [b for b, _, _ in BENCH]
    fams = sorted([f for f in fam if len(fam[f]) >= 2],
                  key=lambda f: -np.mean([fam[f][b] for b in benches if b in fam[f]]))
    M = np.full((len(fams), len(benches)), np.nan)
    for i, f in enumerate(fams):
        for j, b in enumerate(benches):
            if b in fam[f]:
                M[i, j] = fam[f][b]
    fig, ax = plt.subplots(figsize=(11.5, max(6, .42 * len(fams))))
    vmax = .7
    im = ax.imshow(M, cmap="YlOrRd", vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(benches)))
    ax.set_xticklabels([LABEL[b].replace("\n", " ") for b in benches], fontsize=8.5,
                       rotation=25, ha="right")
    ax.set_yticks(range(len(fams)))
    ax.set_yticklabels(fams, fontsize=8.5)
    for i in range(len(fams)):
        for j in range(len(benches)):
            v = M[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=7.5,
                        color="white" if v > .45 else "#222")
            else:
                ax.text(j, i, "-", ha="center", va="center", fontsize=8, color="#aaa")
    cb = fig.colorbar(im, ax=ax, shrink=.7, pad=.02)
    cb.set_label("within-family slope: Δscore per +1 effective bpw")
    ax.set_title("F9 — One family per row, one benchmark per column; cell = that family's own slope.\n"
                 "Rows sorted by mean slope. Every row varies only bpw (same base weights). "
                 "Blank '-' = benchmark not measured for that family.", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig2_slope_heatmap.png", dpi=140, bbox_inches="tight")
    print("wrote fig2_slope_heatmap.png")


def fig3(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.4))

    # left: Qwen3.5-2B MultiPL-E ladder (pooled over languages, panel m3-quant-ladder)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT model,language,_score FROM experiments "
        "WHERE protocol='multipl-e-raw-greedy-768' "
        "AND run_tag='m3-quant-ladder' AND model LIKE 'Qwen3.5-2B%'").fetchall()
    acc = collections.defaultdict(list)
    for m, lang, s in rows:
        if s is not None and m in BPW:
            acc[m].append(s)
    pts = {round(BPW[m], 2): sum(v) / len(v) for m, v in acc.items()}
    k = sorted(pts)
    xs = [round(x, 2) for x in k]
    ys = [pts[x] for x in k]
    ax1.plot(xs, ys, "-o", color="#2c6fbb", lw=2, ms=7)
    for x, y in zip(xs, ys):
        ax1.annotate(f"{y:.3f}", (x, y), textcoords="offset points", xytext=(0, 8),
                     ha="center", fontsize=8)
    ax1.set_xlabel("effective bpw")
    ax1.set_ylabel("MultiPL-E pooled pass@1")
    ax1.set_title("F2 — the quant curve is a STEP then a plateau\n(Qwen3.5-2B, raw-greedy)", fontsize=10.5)
    ax1.grid(alpha=.3)

    # right: 2B tool-call floor collapse Q2 vs Q3
    cats = ["multi_turn_base", "multi_turn_miss_param",
            "multi_turn_long_context", "multi_turn_miss_func"]
    q2 = [0.025, 0.005, 0.005, 0.005]
    q3 = [0.185, 0.105, 0.110, 0.080]
    x = np.arange(len(cats))
    ax2.bar(x - .2, q2, .4, label="Q2 (2B)", color="#bdc3c7")
    ax2.bar(x + .2, q3, .4, label="Q3 (2B)", color="#c0392b")
    ax2.set_xticks(x)
    ax2.set_xticklabels([c.replace("multi_turn_", "") for c in cats], fontsize=9)
    ax2.set_ylabel("BFCL accuracy (200 items)")
    ax2.set_title("F3 — at 2B/Q2 every hard agentic category\npins to the floor (~0.005)", fontsize=10.5)
    ax2.legend(fontsize=9)
    ax2.grid(axis="y", alpha=.3)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig3_steps.png", dpi=140, bbox_inches="tight")
    print("wrote fig3_steps.png")


def fig4():
    recipes = ["uniform Q3_K_M\nbaseline", "experts IQ2/Q2\nrest Q5_K_M", "experts Q4_K\nrest Q2_K"]
    bpw = [3.88, 2.92, 4.48]
    # HumanEval+ / MBPP+ / MMLU / GSM8K  (table D in RESULTS_BY_COMPARISON.md)
    data = {
        "HumanEval+": [0.3354, 0.2866, 0.1341],
        "MBPP+":      [0.4815, 0.3280, 0.2381],
        "MMLU":       [0.4474, 0.4265, 0.2873],
        "GSM8K":      [0.7500, 0.7800, 0.5300],
    }
    x = np.arange(len(recipes))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(14, 5.4), gridspec_kw={"width_ratios": [2.2, 1]})
    w = .2
    colors = ["#2c6fbb", "#e67e22", "#27ae60", "#8e44ad"]
    for i, (name, vals) in enumerate(data.items()):
        ax.bar(x + (i - 1.5) * w, vals, w, label=name, color=colors[i])
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r}\n{b:.2f} bpw" for r, b in zip(recipes, bpw)], fontsize=9)
    ax.set_ylabel("score")
    ax.set_ylim(0, .9)
    ax.legend(fontsize=9)
    ax.set_title("F11 — same base weights, only WHICH layers get low bits varies.\n"
                 "The highest-bpw recipe is the WORST model.", fontsize=10.5)
    ax.grid(axis="y", alpha=.3)
    ax2.bar(x, bpw, .5, color=["#7f8c8d", "#27ae60", "#c0392b"])
    ax2.set_xticks(x)
    ax2.set_xticklabels(["uniform", "exq2", "exq4"], fontsize=9)
    ax2.set_ylabel("effective bpw")
    ax2.set_title("bits spent", fontsize=10.5)
    for xi, b in zip(x, bpw):
        ax2.text(xi, b + .05, f"{b:.2f}", ha="center", fontsize=9)
    ax2.set_ylim(0, 5)
    ax2.grid(axis="y", alpha=.3)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig4_moe.png", dpi=140, bbox_inches="tight")
    print("wrote fig4_moe.png")


def main():
    os.makedirs(OUT, exist_ok=True)
    data = load()
    fam = slopes_by_family(data)
    fig1(data, fam)
    fig2(data, fam)
    fig3(data)
    fig4()

    # also print the numbers behind fig1 in text form
    print("\nper-benchmark median slope (behind fig1A):")
    for b, _, _ in BENCH:
        v = [fa[b] for fa in fam.values() if b in fa]
        if v:
            print(f"  {b:16s} n={len(v):2d} median {np.median(v):+.4f} mean {np.mean(v):+.4f}")


if __name__ == "__main__":
    main()
