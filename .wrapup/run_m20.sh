#!/bin/bash
# M20 — B3 cross-architecture multi-turn: sparse-MoE anchor (Qwen3.6-35B-A3B, A3B) on
# BFCL multi_turn_base, Q2/Q3 pair, native Qwen FC handler (Qwen3-30B-A3B-Instruct-2507-FC).
# Goal: extend the item-level Q2->Q3 multi-turn quant ladder beyond the dense Qwen3.5 family
# to a large sparse-MoE architecture (B3 "the MoE anchors"). 131072 ctx / 2 slots = 65536/slot,
# matches the m17 9B panel; multi_turn_base prompts stay < 53k so no overflow expected.
set -u
cd /home/z/hf/research
WR=/home/z/hf/research/.wrapup
export LOG=$WR/m20.log
export SUM=$WR/m20_summary.jsonl
export CTX=131072
export NP=2
echo "=== M20 start $(date) ===" >> "$LOG"
for qf in q2:Qwen3.6-35B-A3B-UD-Q2_K_XL.gguf q3:Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf; do
  tag="${qf%%:*}"; file="${qf#*:}"
  bash $WR/gpu_locked.sh bash $WR/run_m9_panel.sh \
    "m20-${tag}" "$file" "Qwen/Qwen3-30B-A3B-Instruct-2507-FC" multi_turn_base
done
echo "=== M20 end $(date) ===" >> "$LOG"
