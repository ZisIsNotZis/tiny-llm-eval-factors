# AXES_RESULTS_SYNTHESIS.md — QAT / GSQ-RCO / DiffusionGemma readout

**Status: axis 1.6 COMPLETE for all runnable pairs (12B Q4, E2B Q2, E2B Q4, E4B Q2, E4B Q4); 31B + 26B-A4B native BLOCKED-on-VRAM. Axis 1.5 COMPLETE; axis 7 gate-fail.**
Last updated 2026-10-14 06:55 +08:00.

**Writer note (2026-10-14 06:55):** the AXES campaign has **finished** — driver `campaign end
done=9 failed_stages=0` and the detached finisher exited with `all 12 complete`. All five runnable
axis-1.6 pairs are now complete: **12B Q4**, **E2B Q2**, **E2B Q4**, **E4B Q2**, **E4B Q4**; the
31B pair (m142/m143) and the 26B-A4B native (m145) remain BLOCKED-on-VRAM (non-measurements).
Axis 1.5 (GSQ-RCO) is finalized (F13) and axis 7 is runtime-gated (gate-fail).

This is the human synthesis of the three new axes. It is built **only** from the canonical
cells (same 7 benchmarks / same protocols as `bpw_sensitivity.py`) via
`.wrapup/axes_findings.py`; any cell not yet measured prints `pending` and is **never**
fabricated. A cell that cannot run is reported `BLOCKED`, never as 0.

Item-level SE = `sqrt(p(1-p)/n)`; delta = treatment − control; CI = delta ± 1.96·SE.
Positive delta = the treatment (QAT / GSQ-RCO) scores higher.

Legend: ✅ complete · ◐ partial (one side measured, other pending) · ⏳ pending · ⛔ BLOCKED.

---

## Axis 1.6 — QAT vs native at the same nominal UD-Q?_K_XL recipe

Held fixed: model size + nominal recipe. Varied: whether the weights were QAT-trained.
**Caveat carried with every row:** QAT files compress to a *lower* effective bpw than their
native partner (e.g. 12B: 4.512 vs 4.949), so this is not a byte-matched comparison.

### 12B UD-Q4_K_XL (m140 QAT vs m141 native) — ✅ complete (6/7 benches)
| bench | delta (QAT−native) | 95% CI | n_t/n_c |
|---|---|---:|---|
| humaneval-plus | −0.0061 | [−0.0675, +0.0553] | 164/164 |
| mbpp-plus | −0.0106 | [−0.0735, +0.0523] | 378/378 |
| mmlu | **−0.1974** | [−0.2422, −0.1526] | 912/912 |
| arc_challenge | **NO RESULT** both sides | — | — |
| truthfulqa_mc2 | +0.0255 | [−0.1129, +0.1640] | 100/100 |
| gsm8k | +0.0200 | [−0.0458, +0.0858] | 100/100 |
| ifeval | −0.0200 | [−0.1067, +0.0667] | 100/100 |

Raw sides: QAT m140 — HumanEval+ 0.9085 (149/164), MBPP+ 0.7302 (276/378), MMLU 0.4463,
TruthfulQA 0.5295, GSM8K 0.9500, IFEval 0.8800. Native m141 — HumanEval+ 0.9146 (150/164),
MBPP+ 0.7407 (280/378), MMLU 0.6436, TruthfulQA 0.5039, GSM8K 0.9300, IFEval 0.9000.
Both arcs: `SHIM ERROR ... continuation token id=… absent ... refusing to guess` →
**NO RESULT, not 0**.

**Code and instruction-following are null at 12B.** HumanEval+ (−0.006), MBPP+ (−0.011),
GSM8K (+0.020), IFEval (−0.020) and TruthfulQA (+0.026) are all well inside one item-level
SE. The QAT file stays with ~0.44 bpw *fewer* bytes.

**⚠ Anomaly flag on the 12B MMLU cell (do not over-read).** The native 12B MMLU ladder in
the DB is Q2 0.3695 → Q3 0.4178 → **Q4 0.6436** (m93/m105/m141, same protocol, n=912).
That Q3→Q4 jump (+0.226) is ~28× the study's pooled `Q3→Q4` plateau (+0.008, F2) and is
not matched on any code/instruction cell (native Q3 HumanEval+ 0.9146 ≈ QAT Q4 0.9085;
native Q4 GSM8K 0.9300 = Q3 0.9300). The QAT Q4 (0.4463) sits at the **native Q3** level,
not at the native Q4 level. So the −0.197 MMLU delta is **measured** but the native-Q4 rung
it is measured against is the outlier; treat this cell as **suspect pending re-measurement**,
not as evidence that QAT destroys knowledge.

> **Resolution attempt (2026-10-13, no GPU re-run) — verdict: measurement-level outlier, NOT a
> capability jump, NOT a checkpoint/protocol/shim mixup.** Both 12B Q4 MMLU runs are clean:
> m141 `server.log` loads the correct `gemma-4-12b-it-UD-Q4_K_XL.gguf`; m140/m141 share the same
> protocol *and* the same `lm_eval` git `194c1059b`; the MMLU task file/dataset are identical; and
> the two GGUFs' tokenizers are byte-identical (n_vocab 262144, same answer-letter token ids).
> m141's 61-subject profile matches no other model's (3–12/61 exact subjects vs anything else) →
> not a checkpoint flush. The shift is systematic (180/912 items) and **confined to the MMLU
> task**: HumanEval+ / MBPP+ / GSM8K / IFEval / TruthfulQA all agree between m140 and m141, and
> TruthfulQA — the other knowledge loglikelihood task — is *flat* across the whole 12B ladder
> (Q2 0.5008, Q3 0.4986, QAT-Q4 0.5295, native-Q4 0.5039). A genuine Q4 knowledge jump would move
> it. The Q2/Q3 rungs were also measured under an *older* lm_eval git (`63f565aba`) than Q4
> (`194c1059b`), so the 12B MMLU ladder is not on one stable harness.
> **TODO (flagged, not re-run here): re-measure the 12B MMLU ladder m93/m105/m140/m141 on a single
> harness.**

### E2B UD-Q2_K_XL (m146 QAT vs m119 native) — ✅ complete (5/7 benches)
| bench | delta (QAT−native) | 95% CI | n_t/n_c |
|---|---|---:|---|
| humaneval-plus | **−0.3110** | [−0.4090, −0.2129] | 164/164 |
| mmlu | −0.0296 | [−0.0753, +0.0161] | 912/912 |
| truthfulqa_mc2 | +0.0466 | [−0.0913, +0.1845] | 100/100 |
| gsm8k | −0.2900 | [−0.4226, −0.1574] | 100/100 |
| ifeval | −0.1700 | [−0.3066, −0.0334] | 100/100 |
| mbpp-plus | **NO RESULT** (not 0) | — | — |
| arc_challenge | **NO RESULT** (not 0) | — | — |

mbpp-plus: the QAT evalplus evaluate step aborted with `AssertionError: Missing problems
in samples` (only 179 unique MBPP completions; repeated `Unknown error` / `end of time`
retries on the last items). arc_challenge: the m146 GGUF shim refused a continuation token
(`SHIM ERROR ... refusing to guess`). Both are **non-measurements**, not nulls.

**Preliminary read (E2B Q2):** QAT does **not** rescue the sub-3-bit regime. At equal
nominal recipe the QAT file loses heavily on code (HumanEval+ −0.311, the largest and
clearest gap), GSM8K (−0.290) and IFEval (−0.170); MMLU (−0.030, ns) and TruthfulQA
(+0.047, ns) are unchanged. The QAT file is also 0.36 bpw *smaller*, so even the null
knowledge cells are not evidence that "QAT bits are free" — the capability tasks (code,
arithmetic, instruction-following) are exactly where the loss lands.

### E2B UD-Q4_K_XL (m147 QAT vs m148 native) — ✅ complete (7/7 benches)
| bench | delta (QAT−native) | 95% CI | n_t/n_c |
|---|---|---:|---|
| humaneval-plus | +0.0061 | [−0.0927, +0.1049] | 164/164 |
| mbpp-plus | +0.0344 | [−0.0369, +0.1056] | 378/378 |
| mmlu | +0.0055 | [−0.0398, +0.0508] | 912/912 |
| arc_challenge | −0.0200 | [−0.1585, +0.1185] | 100/100 |
| truthfulqa_mc2 | −0.0208 | [−0.1593, +0.1178] | 100/100 |
| gsm8k | −0.0400 | [−0.1565, +0.0765] | 100/100 |
| ifeval | −0.0200 | [−0.1444, +0.1044] | 100/100 |

Raw sides: QAT m147 — HumanEval+ 0.707 (116/164), MBPP+ 0.516 (195/378), MMLU 0.583, ARC-c 0.480,
TruthfulQA 0.501, GSM8K 0.750, IFEval 0.710. Native m148 — HumanEval+ 0.701 (115/164), MBPP+ 0.481
(182/378), MMLU 0.578, ARC-c 0.500, TruthfulQA 0.521, GSM8K 0.790, IFEval 0.730. bpw QAT 4.529 vs
native 5.482 (d=−0.953).

**Read (E2B Q4).** **All 7 cells are null** — every delta's 95% CI spans 0, and the largest
magnitude is only −0.040 (GSM8K). Unlike the E2B **Q2** pair (where QAT lost −0.311 HumanEval+ /
−0.290 GSM8K / −0.170 IFEval at 0.36 fewer bpw), at **Q4** the QAT file is 0.95 bpw *smaller* than
its native partner yet loses nothing measurable on any of the 7 benchmarks — it is even nominally
ahead on HumanEval+ (+0.006), MBPP+ (+0.034) and MMLU (+0.006). So the E2B size range shows a Q2
collapse but no Q4 damage; the result is “no measurable QAT effect at Q4”, not “QAT helps”.

### E4B UD-Q2_K_XL (m149 QAT vs m121 native) — ✅ complete (7/7 benches)
| bench | delta (QAT−native) | 95% CI | n_t/n_c |
|---|---|---:|---|
| humaneval-plus | **−0.1646** | [−0.2686, −0.0607] | 164/164 |
| mbpp-plus | **−0.2116** | [−0.2812, −0.1421] | 378/378 |
| mmlu | **−0.1502** | [−0.1951, −0.1054] | 912/912 |
| arc_challenge | −0.1100 | [−0.2452, +0.0252] | 100/100 |
| truthfulqa_mc2 | +0.0598 | [−0.0779, +0.1975] | 100/100 |
| gsm8k | **−0.3900** | [−0.5111, −0.2689] | 100/100 |
| ifeval | −0.0600 | [−0.1813, +0.0613] | 100/100 |

Raw sides: QAT m149 — HumanEval+ 0.530 (87/164), MBPP+ 0.370 (140/378), MMLU 0.500, ARC-c 0.350,
TruthfulQA 0.578, GSM8K 0.450, IFEval 0.710. Native m121 — HumanEval+ 0.695 (114/164), MBPP+ 0.582
(220/378), MMLU 0.650, ARC-c 0.460, TruthfulQA 0.518, GSM8K 0.840, IFEval 0.770. bpw QAT 3.451 vs
native 3.998 (d=−0.547).

**Read (E4B Q2).** QAT does **not** rescue the sub-3-bit regime: **4 of 7 cells are significant
losses** — HumanEval+ −0.165, MBPP+ −0.212, MMLU −0.150 and GSM8K −0.390 — while ARC-c −0.110,
TruthfulQA +0.060 and IFEval −0.060 are null. This is the E2B Q2 shape, sharper: at ~0.55 fewer
bpw the QAT file is worse on code, knowledge and arithmetic, which confirms that at Q2 the bit
budget (not QAT) drives the score. This is the strongest QAT-vs-native contrast in the batch.

### E4B UD-Q4_K_XL (m155 QAT vs m156 native) — ✅ complete (7/7 benches)
| bench | delta (QAT−native) | 95% CI | n_t/n_c |
|---|---|---:|---|
| humaneval-plus | +0.0366 | [−0.0529, +0.1261] | 164/164 |
| mbpp-plus | +0.0556 | [−0.0131, +0.1242] | 378/378 |
| mmlu | +0.0132 | [−0.0286, +0.0549] | 912/912 |
| arc_challenge | +0.0300 | [−0.1085, +0.1685] | 100/100 |
| truthfulqa_mc2 | −0.0141 | [−0.1503, +0.1221] | 100/100 |
| gsm8k | +0.0500 | [−0.0501, +0.1501] | 100/100 |
| ifeval | −0.0500 | [−0.1574, +0.0574] | 100/100 |

Raw sides: QAT m155 — HumanEval+ 0.799 (131/164), MBPP+ 0.659 (249/378), MMLU 0.715, ARC-c 0.510,
TruthfulQA 0.585, GSM8K 0.870, IFEval 0.790. Native m156 — HumanEval+ 0.762 (125/164), MBPP+ 0.603
(228/378), MMLU 0.702, ARC-c 0.480, TruthfulQA 0.599, GSM8K 0.820, IFEval 0.840. bpw QAT 4.519 vs
native 5.455 (d=−0.936).

**Read (E4B Q4).** Like E2B Q4 and unlike E4B Q2: **all 7 cells are null** — every delta's CI
spans 0 (largest +0.056 on MBPP+) — while the QAT file is 0.94 bpw smaller. At Q4 the E4B QAT file
is nominally ahead on code/arithmetic/MMLU but never significantly. This completes the batch
pattern: QAT neither helps nor hurts measurably at Q4; the significant QAT effects are all
sub-3-bit (Q2).

### Other axis-1.6 pairs — ⏳ pending / ⛔ BLOCKED
| pair | recipe | state |
|---|---|---|
| m144 QAT vs m145 native (26B-A4B) | UD-Q4_K_XL | ⏳ native pending; m145 native is BLOCKED-on-VRAM (see below) |
| m142 QAT vs m143 native (31B) | UD-Q4_K_XL | ⛔ BLOCKED-on-VRAM (both sides; non-measurement) |

**No runnable axis-1.6 pair remains.** Every non-BLOCKED pair is complete (12B Q4, E2B Q2, E2B Q4,
E4B Q2, E4B Q4); the only open rows are the VRAM-blocked 31B pair and the 26B-A4B native control.

A pair's delta needs **both** sides; a one-sided row is listed as ◐ and is **not** a comparison.
Rows are added to F12 and this file as the campaign drains; no one-sided value is ever shown as a
delta.

**⚠ Recipe-label confound (GGUF metadata, 2026-10-13).** Every QAT file in this batch is stored
`general.file_type=2` (Q4_0 lineage) regardless of its nominal label: `general.name` = `Gemma-4
12B IT (smart Q4_0, QAT-lossless)`, `Gemma-4 E2B IT (mobile wNa8o8 -> gguf)`, `Gemma-4 E4B IT
(mobile wNa8o8 -> gguf, faithful)`, `Gemma-4 26B-A4B IT (smart Q4_0, QAT-lossless)`. The native
partners are real K-quants (12B Q4 = `file_type=15` Q4_K_M; Q2 = Q2_K; Q3 = Q3_K_M). So the
"same nominal `UD-Q?_K_XL` recipe" framing is false at the byte level: each QAT-vs-native delta
mixes a *scheme* change with the bpw change and the QAT change.

### Axis 1.6 verdict (from the five complete pairs)
**Quantisation-aware training (量化感知训练, QAT) does not buy quality at a fixed recipe.**
At the same nominal UD-Q?_K_XL recipe the QAT file is **0.36–0.95 bpw smaller** than its
native partner (12B 4.512 vs 4.949; E2B Q2 3.779 vs 4.138; E2B Q4 4.529 vs 5.482), so the
contrast is really “QAT + fewer bits” vs “native + more bits”, not a byte-matched test.
* **12B Q4** — code/instruction cells are all null (HumanEval+ −0.006, MBPP+ −0.011, GSM8K
  +0.020, IFEval −0.020, TruthfulQA +0.026, all CIs span 0); the single large cell (MMLU
  −0.197) is flagged suspect because the native-Q4 rung itself is the outlier.
* **E2B Q4** — all 7 cells null (largest |delta| −0.040) despite the QAT file being 0.95 bpw
  smaller. At Q4 the QAT file neither helps nor hurts measurably; unlike Q2 it does not collapse.
* **E4B Q4** — all 7 cells null (largest +0.056 on MBPP+) while the QAT file is 0.94 bpw smaller;
  nominally ahead on code/arithmetic/MMLU but never significantly. Same Q4 pattern as E2B Q4.
* **E2B Q2** — no rescue of the sub-3-bit regime: HumanEval+ −0.311, GSM8K −0.290, IFEval
  −0.170 (all significant), MMLU/TruthfulQA null. This is consistent with the lower bpw.
* **E4B Q2** — same sub-3-bit collapse, and the strongest evidence in the batch: 4 of 7 cells
  significant (HumanEval+ −0.165, MBPP+ −0.212, MMLU −0.150, GSM8K −0.390) at 0.55 fewer bpw;
  ARC-c / TruthfulQA / IFEval null.
* Net: the only significant QAT effects found are **negative**, and they all land in the
  sub-3-bit (Q2) regime — E2B Q2 and E4B Q2 — where the QAT file gives up 0.36–0.55 bpw; at Q4
  (12B, E2B and E4B) the QAT file gives up 0.44–0.95 bpw and is statistically indistinguishable
  from its native partner. There is no evidence QAT recovers quality lost to quantisation. One
  complete matched cell (12B MMLU) contradicts this and must be re-checked before any “QAT helps
  at Q4” claim.

---

## Axis 1.5 — GSQ-RCO vs the standard Qwen3.8-27B quant ladder — ✅ complete

Held fixed: base model Qwen3.8-27B. Varied: quantisation scheme (GSQ-RCO vs unsloth UD).
There is no 1:1 byte-matched partner, so each GSQ quant is compared (a) to the nearest native
ladder point and (b) to the native score linearly interpolated to the GSQ quant's own bpw.
Item-level SE = `sqrt(p(1-p)/n)`; delta = GSQ − native (positive favours GSQ-RCO). All cells are
the canonical 7-benchmark protocol; bpw is the true effective value from `.wrapup/bpw_map.json`.

Native ladder (all 3 rungs measured):

| native rung | bpw | HumanEval+ | MBPP+ | MMLU | ARC-c | TruthfulQA | GSM8K | IFEval |
|---|---:|---|---|---|---|---|---|---|
| UD-Q2_K_XL (m91) | 2.878 | 0.8963 | 0.7619 | 0.8037 | 0.6100 | 0.5210 | 0.9800 | 0.8300 |
| UD-Q3_K_XL (m100) | 3.850 | 0.8354 | 0.7381 | 0.8366 | 0.5900 | 0.5693 | 0.9600 | 0.7500 |
| UD-IQ4_XS (m152) | 4.173 | 0.8720 | 0.7593 | 0.8498 | 0.6000 | 0.5685 | 0.9800 | 0.7700 |

GSQ-RCO treatments (both complete):

| GSQ quant | bpw | HumanEval+ | MBPP+ | MMLU | ARC-c | TruthfulQA | GSM8K | IFEval |
|---|---:|---|---|---|---|---|---|---|
| GSQ-RCO IQ3_XXS (m150) | 3.058 | 0.8476 | 0.7540 | 0.8103 | 0.6100 | 0.5733 | 0.9400 | 0.8200 |
| GSQ-RCO IQ3_S (m151) | 3.549 | 0.8963 | 0.7646 | 0.8279 | 0.6000 | 0.5499 | 0.9600 | 0.8500 |

### GSQ-RCO IQ3_XXS @3.058 vs nearest native UD-Q2_K_XL @2.878 (+0.180 bpw)

| bench | delta (nearest, n) | 95% CI | delta (native interp @3.058) | 95% CI |
|---|---|---|---|---|
| humaneval-plus | −0.0488 (164/164) | [−0.1209, +0.0234] | −0.0375 | [−0.1096, +0.0346] |
| mbpp-plus | −0.0079 (378/378) | [−0.0690, +0.0531] | −0.0035 | [−0.0646, +0.0575] |
| mmlu | +0.0066 (912/912) | [−0.0296, +0.0428] | +0.0005 | [−0.0357, +0.0367] |
| arc_challenge | +0.0000 (100/100) | [−0.1352, +0.1352] | +0.0037 | [−0.1315, +0.1389] |
| truthfulqa_mc2 | +0.0523 (100/100) | [−0.0855, +0.1901] | +0.0433 | [−0.0945, +0.1811] |
| gsm8k | −0.0400 (100/100) | [−0.0940, +0.0140] | −0.0363 | [−0.0903, +0.0177] |
| ifeval | −0.0100 (100/100) | [−0.1153, +0.0953] | +0.0048 | [−0.1005, +0.1101] |

### GSQ-RCO IQ3_S @3.549 vs nearest native UD-Q3_K_XL @3.850 (−0.301 bpw)

| bench | delta (nearest, n) | 95% CI | delta (native interp @3.549) | 95% CI |
|---|---|---|---|---|
| humaneval-plus | +0.0610 (164/164) | [−0.0125, +0.1344] | +0.0421 | [−0.0314, +0.1156] |
| mbpp-plus | +0.0265 (378/378) | [−0.0351, +0.0881] | +0.0191 | [−0.0425, +0.0807] |
| mmlu | −0.0088 (912/912) | [−0.0431, +0.0255] | +0.0014 | [−0.0329, +0.0357] |
| arc_challenge | +0.0100 (100/100) | [−0.1261, +0.1461] | +0.0038 | [−0.1322, +0.1399] |
| truthfulqa_mc2 | −0.0194 (100/100) | [−0.1570, +0.1182] | −0.0045 | [−0.1420, +0.1331] |
| gsm8k | +0.0000 (100/100) | [−0.0543, +0.0543] | −0.0062 | [−0.0605, +0.0481] |
| ifeval | +0.1000 (100/100) | [−0.0100, +0.2100] | +0.0752 | [−0.0348, +0.1853] |

**Verdict (complete).** Under **both** controls — nearest native quant and the bpw-interpolated
native ladder — the GSQ-RCO quants are statistically indistinguishable from the native unsloth
ladder: **all 28 deltas have 95% CIs that span 0**. The only near-significant cell is IQ3_S IFEval
**+0.100 [−0.010, +0.210]** (nearest) / +0.075 [−0.035, +0.185] (interp): a single 100-item task
whose CI touches 0. The native ladder is itself non-monotone (MMLU rises with bpw while code and
GSM8K fall), which is why the interpolated control matters and why a single-label comparison would
mis-rank the GSQ quants. **GSQ-RCO is a size/format option, not a quality upgrade, at matched
effective bpw on Qwen3.8-27B.** Finalized as **F13** in `FINAL_REPORT.md`; figure `fig5_axes.png`
panel B.

**Writer note (2026-10-14 02:05).** Axis 1.5 is complete: m150 (IQ3_XXS) and m151 (IQ3_S) are
fully measured and the native ladder m91/m100/m152 is complete. This section is final. (This is
*not* a statement about axis 1.6, which is still draining — see the top of this file.)

---

## Axis 7 — DiffusionGemma vs same-size autoregressive gemma-4-26B-A4B

⛔ **GATE-FAIL.** `m154-diffusiongemma-26b-a4b-q4km` is excluded: no local llama.cpp build
accepts the architecture `diffusion-gemma` (`llama_model_load: error loading model: unknown
model architecture: 'diffusion-gemma'`; both build 4399 and the 0.2.0 build). There is no
diffusion-side measurement, so **no comparison exists** until a runtime supports the arch.
The autoregressive control (m145 native gemma-4-26B-A4B UD-Q4_K_XL) is itself BLOCKED-on-VRAM.
Axis 7 is reported as runtime-blocked, never as a null/0.

---

## BLOCKED-on-VRAM (non-measurements, never 0)

| tag | file | bytes (GiB) | cause |
|---|---|---:|---|
| m142-qat-gemma31b-q4 | gemma-4-31B-it-qat-UD-Q4_K_XL.gguf | 16.10 | co-resident foreign server on :8834; `cudaMalloc failed` / KV alloc fail |
| m143-native-gemma31b-q4 | gemma-4-31B-it-UD-Q4_K_XL.gguf | 17.53 | same; ≥ m142 footprint, cannot fit in ~17.9 GiB free |
| m145-native-gemma26b-a4b-q4 | gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf | 15.84 | same co-resident constraint |

See `.wrapup/AXES_BLOCKED.md` for the `server.log` evidence. Operator decision (option a): no
end-of-run retry pass.

---

## Provenance

- Auto-readout: `.wrapup/AXES_RESULTS.md` (refreshed by `.wrapup/axes_finisher.sh` every 10 min).
- Machine JSON: `.wrapup/axes_findings.json`.
- Figure: `figures/fig5_axes.png` (`.wrapup/axes_figure.py`).
