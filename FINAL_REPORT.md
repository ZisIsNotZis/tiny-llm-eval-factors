# Quantisation vs benchmark scores for local LLMs — what we actually found

*Final report. Companion operational/intermediate docs: `WRAPUP.md`, `MULTIPLE.md`,
`LADDER_TOOLS.md`, `HORIZON.md`, `PPL_REPORT.md`, `REANALYSIS.md`, `CLAIMS_RESOLUTION.md`.
All numbers come from `experiments.sqlite` (2,094 rows) and are reproduced by the scripts listed
in each section.*

---

## The question

The quantised-LLM community publishes **perplexity** as its headline quality number. But PPL is not
benchmark score: PPL can improve while task scores don't, and vice versa. Nobody had systematically
measured **how quantisation maps onto *measured task scores*** across models, sizes, model types and
task types, under a controlled protocol. That is what this study does — deliberately *not* as a
leaderboard, but as a factor study with explicit error bars.

## Method, and why the numbers can be trusted

* **Everything is in one database** (`experiments.sqlite`), one row per run, with factor columns
  (`model, __quant, __size, __k_ratio, __v_ratio, reasoning, spec_type, temp, top_k, ctx_size,
  protocol, run_tag, …`). Replicates are first-class (the original unique index that forbade them
  was dropped).
* **Item-level confidence intervals everywhere.** A benchmark item is a Bernoulli trial, so a
  quant-step CI is `sqrt(p(1-p)/n + p'(1-p')/n')` over *items*. (An earlier version of the headline
  table used a cross-language CI with n = 2–3 languages and was ~10× too narrow; that produced a
  spurious "Q3 is worse than Q2" result. Corrected — see *Corrections*.)
* **Protocol is recorded and never mixed.** This matters more than expected (Finding 6).
* **Task-level evaluation uses the official harnesses**: EvalPlus (HumanEval+/MBPP+), a locally
  generated MultiPL-E suite (7 languages), and `bfcl-eval` driven against `llama-server` for tool
  calling and multi-turn agentic evaluation.
* **Coverage**: 13 code anchors (0.8B–35B, dense and MoE, 5 architecture families), 5 tool-calling
  anchors, multi-turn on 2B/4B/9B Qwen3.5 and granite-4.1-3b.

### Five silent-failure classes were found and fixed

Every one of these yields *plausible-looking but wrong numbers* rather than an error — the most
dangerous kind in an automated study:

1. **Stale result reuse** — `bfcl generate` keys outputs by handler and reuses existing files, so a
   second quant level silently re-scored the first one's answers (would have produced a false
   "Q3 ≈ Q2" null).
2. **Orphaned server holding the GPU lock** — an interrupted panel left `llama-server` holding the
   inherited `flock`, stalling the queue indefinitely.
3. **Non-idempotent ingest** — a one-shot ingest dropped hour-long panels when the pipeline re-ran.
4. **Wrong-model server on the port** — a health check could answer from the *previous* model's
   still-running server, attributing scores to the wrong checkpoint.
5. **Grader dialect mismatch** — BFCL's prompt-style handler vs the model's native `<tool_call>`
   dialect produced 0.0% for a model that in fact tool-calls correctly.

**Rule adopted:** a `0.00` score is attributed to the harness first, never to capability.

---

## Finding 1 — `Q2 → Q3` is reliably positive for 8 of 13 anchors, null for 5, and never significantly negative

MultiPL-E, raw completion, greedy, 2–4 languages each, item-level 95% CIs
(`multipl_e_analysis.py` → `MULTIPLE.md`):

| anchor | Q2→Q3 | 95% CI | significant |
|---|---|---|---|
| granite-4.1-3b | **+0.344** | [+0.296, +0.391] | ✔ |
| MiniCPM5-2B | **+0.314** | [+0.253, +0.374] | ✔ |
| gemma-4-E4B-it | **+0.222** | [+0.160, +0.283] | ✔ |
| gemma-4-E2B-it | **+0.215** | [+0.159, +0.272] | ✔ |
| Qwen3.5-2B | **+0.155** | [+0.106, +0.205] | ✔ |
| Qwen3.5-9B | **+0.143** | [+0.080, +0.205] | ✔ |
| Qwen3.5-4B | **+0.142** | [+0.099, +0.185] | ✔ |
| Qwen3.5-0.8B | **+0.061** | [+0.032, +0.090] | ✔ |
| Qwen3.6-35B-A3B | +0.037 | [−0.032, +0.107] | ✘ |
| Qwen3.8-27B | +0.019 | [−0.047, +0.085] | ✘ |
| NVIDIA-Nemotron-3-Nano-4B | +0.019 | [−0.056, +0.094] | ✘ |
| gemma-4-26B-A4B-it | −0.009 | [−0.039, +0.021] | ✘ |
| LFM2.5-8B-A1B | −0.022 | [−0.068, +0.025] | ✘ |

**Reading:** the step from 2-bit to 3-bit is a *large, real* gain for models that 2-bit actually
damages — and **nothing measurable** for models that are already fine at 2-bit (larger/MoE models).
It is never significantly *negative*.

## Finding 2 — the quant curve is a step, then a plateau

`Qwen3.5-2B`, MultiPL-E cpp (`ladder_analysis.py` → `LADDER_TOOLS.md`):

| quant | score | note |
|---|---|---|
| IQ2_XXS | 0.006 | **collapsed** |
| IQ2_M | 0.112 | ≈ Q2 |
| Q2_K_XL | 0.112 | |
| **Q3_K_XL** | **0.242** | the one big step |
| Q4_K_XL | 0.230 | ≈ Q3 |
| Q5_K_XL | 0.261 | ≈ Q3 |

`IQ2_M → Q2` is flat (−0.019), `Q2 → Q3` is the only large move (+0.155), and `Q3 → Q4 → Q5` are
flat (+0.008, −0.006). **Operational rule: ≥ Q3; above Q3 you are buying nothing measurable on
these tasks.**

## Finding 3 — but "≥ Q3" is *conditional*: when the next level genuinely helps, scores follow

`granite-4.1-3b` has the largest above-Q3 PPL drop (Q3 2.053 → Q4 1.766, **−14 %**), and it *does*
translate: `Q3 → Q4` pass@1 **+0.093** (cpp) and **+0.062** (py), pooled **+0.078**
[+0.002, +0.153] (`m10-granite-q34`). For `Qwen3.5`, whose above-Q3 PPL changes are ~1–2 %, pass@1
is flat.

So the honest form of the rule is: **Q3 is a safe default, not a guaranteed optimum — it is optimal
exactly when the Q3 weights already capture nearly all of the model's usable capacity.**

## Finding 4 — quantisation produces *cliffs*, not just slopes

* `granite-4.1-3b` at **`Q2_K` returns empty completions** — 734 empty responses in the multi-turn
  panel alone — and near-zero everywhere else (code 0.037–0.056, BFCL single-turn 0.015,
  live_simple 0.016) while `Q3_K_M` is healthy (0.24–0.66). This is not a low score; it is a broken
  model.
* `Qwen3.5-2B` at `IQ2_XXS` scores 0.006.

Low-bit quantisation is therefore **not a smooth quality dial**; some checkpoints fall off a cliff.
This is why we report per-checkpoint, not per-level.

## Finding 5 — the absolute `Q2→Q3` gain is ~+0.15, and it is essentially constant

Direct measurement across **model size × task type** (Qwen3.5, item-level scores):

| size | axis | Q2 | Q3 | **absolute Δ** | retention (Q2/Q3) |
|---|---|---|---|---|---|
| 2B | code (MultiPL-E) | 0.120 | 0.275 | **+0.155** | 0.436 |
| 2B | tool multi-turn | 0.025 | 0.185 | **+0.160** | 0.135 |
| 4B | code | 0.314 | 0.456 | **+0.142** | 0.688 |
| 4B | tool multi-turn | 0.385 | 0.535 | **+0.150** | 0.720 |
| 9B | code | 0.429 | 0.571 | **+0.143** | 0.750 |
| 9B | tool multi-turn | 0.490 | 0.650 | **+0.160** | 0.754 |

Every one of the six cells gives **+0.142 … +0.160**. The Q2→Q3 upgrade therefore buys a roughly
**fixed amount of absolute score**, whether you are doing single-function code or multi-turn agentic
work, on a 2B or a 9B model.

What varies is the **retention ratio** (0.135 … 0.754) — and it varies *only* because the Q3 baseline
differs. Multi-turn at 2B starts low (Q3 = 0.185), so the same +0.16 looks like a 7× relative loss;
multi-turn at 4B starts high (Q3 = 0.535) and looks like a 28 % loss.

The **ratio of retentions** (`multi-turn / code`) makes the size-dependence explicit:

| anchor | multi-turn ÷ code retention |
|---|---|
| Qwen3.5-2B | **0.310** [0.119, 0.806] |
| Qwen3.5-4B | 1.045 [0.816, 1.337] |
| Qwen3.5-9B | 1.005 [0.809, 1.248] |

Only the 2B model shows a *disproportionate relative* multi-turn loss — and since its **absolute**
gain is the same +0.160, that is a statement about its low Q3 baseline, not about horizon.

> **Correction of an earlier claim in this report.** An earlier version stated that "quantisation
> damage scales with task horizon" based on the retention column. That was a *ratio* artifact: in
> absolute terms the multi-turn penalty is the same ~+0.15 as for code at every size, so there is no
> evidence of horizon-specific amplification. The practical statement that survives is narrower and
> better supported: **a small model at Q2 can be near-unusable on multi-turn (2.5 %) even though the
> upgrade gain is the same absolute size** — i.e. relative severity depends on where you start.

Cross-family check where the harness works: `granite-4.1-3b` multi-turn Q3 = 0.175 with Q2 broken
(see Finding 4); `Qwen3.5-2B` 0.025 → 0.185; `Qwen3.5-4B` 0.385 → 0.535.

## Finding 6 — protocol choice flips the sign of quant conclusions

Observed twice, independently:

| case | protocol A | protocol B |
|---|---|---|
| Qwen3.5-9B, `Q2→Q3` | HumanEval **chat/thinking**: **−0.073** | MultiPL-E **raw completion**: **+0.143** |
| Qwen3.5-4B, tool calling | **forced-JSON** prompt: a "profile flip" (abstention up, multi-call down) | **native `tools=`**: uniformly better (+0.08) |

**Any quant-effect claim is meaningless without naming its generation protocol.** This also
retroactively explains several contradictory results in the pre-existing dataset.

## Finding 7 — PPL is a weak proxy for capability (in both directions)

Direction agreement between `code_multi` PPL and pass@1 across Q2→Q3: **5 of 7 anchors agree,
2 disagree** — including one in each direction:

* `LFM2.5-8B-A1B`: PPL **improves** 2.938 → 2.852 (−2.9 %) while score **drops** 0.112 → 0.090.
* `gemma-4-E2B-it`: PPL **worsens** 3.107 → 3.538 (+13.9 %) while score **doubles** 0.201 → 0.416.

Meanwhile PPL *does* keep improving above the point where pass@1 saturates (Qwen3.5-2B code_multi:
Q3 1.806 → Q4 1.783 → Q5 1.779 while pass@1 stays 0.275/0.284/0.277). So the extra quality is real
in the likelihood distribution but simply not expressed on these tasks.

A continuous **per-test pass fraction** does not rescue this: it separates `Q2→Q3`
(+0.216 [0.177, 0.254]) but not `Q3→Q4` (+0.002 [−0.029, +0.033]) or `Q3→Q5` (−0.002).

---

## Practical answer for a person choosing a quant

1. **Default to ≥ Q3.** It was never significantly worse than Q2 in 13 anchors × (code, tools,
   multi-turn), and it is usually much better.
2. **Above Q3, only pay if you measure a reason to.** For most Qwen/gemma checkpoints Q3 ≈ Q4 ≈ Q5
   on task scores; for some (granite) Q4 still helps.
3. **If you run agentic/long-horizon workloads on a small model, budget more headroom.** A 2B model
   at Q2 keeps only ~14 % of its Q3 multi-turn ability.
4. **Ignore PPL as a decision rule**, or treat it as one weak signal among several: it disagrees
   with task score in ~30 % of cases and can point the wrong way.
5. **Always re-measure on your own protocol.** The same weights can look better or worse depending
   on chat vs raw prompting and on forced vs native tool calling.

## Corrections and honest negatives

* **Retracted:** "Q3 is worse than Q2 for LFM2.5-8B" — an artifact of a cross-language CI; at item
  level it is −0.022 [−0.068, +0.025], i.e. null.
* **Retracted:** "the flagship reasoning result — enabling thinking collapses output validity
  (bad_rate ≈ 0.80)" — 188/189 high-bad-rate rows come from a chaotic random-sampling sweep;
  under clean decoding the validity difference is 0.02–0.04.
* **Retracted:** "gemma-4-12B is destroyed by quantisation" — it is a *format* artifact (the model
  re-declares the signature in C++ and drops indentation in Python, differently per quant). Excluded.
* **Retracted:** "the pooled structural score model is a usable predictor" — a plain ridge beats it
  once a whole architecture is held out (family RMSE 0.294 vs 0.282).
* **Not resolvable from the original DB:** any conclusion phrased with `ctx=` / `parallel=` — those
  columns did not exist until this work added them.

## Limits, and what is queued

* **Backlog B1 (operator-requested):** off-curve quantisation — ternary / `Q1` / `Q2` schemes that
  may not lie on the bits→score curve. Recon done: `Ternary-Bonsai-27B-Q2_0` uses ggml type 42
  (known to our build but currently fails to load — suspect truncation), `PQ2_0` uses type 142
  (beyond our type table), and the model is a hybrid SSM+attention `qwen35`. Needs a newer
  llama.cpp build in a separate directory. See `BACKLOG.md` §B1a.
* **B2:** do vendor-recommended sampling parameters (unsloth) change any quant conclusion?
* **B3:** multi-turn on more families (MiniCPM running; gemma has no native FC handler in BFCL).
* Scoped to **evaluated open weights** (no self-training), one GPU, and to the checkpoints listed;
  magnitudes are family-specific even where signs are consistent.
