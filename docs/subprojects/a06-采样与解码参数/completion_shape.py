#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a06: the shape of one cell's completions, under an explicit tokenisation.

Why this file exists: an earlier version of `RESULT.md` reported three shape
statistics (`cpp_kw_share`, `types/tokens`, mean length) with no script and no
repro, and a reviewer could not reproduce two of them under any of three
tokenisations.  A number nobody can recompute is not evidence.  So the definition
lives here, once, and the numbers come from running this.

Two measures are stable enough to quote:

  * `mean_words` -- whitespace split.  Exact, tokeniser-independent, reproducible.
  * the status histogram -- from the `_eval.json`, not from the text.

Two are NOT stable, because they depend on how the text is split
(`[A-Za-z_]\\w*` vs `\\w+` vs the model's own vocabulary all give different
answers), so they are printed with their tokenisation and must be quoted as
DIRECTION, never as a number:

  * `types/tokens` -- distinct / total tokens inside each completion;
  * `cpp_kw_share` -- C++ keyword hits / words.

Run from the repository root:

    python3 "docs/subprojects/a06-采样与解码参数/completion_shape.py"

Exit status: 0 when every requested product was readable; 2 when one is missing
(a shape table over half the products is not a shape table).
"""
from __future__ import annotations

import json
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
WR = os.path.join(ROOT, ".wrapup", "mres")

# label -> product holding `{"completion": ...}` lines
CELLS = [
    ("greedy anchor (m31 tk1)", "m31-q3-tk1-cpp.jsonl"),
    ("temp 0.3 (m27)", "m27-q3-t0.3-cpp.jsonl"),
    ("temp 0.6 (m27)", "m27-q3-t0.6-cpp.jsonl"),
    ("vendor R1 (pp=2.0)", "m165-vendor/mpl-q3-cpp-vendor.jsonl"),
    ("M1 probe 40 (pp=0)", "m165-mechanism/m1-q3-cpp-pp0-probe40.jsonl"),
    ("M2 probe 40 (truncated)", "m165-mechanism/m2-q3-cpp-probe40.jsonl"),
    ("M2 full 161 (temp 1.0)", "m165-mechanism/m2full-q3-cpp-probe161.jsonl"),
]

TOKEN = re.compile(r"[A-Za-z_]\w*|[{}();\[\]<>=+\-*/&|!]")
CPP_KW = re.compile(r"\b(return|if|else|for|while|int|void|auto|const|std|vector|"
                    r"string|size_t|struct|class|template|typename|nullptr|true|"
                    r"false|char|bool|double|float|long|unsigned)\b")


def main(argv):
    missing, rows = [], []
    for label, rel in CELLS:
        path = os.path.join(WR, rel)
        if not os.path.exists(path):
            missing.append(path)
            continue
        comps = [json.loads(line).get("completion", "") for line in open(path)]
        words = [len(c.split()) for c in comps]
        ttr, kw = [], []
        for c in comps:
            toks = TOKEN.findall(c)
            if len(toks) >= 8:
                ttr.append(len(set(toks)) / len(toks))
            w = c.split()
            if w:
                kw.append(len(CPP_KW.findall(c)) / len(w))
        rows.append((label, len(comps), st.mean(words), st.median(words),
                     st.mean(ttr) if ttr else float("nan"),
                     st.mean(kw) if kw else float("nan")))
    if missing:
        print("UNMEASURED: missing product(s):", file=sys.stderr)
        for m in missing:
            print(f"  {os.path.relpath(m, ROOT)}", file=sys.stderr)
        return 2

    print(f"{'cell':<28}{'n':>4}{'mean_words':>12}{'median':>8}"
          f"{'types/tokens*':>15}{'cpp_kw*':>9}")
    for label, n, mw, md, ttr, kw in rows:
        print(f"{label:<28}{n:>4}{mw:>12.1f}{md:>8.1f}{ttr:>15.3f}{kw:>9.3f}")
    print("\nmean_words: whitespace split -- exact and reproducible, quote as a number.")
    print("types/tokens*, cpp_kw*: tokenisation-dependent (this script uses the regex")
    print("  above).  Compare rows for DIRECTION only; do not quote these two as values.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
