#!/usr/bin/env python3
"""Classify every claim in conclusions.md against the measured resolution floors.

Statuses
--------
resolved      |Δ| clears the paired MDE at that claim's own aggregation level
underpowered  |Δ| is above the repeat floor but below the MDE
noise_level   |Δ| is below the repeat floor (not reproducible even run-to-run)
pooled_only   a pooled regression coefficient, not a matched contrast -> directional,
              not resolution-testable
unauditable   the claim depends on a variable absent from the DB schema
              (ctx_size, parallel_slots, start_time, reason, seed, source_file)

Outputs claims_ledger.csv and prints a distribution summary.
"""
import csv
import json
import math
import re

CLAIMS = "conclusions.md"
RES = json.load(open("resolution.json"))
REPEAT = RES["thresholds"]["repeat_floor"]          # 0.008
MDE_HE = RES["thresholds"]["single_pair_humaneval"] # 0.108
MDE_MBPP = RES["thresholds"]["single_pair_mbpp"]    # 0.071
UNAUDITABLE_TOKENS = ("ctx=", "ctx8192", "ctx24576", "parallel=", "par1", "par4",
                      "start_time", "end_time", "perf_event")


def parse_claims(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("*"):
            continue
        body = line.lstrip("*").strip()
        if not body:
            continue
        claim, sep, rest = body.partition("| evidence")
        out.append((claim.strip(), (sep + rest).strip() if sep else ""))
    return out


def extract_deltas(claim):
    """Return explicit signed deltas and a->b pair differences.

    Confidence intervals, standard deviations and parenthetical stats are removed
    first so their numbers are not mistaken for effect sizes.
    """
    text = re.sub(r"95%\s*CI\s*\[[^\]]*\]", " ", claim)
    text = re.sub(r"\[[+-]?0\.\d+,\s*[+-]?0\.\d+\]", " ", text)
    text = re.sub(r"sd\s*[=:]?\s*0\.\d+", " ", text, flags=re.I)
    text = re.sub(r"n\s*=\s*\d+", " ", text)
    deltas = []
    # explicit signed decimals: +0.0854 / -0.0317 / Δ...≈+0.0698 / theta=-0.6709
    for m in re.finditer(r"[+\-−]\s?(0\.\d+)", text):
        deltas.append(-float(m.group(1)) if m.group(0)[0] in "−-" else float(m.group(1)))
    # a -> b pairs
    for m in re.finditer(r"(0\.\d+)\s*(?:->|→|to)\s*(0\.\d+)", text):
        deltas.append(float(m.group(2)) - float(m.group(1)))
    return deltas


def aggregation_n(claim):
    m = re.search(r"(\d+)\s*(?:matched pairs|contexts|matched contexts|pairs)", claim)
    if m:
        return max(1, int(m.group(1)))
    return 1


def classify(claim, evidence):
    text = (claim + " " + evidence).lower()
    from json import dumps
    if any(t in text for t in UNAUDITABLE_TOKENS):
        return "unauditable", None, 1, "depends on variable absent from DB schema"
    if ("theta=" in text or "partial effect" in text or "residual" in text
            or "coefficient" in text or "rmse" in text or "refit" in text
            or "formula" in text or "k_quant=" in text or "cap-family" in text
            or "cap search" in text):
        return "model_fit", None, 1, "model-fit / coefficient statement, not an effect claim"

    deltas = extract_deltas(claim)
    if not deltas:
        return "qualitative", None, 1, "no numeric contrast in the claim"

    n = aggregation_n(claim)
    maxd = max(abs(d) for d in deltas)
    # use the stricter (humaneval) floor for a single pair; scale by sqrt(n)
    mde = MDE_HE / math.sqrt(n)
    if maxd < REPEAT:
        return "noise_level", round(maxd, 4), n, f"|Δ|={maxd:.4f} < repeat floor {REPEAT}"
    if maxd < mde:
        return "underpowered", round(maxd, 4), n, f"|Δ|={maxd:.4f} < MDE {mde:.3f} at n={n}"
    return "resolved", round(maxd, 4), n, f"|Δ|={maxd:.4f} >= MDE {mde:.3f} at n={n}"


def main():
    claims = parse_claims(open(CLAIMS).read())
    rows = []
    for i, (claim, ev) in enumerate(claims, 1):
        status, delta, n, reason = classify(claim, ev)
        rows.append({
            "id": i,
            "status": status,
            "max_abs_delta": delta if delta is not None else "",
            "aggregation_n": n,
            "reason": reason,
            "claim": claim,
        })
    with open("claims_ledger.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    c = Counter(r["status"] for r in rows)
    print(f"claims parsed: {len(rows)}")
    for k, v in c.most_common():
        print(f"  {k:14s} {v:3d}  ({v/len(rows):.0%})")
    print("\nthresholds: repeat=%.3f  MDE_single_HE=%.3f  MDE_single_MBPP=%.3f"
          % (REPEAT, MDE_HE, MDE_MBPP))
    print("\nresolved claims:")
    for r in rows:
        if r["status"] == "resolved":
            print(f"  [{r['max_abs_delta']}] {r['claim'][:95]}")

    # ---- markdown ledger ----
    ORDER = ["resolved", "underpowered", "noise_level", "unauditable",
             "pooled_only", "model_fit", "qualitative"]
    md = ["# Claims resolution ledger\n",
          "_Auto-generated by `claims_ledger.py` from `conclusions.md` and the",
          "floors in `resolution.json`. Read alongside `resolution.md`._\n",
          f"Thresholds: repeat floor **{REPEAT}**, single-pair MDE on HumanEval "
          f"**{MDE_HE}**, on MBPP **{MDE_MBPP}**.\n",
          "| status | n | share |", "|---|---|---|"]
    for k in ORDER:
        if c.get(k):
            md.append(f"| {k} | {c[k]} | {c[k]/len(rows):.0%} |")
    md.append("")
    for status in ORDER:
        sub = [r for r in rows if r["status"] == status]
        if not sub:
            continue
        md.append(f"## {status} ({len(sub)})\n")
        for r in sub:
            d = f"Δ={r['max_abs_delta']} " if r["max_abs_delta"] != "" else ""
            md.append(f"- {d}— {r['claim']}")
            md.append(f"  - _{r['reason']}_")
        md.append("")
    with open("CLAIMS_RESOLUTION.md", "w") as f:
        f.write("\n".join(md) + "\n")
    print("\nwrote claims_ledger.csv + CLAIMS_RESOLUTION.md")


if __name__ == "__main__":
    main()
