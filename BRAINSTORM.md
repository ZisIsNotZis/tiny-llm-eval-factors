# BRAINSTORM.md — axes we have NOT crossed, ranked by information gain

Method: `RESEARCH_METHOD.md`. Each item states *what we know*, *what the gap is*, and *a concrete,
feasible test on this host*. Ranked by expected information gain per GPU-hour, not by ease.

---

## Tier 1 — quantisation *scheme* diversity (highest novelty)

We have so far varied only the **level** within one scheme family (Unsloth `UD-*` dynamic quants,
plus one ternary model). The scheme itself is confounded with the level.

### 1A. MoE-aware / expert-wise quantisation  ← the thing you were thinking of
**Names to look for:** *MoQE* (IBM, "Mixture of Quantized Experts" — 2-bit experts with outlier
handling), *QMoE* (sub-1-bit MoE compression, ~1.7 bits/expert), *expert-wise mixed precision*.
**Why it matters:** in a sparse MoE, only a few experts fire per token, so errors are *not*
averaged across the whole model the way they are in dense. A scheme that allocates bits per expert
should sit well off the bits→score curve — which is exactly the effect we already glimpsed with
ternary Bonsai (Finding 8).
**What is testable here without new runtimes:** `llama-quantize` supports **per-tensor type
overrides** (`--tensor-type`), and MoE experts live in separate tensors (`ffn_*_exps`). So we can
build mixed recipes from an F16/BF16 GGUF: e.g. **experts at Q2_K while attention/other at Q4_K**,
and the reverse, and compare at matched file size against a uniform Q3/Q4.
**Test:** 3 recipes × 1 MoE anchor (Qwen3.6-35B-A3B or gemma-4-26B-A4B) × MultiPL-E cpp/py + BFCL
single-turn. Needs the F16 source (~70 GB download; disk has room).
**Cheap precursor (do first):** compare *existing* recipes from different providers for the same
MoE (unsloth `UD` vs a plain `Q4_K_M`/`IQ4_XS` build) — no requantisation, tests whether the label
`UD` predicts anything beyond file size.

### 1B. IQ (imatrix) vs K-quant at matched file size
**Known:** we compare across levels but never IQ vs K at the *same* size. `IQ*` uses an importance
matrix; `Q*_K` does not.
**Test:** for 2 anchors that have both (e.g. `UD-IQ3_XXS` vs `UD-Q3_K_XL` at ~equal size), measure
code + BFCL. Directly answers "does imatrix buy score per byte?"

### 1C. Sub-2-bit frontier  (partially done)
**Known:** `IQ2_XXS` collapses 2B (0.006); `IQ2_M` ≈ `Q2_K_XL`; ternary Bonsai (2.25 bpw) is
*above* the curve.
**Gap:** we have exactly ONE usable ternary checkpoint. Any second ternary/sub-2-bit family would
turn a single observation into a class.
**Test:** search ModelScope/HF for other ternary or `Q2_0`/`IQ1` releases; run the same panel.

---

## Tier 2 — MoE *structure* as a predictor (cheap; we already own the data)

### 2A. Total params vs **active** params vs **expert size** as the predictor of quantised score
**Known:** we have dense 0.8B–9B and MoE 8B-A1B, 26B-A4B, 35B-A3B.
**Gap:** our score model uses `__size` (total). For MoE, `active` may be the better predictor —
it is the *compute* that runs at inference. Nobody has checked which one predicts quant damage.
**Test (analysis, ~0 GPU):** regress quantised MultiPL-E score on (total, active, expert-count) for
the anchors we have; then **one** targeted run to break the collinearity (a model with high total
and low active, e.g. Qwen3.6-35B-A3B, vs a coarse-MoE anchor with similar active but far fewer
experts, e.g. gemma-4-26B-A4B).

### 2B. Expert granularity (many-small vs few-large experts)
**Test:** pick two MoEs matched on active params but differing in expert count/size, run Q2 and Q3.

### 2C. Dense vs sparse at matched **total** size
**Known:** Qwen3.5-4B (dense) vs nothing matched. **Test:** a dense ~26–35B at Q2/Q3 vs the MoE
twins — does sparsity make quantisation *more* damaging (errors not averaged) or less (fewer active
weights to damage)? This is a clean, novel question.

---

## Tier 3 — precision axes *other than* weights

### 3A. Attention/compute precision (`-fa` flash-attn on/off, attention dtype)
**Why:** changes the numerics of the same weights; interacts with KV quant.
**Test:** 2B/4B at Q3/Q4 × {`-fa` on, off} × {KV f16, q8_0} on code + long-context.

### 3B. KV-cache quant (partially done) — extend to the long-context regime
**Known:** K vs V asymmetry at 8k/24k on one model. **Gap:** no systematic KV × ctx × quant grid.

### 3C. True activation quantisation (W8A8/W4A16)
**Verdict: NOT FEASIBLE on llama.cpp** — there is no activation-quant path (only KV-cache quant is
exposed). Record this as an explicit scope limitation rather than faking a proxy. The nearest
honest axes are 3A (compute precision) and 3B (KV). If a W8A8 runtime appears, this becomes Tier 1.

---

## Tier 4 — decoding axes

### 4A. Does the **optimal sampling** shift with quant?
**Gap:** our early sampling panel was one model, one quant level. If the best `temp`/`top_k` depends
on quant, then every quant comparison done at fixed sampling is under-stated.
**Test:** 2B at Q2 vs Q3 vs Q4 × {temp 0.0/0.3/0.6} × {top_k 20/40/64} on cpp+py (greedy already
measured). 18–24 short cells; 2B is fast.

### 4B. Draft / MTP length × **speed** across datasets  (your speed-fit)
**Known:** `spec_draft_n_max` and MTP rows exist but were never analysed as a speed curve.
**Test:** for one model, sweep draft length n∈{1,2,3,4} and measure tokens/s on code vs prose vs
long-context prompts; fit speed(n). Answers "how long a draft is worth it" and whether acceptance
rate depends on task type. Cheap, and it uses the existing MTP GGUFs.

### 4C. Speculative decoding correctness under quant
**Gap:** does drafting change *scores* (not just speed) at low quant? Drafting is exact in theory;
verify empirically at Q2.

---

## Tier 5 — coverage (breadth, lower novelty per hour)

### 5A. More architecture families on the same panel
MiniCPM5, Nemotron-3, Ornith, GLM-4.7, LFM2.5, Qwen3.8 sizes, gemma-4 sizes. Adds rows to every
cross-family table. Do this when the GPU would otherwise idle, not as the primary thrust.

### 5B. Multilingual depth (MultiPL-E already supports 7 languages; we run 2–4 per anchor)

### 5C. Statistical power: more items, not more runs
The MDE table says the fix for a headline CI is **items**. `MultiPL-E` gives 161/language;
adding languages is the cheapest power boost we have.

---

## Explicitly out of scope (record, do not attempt)

* Activation quantisation (no llama.cpp path) — see 3C.
* Terminal-Bench / SWE-bench as data sources: compute-hostile, and they floor this model panel.
* Any panel whose BFCL handler dialect has not been verified (it silently produces 0.00).
* Fixed-loop sweeps over the whole GGUF zoo (policy: no blind grids).
