# Quantisation vs benchmark scores for local LLMs — what we actually found

*Final report. Companion operational/intermediate docs: `WRAPUP.md`, `MULTIPLE.md`,
`LADDER_TOOLS.md`, `HORIZON.md`, `PPL_REPORT.md`, `REANALYSIS.md`, `CLAIMS_RESOLUTION.md`.
All numbers come from `experiments.sqlite` (2,149 rows) and are reproduced by the scripts listed
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

## Finding 5 — how big is the Q2 penalty? Not a constant: ~0.08 to ~0.20, and a *floor* on hard agentic tasks

The complete matrix we have (Qwen3.5, **item-level** scores, native-FC for tools, greedy):

| anchor | axis | Q2 | Q3 | **Q2 deficit** |
|---|---|---|---|---|
| 2B | code (MultiPL-E) | 0.120 | 0.275 | **0.155** |
| 2B | tool single-turn | 0.299 | 0.502 | **0.202** |
| 2B | tool multi-turn | 0.025 | 0.185 | **0.160** |
| 4B | code | 0.315 | 0.457 | **0.142** |
| 4B | tool single-turn | 0.615 | 0.691 | **0.077** |
| 4B | tool multi-turn | 0.385 | 0.535 | **0.150** |
| 9B | code | 0.429 | 0.571 | **0.143** |
| 9B | tool multi-turn | 0.490 | 0.650 | **0.160** |

**The deficit ranges from 0.08 to 0.20 — there is no constant.** The pattern is headroom:
4B tool single-turn has the smallest deficit (0.077) precisely because Q2 is already near its own
ceiling (0.615 vs 0.691); 2B tool single-turn has the largest (0.202) because Q2 is far below it
(0.299 vs 0.502). Code sits at ~0.14–0.155 for all three sizes.

The sharpest structure is at the hard end. Within BFCL multi-turn at 2B:

| category | Q2 | Q3 | deficit |
|---|---|---|---|
| `multi_turn_base` | 0.025 | 0.185 | 0.160 |
| `multi_turn_miss_param` | 0.005 | 0.105 | 0.100 |
| `multi_turn_long_context` | 0.005 | 0.110 | 0.105 |
| `multi_turn_miss_func` | 0.005 | 0.080 | 0.075 |

**At 2B, every hard agentic category is pinned to the floor (0.005) at Q2**, and Q3 lifts each to its
own ceiling. The category ranking is unchanged by quant
(`base > miss_param > long_context > miss_func` at both levels).

> **Correction history for this finding (kept deliberately).** Version 1 said "quantisation damage
> scales with task horizon" — that was a *retention-ratio* artifact (ratios vary only because the Q3
> baseline varies). Version 2 said "the absolute gain is a constant ~+0.15" — that was over-generalised
> from six cells; the 4B single-turn cell (0.077) disproves it. The version above is the honest one:
> **the deficit is headroom-limited and ranges ~0.08–0.20, with a genuine floor collapse at 2B on hard
> agentic tasks.** We are reporting the correction trail because a reader should know how the claim was
> narrowed.

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

## Finding 8 — **the bits→score curve is not universal: ternary 2-bit competes with conventional 3-bit**

Operator-requested off-curve probe. Same protocol as every other anchor (MultiPL-E, raw completion,
greedy), matched model size and architecture family (27B, `qwen35`):

| checkpoint | file size | ≈ bits/weight | cpp | py |
|---|---|---|---|---|
| Qwen3.8-27B `UD-Q3_K_XL` | 13.15 GB | ~3.9 | 0.807 | 0.733 |
| Qwen3.8-27B `UD-Q2_K_XL` | 9.83 GB | ~2.9 | 0.758 | 0.745 |
| **Ternary-Bonsai-27B `Q2_g64`** | **7.59 GB** | **~2.25** | **0.696** | **0.764** |

The ternary model is **23 % smaller** than the 2.9-bit file yet matches it on C++ and **beats** it on
Python, and lands within 0.11/0.03 of the 3.9-bit file. So "more bits → more score" is only a trend
*within* a quantisation scheme: a ternary scheme can sit well **above** the curve. Practical read:
**a ternary 2-bit model can be a better trade than a conventional 2–3-bit one** of the same size.

### The ternary advantage does NOT generalise (negative control, m39)

A second model's ternary variant was tested against **its own** conventional quant, so base weights
are held fixed:

| GLM-4.7-Flash | cpp | py |
|---|---|---|
| `UD-Q2_K_XL` (conventional ~2.9 bpw) | **0.472** | **0.348** |
| `UD-TQ1_0` (ternary, ~1.x bpw) | 0.236 | 0.118 |

Here the ternary scheme is **half** its own conventional Q2 reference. So the Bonsai result is
**model/recipe-specific, not a general property of ternary quantisation**. The honest form of
Finding 8 is therefore: *the scheme can move a model well above the bits→score curve — Bonsai is
such a case — but tripling bits is not a general guarantee, as GLM-4.7-Flash shows.* Two more
sub-2-bit data points agree that 1-bit is *usable* (Bonsai-27B `Q1_0` 0.547/0.373;
Qwen3.5-35B-A3B `IQ1_M` 0.491/0.565) without beating conventional quants of the same model.

*Caveat:* Bonsai-27B and Qwen3.8-27B are different checkpoints in the same family, so part of the gap
may be training rather than scheme. The within-model scheme comparison is incomplete because
`Ternary-Bonsai-Q2_0` will not load in our llama.cpp (see below) and `PQ2_0` uses an unsupported
ggml type.

### What is *not* reproducible about it

Re-downloading the `Q2_0` variant produced a **byte-identical SHA256**, ruling out truncation.
All three variants carry the same tensor-type histogram, yet `Q2_g64` loads and `Q2_0` reproducibly
fails (`failed to read tensor data`, also at `-ngl 0`); `PQ2_0` uses ggml type 142, which is beyond
our `GGML_TYPE_COUNT = 43`. So exactly one of the three ternary checkpoints is usable here.

## Finding 9 — at *matched file size*, the quantisation **scheme** does not lose to the **level**, and the vendor label does not matter

Two same-base, matched-bytes contrasts (raw-greedy MultiPL-E, **item-level** 95 % CIs,
`multipl_e_analysis.py` §Size-matched → `MULTIPLE.md`):

| model | A | B | size (A vs B) | cpp A vs B | py A vs B | pooled Δ (A−B) |
|---|---|---|---|---|---|---|
| Qwen3.5-4B | `UD-IQ3_XXS` | `UD-Q2_K_XL` | 1.949 vs 1.941 GB (**+0.4 %**) | **0.379 vs 0.342** | **0.410 vs 0.354** | **+0.0466** [−0.0280, +0.1211] |
| Qwen3.5-2B | `UD-IQ3_XXS` | `UD-Q2_K_XL` | 0.932 vs 0.967 GB (**−3.6 %**) | **0.180 vs 0.112** | **0.199 vs 0.137** | **+0.0652** [+0.0093, +0.1212] ✔ |
| Qwen3.6-35B-A3B | bartowski `Q3_K_M` | unsloth `UD-Q3_K_XL` | 17.118 vs 17.228 GB (**−0.6 %**) | 0.758 vs 0.720 | 0.739 vs 0.758 | +0.0093 [−0.0581, +0.0767] |

**Reading:**

* The **i-quant scheme never loses** to the K-quant level at the same bytes — all four cells are
  positive, pooled **+0.047 (4B, ns)** and **+0.065 (2B, significant)**. This is a within-model
  version of Finding 8's off-curve result: at equal size, scheme choice buys ~0.05 of score.
* The **`UD-` vendor label is not a factor**: bartowski and unsloth files at the same nominal level and
  within 0.6 % of size differ by **+0.009 pooled** with a ±0.07 CI — a clean **null**. Buyer-facing
  lesson: match bytes/level, not the label.

**Speed corollary (M28).** Draft/MTP length is task-dependent (Qwen3.5-2B `UD-Q4_K_XL`, 256-tok
generations): code peaks at **+32 %** (n=3, 168.6→223.1 tok/s), prose **+19 %**, but a ~10k-token
long prompt is **slower for every draft length** (**−15.6 %** at n=4) as acceptance collapses
0.65→0.41. Drafting is not a free speedup; its value is bounded by task and prompt length.

*Caveat:* M23 is one family (Qwen3.5) and cpp+py only; the 4B pooled CI still includes 0. M25 is one
MoE anchor. The speed curve is one 2B model on one GPU.

---

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

* **Backlog B1 (operator-requested): DONE — see Finding 8.** The ternary model is off-curve in the
  expected direction (better than its bit count suggests). Outstanding detail: `Ternary-Bonsai-27B-Q2_0` uses ggml type 42
  (known to our build but currently fails to load — suspect truncation), `PQ2_0` uses type 142
  (beyond our type table), and the model is a hybrid SSM+attention `qwen35`. Needs a newer
  llama.cpp build in a separate directory. See `BACKLOG.md` §B1a.
* **B2:** do vendor-recommended sampling parameters (unsloth) change any quant conclusion?
* **B3:** multi-turn on more families (MiniCPM running; gemma has no native FC handler in BFCL).
* Scoped to **evaluated open weights** (no self-training), one GPU, and to the checkpoints listed;
  magnitudes are family-specific even where signs are consistent.
