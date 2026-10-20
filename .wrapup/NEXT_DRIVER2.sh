#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# NEXT_DRIVER2.sh — successor queue for NEXT_DRIVER.sh (SSOT 6b anti-idle).
#
# NEXT_DRIVER.sh hands over with `locked bash NEXT_DRIVER2.sh`, i.e. this script
# starts WHILE /tmp/llama_gpu.lock is already held by an ancestor (the driver chain
# `exec`s its successor). `locked()` therefore takes the lock itself only when it
# is NOT already held, so the script is correct both in the handover and standalone.
#
# Why this successor exists: the old chain drained in ~20 min because its remaining
# entries (m34/m40/m53) all failed the load gate with 0 rows (unsupported ggml
# types, no ModelScope release). These entries are the replacements. Order is
# cheapest-and-certain first so rows start landing immediately:
#   E1 m56  LFM2.5-8B-A1B  Q2/Q3 x {java,js}     (Tier 5B power; on disk)
#   E2 m57  Nemotron-3-4B  Q2/Q3 x {java,js}     (Tier 5B power; on disk)
#   E3 m60  Ornith-1.5-9B  Q4/Q5 x {rust,ruby}   (Tier 5B power; on disk)
#   E4 m58  Llama-3.2-3B   Q2/Q3 x {cpp,py}      (Tier 5A new family; fetch-gated)
#   E5 m59  Phi-4-mini     Q2/Q3 x {cpp,py}      (Tier 5A new family; fetch-gated)
#   E6 m55  expert-wise mixed-precision (Tier 1A; CPU prebuild + gate)
#   E7 m32  ternary Bonsai multi-turn_base (demoted repair, 1/2 rows after 3 tries)
#
# Idempotent (summary row count / null check), never stops on failure, logs
# START/DONE/FAIL/SKIP to .wrapup/NEXT_DRIVER2.log.
set -u
W=${REPO_ROOT}/.wrapup
LOG=$W/NEXT_DRIVER2.log
echo "=== NEXT_DRIVER2 start $(date) pid=$$ ===" >> "$LOG"

locked() {
  if flock -n /tmp/llama_gpu.lock true >/dev/null 2>&1; then
    bash "$W/gpu_locked.sh" "$@"
  else
    "$@"
  fi
}

nlines() { if [ -f "$1" ]; then wc -l < "$1"; else echo 0; fi; }
nnull()  { if [ -f "$1" ]; then grep -c '"accuracy": *null' "$1" 2>/dev/null || true; else echo 0; fi; }

run_step() {  # kind name script summary need
  local kind="$1" name="$2" script="$3" summary="$4" need="$5"
  local have nulls rc
  have=$(nlines "$summary"); nulls=$(nnull "$summary")
  if [ "${have:-0}" -ge "$need" ] && { [ "$kind" = mpl ] || [ "${nulls:-0}" -eq 0 ]; }; then
    echo "[next2] SKIP $name: summary complete ($have/$need, nulls=$nulls) $(date)" >> "$LOG"; return 0
  fi
  [ -f "$script" ] || { echo "[next2] SKIP $name: script $script missing $(date)" >> "$LOG"; return 0; }
  echo "[next2] START $name $(date) [$script]" >> "$LOG"
  locked bash "$script"; rc=$?
  have=$(nlines "$summary"); nulls=$(nnull "$summary")
  if [ "$rc" -eq 0 ] && [ "${have:-0}" -ge "$need" ] && { [ "$kind" = mpl ] || [ "${nulls:-0}" -eq 0 ]; }; then
    echo "[next2] DONE $name ($have/$need, nulls=$nulls) $(date)" >> "$LOG"
  else
    echo "[next2] FAIL $name rc=$rc ($have/$need, nulls=$nulls) -> moving on $(date)" >> "$LOG"
  fi
}

run_step mpl  "E1 m56 LFM2.5-8B-A1B java+js power" \
              "$W/run_m56.sh" "$W/m56_summary.jsonl" 4
run_step mpl  "E2 m57 Nemotron-3-4B java+js power" \
              "$W/run_m57.sh" "$W/m57_summary.jsonl" 4
run_step mpl  "E3 m60 Ornith-1.5-9B rust+ruby power" \
              "$W/run_m60.sh" "$W/m60_summary.jsonl" 4
run_step mpl  "E4 m58 Llama-3.2-3B new family (fetch+gate)" \
              "$W/run_m58.sh" "$W/m58_summary.jsonl" 4
run_step mpl  "E5 m59 Phi-4-mini new family (fetch+gate)" \
              "$W/run_m59.sh" "$W/m59_summary.jsonl" 4
run_step mpl  "E6 m55 expert-wise mixed-precision (Tier 1A)" \
              "$W/run_m55.sh" "$W/m55_summary.jsonl" 2
# Demoted: m32 has failed three times (1/2 rows; the model serves but the category
# never completes in GEN_TO). Kept last so it cannot block the new science.
# RUN_M32=0 lets the standalone watchdog re-run the queue without paying for it twice.
if [ "${RUN_M32:-1}" = 1 ]; then
  run_step bfcl "E7 m32 ternary Bonsai multi-turn base (repair)" \
                "$W/run_m32.sh" "$W/m32_summary.jsonl" 2
fi

echo "=== NEXT_DRIVER2 complete $(date): E1..E7 drained. ===" >> "$LOG"
