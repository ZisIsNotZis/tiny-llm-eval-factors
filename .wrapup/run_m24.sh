#!/bin/bash
# M24 — ternary (Bonsai) SIZE SERIES.
#
# Earlier single ternary observation: Ternary-Bonsai-27B-Q2_g64 (m21, 7.59 GB,
# cpp .6957 / py .7640). This extends it to 1.7B and 8B so the "ternary sits
# above the bits->score curve" claim becomes a size series.
#
# The first download attempt fetched the LEGACY g128 `Q2_0.gguf` packs, which the
# loader rejects ("legacy Prism Q2_0 layout ... expected group-64"). The
# upstream-loadable files are `*Q2_0_g64.gguf` (same ggml type 42, group size 64).
# Both load under build 4399 -> same runtime as the 27B g64, so the series is
# protocol-consistent.
#
# Frozen protocol (identical to run_m5.sh / run_m21.sh): ctx 4096, KV q8_0/q8_0,
# top_p .95 / top_k 40 / min_p .05, raw completion (MultiPL-E native), greedy,
# 768 max tokens. panel_one.sh smoke-tests each model before the panel.
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m24_29.log
echo "=== M24 ternary size series start $(date) ===" >> "$LOG"

run() {  # tag gguf summary
  local tag="$1" model="$2" sum="$3"
  while [ ! -s "$W/dl_ready/$model.ready" ]; do sleep 20; done
  echo "[$(date +%H:%M:%S)] M24 launching $tag $model" >> "$LOG"
  bash "$W/gpu_locked.sh" bash "$W/panel_one.sh" "$tag" "$model" "$W/$sum" "mpl-raw-greedy-768" "cpp py"
  echo "[$(date +%H:%M:%S)] M24 finished $tag rc=$?" >> "$LOG"
}

run bonsai17b-g64 Ternary-Bonsai-1.7B-Q2_0_g64.gguf m24_summary.jsonl
run bonsai8b-g64  Ternary-Bonsai-8B-Q2_0_g64.gguf   m24_summary.jsonl
echo "=== M24 ternary size series end $(date) ===" >> "$LOG"
