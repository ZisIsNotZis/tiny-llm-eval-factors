#!/usr/bin/env python3
"""Figure for the three new axes (1.6 QAT, 1.5 GSQ-RCO, 7 DiffusionGemma).

Reads experiments.sqlite through axes_findings.py (same canonical cells, same item-level
CIs).  Produces figures/fig5_axes.png:

  A  Axis 1.6 forest: pooled per-benchmark delta (QAT - native), UD-Q4_K_XL pairs (solid)
     and UD-Q2_K_XL pairs (open), 95% item-level CI.
  B  Axis 1.5: per-benchmark delta of each GSQ-RCO quant against the native score
     interpolated to the GSQ quant's own effective bpw, 95% CI.
  C  Axis 1.6 confound note: effective bpw of the QAT file vs its native partner per pair
     (the nominal recipe is held fixed but the QAT file compresses to fewer bytes).

Run: python3 .wrapup/axes_figure.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

# CJK font for the Chinese/English (中文/英文) panel labels
_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
if os.path.exists(_CJK):
    fm.fontManager.addfont(_CJK)
    plt.rcParams["font.sans-serif"] = [fm.FontProperties(fname=_CJK).get_name(), "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from axes_findings import (BENCH, QAT_PAIRS, GSQ_TAGS, NATIVE_TAGS, TAG_MODEL,  # noqa: E402
                           BPW, Z, delta_ci, load, cell)
import math  # noqa: E402

OUT = "figures"
SHORT = {"humaneval-plus": "HumanEval+", "mbpp-plus": "MBPP+", "mmlu": "MMLU",
         "arc_challenge": "ARC-c", "truthfulqa_mc2": "TruthfulQA", "gsm8k": "GSM8K",
         "ifeval": "IFEval"}


def pooled_per_bench(data, pairs):
    out = {}
    for b in BENCH:
        ds = [delta_ci(cell(data, t, b), cell(data, c, b)) for t, c, _, _ in pairs]
        ds = [x for x in ds if x]
        if not ds:
            out[b] = None
            continue
        w = [1 / x["se"] ** 2 for x in ds]
        d = sum(wi * x["delta"] for wi, x in zip(w, ds)) / sum(w)
        se = math.sqrt(1 / sum(w))
        out[b] = {"delta": d, "ci_lo": d - Z * se, "ci_hi": d + Z * se, "n": len(ds)}
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    data = load()
    q4 = [p for p in QAT_PAIRS if p[3] == "UD-Q4_K_XL"]
    q2 = [p for p in QAT_PAIRS if p[3] == "UD-Q2_K_XL"]
    p4 = pooled_per_bench(data, q4)
    p2 = pooled_per_bench(data, q2)

    fig, (axA, axB, axC) = plt.subplots(1, 3, figsize=(17, 6.0),
                                        gridspec_kw={"width_ratios": [1.15, 1.05, 0.8]})

    # --- A: axis 1.6 forest ---
    order = list(reversed(BENCH))
    y = range(len(order))
    dx4 = [p4[b]["delta"] if p4[b] else float("nan") for b in order]
    ex4 = [(p4[b]["delta"] - p4[b]["ci_lo"], p4[b]["ci_hi"] - p4[b]["delta"]) if p4[b]
           else (0, 0) for b in order]
    dx2 = [p2[b]["delta"] if p2[b] else float("nan") for b in order]
    ex2 = [(p2[b]["delta"] - p2[b]["ci_lo"], p2[b]["ci_hi"] - p2[b]["delta"]) if p2[b]
           else (0, 0) for b in order]
    axA.axvline(0, color="0.4", lw=1)
    axA.errorbar(dx4, list(y), xerr=list(zip(*ex4)), fmt="o", color="#1f77b4",
                 capsize=3, label="UD-Q4_K_XL (5 pairs)")
    axA.errorbar(dx2, [i + 0.22 for i in y], xerr=list(zip(*ex2)), fmt="s",
                 mfc="white", color="#d62728", capsize=3, label="UD-Q2_K_XL (2 pairs)")
    axA.set_yticks(list(y))
    axA.set_yticklabels([SHORT[b] for b in order])
    axA.set_xlabel("pooled delta  QAT - native  (score points)\n量化QAT − 原生native 得分差")
    axA.set_title("A  轴 1.6  QAT vs native / 量化QAT对原生\n"
                  "(controlled: same size + same nominal recipe / 同尺寸同标称配方)")
    axA.legend(fontsize=8, loc="lower right")
    axA.grid(alpha=0.25)

    # --- B: axis 1.5 forest (delta vs interpolated native at the GSQ bpw) ---
    native = sorted((BPW.get(TAG_MODEL[t]), lbl, t) for t, lbl in NATIVE_TAGS)
    colors = {"GSQ-RCO IQ3_XXS": "#2ca02c", "GSQ-RCO IQ3_S": "#9467bd"}
    b_any = False
    for j, (tag, label) in enumerate(GSQ_TAGS):
        gbpw = BPW.get(TAG_MODEL[tag])
        lo = max((x for x in native if x[0] <= gbpw), default=None)
        hi = min((x for x in native if x[0] >= gbpw), default=None)
        ds, ys = [], []
        for i, b in enumerate(order):
            g = cell(data, tag, b)
            cl = cell(data, lo[2], b) if lo else None
            ch = cell(data, hi[2], b) if hi else None
            if g and cl and ch and lo and hi and lo[0] != hi[0]:
                frac = (gbpw - lo[0]) / (hi[0] - lo[0])
                pred = cl[0] + frac * (ch[0] - cl[0])
                d = g[0] - pred
                # SE propagation: g's Bernoulli + the native bracket's nearest n
                nb = cl if abs(gbpw - lo[0]) < abs(hi[0] - gbpw) else ch
                se = math.sqrt(g[0] * (1 - g[0]) / g[1] + nb[0] * (1 - nb[0]) / nb[1])
                ds.append((d, se, i, g[0]))
        axB.axvline(0, color="0.4", lw=1)
        if ds:
            b_any = True
            for d, se, i, _ in ds:
                axB.errorbar(d, i + (j - 0.5) * 0.22, xerr=1.96 * se, fmt="o" if j == 0 else "s",
                             color=colors[label], capsize=3, alpha=0.9)
            axB.plot([], [], "o", color=colors[label], label=f"{label} @{gbpw:.2f} bpw")
    axB.set_yticks(list(y))
    axB.set_yticklabels([SHORT[b] for b in order])
    axB.set_xlabel("delta  GSQ-RCO - native(interp to same bpw)\nGSQ-RCO − 原生(插值到同bpw)")
    axB.set_title("B  轴 1.5  GSQ-RCO vs native ladder / 对原生量化阶梯\n"
                  "(control interpolated to the GSQ bpw / 对照插值到GSQ自身bpw)")
    if b_any:
        axB.legend(fontsize=8, loc="lower right")
    else:
        axB.text(0.5, 0.5, "pending / 待测", transform=axB.transAxes,
                 ha="center", va="center", color="0.5", fontsize=12)
    axB.grid(alpha=0.25)

    # --- C: bpw confound ---
    labels, dq = [], []
    for t, c, label, recipe in QAT_PAIRS:
        bt, bc = BPW.get(TAG_MODEL[t]), BPW.get(TAG_MODEL[c])
        labels.append(f"{label}\n{recipe}")
        dq.append(bt - bc)
    axC.barh(range(len(labels)), dq, color="#1f77b4")
    axC.axvline(0, color="0.4", lw=1)
    axC.set_yticks(range(len(labels)))
    axC.set_yticklabels(labels, fontsize=7)
    axC.set_xlabel("effective bpw  QAT - native\n有效bpw差 QAT−原生")
    axC.set_title("C  轴 1.6 confound / 混淆:\nQAT files are lower bpw / QAT文件bpw更低")
    axC.grid(alpha=0.25, axis="x")

    fig.suptitle("Three new axes / 三个新轴: QAT (1.6), GSQ-RCO (1.5), "
                 "DiffusionGemma (7 = gate-fail runtime-blocked, 无数值)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(f"{OUT}/fig5_axes.png", dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}/fig5_axes.png")


if __name__ == "__main__":
    main()
