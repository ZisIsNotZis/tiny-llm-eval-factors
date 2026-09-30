#!/bin/bash
# T4 full chain — runs under a single GPU-lock acquisition.
#   1) gemma-4-12B repair (probe+select protocol) -> m6b_summary.jsonl
#   2) new architecture anchors, raw greedy protocol -> m10_summary.jsonl
# Batches are ordered by priority so partial completion still covers the core.
set -u
cd /home/z/hf/research/.wrapup
MS=/home/z/hf/research/.wrapup
LOG=$MS/t4_run.log
MRES=$MS/mres
M10=$MS/m10_summary.jsonl
META=$MS/t4_meta.jsonl
PY=python3

run_batch() {  # run_batch <proto> <ctx> <panels> [langs]
  local proto="$1" ctx="$2" panels="$3" langs="${4:-cpp py}"
  SUMMARY="$M10" META="$META" LOG="$LOG" MRES="$MRES" PREFIX=m10 \
  PANELS="$panels" CTX="$ctx" LANGS="$langs" PROTO="$proto" MODE=raw \
    bash "$MS/t4_run.sh"
}

echo "=== T4_all start $(date) ===" >> "$LOG"

# ---- 1) gemma-4-12B repair ----
$PY "$MS/t4_gemma_repair.py" >> "$LOG" 2>&1

# ---- 2) required new anchors (Q2/Q3) ----
run_batch mpl-raw-greedy-768 2048 \
  "q38-27b-q2:Qwen3.8-27B-UD-Q2_K_XL.gguf q38-27b-q3:Qwen3.8-27B-UD-Q3_K_XL.gguf"

run_batch mpl-raw-greedy-768 2048 \
  "g26b-q2:gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf g26b-q3:gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf"

# ---- 3) small new families (adjacent pairs) ----
run_batch mpl-raw-greedy-768 4096 \
  "nem4b-q2:NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL.gguf nem4b-q3:NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL.gguf"

run_batch mpl-raw-greedy-768 4096 \
  "mcp5-2b-q2:MiniCPM5-2B-Q2_K.gguf mcp5-2b-q3:MiniCPM5-2B-Q3_K_M.gguf"

run_batch mpl-raw-greedy-768 4096 \
  "lfm25-8b-q2:LFM2.5-8B-A1B-UD-Q2_K_XL.gguf lfm25-8b-q3:LFM2.5-8B-A1B-UD-Q3_K_XL.gguf"

run_batch mpl-raw-greedy-768 4096 \
  "orn9b-q4:Ornith-1.5-9B-Q4_K_M.gguf orn9b-q5:Ornith-1.5-9B-Q5_K_M.gguf"

echo "=== T4_all end $(date) ===" >> "$LOG"
