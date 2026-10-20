#!/usr/bin/env python3
"""Audit every MultiPL-E cell in `experiments.sqlite` against the artefact behind it.

The a12 acceptance asks two things of data rather than of prose:

1. lineage  -- does each model x language cell in the DB trace to a stored panel
   summary (`source_file`) or to a per-item eval file whose pass count reproduces
   the stored score at the language's item count?
2. coverage -- which model x language cells were never measured, and which stored
   values are non-measurements rather than scores?

The script is read-only: it opens the database with `mode=ro` and writes nothing.

Run from the repository root:

    python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"

Exit 0 = every scored cell traced, no all-Exception cell carries a score, and the
prompt set matches its pin.  Exit 1 = at least one of those failed (the offending
rows are printed).  Exit 2 = the DB is missing.  A NULL cell is a declared
non-measurement: it is listed, never failed.
"""
from __future__ import annotations

import collections
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB = os.path.join(REPO, "experiments.sqlite")
WRAPUP = os.path.join(REPO, ".wrapup")
PROMPTS = os.path.join(WRAPUP, "prompts")

LANGS = ["cpp", "py", "js", "java", "rs", "rb"]
RAW_GREEDY = "multipl-e-raw-greedy-768"


def mpl_rows():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    rows = con.execute(
        "SELECT model, protocol, language, _score, n_items, run_tag, source_file "
        "FROM experiments WHERE bench_family='humaneval-multipl-e' "
        "ORDER BY source_file, model, language").fetchall()
    con.close()
    return rows


def summary_lines(source_file):
    """{lang: [(score, n, protocol)]} for one panel summary, or None if absent."""
    path = os.path.join(WRAPUP, source_file or "")
    if not source_file or not os.path.exists(path):
        return None
    out = collections.defaultdict(list)
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if "lang" in r and "score" in r:
            out[r["lang"]].append((r["score"], r.get("n"), r.get("protocol")))
    return out


def language_item_counts():
    """{language: item count} from every stored panel summary, most common first.

    A MultiPL-E row in the DB carries no `n_items`, so the item count a cell was
    scored on lives only in the panel summary; the most common count per language
    is the full-cell size (161 for the 161-problem panels).
    """
    seen = collections.defaultdict(list)
    for path in glob.glob(os.path.join(WRAPUP, "*_summary.jsonl")):
        for lang, lines in (summary_lines(os.path.basename(path)) or {}).items():
            seen[lang].extend(n for _s, n, _p in lines if n)
    return {lang: collections.Counter(v).most_common(1)[0][0] for lang, v in seen.items()}


def eval_index():
    """{(lang, pass, n): [(basename, Counter(status))]} from the per-item eval files."""
    idx = collections.defaultdict(list)
    for path in glob.glob(os.path.join(WRAPUP, "mres", "*_eval.json")):
        try:
            d = json.load(open(path, encoding="utf-8"))
        except ValueError:
            continue
        det = d.get("details")
        if not isinstance(det, list) or not det:
            continue
        base = re.sub(r"(-chat)?(_fixed)?$", "", os.path.basename(path)[: -len("_eval.json")])
        lang = next((l for l in LANGS if base.endswith("-" + l) or base.endswith("_" + l)), None)
        idx[(lang, int(d.get("pass") or 0), len(det))].append(
            (os.path.basename(path), collections.Counter(x.get("status") for x in det)))
    return idx


def own_eval_files(cell, candidates):
    """Narrow `(lang, pass, n)` candidates to the files this cell can own.

    Pass/n is not model-unique: different models hit the same count, so the
    pairing the report uses accepts any file and only then insists the status
    histograms agree.  For lineage the file must also belong to this cell, which
    the run tag's panel prefix and, where the protocol string carries them, the
    ctx / KV tokens decide.
    """
    tag = (cell["run_tag"] or "").split("-")[0]
    own = [(b, st) for b, st in candidates if tag and b.startswith(tag + "-")]
    matched = "tag"
    if not own:
        own, matched = candidates, "pair-only"
    for pat in (r"ctx=(\d+)", r"kv=(\w+)/(\w+)"):
        m = re.search(pat, cell["protocol"] or "")
        if not m:
            continue
        needle = "ctx" + m.group(1) if pat.startswith("ctx") else "kv%s_%s" % m.groups()
        hit = [(b, st) for b, st in own if needle in b]
        own = hit or own
    return own, matched


def cells_with_lineage(rows, idx, lang_n):
    """One record per stored cell: its item count, artefact source and eval hits."""
    out = []
    per_file = collections.defaultdict(list)
    for row in rows:
        per_file[row[6] or ""].append(row)
    for src, group in sorted(per_file.items()):
        lines = summary_lines(src)
        # A summary may hold more lines than the DB uses (a superseded re-run, a
        # probe, a cell a later panel replaced), so the DB's multiset must be a
        # sub-multiset of the file's, consumed once per DB cell.
        pool = collections.Counter((lang, round(sc, 9)) for lang, ls in (lines or {}).items()
                                   for sc, _n, _p in ls)
        for model, proto, lang, score, _n_items, tag, _src in group:
            rec = {"model": model, "protocol": proto, "lang": lang, "score": score,
                   "run_tag": tag, "source_file": src, "n": None,
                   "via_summary": False, "eval": [], "own_eval": [], "own_match": None}
            if score is not None:
                key = (lang, round(score, 9))
                if pool[key] > 0:
                    pool[key] -= 1
                    rec["via_summary"] = True
                    for sc, n, _p in lines.get(lang, []):
                        if sc == score:
                            rec["n"] = n
                            break
                if rec["n"] is None:
                    rec["n"] = lang_n.get(lang)
                if rec["n"]:
                    passes = int(round(score * rec["n"]))
                    rec["eval"] = idx.get((lang, passes, rec["n"]), [])
                    rec["own_eval"], rec["own_match"] = own_eval_files(rec, rec["eval"])
                if not rec["via_summary"] and not rec["own_eval"]:
                    # The pair-only match landed on another cell's file: not a trace.
                    rec["eval"] = []
            out.append(rec)
    return out


def coverage(cells):
    """{(protocol, model): {language: score}} over the stored cells."""
    matrix = collections.defaultdict(dict)
    for c in cells:
        matrix[(c["protocol"], c["model"])][c["lang"]] = c["score"]
    return matrix


def report_mpl_cells():
    """[(model, lang, score, n)] from the per-language table inside `report.html`.

    Read out of the generated artefact rather than from `make_report` internals:
    the acceptance is about what the report shows, and a stale report is exactly
    the failure this check must see.
    """
    path = os.path.join(REPO, "report.html")
    if not os.path.exists(path):
        return None
    h = open(path, encoding="utf-8").read()
    start = h.find("<th>模型文件</th><th>生成协议</th>")
    if start < 0:
        return None
    table = h[start:h.find("</table>", start)]
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 2 + len(LANGS):
            continue
        model = re.sub(r"<[^>]+>", "", tds[0]).strip()
        if model in ("覆盖", ""):
            continue
        for i, lang in enumerate(LANGS):
            cell = tds[2 + i]
            m = re.match(r"\s*([0-9.]+)", re.sub(r"<[^>]+>", "", cell)
                         if "<span" in cell else cell)
            if not m:
                continue
            n = re.search(r"\((\d+)\)", cell)
            out.append((model, lang, round(float(m.group(1)), 4),
                        int(n.group(1)) if n else None))
    return out


def main() -> int:
    if not os.path.exists(DB):
        print("FAIL: %s is missing" % DB)
        return 2
    rows = mpl_rows()
    idx = eval_index()
    lang_n = language_item_counts()
    cells = cells_with_lineage(rows, idx, lang_n)
    scored = [c for c in cells if c["score"] is not None]
    nulls = [c for c in cells if c["score"] is None]
    print("MultiPL-E cells in the DB: %d (scored %d, NULL %d); full-cell item counts: %s"
          % (len(cells), len(scored), len(nulls), {l: lang_n.get(l) for l in LANGS}))

    print("\n[1] lineage: does each scored cell trace to a stored artefact?")
    untraced = [c for c in scored if not c["via_summary"] and not c["own_eval"]]
    via_eval = [c for c in scored if not c["via_summary"] and c["own_eval"]]
    no_eval = [c for c in scored if not c["own_eval"]]
    print("    scored cells traced          : %d/%d (via summary %d, via per-item eval %d)"
          % (len(scored) - len(untraced), len(scored), len(scored) - len(untraced) - len(via_eval),
             len(via_eval)))
    print("    untraced                     : %d" % len(untraced))
    for c in via_eval:
        print("      eval-only trace: %-40s %-6s %r <- %s (%s match)"
              % (c["model"], c["lang"], c["score"], [b for b, _s in c["own_eval"]],
                 c["own_match"]))
    for c in untraced:
        print("      UNTRACED: %-40s %-24s %-5s %r (summary %s, n=%s)"
              % (c["model"], c["protocol"], c["lang"], c["score"], c["source_file"], c["n"]))
    print("    scored cells with no per-item eval: %d/%d (older panels stored only the panel "
          "summary; the summary is then the artefact of record)" % (len(no_eval), len(scored)))
    print("    eval keys with >1 file       : %d (the report accepts only identical status "
          "histograms for those)" % sum(1 for v in idx.values() if len(v) > 1))

    print("\n[2] coverage: canonical raw-greedy protocol (%s)" % RAW_GREEDY)
    matrix = coverage(cells)
    raw_models = sorted(m for (p, m) in matrix if p == RAW_GREEDY)
    full = [m for m in raw_models
            if all(matrix[(RAW_GREEDY, m)].get(l) is not None for l in LANGS)]
    pair = [m for m in raw_models if matrix[(RAW_GREEDY, m)].get("cpp") is not None
            and matrix[(RAW_GREEDY, m)].get("py") is not None]
    print("    models: %d; with all 6 languages: %d; with the cpp+py pair: %d"
          % (len(raw_models), len(full), len(pair)))
    print("    measured cells per language: " + ", ".join(
        "%s %d" % (l, sum(1 for m in raw_models if matrix[(RAW_GREEDY, m)].get(l) is not None))
        for l in LANGS))
    for m in raw_models:
        marks = []
        for l in LANGS:
            if l not in matrix[(RAW_GREEDY, m)]:
                marks.append("     .")
            elif matrix[(RAW_GREEDY, m)][l] is None:
                marks.append("  NULL")
            else:
                marks.append("%.4f" % matrix[(RAW_GREEDY, m)][l])
        print("      %-46s | %s" % (m, " ".join(marks)))

    print("\n[3] coverage: chat-generation protocol")
    chat = sorted((p, m) for (p, m) in matrix if "chat" in p)
    for proto, m in chat:
        print("      %-46s %-52s %s" % (m, proto, {
            l: ("NULL" if v is None else round(v, 4)) for l, v in matrix[(proto, m)].items()}))
    print("    chat cells: %d over %d models; languages %s"
          % (sum(len(matrix[(p, m)]) for p, m in chat), len({m for _p, m in chat}),
             sorted({l for p, m in chat for l in matrix[(p, m)]})))

    print("\n[4] non-measurements and stored zeros")
    print("    NULL cells (every item raised -> missing, never a 0): %d" % len(nulls))
    for c in nulls:
        print("      %-46s %-22s %-4s run_tag=%-20s file=%s"
              % (c["model"], c["protocol"], c["lang"], c["run_tag"], c["source_file"]))
    zeros = [c for c in scored if c["score"] == 0.0]
    print("    cells stored as exactly 0.0: %d" % len(zeros))
    for c in zeros:
        hist = c["own_eval"][0][1] if len(c["own_eval"]) == 1 else None
        print("      %-46s %-5s n=%-4s run_tag=%-20s %s"
              % (c["model"], c["lang"], c["n"], c["run_tag"],
                 ("%s <- %s (%s match)" % (dict(hist), c["own_eval"][0][0], c["own_match"]))
                 if hist else "%d candidate(s), %s match" % (len(c["own_eval"]), c["own_match"])))
    # The carried defect class: a cell whose items all raised is a non-measurement,
    # so a stored score there is fabricated, whichever value it holds.
    bad = [c for c in scored for _b, st in c["own_eval"]
           if st and sum(st.values()) == st.get("Exception", 0)]
    print("    scored cells whose eval is all-Exception: %d" % len(bad))
    for c in bad:
        print("      %-46s %-5s %r <- %s" % (c["model"], c["lang"], c["score"],
                                            [b for b, _s in c["own_eval"]]))

    print("\n[5] is one pooled cpp+py number faithful to both languages?")
    both = [(m, matrix[(RAW_GREEDY, m)]["cpp"], matrix[(RAW_GREEDY, m)]["py"]) for m in pair]
    deltas = sorted(((py - cpp), m) for m, cpp, py in both)
    print("    models with cpp+py: %d; py-cpp delta: min %+.4f (%s), max %+.4f (%s), median %+.4f"
          % (len(both), deltas[0][0], deltas[0][1], deltas[-1][0], deltas[-1][1],
             deltas[len(deltas) // 2][0]))
    order_cpp = [m for m, _c, _p in sorted(both, key=lambda t: t[1])]
    order_py = [m for m, _c, _p in sorted(both, key=lambda t: t[2])]
    disc = sum(1 for i in range(len(order_cpp)) for j in range(i + 1, len(order_cpp))
               if (order_cpp[i] < order_cpp[j]) != (order_py[i] < order_py[j]))
    print("    pairwise orderings the two languages disagree on: %d of %d pairs"
          % (disc, len(order_cpp) * (len(order_cpp) - 1) // 2))

    print("\n[6] prompt set pin (.wrapup/prompts/SHA256SUMS)")
    sums = os.path.join(PROMPTS, "SHA256SUMS")
    drift = []
    if not os.path.exists(sums):
        drift.append("SHA256SUMS missing")
    else:
        pinned = [l.split() for l in open(sums, encoding="utf-8") if l.split()]
        for want, name in pinned:
            path = os.path.join(PROMPTS, name)
            got = (hashlib.sha256(open(path, "rb").read()).hexdigest()
                   if os.path.exists(path) else None)
            if got != want:
                drift.append(name)
        print("    %d files pinned; %d drifted" % (len(pinned), len(drift)))
    for name in drift:
        print("      DRIFT: %s" % name)

    print("\n[7] every MultiPL-E cell printed in report.html is a stored cell")
    shown = report_mpl_cells()
    stale = []
    if shown is None:
        print("    report.html: no per-language MultiPL-E table found")
        stale.append("report.html")
    else:
        stored = {(c["model"], c["lang"], round(c["score"], 4)) for c in scored}
        for model, lang, score, _n in shown:
            if (model, lang, score) not in stored:
                stale.append((model, lang, score))
        print("    report cells read: %d; not found in the DB: %d" % (len(shown), len(stale)))
        for row in stale[:20]:
            print("      NOT IN DB: %s" % (row,))
        print("    report.html mtime %s, DB mtime %s"
              % (int(os.path.getmtime(os.path.join(REPO, "report.html"))),
                 int(os.path.getmtime(DB))))

    ok = not untraced and not bad and not drift and not stale
    print("\n%s" % ("PASS: every scored cell traces to a stored artefact, no all-Exception cell "
                    "carries a score, the prompt set matches its pin, and every cell the report "
                    "prints is a stored cell" if ok else
                    "FAIL: see the untraced / all-Exception / drift / not-in-DB rows above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
