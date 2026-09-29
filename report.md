# Formal study draft: generic factor relationships to quality and wall-time

This report is a **generic factor study**. It avoids model recommendations and avoids model-specific conclusions.

## 0. Handoff snapshot (for continuation without chat history)

### 0.1 Intent (current)

1. Build two predictive views that remain structurally reasonable:
   - `score_fix` model with explicit zero-capacity behavior (`size_b/activated_size_b/quant_ratio -> 0 => score -> 0`).
   - `wall_time_sec` model over the same factor set.
2. Prioritize experiments that increase **independent identifiability** of single factors and reduce coupled conclusions.
3. Produce evidence that generalizes across families/scales, not one-off model anecdotes.

### 0.2 Methodology and practice (current)

1. Manual high-EIG experiment choice only; no fixed-loop sweeps.
2. Serial GPU execution phase (one benchmark run active at a time) to preserve timing attribution and reduce resource thrash.
3. Every inserted run records explicit `start_time` and `reason`.
4. Before each DB mutation: create numbered backup; after mutation: integrity check.
5. Primary analysis mode is now **chaotic-observation orthogonalization** (cross-fit residual-on-residual with bootstrap CIs) over broad high-EIG data; exact matched pairs are retained as secondary sanity checks.
6. Keep knowledge lifecycle synchronized (`questions -> assumptions -> conclusions`) with confidence tags and scope boundaries.

### 0.3 What was completed in this phase

1. Cross-family decoupling panels:
   - Nemotron sampling/reasoning panel (`manualeig6`)
   - Granite short+long context one-sided KV panels (`manualeig7/8/9`)
2. Quant-mix ladders under matched controls:
   - Qwen4B (`manualeig10`)
   - Gemma-12B attempt (`manualeig11`) intentionally stopped mid-panel due poor time/EIG tradeoff; evidence retained but not used as primary anchor
   - Gemma-E2B (`manualeig12`)
   - Qwen2B (`manualeig13`)
3. Serial formula-structure search:
   - 27 cap-family combinations (`.serial_formula_search_caps.csv`), best CV RMSE `0.119596`.

### 0.4 Current doing / next queue focus

1. Continue manual high-EIG serial runs targeting unresolved generic assumptions (see `questions.md`, `task_queue.md`).
2. Highest-value pending item: larger-scale quant-mix ladder on largest feasible Qwen/Gemma anchor.
3. Second pending item: third-family long-context one-sided KV panel to resolve contradictory long-context KV behavior.

### 0.5 Todo state snapshot

* SQL todo board state at last sync: `22 done`, `1 in_progress`, `2 blocked`.
* In-progress focus: `manual-high-eig-benchmark-runs`.
* Blocked items: `evalperf-generalization-r2` (perf permission), `automated-coverage-sweep-r4` (disallowed by policy).

## 1. Scope and evidence partition

Current evidence in `experiments.sqlite`:

* `humaneval` (1614)
* `mbpp` (1569)
* `agentic_patch` (71)
* `kv_context_speed` (16)
* `mtp_speed_curve` (7)

Primary score datasets (used for quality `%` conclusions):

* `humaneval`
* `mbpp`

Auxiliary/non-standard datasets (used for mechanism diagnostics, not primary `%` score conclusions):

* `agentic_patch` (protocol/format/sampling behavior probe)
* `kv_context_speed` (context/KV timing probe)
* `mtp_speed_curve` (MTP timing probe)
* `evalperf` (efficiency/generalization probe; next high-yield expansion candidate)

Confidence legend:

* **high**: repeated direct evidence, robust across slices
* **medium**: partial evidence, not fully identified
* **low**: weak/speculative or confounded

## 2. Modeling stance (current)

The previous “all-plus linear predictor” is treated as a **temporary scaffold only**, not a final structural claim.

For now, the study should use:

1. **Main effects + selected interactions** only where experimentally identified.
2. **Nonlinear transforms** for known nonlinear factors (for example quant-ratio response and context effects).
3. **Hierarchical/partial-pooling formulation** to separate architecture constants from size/quant/sampling factors.
4. **Mechanism decomposition** where needed (for example reasoning affects validity first, then pass given valid).

Final closed-form formula will be produced only after stronger identifiability.

## 3. Generic conclusions from current data only

### 3.1 Reasoning must be decomposed through output validity (**high**)

\[
P(pass)=P(valid\_output)\times P(pass\mid valid\_output)
\]

Raw pass-rate comparisons of reasoning modes are confounded when validity changes across protocols.

Current primary-dataset aggregates also show a large raw-score and wall-time penalty when reasoning is enabled, so reasoning is currently a protocol cost unless validity-separated gains are demonstrated.

Using matched pairs with all non-reasoning factors fixed (legacy: 171 pairs/dataset), reasoning-on had `bad_rate≈0.80` and large raw-score loss. With expanded data, matched strict off→on contrasts now total 348 unique pairs and remain strongly negative on `score_fix` (mean `Δ≈-0.624`) with very large time penalty (mean `Δ≈+1084s`).

Chaotic-observation orthogonalized estimation (cross-fit RF nuisance models, bootstrap CIs) on 718 unique configs confirms a strong negative reasoning effect: `theta=-0.6709`, 95% CI `[-0.7053, -0.6290]`.

### 3.2 MTP appears primarily wall-time related in current evidence (**medium**)

Current auxiliary timing data is consistent with “speed effect first, quality structural effect unclear,” but this is not yet high confidence. The existing MTP rows are dominated by very high wall times and near-zero or zero pass@1_plus on the sampled HumanEval set, so the active signal is still timing, not quality.

### 3.3 KV cache quantization is not identified yet (**low**)

Generic coefficients are still under-identified across architectures, but the new Qwen `k/v × ctx × parallel` block is internally stable: for both primary datasets, q8/q5 and q5/q5 are consistently above q8/q8 on plus pass@1 at `ctx=8192/24576` and `parallel=1/4`. In one-sided long-context split at `ctx=24576` on Humaneval (`Qwen3.6-27B-UD-IQ2_M`), K-only (`k=q8_0,v=f16`) remains nonzero while V-only (`k=f16,v=q8_0`) is `0.0000`, indicating V-side fragility at that extreme point.

Across broader chaotic data, isolated local KV move at fixed Q3 (`q8/q8 -> q8/q5_1`) is near-zero overall (`mean Δscore≈+0.0028` over 40 unique contexts), so current global KV coefficient confidence remains low-to-medium.

### 3.4 Sampling-factor coefficients are not identified for generic quality claims (**low**)

`humaneval`/`mbpp` have limited sampling variation; therefore generic effects for temperature/top-p/top-k/min-p/presence are under-identified.

A direct `temperature=0.6, top_k=64` contrast on the current Qwen3.6-35B primary setup moved HumanEval down (`0.8902 -> 0.8598`, plus pass@1) and MBPP slightly up (`0.7487 -> 0.7513`, plus pass@1).  
A 2x2 follow-up panel (`temperature={0.3,0.6}`, `top_k={20,64}`) shows `top_k` dominates under current settings: HumanEval is baseline-like at `k=20` for both temperatures but lower at `k=64`; MBPP is lower at `k=20` and higher at `k=64`, with minimal temperature effect at fixed `k`.

### 3.5 Quant-ratio effects are weak once the exact latent model is fit (**medium**)

Legacy exact-fit snapshots suggested weak incremental quant-ratio contribution after category controls, but expanded chaotic-observation orthogonalization now shows a significant positive partial effect for `quant_ratio` (`theta=+0.4513`, 95% CI `[+0.2850,+0.7243]`) on `score_fix`.

Interpretation: quant-ratio effect is now supported directionally in pooled partial-effect space, while local ladder non-monotonicities still occur within specific family/size slices.

### 3.6 Architecture constants are still confounded with size/quant in current comparisons (**high**)

Any architecture-vs-architecture statement remains invalid unless size, activated-size, quant ratio, and decoding protocol are controlled.

New strict matched-anchor evidence now exists at 2B, 4B, and an additional 31B anchor (`ctx=8192`, `parallel=1`, `q8/q8`, reasoning off). At 4B, Gemma4-E4B is above Qwen3.5-4B on both primary datasets (`humaneval`: `0.8049 > 0.7805`, `mbpp`: `0.6667 > 0.6481`). At 2B, Gemma4-E2B is below Qwen3.5-2B on both primary datasets (`humaneval`: `0.0793 < 0.2134`, `mbpp`: `0.1852 < 0.3571`). A strict 35B Qwen family anchor could not be loaded on this 24GB GPU (`cudaMalloc failed: out of memory`), so the architecture-family comparison cannot be pushed to a broader same-scale family check here. The evidence still supports size-conditioned architecture effects, but not a generic ranking.

QAT expansion now includes both E2B and E4B Gemma anchors. The E4B strict match (`q8/q8`, same ctx/parallel/decoding) is mixed-sign: Humaneval improves (`0.8049 -> 0.8293`) while MBPP decreases (`0.6667 -> 0.6534`). A strict matched E2B QAT-vs-nonQAT contrast was also completed under `q8_0/q8_0`, `ctx8192`, `parallel=1`, reasoning off, with large positive deltas on both datasets (`humaneval: 0.0793 -> 0.7073`, `mbpp: 0.1852 -> 0.5317`), reinforcing that current QAT behavior is scale-conditioned rather than globally signed.

### 3.7 Exact score model form on primary data (**high**)

On a legacy fully-populated primary snapshot (`n=542` at fit time), a cleaner single-use formula was:

* **sigmoid-linked** (no `clip01`)
* **soft-capped at both ends** via sigmoid
* **exact zero at zero capacity** via multiplicative cap
* each of `size_b`, `activated_size_b`, `quant_ratio` appears **once** (no duplicated placement)
* only family/dataset are enums; quant/KV are numeric ratios

Five-fold CV RMSE on that snapshot is `0.1201` (train RMSE `0.1173`), improving over the prior `0.1246` fit while preserving the same structure. Current usable exact-score subset is larger (`n=599`), and an updated coefficient refit is pending; cap-family behavior on the current subset is reported in §3.16.

Preview-safe exact formula:

```text
score_fix_hat =
  sigmoid(
    1.3884267112
    + family_intercept[family]
    + dataset_intercept[dataset]
    + 0.6559292414 * k_ratio
    + 4.6204980447 * v_ratio
    - 7.7009631601 * reasoning_bool
  )
  * (size_b / (size_b + 0.5709722892))
  * (activated_size_b / (activated_size_b + 0.3824513340))
  * (quant_ratio / (quant_ratio + 1.9079046183e-16))
```

Zero-capacity guarantee:

* if `size_b -> 0` or `activated_size_b -> 0` or `quant_ratio -> 0`, then `score_fix_hat -> 0`.
* `quant_ratio` additive term was removed because it had no measurable contribution in the previous fit.

Family intercepts:

| family | intercept |
|---|---:|
| gemma\|4.0 | 0.0000000000 |
| glm\|4.7 | 2.5632085089 |
| lfm\|2.5 | 3.4945549489 |
| nemotron\|3.0 | 3.7659288682 |
| qwen\|3.5 | 3.4659510794 |
| qwen\|3.6 | 1.1464064561 |

Dataset intercepts:

| dataset | intercept |
|---|---:|
| humaneval | 0.0000000000 |
| mbpp | -2.6512035765 |

KV ratios from `~/llama.cpp` (`ggml-common.h` block definitions):

| kv quant type | bytes/element | ratio vs fp16 |
|---|---:|---:|
| fp16 | 2.00000 | 1.00000 |
| q8_0 | 1.06250 | 0.53125 |
| q5_1 | 0.75000 | 0.37500 |
| q5_0 | 0.68750 | 0.34375 |

### 3.8 Structural-prior stress test (sigmoid + monotone constraints) (**high**)

To test the constraints you requested, we fit a constrained model on the same legacy usable subset (`n=542`) with:

* sigmoid link (no `clip01`)
* numeric quant proxy (`quant_bits/16`) instead of quant categories
* family/dataset enums only
* monotonicity constraints: `beta_act >= beta_size >= 0`, `beta_reasoning >= 0`, `beta_quant_ratio >= 0`, `beta_kv >= 0`
* activated-size gate so `activated_size_b -> 0` implies `score -> 0`

Result: the optimizer converges, but fit quality collapses.

* unconstrained sigmoid version of the same feature set: RMSE `0.1168`
* constrained-prior version: RMSE `0.3786` (much worse)
* constrained solution pushes disputed terms to boundary: `beta_reasoning ≈ 0`, `beta_quant_ratio ≈ 0`

Interpretation: with current data, those priors are not jointly compatible with observed outcomes at this scale.

Additional data diagnostics for your six points:

* `quant_ratio` is now backfilled from on-disk GGUF size for almost all primary rows; 2 Gemma-26B IQ4_XS rows still miss an exact on-disk artifact. The latest usable exact-score subset is `n=599`; legacy coefficient tables above are snapshot coefficients pending full refresh.
* This formula removes `clip01`, enforces zero at zero capacity, and removes duplicated `quant_ratio` placement; reasoning is still negative on current data.
* In family-local regressions with size+activation+reasoning controls, size slope remains positive on the only well-powered family (`qwen3.6`: `+0.188`).
* For KV, constrained fits do preserve `q8/q8 > q5/q5` via positive KV-bit slopes, but only after accepting the large global fit degradation above.

### 3.9 Data-integrity collision check on eval artifacts (**high**)

A hash scan over generated sample JSONLs found cache-collision style duplicates in legacy artifacts:

* one confirmed cross-family artifact exists on disk (`gemma-4-E2B-it-UD-Q4_K_XL-archprobe2`) whose JSONL is byte-identical to `Qwen3.5-2B-UD-Q4_K_XL-archprobe2`; these rows were intentionally not ingested.
* in DB-ingested rows, 20 usable-primary rows share identical sample hashes across distinct experimental tags (mainly old Qwen3.6-27B quant/KV/MTP label combinations), consistent with evalplus sample-cache reuse behavior when labels changed without unique sample identity.

For formula fitting, we keep the full table as primary and track a collision-pruned sensitivity subset (legacy snapshot `n=522`). The selected formula remained stable in sign and shape in that audit; affected legacy slices are still treated as lower-confidence evidence.

### 3.10 Full-factor dual formulas (score + time) (**medium**)

Per the latest requirement, we now maintain **both** formulas with the full factor set:

* factors: `model_arch, version, variant, size_b, activated_size_b, qat_bool, quant_ratio, k_quant, v_quant, reasoning_bool, mtp, temperature, top_p, top_k, min_p, presence_penalty, parallel_slots, ctx_size, dataset`
* outputs: `score_fix` and `wall_time_sec`

Because legacy data has missing fields on some factors, we use:

* numeric default-imputation + explicit missingness indicator columns
* categorical `<NA>` bucket
* ridge regression (`L2`) with 5-fold CV

Current all-factor fits on primary `pass@1_plus` rows:

* **score formula** (`score_fix`): `n=2483` currently available (latest full-ridge CV RMSE snapshot remains `0.1651` at `n=1481`; full refit pending on newest rows)
* **time formula** (`log1p(wall_time_sec)`): `n=2431` currently available (latest full-ridge CV RMSE(log) snapshot remains `0.3108` at `n=1429`; full refit pending on newest rows)

Interpretation:

* this satisfies full-factor coverage for both targets, but current accuracy is still limited by confounding and legacy artifact quality.
* best next gains come from targeted manual runs that deliberately decorrelate sampling/KV/QAT effects rather than broad coverage sweeps.

Operational update:

* automated fixed-loop GGUF sweeps are now disabled.
* every new benchmark launch is manually selected by expected information gain, and each inserted row records explicit `start_time` and `reason`.

### 3.11 Orthogonal single-variable panels for identifiability (**medium**)

To reduce coupling and support per-variable interpretation, we ran manual orthogonal panels on the fast `LFM2.5-230M-UD-Q4_K_XL` anchor (`ctx=2048`, `parallel=1`, no-MTP), one variable changed at a time:

1. **Sampling panel** at fixed KV (`q8_0/q8_0`) with baseline `t=0.3, top_p=0.95, top_k=40, min_p=0.05, presence=0.0`:
   - `temperature: 0.3 -> 0.6`:
     - Humaneval `Δscore=-0.0244`, `Δtime=-0.2s`
     - MBPP `Δscore=+0.0106`, `Δtime=+79.9s`
   - `top_p: 0.95 -> 0.9`:
     - Humaneval `Δscore=+0.0000`, `Δtime=-0.7s`
     - MBPP `Δscore=+0.0503`, `Δtime=+0.3s`
   - `top_k: 40 -> 20`:
     - Humaneval `Δscore=-0.0244`, `Δtime=-0.0s`
     - MBPP `Δscore=+0.0397`, `Δtime=-0.5s`
   - `min_p: 0.05 -> 0.02`:
     - Humaneval `Δscore=+0.0122`, `Δtime=-0.6s`
     - MBPP `Δscore=+0.0291`, `Δtime=+60.9s`
   - `presence_penalty: 0.0 -> 0.5`:
     - Humaneval `Δscore=+0.0000`, `Δtime=-0.4s`
     - MBPP `Δscore=+0.0370`, `Δtime=+1.9s`

2. **KV panel** at fixed sampling (`t=0.3, top_p=0.95, top_k=40, min_p=0.05, presence=0.0`) with baseline `f16/f16`:
   - `k=q8_0, v=f16`:
     - Humaneval `Δscore=+0.0122`, `Δtime=+0.7s`
     - MBPP `Δscore=-0.0079`, `Δtime=+3.4s`
   - `k=f16, v=q8_0`:
     - Humaneval `Δscore=+0.0183`, `Δtime=-0.1s`
     - MBPP `Δscore=+0.0159`, `Δtime=+0.8s`

3. **Reasoning panel** at same fixed settings (`q8_0/q8_0`, baseline sampling):
   - `reasoning off -> on`:
     - Humaneval `Δscore=-0.0183`, `Δtime=-0.7s`
     - MBPP `Δscore=+0.0608`, `Δtime=+79.9s`

Interpretation (scope-limited): these runs materially improve variable identifiability (single-variable perturbations), but remain **single-model evidence** and therefore do not yet support generic high-confidence global coefficient claims.

### 3.12 Cross-family manual high-EIG decoupling on unseen architectures (**medium**)

To expand beyond the fast LFM anchor, we ran two manual high-EIG panels on previously unseen families with explicit `start_time` + `reason` provenance in DB.

1. **Nemotron-4B sampling/reasoning panel** (`NVIDIA-Nemotron-3-Nano-4B-UD-Q4_K_XL`, `ctx=2048`, `parallel=1`, `q8_0/q8_0`, no-MTP):
   - Baseline (`top_k=40`, reasoning off):
     - Humaneval `0.7744`, `442.0s`
     - MBPP `0.6931`, `924.6s`
   - `top_k: 40 -> 20` (reasoning off):
     - Humaneval `Δscore=-0.0061`, `Δtime=+20.6s`
     - MBPP `Δscore=-0.0317`, `Δtime=+9.2s`
   - `reasoning: off -> on` (fixed baseline sampling):
     - Humaneval `Δscore=-0.0488`, `Δtime=+288.7s`
     - MBPP `Δscore=-0.0265`, `Δtime=+473.3s`

2. **Granite-3B one-sided KV panel** (`granite-4.1-3b-UD-Q3_K_XL`, `ctx=2048`, `parallel=1`, reasoning off, fixed baseline sampling):
   - Baseline `f16/f16`:
     - Humaneval `0.7195`, `153.9s`
     - MBPP `0.5635`, `257.3s`
   - `k=q8_0, v=f16`:
     - Humaneval `Δscore=+0.0122`, `Δtime=+4.5s`
     - MBPP `Δscore=+0.0000`, `Δtime=+4.3s`
   - `k=f16, v=q8_0`:
     - Humaneval `Δscore=+0.0122`, `Δtime=+6.8s`
     - MBPP `Δscore=+0.0000`, `Δtime=-3.7s`

Interpretation:

* sampling and reasoning effects are now measured on a second non-LFM family, reducing pure single-family coupling.
* at short context on Granite-3B, one-sided KV effects remain small/near-neutral; this does not resolve long-context asymmetry seen in the prior extreme Qwen point.

### 3.13 Long-context cross-family KV check on unseen Granite (**medium**)

To directly test whether the prior long-context V-side collapse is generic or family-specific, we ran a matched long-context one-sided KV panel on the same unseen Granite anchor (`granite-4.1-3b-UD-Q3_K_XL`) at `ctx=24576`, `parallel=1`, reasoning off, baseline sampling.

1. **Humaneval** (`manualeig8`):
   - Baseline `f16/f16`: `0.7317`, `154.3s`
   - K-only `q8_0/f16`: `0.7439` (`Δ+0.0122`), `160.2s` (`Δ+5.8s`)
   - V-only `f16/q8_0`: `0.7439` (`Δ+0.0122`), `161.3s` (`Δ+7.0s`)

2. **MBPP** (`manualeig9`):
   - Baseline `f16/f16`: `0.5529`, `253.0s`
   - K-only `q8_0/f16`: `0.5714` (`Δ+0.0185`), `261.2s` (`Δ+8.2s`)
   - V-only `f16/q8_0`: `0.5661` (`Δ+0.0132`), `259.1s` (`Δ+6.1s`)

Interpretation:

* long-context one-sided KV on this second family is **non-collapsing** for both K-only and V-only settings.
* therefore, the earlier `Qwen3.6-27B` V-side collapse point should be treated as family/protocol-specific (or artifact-sensitive), not a universal KV law.

### 3.14 Qwen3.5-4B weight ladder with a KV contrast (**medium**)

We also ran a compact quant-mix panel on `Qwen3.5-4B` to separate weight-quant movement from a nearby KV perturbation, all under the same fixed decoding settings (`ctx=2048`, `parallel=1`, reasoning off, `t=0.3`, `top_p=0.95`, `top_k=40`, `min_p=0.05`).

1. **Weight ladder under fixed `q8_0/q8_0` KV**:
   - `Q2_K_XL` baseline:
     - Humaneval `0.6585`, `254.0s`
     - MBPP `0.6032`, `866.8s`
   - `Q3_K_XL`:
     - Humaneval `0.7439` (`Δ+0.0854`), `264.4s` (`Δ+10.3s`)
     - MBPP `0.6429` (`Δ+0.0397`), `585.9s` (`Δ-280.9s`)

2. **KV contrast at fixed `Q3_K_XL`**:
   - `q8_0/q8_0`:
     - Humaneval `0.7439`, `264.4s`
     - MBPP `0.6429`, `585.9s`
   - `q8_0/q5_1`:
     - Humaneval `0.7500` (`Δ+0.0061`), `261.8s` (`Δ-2.6s`)
     - MBPP `0.6376` (`Δ-0.0053`), `589.4s` (`Δ+3.5s`)

Interpretation:

* At this scale, the local weight-quant move (`Q2 -> Q3`) is much larger than the nearby KV perturbation.
* KV effects are present but small, and their sign still depends on dataset.

### 3.15 Gemma-E2B quant ladder with a KV contrast (**medium**)

To check whether the Qwen4B pattern generalizes within Gemma, we ran the same compact quant-mix panel on `Gemma-4-E2B-it` with identical decoding settings.

1. **Weight ladder under fixed `q8_0/q8_0` KV**:
   - `Q2_K_XL` baseline:
     - Humaneval `0.5122`, `471.7s`
     - MBPP `0.4709`, `926.1s`
   - `Q3_K_XL`:
     - Humaneval `0.6707` (`Δ+0.1585`), `548.1s` (`Δ+76.4s`)
     - MBPP `0.5238` (`Δ+0.0529`), `1069.6s` (`Δ+143.5s`)

2. **KV contrast at fixed `Q3_K_XL`**:
   - `q8_0/q8_0`:
     - Humaneval `0.6707`, `548.1s`
     - MBPP `0.5238`, `1069.6s`
   - `q8_0/q5_1`:
     - Humaneval `0.6768` (`Δ+0.0061`), `554.1s` (`Δ+6.0s`)
     - MBPP `0.5053` (`Δ-0.0185`), `1088.0s` (`Δ+18.3s`)

Interpretation:

* The weight-quant lift again dominates the nearby KV perturbation.
* Unlike the weight ladder, the KV change is small and dataset-dependent.

### 3.16 Serial cap-function search for exact score formula (**high**)

Using the search-method hint, we ran a **serial** (non-parallel) cap-family search for the exact score formula while preserving required priors:

* keep sigmoid link (no `clip01`)
* keep one-use capacity variables (`size_b`, `activated_size_b`, `quant_ratio`)
* enforce `score -> 0` when any of those capacity variables tends to zero
* keep the same linear block (`family`, `dataset`, `k_ratio`, `v_ratio`, `reasoning_bool`)

Search setup:

* candidate cap families per variable: `{rational, exp, tanh}`
* total combinations: `3^3 = 27`
* five-fold CV, refit per fold with nonlinear least squares
* each candidate run serially and timed (artifact: `.serial_formula_search_caps.csv`)

Top results:

| size cap | act cap | quant cap | CV RMSE | elapsed (s) |
|---|---|---|---:|---:|
| rational | rational | tanh | 0.119596 | 0.105 |
| rational | rational | exp | 0.119604 | 0.101 |
| rational | rational | rational | 0.119734 | 0.121 |

Interpretation:

* The best variant is only marginally better than the current pure-rational form (`ΔRMSE ≈ 0.00014`), so structural uncertainty is now narrow.
* Capacity-zero priors remain preserved across all tested candidates.
* The next meaningful improvement is more likely to come from targeted data (especially larger matched ladders) than from further cap-family tweaking alone.

### 3.17 Qwen3.5-2B quant ladder with KV contrast (**medium**)

To extend the quant-mix evidence across scale within Qwen, we ran the same panel on `Qwen3.5-2B` under the same fixed decoding settings.

1. **Weight ladder under fixed `q8_0/q8_0` KV**:
   - `Q2_K_XL` baseline:
     - Humaneval `0.2622`, `197.2s`
     - MBPP `0.2434`, `430.9s`
   - `Q3_K_XL`:
     - Humaneval `0.4329` (`Δ+0.1707`), `195.9s` (`Δ-1.3s`)
     - MBPP `0.3862` (`Δ+0.1429`), `397.9s` (`Δ-33.0s`)

2. **KV contrast at fixed `Q3_K_XL`**:
   - `q8_0/q8_0`:
     - Humaneval `0.4329`, `195.9s`
     - MBPP `0.3862`, `397.9s`
   - `q8_0/q5_1`:
     - Humaneval `0.4207` (`Δ-0.0122`), `196.3s` (`Δ+0.5s`)
     - MBPP `0.4127` (`Δ+0.0265`), `421.9s` (`Δ+24.0s`)

Interpretation:

* At 2B scale, the `Q2->Q3` weight move remains much larger than the nearby KV perturbation.
* This aligns with the 4B Qwen and E2B Gemma panels, strengthening the current “weight-dominant local effect” conclusion.

### 3.18 Chaotic-observation orthogonalized effects on expanded data (**high/medium**)

To handle high-EIG randomized/chaotic coverage where exact one-difference pairs are sparse, we use a deconfounded observational estimator:

1. Collapse duplicate identical configs to mean outcomes (reduces repeated-run noise).
2. For each target variable `T`, fit nuisance models `E[Y|X]` and `E[T|X]` with cross-fitted random forests (`X` = all other factors).
3. Regress residual outcome on residual treatment (`Y-E[Y|X]` on `T-E[T|X]`) to estimate partial effect `theta`.
4. Bootstrap confidence intervals for robustness.

Current run used `N_CONFIGS=718` (from `N_RAW=2484` primary rows).

Key partial effects for `score_fix`:

| variable | theta | 95% CI | confidence note |
|---|---:|---:|---|
| `reasoning_bool` | `-0.6709` | `[-0.7053, -0.6290]` | **high** strong negative |
| `size_b` | `+0.0039` | `[+0.0027, +0.0050]` | **high** positive |
| `quant_ratio` | `+0.4513` | `[+0.2850, +0.7243]` | **high** positive |
| `k_ratio` | `+0.0326` | `[-0.0122, +0.0716]` | not significant |
| `v_ratio` | `-0.0257` | `[-0.0526, +0.0004]` | borderline / not significant |

Interpretation:

* This estimator is now primary for global relationship direction under chaotic high-EIG data.
* Exact matched contrasts are still useful local validation, but no longer the sole inference path.

### 3.19 Prior-constrained formula refit (requested bias set) (**high** on fit procedure, **medium** on transfer)

Using current `pass@1_plus` rows and enforcing your structural priors directly, we refit a constrained score model on the **enough-context subset** defined as:

\[
I_{\text{enough}}=1[\text{ctx\_size} \ge P75(\text{ctx\_size}\mid \text{model\_enum})]
\]

with `model_enum := model_arch + "|" + version` (version is part of enum, not a separate numeric slope).

Fitted target: `score_fix` (the “pass given non-empty output” target).

Constrained structure:

\[
\hat s_{\text{fix}}=
\mathrm{clip}_{[0,1]}
\left(
\exp(w_{m}+d_{b})
\cdot f_{\text{size}}(S)
\cdot f_{\text{act}}(A/S)
\cdot f_q(Q)
\cdot (1+\alpha_{\text{qat}}\cdot \text{qat})
\cdot \exp((\beta_0+\beta_m)\cdot \text{reason})
\right)
\]

where:

* \(f_{\text{size}}(S)=1-\exp(-k_s S)\), \(k_s>0\)  (monotone, \(S\to0 \Rightarrow 0\))
* \(f_{\text{act}}(u)=u^{1/(1+k_a)}\), \(u=A/S\in[0,1],\;k_a>0\)  (monotone, \(u\to0 \Rightarrow 0\))
* quant saturating prior (0 to 1, diminishing, no gain past 0.5):
\[
f_q(Q)=
\begin{cases}
\frac{1-\exp(-k_q\cdot Q/0.5)}{1-\exp(-k_q)}, & Q\le 0.5\\
1, & Q>0.5
\end{cases}
\quad,\;k_q>0
\]
* `mtp` excluded from score formula by construction.
* `ctx_size` not used as continuous regressor; only the enough/not-enough gate above.
* strict positive QAT prior enforced with \(\alpha_{\text{qat}}\ge 0.01\).

Fit summary (current DB):

* subset: `n=523` rows (`I_enough=1`)
* 5-fold CV RMSE on `score_fix`: **0.0614**
* train RMSE: `0.0605`
* fitted global shape: `k_s=0.4605`, `k_a≈726`, `k_q≈192.5`, `alpha_qat=0.01` (at floor)

Interpretation:

* The data strongly supports an early-saturating quant-ratio response under the enforced shape.
* Under strict positivity prior, QAT effect is currently at minimal supported magnitude (hits lower bound), so present data does not support large generic QAT uplift after controlling other factors.

Reasoning-bug decomposition note (bias #1):

* For `pass@1_plus`, `bad_rate` is not populated in the current table, so direct empty-output decomposition is not available on this primary target.
* On `pass_rate` rows (where `bad_rate` exists), a separate constrained bug model confirms reasoning strongly increases empty-output probability; this supports keeping score decomposition as:
\[
\hat s \approx \hat s_{\text{fix}}\cdot (1-\hat p_{\text{empty}})
\]
with `\hat p_empty` estimated from the bad-rate-capable subset.

## 4. What is currently claimable

### Supported now

* **high**: validity decomposition is required for reasoning analysis.
* **high**: architecture-only comparisons are currently confounded.
* **medium**: MTP mostly impacts wall-time in current evidence.

### Not supported yet

* **low**: generic KV quant coefficients/effects.
* **low**: generic sampling coefficient signs/magnitudes.
* **low**: universal architecture ranking independent of other factors.

## 5. Data adequacy (for generic formalization)

Adequacy status by factor family:

* architecture constant: **partial** (confounded)
* size / activated-size: **partial**
* quant-ratio effect: **partial**
* KV K/V constants and interactions: **insufficient**
* reasoning gain: **partial** (needs validity-aware fits)
* sampling effects: **insufficient** on primary score datasets
* wall-time modeling: **partial** (missingness in auxiliary sets)

## 6. Next formalization rule

Until identifiability improves, report coefficients as:

* directional effects (sign and confidence),
* interaction existence/non-existence evidence,
* explicit scope conditions.

Do not present a final closed-form universal additive equation yet.
