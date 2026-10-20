#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M35 (QUEUE #9) — sub-2-bit model sweep: turn the single ternary point (Bonsai 27B,
# Finding 8) into a class of sub-2-bit observations across schemes and families.
#
# Candidates (each resolved from ModelScope, load-gated, then run on the shared
# frozen MultiPL-E cpp+py panel):
#   * Ternary-Bonsai-4B-Q2_0_g64  — ternary, a NEW size point on the Bonsai curve
#     (1.6 bpw class: only 1.7B/8B/27B existed before)
#   * Bonsai-27B-Q1_0            — a 1-bit (Bonsai gen-1) release: the extreme end
#   * Qwen3.5-35B-A3B-IQ1_M      — a completely different scheme (imatrix IQ1) AND a
#     MoE family, so it tests whether sub-2-bit damage is Bonsai-specific or general
# Note Ternary-Bonsai-2-27B (gen-2) and GLM-4.7-Flash-UD-TQ1_0 are handled by m34/m39.
#
# Rows: m35_summary.jsonl = 3 models x 2 langs = 6 (models that load).
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m35.log
SUM=$W/m35_summary.jsonl
export LOG
echo "=== M35 start $(date) ===" >> "$LOG"

# repo : file : tag
PANELS=(
  "prism-ml/Ternary-Bonsai-4B-gguf:Ternary-Bonsai-4B-Q2_0_g64.gguf:bonsai4b-ternary"
  "prism-ml/Bonsai-27B-gguf:Bonsai-27B-Q1_0.gguf:bonsai27b-1bit"
  "Manojb/Qwen_Qwen3.5-35B-A3B-IQ1_M.gguf:Qwen_Qwen3.5-35B-A3B-IQ1_M.gguf:qwen35-35a3b-iq1m"
)
for spec in "${PANELS[@]}"; do
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M35] SKIP $tag: $repo/$file unavailable on ModelScope" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" \
    || echo "[M35] FAIL $tag" >> "$LOG"
done

echo "=== M35 end $(date) ===" >> "$LOG"
