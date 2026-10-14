# DB de-duplication (2026-10-14) — integrity note

## What happened

`experiments.sqlite` accumulated **exact duplicate rows** (all 47 columns identical). Root
cause: `migrate_db.py` is **not idempotent for the MultiPL-E / per-language ingest paths**
(underlying behaviour predates this work — `bak31` already had 4928 rows / 3044 unique).
The AXES **finisher** (`axes_finisher.sh`) ran `migrate_db.py` every 10 minutes for ~13 h,
which amplified it:

| snapshot | rows | distinct (all cols) | excess |
|---|---:|---:|---:|
| `bak31` (10-12 22:55) | 4928 | 3044 | 1884 |
| `bak32` (10-13 02:37) | 5328 | 3124 | 2204 |
| `bak33` (10-13 10:49) | 5558 | 3194 | 2364 |
| **before dedup** (10-14 06:52) | **12871** | **3307** | **9564** |

Exact duplicates are information-free: the DB cannot distinguish them (`rep` identical too),
and the analysis scripts aggregate over distinct values / use stored `n_items`, so results are
unaffected. But the table violated the workspace cleanliness rule.

## Fix applied

Backup `experiments.sqlite.bak34` → rebuilt the table as
`SELECT DISTINCT <all 47 columns>` → recreated the 5 indexes → verified:

- rows **12871 → 3307** (removed 9564 exact duplicates)
- `PRAGMA integrity_check` = **ok**, `foreign_key_check` = **[]**
- null/empty mandatory fields = **0**
- all AXES tags (`m140`–`m156`) and campaign tags (`m68`, `m116`, …) present
- `bpw_sensitivity.py`, `bpw_paired.py`, `axes_findings.py`, `mktables.py`, figures all re-run
  clean on the deduped DB; F9 grouped paired test unchanged (+0.123 vs +0.120), F12/F13 intact

## Rule going forward

**Do NOT re-run `migrate_db.py` on a schedule.** Run it once per ingest event, then verify
`total == distinct`. If repeated runs are ever needed, fix the per-language ingest to
`DELETE FROM experiments WHERE run_tag=?` first (the pattern already used by `ingest_m22`).
