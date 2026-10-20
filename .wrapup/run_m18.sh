#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M18 — the other two multi-turn sub-categories (error handling), 2B Q2 vs Q3.
#   miss_func : the needed function is absent -> the model should NOT hallucinate a call
#   miss_param: a required argument is unavailable -> the model should not fabricate it
set -u
cd ${REPO_ROOT}
WR=${REPO_ROOT}/.wrapup
export LOG=$WR/m18.log
export SUM=$WR/m18_summary.jsonl
export CTX=131072
export NP=2
echo "=== M18 start $(date) ===" >> "$LOG"
for qf in q2:Qwen3.5-2B-UD-Q2_K_XL.gguf q3:Qwen3.5-2B-UD-Q3_K_XL.gguf; do
  tag="${qf%%:*}"; file="${qf#*:}"
  bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
    "m18-${tag}" "$file" "Qwen/Qwen3-1.7B-FC" multi_turn_miss_func,multi_turn_miss_param
done
echo "=== M18 end $(date) ===" >> "$LOG"
