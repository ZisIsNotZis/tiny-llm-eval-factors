# MOE_STRUCTURE.md — BRAINSTORM Tier 2A/2C: is *active* param count the predictor of quantised score for MoE?

Method: `RESEARCH_METHOD.md`. Dataset: `experiments.sqlite`, protocol
`multipl-e-raw-greedy-768` only (raw completion, greedy, 768 tokens, temp 0,
top_p .95 / top_k 40 / min_p .05, KV q8_0/q8_0). Score = pooled MultiPL-E
cpp+python pass@1 (n = 322 items per point, item-level SE in the table).
Model structure (`expert_count`, `expert_used`) is read from **GGUF metadata**,
not from the filename. Reproducer: `.wrapup/moe_structure_analysis.py`
→ `.wrapup/moe_structure.json`.

Run tags: `m1-multipl-e` (Qwen3.5-4B), `m2-multipl-e` (Qwen3.5-9B),
`m3-quant-ladder` (Qwen3.5-2B), `m5-family-ladder` (granite, gemma-4 E2B/E4B),
`m6-family-ladder` (Qwen3.5-0.8B, Qwen3.6-35B-A3B), `m10-family-ladder`
(Qwen3.8-27B, gemma-4-26B-A4B, LFM2.5-8B-A1B, Nemotron-4B, MiniCPM5-2B,
Ornith-9B), `m10-granite-q34`, `m21-bonsai-ternary`.

## 0. One anchor had to be quarantined first (the 0.00 rule)

`gemma-4-26B-A4B` was run under the raw protocol and scored the harness floor
(cpp/py = 0.056/0.031 at Q2, 0.025/0.043 at Q3). That is a **harness failure,
not a model result**, verified two ways:

* `t4_gemma_repair.log` probed five raw-completion variants on gemma-4-12B
  (`raw-baseline`, `raw-prime`, `raw-turnprime`, `raw-prime-stop`) — **all scored
  0/40**; only a chat turn with `enable_thinking=false` produced compilable code.
* its raw completions are markdown *prose*, not code: average length 1.8–2.0 kB
  with fenced blocks and `**bold**` reasoning (e.g. "**Wait, I need to know the
  completion of the code.** … **Functionality:** …"), versus 0.4–1.2 kB of plain
  code for every working model.

So the two `gemma-4-26B-A4B` raw points are excluded from the fits (flagged, not
silently dropped). The gemma-4 **dense** E2B/E4B points are kept: their raw scores
are 0.24–0.69, i.e. not the floor, so they are not harness failures.
The 2C panel re-runs gemma-4-26B-A4B under the repaired protocol.

## 1. The data (31 valid points: 27 dense, 4 MoE)

| model (tag) | total B | active B | experts (top) | quant | cpp | py | score ± SE |
|---|---|---|---|---|---|---|---|
| Qwen3.5-0.8B | 0.8 | 0.8 | – | Q2/Q3 | .043/.068 | .068/.130 | .056/.099 |
| Qwen3.5-2B | 2.0 | 2.0 | – | IQ2..Q5 | .112→.261 | .137→.280 | .124→.270 |
| Qwen3.5-4B | 4.0 | 4.0 | – | Q2/Q3 | .342/.453 | .354/.503 | .348/.478 |
| Qwen3.5-9B | 9.0 | 9.0 | – | Q2/Q3 | .435/.584 | .348/.522 | .391/.553 |
| Qwen3.8-27B | 27 | 27 | – | Q2/Q3 | .758/.807 | .745/.733 | .752/.770 |
| Ternary-Bonsai-27B | 27 | 27 | – | Q2_g64 | .696 | .764 | .730 |
| gemma-4-E2B / E4B | 2.4 / 4.6 | = | – | Q2/Q3 | .298/.534 | .186/.348 | .242/.441 |
| granite-4.1-3b | 3.0 | 3.0 | – | Q2/Q3/Q4 | .037→.571 | .056→.304 | .047→.438 |
| Nemotron-3-4B, MiniCPM5-2B, Ornith-9B | 4/2/9 | = | – | mixed | | | |
| **LFM2.5-8B-A1B** (MoE) | **8** | **1** | **32 (4)** | Q2/Q3 | .162/.143 | .062/.037 | **.112/.090** |
| **Qwen3.6-35B-A3B** (MoE) | **35** | **3** | **256 (8)** | Q2/Q3 | .708/.721 | .696/.758 | **.702/.739** |
| gemma-4-26B-A4B (MoE) | 26 | 4 | 128 (8) | Q2/Q3 | — | — | *quarantined, see §0* |

## 2. Regression: quantised score on (total, active, experts, quant level)

OLS, response = pooled cpp+py score. Features are ln-transformed; `is_moe` =
`expert_count>0`; `ln_experts` = log(1+expert_count); quant level = ln(quant_ratio)
bytes-per-param (fp16 = 1.0). corr(ln total, ln active) = 0.695, VIF = 1.93 —
collinear but separable.

| model | adj R² | AIC | family-LOO RMSE | key coefficients (t) |
|---|---|---|---|---|
| `ln total + ln quant` | 0.668 | −29.5 | **0.1495** | ln_total **+0.214 (7.9)**, ln_quant +0.321 (3.6) |
| `ln active + ln quant` | 0.588 | −22.8 | 0.1668 | ln_active +0.203 (6.7), ln_quant +0.117 (1.3, ns) |
| `total + active + quant` | 0.750 | −36.2 | 0.1627 | total +0.142 (4.4), active +0.104 (3.2) |
| `total + quant + is_moe` | 0.765 | −38.1 | — | ln_total +0.246 (10.0), **is_moe −0.253 (−3.5)** |
| `active + quant + is_moe + ln_experts` | **0.807** | **−42.3** | — | ln_active +0.227 (9.7), is_moe −0.542 (−2.2), ln_experts +0.183 (3.5) |
| `total+active+quant+is_moe+ln_experts` | 0.800 | −39.1 | — | ln_total **−0.127 (−1.4, ns)**, ln_active +0.353 (4.3) |
| `total + quant + is_moe + (is_moe·ln_quant)` | 0.761 | −35.7 | — | interaction **−0.300 (−0.8, ns)** |

## 3. Where each MoE sits on the dense size curve

Inverting the dense-only size fit for each MoE ("effective dense size" = the dense
model that would score the same at the same quant):

| MoE (total/active) | quant | score | effective dense size | vs active | vs total |
|---|---|---|---|---|---|
| LFM2.5-8B-A1B (8/1) | Q2 | 0.112 | **2.0 B** | 2.0× | 0.24× |
| LFM2.5-8B-A1B (8/1) | Q3 | 0.090 | **1.2 B** | 1.2× | 0.16× |
| Qwen3.6-35B-A3B (35/3) | Q2 | 0.702 | **26.5 B** | 8.8× | 0.76× |
| Qwen3.6-35B-A3B (35/3) | Q3 | 0.739 | **21.8 B** | 7.3× | 0.62× |

The two valid MoE families land on **opposite sides** of the total/active question:
LFM2.5-8B-A1B behaves like its *active* (1–2 B), Qwen3.6-35B-A3B behaves like its
*total* (22–27 B). Same protocol, same metric. The disagreement is ~15× in
effective dense size.

## 4. Verdict

1. **As a single predictor, TOTAL edges out ACTIVE** — higher adj R² (0.668 vs
   0.588), lower AIC (−29.5 vs −22.8), lower family-held-out RMSE (0.1495 vs
   0.1668). Under `active_only` the quant term even loses significance (t 1.3). The
   reason is Qwen3.6-35B-A3B: a 3 B-active MoE that scores like a ~22–27 B dense
   model, which active alone cannot explain.
2. **But conditional on MoE structure, ACTIVE is the informative one and TOTAL
   becomes redundant**: in `total+active+is_moe+ln_experts` the total coefficient
   collapses to −0.13 (t −1.4, ns) while active stays +0.35 (t 4.3). Adding
   `is_moe` and `ln_experts` lifts adj R² to 0.81 (best AIC).
3. **So neither alone predicts a MoE's quantised score.** MoE is a separate class
   with a large negative level offset vs the dense curve (is_moe ≈ −0.25 to −0.54,
   i.e. a MoE scores 0.05–0.13 below a *same-size, same-quant* dense model), and
   the spread *between* MoE families (active-like LFM vs total-like Qwen) is larger
   than the total-vs-active distinction itself.
4. **Sparsity lowers the ceiling, it does not steepen the quant slope.** The
   `is_moe × ln_quant` interaction is not significant (−0.30, t −0.8): within
   this panel a MoE loses about as many points per byte of quantisation as a dense
   model of the same effective capacity — the MoE penalty is a level shift, not
   extra quant fragility.

**Caveats (read before citing).** MoE evidence is 2 families / 4 points
(+2 quarantined). "Expert count" enters only as a weak positive term estimated off
three anchors (32/128/256) and is confounded with family; 2B will test granularity
directly. Family is a first-order confounder throughout — the regression has no
family fixed effect for the MoE rows because there is one MoE per family.

## 5. 2C — the one targeted panel that breaks the tie

To turn 2 MoE families into 3 and to break total/active collinearity cleanly, one
panel (`.wrapup/run_m26.sh`, launched detached under the GPU flock) re-runs, under
the **same** repaired protocol (`mpl-chat-nothink-greedy-768`, both sides — SSOT
§3.2 forbids mixing protocols):

* `gemma-4-26B-A4B` (26 B total, 4 B active) Q2/Q3 × cpp/py — the missing *valid*
  MoE anchor (the raw rows are quarantined in §0);
* `Qwen3.8-27B` dense (27 B total = 27 B active) Q2/Q3 × cpp/py — the matched-total
  dense twin, re-run under the same protocol.

Matched TOTAL ≈ 26–27 B, ACTIVE 4 B vs 27 B → a clean orthogonal contrast, with the
known family confound noted. Results land in `.wrapup/m26_summary.jsonl`
(shape `{"model","lang","n","pass","score","protocol"}`) for the orchestrator to
ingest; this file will be updated with the outcome.
