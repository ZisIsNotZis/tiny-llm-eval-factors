**English** | [简体中文](README.zh-CN.md)

<img src="assets/logo.svg" alt="tiny-llm-eval-factors" width="200">

# tiny-llm-eval-factors

*A reproducible workbench for measuring which factors actually move a local language model's benchmark score.*

**Quantization width, model size, decoding protocol, scoring: one factor at a time, one SQLite database, and a report that a clean clone rebuilds byte for byte.**

Does a model really lose code ability when it drops from 6-bit to 4-bit? Does a vendor's recommended sampling preset help or destroy the run? Does KV-cache precision cost anything at 32k context? This repository answers questions of that shape with controlled panels, per-item artefacts and a generated report — every printed number is recomputed from `experiments.sqlite`, never typed into prose. It is research evidence, not a model release, and it does not claim that every planned comparison is finished: unknown, blocked and unmeasured results are kept distinct from zero and from a negative result.

## Quick start

Zero to a rebuilt report, from a clean clone:

```bash
sudo apt-get install -y fonts-noto-cjk       # the report font is part of the reproduction conditions
python3 -m pip install -r requirements.txt   # ~1 min measured on this machine (matplotlib included)
./reproduce.sh                               # verify inputs, rebuild report.html, ~40 s
```

`./reproduce.sh` walks the chain in order and stops with a non-zero exit on any failure: runtime dependencies → prompt-set SHA256 (`.wrapup/prompts/SHA256SUMS`) → report inputs → database integrity and cleanliness → no executable script still pointing at a retired absolute root → documentation checks → rebuild `report.html` from `experiments.sqlite` and compare it **byte for byte** with the committed copy → cross-check the report against the artefacts it claims (`checks/report_check.py`). The last line, `OK：报告可从库重建…`, is the completion signal. A `SKIP` or `BLOCKED` line means that item was *not* verified — for example a clean clone has no local `.wrapup/mres/` run outputs — and must not be read as green.

Measured on this machine (12 CPU cores, no GPU): report build ≈ 35 s; the whole `./reproduce.sh` 41.1 / 49.9 / 60.2 s across three clean-clone runs, the spread coming from font cache and load. Dependencies were tested on Python 3.12.3 (`requirements.txt`).

If you need `lm-eval` runs, rebuild the venv from the pinned dependencies rather than committing it — venvs stay out of the repo:

```bash
./bootstrap_venv.sh .wrapup/lmenv requirements.txt
```

**The CJK font is a reproduction condition, not a nicety.** Its path and expected sha256 have exactly one home: `CJK_FONT` / `CJK_FONT_SHA256` in `make_report.py`. The build prints the font it actually used as `cjk font: <path> sha256=<hash>`, and `./reproduce.sh` checks that line as its own step. A missing or different font makes the build **fail** and say what to install; it never silently substitutes one, because 86 figures would change their glyphs and metrics and the report would stop being byte-identical.

What a clean clone cannot rebuild: model weights (`.gguf` files are not in the repo and the original weight files are no longer on this machine — the repo has no `artifacts.tsv` for them and does not plan one, those bytes are lost), the `/tmp/MultiPL-E` prompt cache, the CJK font (a system package — install it with the command above), and the evaluation runs themselves (they need a GPU and model files).

## What it can do now

Sixteen research units are closed, and the first delivered report is 21 sections / 86 figures (`report.html`, rebuilt by one command). The measured factors:

- **Quantization bit width** — a recomputable score curve per model family with breakpoints and intervals; only Qwen3.5-2B has a non-degenerate breakpoint in the recorded data. Ternary and extreme-low-bit variants have explicit supported / refuted / bounded verdicts, and the 12B MMLU anomaly is attributed to a file/protocol property by a bit-identical repeat.
- **Model size** — the legacy "size" column is audited per row and only partly credible; size is replaced as a factor by GGUF tensor parameter counts from shipped fixtures, with 63 same-family same-recipe curves registered and the multi-variable regression judged unidentifiable.
- **Quantization scheme vs vendor label** — at equal bytes the two are indistinguishable at this design's resolution; the label turns out to be a proxy for bit allocation.
- **MoE layer bit allocation** — uniform beats expert-first in a pinned-budget contrast, and the budget term is separable from the allocation term; the win is *n=1* against a known-pathological arm, and that is written down as such.
- **KV-cache precision** — short context moves individual item verdicts in both directions while aggregate scores look unchanged; long context is covered by needle retrieval up to 32k with no observed difference and a measurable floor.
- **Sampling and decoding** — a vendor-recommended preset collapses MultiPL-E and EvalPlus; single-variable probes attribute the collapse to `temperature=1.0`, not to penalties or `top_p`/`min_p`.
- **Speculative decoding** — speed and quality are measured together; the byte-identity floor is 164/164 across sessions, the speculative arm differs on 73 of 164 items, and the divergence is reproducible on both sides.
- **Thinking toggle, QAT, third-party schemes (GSQ-RCO), diffusion decoding, per-language MultiPL-E, BFCL tool calling, partial credit** — each with a closed verdict, a partially supported verdict, or an explicit gate/unmeasured registration.
- **Scoring and benchmark validity** — a per-harness audit with a deterministic-decoding noise floor of zero items, single-run noise measured, and retired scores (fence stripping, language pooling) withdrawn rather than quietly fixed.

Verdicts, their evidence and the command that reproduces each one live in the owning subproject's `RESULT.md`; `FINDINGS.md` is the route table that says which conclusion lives in which node and how it should currently be read (`current`, `provisional`, `retracted`).

## Architecture

Two stores and one generated artefact: measurements go into `experiments.sqlite`, derived indices go into `report_inputs/`, and `make_report.py` renders `report.html` from both. Nothing is edited downstream of the database.

```
tiny-llm-eval-factors/
├── experiments.sqlite     # data SSOT: one row per measurement, derived columns prefixed `__`
├── make_report.py         # renders report.html + figures from the DB and report_inputs/ (opens the DB read-only)
├── migrate_db.py          # schema upgrades and ingestion of run artefacts into the DB
├── exp.py                 # DB helper the experiment scripts share
├── report.html            # generated report, 21 sections / 86 figures — never hand-edited
├── report_inputs/         # derived indices the report reads besides the DB, plus their builders
├── checks/                # 39 infrastructure checks, each with a negative control
├── docs/                  # pain / need / product / architecture / method / plan / subprojects
├── .wrapup/               # run outputs, prompt set, panel scripts (ship rule below)
├── migrations/            # one-off data migrations
├── inbox/                 # messages exchanged with the layer above this repo
├── reproduce.sh           # the one command that verifies and rebuilds the chain
├── bootstrap_venv.sh      # throwaway venv builder (venvs are not committed)
├── requirements.txt
├── STATUS.md              # what this is, where it stands, what is next
├── FINDINGS.md            # conclusion -> owning node, with the reading status
├── AGENTS.md              # data-trust, experiment and database-safety rules
└── LICENSE                # MIT
```

How the pieces talk: an evaluation run writes per-item artefacts (`.wrapup/mres/*_eval.json`) and panel summaries → `migrate_db.py` ingests them into `experiments.sqlite` after a numbered backup (`.bak1`, `.bak2`, …) and reports skipped names instead of guessing → `report_inputs/build_*.py` derive the indices the report needs (item counts, open questions, paired deltas, size claims, …) → `make_report.py` renders the report and its figures → `checks/report_check.py` re-reads the artefacts and fails if the report prints a row label twice, prints an item count that its own artefact contradicts, or hides a cell in which two values cannot be told apart. `./reproduce.sh` wires all of it into `PASS` / `SKIP` / `FAIL` lines.

### Source of truth

- `experiments.sqlite` is the data source of truth for recorded measurements.
- `docs/plan/subprojects.md` owns the research split: which unit owns which section, its goal and its acceptance.
- `docs/subprojects/<id>-<name>/PLAN.md` owns that unit's milestone and work packages; `RESULT.md` owns its current facts, each with its evidence and the command that reproduces it.
- The layers that are not cut per unit live in `docs/pain/`, `docs/need/`, `docs/product/`, `docs/architecture/` and `docs/method/` (`method.yaml` holds method and protocol).
- `AGENTS.md` defines data-trust, experiment and database-safety rules.
- `docs/check_docs.py` validates the documented schema (`docs/docs.schema.yaml`) and exits 0 today.
- `checks/` holds the infrastructure checks: database integrity and cleanliness, report-versus-artefact agreement, retired absolute paths, and the routing tables themselves.
- `STATUS.md` is the entry point (what it is, current state, next step); `FINDINGS.md` is the conclusion index.

### What ships from `.wrapup/`

`.wrapup/` holds run outputs, downloaded corpora and other regenerable experiment artefacts. One criterion decides what ships (`@regeneration_cost`): **an artefact ships when it carries an assertion and cannot be recomputed from what ships; it stays out when it is a rebuildable distribution.**

- **Ships (evidence):** `.wrapup/prompts/` (the prompt set plus `SHA256SUMS`), `.wrapup/mres/*_eval.json` (the per-item eval artefacts — they are what makes "no all-Exception cell carries a score" and every printed item count checkable in a fresh clone; count them with `git ls-files '.wrapup/mres/*_eval.json' | wc -l`), the panel scripts and the `*_summary.jsonl` they produced, `bpw_map.json`, everything under `report_inputs/`, plus the aggregate artefacts and logs that a subproject's `RESULT.md` names in an `evidence:`/`repro:` line (`evalplus.json`, `lmeval_panel.json`, `ident_control.json`, probe outputs; run logs ship gzipped next to their original path; a panel's per-task `lmeval_*.json` neighbours ship with it, because `migrate_db.py` reads the metric names and scores out of them and a clean-clone refresh would otherwise rewrite those rows as `#None`). The criterion is "it was named", not "it is small".
- **Does not ship (rebuildable cache):** `.wrapup/mres/*.jsonl` per-item samples, venvs (`lmenv/`, `msenv/`, `evalpy/`, `bfclenv/`, `mplenv/`), `jars/`, run logs and process stamps, `dl_ready/`, `ppl_corpora/`, `figures/` (redrawn by `make_report.py`, no row of the database differs), database backups and side files (`experiments.sqlite.bak*`, `*.sqlite-wal`, `*.sqlite-shm`), `.tmp/`.

That second list is a summary only: the single home for the class list is `REBUILDABLE_CLASSES` in `checks/evidence_logs.py`, which also says which ignore rule counts as which class and which path shapes that class allows. Add or remove a class there, not in a second copy. Whether the named artefacts really ship is not asserted by this paragraph but checked item by item by `python3 checks/evidence_logs.py`: on a machine that still has the run files it resolves every named `.wrapup/…` path and exits 0; in a clean clone it can only judge by declaration/index, so it prints `BLOCKED` (exit 2) with the number of items it could not see. Unavailable is not passed — do not read a clean clone as green.

## How to develop

Install the runtime dependencies first (same command as the quick start), then use the checks directly while you work:

```bash
./reproduce.sh                                  # the full gate before any commit
REPRODUCE_INPUTS_ONLY=1 ./reproduce.sh           # only the report-input section (~2 s; used by its negative control)
python3 checks/db_check.py                      # schema, foreign keys, mandatory fields, value ranges, duplicate identities
python3 docs/check_docs.py                      # documentation schema (docs@1)
python3 checks/router_refs.py                   # every node reference in STATUS/FINDINGS/README resolves
python3 checks/readme_counts.py                 # README's shipping claims agree with `git ls-files`
python3 checks/evidence_logs.py                 # every named .wrapup artefact has a disposition
python3 checks/<name>_negative_control.py       # prove a check can go red
```

Every check ships with a negative control that demonstrates it fails when its subject is broken; the pair is what `./reproduce.sh` calls. `checks/README.md` explains, per script, what it proves and who calls it. There is no lint step, no build step and no CI — `./reproduce.sh` is the gate, and it exits non-zero on the first thing that is not true.

Rules that are not negotiable when changing data: back up the database before any mutation (numbered `.bak` files), keep the database clean (no nulls in mandatory fields, scores within range), never hand-edit `report.html`, and regenerate both a `report_inputs/` file and the report when its source changes.

## How to contribute

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: a change that moves a number must bring the command that reproduces it and the check that would catch it going wrong; `./reproduce.sh` must exit 0 before a pull request is opened.

## Roadmap

**Implemented**

- Sixteen research units closed, covering bit width, model size, scheme/vendor, MoE allocation, KV cache, sampling, speculative decoding, thinking toggle, QAT, third-party quantization, diffusion decoding, per-language code, tool calling, partial credit, scoring validity and measurement infrastructure.
- First delivered report: 21 sections / 86 figures, byte-identically rebuildable from `experiments.sqlite` in a clean clone.
- Milestone `entry`: the two reader-facing route tables (`STATUS.md`, `FINDINGS.md`) point at nodes that exist, and the property is guarded by `checks/router_refs.py` with a 21-expectation negative control. Accepted on result revision `3287b76`.
- 39 infrastructure checks, each paired with a control that proves it can fail; report inputs are drift-checked so a stale index is a hard failure rather than a warning.

**Planned**

- Three classes of *unmeasured*, already priced and registered but not resolved: blocked on VRAM (priced, not bought), gate-failed (this environment lacks the runtime), and not measurable here. They are registered as unmeasured, never as a low score.
- Diffusion decoding (unit `a11`): the upstream gate lifted on 2026-10-27, no scores yet — the open work is to produce a controlled comparison or a reproduced gate.
- Two accepted measurement limits, recorded rather than hidden: the table row key cannot hold `top_k`, and the audit proves a value is present in the panel's multiset but not which cell each value came from.
- The next research direction (buy more VRAM, or change the question) needs a human decision and is deliberately not decided inside the repo — it is stated as such in `STATUS.md`.

Future vision: the same discipline — one factor, one panel, one artefact, one route from claim to evidence — extended to the factors that currently stop at a resource wall. The deliverable stays a report a stranger can rebuild, because a claim that cannot be rebuilt is not a measurement.

## License

Original code and documentation retain the repository's existing MIT license; see [LICENSE](LICENSE). Model weights, benchmark datasets and other third-party materials keep their own licenses and are not relicensed by this notice.
