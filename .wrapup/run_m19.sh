#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M19 — long-context multi-turn: complete the Q2/Q3 pair and cross the 4B size.
set -u
cd ${REPO_ROOT}
WR=${REPO_ROOT}/.wrapup
export LOG=$WR/m19.log
export SUM=$WR/m19_summary.jsonl
export CTX=196608
export NP=2
echo "=== M19 start $(date) ===" >> "$LOG"
for qf in q2:Qwen3.5-2B-UD-Q2_K_XL.gguf q3:Qwen3.5-2B-UD-Q3_K_XL.gguf; do
  tag="${qf%%:*}"; file="${qf#*:}"
  bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
    "m19-${tag}" "$file" "Qwen/Qwen3-1.7B-FC" multi_turn_long_context
done
for qf in q2:Qwen3.5-4B-UD-Q2_K_XL.gguf q3:Qwen3.5-4B-UD-Q3_K_XL.gguf; do
  tag="${qf%%:*}"; file="${qf#*:}"
  bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
    "m19-4b${tag}" "$file" "Qwen/Qwen3-4B-Instruct-2507-FC" multi_turn_long_context
done
echo "=== M19 end $(date) ===" >> "$LOG"
