#!/usr/bin/env python3
"""i01 WP7 — the repeatability floor: same cell, same inputs, run twice.

The number this produces is NOT plan15's +/-16/161.  plan15's difference came from an
input change (a different prompt set / a different postprocess version), which
RESULT.md::res29 records separately.  This one is what repeats of an identical cell
do, i.e. the smallest difference that carries no information.

Four harness families, each read from artefacts on disk so the number is one command:

  MultiPL-E chat   i01-slot-np1-p{1,2} and i01-slot-npauto-p{1,2}  (2 repeats x 2 configs)
  EvalPlus chat    wres/humaneval/w1-2bq4-r{1,2,3} at temp 0      (3 repeats)
  lm-eval gsm8k    .wrapup/mres/i01-floor/gsm8k-r{1,2} samples    (2 repeats, --log_samples)
  BFCL single-turn .wrapup/mres/i01-floor/bfcl-r{1,2} predicted calls (2 repeats)

For each family it reports: identical problems, upward flips, downward flips, the
largest score swing, and the per-problem agreement (Jaccard over the pass sets).
A family whose artefacts are missing is reported as unmeasured, never as zero.

Run from the repository root:

    python3 "docs/subprojects/i01-判分与基准有效性/audits/noise_floor_compare.py"
"""
from __future__ import annotations

import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
MRES = os.path.join(REPO, ".wrapup", "mres")
FLOOR = os.path.join(MRES, "i01-floor")
MISSING = []


def load_eval_pass(path):
    """{problem: passed} from an mpl_run-style _eval.json."""
    d = json.load(open(path))
    return {x["name"]: x["pass"] for x in d["details"]}, d["pass"], d["n"]


def compare(name, a, b, na, nb):
    keys = sorted(set(a) | set(b))
    same = sum(1 for k in keys if a.get(k) == b.get(k))
    up = sum(1 for k in keys if b.get(k) and not a.get(k))
    down = sum(1 for k in keys if a.get(k) and not b.get(k))
    pa, pb = {k for k in a if a[k]}, {k for k in b if b[k]}
    jac = len(pa & pb) / len(pa | pb) if (pa | pb) else 1.0
    print("  %-28s n=%d identical=%d up=%d down=%d  score=%d/%d vs %d/%d (swing %.4f)  jaccard=%.4f"
          % (name, len(keys), same, up, down, na, len(keys), nb, len(keys),
             abs(na - nb) / max(len(keys), 1), jac))
    return {"name": name, "n": len(keys), "identical": same, "up": up, "down": down,
            "swing": abs(na - nb) / max(len(keys), 1), "jaccard": round(jac, 4)}


def multipl_e():
    print("\n[MultiPL-E chat, q38-27b-q3 py, greedy]")
    rows = []
    for a, b in (("np1-p1", "np1-p2"), ("npauto-p1", "npauto-p2")):
        pa = os.path.join(MRES, "i01-slot-%s-py-chat_eval.json" % a)
        pb = os.path.join(MRES, "i01-slot-%s-py-chat_eval.json" % b)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            print("  UNMEASURED: %s / %s missing" % (a, b)); MISSING.append("multipl-e " + a); continue
        xa, na, _ = load_eval_pass(pa); xb, nb, _ = load_eval_pass(pb)
        rows.append(compare("%s vs %s" % (a, b), xa, xb, na, nb))
    return rows


def evalplus():
    print("\n[EvalPlus chat, 2b q4 humaneval, temp 0]")
    paths = [os.path.join(REPO, ".wrapup", "wres", "humaneval",
                          "w1-2bq4-r%d_openai_temp_0.0_eval_results.json" % r) for r in (1, 2, 3)]
    if not all(os.path.exists(p) for p in paths):
        print("  UNMEASURED: the w1-repeat temp=0 files are missing")
        MISSING.append("evalplus")
        return []
    sets = []
    for p in paths:
        d = json.load(open(p))["eval"]
        sets.append({t: all(r.get("plus_status") == "pass" for r in v) for t, v in d.items()})
    rows = []
    for i in (1, 2):
        na = sum(sets[0].values()); nb = sum(sets[i].values())
        rows.append(compare("rep1 vs rep%d" % (i + 1), sets[0], sets[i], na, nb))
    return rows


def lm_eval_gsm8k():
    print("\n[lm-eval gsm8k chat reasoning-off --limit 100, greedy]")
    paths = []
    for r in (1, 2):
        hits = glob.glob(os.path.join(FLOOR, "gsm8k-r%d" % r, "**", "samples_gsm8k_*.jsonl"), recursive=True)
        if not hits:
            print("  UNMEASURED: no samples file for rep%d" % r); MISSING.append("lm-eval r%d" % r); return []
        paths.append(hits[0])
    per = []
    for p in paths:
        rows = [json.loads(l) for l in open(p) if l.strip()]
        # with two filters the samples carry both; key on the filter name
        out = {}
        for row in rows:
            did = row.get("doc_id", row.get("id"))
            ex = row.get("exact_match") or {}
            flexible = ex.get("flexible-extract") if isinstance(ex, dict) else ex
            out[did] = bool(flexible) if not isinstance(flexible, list) else bool(flexible[0])
        per.append(out)
    print("  samples files: %s" % ", ".join(os.path.relpath(p, REPO) for p in paths))
    return [compare("rep1 vs rep2", per[0], per[1], sum(per[0].values()), sum(per[1].values()))]


def bfcl():
    print("\n[BFCL single-turn simple_python, native tools, --limit 40]")
    paths = [os.path.join(FLOOR, "bfcl-r%d.jsonl" % r) for r in (1, 2)]
    evals = [os.path.join(FLOOR, "bfcl-r%d-eval.json" % r) for r in (1, 2)]
    if not all(os.path.exists(p) for p in paths + evals):
        print("  UNMEASURED: bfcl repeat artefacts missing"); MISSING.append("bfcl"); return []
    calls = []
    for p in paths:
        calls.append({r["id"]: json.dumps(r.get("calls"), sort_keys=True) for r in
                      (json.loads(l) for l in open(p) if l.strip())})
    scores = [json.load(open(e))["correct"] for e in evals]
    n = len(calls[0])
    diff = sum(1 for k in calls[0] if calls[0].get(k) != calls[1].get(k))
    print("  items whose predicted calls differ: %d/%d" % (diff, n))
    print("  correct: rep1=%d rep2=%d (n=%d)" % (scores[0], scores[1], n))
    # same predicted calls => same verdict, so the verdict flip count is bounded by `diff`
    print("  verdict flips are 0 when the predicted calls are identical for every item")
    return [{"name": "run1 vs run2", "n": n, "identical": (n - diff), "up": None, "down": None,
             "swing": abs(scores[0] - scores[1]) / max(n, 1), "jaccard": None, "calls_differ": diff}]


def main() -> int:
    multipl_e()
    evalplus()
    lm_eval_gsm8k()
    bfcl()
    print("\nSUMMARY")
    print("  the floor is the largest swing above for a cell whose INPUTS are identical;")
    print("  plan15's +/-16/161 (RESULT.md::res29) is an input difference, not part of it.")
    if MISSING:
        print("  unmeasured: %s" % ", ".join(sorted(set(MISSING))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
