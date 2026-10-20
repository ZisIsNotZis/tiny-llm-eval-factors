#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M14 — granite multi-turn with the granite-4 native FC handler + larger per-slot ctx.
set -u
cd ${REPO_ROOT}
WR=${REPO_ROOT}/.wrapup
export LOG=$WR/m14.log
export SUM=$WR/m14_summary.jsonl
export CTX=131072
export NP=2
echo "=== M14 start $(date) ===" >> "$LOG"
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  gr4b-q2 granite-4.1-3b-Q2_K.gguf "ibm-granite/granite-4.0-350m" multi_turn_base
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  gr4b-q3 granite-4.1-3b-Q3_K_M.gguf "ibm-granite/granite-4.0-350m" multi_turn_base
echo "=== M14 end $(date) ===" >> "$LOG"
