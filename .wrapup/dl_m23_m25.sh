#!/bin/bash
# Downloads for BRAINSTORM Tier-1 (1B/1C/1A). Detached; writes .ready markers
# under .wrapup/dl_ready/<file>.ready once a GGUF is fully local and symlinked.
# ModelScope first (China-reachable, matches workspace layout); HF mirror for
# repos absent from ModelScope (penkia/TernaryQuench).
set -u
W=/home/z/hf/research/.wrapup
MS=$W/msenv/bin/modelscope
DST=/home/z/hf/mscache
HF=/home/z/.venv/bin/hf
LOG=$W/dl_m23_m25.log
mkdir -p "$DST" "$W/dl_ready"
echo "=== dl start $(date) ===" >> "$LOG"

dl_ms() {  # repo file
  local repo="$1" file="$2" src
  echo "[$(date +%H:%M:%S)] MS START $repo :: $file" >> "$LOG"
  rm -f "$W/dl_ready/$file.ready"
  if $MS download --model "$repo" "$file" --local_dir "$DST/$repo" >> "$LOG" 2>&1; then
    src=$(find "$DST/$repo" -name "$file" -size +100M | head -1)
    if [ -n "$src" ]; then
      ln -sf "$src" "/home/z/hf/$file"
      echo "$src" > "$W/dl_ready/$file.ready"
      echo "[$(date +%H:%M:%S)] MS OK $file $(stat -c%s "$src")" >> "$LOG"
    else
      echo "[$(date +%H:%M:%S)] MS OK-but-missing $file" >> "$LOG"
    fi
  else
    echo "[$(date +%H:%M:%S)] MS FAIL $file" >> "$LOG"
  fi
}

dl_hf() {  # repo file
  local repo="$1" file="$2" src
  echo "[$(date +%H:%M:%S)] HF START $repo :: $file" >> "$LOG"
  rm -f "$W/dl_ready/$file.ready"
  if $HF download "$repo" "$file" --local-dir "$DST/$repo" >> "$LOG" 2>&1; then
    src=$(find "$DST/$repo" -name "$file" -size +100M | head -1)
    if [ -n "$src" ]; then
      ln -sf "$src" "/home/z/hf/$file"
      echo "$src" > "$W/dl_ready/$file.ready"
      echo "[$(date +%H:%M:%S)] HF OK $file $(stat -c%s "$src")" >> "$LOG"
    else
      echo "[$(date +%H:%M:%S)] HF OK-but-missing $file" >> "$LOG"
    fi
  else
    echo "[$(date +%H:%M:%S)] HF FAIL $file" >> "$LOG"
  fi
}

# --- 1B: IQ3_XXS arms (K-quant arms already measured: m1 4B Q2/Q3, m3 2B Q2/Q3)
dl_ms unsloth/Qwen3.5-4B-GGUF Qwen3.5-4B-UD-IQ3_XXS.gguf
dl_ms unsloth/Qwen3.5-2B-GGUF Qwen3.5-2B-UD-IQ3_XXS.gguf
# --- 1C: ternary / sub-2-bit releases (Bonsai size series + new ternary family)
dl_ms prism-ml/Ternary-Bonsai-1.7B-gguf Ternary-Bonsai-1.7B-Q2_0.gguf
dl_ms prism-ml/Ternary-Bonsai-8B-gguf Ternary-Bonsai-8B-Q2_0.gguf
dl_hf penkia/TernaryQuench-Qwen3.8-27B-GGUF TernaryQuench-Qwen3.8-27B-Hybrid-Q2_0.gguf
# --- 1A: same MoE base, different provider (unsloth UD-Q3_K_XL already on disk)
dl_ms bartowski/Qwen_Qwen3.6-35B-A3B-GGUF Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf
echo "=== dl end $(date) ===" >> "$LOG"
