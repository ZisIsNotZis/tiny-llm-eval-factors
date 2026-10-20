#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M57 (Tier 5B statistical power) — NVIDIA Nemotron-3-Nano-4B Q2/Q3 x {java, js}.
#
# A non-Qwen, non-gemma architecture family that already has cpp+py rows (m10,
# tags nem4b-q2/q3). Adding java+js on the same tags/protocol doubles the item
# count on this anchor (BRAINSTORM 5C). Files are on disk and already served by
# m10, so this panel is load-certain.
#
# Rows: m57_summary.jsonl = 2 quants x 2 langs = 4.  Protocol mpl-raw-greedy-768.
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m57.log
SUM=$W/m57_summary.jsonl
export LOG
echo "=== M57 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL.gguf:nem4b-q2"
  "NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL.gguf:nem4b-q3"
)
for spec in "${PANELS[@]}"; do
  file="${spec%%:*}"; tag="${spec##*:}"
  if [ ! -e "/home/z/hf/$file" ]; then echo "[M57] SKIP $tag: $file missing" >> "$LOG"; continue; fi
  st=$(bash "$W/lg_state.sh" "$file"); [ "$st" = FAIL ] && { echo "[M57] SKIP $tag: load gate FAIL" >> "$LOG"; continue; }
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "java js" "mpl-raw-greedy-768" \
    || echo "[M57] FAIL $tag" >> "$LOG"
done
echo "=== M57 end $(date) ===" >> "$LOG"
