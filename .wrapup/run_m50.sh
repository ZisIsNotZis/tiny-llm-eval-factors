#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M50 (NEXT_DRIVER N1) — BRAINSTORM 1B: does the imatrix (IQ*) scheme buy SCORE
# PER BYTE over a plain K-quant? We have compared levels, never schemes at EQUAL
# file size. The pairs below are chosen so the two members are within ~3% of each
# other in on-disk bytes:
#   Qwen3.5-4B  UD-IQ3_XXS (1859 MB) vs UD-Q2_K_XL (1851 MB)  <- 0.4% size match
#   Qwen3.5-2B  UD-IQ3_XXS ( 889 MB) vs UD-Q2_K_XL ( 922 MB)  <- 3.5% size match
# (Sizes are symlink-resolved on-disk bytes, verified 2026-10-07.)
# Same frozen protocol as m38/m42 (panel_mpl.sh: raw completion, greedy, ctx 4096,
# KV q8_0, 768 max tokens) so the rows join the existing anchors. This is a
# *scheme* axis (imatrix vs not) holding bytes roughly constant, which the level
# series cannot answer.
#
# Rows: m50_summary.jsonl = 4 models x cpp+py = 8.
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m50.log
SUM=$W/m50_summary.jsonl
export LOG
echo "=== M50 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "Qwen3.5-4B-UD-IQ3_XXS.gguf:qwen4b-iq3xxs"
  "Qwen3.5-4B-UD-Q2_K_XL.gguf:qwen4b-q2kxl"
  "Qwen3.5-2B-UD-IQ3_XXS.gguf:qwen2b-iq3xxs"
  "Qwen3.5-2B-UD-Q2_K_XL.gguf:qwen2b-q2kxl"
)
for spec in "${PANELS[@]}"; do
  file="${spec%%:*}"; tag="${spec##*:}"
  if [ ! -e "/home/z/hf/$file" ]; then echo "[M50] SKIP $tag: $file missing" >> "$LOG"; continue; fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" \
    "mpl-raw-greedy-768-iq-vs-k-size-matched" \
    || echo "[M50] FAIL $tag" >> "$LOG"
done
echo "=== M50 end $(date) ===" >> "$LOG"
