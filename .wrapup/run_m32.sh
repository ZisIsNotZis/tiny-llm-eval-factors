#!/bin/bash
# M32 (QUEUE #6) — ternary on the HARD axis: official BFCL multi-turn.
#
# Highest-value connection between our two strongest findings:
#   * off-curve ternary weights (Bonsai 27B Q2_g64: m21 cpp .6957 / py .7640;
#     m22 single-turn .7024 and multi_turn_base .6950), and
#   * the Q2 floor on the agentic axis (m9: qwen2b-q2 multi_turn_base 0.025 vs
#     qwen2b-q3 0.185 — native-FC dialect, temp 0).
# m22 already covered single-turn + multi_turn_base; this panel adds
# multi_turn_long_context, where the prompts reach ~100k tokens and the 2-bit
# ternary weights are stressed hardest. Re-running multi_turn_base is the
# axis's noise floor (identical config to m22's 0.695).
#
# Dialect matches m9/m22 exactly (SSOT 3.3): official bfcl-eval, native-FC
# handler Qwen/Qwen3-1.7B-FC, temperature 0, K/V cache q8_0. Per-slot context
# follows SSOT 3.4: -c 196608 -np 2 = 98 304 tokens per slot, sized for the
# ~100k-token long-context prompts (the model's own window is 262 144).
#
# The stale official result file is deleted before generation (a stale
# BFCL_v4_*_result.json silently re-scores the previous model's responses);
# run_m9_panel.sh does this per category, the explicit delete below documents it.
# run_m9_panel.sh is called with SMOKE=1, so the 27B model must produce one real
# completion before the ~2h category loop starts.
#
# Must run under the GPU flock (the chain does this):
#   bash gpu_locked.sh bash run_m32.sh
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/m30_32.log
SUM=$W/m32_summary.jsonl
HANDLER=Qwen/Qwen3-1.7B-FC
CATS=multi_turn_base,multi_turn_long_context
RRES=$W/bfclenv/lib/python3.11/site-packages/result

echo "=== M32 start $(date) ===" >> "$LOG"
rm -f "$SUM"
find "$RRES/$(echo "$HANDLER" | tr '/' '_')" -name 'BFCL_v4_multi_turn_*_result.json' -delete 2>/dev/null

CTX=196608 NP=2 SMOKE=1 LOG="$LOG" SUM="$SUM" \
  bash "$W/run_m9_panel.sh" bonsai-q2g64 Ternary-Bonsai-27B-Q2_g64.gguf "$HANDLER" "$CATS"
rc=$?
echo "=== M32 end rc=$rc $(date) ===" >> "$LOG"
