#!/bin/bash
# M33 (QUEUE #7) — Tier 5A architecture-family breadth on the frozen MultiPL-E panel.
#
# The cross-family table is dominated by Qwen/gemma/granite; four families we have
# never measured end-to-end are added here at one on-curve level each (breadth, not a
# ladder — SSOT 4 item 3): MiniCPM5, Nemotron-3, Ornith-1.5, GLM-4.7-Flash. All four
# are MoE or non-Qwen dense archs, so this also feeds the "architecture/cross-family"
# part of the study question. GLM-4.7-Flash is the only download (13.8 GB); the other
# three are already symlinked in /home/z/hf from an earlier fetch.
#
# Protocol is the shared frozen panel (panel_mpl.sh): ctx 4096, KV q8_0/q8_0,
# top_p .95 / top_k 40 / min_p .05, raw completion, greedy, 768 max tokens, cpp+py.
# Every model passes a real-completion load gate before its panel (a healthy
# /health only proves the weights parsed).
#
# Rows: m33_summary.jsonl = 4 models x 2 langs = 8.
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m33.log
SUM=$W/m33_summary.jsonl
export LOG
echo "=== M33 start $(date) ===" >> "$LOG"

# repo : file : tag
PANELS=(
  "bartowski/MiniCPM5-2B-GGUF:MiniCPM5-2B-Q3_K_M.gguf:minicpm5-2b-q3"
  "unsloth/NVIDIA-Nemotron-3-Nano-4B-GGUF:NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL.gguf:nemotron3-4b-q3"
  "ornith-ai/Ornith-1.5-9B-GGUF:Ornith-1.5-9B-Q4_K_M.gguf:ornith9b-q4"
  "unsloth/GLM-4.7-Flash-GGUF:GLM-4.7-Flash-UD-Q3_K_XL.gguf:glm47flash-q3"
)
for spec in "${PANELS[@]}"; do
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M33] SKIP $tag: $repo/$file unavailable on ModelScope" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" \
    || echo "[M33] FAIL $tag" >> "$LOG"
done

echo "=== M33 end $(date) ===" >> "$LOG"
