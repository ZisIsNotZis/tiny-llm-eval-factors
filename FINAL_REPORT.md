# Quantisation vs benchmark scores for local LLMs — definitive synthesis

*Reader-facing final report of the study. Every number names its `run_tag`; all values come from
`experiments.sqlite` (2,786 rows) and are reproduced by the generated reports `MULTIPLE.md`,
`LADDER_TOOLS.md`, `HORIZON.md`, `PPL_REPORT.md`, `REANALYSIS.md`, `MOE_STRUCTURE.md` (scripts:
`multipl_e_analysis.py`, `ladder_analysis.py`, `horizon_analysis.py`, `ppl_analysis.py`,
`reanalysis.py`, `claims_ledger.py`). Operational/harness detail lives in `OPERATIONS.md`.*

---

## 1. The question

How does quantisation map onto **measured task scores** for local LLMs — across model size, model
type (dense/MoE), architecture, task type and decoding — under one controlled protocol? The
quantised-LLM community publishes **perplexity** as its headline quality number; PPL is a reference
only (vendors publish it as marketing; we are filling the missing quant↔score gap). This is a factor
study with explicit error bars, not a leaderboard. Non-goals: model recommendations as products,
self-training, beating PPL.

## 2. Method, and why the numbers are trustworthy

- **Item-level CIs everywhere.** A benchmark item is a Bernoulli trial, so a quant step's uncertainty
  is `SE = sqrt(p(1-p)/n + p'(1-p')/n')` over **items**. CIs computed over languages/categories
  (n = 2–5) are ~10× too narrow and produced two false claims (see §5).
- **The floors are measured, not assumed.** Greedy code is reproducible run-to-run (W1, sd 0.0);
  agentic multi-turn drifts ±0.015 (m15 0.095 vs m19 0.110, same config); a single HumanEval pair can
  only resolve |Δ| ≳ 0.03.
- **Protocol is recorded and never mixed** — raw-completion vs chat vs native-tools; forced-JSON vs
  native calling. Protocol alone has flipped the sign of quant conclusions twice (§3-F8).
- **Official harnesses**: EvalPlus (HumanEval+/MBPP+), a local MultiPL-E suite, and `bfcl-eval`
  driven against `llama-server` for single- and multi-turn tool calling.
- **Coverage**: 13 valid code anchors (0.8B–35B; dense and MoE; ≥6 architecture families), BFCL
  single-turn tool-calling at 2B/3B/4B (plus gemma-E 2.4B/4.6B), and BFCL multi-turn at
  2B/4B/9B/27B-ternary/35B-MoE.

**Five silent-failure classes were found and fixed** (each yields plausible-but-wrong numbers):

| # | class | what it produced |
|---|---|---|
| 1 | stale BFCL result reuse (`generate` keys by handler, not run) | would have faked a "Q3≈Q2" null |
| 2 | orphaned `llama-server` holding the inherited `flock` | stalled the queue ~36 min–59 h |
| 3 | non-idempotent ingest | dropped hour-long panels on re-run |
| 4 | wrong-model server on the port | attribution to the wrong checkpoint |
| 5 | grader dialect ≠ model's tool-call dialect | 0.00% for a model that calls tools fine |

**Rule adopted:** a `0.00` score is attributed to the harness first, never to capability (m12/m14:
granite Q2_K 0.00 persists under the correct handler and is a *real* cliff; granite Q3 0.00 was a
handler dialect artifact).

---

## 3. Findings

### F1 — `Q2→Q3` is reliably positive for 8 of 13 code anchors, null for 5, never significantly negative

MultiPL-E, raw completion, greedy, 2–4 languages each, **item-level** 95% CIs
(`multipl_e_analysis.py` → `MULTIPLE.md`):

| anchor | Q2→Q3 | 95% CI | sig | run_tag |
|---|---|---|---|---|
| granite-4.1-3b | **+0.344** | [+0.296, +0.391] | ✔ | m5-family-ladder |
| MiniCPM5-2B | **+0.314** | [+0.253, +0.374] | ✔ | m10-family-ladder |
| gemma-4-E4B-it | **+0.222** | [+0.160, +0.283] | ✔ | m5-family-ladder |
| gemma-4-E2B-it | **+0.215** | [+0.159, +0.272] | ✔ | m5-family-ladder |
| Qwen3.5-2B | **+0.155** | [+0.106, +0.205] | ✔ | m3-quant-ladder |
| Qwen3.5-9B | **+0.143** | [+0.080, +0.205] | ✔ | m2-multipl-e |
| Qwen3.5-4B | **+0.142** | [+0.099, +0.185] | ✔ | m1-multipl-e |
| Qwen3.5-0.8B | **+0.061** | [+0.032, +0.090] | ✔ | m6-family-ladder |
| Qwen3.6-35B-A3B | +0.037 | [−0.032, +0.107] | ✘ | m6-family-ladder |
| Qwen3.8-27B | +0.019 | [−0.047, +0.085] | ✘ | m10-family-ladder |
| NVIDIA-Nemotron-3-Nano-4B | +0.019 | [−0.056, +0.094] | ✘ | m10-family-ladder (Q2) + m33-family-breadth (Q3) |
| gemma-4-26B-A4B-it | −0.009 | [−0.039, +0.021] | ✘ | m10-family-ladder |
| LFM2.5-8B-A1B | −0.022 | [−0.068, +0.025] | ✘ | m10-family-ladder |

**Reading:** the step is large and real for models that Q2 actually damages, and **nothing
measurable** for models that are already fine at Q2 (larger/MoE anchors). It is **never significantly
negative**. Two clean replicates: (1) LFM2.5-8B-A1B's `Q3<Q2` ordering **reproduced** on an
independent panel (m45: cpp 0.161→0.143, py 0.062→0.037) but pooled is still ns (−0.022) — suggestive,
not an established reversal; (2) Bonsai ternary `multi_turn_base` 0.695 (m22) vs 0.675 (m32 re-run;
first m32 read 0.700) — see F5. A 14th family, GLM-4.7-Flash (m39 Q2 → m33 Q3), was ingested after
this table: **+0.127 [+0.097, +0.158]** (significant), so the live tally is 9 positive / 5 null,
range −0.022..+0.344 unchanged. gemma-4-12b is excluded (harness floor, §5).

### F2 — the quant curve is a **step, then a plateau**

`Qwen3.5-2B`, MultiPL-E pooled (`ladder_analysis.py` → `LADDER_TOOLS.md`, `run_tag='m3-quant-ladder'`):

| quant | pooled score | note |
|---|---|---|
| UD-IQ2_XXS | 0.006 | **collapsed** (1 language only) |
| UD-IQ2_M | 0.139 | ≈ Q2 |
| UD-Q2_K_XL | 0.120 | |
| **UD-Q3_K_XL** | **0.275** | the one big step |
| UD-Q4_K_XL | 0.284 | ≈ Q3 |
| UD-Q5_K_XL | 0.277 | ≈ Q3 |

Steps: `IQ2_M→Q2` **−0.019**, `Q2→Q3` **+0.155 [+0.107, +0.204]**, `Q3→Q4` **+0.008 [−0.016, +0.033]**,
`Q4→Q5` **−0.006 [−0.057, +0.045]**. The aggregate matched-context re-analysis agrees: the
`Q2→Q3` step dominates (+0.061 [+0.042, +0.081], n=87 clean-decoding contexts; `reanalysis.py` →
`REANALYSIS.md`). **Operational rule: ≥ Q3; above Q3 you buy nothing measurable on these tasks.**
(Caveat in F3: for some families Q4 still helps.)

### F3 — the `Q2` floor: at 2B every hard agentic category pins to ~0.005; the deficit is headroom-limited, not a law

Complete Qwen3.5 matrix, item-level (`m3`/`m1`/`m2` code; `m4b` tool single-turn; `m9`/`m11`/`m17`
multi-turn):

| anchor | axis | Q2 | Q3 | deficit |
|---|---|---|---|---|
| 2B | code (MultiPL-E) | 0.120 | 0.275 | **0.155** (m3) |
| 2B | tool single-turn | 0.299 | 0.502 | **0.202** (m4b) |
| 2B | tool multi-turn | 0.025 | 0.185 | **0.160** (m9) |
| 4B | code | 0.314 | 0.457 | **0.142** (m1) |
| 4B | tool single-turn | 0.615 | 0.691 | **0.077** (m4b) |
| 4B | tool multi-turn | 0.385 | 0.535 | **0.150** (m11) |
| 9B | code | 0.429 | 0.571 | **0.143** (m2) |
| 9B | tool multi-turn | 0.490 | 0.650 | **0.160** (m17) |
| 35B-MoE | multi-turn base | 0.600 | 0.675 | **0.075** (m20) |

**The deficit ranges ~0.077–0.202 — there is no constant.** It is **headroom-limited**: 4B
single-turn has the smallest deficit precisely because Q2 is already near its own ceiling (0.615 vs
0.691); the 35B MoE is the same (0.600 vs 0.675). The crisp invariant is the **floor** — at 2B, BFCL
multi-turn (`run_tags m9/m18/m19`, 200 items each):

| category | Q2 | Q3 | deficit |
|---|---|---|---|
| `multi_turn_base` | 0.025 | 0.185 | 0.160 (m9) |
| `multi_turn_miss_param` | 0.005 | 0.105 | 0.100 (m18) |
| `multi_turn_long_context` | 0.005 | 0.110 | 0.105 (m19) |
| `multi_turn_miss_func` | 0.005 | 0.080 | 0.075 (m18) |

At Q2 **every** hard agentic category sits at the floor (~0.005); Q3 lifts each to its own ceiling,
and the category ranking (`base > miss_param > long_context > miss_func`) is quant-invariant.

> **Correction trail (kept deliberately).** v1 said quant damage "scales with task horizon" — a
> *retention-ratio* artifact (the ratio varies only because the Q3 baseline varies). v2 said "the
> gain is a constant ~+0.15" — over-generalised from six cells; the 4B single-turn cell (0.077)
> disproves it. The honest claim is the one above: **deficit = headroom, with a genuine floor
> collapse at small size on hard agentic tasks.**

### F4 — SCHEME > bits: at matched file size the i-quant scheme beats the K-quant level; the vendor label is null

`run_tag='m50-imatrix-vs-k'` (raw-greedy MultiPL-E, size-matched to <4%, item-level CIs, 644 items):

| contrast | size A vs B | Δ (A−B) | 95% CI |
|---|---|---|---|
| 2B `UD-IQ3_XXS` vs `UD-Q2_K_XL` | 888.7 vs 921.8 MB (−3.6%) | **+0.065** | [+0.009, +0.121] ✔ |
| 4B `UD-IQ3_XXS` vs `UD-Q2_K_XL` | 1858.7 vs 1850.9 MB (+0.4%) | **+0.047** | [−0.028, +0.121] |
| **pooled (4/4 cells positive)** | | **+0.056** | **[+0.008, +0.104]** ✔ |

So *how* you quantise matters as much as *how much*. The **vendor label does not**: Qwen3.6-35B-A3B
bartowski `Q3_K_M` (17.118 GB) vs unsloth `UD-Q3_K_XL` (17.228 GB, −0.6%) gives pooled
**+0.009 [−0.058, +0.077]** — a clean null (`m25-vendor`, replicated `m37-vendor-matched-size`).
Buyer rule: match **bytes/level**, not the label.

### F5 — ternary (~2.25 bpw) is competitive with conventional 2.9–3.9 bpw — but it is model/recipe-specific, not a ternary law

`Ternary-Bonsai-27B-Q2_g64` (~2.25 bpw):

| task | Bonsai score | reference | run_tag |
|---|---|---|---|
| BFCL `multi_turn_base` | **0.695 / 0.675** | Qwen3.6-35B-A3B Q3 0.675; Qwen3.5-9B Q3 0.650 | m22 / m32 (first read 0.700) |
| BFCL `multi_turn_miss_func` | **0.515** | Qwen3.5-2B Q3 0.080 | m36-bonsai-ternary-mt2 |
| BFCL `multi_turn_miss_param` | **0.435** | no dense anchor above 0.42 | m36-bonsai-ternary-mt2 |
| MultiPL-E cpp/py (27B) | **0.696 / 0.764** | Qwen3.8-27B ~2.9 bpw 0.758/0.745; ~3.9 bpw 0.807/0.733 | m21-bonsai-ternary |
| MultiPL-E cpp/py (8B) | **0.553 / 0.615** | beats Qwen3.5-4B Q3 (0.453/0.503) | m24-bonsai-series |

It **tops the multi-turn table** at ~2.25 bpw, above every conventional quant. **But the same scheme
does not generalise:** `GLM-4.7-Flash-UD-TQ1_0` scores cpp **0.236** / py **0.118** vs its **own**
`UD-Q2_K_XL` reference 0.472 / 0.348 (`m39-glm-ternary`) — half its own Q2 at fewer bits. So the
effect is **model/recipe-specific**, not a property of ternary quantisation. Sub-2-bit is usable
without beating conventional: Bonsai-27B **1-bit** `Q1_0` 0.547/0.373, Qwen3.5-35B-A3B `IQ1_M`
0.491/0.565, Ternary-Bonsai-4B 0.491/0.677 (`m35-sub2bit`).

### F6 — axes that are INERT (nulls with tight evidence)

| axis | result | run_tag |
|---|---|---|
| KV-cache quant (K/V f16↔q8_0) | **no effect across a 48× context range** (996 / 15 328 / 48 096 prompt tokens; all four settings identical per length) | m30-kv-ctx |
| `top_k` above 20 (temp 0.3) | K ∈ {20,40,64,200} **byte-identical** on all 6 model×lang cells; only K=1 moves (both ways) | m31-topk |
| temperature | no significant effect on pass@1 across Q2/Q3/Q4 (|Δ| ≤ 0.068, all CIs cross 0) | m27-sampling |
| flash-attn `-fa` | **no-op at Q3** (0/3 probes change) but **real at Q2** (1/3); V-cache-q8 control moves text at both | m44-fa-probe |
| MTP draft length | task-dependent: code peaks at n=3 (**+32%**), but a ~10k-token long prompt is **slower for every n>0** (−15.6% at n=4) | m28-speed |

**Reading:** the sampling/precision knobs people tune most are largely inert on these tasks; the
lever that matters is the **weight-quant scheme** (F4).

### F7 — PPL is a weak proxy for capability (agrees 5/7, fails in both directions)

`code_multi` PPL vs pass@1 across `Q2→Q3` (`ppl_analysis.py` → `PPL_REPORT.md`;
`run_tags m5/m10/m45`):

- **LFM2.5-8B-A1B**: PPL **improves** 2.938→2.852 (−2.9%) while score **drops** 0.112→0.090.
- **gemma-4-E2B-it**: PPL **worsens** 3.107→3.538 (+13.9%) while score **doubles** 0.201→0.416.
- PPL keeps falling above pass@1 saturation: Qwen3.5-2B Q3→Q5 PPL 1.806→1.779 while pass@1 is flat
  0.275/0.284/0.277 (m3). A continuous per-test fraction separates `Q2→Q3` (+0.216 [+0.177, +0.254])
  but not `Q3→Q4`/`Q3→Q5` (m41/testfrac). So "≥Q3 is enough" is a statement about **what these
  benchmarks can measure**, not about model quality.

### F8 — protocol choice flips the sign of quant conclusions (twice)

| case | protocol A | protocol B |
|---|---|---|
| Qwen3.5-9B `Q2→Q3` | HumanEval chat/thinking: **−0.073** (W2) | MultiPL-E raw completion: **+0.143** (m2) |
| Qwen3.5-4B tool calling | forced-JSON prompt: a "profile flip" (abstention ↑, multi-call ↓) (m4) | native `tools=`: uniformly better (+0.08) (m4b) |

**Any quant-effect claim is meaningless without naming its generation protocol.**

---

## 4. Practical answer for choosing a quant

1. **Default to ≥ Q3.** It was never significantly worse than Q2 in 13 anchors × (code, tools,
   multi-turn), and is usually much better (F1).
2. **Above Q3, only pay if you can measure a reason to.** For most Qwen/gemma checkpoints Q3 ≈ Q4 ≈
   Q5 on task scores; for granite, Q4 still helps (`Q3→Q4` pooled +0.078 [+0.002, +0.153],
   `m10-granite-q34`).
3. **Small models on agentic/long-horizon work need more headroom**: a 2B at Q2 collapses to ~0.005
   on every hard multi-turn category while Q3 recovers it (F3).
4. **At equal file size, the scheme can beat the level** (IQ > K, F4); match bytes/level, not the
   vendor label.
5. **Ignore PPL as a decision rule** — it disagrees with task score in ~30% of cases and can point
   the wrong way (F7).
6. **Re-measure on your own protocol.** The same weights look better or worse under chat vs raw, and
   forced vs native tool calling (F8).

---

## 5. Corrections and retractions (consolidated)

| claim | status | reason it was wrong | source |
|---|---|---|---|
| Reasoning "collapses output validity" (`bad_rate≈0.80`) | **RETRACTED** | 188/189 high-bad-rate rows came from a chaotic random-sampling sweep lumped into the reasoning factor; under clean decoding the validity gap is 0.02–0.04 | `reanalysis.py` → `REANALYSIS.md` |
| LFM2.5-8B-A1B `Q3<Q2` **significant** | **CORRECTED to null** | used a cross-language CI (n=2 languages), ~10× too narrow; item-level is −0.022 [−0.068, +0.025] | `m10-family-ladder` (+ m45) |
| gemma-4-12B "destroyed by quantisation" | **RETRACTED** | a **format** artifact — it re-declares the signature and drops indentation, differently per quant; not a capability effect | `m6b`, `m51`, `m54` |
| "the `Q2→Q3` gain is a **constant +0.15**" | **CORRECTED** | over-generalised from six cells; the 4B tool single-turn deficit (+0.077) disproves constancy | `m4b` |
| "quant damage scales with **task horizon**" | **RETRACTED** | a retention-ratio artifact — the ratio varies only because the Q3 baseline varies | `horizon_analysis.py` → `HORIZON.md` |
| m29 `-fa` / V-cache "null" | **CORRECTED: non-measurement** | `faon_f16` and `faoff_f16` byte-identical in all cells and the panel has 0 DB rows (ingest key mismatch) | `m29` → probe `m44` |
| old m31 "`top_k` inert" wording | **CORRECTED** | the old K∈{20,40,64} sat *inside* the sampling noise, not "measuring nothing by construction"; repaired panel spans K∈{1..200} | `m31-topk` |
| old m30 "KV inert" null | **CORRECTED** | short prompts meant only the *allocated* `-c` moved; repaired panel pads to ~2k/16k/48k real tokens | `m30-kv-ctx` |
| m26 / m51 / m54 gemma Q2→Q3 numbers | **FLAGGED: harness floors** | gemma under the raw protocol does not emit the language-conformant body (py 0.00, cpp byte-identical across Q2/Q3); a non-measurement, not a null | `m26`, `m51`, `m54` |
| m32 `multi_turn_base` = 0.700 | **CORRECTED** | repaired full re-run scores **0.675**; with m22 0.695, Bonsai's two runs span 0.675–0.700 (≈ the ±0.015 agentic floor) | `m32-bonsai-ternary-mt` |
| "the pooled structural score model is a usable predictor" | **RETRACTED** | a plain ridge beats it once a whole architecture is held out (family RMSE 0.294 vs 0.282) | `WRAPUP.md` |
| any conclusion phrased with `ctx=`/`parallel=`/`seed=` | **UNAUDITABLE** | those columns did not exist before this work added them | schema gap |

---

## 6. Scope limits, and what is still open

**Limits.** Evaluated open weights only (no self-training); one GPU, one host; magnitudes are
family-specific even where signs are consistent; MoE evidence is 2–3 families (+2 quarantined); the
ternary within-model scheme contrast is incomplete (`Ternary-Bonsai-Q2_0` fails to load in llama.cpp
4399; `PQ2_0` uses unsupported ggml type 142 — see `BACKLOG.md` §B1a). Activation quantisation
(W8A8/W4A16) is out of scope: llama.cpp exposes no activation-quant path (`BRAINSTORM.md` §3C).

**Open (queued / backlog).**

| item | state |
|---|---|
| `m32` Bonsai `multi_turn_long_context` (~117k-token prompts) | **BLOCKED-on-VRAM** (>16 GB KV on top of 7.6 GB weights) |
| `m40`/`m53` third-party-quantiser + ModelScope ternary probes | **SKIP** — no loadable candidate found (0-byte summaries, not nulls) |
| B2: do vendor-recommended sampling params change any quant conclusion? | unrun (`BACKLOG.md` B2) |
| B3: multi-turn on more families (gemma has no native FC handler in BFCL) | unrun (`BACKLOG.md` B3) |
| B1a: newer llama.cpp build in a separate tree for `Q2_0`/`PQ2_0` ternary | unrun |
| Tier 1A expert-wise / per-tensor MoE quantisation (`--tensor-type`) | designed, needs F16 source (~70 GB) |
| Redundancy: 209 duplicate groups differing only in `spec_draft_n_max` (200 legitimate MTP) | documented in `reanalysis.py`; not artifact duplication |

Queue state and armed drivers live in `QUEUE.md`; harness/ops lessons in `OPERATIONS.md`.
