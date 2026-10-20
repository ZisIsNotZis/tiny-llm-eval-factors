#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M12 — cross-family multi-turn + long-context multi-turn.
# Each panel carries its own category (was a single CATS before, which duplicated m9).
set -u
cd ${REPO_ROOT}
WR=${REPO_ROOT}/.wrapup
export LOG=$WR/m12.log
export SUM=$WR/m12_summary.jsonl
echo "=== M12 start $(date) ===" >> "$LOG"

# long-context multi-turn (different horizon stressor) for the known-good anchor
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  qwen2b-lc Qwen3.5-2B-UD-Q3_K_XL.gguf "Qwen/Qwen3-1.7B-FC" multi_turn_long_context

# cross-family multi-turn (granite uses its own handler; may or may not parse)
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  gr3b-q2 granite-4.1-3b-Q2_K.gguf "ibm-granite/granite-3.1-8b-instruct" multi_turn_base
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  gr3b-q3 granite-4.1-3b-Q3_K_M.gguf "ibm-granite/granite-3.1-8b-instruct" multi_turn_base

echo "=== M12 end $(date) ===" >> "$LOG"
