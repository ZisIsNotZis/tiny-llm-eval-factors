#!/usr/bin/env python3
"""MultiPL-E analysis across families and quant levels.

Reads all DB rows with bench_family='humaneval-multipl-e' (run tags m1/m2/m3/m5),
groups by (base model, quant level, language), and reports:

  * per-family quant ladders (pooled over languages),
  * per-step deltas (level N -> N+1) with CIs over languages,
  * the cross-family Q2->Q3 summary (the study's core effect).

Quant strings differ by family (`UD-Q2_K_XL`, `Q2_K`, `Q3_K_M`, `UD-IQ2_M`), so
the level is taken from the digit and the ladder is built on levels.

Writes multipl_e.json + MULTIPLE.md.
"""
import json
import math
import re
import sqlite3
from collections import defaultdict

DB = "file:experiments.sqlite?mode=ro"
QUANT_RE = re.compile(r"-((UD-)?I?Q[1-8][A-Z0-9_]*)\.gguf$", re.I)
LEVEL_RE = re.compile(r"(?:I)?Q([1-8])", re.I)


def ci95(vals):
    """Cross-language CI (kept for reference only -- n is the number of LANGUAGES,
    which is far too small to be the uncertainty of an item-level effect)."""
    n = len(vals)
    if n < 2:
        return None
    m = sum(vals) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (n - 1))
    se = sd / math.sqrt(n)
    return {"n": n, "mean": round(m, 4), "ci_low": round(m - 1.96 * se, 4),
            "ci_high": round(m + 1.96 * se, 4)}


def ci_items(pass_a, n_a, pass_b, n_b):
    """Item-level 95% CI for the difference of two independent proportions.

    THIS is the correct uncertainty for a quant step: every benchmark item is a
    Bernoulli trial.  Using the cross-language CI instead (n = 2-3) makes the
    intervals roughly an order of magnitude too narrow.
    """
    if not n_a or not n_b:
        return None
    pa, pb = pass_a / n_a, pass_b / n_b
    se = math.sqrt(pa * (1 - pa) / n_a + pb * (1 - pb) / n_b)
    d = pb - pa
    return {"n_items": n_a + n_b, "mean": round(d, 4),
            "se": round(se, 4),
            "ci_low": round(d - 1.96 * se, 4), "ci_high": round(d + 1.96 * se, 4),
            "significant": abs(d) > 1.96 * se}



def _summary_items(fn):
    """{(model, lang): (pass, n)} from a MultiPL-E summary file."""
    import os
    out = {}
    path = os.path.join(".wrapup", fn)
    if not os.path.exists(path):
        return out
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("n"):
            out[(r.get("model"), r.get("lang"))] = (r.get("pass", 0), r["n"])
    return out


# Comparisons the level ladder cannot express: two checkpoints at the SAME file
# size but a different quantisation scheme (M23) or provider (M25).  Reported as
# (first - second), item-level CI via ci_items.
MATCHED_SIZE_SPECS = [
    ("M23 4B IQ3_XXS vs Q2_K_XL (1.949 vs 1.941 GB, +0.4%)",
     "m23_summary.jsonl", "iq3-4b", "m1_summary.jsonl", "qwen4b-q2", "m23-scheme-iqk"),
    ("M23 2B IQ3_XXS vs Q2_K_XL (0.932 vs 0.967 GB, -3.6%)",
     "m23_summary.jsonl", "iq3-2b", "m3_summary.jsonl", "q2", "m23-scheme-iqk"),
    ("M25 Qwen3.6-35B-A3B bartowski Q3_K_M vs unsloth UD-Q3_K_XL (17.118 vs 17.228 GB, -0.6%)",
     "m25_summary.jsonl", "q36-35b-bartq3", "m6_summary.jsonl", "q36-35b-q3", "m25-vendor"),
]


def matched_size_contrasts():
    srcs = {fn: _summary_items(fn) for fn in
            {"m1_summary.jsonl", "m3_summary.jsonl", "m6_summary.jsonl",
             "m23_summary.jsonl", "m25_summary.jsonl"}}
    out = {}
    for label, fa, ta, fb, tb, run_tag in MATCHED_SIZE_SPECS:
        langs = sorted({l for (t, l) in srcs[fa] if t == ta} &
                       {l for (t, l) in srcs[fb] if t == tb})
        if not langs:
            continue
        per = {}
        for lang in langs:
            pa, na = srcs[fa][(ta, lang)]
            pb, nb = srcs[fb][(tb, lang)]
            it = ci_items(pa, na, pb, nb)
            if it:
                per[lang] = dict(it, a=round(pa / na, 4), b=round(pb / nb, 4),
                                 mean=round(-it["mean"], 4),
                                 ci_low=round(-it["ci_high"], 4),
                                 ci_high=round(-it["ci_low"], 4))
        pa = sum(srcs[fa][(ta, l)][0] for l in langs)
        na = sum(srcs[fa][(ta, l)][1] for l in langs)
        pb = sum(srcs[fb][(tb, l)][0] for l in langs)
        nb = sum(srcs[fb][(tb, l)][1] for l in langs)
        pooled = ci_items(pa, na, pb, nb)
        if pooled:
            pooled = dict(pooled, mean=round(-pooled["mean"], 4),
                          ci_low=round(-pooled["ci_high"], 4),
                          ci_high=round(-pooled["ci_low"], 4))
        out[label] = {"run_tag": run_tag, "langs": langs,
                      "per_language": per, "pooled": pooled}
    return out


def _model_maps():
    """tag -> model file, merged from the migrate_db maps."""
    maps = {}
    try:
        import migrate_db as M
        for name in dir(M):
            if name.endswith("_MODELS") and isinstance(getattr(M, name), dict):
                maps.update(getattr(M, name))
    except Exception as e:
        print("warn: could not import maps:", e)
    return maps


def load_items():
    """{(base_model, quant, lang): (pass, n)} from the per-run summary files."""
    import os
    maps = _model_maps()
    out = {}
    for fn in ("m1_summary.jsonl", "m2_summary.jsonl", "m3_summary.jsonl",
               "m5_summary.jsonl", "m6_summary.jsonl", "m10_summary.jsonl",
               "m10_granite_summary.jsonl"):
        path = os.path.join(".wrapup", fn)
        if not os.path.exists(path):
            continue
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            f = maps.get(r.get("model"))
            if not f or r.get("n") in (None, 0):
                continue
            out[(base_of(f), r.get("quant") or _quant_of(f), r.get("lang"))] = (
                r.get("pass", 0), r["n"])
    return out


def _quant_of(fname):
    m = QUANT_RE.search(fname)
    return m.group(1) if m else None

def base_of(model):
    return QUANT_RE.sub("", model).rstrip("-.")


def level_of(quant):
    m = LEVEL_RE.search(quant or "")
    return int(m.group(1)) if m else None


def load():
    con = sqlite3.connect(DB, uri=True)
    # The frozen greedy ladder is a single protocol.  Sampling experiments (m27)
    # carry `multipl-e-raw-t<temp>-768` and MUST NOT be averaged into a ladder
    # cell (SSOT: never mix protocols in one comparison); the temp=0.0 anchor
    # keeps the greedy string and therefore agrees with m3 where they overlap.
    q = """SELECT model, __quant, language, _score, run_tag FROM experiments
           WHERE bench_family='humaneval-multipl-e' AND _score IS NOT NULL
             AND protocol='multipl-e-raw-greedy-768'"""
    return [dict(zip([d[0] for d in con.execute(q).description], r))
            for r in con.execute(q)]


def main():
    global ITEMS
    ITEMS = load_items()
    rows = load()
    if not rows:
        print("no MultiPL-E rows")
        return

    grid = defaultdict(list)      # (base, quant, lang) -> scores
    for r in rows:
        lv = level_of(r["__quant"])
        if lv is None:
            continue
        grid[(base_of(r["model"]), r["__quant"], r["language"])].append(r["_score"])

    fams = sorted({k[0] for k in grid})
    out = {"n_rows": len(rows), "families": {}, "per_language": {}}

    # per-family ladder over exact quant strings, ordered by (level, name)
    steps = defaultdict(dict)
    for fam in fams:
        quants = sorted({q for (b, q, _) in grid if b == fam},
                        key=lambda q: (level_of(q), q))
        cells = {}
        for (b, q, lang), v in grid.items():
            if b == fam:
                cells.setdefault(q, {})[lang] = sum(v) / len(v)
        pooled = {q: round(sum(cells[q].values()) / len(cells[q]), 4) for q in quants}
        out["families"][fam] = {"levels": pooled, "per_language": cells,
                                "order": quants}
        # A sub-3-bit scheme anchor (e.g. IQ3_XXS) is a file-size-matched
        # ALTERNATIVE to a level, not a rung of the K-quant ladder: shown in the
        # table, but kept out of the level->level step chain so Q2_K_XL still
        # pairs with Q3_K_XL rather than with the alphabetically-earlier IQ3_XXS.
        step_order = [q for q in quants if "XXS" not in q.upper()]
        for a, b in zip(step_order, step_order[1:]):
            if level_of(b) <= level_of(a):
                continue
            langs = set(cells[a]) & set(cells[b])
            d = [cells[b][l] - cells[a][l] for l in langs]
            if not d:
                continue
            pa = sum(ITEMS.get((fam, a, l), (0, 0))[0] for l in langs)
            na = sum(ITEMS.get((fam, a, l), (0, 0))[1] for l in langs)
            pb = sum(ITEMS.get((fam, b, l), (0, 0))[0] for l in langs)
            nb = sum(ITEMS.get((fam, b, l), (0, 0))[1] for l in langs)
            entry = ci95(d) or {}
            it = ci_items(pa, na, pb, nb)
            if it:
                entry = dict(entry or {})
                entry.update(it)
                entry["n_langs"] = len(langs)
            steps[fam][f"{a}->{b}"] = entry
    out["steps"] = {k: v for k, v in steps.items()}

    # cross-family Q2->Q3 (any step crossing level 2 -> level 3)
    q23 = {}
    for fam, st in steps.items():
        for k, v in st.items():
            a, b = k.split("->")
            if level_of(a) == 2 and level_of(b) == 3:
                q23[fam] = v
    out["Q2_Q3_by_family"] = q23
    alllangs = [v["mean"] for v in q23.values() if v]
    if alllangs:
        out["Q2_Q3_family_summary"] = {
            "n_families": len(alllangs),
            "min": round(min(alllangs), 4),
            "max": round(max(alllangs), 4),
            "mean": round(sum(alllangs) / len(alllangs), 4),
            "all_positive": all(x > 0 for x in alllangs),
        }

    # ---- matched-size scheme / vendor contrasts ----
    out["matched_size"] = matched_size_contrasts()

    with open("multipl_e.json", "w") as f:
        json.dump(out, f, indent=1)

    # ---- markdown ----
    L = ["# MultiPL-E across families\n",
         "_Auto-generated by `multipl_e_analysis.py`._\n",
         f"Rows: **{len(rows)}** across {len(fams)} model anchors "
         f"({len({f.split('-')[0] for f in fams})} architecture families).\n"]
    for fam in fams:
        L.append(f"### {fam}\n")
        info = out["families"][fam]
        quants = info["order"]
        allangs = sorted({l for q in quants for l in info["per_language"][q]})
        L.append("| quant | " + " | ".join(allangs) + " | pooled |")
        L.append("|---|" + "---|" * (len(allangs) + 1))
        for q in quants:
            L.append(f"| {q} | " + " | ".join(
                str(round(info["per_language"][q].get(l, float('nan')), 3))
                for l in allangs) + f" | {info['levels'][q]} |")
        L.append("")
        for k, v in out["steps"].get(fam, {}).items():
            if v:
                L.append(f"- `{k}`: **{v['mean']:+.4f}** "
                         f"95% CI [{v['ci_low']:+.4f}, {v['ci_high']:+.4f}] (n={v['n']} langs)")
        L.append("")
    if alllangs:
        s = out["Q2_Q3_family_summary"]
        L.append("## Cross-family Q2->Q3\n")
        L.append("| family | mean Δ | 95% CI |")
        L.append("|---|---|---|")
        for f, v in sorted(q23.items()):
            if v:
                L.append(f"| {f} | {v['mean']:+.4f} | [{v['ci_low']:+.4f}, {v['ci_high']:+.4f}] |")
        L.append("")
        L.append(f"**{s['n_families']} model anchors, all sign-consistent "
                 f"({s['all_positive']}), range {s['min']:+.3f} .. {s['max']:+.3f}, "
                 f"mean {s['mean']:+.3f}.**\n")
    if out.get("matched_size"):
        L.append("## Size-matched scheme / vendor contrasts\n")
        L.append("_Δ = first − second; item-level 95% CI via `ci_items`. "
                 "Both sides sit at the same file size, so the ladder cannot "
                 "express this contrast._\n")
        L.append("| contrast | lang | first | second | Δ | 95% CI | sig |")
        L.append("|---|---|---|---|---|---|---|")
        for label, d in out["matched_size"].items():
            for l in d["langs"]:
                e = d["per_language"].get(l)
                if not e:
                    continue
                L.append(f"| {label} | {l} | {e['a']:.4f} | {e['b']:.4f} | "
                         f"{e['mean']:+.4f} | [{e['ci_low']:+.4f}, {e['ci_high']:+.4f}] | "
                         f"{'yes' if e['significant'] else 'no'} |")
            p = d["pooled"]
            if p:
                L.append(f"| {label} | pooled | | | {p['mean']:+.4f} | "
                         f"[{p['ci_low']:+.4f}, {p['ci_high']:+.4f}] | "
                         f"{'yes' if p['significant'] else 'no'} |")
        L.append("")
    with open("MULTIPLE.md", "w") as f:
        f.write("\n".join(L) + "\n")

    print(json.dumps(out.get("Q2_Q3_family_summary", {}), indent=1))
    print("matched-size:", json.dumps(out.get("matched_size", {}), indent=1)[:1200])
    print("steps:", json.dumps({k: {kk: vv for kk, vv in v.items()} for k, v in out["steps"].items()},
                               indent=1)[:1200])
    print("wrote multipl_e.json + MULTIPLE.md")


if __name__ == "__main__":
    main()
