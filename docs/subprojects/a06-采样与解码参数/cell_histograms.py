#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a06 vendor arm: the status histogram of every MultiPL-E cell.

Why a histogram and not just a score: a cell can fall from 0.1118 to 0.0062 either
because the model got worse at the same task or because its output stopped being
parseable at all.  Those are different findings and only the status distribution
tells them apart.  A cell whose pass count sits under a `SyntaxError`/`Exception`
floor is not a capability reading and must not be compared to a cell that is above
its floor (the a12 rule).

Writes `.wrapup/mres/m165-vendor/histograms.jsonl`, one line per cell, and prints
the same table.  Re-runnable while the arm is still running: it only reads the
`*_eval.json` products that exist.

Run from the repository root (defaults to the vendor arm directory; pass --dir for
another product directory, e.g. the M1 mechanism probe):

    python3 "docs/subprojects/a06-采样与解码参数/cell_histograms.py"
    python3 "docs/subprojects/a06-采样与解码参数/cell_histograms.py" --dir .wrapup/mres/m165-mechanism

Exit status: 0 when at least one cell was read; 2 when the product directory or
every `*_eval.json` is missing (a histogram of nothing must not exit 0).
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, ".wrapup", "mres", "m165-vendor")
DEST = os.path.join(OUT, "histograms.jsonl")

# A cell is "at its floor" when fewer than this share of items pass.  0.05 is NOT a
# universal threshold; it is derived from this ladder's own numbers: the lowest
# greedy cell here is Q2 cpp 18/161 = 0.1118, and the collapsed cells measured so
# far are 1/161 = 0.0062 and 3/161 = 0.0186, so 0.05 sits between them with more than
# 2x margin to either side.  Another ladder or benchmark needs its own figure.
# The flag is a coarse separator, not the verdict: when the score lands near it but
# `status_histogram` shows a different failure mechanism (Timeout-dominated, or a
# high OK share), the histogram wins and the cell is described by its mechanism.
FLOOR_SHARE = 0.05


def main(argv):
    global OUT, DEST
    if argv and argv[0] in ("--dir",):
        OUT = os.path.join(ROOT, argv[1]) if not os.path.isabs(argv[1]) else argv[1]
        DEST = os.path.join(OUT, "histograms.jsonl")
    if not os.path.isdir(OUT):
        print(f"UNMEASURED: no product directory {OUT}", file=sys.stderr)
        return 2
    evals = sorted(glob.glob(os.path.join(OUT, "*_eval.json")))
    if not evals:
        print(f"UNMEASURED: no *_eval.json under {OUT}", file=sys.stderr)
        return 2

    rows, printed = [], []
    for path in evals:
        d = json.load(open(path))
        details = d.get("details") or []
        hist = collections.Counter(x.get("status") for x in details)
        n = d.get("n") or len(details)
        passed = d.get("pass", hist.get("OK", 0))
        floor = hist.get("SyntaxError", 0) + hist.get("Exception", 0)
        share = passed / n if n else None
        collapsed = share is not None and share < FLOOR_SHARE
        rec = {
            "cell": os.path.basename(path).replace("_eval.json", ""),
            "n": n, "pass": passed, "score": d.get("score"),
            "status_histogram": dict(hist),
            "unparseable_share": round(floor / n, 4) if n else None,
            "at_floor": collapsed,
            "verdict": ("collapsed: below the syntax floor, not a capability reading"
                        if collapsed else
                        "above the floor: the score is a capability reading"),
            "source": os.path.relpath(path, ROOT),
        }
        rows.append(rec)
        printed.append(rec)

    with open(DEST, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")

    print(f"{'cell':<34}{'n':>4}{'pass':>6}{'score':>8}{'unparse':>9}  histogram")
    for r in printed:
        h = ",".join(f"{k}={v}" for k, v in sorted(r["status_histogram"].items()))
        score = "-" if r["score"] is None else f"{r['score']:.4f}"
        share = "-" if r["unparseable_share"] is None else f"{r['unparseable_share']:.2f}"
        print(f"{r['cell']:<34}{r['n']:>4}{r['pass']:>6}{score:>8}{share:>9}  {h}")
    collapsed = [r["cell"] for r in rows if r["at_floor"]]
    print(f"\ncells at the floor (pass share < {FLOOR_SHARE}): "
          f"{len(collapsed)}/{len(rows)} {collapsed}")
    print(f"wrote {os.path.relpath(DEST, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
