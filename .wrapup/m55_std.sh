#!/bin/bash
# MoE expert-wise recipes on the STANDARD benchmark set (table D was MultiPL-E only).
# The three m55 recipes differ in which tensors get the bits, at 2.92-4.48 effective bpw.
set -u
cd /home/z/hf/research || exit 2
WR=/home/z/hf/research/.wrapup
LOG="$WR/m55_std.log"
exec 7>/tmp/m55std.lock
flock -n 7 || { echo "another m55 driver holds the lock"; exit 0; }
for spec in "LFM2.5-8B-A1B-m55-Q3_K_M m132-m55-uniform" \
            "LFM2.5-8B-A1B-m55-exq2 m133-m55-exq2" \
            "LFM2.5-8B-A1B-m55-exq4 m134-m55-exq4"; do
  set -- $spec; model="/home/z/hf/$1.gguf"; tag="$2"
  [ -f "$WR/mres/$tag/DONE" ] && { echo "[$(date -Is)] SKIP $tag" >> "$LOG"; continue; }
  echo "[$(date -Is)] START $tag" >> "$LOG"
  mmlu=$(python3 -c "
import json,collections,subprocess,sys
" 2>/dev/null)
  # the m55 recipes are 16k-48k-token context MoE files; lmeval_panel runs the standard five
  MMLU_LIMIT=16 "$WR/lmeval_panel.sh" "$model" "$tag" 100 >> "$WR/m55_std.out" 2>&1
  [ -f "$WR/mres/$tag/DONE" ] && echo "[$(date -Is)] DONE $tag" >> "$LOG" \
                              || echo "[$(date -Is)] FAIL $tag" >> "$LOG"
done
echo "[$(date -Is)] === m55 standard campaign end ===" >> "$LOG"
