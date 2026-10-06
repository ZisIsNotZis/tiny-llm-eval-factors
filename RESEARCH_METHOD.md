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
  `BACKLOG.md` (unrun hypotheses), `questions.md`, `assumptions.md`, `resources.md`.
* `FINAL_REPORT.md` is the reader-facing synthesis; it must contain the *final* version of each
  claim, and we keep the correction trail when a claim was narrowed.

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
   only when there is genuinely nothing left in `BRAINSTORM.md`.
2. Keep a persisted queue file `QUEUE.md` (ordered list of not-yet-run panels with their script
   path and summary path). A chain's last step launches the next QUEUE.md entry and marks the
   finished one done. State lives on disk, not in a session.
3. Before ending a work batch, verify: `ps` shows a live lock holder OR the next QUEUE.md entry is
   armed. If neither, arm one.
4. Never rely on the session being awake for work to continue.
