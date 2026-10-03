#!/bin/bash
# Panel chain for the three worker-built queue entries, in priority order
# (SSOT 6b — the queue must never idle):
#   1. run_m32.sh  QUEUE #6  ternary Bonsai 27B on BFCL multi-turn + long_context
#   2. run_m30.sh  QUEUE #4  KV-quant x ctx grid (2B Q3, cpp)
#   3. run_m31.sh  QUEUE #5  top_k x quant (2B Q2/Q3/Q4, cpp+py)
#
# It waits for the already-armed m29 panel (m29_launch.sh) to exit, then runs the
# three panels one at a time, each inside its own gpu_locked.sh invocation (so the
# flock also serialises against any other panel that appears meanwhile, and a
# panel that dies cannot stay off the lock). Status/progress goes to m30_32.log.
#
# Last step: hand the GPU to the next QUEUE.md entry if a script for it exists;
# otherwise log that the queue is empty so the idle is visible in the log.
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/m30_32.log
echo "=== M32/M30/M31 chain armed $(date) ===" >> "$LOG"

# m29 is already launched and holds/will hold the GPU; wait for its process.
while pgrep -f "[r]un_m29.sh" >/dev/null 2>&1 || pgrep -f "[m]29_launch.sh" >/dev/null 2>&1; do
  sleep 30
done
echo "[chain] m29 drained $(date)" >> "$LOG"

for p in run_m32.sh run_m30.sh run_m31.sh; do
  echo "[chain] start $p $(date)" >> "$LOG"
  bash "$W/gpu_locked.sh" bash "$W/$p"
  echo "[chain] $p rc=$? $(date)" >> "$LOG"
done
echo "[chain] m32/m30/m31 complete $(date)" >> "$LOG"

# SSOT 6b: launch the successor entry if its script has been built.
if [ -f "$W/run_m33.sh" ]; then
  echo "[chain] launching QUEUE #7 (run_m33.sh) $(date)" >> "$LOG"
  exec bash "$W/gpu_locked.sh" bash "$W/run_m33.sh"
fi
echo "[chain] STOP $(date): QUEUE #7..#9 (m33/m34/m35) have no script yet -> GPU idles until one is built" >> "$LOG"
