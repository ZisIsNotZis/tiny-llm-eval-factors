#!/bin/bash
# Arm the repaired m32 (Ternary-Bonsai-27B BFCL multi-turn, QUEUE #6) BEHIND the
# current fixes chain `run_fixes_after_driver.sh` (m31 -> m30b). This worker must
# not block on /tmp/llama_gpu.lock, so this script waits for the predecessor
# *process* to exit (never touching the lock), then takes the lock normally and
# runs run_m32b.sh. Up to two attempts, matching the two-preflight-attempt rule.
#
# It does NOT touch the lock while waiting. Launch detached:
#   setsid nohup bash /home/z/hf/research/.wrapup/arm_m32_after_fixes.sh \
#       >>/home/z/hf/research/.wrapup/m32_arm.log 2>&1 &
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/m32_arm.log
echo "=== arm_m32 armed $(date) pid=$$ ===" >> "$LOG"

# 1) Wait for the m31/m30b chain to finish. Process exit is the ground truth
#    (the driver holds the flock for its whole life).
waited=0
while pgrep -f "[r]un_fixes_after_driver\.sh" >/dev/null 2>&1 \
   || pgrep -f "[r]un_m31\.sh"            >/dev/null 2>&1 \
   || pgrep -f "[r]un_m30b\.sh"           >/dev/null 2>&1; do
  [ $((waited % 600)) -eq 0 ] && echo "[arm_m32] waiting for m31/m30b chain $(date)" >> "$LOG"
  sleep 30; waited=$((waited + 30))
  if [ "$waited" -ge 43200 ]; then
    echo "[arm_m32] ABORT: predecessor chain still running after 12 h $(date)" >> "$LOG"; exit 1
  fi
done
echo "[arm_m32] predecessor chain gone $(date)" >> "$LOG"

# 2) No one else holds the lock (non-blocking probe; never block on the lock).
while ! flock -n /tmp/llama_gpu.lock true >/dev/null 2>&1; do
  echo "[arm_m32] lock still held by another panel, waiting $(date)" >> "$LOG"
  sleep 60
done
echo "[arm_m32] lock free, starting m32b $(date)" >> "$LOG"

# 3) Run m32b under the lock, up to 2 attempts. run_m32b -> run_m32 does the two
#    preflight attempts and writes m32_BLOCKED.md (no null row) if it still fails.
for attempt in 1 2; do
  echo "[arm_m32] run_m32b.sh attempt $attempt $(date)" >> "$LOG"
  bash "$W/gpu_locked.sh" bash "$W/run_m32b.sh" >> "$LOG" 2>&1
  rc=$?
  rows=0; [ -f "$W/m32_summary.jsonl" ] && rows=$(wc -l < "$W/m32_summary.jsonl")
  echo "[arm_m32] run_m32b.sh rc=$rc rows=$rows $(date)" >> "$LOG"
  if [ "$rc" -eq 0 ] && [ "$rows" -ge 1 ]; then
    echo "=== arm_m32 DONE $(date) ===" >> "$LOG"; exit 0
  fi
  sleep 30
done
echo "=== arm_m32 FAILED after 2 attempts; see m32b.log + m32_BLOCKED.md $(date) ===" >> "$LOG"
exit 1
