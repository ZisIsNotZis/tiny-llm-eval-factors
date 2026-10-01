#!/bin/bash
# M11 — cross-family / cross-size multi-turn BFCL.
set -u
cd /home/z/hf/research
WR=/home/z/hf/research/.wrapup
export LOG=$WR/m11.log
export SUM=$WR/m11_summary.jsonl
CATS="${CATS:-multi_turn_base}"
PANELS="${PANELS:-qwen4b-q2:Qwen3.5-4B-UD-Q2_K_XL.gguf|Qwen/Qwen3-4B-Instruct-2507-FC qwen4b-q3:Qwen3.5-4B-UD-Q3_K_XL.gguf|Qwen/Qwen3-4B-Instruct-2507-FC}"
echo "=== M11 start $(date) cats=$CATS ===" >> "$LOG"
for spec in $PANELS; do
  tag="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%|*}"; handler="${rest#*|}"
  bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh "$tag" "$file" "$handler" "$CATS"
done
echo "=== M11 end $(date) ===" >> "$LOG"
