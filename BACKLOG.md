# Backlog — hypotheses worth testing (not yet run)

## B1. Off-curve quantisation: ternary / Q1 / Q2 "surprises"  *(operator-requested 2026-10-01)*

**Hypothesis.** Extremely low-bit schemes — especially *ternary* (Bonsai) and `Q1`/`Q2` — may not lie
on the smooth "more bits → better score" curve at all. They may be:

* **surprisingly good** (the quantiser was co-designed with the model, or the calibration set matches
  the benchmark better than a generic `K`-quant does), or
* **discontinuously bad** (attention kicks/outliers destroyed, giving a cliff rather than a slope).

**Why it matters for this study.** Our whole result is a *quant ↔ benchmark score* mapping. If some
family is off-curve, then "use ≥ Q3" is not just conditional on the model — it is conditional on the
*quantisation scheme*. That would be a much stronger and more useful statement.

**Assets already on disk** (verify before starting):
* `Ternary-Bonsai-27B-PQ2_0.gguf`, `Ternary-Bonsai-27B-Q2_0.gguf`, `Ternary-Bonsai-27B-Q2_g64.gguf`
  (prism-ml/Ternary-Bonsai-27B-gguf) — a **ternary** model, i.e. off the usual bit-width axis.
* `DeepSeek-R1-0528-Qwen3-8B-UD-IQ1_S.gguf` / `-UD-IQ1_M.gguf` in the legacy DB (need re-download).
* `GLM-4.7-Flash-UD-IQ1_S/IQ1_M`, `North-Mini-Code-1.0-UD-IQ1_M` in the legacy DB (need re-download).
* `LFM2.5-230M-UD-IQ2_M`, `NVIDIA-Nemotron-3-Nano-4B-UD-IQ2_XXS` (legacy; re-download as needed).

**Design (when run).**
1. For each off-curve candidate, measure the *same* MultiPL-E panel (cpp/py/js, raw greedy) **and**
   the nearest in-family `UD-Q2_K_XL` / `UD-Q3_K_XL` as the on-curve reference.
2. Compare against the fitted curve from the 13-anchor dataset at matched file size (bits/weight),
   not matched quant name.
3. Report "surprise" = residual from the curve, with item-level CIs.
4. Also worth including: `IQ2_XXS` vs `Q2_K_XL` at matched size (we already saw `IQ2_XXS` collapses
   the 2B model while `IQ2_M` ≈ `Q2` — i.e. the *scheme* matters within the same nominal level).

**Status:** backlog. Run after the main-line cross-family/cross-task expansion is complete.

## B2. Sampling-parameter recommendations from vendors

Unsloth publishes recommended llama.cpp run/sampling parameters per model. We currently use a fixed
protocol (`top_p .95 / top_k 40 / min_p .05`, greedy). Worth a controlled check: does using the
vendor-recommended sampling change any *quant* conclusion (i.e. is our protocol a confound)?
Cross-reference: our existing finding that **protocol choice changes the sign** of quant conclusions.

**Status:** backlog.

## B3. Cross-family multi-turn

Multi-turn BFCL was run on one anchor only (Qwen3.5-2B, `multi_turn_base`). Extend to granite /
gemma / the MoE anchors, and to the other multi-turn categories
(`multi_turn_miss_func`, `multi_turn_miss_param`, `multi_turn_long_context`).

**Status:** backlog (highest value remaining experiment).
