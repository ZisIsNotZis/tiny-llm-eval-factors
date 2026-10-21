#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a06 per-item verdict movement between the fixed protocol and a sampled one.

Run from the repository root:

    python3 "docs/subprojects/a06-采样与解码参数/peritem_moves.py"

Read-only.  It reads the MultiPL-E per-item products
`.wrapup/mres/m27-*_eval.json` and `.wrapup/mres/m31-*_eval.json` and, for every
(quantisation level, language), compares the greedy anchor against each
temperature / top_k setting item by item: how many tasks flipped up, how many
flipped down, what the net score move is, and the Jaccard overlap of the two
pass sets.

Why this file exists: a score move of a few items can hide a much larger
reshuffle.  i01 measured that on repeated identical temp=0.3 runs (per-item
Jaccard 0.53-0.67, 8-15 up / 6-12 down flips, net score move 6/164).  This script
puts each protocol change on the same pair of scales so the two are comparable.

Exit status: 0 when every required product was readable and the comparison ran;
2 when a required product is missing (a comparison that cannot see its inputs
must not exit 0).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
MRES = os.path.join(ROOT, ".wrapup", "mres")

# i01's repeat floor, for the "is this move separable from repeat noise" column.
# i01's res node: five repeats of one temp=0.3 cell gave per-item Jaccard
# 0.53-0.67, 8-15 up / 6-12 down flips, and a NET score move of at most 6 of 164.
FLOOR_NET = 6

LEVELS = ["q2", "q3", "q4"]
LANGS = ["cpp", "py"]

# anchor (greedy) -> the settings compared against it, as (label, kind)
ANCHORS = {}
for lv in LEVELS:
    ANCHORS[lv] = f"m31-{lv}-tk1"          # top_k=1 at temp 0.3 == argmax == greedy
ANCHORS["q2"] = "m27-q2-t0.0"              # a true temp=0 run exists for Q2; prefer it

SETTINGS = []
for lv in LEVELS:
    SETTINGS.append((lv, "m27-%s-t0.3" % lv, "temp 0.3"))
    SETTINGS.append((lv, "m27-%s-t0.6" % lv, "temp 0.6"))
    for tk in ("20", "40", "64", "200"):
        SETTINGS.append((lv, "m31-%s-tk%s" % (lv, tk), "top_k %s @ temp 0.3" % tk))

MISSING = []


def load(stem, lang):
    path = os.path.join(MRES, f"{stem}-{lang}_eval.json")
    if not os.path.exists(path):
        MISSING.append(path)
        return None
    d = json.load(open(path))
    return {x["name"]: bool(x["pass"]) for x in d["details"]}, d


def head(argv):
    rev = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    print(f"# command : python3 {os.path.relpath(os.path.abspath(__file__), ROOT)}"
          f" {' '.join(argv)}")
    print(f"# git HEAD: {rev}")
    print(f"# floor   : i01 five-repeat temp=0.3 net score move <= {FLOOR_NET} of 164")
    print()


def main(argv):
    head(list(argv))
    print(f"{'level':<6}{'lang':<5}{'setting':<22}{'n':>5}{'pass(g)':>8}{'pass(s)':>8}"
          f"{'delta':>7}{'up':>5}{'down':>6}{'net':>5}{'jacc':>7}  separable")
    for lv in LEVELS:
        anchor = ANCHORS[lv]
        for lang in LANGS:
            a = load(anchor, lang)
            if a is None:
                continue
            a_pass, a_doc = a
            for slv, stem, label in SETTINGS:
                if slv != lv:
                    continue
                s = load(stem, lang)
                if s is None:
                    continue
                s_pass, s_doc = s
                names = sorted(set(a_pass) | set(s_pass))
                up = sum(1 for n in names if s_pass.get(n) and not a_pass.get(n))
                down = sum(1 for n in names if a_pass.get(n) and not s_pass.get(n))
                ap = sum(a_pass.values())
                sp = sum(s_pass.values())
                inter = sum(1 for n in names if a_pass.get(n) and s_pass.get(n))
                union = sum(1 for n in names if a_pass.get(n) or s_pass.get(n))
                jacc = inter / union if union else float("nan")
                net = abs(sp - ap)
                verdict = ("NO, |net|<=floor" if net <= FLOOR_NET
                           else "yes, |net|>floor")
                print(f"{lv:<6}{lang:<5}{label:<22}{a_doc['n']:>5}{ap:>8}{sp:>8}"
                      f"{sp - ap:>+7}{up:>5}{down:>6}{sp - ap:>+5}{jacc:>7.2f}  {verdict}")
    if MISSING:
        print("\nUNMEASURED: missing per-item product(s):", file=sys.stderr)
        for m in MISSING:
            print(f"  {m}", file=sys.stderr)
        return 2
    print("\n# up   = fail under the anchor, pass under the setting")
    print("# down = pass under the anchor, fail under the setting")
    print("# net  = score move in items (signed); 'separable' compares |net| with"
          f" i01's repeat floor of {FLOOR_NET}/164")
    print("# jacc = |pass(g) and pass(s)| / |pass(g) or pass(s)|")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
