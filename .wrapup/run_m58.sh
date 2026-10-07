#!/bin/bash
# M58 (Tier 5A architecture-family breadth) — Llama-3.2-3B-Instruct Q2_K / Q3_K_M.
#
# A family the study has never crossed (no Llama-architecture anchor at all).
# Downloaded + CPU-load-gated by m55_prebuild.sh; this runner only runs the panel
# for a model whose load gate recorded PASS, so an unverified GGUF can never take
# a GPU slot (the m34/m40/m53 failure mode).
#
# Rows: m58_summary.jsonl = 2 levels x {cpp, py} = 4.
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m58.log
SUM=$W/m58_summary.jsonl
export LOG
echo "=== M58 start $(date) ===" >> "$LOG"
: > "$SUM"

PANELS=(
  "Llama-3.2-3B-Instruct-Q2_K.gguf:llama32-3b-q2"
  "Llama-3.2-3B-Instruct-Q3_K_M.gguf:llama32-3b-q3"
)
for spec in "${PANELS[@]}"; do
  file="${spec%%:*}"; tag="${spec##*:}"
  if [ ! -e "/home/z/hf/$file" ]; then echo "[M58] SKIP $tag: $file missing" >> "$LOG"; continue; fi
  if ! bash "$W/lg_state.sh" "$file" >/dev/null 2>&1; then
    echo "[M58] SKIP $tag: load gate not PASS ($(bash "$W/lg_state.sh" "$file"))" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" "mpl-raw-greedy-768-new-family" \
    || echo "[M58] FAIL $tag" >> "$LOG"
done
echo "=== M58 end $(date) ===" >> "$LOG"
