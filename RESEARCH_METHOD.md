# RESEARCH_METHOD.md — single source of truth (SSOT) for this study

*This file governs how the study is run. If a decision conflicts with it, fix the file first,
then the decision. Keep it short; add rules only when a run has actually burned us.*

---

## 1. The question (never lose this)

**How does quantisation map onto *measured task scores* for local LLMs — across model size,
model type (dense/MoE), architecture, task type and decoding — under a controlled protocol?**

Explicit non-goals: leaderboards, model recommendations as products, self-training, beating PPL.
PPL is a *reference* only (vendors publish it as marketing; we are filling the missing
quant↔score gap).

## 2. What counts as a result

* A result is a **difference with an uncertainty**, not a point estimate.
* **Significance is item-level.** A benchmark item is a Bernoulli trial:
  `SE = sqrt(p(1-p)/n + p'(1-p')/n')`. CIs computed over languages/categories (n = 2–5) are
  ~10× too narrow and have already produced two false claims.
* Every number must name its **`run_tag`** (the provenance key). Unsourced numbers are deleted.
* Report the **floor** as well as the effect: the same config run twice gives the axis's noise
  (agentic ≈ ±0.015; greedy code = 0). Deltas below the floor are noise.
* Negative and null results are first-class. A null with a tight CI is a finding.

### 2b. Data contract — record only what happened (no interpretation)

| what happened | what is written |
|---|---|
| the harness produced a score | **the score, verbatim** (0.0 is a value, not an error) |
| the harness produced no score (crash, OOM, timeout, no result file) | **`无结果`** and nothing else |

Explicitly **forbidden** — these were invented by the agent, are not part of the study, and any
number produced under them must be re-derived:

* no "byte-identical to another cell ⇒ failure" heuristic;
* no output-format checks (indentation, markdown fences, signature re-declaration);
* no "category A contradicts category B ⇒ failure" reasoning;
* no truncation heuristic.

A pass is a pass and a fail is a fail, as the harness reports it. The agent does not annotate,
interpret, or discard results.

## 2c. Benchmarks — standard suites only, and more than one task type

**Rule (operator, 2026-10-08): a conclusion is not accepted on a single task type. Every live
claim must be measured on at least two benchmark families — code *and* knowledge/reasoning *and*
instruction-following.** A quantisation result that holds only on code is a coding-harness finding,
not a quantisation finding.

Only standard suites. Anything else needs an explicit written case, and no agent-invented scoring
may be added.

| family | benchmark | items | tool | status |
|---|---|---|---|---|
| code | **HumanEval / HumanEval+** | 164 | EvalPlus 0.3.1 | 5 registry rows |
| code | **MBPP / MBPP+** | 378 | EvalPlus 0.3.1 | 1 registry row |
| code | **MultiPL-E** (cpp, py, java, js, rs, rb) | 164/lang | MultiPL-E | 54 rows |
| knowledge / reasoning | **MMLU** (57 subjects) | 14042 | lm-evaluation-harness | 0 rows |
| reasoning | **GSM8K** (CoT) | 1319 | lm-evaluation-harness | 0 rows |
| instruction following | **IFEval** | 541 | lm-evaluation-harness | 0 rows |
| knowledge | **ARC-Challenge** | 1172 | lm-evaluation-harness | 0 rows |
| commonsense | **HellaSwag** | 10042 | lm-evaluation-harness | 0 rows |
| truthfulness | **TruthfulQA (mc2)** | 817 | lm-evaluation-harness | 0 rows |

Retired from the main tables (kept in the DB as history, not planned further): BFCL single-turn,
BFCL multi-turn (incl. `miss_func` / `miss_param`), `testfrac`, `fa-probe`. `miss_func` and
`miss_param` are **BFCL multi-turn sub-categories**, not benchmarks — a function or a required
argument is deliberately withheld to test whether the model invents it.

**Sampling policy for the added suites.** MMLU / ARC / HellaSwag / TruthfulQA are scored by
log-likelihood over the answer letters, so they are deterministic given the context and are the
*cleanest* quantisation probe (no decoding stochasticity at all). GSM8K and IFEval generate text
and are run **greedy** so that the only moving part is the weights. Every harness run goes through
`llama-server` on a recorded port with a recorded `-c/-np`, and its `run_tag` is `mu<N>-<suite>`.

## 2d. Measurement protocol (established; each line bought with a measurement)

| setting | value | why |
|---|---|---|
| runtime | `llama-server` build 4399 (commit 4bc272fd72) | the only runtime for which every gguf we own loads; mixing runtimes inside one benchmark would confound the quant effect with the dequantisation kernel |
| context | `-c 8192 -np 1` | enough for 5-shot GSM8K + a full generation |
| generative decoding | greedy, `max_gen_toks=1024`, chat template, 5-shot, `fewshot_as_multiturn=True` | only the weights move. **The gsm8k score is strongly protocol-sensitive and this default was chosen after measuring the alternatives on UD-Q2_K_XL**: thinking-off + multiturn=True gives strict 0.38 / flexible 0.44 (matching the campaign's 0.36); thinking-on drops it to 0.06; a single-string prompt (`fewshot_as_multiturn=False`) gives strict 0.08 / flexible 0.50. The default is also lm_eval's own default for chat models. |
| thinking | OFF everywhere | with thinking ON, IFEval collapses to 0.00 (vs 0.50 with it off) and costs 27 s/item instead of 5 s/item, because the instruction checker sees the reasoning stream. For the loglikelihood tasks the mode does not apply (raw completion). The thinking-**on** gsm8k variant is kept only as a separate diagnostic axis, tagged `reasoning='on'` in the DB, and must never be merged with the primary column. |
| loglikelihood transport | exact echo shim (`.wrapup/lmeval_run.py`) | measured: this build silently **ignores** OpenAI `echo` and returns only the generated token in the new `logprobs.content[*]` shape, so stock `lm_eval --model gguf` gets a KeyError. The shim reads each continuation token's true logprob out of `top_logprobs` at tiers 100 -> 8000 -> full vocabulary, and **refuses to guess** rather than fabricate. Selftest measures 0.000e+00 error against llama.cpp's own value for both argmax and non-argmax tokens. |
| network | `HF_HUB_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` | measured: a transient DNS failure made mmlu return **null** while the dataset cache was intact (`[Errno -3] Temporary failure in name resolution`) |
| code | EvalPlus 0.3.1 on the FULL 164/378 problems | the published headline is the full set; the build's `eval_results.json` has no `pass_at_k`, so pass@1 is computed from the `eval` dict with the numerator recorded (46/164 regression check reproduces the existing numbers) |
| limits | `--limit 100`; `--mmlu-limit 16` | MMLU's limit is **per subject** (57 subjects) so a shared limit either starves the other tasks or inflates MMLU 57x. n=912 gives SE ~ 0.017 on MMLU, SE ~ 0.05 on the others. |

**Known non-measurements — never cite these as results** (each is a harness artifact with a
measurement behind it): gemma-4 output format vs the code graders (m26/m51/m54); the `-fa on/off`
byte-identical pair at Q3 (m44) which makes m29's "fa null" a non-measurement; MTP
`--spec-draft-n-max` never engaging on gemma (m52); the granite Q2 BFCL native-FC dialect mismatch.

## 3. Protocol discipline (each rule bought with a real bug)

1. **Name the generation protocol in every claim**: raw-completion vs chat vs native-tools;
   forced-JSON vs native calling. Protocol alone has flipped the sign of quant conclusions twice.
2. **Never mix protocols** in one comparison.
3. **Grader dialect must match the model's tool-call dialect.** A 0.00 score means "suspect the
   harness first": check per-slot context, whether the FC (native) handler is in use, and whether
   a stale result file is being re-scored.
4. **Per-slot context**: BFCL multi-turn prompts reach ~100k tokens; a `-c N -np K` server gives
   `N/K` per slot. Set it from the observed prompt sizes, not from a guess.
5. **Greedy unless sampling is the variable.** Record temp/top_p/top_k/min_p/penalty always.
6. **One GPU job at a time**, serialised by `flock /tmp/llama_gpu.lock`
   (`.wrapup/gpu_locked.sh`). A panel must not orphan its server (use the `trap` in
   `.wrapup/run_m9_panel.sh`).
7. **Never modify upstream projects** (llama.cpp, BFCL, EvalPlus). Build a *separate* tree if a
   newer feature is genuinely required.

## 4. Choosing the next experiment (maximum information gain, not brute force)

No blind grids, no random sweeps. Score a candidate by:

```
Value = (expected reduction in uncertainty on a live question)
        × (number of pending questions it touches)
        / (GPU-seconds × novelty risk)
```

Priority order that has served us:
1. **Resolve a contradiction or a suspicious number** (highest value; has caught 5+ real bugs).
2. **Cross a boundary we have never crossed** (new model type, new quant scheme, new task type).
3. **Shrink a CI on a headline claim** (more items/languages, not more runs of the same).
4. **Fill a provenance hole** (a number we cannot re-derive).

Explicitly deprioritised: repeating an existing axis at a new size just to add a row; panels whose
handler dialect we have not verified; anything requiring a new toolchain before its value is proven.

## 5. Architecture of the workspace

* `experiments.sqlite` — the only source of truth for results (one row per run; derived columns
  `__*` backfilled by `exp.py check`). Backups are numbered `.bakN`.
* `.wrapup/` — raw runs, logs, summaries. **Not committed** (except small scripts).
* `migrate_db.py` — ingest, via the `ONCE`/`REFRESH` registry in `main()`. Add ONE line per panel.
  `REFRESH` = delete-then-reinsert (for panels that append over hours).
* Reports are **generated**: `multipl_e_analysis.py`, `ladder_analysis.py`,
  `horizon_analysis.py`, `ppl_analysis.py`, `claims_ledger.py`, `build_wrapup.py`.
  Never hand-edit a generated report.
* Knowledge files: `conclusions.md` (science only), `OPERATIONS.md` (tooling/queue),
  `BACKLOG.md` (unrun hypotheses).
* `FINAL_REPORT.md` is the reader-facing synthesis; it must contain the *final* version of each
  claim, and we keep the correction trail when a claim was narrowed.
* `RESULTS_BY_COMPARISON.md` is the only results-table file, generated by `.wrapup/mktables.py`.
* Analysis scripts write their intermediates to `.wrapup/out/` (gitignored), so the repo root
  cannot re-accumulate generated reports. **Nine documents, no more.**

## 5b. Coverage plan (the current campaign — approved, not yet started)

The blocker is coverage: MultiPL-E has 54 rows but the EvalPlus suites have 5 and 1. Every variable
must be measured on every benchmark before a table is meaningful.

**Target matrix** — for each anchor row, all of: HumanEval, HumanEval+, MBPP, MBPP+, MultiPL-E
(all 6 languages).

**Anchor rows (~30)** — the smallest set that supports every live question:

| question | anchors |
|---|---|
| BPW curve | Qwen3.5-2B (3.27→6.24, 7 levels); granite-4.1-3b (3 levels); Qwen3.5-4B (3); Qwen3.5-9B (2); Phi-4-mini (2); gemma-4-E2B (2); gemma-4-E4B (2); Ternary-Bonsai-27B (1.13 / 2.26) |
| scheme / vendor | 2B and 4B (IQ3_XXS vs Q2_K_XL); 35B-A3B (UD-Q3_K_XL vs vendor Q3_K_M) |
| MoE bit allocation | LFM2.5-8B-A1B (expert-Q2/uniform/expert-Q4) |
| model size | Ternary-Bonsai 1.7/4/8/27B; Qwen3.5 0.8/2/4/9B |
| extremes / counterexamples | gemma-4-12b, gemma-4-26B-A4B, Bonsai-27B-Q1_0, Qwen3.5-35B-A3B-IQ1_M |

**Fill order (highest information per GPU-hour first)**

1. Add the EvalPlus suite to the rows that already have MultiPL-E (54 rows) — smallest gap per row.
2. Add the missing MultiPL-E languages (java / js / rs / rb) to the anchor rows.
3. Rows with no comparison space must be given one before they are kept:
   * `IQ1_M` (35B, one BPW only) → add a second BPW of the *same* model;
   * `Ternary-Bonsai` 1.7/4/8B (one BPW each) → the size axis already provides the contrast; add a
     second BPW only if a BPW claim is wanted for them.
4. Sampling / KV axes only have MultiPL-E data — re-run them on the EvalPlus suite.

**Cost** one EvalPlus suite per model ≈ 1–2 GPU-hours (short generations, an order of magnitude
cheaper than the retired multi-turn panels). 30 rows ≈ 45 GPU-hours.

**Acceptance** a variable table is publishable only when every anchor in it has a value in every
column of that table, or the missing cells are explicitly marked `无结果`.

## 6. Delegation protocol (for the orchestrator)

* One GPU job at a time means parallelism is only useful if the workers **launch detached and
  return**. A worker must: verify the tooling, launch with `setsid nohup … &` under the lock,
  poll once briefly, write a status line, and end its turn. Nobody waits on a 1-hour panel.
* Subagent hard limit is 30 minutes. Never assign a task that needs to stay alive longer.
* Workers report: files written, `run_tag`s, key numbers with CIs, blockers. ≤15 lines.
* **A worker must never block on the GPU lock.** If another panel holds it, the worker's
  `gpu_locked.sh` call will hang and then die on its tool timeout (observed twice). Instead the
  worker writes its script, arms it behind the current holder (poll for the holder's end marker,
  then run), launches detached, and returns. Escalate to the orchestrator if two panels must
  interleave.
* After a batch: ingest → regenerate → append to `conclusions.md` → commit.

### 6b. Anti-idle rule (learned the hard way: 9.5 h of GPU idle on 2026-10-02/03)

A detached panel chain ends and **nothing refills the queue** — the GPU then sits idle until a
human notices. The checkpoint schedule is *session-only*, so it does not fire while the session is
inactive. Therefore:

1. Every panel script must, **at its end**, test whether its successor's summary is complete and if
   not, launch it — i.e. chains write their own successor (`chain9.sh` pattern), so a queue drains
   only when there is genuinely nothing left in `BACKLOG.md`.
2. Keep a persisted queue file `QUEUE.md` (ordered list of not-yet-run panels with their script
   path and summary path). A chain's last step launches the next QUEUE.md entry and marks the
   finished one done. State lives on disk, not in a session.
3. Before ending a work batch, verify: `ps` shows a live lock holder OR the next QUEUE.md entry is
   armed. If neither, arm one.
4. Never rely on the session being awake for work to continue.
5. **Never use text-based liveness gates** (`pgrep -f "<script name>"`). They match ANY
   stray shell whose command line merely *mentions* the name — an `ls`-style inspection
   command is enough — and they also match other projects' processes (a foreign
   `llama-server -m /home/z/hf/...` produced a 1.6 h false "busy"). This stalled the
   queue three times. Liveness is determined **only** by `flock -n /tmp/llama_gpu.lock`
   (every panel runs under `gpu_locked.sh`) or by an explicit completion banner in a log.
