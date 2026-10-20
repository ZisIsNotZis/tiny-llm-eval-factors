#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M51 (NEXT_DRIVER N2) — Tier 5B power, step 3: a THIRD anchor for the multilingual
# code claim, in a NEW architecture family (gemma-4, after Qwen2B/2B in m38/m42).
# Adding java+js for gemma-4-12B Q2->Q3 raises the item count on a second,
# independent anchor rather than re-running an existing one (SSOT 5C: the fix for a
# headline CI is items, not runs).
#
# Rows: m51_summary.jsonl = 2 anchors x java+js = 4.  Same frozen protocol (panel_mpl.sh).
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m51.log
SUM=$W/m51_summary.jsonl
export LOG
echo "=== M51 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "gemma-4-12b-it-UD-Q2_K_XL.gguf:gemma12b-q2"
  "gemma-4-12b-it-UD-Q3_K_XL.gguf:gemma12b-q3"
)
for spec in "${PANELS[@]}"; do
  file="${spec%%:*}"; tag="${spec##*:}"
  if [ ! -e "/home/z/hf/$file" ]; then echo "[M51] SKIP $tag: $file missing" >> "$LOG"; continue; fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "java js" \
    "mpl-raw-greedy-768-third-family-code" \
    || echo "[M51] FAIL $tag" >> "$LOG"
done
echo "=== M51 end $(date) ===" >> "$LOG"
