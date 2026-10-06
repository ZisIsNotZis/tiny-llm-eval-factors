#!/bin/bash
# M42 (QUEUE #16) — Tier 5B/5C statistical power, step 2: MultiPL-E rust + ruby.
#
# SSOT 2/§5C: the fix for a headline CI is more ITEMS, not more runs. The
# Qwen3.5-2B Q2->Q3 code step is the headline quant claim; m38 already added
# java+js (161 items each). This adds the two remaining MultiPL-E languages with
# a local toolchain on this host (rustc, ruby both present; prompts
# /tmp/MultiPL-E/prompts/humaneval-{rs,rb}.jsonl exist; mpl_run.py has eval
# runners for both). Same two anchors, same frozen protocol -> the item count on
# the Q2->Q3 step goes 644 -> 966.
#
# Rows: m42_summary.jsonl = 2 anchors x 2 langs = 4.
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m42.log
SUM=$W/m42_summary.jsonl
export LOG
echo "=== M42 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "unsloth/Qwen3.5-2B-GGUF:Qwen3.5-2B-UD-Q2_K_XL.gguf:qwen2b-q2"
  "unsloth/Qwen3.5-2B-GGUF:Qwen3.5-2B-UD-Q3_K_XL.gguf:qwen2b-q3"
)
for spec in "${PANELS[@]}"; do
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M42] SKIP $tag: $repo/$file unavailable" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "rs rb" \
    || echo "[M42] FAIL $tag" >> "$LOG"
done

echo "=== M42 end $(date) ===" >> "$LOG"
