#!/bin/bash
# QUEUE_DRIVER.sh — keep the GPU busy through the whole QUEUE.md list with no session.
#
# Implements SSOT 6b (anti-idle): the driver is the single persisted queue runner.
# Each step runs in its own `gpu_locked.sh` invocation, so a step cannot stay off the
# lock, and each step's success/failure is logged as DONE / FAIL / SKIP. The driver
# NEVER stops on a failed step: a model that will not load, a download that 404s, or a
# panel that dies just moves on to the next entry. Re-running the driver is
# idempotent: a step whose summary is already complete is skipped (resume after crash).
#
# Launch detached (do not wait):
#   setsid nohup bash /home/z/hf/research/.wrapup/QUEUE_DRIVER.sh >>/home/z/hf/research/.wrapup/QUEUE_DRIVER.log 2>&1 &
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/QUEUE_DRIVER.log
echo "=== QUEUE_DRIVER armed $(date) pid=$$ ==="

# Do not start a queue step while another panel already holds the GPU. The current
# m30/m31/m32 chain is already drained, but this makes a re-arm safe at any time.
wait_for_gpu_idle() {
  while pgrep -f "[r]un_m[0-9].*\.sh" >/dev/null 2>&1 \
     || pgrep -f "[l]lama-server .*-m /home/z/hf/" >/dev/null 2>&1; do
    echo "[driver] waiting for a running panel to drain $(date)"; sleep 60
  done
  echo "[driver] GPU idle, starting queue $(date)"
}

nlines() { if [ -f "$1" ]; then wc -l < "$1"; else echo 0; fi; }
nnull()  { if [ -f "$1" ]; then grep -c '"accuracy": *null' "$1" 2>/dev/null || true; else echo 0; fi; }

# run_step <kind> <name> <script> <summary> <need>
#   kind= mpl or bfcl ; need= expected summary lines for "complete"
run_step() {
  local kind="$1" name="$2" script="$3" summary="$4" need="$5"
  local have nulls rc
  have=$(nlines "$summary"); nulls=$(nnull "$summary")
  if [ "${have:-0}" -ge "$need" ] && { [ "$kind" = mpl ] || [ "${nulls:-0}" -eq 0 ]; }; then
    echo "[driver] SKIP $name: summary already complete ($have/$need, nulls=$nulls)"; return 0
  fi
  if [ ! -f "$script" ]; then
    echo "[driver] SKIP $name: script $script not found"; return 0
  fi
  echo "[driver] START $name $(date) [$script]"
  bash "$W/gpu_locked.sh" bash "$script"; rc=$?
  have=$(nlines "$summary"); nulls=$(nnull "$summary")
  if [ "$rc" -eq 0 ] && [ "${have:-0}" -ge "$need" ] && { [ "$kind" = mpl ] || [ "${nulls:-0}" -eq 0 ]; }; then
    echo "[driver] DONE $name rc=0 ($have/$need, nulls=$nulls) $(date)"
  else
    echo "[driver] FAIL $name rc=$rc ($have/$need, nulls=$nulls) -> moving on $(date)"
  fi
}

wait_for_gpu_idle

run_step mpl  "QUEUE#7  m33 family breadth (MiniCPM5/Nemotron/Ornith/GLM)" \
              "$W/run_m33.sh" "$W/m33_summary.jsonl" 8
run_step mpl  "QUEUE#8  m34 third-party ternary/1-bit family" \
              "$W/run_m34.sh" "$W/m34_summary.jsonl" 2
run_step mpl  "QUEUE#9  m35 sub-2-bit sweep (Bonsai4B/1bit/IQ1_M)" \
              "$W/run_m35.sh" "$W/m35_summary.jsonl" 6
run_step bfcl "QUEUE#10 m36 ternary Bonsai miss_func/miss_param" \
              "$W/run_m36.sh" "$W/m36_summary.jsonl" 2
run_step mpl  "QUEUE#11 m37 Tier1A matched-size MoE scheme pair" \
              "$W/run_m37.sh" "$W/m37_summary.jsonl" 4
run_step mpl  "QUEUE#12 m38 Tier5B java+js statistical power" \
              "$W/run_m38.sh" "$W/m38_summary.jsonl" 4
run_step mpl  "QUEUE#13 m39 second ternary family (GLM-4.7-Flash TQ1_0)" \
              "$W/run_m39.sh" "$W/m39_summary.jsonl" 4

# SSOT 6b: a chain's last step launches the next entry if one exists. If a future
# driver/successor is written, hand over; otherwise say so loudly so an idle GPU is
# visible in the log rather than silent.
if [ -f "$W/NEXT_DRIVER.sh" ]; then
  echo "[driver] handing over to NEXT_DRIVER.sh $(date)"
  exec bash "$W/gpu_locked.sh" bash "$W/NEXT_DRIVER.sh"
fi
echo "=== QUEUE_DRIVER complete $(date): QUEUE.md #7..#13 drained. GPU now IDLE; add entries or re-arm. ==="
