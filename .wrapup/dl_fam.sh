#!/bin/bash
MS=/home/z/hf/research/.wrapup/msenv/bin/modelscope
DST=/home/z/hf/mscache
LOG=/home/z/hf/research/.wrapup/dl_fam.log
dl() {
  local repo="$1" file="$2"
  echo "[$(date +%H:%M:%S)] START $file" >> "$LOG"
  $MS download --model "$repo" "$file" --local_dir "$DST/$repo" >> "$LOG" 2>&1 \
    && ln -sf "$(find "$DST/$repo" -name "$file" | head -1)" "/home/z/hf/$file" \
    && echo "[$(date +%H:%M:%S)] OK $file" >> "$LOG" || echo "[$(date +%H:%M:%S)] FAIL $file" >> "$LOG"
}
dl unsloth/gemma-4-E2B-it-GGUF gemma-4-E2B-it-UD-Q2_K_XL.gguf
dl unsloth/gemma-4-E4B-it-GGUF gemma-4-E4B-it-UD-Q2_K_XL.gguf
dl ibm-granite/granite-4.1-3b-GGUF granite-4.1-3b-Q2_K.gguf
dl ibm-granite/granite-4.1-3b-GGUF granite-4.1-3b-Q3_K_M.gguf
echo done >> "$LOG"
