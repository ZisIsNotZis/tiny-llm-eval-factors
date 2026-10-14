#!/usr/bin/env python3
"""The Q2->Q3 step, measured on every standard benchmark at once.

F1 in docs/FINDINGS.md originally rested on MultiPL-E alone.  The operator's requirement is
that a conclusion be tested on more than one benchmark, so this repeats the same step on all
seven columns using one fixed bpw window for "Q2-ish" and "Q3-ish":

    low  = 3.0 - 3.7 effective bpw
    high = 3.9 - 4.5 effective bpw

The window is defined in EFFECTIVE BPW, not in the nominal labels, because `Q2` spans
2.76-5.04 bpw across vendors and the label therefore carries no information.

Within each family only the lowest bpw in each window is used, so the step is always a real
bpw displacement and never a lateral move.
"""
from __future__ import annotations

import collections
import sys

sys.path.insert(0, ".")
from bpw_sensitivity import BENCH, BPW, family_of, load  # noqa: E402

LOW = (3.0, 3.7)
HIGH = (3.9, 4.5)


def main():
    data = load()          # (family, bench) -> {bpw: (score, n, model)}
    benches = [b for b, _, _ in BENCH]
    per_bench = collections.defaultdict(list)
    print("Q2 -> Q3 STEP PER BENCHMARK "
          f"(low = {LOW[0]}-{LOW[1]} bpw, high = {HIGH[0]}-{HIGH[1]} bpw)\n")
    print(f"{'family':28s} " + " ".join(f"{b[:9]:>9s}" for b in benches))
    print("-" * 28 + "-" + "-" * 10 * len(benches))
    for fam in sorted({f for f, _ in data}):
        cells, any_ = [], False
        for b in benches:
            pts = data.get((fam, b)) or {}
            lo = [bp for bp in pts if LOW[0] <= bp <= LOW[1]]
            hi = [bp for bp in pts if HIGH[0] <= bp <= HIGH[1]]
            if lo and hi:
                d = pts[min(hi)][0] - pts[min(lo)][0]
                per_bench[b].append(d)
                cells.append(f"{d:+9.3f}")
                any_ = True
            else:
                cells.append(f"{'-':>9s}")
        if any_:
            print(f"{fam[:28]:28s} " + " ".join(cells))

    print("\nmedian step per benchmark (and how often it is positive):")
    print(f"{'benchmark':18s} {'n':>3s} {'median':>9s} {'mean':>9s}  positive")
    for b in sorted(benches, key=lambda x: -(sorted(per_bench[x])[len(per_bench[x]) // 2]
                                             if per_bench[x] else -9)):
        v = sorted(per_bench[b])
        if not v:
            continue
        print(f"{b:18s} {len(v):3d} {v[len(v)//2]:+9.3f} "
              f"{sum(v)/len(v):+9.3f}  {sum(1 for x in v if x > 0)}/{len(v)}")


if __name__ == "__main__":
    main()
