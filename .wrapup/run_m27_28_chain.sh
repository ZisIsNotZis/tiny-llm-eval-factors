#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# Tier-4 decoding panels, one GPU job at a time.
#   1) M28 — MTP draft length x speed   (fast, ~5-10 min)
#   2) M27 — sampling (temp) x quant on MultiPL-E cpp+py (long, ~1.5 h)
# Each panel takes the GPU flock for its whole duration.
set -u
WR=${REPO_ROOT}/.wrapup
bash "$WR/gpu_locked.sh" bash "$WR/run_m28.sh"
bash "$WR/gpu_locked.sh" bash "$WR/run_m27.sh"
echo "chain complete $(date)"
