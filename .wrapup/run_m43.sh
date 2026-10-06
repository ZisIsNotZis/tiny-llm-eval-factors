#!/bin/bash
# M43 (QUEUE #17) — provenance recovery for Tier 2C (dense vs MoE at matched
# TOTAL size).
#
# Finding while re-arming the queue: the Tier-2C panel (run_m26.sh: gemma-4-26B-A4B
# MoE vs Qwen3.8-27B dense, Q2 and Q3, chat protocol `mpl-chat-nothink-greedy-768`)
# DID complete on 2026-10-02 — its raw completions and `_eval.json` files are on
# disk in mres/ — but m26_summary.jsonl is empty/missing and no m26 rows reached
# the DB. That makes a measured axis unquotable (SSOT §2: every number must name
# its run_tag; §4 priority 4: fill a provenance hole).
#
# This rebuilds m26_summary.jsonl from the existing per-cell evals. It is
# CPU-only and does NOT re-run the 27B panel (SSOT: deprioritise repeating an
# existing axis). If an eval file is missing the cell is skipped and reported.
#
# Rows: m26_summary.jsonl = 4 cells x 2 langs = 8.
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m43.log
SUM=$W/m26_summary.jsonl
echo "=== M43 start $(date) ===" >> "$LOG"
: > "$SUM"

python3 - "$W/mres" "$SUM" <<'PY' >> "$LOG" 2>&1
import glob, json, os, re, sys
mres, dest = sys.argv[1], sys.argv[2]
n = 0
for ev in sorted(glob.glob(os.path.join(mres, "m26-*-*_eval.json"))):
    m = re.match(r"m26-(.+)-(cpp|py)_eval\.json$", os.path.basename(ev))
    if not m:
        continue
    tag, lang = m.group(1), m.group(2)
    d = json.load(open(ev))
    row = {"model": tag, "lang": lang, "n": d["n"], "pass": d["pass"],
           "score": d["score"], "protocol": "mpl-chat-nothink-greedy-768"}
    with open(dest, "a") as f:
        f.write(json.dumps(row) + "\n")
    n += 1
    print("recovered", tag, lang, d["n"], round(d["score"], 4))
print("M43 recovered rows:", n)
PY

echo "=== M43 end $(date) rows=$(wc -l < "$SUM") ===" >> "$LOG"
