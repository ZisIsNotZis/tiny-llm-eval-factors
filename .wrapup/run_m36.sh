#!/bin/bash
# M36 (NEW QUEUE entry) — ternary Bonsai on the OTHER multi-turn task types:
# multi_turn_miss_func and multi_turn_miss_param.
#
# m22 covered single-turn + multi_turn_base for the 27B ternary anchor; m32 added
# multi_turn_long_context (which overflowed per-slot ctx and returned null — see
# OPEN RISKS in QUEUE.md). These two categories are the remaining half of Tier 3 /
# B3 ("cross-family multi-turn"): they stress FUNCTION SELECTION (miss_func: the
# right function is absent, so the correct action is not to call) and PARAMETER
# COMPLETION (miss_param: a needed argument is missing, so the model must ask).
# A near-floor score here (as m18 saw for 2B q2/q3: 0.005/0.005) is a real result,
# not a harness zero, provided the gate/ctx checks below pass.
#
# Dialect matches m9/m18/m22 exactly (SSOT 3.3): official bfcl-eval, native-FC
# handler Qwen/Qwen3-1.7B-FC, temperature 0, K/V cache q8_0. Per-slot context
# follows SSOT 3.4: -c 196608 -np 2 = 98 304/slot, which m22 proved sufficient for
# base+long_context up to ~117k *except* the 117 648-token item; miss_func/miss_param
# prompts are shorter than long_context, so this ctx is safe here.
#
# The stale official result file is deleted before generation (run_m9_panel.sh does
# this too); SMOKE=1 forces one real completion before the ~2 h category loop.
#
# Rows: m36_summary.jsonl = 2 categories.
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/m36.log
SUM=$W/m36_summary.jsonl
HANDLER=Qwen/Qwen3-1.7B-FC
CATS=multi_turn_miss_func,multi_turn_miss_param
RRES=$W/bfclenv/lib/python3.11/site-packages/result
echo "=== M36 start $(date) ===" >> "$LOG"
rm -f "$SUM"
find "$RRES/$(echo "$HANDLER" | tr '/' '_')" -name 'BFCL_v4_multi_turn_*_result.json' -delete 2>/dev/null

CTX=196608 NP=2 SMOKE=1 LOG="$LOG" SUM="$SUM" \
  bash "$W/run_m9_panel.sh" bonsai-q2g64 Ternary-Bonsai-27B-Q2_g64.gguf "$HANDLER" "$CATS"
rc=$?
echo "=== M36 end rc=$rc $(date) ===" >> "$LOG"
