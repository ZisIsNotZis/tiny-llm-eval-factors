#!/bin/bash
# Run the three repaired panels (m32b -> m31 -> m30b) once the concurrent
# QUEUE_DRIVER.sh workstream has released the GPU.
#
# WHY A POLL INSTEAD OF `gpu_locked.sh`: QUEUE_DRIVER.sh holds /tmp/llama_gpu.lock
# for several hours (QUEUE #7..#13). A waiter started now would sit on flock and
# die on its 6 h timeout without running anything. So this script waits for the
# driver *process* to exit first (no lock held by us, no GPU touched), then takes
# the lock normally — by then the wait is short.
#
# Each panel is retried up to 3 times: a lock timeout or a transient load failure
# drops one panel without killing the run, and every panel is idempotent (it
# rewrites its own summary from scratch).
#
# Launch detached:
#   setsid nohup bash /home/z/hf/research/.wrapup/run_fixes_after_driver.sh \
#       >>/home/z/hf/research/.wrapup/fixes_after_driver.log 2>&1 &
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/fixes_after_driver.log
DLOG=$W/QUEUE_DRIVER.log
echo "=== fixes_after_driver armed $(date) pid=$$ ===" >> "$LOG"

# 1) Wait for the driver to finish. Ground truth is the process exiting; the log
#    banner is reported when present (the driver prints "QUEUE_DRIVER complete",
#    not "end", so match either).
waited=0
while pgrep -f "[Q]UEUE_DRIVER.sh" >/dev/null 2>&1; do
  [ $((waited % 1800)) -eq 0 ] && echo "[fixes] waiting for QUEUE_DRIVER.sh $(date)" >> "$LOG"
  sleep 60; waited=$((waited + 60))
  if [ "$waited" -ge 129600 ]; then   # 36 h bound
    echo "[fixes] ABORT: driver still running after 36 h $(date)" >> "$LOG"; exit 1
  fi
done
if grep -qE "QUEUE_DRIVER (end|complete)" "$DLOG" 2>/dev/null; then
  echo "[fixes] driver finished: $(grep -E 'QUEUE_DRIVER (end|complete)' "$DLOG" | tail -1)" >> "$LOG"
else
  echo "[fixes] WARNING: QUEUE_DRIVER.sh process gone but no end banner in $DLOG; proceeding" >> "$LOG"
fi

# 2) Make sure no other panel is mid-flight before taking the lock (a successor
#    driver would have been exec'd in place of QUEUE_DRIVER.sh).
#    Ground truth for "a panel holds the GPU" is /tmp/llama_gpu.lock: every panel
#    runs under gpu_locked.sh. Do NOT probe for llama-server processes by model
#    path — other projects (e.g. /home/z/vibe/helpagent) serve models from
#    /home/z/hf/ with a long-lived llama-server, which made the old
#    `pgrep -f "[l]lama-server .*-m /home/z/hf/"` clause a permanent false
#    positive (observed stalled 15:55-16:14 after the driver finished).
while pgrep -f "[r]un_m[0-9].*\.sh" >/dev/null 2>&1 \
   || pgrep -f "[c]hain_.*\.sh" >/dev/null 2>&1 \
   || ! flock -n /tmp/llama_gpu.lock true >/dev/null 2>&1; do
  echo "[fixes] another panel still live, waiting $(date)" >> "$LOG"
  sleep 60
done
echo "[fixes] GPU free, starting the repaired panels $(date)" >> "$LOG"

# 3) Run the repaired panels in the approved order, each under the lock.
run_panel() {  # script summary need
  local p="$1" sum="$2" need="$3" i have rc
  for i in 1 2 3; do
    echo "[fixes] start $p (attempt $i) $(date)" >> "$LOG"
    bash "$W/gpu_locked.sh" bash "$W/$p" >> "$LOG" 2>&1
    rc=$?
    have=0; [ -f "$sum" ] && have=$(wc -l < "$sum")
    echo "[fixes] $p rc=$rc rows=$have/$need $(date)" >> "$LOG"
    if [ "$rc" -eq 0 ] && [ "$have" -ge "$need" ]; then return 0; fi
    sleep 30
  done
  return 1
}

run_panel run_m32b.sh "$W/m32_summary.jsonl" 2
run_panel run_m31.sh  "$W/m31_summary.jsonl" 30
run_panel run_m30b.sh "$W/m30_summary.jsonl" 12

echo "=== fixes_after_driver complete $(date) ===" >> "$LOG"
