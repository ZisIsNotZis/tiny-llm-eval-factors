#!/usr/bin/env python3
"""T2 analysis — binary pass@1 vs continuous per-test fraction.

Reads .wrapup/testfrac_summary.jsonl and the per-item testfrac_*.jsonl files,
then reports the Qwen3.5-2B quant ladder (the Q3/Q4/Q5 region) and the other
anchors, and tests whether the continuous metric separates the quant levels.
"""
import glob
import json
import os
import random
import re
import sys

WD = "/home/z/hf/research/.wrapup"

# filename tag -> (anchor, quant)
TAG = {
    "m1-qwen4b-q2": ("Qwen4B", "Q2"),
    "m1-qwen4b-q3": ("Qwen4B", "Q3"),
    "m3-iq2xxs": ("Qwen3.5-2B", "IQ2_XXS"),
    "m3-iq2m": ("Qwen3.5-2B", "IQ2_M"),
    "m3-q2": ("Qwen3.5-2B", "Q2_K_XL"),
    "m3-q3": ("Qwen3.5-2B", "Q3_K_XL"),
    "m3-q4": ("Qwen3.5-2B", "Q4_K_XL"),
    "m3-q5": ("Qwen3.5-2B", "Q5_K_XL"),
    "m3-e2b-q2": ("gemma-4-E2B", "Q2_K_XL"),
    "m3-e2b-q3": ("gemma-4-E2B", "Q3_K_XL"),
    "m3-e4b-q2": ("gemma-4-E4B", "Q2_K_XL"),
    "m3-e4b-q3": ("gemma-4-E4B", "Q3_K_XL"),
    "m3-gr3b-q2": ("granite-4.1-3b", "Q2_K"),
    "m3-gr3b-q3": ("granite-4.1-3b", "Q3_K_M"),
    "m3-q08b-q2": ("Qwen3.5-0.8B", "Q2_K_XL"),
    "m3-q08b-q3": ("Qwen3.5-0.8B", "Q3_K_XL"),
    "m3-g12b-q2": ("gemma-4-12B", "Q2_K_XL"),
    "m3-g12b-q3": ("gemma-4-12B", "Q3_K_XL"),
    "m3-q36-35b-q2": ("Qwen3.6-35B-A3B", "Q2_K_XL"),
    "m3-q36-35b-q3": ("Qwen3.6-35B-A3B", "Q3_K_XL"),
}
ORDER = ["IQ2_XXS", "IQ2_M", "Q2_K", "Q2_K_XL", "Q3_K_M", "Q3_K_XL",
         "Q4_K_XL", "Q5_K_XL"]


def tag_of(samples):
    base = os.path.basename(samples).replace(".jsonl", "")
    for t in sorted(TAG, key=len, reverse=True):
        if base == t + "-" + base.rsplit("-", 1)[-1] and base.startswith(t + "-"):
            return t
    m = re.match(r"(m\d+-[a-z0-9]+-[a-z0-9]+)-(cpp|java|js|py|rs|rb)$", base)
    return m.group(1) if m else base


def load_summary():
    rows = []
    for line in open(f"{WD}/testfrac_summary.jsonl"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        base = os.path.basename(d["samples"]).replace(".jsonl", "")
        lang = d["lang"]
        tag = base[: -len(lang) - 1]
        anchor, quant = TAG.get(tag, (tag, tag))
        d.update({"tag": tag, "anchor": anchor, "quant": quant,
                  "lang": lang})
        rows.append(d)
    return rows


def load_items(tag, lang):
    p = f"{WD}/testfrac_{tag}-{lang}.jsonl"
    if not os.path.exists(p):
        return {}
    return {json.loads(l)["name"]: json.loads(l) for l in open(p)}


def qorder(qs):
    return sorted(qs, key=lambda q: ORDER.index(q) if q in ORDER else 99)


def bootstrap_mean_ci(vals, n=5000, seed=0):
    if not vals:
        return (0.0, 0.0)
    rnd = random.Random(seed)
    means = []
    N = len(vals)
    for _ in range(n):
        means.append(sum(vals[rnd.randrange(N)] for _ in range(N)) / N)
    means.sort()
    return means[int(0.025 * n)], means[int(0.975 * n)]


def table_by_quant(rows, anchor, langs):
    print(f"\n## {anchor}: binary pass@1 vs continuous fraction")
    print(f"{'quant':10} {'lang':5} {'n':>4} {'pass@1':>8} {'mean_frac':>10} {'micro_frac':>11}")
    qs = qorder({r["quant"] for r in rows if r["anchor"] == anchor})
    pooled = {}
    for q in qs:
        for lang in langs:
            rs = [r for r in rows if r["anchor"] == anchor and r["quant"] == q
                  and r["lang"] == lang]
            if not rs:
                continue
            r = rs[0]
            print(f"{q:10} {lang:5} {r['n']:>4} {r['pass_at_1']:>8.3f} "
                  f"{r['mean_frac']:>10.3f} {r['micro_frac']:>11.3f}")
        # pool langs by item
        items = {}
        for lang in langs:
            for name, it in load_items(
                    next(r["tag"] for r in rows if r["anchor"] == anchor
                         and r["quant"] == q), lang).items():
                items[(lang, name)] = it
        if items:
            fracs = [it["frac"] for it in items.values() if it["n_tests"]]
            tot_t = sum(it["n_tests"] for it in items.values() if it["n_tests"])
            tot_p = sum(it["n_pass"] for it in items.values() if it["n_tests"])
            npass = sum(1 for it in items.values() if it["binary_pass"])
            pooled[q] = {"n": len(items), "mean_frac": sum(fracs) / len(fracs),
                         "micro_frac": tot_p / tot_t if tot_t else 0,
                         "pass_at_1": npass / len(items), "fracs": fracs}
    return qs, pooled


def paired_region(rows, anchor, quants, langs, seed=1):
    """Per-item fraction for each quant; bootstrap the mean differences."""
    print(f"\n## {anchor}: paired per-item fraction, quants {quants}")
    tags = {}
    for r in rows:
        if r["anchor"] == anchor and r["quant"] in quants:
            tags[r["quant"]] = r["tag"]
    # item key -> frac per quant (average frac over langs for the same item)
    per_q = {}
    for q in quants:
        agg = {}
        for lang in langs:
            for name, it in load_items(tags[q], lang).items():
                agg.setdefault(name, []).append(it["frac"])
        per_q[q] = {k: sum(v) / len(v) for k, v in agg.items()}
    common = set.intersection(*[set(per_q[q]) for q in quants]) if quants else set()
    common = sorted(common)
    print(f"common items: {len(common)}")
    means = {q: sum(per_q[q][k] for k in common) / len(common) for q in quants}
    for q in quants:
        lo, hi = bootstrap_mean_ci([per_q[q][k] for k in common], seed=seed)
        print(f"  {q:10} mean_frac={means[q]:.4f}  boot95%=[{lo:.4f},{hi:.4f}]")
    base = quants[0]
    for q in quants[1:]:
        diffs = [per_q[q][k] - per_q[base][k] for k in common]
        m = sum(diffs) / len(diffs)
        lo, hi = bootstrap_mean_ci(diffs, seed=seed + 5)
        # sign test
        pos = sum(1 for d in diffs if d > 1e-9)
        neg = sum(1 for d in diffs if d < -1e-9)
        print(f"  d({q} - {base}) = {m:+.4f}  boot95%=[{lo:+.4f},{hi:+.4f}]  "
              f"items +/{pos} -/{neg}")
    return common, per_q


def main():
    rows = load_summary()
    print(f"loaded {len(rows)} file summaries")
    qs, pooled = table_by_quant(rows, "Qwen3.5-2B", ["cpp", "js", "py"])
    print("\n  pooled cpp+js+py (per quant):")
    for q in qs:
        if q in pooled:
            p = pooled[q]
            print(f"    {q:10} n={p['n']} pass@1={p['pass_at_1']:.4f} "
                  f"mean_frac={p['mean_frac']:.4f} micro_frac={p['micro_frac']:.4f}")
    paired_region(rows, "Qwen3.5-2B", ["Q3_K_XL", "Q4_K_XL", "Q5_K_XL"],
                  ["cpp", "js", "py"])
    paired_region(rows, "Qwen3.5-2B", ["Q2_K_XL", "Q3_K_XL"], ["cpp", "js", "py"])
    # other anchors quick table
    for anchor, langs in [("Qwen4B", ["cpp", "java", "js", "py"]),
                          ("gemma-4-E2B", ["cpp", "js", "py"]),
                          ("gemma-4-E4B", ["cpp", "js", "py"]),
                          ("gemma-4-12B", ["cpp", "js", "py"]),
                          ("granite-4.1-3b", ["cpp", "js", "py"]),
                          ("Qwen3.5-0.8B", ["cpp", "java", "js", "py"]),
                          ("Qwen3.6-35B-A3B", ["cpp", "py"])]:
        if any(r["anchor"] == anchor for r in rows):
            table_by_quant(rows, anchor, langs)


if __name__ == "__main__":
    main()
