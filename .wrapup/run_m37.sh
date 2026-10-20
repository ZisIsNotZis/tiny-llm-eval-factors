#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M37 (NEW QUEUE entry) — Tier 1A cheap precursor: the "half-finished expert-wise
# probe". BRAINSTORM 1A says the no-requantisation precursor is to compare EXISTING
# recipes from different providers for the SAME MoE at matched file size: does the
# label (Unsloth "UD" dynamic vs a plain K-quant) predict score beyond file size?
#
# A matched-size pair exists on disk for Qwen3.6-35B-A3B (the MoE anchor):
#   Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf   17.23 GB   (unsloth UD dynamic)
#   Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf  17.12 GB   (bartowski plain Q3_K_M)
# Same nominal level (Q3_K), ~0.6% size difference, same base model, different
# provider/scheme -> the closest thing to a controlled "scheme, not level" test we
# can run with zero requantisation (SSOT 1A: needs an F16 source otherwise).
#
# Protocol is the shared frozen panel (panel_mpl.sh), cpp+py. Rows:
# m37_summary.jsonl = 2 models x 2 langs = 4.
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m37.log
SUM=$W/m37_summary.jsonl
export LOG
echo "=== M37 start $(date) ===" >> "$LOG"

# file present on disk -> resolve_model.sh exits 0 without a download
PANELS=(
  "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf:qwen36-35a3b-udq3kxl"
  "bartowski/Qwen_Qwen3.6-35B-A3B-GGUF:Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf:qwen36-35a3b-q3km"
)
for spec in "${PANELS[@]}"; do
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M37] SKIP $tag: $repo/$file unavailable" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" \
    || echo "[M37] FAIL $tag" >> "$LOG"
done

echo "=== M37 end $(date) ===" >> "$LOG"
