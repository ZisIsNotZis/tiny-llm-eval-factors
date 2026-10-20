#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# resolve_model.sh <modelscope-repo> <gguf-basename>
#
# Model resolution for the QUEUE driver panels (SSOT 6b: state lives on disk).
# Downloads <gguf-basename> from <modelscope-repo> into /home/z/hf/mscache/<repo>/
# and symlinks it to /home/z/hf/<basename> — the layout llama-server / exp.py expect.
#
# Idempotent: exits 0 immediately if the /home/z/hf symlink already resolves.
# Exit codes: 0 present/downloaded, 3 repo or file unavailable (caller logs SKIP).
set -u
MS=${REPO_ROOT}/.wrapup/msenv/bin/modelscope
DST=/home/z/hf/mscache
repo="$1"; file="$2"
link="/home/z/hf/$file"
LOG="${RESOLVE_LOG:-${REPO_ROOT}/.wrapup/queue_downloads.log}"

if [ -e "$link" ]; then
  echo "[resolve] $(date +%H:%M:%S) present $file" >> "$LOG"
  exit 0
fi
echo "[resolve] $(date +%H:%M:%S) download $repo/$file" >> "$LOG"
if timeout 14400 "$MS" download --model "$repo" "$file" --local_dir "$DST/$repo" >> "$LOG" 2>&1; then
  src=$(find "$DST/$repo" -name "$file" -type f 2>/dev/null | head -1)
  if [ -n "$src" ]; then
    ln -sf "$src" "$link" && { echo "[resolve] $(date +%H:%M:%S) OK $file" >> "$LOG"; exit 0; }
  fi
fi
echo "[resolve] $(date +%H:%M:%S) SKIP/FAIL $repo/$file (unavailable on ModelScope or download error)" >> "$LOG"
exit 3
