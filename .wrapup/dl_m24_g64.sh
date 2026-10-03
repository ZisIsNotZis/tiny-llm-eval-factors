#!/bin/bash
# M24 — acquire the group-64 (upstream-loadable) ternary Bonsai packs for the
# SIZE SERIES. The earlier download fetched the legacy g128 `Q2_0.gguf` files,
# which the loader rejects ("legacy Prism Q2_0 layout ... expected group-64").
# The correct upstream-loadable files are `*Q2_0_g64.gguf`.
set -u
W=/home/z/hf/research/.wrapup
MS=$W/msenv/bin/modelscope
DST=/home/z/hf/mscache
LOG=$W/m24_29.log
mkdir -p "$DST" "$W/dl_ready"
echo "=== dl_m24_g64 start $(date) ===" >> "$LOG"

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

dl_ms prism-ml/Ternary-Bonsai-1.7B-gguf Ternary-Bonsai-1.7B-Q2_0_g64.gguf
dl_ms prism-ml/Ternary-Bonsai-8B-gguf   Ternary-Bonsai-8B-Q2_0_g64.gguf
echo "=== dl_m24_g64 end $(date) ===" >> "$LOG"
