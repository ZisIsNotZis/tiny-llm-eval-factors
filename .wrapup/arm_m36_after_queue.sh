#!/bin/bash
# arm_m36_after_queue.sh — detached safety-net armer for the m36 repair (QUEUE #10).
#
# The current QUEUE_DRIVER.sh already ran #10 (and recorded 2 nulls) and is now on
# #11..#19; it will not revisit #10. This script polls until the GPU is genuinely
# idle (no run_m*.sh, no QUEUE_DRIVER/NEXT_DRIVER, and /tmp/llama_gpu.lock free via
# a NON-BLOCKING flock probe — never blocks on the lock) and then runs the repaired
# run_m36.sh under gpu_locked.sh.
#
# It is idempotent: if m36_summary.jsonl already holds >=2 rows with zero nulls (the
# NEXT_DRIVER.sh step-0 path may have completed it first), it logs SKIP and exits.
#
# Launch detached:
#   setsid nohup bash .wrapup/arm_m36_after_queue.sh >>.wrapup/m36_arm.log 2>&1 &
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/m36_arm.log
SUM=$W/m36_summary.jsonl
echo "=== m36 armer start $(date) pid=$$ ===" >> "$LOG"

while pgrep -f "[r]un_m[0-9].*\.sh" >/dev/null 2>&1 \
   || pgrep -f "[Q]UEUE_DRIVER.sh" >/dev/null 2>&1 \
   || pgrep -f "[N]EXT_DRIVER.sh" >/dev/null 2>&1 \
   || ! flock -n /tmp/llama_gpu.lock true >/dev/null 2>&1; do
  sleep 60
done
echo "[armer] GPU idle, driver chain drained $(date)" >> "$LOG"

n=$([ -f "$SUM" ] && wc -l < "$SUM" || echo 0)
nulls=$([ -f "$SUM" ] && grep -c '"accuracy": *null' "$SUM" 2>/dev/null || true)
if [ "${n:-0}" -ge 2 ] && [ "${nulls:-0}" -eq 0 ]; then
  echo "[armer] SKIP: m36 summary already complete ($n rows, nulls=$nulls) $(date)" >> "$LOG"
  exit 0
fi

echo "[armer] launching m36 repair $(date)" >> "$LOG"
setsid nohup bash "$W/gpu_locked.sh" bash "$W/run_m36.sh" >> "$LOG" 2>&1 &
echo "[armer] m36 pid=$! $(date)" >> "$LOG"
