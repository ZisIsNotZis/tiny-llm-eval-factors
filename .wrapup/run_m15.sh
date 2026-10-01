#!/bin/bash
# M15 — long-context multi-turn, per-slot ctx large enough for 85k-token prompts.
set -u
cd /home/z/hf/research
WR=/home/z/hf/research/.wrapup
export LOG=$WR/m15.log
export SUM=$WR/m15_summary.jsonl
export CTX=196608
export NP=2
echo "=== M15 start $(date) ctx=$CTX np=$NP ===" >> "$LOG"
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  qwen2b-lc3 Qwen3.5-2B-UD-Q3_K_XL.gguf "Qwen/Qwen3-1.7B-FC" multi_turn_long_context
echo "=== M15 end $(date) ===" >> "$LOG"
