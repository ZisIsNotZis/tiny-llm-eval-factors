#!/bin/bash
# M16 — multi-turn BFCL cross-family (MiniCPM5-2B) with MiniCPM's native FC handler.
set -u
cd /home/z/hf/research
WR=/home/z/hf/research/.wrapup
export LOG=$WR/m16.log
export SUM=$WR/m16_summary.jsonl
export CTX=131072
export NP=2
echo "=== M16 start $(date) ===" >> "$LOG"
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  mcp5-2b-q2 MiniCPM5-2B-Q2_K.gguf "openbmb/MiniCPM3-4B-FC" multi_turn_base
bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
  mcp5-2b-q3 MiniCPM5-2B-Q3_K_M.gguf "openbmb/MiniCPM3-4B-FC" multi_turn_base
echo "=== M16 end $(date) ===" >> "$LOG"
