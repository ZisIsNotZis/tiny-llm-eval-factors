# STUDY INVENTORY — every axis we measured

*DB snapshot: `experiments.sqlite` — **7911 rows · 208 models · 41 benchmark columns ·
59 protocols · 140 panel run_tags** (2026-10-13). Source of truth: `FINAL_REPORT.md` (findings F1–F13),
`RESULTS_BY_COMPARISON.md` (tables A–H), `QUEUE.md`, `BACKLOG.md`, `conclusions.md`.*

## Scale of the study

| | count |
|---|---:|
| experiment rows | 7911 |
| distinct model files | 208 |
| benchmark columns | 41 |
| protocols | 59 |
| panel run_tags | 140 |
| standard benchmarks | 7 |
| comparison tables (A–H) | 8 |
| findings (F1–F13) | 13 |
| **distinct research axes** | **21** |

## The 18 original axes

| # | axis (研究项) | held constant | varied | main panels | result / finding |
|---|---|---|---|---|---|
| 1 | **Quantisation level / BPW** | family, harness, protocol | effective bpw step | m1,m2,m3,m5,m6,m10,m33, m61–67, m71–124 | **Step then plateau**; `Q2→Q3` +0.155, `Q3→Q4` +0.008 (F2) |
| 2 | **Model size** | family + quant recipe | 0.8B→35B | table B, m33 | Deficit = headroom; 2B/Q2 floor collapse (F3) |
| 3 | **Scheme: IQ vs K (imatrix)** | model, ~file size | IQ3_XXS vs Q2_K_XL | m23, m50 | **Scheme > bits**: pooled +0.056 [+0.008,+0.104] (F4) |
| 4 | **Quantiser vendor** | model, size (−0.6%) | bartowski vs unsloth | m25, m37 | **Null** +0.009 [−0.058,+0.077] (F4) |
| 5 | **Ternary / sub-2-bit** | family, protocol | TQ1_0, Q2_0, Q1_0, IQ1_M | m21,m24,m35,m36,m39,m41 | Competitive but **model/recipe-specific**, not a ternary law (F5) |
| 6 | **MoE vs dense** | harness, protocol | dense vs MoE at same bpw | m26, m45, m56 | MoE degrades differently; basis for F11 |
| 7 | **MoE layer bit-allocation** | base weights, ~size | which tensors get low bits | **m55, m132–134** | **Non-expert layers decide**; highest bpw worst (F11) |
| 8 | **Benchmark / task type** | family, ladder | 7 standard + code | campaign m68–m124 | **Sensitivity is a vector**, ~11× spread (F9) |
| 9 | **Code language** | model, bpw | cpp/py/java/js/rs/rb | m1,m2,m38,m42,m51,m54,m56,m57,m60 | Sign invariant; used for statistical power |
| 10 | **Generation protocol** | model, quant | raw vs chat; forced-JSON vs native tools | m4, m4b, w2 | **Flips the sign of quant conclusions, twice** (F8) |
| 11 | **Sampling** | model, bpw, ctx | temp, top_k, top_p | m27, m31, m131 | Mostly **inert**; temp costs code not knowledge (F6) |
| 12 | **KV-cache quantisation** | model, bpw, ctx | f16/q8_0/q4_0 | m30, m130 | **No measurable cost** down to q4_0 (F6) |
| 13 | **Compute precision (flash-attn)** | model, bpw | `-fa` on/off, V-cache | m29, m44 | No-op at Q3, real at Q2 (F6) |
| 14 | **Speculative decoding (MTP)** | model, ctx | draft depth 0/1/2/4 | m28, m52, **m125–129** | **+36%→+93% tok/s**, no quality cost; MMLU bit-identical (F10) |
| 15 | **Thinking on/off** | model file | `reasoning` on/off | m61–67 gsm8k | Thinking-off is primary; on is worse at small budget (table H) |
| 16 | **PPL vs task score** | family ladder | PPL vs pass@1 | ppl_analysis, reanalysis | **Weak proxy**, wrong direction in ~30% (F7) |
| 17 | **Tool calling (BFCL)** | model, quant | single-turn + 4 multi-turn categories | m4,m4b,m7–m20,m22,m32,m36 | 2B/Q2 pins to ~0.005 floor; retired after standards (F3) |
| 18 | **GSM8K metric definition** | same run | strict-match vs flexible-extract | m61–67 gsm8k-strict | `strict` scored **format compliance**, not arithmetic (correction) |

## AXES follow-up campaign — axes 1.5 / 1.6 / 7 (added 2026-10-13)

The AXES campaign (`.wrapup/AXES_PLAN.md`, `.wrapup/AXES_CAMPAIGN.txt`) added three axes on the
same canonical protocols. Full readout: `.wrapup/AXES_RESULTS_SYNTHESIS.md` (auto:
`.wrapup/AXES_RESULTS.md`); findings: F12–F13.

| # | axis (研究项) | held constant | varied | panels | status / result |
|---|---|---|---|---|---|
| 1.6 | **QAT vs native** (quantisation-aware training / 量化感知训练) | model size + nominal `UD-Q?_K_XL` recipe | whether weights were QAT-trained | complete: m140/m141 (12B Q4), m146/m119 (E2B Q2), m147/m148 (E2B Q4), m149/m121 (E4B Q2), m155/m156 (E4B Q4); BLOCKED: m144/m145 (26B-A4B native), m142/m143 (31B) | **Complete — all runnable pairs (5/5)** — 12B Q4 (code/instruction null, MMLU suspect), E2B Q2 and E4B Q2 (QAT significantly worse, tracks fewer bpw: E4B Q2 4/7 cells significant), E2B Q4 and E4B Q4 (QAT is 0.94–0.95 bpw smaller yet all 7 cells null); no QAT quality bonus at any recipe; F12. Note: every QAT file is `file_type=2` (Q4_0 lineage) vs a real K-quant native, so the contrast is not one-factor |
| 1.5 | **GSQ-RCO scheme** | base model Qwen3.8-27B | GSQ-RCO IQ3_XXS/IQ3_S vs native UD-Q2/Q3/IQ4_XS ladder | m150, m151 vs m91/m100/m152 | **Complete** — both GSQ quants are indistinguishable from the native ladder at matched effective bpw (compared to the nearest native quant **and** to the native score interpolated to each GSQ quant's own bpw); all 28 deltas' 95% CIs span 0 (only near-significant cell: IQ3_S IFEval +0.10 [−0.01,+0.21]); GSQ-RCO is a size/format option, not a quality upgrade; F13 |
| 7 | **DiffusionGemma** | size + quant class | diffusion vs autoregressive gemma-4-26B-A4B | m154 vs m145 | **Runtime-blocked (gate-fail)** — no local llama.cpp accepts arch `diffusion-gemma`; no value fabricated |

BLOCKED-on-VRAM (non-measurements, never 0): **m142/m143** (gemma-4-31B QAT + native Q4; >16 GiB
weights, co-resident foreign server on :8834) and **m145** (gemma-4-26B-A4B native Q4). Evidence:
`.wrapup/AXES_BLOCKED.md`.

## Standard benchmark campaign (the multi-benchmark requirement)

`CAMPAIGN.txt` — 64 entries (54 models + 10 replicates), **54/54 models measured**, 4928 rows.
Seven columns: HumanEval / HumanEval+ / MBPP / MBPP+ / MultiPL-E · MMLU · ARC-C · TruthfulQA ·
GSM8K · IFEval. One failed stage: Phi-4-mini-Q2_K EvalPlus = **NO RESULT** (parser rejects Q2
output), not 0.0.

## Figures

| figure | what it shows |
|---|---|
| `fig1_sensitivity.png` | F9 slope vector + paired forest + grouped paired test + granite worked example |
| `fig2_slope_heatmap.png` | family × benchmark slope matrix (all controlled cells, no aggregation) |
| `fig3_steps.png` | F2 step/plateau curve + F3 2B floor collapse |
| `fig4_moe.png` | F11 MoE bit-allocation, highest bpw worst |
| `fig5_axes.png` | AXES axes: 1.6 QAT-vs-native forest + 1.5 GSQ-RCO forest + QAT bpw confound (中文/English) |
