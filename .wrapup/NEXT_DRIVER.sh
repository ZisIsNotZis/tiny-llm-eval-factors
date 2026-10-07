#!/bin/bash
# NEXT_DRIVER.sh — successor queue for QUEUE_DRIVER.sh (SSOT 6b anti-idle).
#
# QUEUE_DRIVER.sh probes for this file after #19 and does
#   exec bash gpu_locked.sh bash NEXT_DRIVER.sh
# so this script runs WHILE ALREADY HOLDING /tmp/llama_gpu.lock (flock is an
# inherited open-file-description; a *nested* `flock` on the same file from a
# child would block for its full 21600 s timeout -> deadlock). The `locked()`
# helper therefore takes the lock itself only when it is NOT already held, which
# keeps the script correct both under the driver handover and if launched standalone.
#
# Step order (m36 first: it is a REPAIR of a failed existing entry, so it must not
# wait behind the new science):
#   N0 m36  ternary Bonsai multi-turn miss_func/miss_param  (repair, --partial-eval)
#   N1 m50  imatrix-vs-K at MATCHED file size (does IQ buy score per byte?)
#   N2 m51  gemma-4-12B java+js (third-family multilingual-code anchor)
#   N3 m52  speed/draft: decode t/s prose vs code (+ spec-draft length sweep)
#   N4 m53  ModelScope ternary/1-bit search + load-gated probe (new family)
#
# Idempotent (a step whose summary already has `need` rows — and, for BFCL, zero
# nulls — is SKIPped). Never stops on failure. Logs START/DONE/FAIL/SKIP.
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/NEXT_DRIVER.log
echo "=== NEXT_DRIVER start $(date) pid=$$ ===" >> "$LOG"

# Run "$@" under the GPU lock, unless an ancestor already holds it.
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
    echo "[next] SKIP $name: summary complete ($have/$need, nulls=$nulls) $(date)" >> "$LOG"; return 0
  fi
  [ -f "$script" ] || { echo "[next] SKIP $name: script $script missing $(date)" >> "$LOG"; return 0; }
  echo "[next] START $name $(date) [$script]" >> "$LOG"
  locked bash "$script"; rc=$?
  have=$(nlines "$summary"); nulls=$(nnull "$summary")
  if [ "$rc" -eq 0 ] && [ "${have:-0}" -ge "$need" ] && { [ "$kind" = mpl ] || [ "${nulls:-0}" -eq 0 ]; }; then
    echo "[next] DONE $name ($have/$need, nulls=$nulls) $(date)" >> "$LOG"
  else
    echo "[next] FAIL $name rc=$rc ($have/$need, nulls=$nulls) -> moving on $(date)" >> "$LOG"
  fi
}

run_step bfcl "N0 m36 repair (Bonsai miss_func/miss_param)" \
              "$W/run_m36.sh" "$W/m36_summary.jsonl" 2
run_step mpl  "N1 m50 imatrix-vs-K at matched file size" \
              "$W/run_m50.sh" "$W/m50_summary.jsonl" 8
run_step mpl  "N2 m51 gemma-4-12B java+js (third-family code anchor)" \
              "$W/run_m51.sh" "$W/m51_summary.jsonl" 4
run_step mpl  "N3 m52 speed/draft prose vs code" \
              "$W/run_m52.sh" "$W/m52_summary.jsonl" 4
run_step mpl  "N4 m53 ModelScope ternary/1-bit search + probe" \
              "$W/run_m53.sh" "$W/m53_summary.jsonl" 2
# N5/N6 added 2026-10-07: N0-N4 had drained (GPU idle 16:35->19:14) and these two
# are the only script-ready panels whose summaries are still short: m44 (0/6 rows,
# harness bug fixed in run_m44.sh: probe ctx 4096 -> 16384) and m32 (1/2 rows,
# ternary Bonsai multi-turn_base, repaired with preflight + --partial-eval).
run_step mpl  "N5 m44 compute-precision probe (repair: probe ctx 4096->16384)" \
              "$W/run_m44.sh" "$W/m44_summary.jsonl" 6
run_step bfcl "N6 m32 ternary Bonsai multi-turn base (repair, 1/2 rows)" \
              "$W/run_m32.sh" "$W/m32_summary.jsonl" 2

if [ -f "$W/NEXT_DRIVER2.sh" ]; then
  echo "[next] handing over to NEXT_DRIVER2.sh $(date)" >> "$LOG"
  locked bash "$W/NEXT_DRIVER2.sh"
fi
echo "=== NEXT_DRIVER complete $(date): N0..N6 drained. GPU now IDLE; add entries or re-arm. ===" >> "$LOG"
