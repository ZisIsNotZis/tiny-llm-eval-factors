#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M13 — corrected long-context multi-turn re-run.
# M12's long_context panel used 98304/2 = 49152 ctx/slot; prompts reach ~53k.
# Run with 131072/2 = 65536 per slot (and a single-slot fallback already large enough).
set -u
cd ${REPO_ROOT}
WR=${REPO_ROOT}/.wrapup
export LOG=$WR/m13.log
export SUM=$WR/m13_summary.jsonl
export CTX=131072
export NP=2
echo "=== M13 start $(date) ctx=$CTX np=$NP ===" >> "$LOG"
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  qwen2b-lc2 Qwen3.5-2B-UD-Q3_K_XL.gguf "Qwen/Qwen3-1.7B-FC" multi_turn_long_context
echo "=== M13 end $(date) ===" >> "$LOG"
