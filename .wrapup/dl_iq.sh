#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
MS=${REPO_ROOT}/.wrapup/msenv/bin/modelscope
DST=/home/z/hf/mscache
LOG=${REPO_ROOT}/.wrapup/dl_iq.log
dl() {
  local repo="$1" file="$2"
  echo "[$(date +%H:%M:%S)] START $file" >> "$LOG"
  $MS download --model "$repo" "$file" --local_dir "$DST/$repo" >> "$LOG" 2>&1 \
    && ln -sf "$(find "$DST/$repo" -name "$file" | head -1)" "/home/z/hf/$file" \
    && echo "[$(date +%H:%M:%S)] OK $file" >> "$LOG" || echo "[$(date +%H:%M:%S)] FAIL $file" >> "$LOG"
}
dl unsloth/Qwen3.5-2B-GGUF Qwen3.5-2B-UD-IQ2_M.gguf
dl unsloth/Qwen3.5-2B-GGUF Qwen3.5-2B-UD-IQ2_XXS.gguf
dl unsloth/Qwen3.5-0.8B-GGUF Qwen3.5-0.8B-UD-IQ2_M.gguf
dl unsloth/Qwen3.5-0.8B-GGUF Qwen3.5-0.8B-UD-IQ2_XXS.gguf
echo "done" >> "$LOG"
