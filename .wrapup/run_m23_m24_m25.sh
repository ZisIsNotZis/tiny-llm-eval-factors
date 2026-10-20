#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# BRAINSTORM Tier-1 runner: 1B -> 1C -> 1A, strictly sequential, one GPU job at
# a time (every panel goes through .wrapup/gpu_locked.sh).
#   1B m23: IQ3_XXS vs K-quant at matched file size (4B primary, 2B secondary)
#   1C m24: other ternary / sub-2-bit releases (Bonsai size series + new family)
#   1A m25: same MoE base, different provider (unsloth UD-Q3_K_XL vs bartowski Q3_K_M)
# Waits for each GGUF's dl_ready marker before acquiring the lock, so downloads
# never hold the GPU.
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m23_m24_m25.log
echo "=== BRAINSTORM T1 runner start $(date) ===" >> "$LOG"

run() {  # tag gguf summary [langs]
  local tag="$1" model="$2" sum="$3" langs="${4:-cpp py}"
  while [ ! -s "$W/dl_ready/$model.ready" ]; do
    if ! pgrep -f dl_m23_m25.sh >/dev/null 2>&1; then
      echo "[$(date +%H:%M:%S)] DOWNLOADER GONE before $model; skipping $tag" >> "$LOG"
      return 1
    fi
    sleep 30
  done
  echo "[$(date +%H:%M:%S)] launching $tag $model ($(cat "$W/dl_ready/$model.ready"))" >> "$LOG"
  bash "$W/gpu_locked.sh" bash "$W/panel_one.sh" "$tag" "$model" "$W/$sum" "mpl-raw-greedy-768" "$langs"
  local rc=$?
  echo "[$(date +%H:%M:%S)] finished $tag rc=$rc" >> "$LOG"
  return $rc
}

# 1B
run iq3-4b   Qwen3.5-4B-UD-IQ3_XXS.gguf              m23_summary.jsonl
run iq3-2b   Qwen3.5-2B-UD-IQ3_XXS.gguf              m23_summary.jsonl
# 1C
run bonsai17b-q20 Ternary-Bonsai-1.7B-Q2_0.gguf       m24_summary.jsonl
run bonsai8b-q20  Ternary-Bonsai-8B-Q2_0.gguf         m24_summary.jsonl
run tquench27b    TernaryQuench-Qwen3.8-27B-Hybrid-Q2_0.gguf m24_summary.jsonl
# 1A
run q36-35b-bartq3 Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf   m25_summary.jsonl

echo "=== BRAINSTORM T1 runner end $(date) ===" >> "$LOG"
