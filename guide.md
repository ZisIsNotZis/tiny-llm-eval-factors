# Research Guide

Auto-maintain this guide per the outer-loop cadence defined below. All rules are mandatory. Non-compliance degrades conclusion quality and wastes compute budget.

## Current Operational Override (2026-06-28, active)
- **GPU job execution is serial-only** for now (one benchmark job at a time), due limited GPU/network and to preserve clear timing attribution per run.
- Every launched benchmark must write explicit `start_time` and `reason` in DB.
- Continue highest-EIG manual selection (no fixed loops, no blind sweeps).
- Keep formula search serial and timing-tracked when comparing candidate model forms.

## Core Goal
Quantify **generic truth-level causal relationships** (pairwise and interaction effects) between the factor set and the outcome set, across all benchmark datasets. Factors: `model_arch, version, variant, size_b, activated_size_b, qat_bool, quant, quant_ratio, k_quant, v_quant, reasoning_bool, mtp, temperature, top_p, top_k, min_p, presence_penalty, parallel_slots, ctx_size, dataset`. Outcomes: `score, bad_rate, wall_time_sec`.

Maximize factor/dataset diversity to produce robust, generalizable conclusions — not narrow, condition-specific observations.

All claims (priors, assumptions, conclusions) **must** carry an explicit confidence tag and supporting evidence reference.

## Hard Constraints
- GPU and network resources are severely limited. Time is the only budget.
- Maximize useful GPU work under the active policy. During the current serial-only phase, keep exactly one high-value GPU run active and perform analysis/design around it.
- No blind grid search. No random search. All experiments are targeted and value-ranked.
- Maximize **experiment surface area per unit time**:
  - Surface area = (number of independent factors tested) × (number of datasets covered) × (number of pending questions directly answered)
  - Prefer experiments that resolve multiple pending questions in one run over narrow single-question runs.
  - Always attack the weakest evidence point first — the largest uncertainty blocking the most pending questions.

## Operational Definitions (Enforced)
These are quantitative, non-negotiable definitions. Do not interpret subjectively.

- **Evidence weakness score** = 1 − (confidence_value × normalized_sample_count)
  - confidence_value: high=0.9, medium=0.5, low=0.2
  - normalized_sample_count = min(run_count / 5, 1.0)
- **Generic truth-level conclusion**: Validated across ≥3 architecturally distinct model families and ≥3 diverse datasets, with zero counterexamples, and supported by controlled single-variable ablation.
- **Expected Information Gain (EIG)** per experiment:
  ```
  Value(exp) = Σ(target_confidence − current_confidence_i) × weight_i
               / estimated_runtime_seconds
  ```
  - `weight_i` = 1.0 for core factor–outcome pairs, 0.5 for secondary interactions
- **High GPU utilization**: ≥85% of available VRAM occupied by active compute at all times.

---

## Confidence / Support Tags (Required Everywhere)
Every claim in every file must carry exactly one tag:

- `high` — Strong direct evidence, repeated consistency across ≥2 independent reruns with different seeds, no counterexamples. ≥90% confidence.
- `medium` — Partial evidence, directionally consistent but limited sample count or untested confounders. Needs verification. ~50–70% confidence.
- `low` — Weak evidence, speculative, single observation or plausible reasoning only. <50% confidence.

When possible, append compact evidence references: `(dataset:X, model:Y, runs:N, source:Z)`.

---

## Knowledge Files — Read/Write Rules

`guide.md` — the single source of truth for operation rules and process. **Only modified during outer-loop meta-review.**

The following files are **simple flat lists only** — no guide text, no process explanation, no narrative:

| File | Contents | Entry Requirements |
|---|---|---|
| `resources.md` | Resource inventory (models, datasets, GPU specs, environment) | Each item includes version/size/path and availability status |
| `priors.md` | External prior knowledge, `high` confidence only | Each entry: claim + confidence + source link + evidence scope |
| `questions.md` | Unanswered / pending questions | Each entry: question + why it matters + best-next experiment suggestion |
| `assumptions.md` | Claims not yet fully verified | Each entry: claim + current evidence + what specific evidence upgrades confidence |
| `conclusions.md` | Verified conclusions / facts | Each entry: claim + evidence reference (run IDs / datasets) + explicit scope / boundary conditions |

### Lifecycle Rules — Enforced Every Cycle
- Update `questions.md`, `assumptions.md`, `conclusions.md` after **every completed experiment**, not in batches.
- Question → Assumption: when answered at non-high confidence. Remove from questions, add to assumptions.
- Assumption → Conclusion: when reaches `high` confidence. Remove from assumptions, add to conclusions.
- Conclusion → Assumption / Falsified: if new evidence contradicts it. Demote immediately and flag for re-testing.
- **Mutual exclusivity invariant**: the same claim must never exist in more than one of question/assumption/conclusion states. Verify at every compliance check.

---

## Task Queue & Scheduling (Harness Layer)

All asynchronous work (downloads, experiments, data processing) is registered in `task_queue.md` with exactly one state: `pending | running | blocked | completed | failed`.

### Mandatory Queue Discipline
1. **Every cycle starts with queue processing** — before anything else:
   - Promote `completed` tasks: integrate results into `experiments.sqlite` and update knowledge files.
   - Retry or deprecate `failed` tasks per fallback rules (see Error Handling).
   - Dispatch `pending` tasks to fill idle compute / network slots, sorted by Value(exp).
2. Background long downloads. Never block the main loop on network I/O. If a download exceeds 10 minutes, switch to a download-free experiment and keep retrying in the background.
3. While serial-only override is active, do not multi-pack GPU jobs; instead maximize per-run information gain and preserve run-level timing clarity.

---

## experiments.sqlite — Schema & Write Rules

### Schema (Authoritative)
```sql
CREATE TABLE IF NOT EXISTS "experiments" (
  "model_arch" TEXT,
  "version" REAL,
  "variant" TEXT,
  "size_b" REAL,
  "activated_size_b" REAL,
  "qat_bool" INTEGER,
  "quant" TEXT,
  "quant_ratio" REAL,
  "k_quant" TEXT,
  "v_quant" TEXT,
  "reasoning_bool" INTEGER,
  "mtp" INTEGER,
  "temperature" REAL,
  "top_p" REAL,
  "top_k" REAL,
  "min_p" REAL,
  "presence_penalty" REAL,
  "dataset" TEXT,
  "score" REAL,
  "score_kind" TEXT,
  "bad_rate" REAL,
  "score_fix" REAL,
  "wall_time_sec" REAL,
  parallel_slots INTEGER,
  ctx_size INTEGER,
  source_file TEXT,
  start_time TEXT,
  reason TEXT
);
CREATE INDEX idx_experiments_dataset ON experiments(dataset);
CREATE INDEX idx_experiments_model_arch ON experiments(model_arch);
CREATE INDEX idx_experiments_source_file ON experiments(source_file);
```

### Strict Write Rules
1. **All fields must be populated** for every new row. If a field is not applicable, use `NULL` explicitly — never omit the column.
2. Boolean fields (`qat_bool`, `reasoning_bool`) store integer `0` or `1` only.
3. `score_kind` is mandatory. Valid values include (but are not limited to): `exact_match`, `pass@1`, `bleu`, `mmlu_acc`, `gsm8k_acc`. Standardize naming across runs.
4. `source_file` must contain the exact log / result filename for reproducibility.
5. **Atomic writes only**: wrap each INSERT in a transaction. Never write partial rows.
6. **Deduplication before insert**: if an identical configuration (all factor columns match) already exists, do not insert a duplicate — update or append with a seed suffix instead.
7. `wall_time_sec` is end-to-end wall time for the full benchmark run, not per-sample. Include overhead.

---

## Three-Layer Nested Loop Architecture

### Inner Loop — Execution (Per Experiment)
Runs continuously. One iteration per completed experiment.

**Step 0 — Compliance & Queue Check**
1. Run compliance self-audit checklist. Fix all violations before proceeding.
   - [ ] All knowledge entries have explicit confidence tags.
   - [ ] No blind grid / random search in any pending experiment design.
   - [ ] GPU is ≥85% utilized; analysis/design runs in parallel.
   - [ ] Knowledge files are mutually exclusive with no duplicate entries.
   - [ ] Selected experiments maximize questions-answered per unit time.
2. Restate core objective and top 3 constraints to anchor attention.
3. Process `task_queue.md`: handle completed/failed tasks, dispatch new pending tasks.

**Step 1 — Literature & Prior Review**
Research online for priors (papers, docs, repos, blogs, changelogs) relevant to current open questions. Do this before designing any new experiment.
- Add to `priors.md` only if confidence ≥ `high` and source is verifiable.
- Mark every prior with confidence level and source.

**Step 2 — Knowledge Gap Analysis**
Review `report.md`, `conclusions.md`, and `assumptions.md`. Identify:
- Unresolved questions
- Conclusions with less-than-high confidence
- Contradictions or anomalous results
- Confounders not yet controlled for

**Step 3 — Query & Cross-Verify**
Query `experiments.sqlite` for existing evidence. Cross-verify every candidate assumption against the full dataset. Quantify supporting run count and consistency.

**Step 4 — If insufficient evidence: Design targeted experiment**
Use the **Value(exp)** formula to rank all candidate experiments. Select the highest-value feasible experiment that fits within remaining time budget.

Design rules:
- Vary only one primary factor at a time for causal claims.
- Prefer factorial designs that test multiple factor pairs simultaneously, if they still support controlled interpretation.
- Allocate ~15% of experiment quota to **exploratory runs** testing unplanned interaction effects (ε-greedy: ~1 exploratory per 7 exploitation runs).
- Estimate runtime and VRAM footprint before scheduling.

**Step 5 — Dependency & Execution**
- Check dependencies (models, datasets, packages).
- Background long downloads. Never block the loop.
- Use existing `.venv` if available; use `uv` / `pip` for new packages.
- Register run in `task_queue.md` with state `running`.

**Step 6 — Result Integration**
- Validate result sanity: if score deviates >30% from high-confidence priors, flag for automatic rerun before accepting.
- Write row to `experiments.sqlite` per strict write rules.
- Update `questions.md` / `assumptions.md` / `conclusions.md` per lifecycle rules.
- Update `report.md` with revised conclusions and confidence levels.

**Step 7 — Loop back to Step 0**

### Middle Loop — Strategy Review (Every 5 Completed Experiments)
Triggered automatically after every 5 inner-loop completions.
1. Measure info-gain-per-hour trend. Is throughput improving, flat, or declining?
2. Review factor coverage. Are we over-sampling some factors and neglecting others?
3. Re-prioritize the question list. Demote low-impact questions, elevate blockers.
4. Adjust experiment selection weights if needed.
5. Verify GPU utilization targets are being met. If not, diagnose and fix scheduling.

### Outer Loop — Meta Rule Update (Every 15 Completed Experiments)
Triggered automatically after every 15 inner-loop completions.
1. Review this `guide.md` itself. Are the rules working? What's causing friction or waste?
2. Update workflow rules, confidence thresholds, or scheduling heuristics based on empirical performance.
3. Audit schema sufficiency. Are there missing columns needed for conclusion validity?
4. Document all rule changes with rationale. Do not silently modify process rules.

---

## Causal Validity Gate
No conclusion reaches `high` confidence without passing this gate.

Before promoting any assumption to conclusion:
1. List all plausible confounding variables that could explain the observed correlation.
2. Verify each confounder is either controlled for or ruled out by existing data.
3. If confounders remain untested: **cap confidence at `medium`** and schedule a controlled ablation experiment.
4. Only conclusions supported by single-variable ablation with consistent direction across multiple contexts may reach `high` confidence and qualify as "generic truth."

---

## Error Handling & Fallback Rules
Standardized recovery for common failure modes.

| Failure Mode | Immediate Action | Escalation |
|---|---|---|
| GPU OOM | Reduce batch size / ctx_size and retry. Log the failure boundary in `resources.md`. | After 3 failures: mark configuration as resource-infeasible. |
| Download timeout (>10 min) | Background the download. Switch to highest-priority download-free experiment. | Retry download once per cycle. If fails >3 times, flag resource as unavailable. |
| Result outlier (>30% deviation from prior) | Flag run, do not integrate into conclusions yet. Schedule immediate rerun with different seed. | If rerun confirms outlier, demote contradicted prior and schedule follow-up. |
| Dependency install failure | Try alternative package version or installation method. | If unresolved, redesign experiment to avoid the dependency. |
| SQLite schema violation | Reject write. Fix data format and retry. | Persistent violations trigger a middle-loop review of write rules. |

---

## Convergence & Termination Criteria
The research loop terminates when any of these is met:
1. All top-10 priority questions reach `high` confidence.
2. Three consecutive experiments yield zero confidence gain on core questions (diminishing returns).
3. Remaining time is insufficient to complete any above-threshold priority experiment (keep 20% time buffer).
4. A pre-specified time budget is exhausted.

Before final termination:
- Run a full consistency audit across all knowledge files.
- Resolve all dangling `assumptions` — either promote, demote, or flag as open question.
- Finalize `report.md` with summary of all conclusions, confidence levels, and remaining open questions.

---

## Permissions
Full permission to: research the internet, download code/models/datasets (GitHub / HF), install packages (`uv`/`nvm`/`npm`/`npx`), run experiments/benchmarks, modify all knowledge files, update this guide per outer-loop rules.

Always prefer existing `.venv` environments before creating new ones.
