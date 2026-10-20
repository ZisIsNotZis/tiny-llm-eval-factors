#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# arm_next2.sh — detached safety net for the NEXT_DRIVER2.sh queue (SSOT 6b).
#
# The live chain QUEUE_DRIVER.sh -> NEXT_DRIVER.sh -> NEXT_DRIVER2.sh should carry
# the new entries by itself. This watchdog exists because (a) a chain has died
# silently before and left the GPU idle, and (b) m55 depends on a CPU/network
# prebuild (m55_prebuild.sh) that may not be finished when the chain first reaches
# it. It polls the REAL ground truth (`flock -n /tmp/llama_gpu.lock`) until the GPU
# is free, runs NEXT_DRIVER2 once with RUN_M32=0 (the main chain runs m32; do not
# pay for a second 2 h attempt), then re-runs it a few times (spaced out) until the
# new summaries are complete or the attempts are exhausted.
#
# NEXT_DRIVER2 is idempotent, so a pass over completed entries is all SKIPs.
#
# Launch detached:
#   setsid nohup bash .wrapup/arm_next2.sh >>.wrapup/arm_next2.log 2>&1 &
set -u
W=${REPO_ROOT}/.wrapup
LOG=$W/arm_next2.log
echo "=== arm_next2 start $(date) pid=$$ ===" >> "$LOG"

done_ok() {  # all of the row-producing entries have their expected rows
  local spec f need have
  for spec in m56:4 m57:4 m60:4 m58:4 m59:4 m55:2; do
    f=$W/${spec%%:*}_summary.jsonl; need=${spec##*:}
    have=0; [ -f "$f" ] && have=$(wc -l < "$f")
    [ "${have:-0}" -ge "$need" ] || return 1
  done
  return 0
}

for attempt in 1 2 3 4 5 6; do
  if done_ok; then echo "[arm_next2] all entries complete, nothing to do $(date)" >> "$LOG"; break; fi
  while ! flock -n /tmp/llama_gpu.lock true >/dev/null 2>&1; do sleep 60; done
  echo "[arm_next2] GPU free, run $attempt of NEXT_DRIVER2 (RUN_M32=0) $(date)" >> "$LOG"
  RUN_M32=0 bash "$W/gpu_locked.sh" bash "$W/NEXT_DRIVER2.sh" >> "$LOG" 2>&1
  done_ok && { echo "[arm_next2] entries complete after run $attempt $(date)" >> "$LOG"; break; }
  sleep 300
done
echo "=== arm_next2 done $(date) ===" >> "$LOG"
