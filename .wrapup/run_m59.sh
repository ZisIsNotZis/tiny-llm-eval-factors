#!/bin/bash
# M59 (Tier 5A architecture-family breadth) — Microsoft Phi-4-mini-instruct Q2_K / Q3_K_M.
#
# Second new family (Phi) for the cross-family table; downloaded + CPU-load-gated
# by m55_prebuild.sh, and only run when its load gate recorded PASS.
#
# Rows: m59_summary.jsonl = 2 levels x {cpp, py} = 4.
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m59.log
SUM=$W/m59_summary.jsonl
export LOG
echo "=== M59 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "Phi-4-mini-instruct-Q2_K.gguf:phi4mini-q2"
  "Phi-4-mini-instruct-Q3_K_M.gguf:phi4mini-q3"
)
for spec in "${PANELS[@]}"; do
  file="${spec%%:*}"; tag="${spec##*:}"
  if [ ! -e "/home/z/hf/$file" ]; then echo "[M59] SKIP $tag: $file missing" >> "$LOG"; continue; fi
  if ! bash "$W/lg_state.sh" "$file" >/dev/null 2>&1; then
    echo "[M59] SKIP $tag: load gate not PASS ($(bash "$W/lg_state.sh" "$file"))" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" "mpl-raw-greedy-768-new-family" \
    || echo "[M59] FAIL $tag" >> "$LOG"
done
echo "=== M59 end $(date) ===" >> "$LOG"
