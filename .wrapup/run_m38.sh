#!/bin/bash
# M38 (NEW QUEUE entry) — Tier 5B / 5C statistical power: add MultiPL-E java + js to
# the two anchors that define the headline Q2->Q3 quant step.
#
# SSOT 2 and BRAINSTORM 5C: the fix for a headline CI is more ITEMS, not more runs.
# MultiPL-E gives 161 items/language; the Q2->Q3 step on code currently rests on
# cpp+py (322 items). Adding java+js for the same two anchors (Qwen3.5-2B UD-Q2_K_XL
# and UD-Q3_K_XL — the exact pair behind the "Q2 floor on the code axis" claim)
# roughly doubles the item count for that step at two extra languages, with the
# protocol held fixed (shared frozen panel).
#
# MultiPL-E java/js harnesses are already in place (jars/ + testfrac_m3-*-java/js
# runs exist). Rows: m38_summary.jsonl = 2 anchors x 2 langs (java, js) = 4.
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m38.log
SUM=$W/m38_summary.jsonl
export LOG
echo "=== M38 start $(date) ===" >> "$LOG"

# file present on disk -> resolve_model.sh exits 0 without a download
PANELS=(
  "unsloth/Qwen3.5-2B-GGUF:Qwen3.5-2B-UD-Q2_K_XL.gguf:qwen2b-q2"
  "unsloth/Qwen3.5-2B-GGUF:Qwen3.5-2B-UD-Q3_K_XL.gguf:qwen2b-q3"
)
for spec in "${PANELS[@]}"; do
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M38] SKIP $tag: $repo/$file unavailable" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "java js" \
    || echo "[M38] FAIL $tag" >> "$LOG"
done

echo "=== M38 end $(date) ===" >> "$LOG"
