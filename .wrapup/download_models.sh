#!/bin/bash
# Wrap-up resource acquisition. Uses hf-mirror (China-reachable).
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_ENABLE_HF_TRANSFER=0
HF=/home/z/.venv/bin/hf
cd /home/z/hf
LOG=/home/z/hf/research/.wrapup/download_models.log
echo "=== download start $(date) ===" >> $LOG

dl() {  # repo  file
  local repo="$1" file="$2"
  echo "[$(date +%H:%M:%S)] START $repo :: $file" >> $LOG
  for attempt in 1 2 3; do
    if $HF download "$repo" "$file" >> $LOG 2>&1; then
      echo "[$(date +%H:%M:%S)] OK    $repo :: $file" >> $LOG
      return 0
    fi
    echo "[$(date +%H:%M:%S)] retry $attempt $repo :: $file" >> $LOG
    sleep 10
  done
  echo "[$(date +%H:%M:%S)] FAIL  $repo :: $file" >> $LOG
  return 1
}

# --- Priority 1: complete the most-cited Q2->Q3 ladder (enables replicate + power study) ---
dl unsloth/Qwen3.5-4B-GGUF   Qwen3.5-4B-UD-Q2_K_XL.gguf
dl unsloth/Qwen3.5-2B-GGUF   Qwen3.5-2B-UD-Q2_K_XL.gguf

# --- Priority 2: larger-scale anchor (closes the #1 pending question) ---
dl unsloth/Qwen3.5-9B-GGUF   Qwen3.5-9B-UD-Q2_K_XL.gguf
dl unsloth/Qwen3.5-9B-GGUF   Qwen3.5-9B-UD-Q3_K_XL.gguf

# --- Priority 3: restore unseen-architecture anchors at Q3 (family diversity) ---
dl unsloth/gemma-4-E4B-it-GGUF gemma-4-E4B-it-UD-Q3_K_XL.gguf
dl unsloth/gemma-4-E2B-it-GGUF gemma-4-E2B-it-UD-Q3_K_XL.gguf

echo "=== download end $(date) ===" >> $LOG
