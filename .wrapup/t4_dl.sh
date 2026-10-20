#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# T4 downloads (network-only, parallel-safe). Streams run concurrently; each file
# goes to its own repo dir so there is no write contention.
MS=${REPO_ROOT}/.wrapup/msenv/bin/modelscope
DST=/home/z/hf/mscache
LOG=${REPO_ROOT}/.wrapup/t4_dl.log
mkdir -p "$DST"
dl() {
  local repo="$1" file="$2"
  if [ -e "/home/z/hf/$file" ]; then echo "[$(date +%H:%M:%S)] SKIP $file (symlink exists)" >> "$LOG"; return 0; fi
  echo "[$(date +%H:%M:%S)] START $repo/$file" >> "$LOG"
  $MS download --model "$repo" "$file" --local_dir "$DST/$repo" >> "$LOG" 2>&1 \
    && ln -sf "$(find "$DST/$repo" -name "$file" | head -1)" "/home/z/hf/$file" \
    && echo "[$(date +%H:%M:%S)] OK $file" >> "$LOG" || echo "[$(date +%H:%M:%S)] FAIL $file" >> "$LOG"
}
stream_a() {  # required big anchors
  dl unsloth/Qwen3.8-27B-GGUF Qwen3.8-27B-UD-Q2_K_XL.gguf
  dl unsloth/Qwen3.8-27B-GGUF Qwen3.8-27B-UD-Q3_K_XL.gguf
}
stream_b() {
  dl unsloth/gemma-4-26B-A4B-it-GGUF gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf
  dl unsloth/gemma-4-26B-A4B-it-GGUF gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf
}
stream_c() {  # small new families
  dl unsloth/NVIDIA-Nemotron-3-Nano-4B-GGUF NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL.gguf
  dl unsloth/NVIDIA-Nemotron-3-Nano-4B-GGUF NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL.gguf
  dl bartowski/MiniCPM5-2B-GGUF MiniCPM5-2B-Q2_K.gguf
  dl bartowski/MiniCPM5-2B-GGUF MiniCPM5-2B-Q3_K_M.gguf
}
stream_d() {  # new families + ornith
  dl unsloth/LFM2.5-8B-A1B-GGUF LFM2.5-8B-A1B-UD-Q2_K_XL.gguf
  dl unsloth/LFM2.5-8B-A1B-GGUF LFM2.5-8B-A1B-UD-Q3_K_XL.gguf
  dl ornith-ai/Ornith-1.5-9B-GGUF Ornith-1.5-9B-Q5_K_M.gguf
}
echo "[$(date +%H:%M:%S)] t4_dl start" >> "$LOG"
stream_a & pa=$!
stream_b & pb=$!
stream_c & pc=$!
stream_d & pd=$!
wait $pa $pb $pc $pd
echo "[$(date +%H:%M:%S)] t4_dl ALL DONE" >> "$LOG"
