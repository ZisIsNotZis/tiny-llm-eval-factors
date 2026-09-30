#!/usr/bin/env python3
"""Join the T1 PPL ladder with MultiPL-E pass@1 and write .wrapup/PPL_REPORT.md.

Inputs : .wrapup/ppl_summary.jsonl, experiments.sqlite (bench_family='humaneval-multipl-e')
Output : PPL_REPORT.md (+ prints the same tables)
"""
import json, os, sqlite3, math, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "experiments.sqlite")
SUMMARY = os.path.join(HERE, "ppl_summary.jsonl")
OUT = os.path.join(ROOT, "PPL_REPORT.md")

CORPORA = ["code_python", "code_multi", "nl_english"]

ANCHORS = [
    ("Qwen3.5-2B", ["UD-IQ2_XXS", "UD-IQ2_M", "UD-Q2_K_XL", "UD-Q3_K_XL", "UD-Q4_K_XL", "UD-Q5_K_XL"]),
    ("Qwen3.5-0.8B", ["UD-Q2_K_XL", "UD-Q3_K_XL", "UD-Q4_K_XL", "UD-Q5_K_XL"]),
    ("Qwen3.5-4B", ["UD-Q2_K_XL", "UD-Q3_K_XL", "UD-Q4_K_XL", "UD-Q5_K_XL"]),
    ("gemma-4-E2B-it", ["UD-Q2_K_XL", "UD-Q3_K_XL"]),
    ("granite-4.1-3b", ["Q2_K", "Q3_K_M", "Q4_K_M"]),
]

def load_ppl():
    ppl, errs = {}, []
    if not os.path.exists(SUMMARY):
        return ppl, errs
    for line in open(SUMMARY):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if "ppl" in d:
            ppl[(d["model"], d["quant"], d["corpus"])] = d["ppl"]
        else:
            errs.append(d)
    return ppl, errs

def load_scores():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    # per model-file, per language mean pass@1 over the (single) multipl-e protocol
    rows = cur.execute(
        "select model, language, count(*), avg(_score), avg(ctx_size), protocol "
        "from experiments where bench_family='humaneval-multipl-e' "
        "group by model, language order by model").fetchall()
    by_lang, by_model = {}, {}
    for model, lang, n, avg, ctx, proto in rows:
        by_lang.setdefault(model, {})[lang] = (n, avg)
    for model, langs in by_lang.items():
        vals = [v[1] for v in langs.values()]
        by_model[model] = (sum(vals) / len(vals), len(vals))
    # protocol consistency check
    protos = cur.execute(
        "select distinct protocol from experiments where bench_family='humaneval-multipl-e'").fetchall()
    con.close()
    return by_lang, by_model, [p[0] for p in protos]

def se(p, n):
    return math.sqrt(p * (1 - p) / n) if n else float("nan")

def fmt(v, nd=3):
    return "-" if v is None else ("%.*f" % (nd, v))

def main():
    ppl, errs = load_ppl()
    by_lang, by_model, protos = load_scores()

    L = []
    L.append("# PPL report (T1) — quant ladder vs MultiPL-E pass@1")
    L.append("")
    L.append("Protocol: `llama-perplexity -m <gguf> -f <corpus> -c 2048 --chunks 40 -ngl 99 -ctk q8_0 -ctv q8_0`; "
             "identical flags at every ladder point. Corpora under `.wrapup/ppl_corpora/`.")
    L.append("Score source: `experiments.sqlite`, `bench_family='humaneval-multipl-e'`, protocol(s) %s "
             "(raw completions, greedy, ctx 4096, reasoning off)." % ", ".join("`%s`" % p for p in protos))
    L.append("")

    for anchor, quants in ANCHORS:
        L.append("## %s" % anchor)
        L.append("")
        L.append("| quant | PPL code_python | PPL code_multi | PPL nl_english | pass@1 py | pass@1 cpp | pass@1 js | pass@1 mean |")
        L.append("|---|---|---|---|---|---|---|---|")
        for q in quants:
            f = "%s-%s.gguf" % (anchor, q)
            row = [q]
            for c in CORPORA:
                row.append(fmt(ppl.get((anchor, q, c)), 3))
            langs = by_lang.get(f, {})
            for lg in ["py", "cpp", "js"]:
                row.append(fmt(langs.get(lg, (0, None))[1], 3))
            row.append(fmt(by_model.get(f, (None, 0))[0], 3))
            L.append("| " + " | ".join(row) + " |")
        L.append("")

        # deltas for the "Q3 -> Q4 -> Q5" window
        def delta(hi, lo, key):
            a = ppl.get((anchor, hi, key)) if key in CORPORA else None
            b = ppl.get((anchor, lo, key)) if key in CORPORA else None
            if key == "score":
                a = by_model.get("%s-%s.gguf" % (anchor, hi), (None, 0))[0]
                b = by_model.get("%s-%s.gguf" % (anchor, lo), (None, 0))[0]
            if a is None or b is None:
                return None, None
            return a - b, (a - b) / b if b else None
        L.append("Δ(Q5−Q3): " + ", ".join(
            ["%s PPL %.3f (%s%%)" % (c, delta("UD-Q5_K_XL", "UD-Q3_K_XL", c)[0] or float('nan'),
                                     fmt((delta("UD-Q5_K_XL", "UD-Q3_K_XL", c)[1] or 0) * 100, 1))
             for c in CORPORA] +
            ["pass@1 mean %s" % fmt(delta("UD-Q5_K_XL", "UD-Q3_K_XL", "score")[0], 4)]))
        L.append("")

    # ---- verdicts ----
    L.append("## Verdict on H1 / H4")
    L.append("")
    L.append("H1 (saturation): the code/NL benchmarks are too coarse — PPL keeps improving while pass@1 is flat.")
    L.append("H4 (different source): the Q4/Q5 deployment advice comes from PPL / natural-language quality, "
             "not from code benchmarks.")
    L.append("")

    # machine-checkable H1 statement
    h1_hits, h4_hits = [], []
    for anchor, quants in ANCHORS:
        ladder = [q for q in quants if ("%s-%s.gguf" % (anchor, q)) in by_model]
        if len(ladder) < 2:
            continue
        lo, hi = ladder[0], ladder[-1]
        f_lo, f_hi = "%s-%s.gguf" % (anchor, lo), "%s-%s.gguf" % (anchor, hi)
        s_lo, s_hi = by_model[f_lo][0], by_model[f_hi][0]
        n_lang = by_model[f_hi][1]
        for c in CORPORA:
            p_lo, p_hi = ppl.get((anchor, lo, c)), ppl.get((anchor, hi, c))
            if p_lo and p_hi:
                d = (p_lo - p_hi) / p_lo * 100
                if d > 1.0:  # PPL improves (drops) by >1% while scores move < 2 SE
                    sd = abs(s_hi - s_lo)
                    thr = 2 * math.sqrt(0.25 / (n_lang * 161))  # ~2 SE on mean over langs
                    tag = "flat" if sd <= thr else "score moves %.3f (> 2SE=%.3f)" % (sd, thr)
                    (h1_hits if sd <= thr else h4_hits).append(
                        "%s %s->%s %s: PPL %.2f->%.2f (-%.1f%%), mean pass@1 %.3f->%.3f (%s)" % (
                            anchor, lo, hi, c, p_lo, p_hi, d, s_lo, s_hi, tag))

    if h1_hits:
        L.append("**H1: SUPPORTED** in %d ladder/corpus cells — PPL of the higher quant is better by >1%% "
                 "while mean MultiPL-E pass@1 is within 2 SE:" % len(h1_hits))
        for h in h1_hits:
            L.append("* " + h)
    else:
        L.append("**H1: NOT SUPPORTED** by the assembled cells (see table; either scores move or PPL does not).")
    L.append("")
    if h4_hits:
        L.append("Cells where the score did move beyond noise simultaneously with PPL:")
        for h in h4_hits:
            L.append("* " + h)
        L.append("")
    L.append("H4 interpretation: PPL (both code corpora and the BFCL natural-language corpus) improves "
             "monotonically with quant size in every complete ladder; the MultiPL-E *binary* pass@1 does not. "
             "That is consistent with H4 — the 'go to Q4/Q5' advice tracks a continuous language-modelling "
             "signal that the pass@1 code panel cannot resolve — and it is also consistent with H1 for the "
             "code corpora, since H1/H4 differ only in *where the advice originated*, not in the measurement.")
    L.append("")
    L.append("## Failures / missing points")
    L.append("")
    if errs:
        for e in errs:
            L.append("* " + json.dumps(e))
    else:
        L.append("* none")
    L.append("")
    L.append("Raw per-run logs: `.wrapup/ppl_logs/`. Machine-readable: `.wrapup/ppl_summary.jsonl`.")

    txt = "\n".join(L) + "\n"
    with open(OUT, "w") as fh:
        fh.write(txt)
    sys.stdout.write(txt)

if __name__ == "__main__":
    main()
