#!/bin/bash
# M60 (Tier 5B statistical power) — Ornith-1.5-9B Q4/Q5 x {rust, ruby}.
#
# A second non-Qwen family with an on-disk two-level pair (m10 tags orn9b-q4/q5).
# Uses the rust+ruby pair (as m42 for Qwen3.5-2B) so the new language items land on
# a *different* anchor than m56/m57's java+js. Files on disk, already served by
# m10 -> load-certain.
#
# Rows: m60_summary.jsonl = 2 levels x 2 langs = 4.  Protocol mpl-raw-greedy-768.
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m60.log
SUM=$W/m60_summary.jsonl
export LOG
echo "=== M60 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "Ornith-1.5-9B-Q4_K_M.gguf:orn9b-q4"
  "Ornith-1.5-9B-Q5_K_M.gguf:orn9b-q5"
)
for spec in "${PANELS[@]}"; do
  file="${spec%%:*}"; tag="${spec##*:}"
  if [ ! -e "/home/z/hf/$file" ]; then echo "[M60] SKIP $tag: $file missing" >> "$LOG"; continue; fi
  st=$(bash "$W/lg_state.sh" "$file"); [ "$st" = FAIL ] && { echo "[M60] SKIP $tag: load gate FAIL" >> "$LOG"; continue; }
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "rs rb" "mpl-raw-greedy-768" \
    || echo "[M60] FAIL $tag" >> "$LOG"
done
echo "=== M60 end $(date) ===" >> "$LOG"
