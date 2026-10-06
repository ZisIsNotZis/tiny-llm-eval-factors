#!/bin/bash
# M32 (QUEUE #6) — ternary on the HARD axis: official BFCL multi-turn.
#
# WHY THE PREVIOUS RUN RETURNED null (the bug this fixes):
#   The 2026-10-03 run passed both categories to a single run_m9_panel.sh with
#   -c 196608 -np 2 (98 304 tokens/slot) and the panel's 2 h `timeout 7200` cap.
#   * multi_turn_base generation was killed at 138/200 rows; long_context at 49/200
#     (plus 2 real ctx-overflow 400s: a 117 648-token prompt > 98 304/slot).
#   * official `bfcl evaluate` refuses a partial result file ("Length of model
#     result (138) does not match length of test entries (200)") and prints no
#     accuracy -> the recorded value was null. It was never a capability 0.
#   The 9-11 `KeyError: 'arguments'` rows are a known qwen_fc._format_prompt quirk
#   on a malformed model turn; they are still written as result rows and count
#   towards the 200, so they are NOT the cause (m22 scored 0.695 with the same 10).
#
# WHY THE 2026-10-06 RE-RUN ALSO ABORTED (m32b, `SERVER FAIL`):
#   .wrapup/m32_preflight.sh started its capability server at `-c 262144 -np 2`
#   (131 072 tokens/slot) to cover the long-context category. On this 24 GB GPU,
#   shared with a foreign llama-server (`/home/z/vibe/helpagent`, :8834, ~3.9 GB,
#   NOT ours) over the 7.58 GB 27B-Q2 weights, the server could not allocate its
#   compute buffers and died with `cudaMalloc failed: out of memory` before any
#   tool call was sent. The preflight therefore saw no server and the panel
#   aborted. It was a server-start/VRAM problem, NOT a capability zero:
#   an earlier worker had already seen a successful Bonsai tool-call preflight.
#
# FIX (this version):
#   * m32_preflight.sh now starts its server light and steps the context DOWN
#     (32768 -> 16384 -> 8192 at NP=1), prints the llama-server log tail on
#     failure, and only runs the two tool-call checks after `/health` is ok.
#   * This launcher retries the whole preflight once at an even smaller ladder
#     (16384 -> 8192 -> 4096) before giving up, and on a second failure writes
#     .wrapup/m32_BLOCKED.md (with the server log tail) instead of a null row.
#   * multi_turn_base runs at the reduced footprint requested for this GPU
#     (-c 65536 -np 1, fallback 32768 if 65536 cannot allocate).
#   * multi_turn_long_context is NOT run: its prompts reach ~117 648 tokens,
#     needing >~16 GB of q8_0 KV on top of the 7.6 GB model, i.e. more than this
#     GPU has free while the foreign server holds ~3.9 GB. It is recorded as
#     BLOCKED-on-VRAM (a note), never as a null accuracy row.
#
# Dialect matches m9/m22 exactly (SSOT 3.3): official bfcl-eval, native-FC handler
# Qwen/Qwen3-1.7B-FC (qwen_fc manual <tool_call> format over /v1/completions),
# temperature 0.
#
# Must run under the GPU flock (the chain does this):
#   bash gpu_locked.sh bash run_m32.sh
set -u
W=/home/z/hf/research/.wrapup
LOG=${M32_LOG:-$W/m32.log}
SUM=$W/m32_summary.jsonl
HANDLER=Qwen/Qwen3-1.7B-FC
MODEL=Ternary-Bonsai-27B-Q2_g64.gguf

echo "=== M32 start $(date) ===" > "$LOG"
rm -f "$SUM"

# 1. capability preflight: does the ternary 27B emit a real tool call at all?
#    The preflight owns its own server lifecycle (light ctx + log tail on fail);
#    two attempts are made because a transient co-tenant can steal the VRAM.
preflight_once() {  # ctx_list
  M32_PREFLIGHT_PORT=8132 CTX_LIST="$1" bash "$W/m32_preflight.sh" >> "$LOG" 2>&1
}
echo "[$(date +%H:%M:%S)] M32 preflight attempt 1 (native tools= + qwen_fc manual format)" >> "$LOG"
preflight_once "32768 16384 8192"
if ! grep -q NATIVE_TOOL_CALL_OK "$LOG" || ! grep -q MANUAL_TOOL_CALL_OK "$LOG"; then
  echo "[$(date +%H:%M:%S)] M32 preflight attempt 1 failed; retrying at reduced footprint" >> "$LOG"
  preflight_once "16384 8192 4096"
fi
if ! grep -q NATIVE_TOOL_CALL_OK "$LOG" || ! grep -q MANUAL_TOOL_CALL_OK "$LOG"; then
  {
    echo "# m32 — BLOCKED-on-VRAM $(date)"
    echo
    echo "Two tool-call preflight attempts failed: the Ternary-Bonsai-27B-Q2 server"
    echo "could not come up (7.58 GB weights + KV/compute buffers on a 24 GB GPU"
    echo "shared with the foreign helpagent llama-server :8834, ~3.9 GB, which is"
    echo "NOT ours and was left alone). No tool call was ever sent, so this is a"
    echo "server-start/VRAM block, NOT a capability 0. No accuracy row was written."
    echo
    echo "## llama-server log tail (m32_preflight.log)"
    echo '```'
    tail -n 40 "$W/m32_preflight.log" 2>/dev/null || echo "(no preflight log)"
    echo '```'
  } > "$W/m32_BLOCKED.md"
  echo "[$(date +%H:%M:%S)] M32 ABORT: preflight did not produce a real tool call (BLOCKED-on-VRAM; see m32_BLOCKED.md)" >> "$LOG"
  echo "=== M32 end rc=1 $(date) ===" >> "$LOG"
  exit 1
fi

# 2. multi_turn_base — short prompts (~6.3k tokens), reduced-footprint server so
#    the run fits alongside the foreign server (SSOT 3.4, per-slot ctx).
echo "[$(date +%H:%M:%S)] M32 category multi_turn_base ctx=65536 np=1" >> "$LOG"
CTX=65536 FALLBACK_CTX=32768 NP=1 GEN_TO=14400 EVAL_TO=3600 LOG="$LOG" SUM="$SUM" \
  bash "$W/run_m9_panel.sh" bonsai-q2g64 "$MODEL" "$HANDLER" multi_turn_base

# 3. multi_turn_long_context: recorded as BLOCKED-on-VRAM, not run (see header).
echo "[$(date +%H:%M:%S)] M32 long_context BLOCKED-on-VRAM (~117k-token prompts need >16 GB KV on top of 7.6 GB weights) - skipped" >> "$LOG"

echo "=== M32 end $(date) ===" >> "$LOG"
echo "--- m32_summary.jsonl ---" >> "$LOG"
cat "$SUM" >> "$LOG" 2>/dev/null
