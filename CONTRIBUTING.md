# Contributing

This is a research repository: the deliverable is a report whose every number can be rebuilt from `experiments.sqlite` and the run artefacts that ship with it. A change is judged by that property, not by how it reads.

## Scope

- **In scope:** a new controlled comparison (one factor at a time), a corrected or withdrawn claim, a new check that makes a failure mode impossible to miss, ingestion and reporting bug fixes, documentation that keeps a fact at its single home.
- **Out of scope:** model releases or training code, unrecorded protocol changes, hand edits to `report.html` (it is generated), and "improvements" to a number whose command you cannot re-run.
- Unknown, blocked and unmeasured are first-class results. Do not convert them to `0`, and do not delete a cell because it is inconvenient.

## Before opening a pull request

```bash
python3 -m pip install -r requirements.txt
./reproduce.sh          # must exit 0, with no new SKIP/BLOCKED line that used to be PASS
```

`./reproduce.sh` is the whole gate — there is no lint step and no CI. While working, run the individual checks it wraps (`python3 checks/db_check.py`, `python3 docs/check_docs.py`, `python3 checks/router_refs.py`, `python3 checks/evidence_logs.py`, …); `checks/README.md` says what each one proves and who calls it.

If you touch the database: back it up first (numbered `experiments.sqlite.bak*`), then re-run `python3 checks/db_check.py`. If you change anything under `report_inputs/`, regenerate that file and the report together, and commit both.

## A mistake becomes a check

Every failure that can be observed mechanically gets a check, and every check ships with a negative control (`checks/<name>_negative_control.py`) that fails when the thing it guards is broken — an assertion nobody has seen go red is not evidence. Judgement calls that cannot be mechanised get a written rule at the place the mistake happened (usually `AGENTS.md` or the owning `docs/` layer). `./reproduce.sh` calls the pair, so a control that stops working is itself a failure.

## Pull requests

- Small and single-purpose; say which claim or check the change is about.
- Bring the command that reproduces any number you add or change, and its output — not a paraphrase of the output.
- Say what you did **not** verify. A PR that reports an honest gap is better than one that overstates.
- Keep facts at one home. A document that answers a question does not restate an answer owned by another document; link to the owner instead.

## Issues

State the command you ran, what it printed, and what you expected. "The report says X but the artefact says Y" with both paths is the most useful report you can file. If `./reproduce.sh` fails, paste the failing line — `PASS` / `SKIP` / `BLOCKED` / `FAIL` and its text are designed to be readable on their own.

## Language

Code, run logs and commit subjects are English; the research documents under `docs/` are Simplified Chinese (the owners wrote them that way). Either language is fine in an issue or a PR. `README.md` is the English entry point, `README.zh-CN.md` the Chinese one; keep the two in sync when you change structure, not when you change a detail.
