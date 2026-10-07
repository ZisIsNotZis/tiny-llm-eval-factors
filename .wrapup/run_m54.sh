#!/bin/bash
# M54 (QUEUE successor, post-N4) — Tier 5B statistical power, step 4: extend the
# THIRD-family code anchor (gemma-4-12B, java+js in m51) to rust+ruby, the same
# language pair used for the Qwen3.5-2B power step (m42). Adding languages to an
# independent anchor is the SSOT 5C fix for a headline CI (items/anchors, not
# re-runs). No new download: both gemma-4-12B files are already on disk.
#
# Rows: m54_summary.jsonl = 2 anchors x rust+ruby = 4.  Same frozen protocol
# (panel_mpl.sh) as m51, so the two panels pool cleanly.
#
# Must run under the GPU flock (gpu_locked.sh).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m54.log
SUM=$W/m54_summary.jsonl
export LOG
echo "=== M54 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "gemma-4-12b-it-UD-Q2_K_XL.gguf:gemma12b-q2"
  "gemma-4-12b-it-UD-Q3_K_XL.gguf:gemma12b-q3"
)
for spec in "${PANELS[@]}"; do
  file="${spec%%:*}"; tag="${spec##*:}"
  if [ ! -e "/home/z/hf/$file" ]; then echo "[M54] SKIP $tag: $file missing" >> "$LOG"; continue; fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "rust ruby" \
    "mpl-raw-greedy-768-third-family-code" \
    || echo "[M54] FAIL $tag" >> "$LOG"
done
echo "=== M54 end $(date) ===" >> "$LOG"
