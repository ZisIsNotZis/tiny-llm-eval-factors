#!/bin/bash
# plan4 / a11 :: small protocol probes on the diffusion CLI.
# read-only w.r.t. the repo; writes only into this log directory.
set -u
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN=/home/z/llama-diffusion-pr/build/bin/llama-diffusion-cli
MODEL=/home/z/hf/diffusiongemma-26B-A4B-it-Q4_K_M.gguf

run() { # $1=tag  $2..=args
  local tag="$1"; shift
  local log="$OUT/protocol-$tag.log"
  local mem="$OUT/protocol-$tag.mem"
  : > "$mem"
  ( while :; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits >> "$mem"; sleep 0.5; done ) &
  local sampler=$!
  {
    echo "# tag=$tag $(date -Is)"
    echo "# bin: $BIN sha256 $(sha256sum "$BIN" | cut -d' ' -f1)"
    echo "# model: $MODEL ($(stat -c%s "$MODEL") B)"
    echo "# cmd: $BIN -m $MODEL -ngl 99 -no-cnv $*"
  } > "$log"
  local t0=$(date +%s.%N)
  "$BIN" -m "$MODEL" -ngl 99 -no-cnv "$@" >> "$log" 2>&1
  local rc=$?
  local t1=$(date +%s.%N)
  kill "$sampler" 2>/dev/null; wait "$sampler" 2>/dev/null
  local peak; peak=$(sort -n "$mem" | tail -1)
  {
    echo "--- rc=$rc elapsed_s=$(echo "$t1 - $t0" | bc)"
    echo "--- gpu_peak_mib: $peak"
  } >> "$log"
  echo "done $tag rc=$rc peak=$peak elapsed=$(echo "$t1 - $t0" | bc)" >> "$OUT/protocol_runs.status"
}

: > "$OUT/protocol_runs.status"
# A. determinism: identical command, three separate processes (default seed = -1 -> mt19937(0xFFFFFFFF))
for i in 1 2 3; do
  run "det$i" -p '1+1=' -n 64
done
# B. -n 64 vs -n 256 (both round up to one canvas block of 256); -n 512 = two blocks for the contrast
run "n64"  -p '1+1=' -n 64
run "n256" -p '1+1=' -n 256
run "n512" -p '1+1=' -n 512
# C. greedy-per-position configuration (EB off, top-k 1, temp 0, confidence algorithm)
run "greedy-he0" --diffusion-eb off --diffusion-algorithm 4 --temp 0 --top-k 1 --diffusion-steps 32 -f /tmp/plan4_he0_prompt.txt -n 256
echo "ALL DONE $(date -Is)" >> "$OUT/protocol_runs.status"
