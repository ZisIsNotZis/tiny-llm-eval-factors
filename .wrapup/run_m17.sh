#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M17 — multi-turn BFCL, Qwen3.5-9B Q2/Q3 (completes the size trend 2B/4B/9B).
set -u
cd ${REPO_ROOT}
WR=${REPO_ROOT}/.wrapup
export LOG=$WR/m17.log
export SUM=$WR/m17_summary.jsonl
export CTX=131072
export NP=2
echo "=== M17 start $(date) ===" >> "$LOG"
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  qwen9b-q2 Qwen3.5-9B-UD-Q2_K_XL.gguf "Qwen/Qwen3-8B-FC" multi_turn_base
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  qwen9b-q3 Qwen3.5-9B-UD-Q3_K_XL.gguf "Qwen/Qwen3-8B-FC" multi_turn_base
echo "=== M17 end $(date) ===" >> "$LOG"
