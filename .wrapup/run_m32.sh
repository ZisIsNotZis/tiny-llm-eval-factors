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
# FIX: size the per-slot context from the observed prompt lengths (SSOT 3.4) and
# give `generate` enough wall-clock to finish all 200 rows.
#   * multi_turn_base  : prompts reach ~6.3k tokens -> -c 32768 -np 2 = 16 384/slot.
#   * multi_turn_long_context: observed 117 648-token prompt -> -c 262144 -np 2
#     = 131 072/slot (the model's own window is 262 144).
#   * GEN_TO raised per category (4 h / 10 h); run_m9_panel now logs the result-row
#     count so a truncated generation is visible instead of silently null.
#
# Dialect matches m9/m22 exactly (SSOT 3.3): official bfcl-eval, native-FC handler
# Qwen/Qwen3-1.7B-FC (qwen_fc manual <tool_call> format over /v1/completions),
# temperature 0. m32_preflight.sh first proves the model really emits tool calls,
# both natively (tools=) and in the exact qwen_fc manual format.
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
echo "[$(date +%H:%M:%S)] M32 preflight (native tools= + qwen_fc manual format)" >> "$LOG"
bash "$W/m32_preflight.sh" >> "$LOG" 2>&1
if ! grep -q NATIVE_TOOL_CALL_OK "$LOG" || ! grep -q MANUAL_TOOL_CALL_OK "$LOG"; then
  echo "[$(date +%H:%M:%S)] M32 ABORT: preflight did not produce a real tool call" >> "$LOG"
  echo "=== M32 end rc=1 $(date) ===" >> "$LOG"
  exit 1
fi

# 2. multi_turn_base — short prompts, small ctx so the run is fast.
echo "[$(date +%H:%M:%S)] M32 category multi_turn_base ctx=32768 np=2" >> "$LOG"
CTX=32768 NP=2 GEN_TO=14400 EVAL_TO=3600 LOG="$LOG" SUM="$SUM" \
  bash "$W/run_m9_panel.sh" bonsai-q2g64 "$MODEL" "$HANDLER" multi_turn_base

# 3. multi_turn_long_context — ~117k-token prompts need 131 072 tokens/slot.
#    If the model cannot allocate -c 262144 (e.g. another process is holding GPU
#    memory), fall back to -c 196608 (98 304/slot); the two >98k prompts then fail
#    as error ROWS (which still count towards 200), so the official eval still runs.
echo "[$(date +%H:%M:%S)] M32 category multi_turn_long_context ctx=262144 np=2" >> "$LOG"
CTX=262144 FALLBACK_CTX=196608 NP=2 GEN_TO=36000 EVAL_TO=3600 LOG="$LOG" SUM="$SUM" \
  bash "$W/run_m9_panel.sh" bonsai-q2g64 "$MODEL" "$HANDLER" multi_turn_long_context

echo "=== M32 end $(date) ===" >> "$LOG"
echo "--- m32_summary.jsonl ---" >> "$LOG"
cat "$SUM" >> "$LOG" 2>/dev/null
