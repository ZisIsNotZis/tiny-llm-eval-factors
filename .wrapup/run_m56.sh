#!/bin/bash
# M56 (Tier 5B statistical power) — LFM2.5-8B-A1B Q2/Q3 x {java, js}.
#
# The model already has cpp+py rows (m45). BRAINSTORM 5C: the fix for a headline
# CI is ITEMS, not runs; MultiPL-E gives 161 items/language and the model supports
# 7. Adding java+js on the same tags (lfm25-8a1b-q2/q3, same frozen protocol)
# doubles the item count on this MoE anchor without a new model. Files are on disk
# and were already served by m45, so this panel is load-certain.
#
# Rows: m56_summary.jsonl = 2 quants x 2 langs = 4.  Protocol mpl-raw-greedy-768
# (joins m45 rows in the DB).
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m56.log
SUM=$W/m56_summary.jsonl
export LOG
echo "=== M56 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "LFM2.5-8B-A1B-UD-Q2_K_XL.gguf:lfm25-8a1b-q2"
  "LFM2.5-8B-A1B-UD-Q3_K_XL.gguf:lfm25-8a1b-q3"
)
for spec in "${PANELS[@]}"; do
  file="${spec%%:*}"; tag="${spec##*:}"
  if [ ! -e "/home/z/hf/$file" ]; then echo "[M56] SKIP $tag: $file missing" >> "$LOG"; continue; fi
  st=$(bash "$W/lg_state.sh" "$file"); [ "$st" = FAIL ] && { echo "[M56] SKIP $tag: load gate FAIL" >> "$LOG"; continue; }
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "java js" "mpl-raw-greedy-768" \
    || echo "[M56] FAIL $tag" >> "$LOG"
done
echo "=== M56 end $(date) ===" >> "$LOG"
