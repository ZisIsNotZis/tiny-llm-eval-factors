#!/bin/bash
# Model acquisition via ModelScope (China-reachable).
MS=/home/z/hf/research/.wrapup/msenv/bin/modelscope
DST=/home/z/hf/mscache
LOG=/home/z/hf/research/.wrapup/dl_ms.log
mkdir -p "$DST"
echo "=== ms download start $(date) ===" >> "$LOG"

dl() {  # repo file
  local repo="$1" file="$2"
  echo "[$(date +%H:%M:%S)] START $repo :: $file" >> "$LOG"
  if $MS download --model "$repo" "$file" --local_dir "$DST/$repo" >> "$LOG" 2>&1; then
    local src
    src=$(find "$DST/$repo" -name "$file" | head -1)
    if [ -n "$src" ]; then
      ln -sf "$src" "/home/z/hf/$file"
      echo "[$(date +%H:%M:%S)] OK+link $file" >> "$LOG"
    else
      echo "[$(date +%H:%M:%S)] OK-but-no-file $file" >> "$LOG"
    fi
  else
    echo "[$(date +%H:%M:%S)] FAIL $repo :: $file" >> "$LOG"
  fi
}

dl unsloth/Qwen3.5-4B-GGUF     Qwen3.5-4B-UD-Q2_K_XL.gguf
dl unsloth/Qwen3.5-2B-GGUF     Qwen3.5-2B-UD-Q2_K_XL.gguf
dl unsloth/Qwen3.5-9B-GGUF     Qwen3.5-9B-UD-Q2_K_XL.gguf
dl unsloth/Qwen3.5-9B-GGUF     Qwen3.5-9B-UD-Q3_K_XL.gguf
dl unsloth/gemma-4-E4B-it-GGUF gemma-4-E4B-it-UD-Q3_K_XL.gguf
dl unsloth/gemma-4-E2B-it-GGUF gemma-4-E2B-it-UD-Q3_K_XL.gguf
echo "=== ms download end $(date) ===" >> "$LOG"
