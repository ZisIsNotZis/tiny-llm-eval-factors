#!/bin/bash
# M9 driver — multi-turn BFCL (official bfcl-eval harness) across quant levels.
# GPU serialised by the shared flock; each panel is a separate script invocation.
set -u
cd /home/z/hf/research
WR=/home/z/hf/research/.wrapup
LOG=$WR/m9.log
CATS="${CATS:-multi_turn_base}"
PANELS="${PANELS:-qwen2b-q2:Qwen3.5-2B-UD-Q2_K_XL.gguf|Qwen/Qwen3-1.7B qwen2b-q3:Qwen3.5-2B-UD-Q3_K_XL.gguf|Qwen/Qwen3-1.7B}"
echo "=== M9 start $(date) cats=$CATS panels=[$PANELS] ===" >> "$LOG"
for spec in $PANELS; do
  tag="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%|*}"; handler="${rest#*|}"
  bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh "$tag" "$file" "$handler" "$CATS"
done
echo "=== M9 end $(date) ===" >> "$LOG"
