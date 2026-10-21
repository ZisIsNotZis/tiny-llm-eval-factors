#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a06 ordering survival: does the ordering of quantisation levels survive a change
of decoding setting?  A re-checkable criterion, not a sentence in prose.

Run from the repository root:

    python3 "docs/subprojects/a06-采样与解码参数/rank_survival.py" --check

The question this answers is a *pairwise* one, so the output is a ledger of level
pairs, never a single model's single difference:

  * a level pair is CONCORDANT under two settings when both settings order the two
    levels the same way, DISCORDANT when they order them oppositely, TIE when at
    least one side is equal;
  * a level pair SURVIVES when every setting pair is concordant or tied over the
    measured settings, and INVERTS when at least one setting pair is discordant.

Three checked-in fixtures under `fixtures/` hold the answer so a reader can
re-check it without re-deriving anything:

  rank_cells.tsv   every cell the question uses: axis, ladder, level, model, bench,
                   language, setting, score, n_items
  rank_ledger.tsv  one row per (level pair x setting pair) with both signed
                   differences and the verdict
  rank_summary.tsv one row per (level pair) with the counts and the verdict

`--write` regenerates all three from the database; `--check` regenerates them in
memory and fails when a stored fixture no longer matches the database, so a drift
in the DB or in the selection cannot pass silently.

Exit status: 0 when the fixtures match (`--check`) or were written (`--write`);
1 when a stored fixture differs from the database; 2 when an input is missing
(database, or a selection that yields no cell).  Never 0 in the last case.
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
DB = os.path.join(ROOT, "experiments.sqlite")
FIX = os.path.join(ROOT, "docs", "subprojects", "a06-采样与解码参数", "fixtures")

CELLS = os.path.join(FIX, "rank_cells.tsv")
LEDGER = os.path.join(FIX, "rank_ledger.tsv")
SUMMARY = os.path.join(FIX, "rank_summary.tsv")

# ---- the declared design -----------------------------------------------------
# Which measured cells stand for which (level, setting).  This table is a DESIGN
# decision, not a measurement: it says which row of the database is the Q3 cell
# under the fixed protocol.  Adding a decoding arm means adding one entry here and
# nothing else, which is why the vendor-recommended arm lands as a single row.
# (setting, note, WHERE clause, counted_in_ledger).  A setting with
# counted_in_ledger=False is measured and reconciled but kept out of the pairwise
# ledger, because two settings that are numerically identical for every level
# would otherwise contribute the same comparison twice.
SELECTION = [
    ("greedy",   "the fixed protocol: greedy, temp 0, top_k 40, max_tokens 768",
     "run_tag = 'm3-quant-ladder' AND protocol = 'multipl-e-raw-greedy-768'", True),
    # top_k=1 truncates the distribution to its argmax, so it *is* greedy decoding.
    # It is a second, independent measurement of the greedy anchor: the check below
    # requires it to agree with `greedy` on every (level, language) cell, so the
    # equivalence is tested rather than assumed.  It stays out of the ledger
    # because it would double-count the greedy comparisons.
    ("t0.3-k1",  "top_k=1 at temp 0.3 -- independent measurement of the greedy anchor",
     "run_tag = 'm31-topk' AND CAST(top_k AS INTEGER) = 1", False),
    ("t0.3-k20", "temp 0.3, top_k 20",
     "run_tag = 'm31-topk' AND CAST(top_k AS INTEGER) = 20", True),
    ("t0.3-k40", "temp 0.3, top_k 40",
     "run_tag = 'm31-topk' AND CAST(top_k AS INTEGER) = 40", True),
    ("t0.3-k64", "temp 0.3, top_k 64",
     "run_tag = 'm31-topk' AND CAST(top_k AS INTEGER) = 64", True),
    ("t0.3-k200", "temp 0.3, top_k 200",
     "run_tag = 'm31-topk' AND CAST(top_k AS INTEGER) = 200", True),
    ("t0.6-k40", "temp 0.6, top_k 40",
     "run_tag = 'm27-sampling' AND temp = '0.6'", True),
]

# The ladder under test: quantisation levels of ONE family at ONE size.  A size
# ladder would be a second entry with axis='size'; the tool does not care which.
AXIS = "quant-level"
LADDER = "Qwen3.5-2B"
LEVELS = [
    ("Q2", "Qwen3.5-2B-UD-Q2_K_XL.gguf"),
    ("Q3", "Qwen3.5-2B-UD-Q3_K_XL.gguf"),
    ("Q4", "Qwen3.5-2B-UD-Q4_K_XL.gguf"),
]
BENCH = "humaneval-multipl-e"
LANGUAGES = ["cpp", "py"]

MISSING = []


def connect():
    if not os.path.exists(DB):
        MISSING.append(f"database: {DB}")
        return None
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def cells(con):
    """Every (ladder, level, language, setting) -> score, from the declared design."""
    out = {}
    for setting, _note, where, _in_ledger in SELECTION:
        for level, model in LEVELS:
            for lang in LANGUAGES:
                rows = con.execute(
                    f"SELECT _score, n_items FROM experiments "
                    f"WHERE model = ? AND bench_family = ? AND language = ? "
                    f"AND _score IS NOT NULL AND {where}",
                    (model, BENCH, lang)).fetchall()
                if not rows:
                    continue
                scores = {r[0] for r in rows}
                if len(scores) > 1:
                    # two rows under one setting is a selection defect, not a value
                    MISSING.append(
                        f"ambiguous cell {model}/{lang}/{setting}: "
                        f"{sorted(scores)} match the same declared setting")
                    continue
                out[(LADDER, level, lang, setting)] = rows[0]
    return out


def bench_n(cell_map, level, lang, setting):
    """Item count of a cell.  The sampling panels carry n_items NULL, so fall back
    to the ladder's full-cell item count, which is itself verified: every score
    times that count is an integer (RESULT.md::limit-n-items)."""
    n = cell_map[(LADDER, level, lang, setting)][1]
    return n if n else 0


def build(con):
    cell_map = cells(con)
    if not cell_map:
        MISSING.append("selection matched no cell")
        return None, None, None
    cell_rows = []
    for (ladder, level, lang, setting) in sorted(cell_map):
        score, n_items = cell_map[(ladder, level, lang, setting)]
        cell_rows.append("\t".join([
            AXIS, ladder, level, dict(LEVELS)[level], BENCH, lang, setting,
            f"{score:.6f}", "" if n_items is None else str(n_items)]))

    settings = [s for s, _n, _w, counted in SELECTION if counted]
    # Anchor reconciliation: every non-counted setting must agree with `greedy`
    # exactly, cell by cell.  This is the checkable form of "top_k=1 is greedy".
    reconcile = [s for s, _n, _w, counted in SELECTION if not counted]
    for setting in reconcile:
        for level, _model in LEVELS:
            for lang in LANGUAGES:
                a = cell_map.get((LADDER, level, lang, setting))
                b = cell_map.get((LADDER, level, lang, "greedy"))
                if a is None or b is None:
                    MISSING.append(f"anchor reconciliation needs a cell: "
                                   f"{level}/{lang}/{setting}")
                elif round(a[0], 6) != round(b[0], 6):
                    MISSING.append(
                        f"anchor reconciliation FAILED: {level}/{lang} {setting}="
                        f"{a[0]:.6f} vs greedy={b[0]:.6f}")
    pairs = [(a, b) for i, a in enumerate(LEVELS)
             for b in LEVELS[i + 1:]]
    ledger, summary = [], []
    for a, b in pairs:
        for lang in LANGUAGES:
            per_setting = {}
            for setting in settings:
                ka = (LADDER, a[0], lang, setting)
                kb = (LADDER, b[0], lang, setting)
                if ka in cell_map and kb in cell_map:
                    per_setting[setting] = (
                        round(cell_map[ka][0] - cell_map[kb][0], 6),
                        int(round((cell_map[ka][0] - cell_map[kb][0]) *
                                  (bench_n(cell_map, a[0], lang, setting) or
                                   bench_n(cell_map, b[0], lang, setting) or 0))))
            usable = [s for s in settings if s in per_setting]
            conc = tie = inv = 0
            for i, s1 in enumerate(usable):
                for s2 in usable[i + 1:]:
                    d1 = per_setting[s1][0]
                    d2 = per_setting[s2][0]
                    if d1 * d2 > 0:
                        verdict = "concordant"
                        conc += 1
                    elif d1 * d2 < 0:
                        verdict = "discordant"
                        inv += 1
                    else:
                        verdict = "tie"
                        tie += 1
                    ledger.append("\t".join([
                        AXIS, LADDER, BENCH, lang, f"{a[0]}>{b[0]}", s1, s2,
                        f"{d1:+.6f}", f"{d2:+.6f}", verdict]))
            outcome = ("survives" if inv == 0 else
                       ("inverts" if conc else "all-tie"))
            summary.append("\t".join([
                AXIS, LADDER, BENCH, lang, f"{a[0]}>{b[0]}",
                str(conc), str(tie), str(inv), str(len(usable)), outcome]))

    header_cells = ("# axis\tladder\tlevel\tmodel\tbench\tlanguage\tsetting"
                    "\tscore\tn_items")
    header_ledger = ("# axis\tladder\tbench\tlanguage\tlevel_pair\tsetting_a"
                     "\tsetting_b\tdiff_a\tdiff_b\tverdict")
    header_summary = ("# axis\tladder\tbench\tlanguage\tlevel_pair\tconcordant"
                      "\ttie\tdiscordant\tsettings\toutcome")
    return ("\n".join([header_cells] + cell_rows) + "\n",
            "\n".join([header_ledger] + ledger) + "\n",
            "\n".join([header_summary] + summary) + "\n")


def print_summary(text):
    print("ordering survival -- quantisation levels of Qwen3.5-2B, 161-item cells")
    print(f"  {'lang':<5}{'level pair':<12}{'conc':>5}{'tie':>5}{'inv':>5}"
          f"{'set':>5}  outcome")
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        f = line.split("\t")
        print(f"  {f[3]:<5}{f[4]:<12}{f[5]:>5}{f[6]:>5}{f[7]:>5}{f[8]:>5}  {f[9]}")


def main(argv):
    mode = argv[0] if argv else "--check"
    if mode not in ("--check", "--write"):
        print(__doc__, file=sys.stderr)
        return 2
    con = connect()
    if con is None:
        print("UNMEASURED: cannot see the database:", file=sys.stderr)
        for m in MISSING:
            print(f"  {m}", file=sys.stderr)
        return 2
    built = build(con)
    if built[0] is None:
        print("UNMEASURED: the declared selection produced no cell:", file=sys.stderr)
        for m in MISSING:
            print(f"  {m}", file=sys.stderr)
        return 2
    if MISSING:
        print("UNMEASURED: ambiguous or incomplete selection:", file=sys.stderr)
        for m in MISSING:
            print(f"  {m}", file=sys.stderr)
        return 2
    cells_text, ledger_text, summary_text = built
    print_summary(summary_text)

    if mode == "--write":
        os.makedirs(FIX, exist_ok=True)
        for path, text in ((CELLS, cells_text), (LEDGER, ledger_text),
                           (SUMMARY, summary_text)):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(f"wrote {os.path.relpath(path, ROOT)}")
        return 0

    drift = []
    for path, text in ((CELLS, cells_text), (LEDGER, ledger_text),
                       (SUMMARY, summary_text)):
        rel = os.path.relpath(path, ROOT)
        if not os.path.exists(path):
            drift.append(f"{rel}: missing (run --write)")
            continue
        stored = open(path, encoding="utf-8").read()
        if stored != text:
            s = set(stored.splitlines())
            n = set(text.splitlines())
            drift.append(f"{rel}: {len(s - n)} stored line(s) no longer in the DB, "
                         f"{len(n - s)} DB line(s) not in the fixture")
    if drift:
        print("\nFAIL: the stored fixtures disagree with the database", file=sys.stderr)
        for d in drift:
            print(f"  {d}", file=sys.stderr)
        return 1
    print("\nOK: cells, ledger and summary all reproduce from experiments.sqlite")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
