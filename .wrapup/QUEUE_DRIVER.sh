#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# QUEUE_DRIVER.sh — keep the GPU busy through the whole QUEUE.md list with no session.
#
# Implements SSOT 6b (anti-idle): the driver is the single persisted queue runner.
# Each GPU step runs in its own `gpu_locked.sh` invocation, so a step cannot stay
# off the lock, and each step's success/failure is logged as DONE / FAIL / SKIP.
# The driver NEVER stops on a failed step: a model that will not load, a download
# that 404s, or a panel that dies just moves on to the next entry. Re-running the
# driver is idempotent: a step whose summary is already complete is skipped.
#
# CPU-only steps (m41 testfrac, m43 summary recovery) do NOT take the GPU lock:
# they never start a server, and holding the lock for them would only stall the
# GPU panels behind a compile/run workload.
#
# Launch detached (do not wait):
#   setsid nohup bash ${REPO_ROOT}/.wrapup/QUEUE_DRIVER.sh >>${REPO_ROOT}/.wrapup/QUEUE_DRIVER.log 2>&1 &
set -u
W=${REPO_ROOT}/.wrapup
LOG=$W/QUEUE_DRIVER.log
echo "=== QUEUE_DRIVER armed $(date) pid=$$ ==="

# Do not start a queue step while another panel already holds the GPU. Ground
# truth for "the GPU is busy" is /tmp/llama_gpu.lock (every panel runs under
# gpu_locked.sh). Do NOT probe for llama-server by model path: other projects
# serve models from /home/z/hf/ with a long-lived server, which made that clause
# a permanent false positive and left this queue idle 14:40-16:16 (QUEUE.md OPEN
# RISKS). The repaired fixes runner (run_fixes_after_driver.sh) must finish first.
wait_for_gpu_idle() {
  # Only the flock probe is authoritative: every panel runs under gpu_locked.sh.
  # Text-based pgrep gates are banned here -- they match ANY stray shell whose
  # command line merely mentions run_mNN.sh, which stalled this queue twice.
  while ! flock -n /tmp/llama_gpu.lock true >/dev/null 2>&1; do
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

# run_cpu_step: same bookkeeping, but no GPU lock (no llama-server is started).
run_cpu_step() {
  local name="$1" script="$2" summary="$3" need="$4"
  local have rc
  have=$(nlines "$summary")
  if [ "${have:-0}" -ge "$need" ]; then
    echo "[driver] SKIP $name: summary already complete ($have/$need)"; return 0
  fi
  if [ ! -f "$script" ]; then
    echo "[driver] SKIP $name: script $script not found"; return 0
  fi
  echo "[driver] START(cpu) $name $(date) [$script]"
  bash "$script"; rc=$?
  have=$(nlines "$summary")
  if [ "$rc" -eq 0 ] && [ "${have:-0}" -ge "$need" ]; then
    echo "[driver] DONE $name rc=0 ($have/$need) $(date)"
  else
    echo "[driver] FAIL $name rc=$rc ($have/$need) -> moving on $(date)"
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

# --- re-armed 2026-10-06 19:xx (QUEUE.md #14..#19) ------------------------------
run_cpu_step  "QUEUE#17 m43 recover Tier-2C (m26) summary [CPU]" \
              "$W/run_m43.sh" "$W/m26_summary.jsonl" 8
run_step mpl  "QUEUE#14 m40 ternary generalisation (third-party quantisers)" \
              "$W/run_m40.sh" "$W/m40_summary.jsonl" 2
run_step mpl  "QUEUE#18 m44 compute-precision probe (provable manipulation)" \
              "$W/run_m44.sh" "$W/m44_summary.jsonl" 6
run_step mpl  "QUEUE#16 m42 Tier5B rust+ruby statistical power" \
              "$W/run_m42.sh" "$W/m42_summary.jsonl" 4
run_step mpl  "QUEUE#19 m45 LFM2.5-8B-A1B MoE family Q2/Q3" \
              "$W/run_m45.sh" "$W/m45_summary.jsonl" 4
run_cpu_step  "QUEUE#15 m41 partial-credit (testfrac) ternary vs conventional [CPU]" \
              "$W/run_m41.sh" "$W/m41_summary.jsonl" 6

# SSOT 6b: a chain's last step launches the next entry if one exists. If a future
# driver/successor is written, hand over; otherwise say so loudly so an idle GPU is
# visible in the log rather than silent.
if [ -f "$W/NEXT_DRIVER.sh" ]; then
  echo "[driver] handing over to NEXT_DRIVER.sh $(date)"
  exec bash "$W/gpu_locked.sh" bash "$W/NEXT_DRIVER.sh"
fi
echo "=== QUEUE_DRIVER complete $(date): QUEUE.md #7..#19 drained. GPU now IDLE; add entries or re-arm. ==="
