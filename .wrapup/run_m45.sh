#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M45 (QUEUE #19) — Tier 5A/2B architecture breadth: LFM2.5-8B-A1B (Liquid MoE).
#
# A new MoE family with a *within-model* Q2 -> Q3 pair already on disk, so it adds
# a clean quant slope on an architecture family the study has never crossed
# (BRAINSTORM 5A: "adds rows to every cross-family table"; 2B: expert structure
# as predictor). LFM2.5-8B-A1B is 8B total / 1B active — a much sparser active
# fraction than gemma-4-26B-A4B, so it sharpens the total-vs-active predictor.
#
# Both files are on disk (no download). Same frozen protocol as m33/m38/m39.
#
# Rows: m45_summary.jsonl = 2 quants x 2 langs = 4.
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m45.log
SUM=$W/m45_summary.jsonl
export LOG
echo "=== M45 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "unsloth/LFM2.5-8B-A1B-GGUF:LFM2.5-8B-A1B-UD-Q2_K_XL.gguf:lfm25-8a1b-q2"
  "unsloth/LFM2.5-8B-A1B-GGUF:LFM2.5-8B-A1B-UD-Q3_K_XL.gguf:lfm25-8a1b-q3"
)
for spec in "${PANELS[@]}"; do
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M45] SKIP $tag: $repo/$file unavailable" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" \
    || echo "[M45] FAIL $tag" >> "$LOG"
done

echo "=== M45 end $(date) ===" >> "$LOG"
