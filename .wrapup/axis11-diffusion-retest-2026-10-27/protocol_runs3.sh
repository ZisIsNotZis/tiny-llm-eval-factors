#!/bin/bash
set -u
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN=/home/z/llama-diffusion-pr/build/bin/llama-diffusion-cli
MODEL=/home/z/hf/diffusiongemma-26B-A4B-it-Q4_K_M.gguf
run() {
  local tag="$1"; shift
  local log="$OUT/protocol-$tag.log"
  {
    echo "# tag=$tag $(date -Is)"
    echo "# bin: $BIN sha256 $(sha256sum "$BIN" | cut -d' ' -f1)"
    echo "# model: $MODEL -> $(readlink -f "$MODEL") ($(stat -Lc%s "$MODEL") B)"
    echo "# cmd: $BIN -m $MODEL -ngl 99 -no-cnv $*"
  } > "$log"
  local t0=$(date +%s.%N); "$BIN" -m "$MODEL" -ngl 99 -no-cnv "$@" >> "$log" 2>&1; local rc=$?
  local t1=$(date +%s.%N)
  echo "--- rc=$rc elapsed_s=$(echo "$t1 - $t0" | bc)" >> "$log"
  echo "done $tag rc=$rc" >> "$OUT/protocol_runs.status"
}
run "seed1234" -s 1234 -p '1+1=' -n 64
run "seed-1"   -s -1   -p '1+1=' -n 64
echo "ALL DONE3 $(date -Is)" >> "$OUT/protocol_runs.status"
