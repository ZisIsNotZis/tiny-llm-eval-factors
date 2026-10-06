#!/bin/bash
# M36 (QUEUE #10) — ternary Bonsai on the OTHER multi-turn task types:
# multi_turn_miss_func and multi_turn_miss_param.
#
# WHY THE 2026-10-06 RUN RECORDED TWO nulls (the bug this fixes):
#   The panel called `bfcl evaluate` WITHOUT `--partial-eval`, so the official
#   eval_runner aborts the moment the result file has fewer rows than the 200 test
#   entries ("ValueError: Length of model result (127) does not match length of test
#   entries (200)") and prints no accuracy -> accuracy:null.
#   BUT the root cause of the row deficit is NOT the evaluate flag: the GENERATION
#   itself was truncated. `.wrapup/m36.log` shows `generated multi_turn_miss_func
#   rows=74 (expect 200)` and `...miss_param rows=127 (expect 200)`. miss_func/
#   miss_param are the slowest BFCL categories (up to 20 sequential steps/item); the
#   same 27B did only 74-127 items per 2h `GEN_TO` cap. m18 (2B, same categories)
#   finished 200 items in 46-64 min, i.e. ~7-13x faster. No other BFCL panel used
#   `--partial-eval`, and none needed to: they all completed 200/200 rows.
#
# FIX (belt + braces, both correct):
#   * GEN_TO raised to 18000 s/category so a complete 200/200 generation is possible.
#   * PARTIAL_EVAL=1 so that IF it still truncates we get a real (subset) accuracy
#     and `n` in the summary, instead of a null. The `n` field makes the subset
#     explicit, so the row is honest (RESEARCH_METHOD 2: a result names its n).
#   * ctx reduced from -c 196608 (98304/slot, which OOM'd once: cudaMalloc 6528 MiB
#     failed) to -c 131072 -np 2 = 65536/slot, exactly the config m22 ran the same
#     27B at; FALLBACK_CTX=98304 (49152/slot) if that will not allocate. BFCL's own
#     "Max context length" for these categories is 40960 tokens, so 49152/slot is
#     sufficient.
#   * a tool-call PREFLIGHT runs first (m32_preflight.sh, light ctx): it proves the
#     model emits a real native `tool_calls` AND the qwen_fc manual <tool_call>
#     format over /v1/completions. Without this a null could be misread as
#     "categories cannot be produced" when it is really a handler/server artifact.
#
# Dialect matches m9/m18/m22 exactly (SSOT 3.3): official bfcl-eval, native-FC
# handler Qwen/Qwen3-1.7B-FC, temperature 0, K/V cache q8_0.
#
# Rows: m36_summary.jsonl = 2 categories (non-null accuracy).
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/m36.log
SUM=$W/m36_summary.jsonl
HANDLER=Qwen/Qwen3-1.7B-FC
CATS=multi_turn_miss_func,multi_turn_miss_param
MODEL=Ternary-Bonsai-27B-Q2_g64.gguf
echo "=== M36 start $(date) ===" >> "$LOG"
rm -f "$SUM"

# 1. tool-call preflight — do not spend hours if the dialect is broken.
echo "[$(date +%H:%M:%S)] M36 preflight (native tools= + qwen_fc manual format)" >> "$LOG"
M32_PREFLIGHT_PORT=8133 CTX_LIST="${M36_PREFLIGHT_CTX:-32768 16384 8192}" \
  bash "$W/m32_preflight.sh" >> "$LOG" 2>&1
PFL=$W/m32_preflight.log
grep -q NATIVE_TOOL_CALL_OK "$PFL" 2>/dev/null || grep -q NATIVE_TOOL_CALL_OK "$LOG" 2>/dev/null \
  && nativ=1 || nativ=0
grep -q MANUAL_TOOL_CALL_OK "$PFL" 2>/dev/null || grep -q MANUAL_TOOL_CALL_OK "$LOG" 2>/dev/null \
  && man=1 || man=0
if [ "${nativ:-0}" != 1 ] || [ "${man:-0}" != 1 ]; then
  echo "[$(date +%H:%M:%S)] M36 ABORT: preflight native=$nativ manual=$man (no real tool call)" >> "$LOG"
  { echo "# m36 — BLOCKED (tool-call preflight failed) $(date)"; echo
    echo "native_tool_call=$nativ manual_tool_call=$man. No real tool call was produced;"
    echo "this is a server/handler block, not a capability 0. No accuracy row written."
    echo '```'; tail -n 30 "$PFL" 2>/dev/null; echo '```'; } > "$W/m36_BLOCKED.md"
  echo "=== M36 end rc=1 $(date) ===" >> "$LOG"; exit 1
fi

# 2. official multi-turn generation + evaluation for both categories.
CTX=131072 FALLBACK_CTX=98304 NP=2 SMOKE=1 GEN_TO=18000 EVAL_TO=1800 PARTIAL_EVAL=1 \
  LOG="$LOG" SUM="$SUM" \
  bash "$W/run_m9_panel.sh" bonsai-q2g64 "$MODEL" "$HANDLER" "$CATS"
rc=$?
echo "=== M36 end rc=$rc $(date) ===" >> "$LOG"
