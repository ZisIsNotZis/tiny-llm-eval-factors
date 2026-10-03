#!/bin/bash
# Tier-4 decoding panels, one GPU job at a time.
#   1) M28 — MTP draft length x speed   (fast, ~5-10 min)
#   2) M27 — sampling (temp) x quant on MultiPL-E cpp+py (long, ~1.5 h)
# Each panel takes the GPU flock for its whole duration.
set -u
WR=/home/z/hf/research/.wrapup
bash "$WR/gpu_locked.sh" bash "$WR/run_m28.sh"
bash "$WR/gpu_locked.sh" bash "$WR/run_m27.sh"
echo "chain complete $(date)"
