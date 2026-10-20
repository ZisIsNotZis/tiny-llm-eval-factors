#!/usr/bin/env python3
"""Audit every MultiPL-E cell in `experiments.sqlite` against the artefact behind it.

The a12 acceptance asks two things of data rather than of prose:

1. lineage  -- does each model x language cell in the DB trace to a stored panel
   summary (`source_file`) or to a per-item eval file whose pass count reproduces
   the stored score at the language's item count?
2. coverage -- which model x language cells were never measured, and which stored
   values are non-measurements rather than scores?

The script is read-only: it opens the database with `mode=ro` and writes nothing
(it does import `make_report` for `mpl_protocol_label`, so that the report's row
labels are interpreted by the same function that wrote them).

Run from the repository root:

    python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"
    python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py" --report PATH

The output starts with the revision it audited, the script's own sha256 and the
exact command, so a saved capture is bound to a tree instead of to a claim.

Exit 0 = every scored cell traced, no all-Exception cell carries a score, the prompt
set matches its pin, every cell the report prints carries its own protocol and item
count, and no stored protocol lost a setting at ingest.  Exit 1 = at least one of
those failed (the offending rows are printed).  Exit 2 = the DB is missing.  A NULL
cell is a declared non-measurement: it is listed, never failed.
"""
from __future__ import annotations

import collections
import glob
import hashlib
import itertools
import json
import os
import re
import sqlite3
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB = os.path.join(REPO, "experiments.sqlite")
WRAPUP = os.path.join(REPO, ".wrapup")
PROMPTS = os.path.join(WRAPUP, "prompts")

LANGS = ["cpp", "py", "js", "java", "rs", "rb"]


def revision():
    """`git HEAD` of the tree being audited, or `unknown` outside a checkout."""
    try:
        return subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def dirty_files():
    """Paths modified/untracked in the audited tree: a clean capture has only evidence."""
    try:
        out = subprocess.run(["git", "-C", REPO, "status", "--short"], check=True,
                             capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return ", ".join(line[3:] for line in out.splitlines() if line.strip()) or "none"


def script_sha256():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()


def protocol_settings(proto):
    """(settings, trailing label) of a protocol string.

    `mpl-raw-greedy-768-third-family-code` names the frozen settings up to the token
    count and then a panel label; the database keeps the settings and records the
    panel in `run_tag`.  Two cells may only share a protocol when this settings part
    is equal, so a mismatch here means a setting was lost or two protocols were
    relabelled into one.
    """
    head = (proto or "").strip().split(";")[0]
    m = re.match(r"^(.*?-\d+)(-.*)?$", head)
    settings, label = (m.group(1), m.group(2) or "") if m else (head, "")
    return settings.replace("mpl-raw-", "multipl-e-raw-", 1), label
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
    tier = re.search(r"[Qq]([0-9])", cell.get("model") or "")
    if tier:
        hit = [(b, st) for b, st in own if "q%s" % tier.group(1) in b]
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


def report_mpl_cells(path):
    """[(model, protocol_label, lang, score, n)] from the per-language table in a report.

    Read out of the generated artefact rather than from `make_report` internals: the
    acceptance is about what the report shows, and a stale or hand-edited report is
    exactly the failure this check must see.  The protocol cell decides which row a
    value belongs to, so it is kept: without it a value from one protocol could be
    checked against any row of the same model.
    """
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
        label = re.sub(r"<[^>]+>", "", tds[1]).strip()
        for i, lang in enumerate(LANGS):
            cell = tds[2 + i]
            text = re.sub(r"<[^>]+>", "", cell) if "<span" in cell else cell
            m = re.match(r"\s*([0-9.]+)", text)
            if not m:
                continue
            n = re.search(r"\((\d+)\)", cell)
            out.append((model, label, lang, round(float(m.group(1)), 4),
                        int(n.group(1)) if n else None))
    return out


def main() -> int:
    report_path = os.path.join(REPO, "report.html")
    if "--report" in sys.argv:
        report_path = os.path.abspath(sys.argv[sys.argv.index("--report") + 1])
    print("a12 MultiPL-E cell audit")
    print("  audited revision : %s" % revision())
    print("  script sha256    : %s" % script_sha256())
    print("  command          : %s %s" % (os.path.basename(sys.executable), " ".join(sys.argv)))
    print("  report           : %s" % report_path)
    print("  dirty paths      : %s" % dirty_files())
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
    one = sum(1 for c in scored if len(c["eval"]) == 1)
    many = sum(1 for c in scored if len(c["eval"]) > 1)
    print("    scored cells with no per-item eval: %d/%d (older panels stored only the panel "
          "summary; the summary is then the artefact of record)" % (len(no_eval), len(scored)))
    print("    (language, pass, n) key matches one file: %d cells; several files: %d cells "
          "(the key is not model-unique, so it proves a file reproduces the cell, not that the "
          "file is this model's)" % (one, many))
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
    tally = {l: {"scored": 0, "null": 0, "absent": 0} for l in LANGS}
    for m in raw_models:
        for l in LANGS:
            if l not in matrix[(RAW_GREEDY, m)]:
                tally[l]["absent"] += 1
            elif matrix[(RAW_GREEDY, m)][l] is None:
                tally[l]["null"] += 1
            else:
                tally[l]["scored"] += 1
    print("    per language: " + "; ".join(
        "%s scored %d / NULL %d / absent %d" % (l, tally[l]["scored"], tally[l]["null"],
                                               tally[l]["absent"]) for l in LANGS))
    print("    of %d model x language slots: %d scored, %d NULL, %d absent"
          % (len(raw_models) * len(LANGS), sum(t["scored"] for t in tally.values()),
             sum(t["null"] for t in tally.values()), sum(t["absent"] for t in tally.values())))
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
    chat_models = sorted({m for _p, m in chat})
    chat_absent = sum(1 for m in chat_models for l in LANGS
                      if not any(l in matrix[(p, m)] for p, _m in chat if _m == m))
    print("    unmeasured under chat: %d of %d model x language slots (languages %s, %d models)"
          % (chat_absent, len(chat_models) * len(LANGS),
             sorted({l for m in chat_models for l in LANGS if l not in {ll for p, mm in chat if mm == m for ll in matrix[(p, mm)]}}),
             len(chat_models)))

    print("\n[4] non-measurements and stored zeros")
    print("    NULL cells (every item raised -> missing, never a 0): %d" % len(nulls))
    for c in nulls:
        # The panel summary can still hold a 0.0 for such a cell (it did for m51/m54), so the
        # proof that the cell is a non-measurement is the per-item status histogram, not the
        # summary score.
        n = c["n"] or lang_n.get(c["lang"])
        cands = idx.get((c["lang"], 0, n), []) if n else []
        own, _match = own_eval_files(
            {"run_tag": c["run_tag"], "protocol": c["protocol"], "model": c["model"]}, cands)
        # Several files for one cell are a panel and its re-measurement; they only stand in
        # for one another when their status histograms agree.
        hists = {tuple(sorted(st.items())) for _b, st in own}
        hist = dict(own[0][1]) if own and len(hists) == 1 else None
        print("      %-46s %-22s %-4s run_tag=%-20s %s"
              % (c["model"], c["protocol"], c["lang"], c["run_tag"],
                 ("%s <- %s" % (hist, own[0][0])) if hist
                 else "file=%s, %d eval candidate(s)" % (c["source_file"], len(own))))
    zeros = [c for c in scored if c["score"] == 0.0]
    print("    cells stored as exactly 0.0: %d" % len(zeros))
    for c in zeros:
        hists = {tuple(sorted(st.items())) for _b, st in c["own_eval"]}
        hist = c["own_eval"][0][1] if c["own_eval"] and len(hists) == 1 else None
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
    deltas = sorted(py - cpp for _m, cpp, py in both)
    print("    models with cpp+py: %d; py-cpp delta: min %+.4f, median %+.4f, max %+.4f; "
          "|delta|>0.05 on %d models" % (len(both), deltas[0], deltas[len(deltas) // 2],
                                         deltas[-1], sum(1 for d in deltas if abs(d) > 0.05)))
    def sign(x):
        return (x > 0) - (x < 0)
    disc = tie = 0
    for (m1, c1, p1), (m2, c2, p2) in itertools.combinations(both, 2):
        a, b = sign(c1 - c2), sign(p1 - p2)
        if a == 0 or b == 0:
            tie += 1
        elif a != b:
            disc += 1
    npairs = len(both) * (len(both) - 1) // 2
    print("    model pairs the two languages order oppositely: %d of %d (%.1f%%); "
          "%d more pairs tie in at least one language"
          % (disc, npairs, 100.0 * disc / npairs, tie))

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

    print("\n[7] every cell the report prints belongs to its own protocol row")
    shown = report_mpl_cells(report_path)
    stale = []
    if shown is None:
        print("    %s: no per-language MultiPL-E table found" % report_path)
        stale.append(report_path)
    else:
        sys.path.insert(0, REPO)
        import make_report  # noqa: E402  the report's own label function
        by_model_lang = collections.defaultdict(list)
        for c in scored:
            by_model_lang[(c["model"], c["lang"])].append(
                (make_report.mpl_protocol_label(c["protocol"]), round(c["score"], 4), c["n"]))
        for model, label, lang, score, n in shown:
            alts = [a for a in by_model_lang[(model, lang)] if a[0] == label]
            if not alts:
                stale.append((model, label, lang, score, "no stored cell under this row's protocol label"))
            elif not any(abs(a[1] - score) < 1e-9 for a in alts):
                stale.append((model, label, lang, score,
                              "stored values under this label are %s" % sorted({a[1] for a in alts})))
            elif n is not None and all(a[2] != n for a in alts if abs(a[1] - score) < 1e-9):
                stale.append((model, label, lang, score,
                              "printed n=%s, artefact n=%s" % (n, sorted({a[2] for a in alts}))))
        print("    report cells read: %d; not belonging to their protocol row: %d"
              % (len(shown), len(stale)))
        for row in stale[:20]:
            print("      MISMATCH: %s" % (row,))
        print("    report mtime %s, DB mtime %s"
              % (int(os.path.getmtime(report_path)), int(os.path.getmtime(DB))))

    print("\n[8] standard-column pooling state in the report")
    pooled = split = 0
    if os.path.exists(report_path):
        h = open(report_path, encoding="utf-8").read()
        for table in re.findall(r"<table[^>]*>(.*?)</table>", h, re.S):
            heads = [re.sub(r"<[^>]+>", "", x) for x in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
            mpl = sum(1 for x in heads if "多语言" in x)
            if mpl == 1:
                pooled += 1
            elif mpl >= 2:
                split += 1
    print("    standard tables with ONE pooled MultiPL-E column: %d" % pooled)
    print("    standard tables with per-language MultiPL-E columns: %d" % split)
    print("    %s" % ("pooled: the standard column averages cpp+py, which the acceptance forbids; "
                     "the split is i02's work package (PLAN.md WP7)" if pooled else
                     "no standard table pools cpp+py"))

    print("\n[9] no stored protocol lost a setting at ingest")
    relabel = []
    for c in cells:
        if not c["via_summary"]:
            continue
        lines = summary_lines(c["source_file"]) or {}
        # A panel can hold several lines with the same score under different settings
        # (m27's temperature sweep reproduces the greedy floor), so the stored protocol
        # is wrong only when none of them carries the stored settings.
        cands = [p for sc, _n, p in lines.get(c["lang"], []) if sc == c["score"]]
        if not cands:
            continue
        have, _t = protocol_settings(c["protocol"])
        if not any(protocol_settings(p)[0] == have for p in cands):
            relabel.append((c["model"], c["lang"], cands[0], c["protocol"]))
    print("    cells whose summary settings differ from the stored protocol: %d" % len(relabel))
    for row in relabel[:20]:
        print("      RELABELLED: summary %r -> stored %r (%s %s)" % (row[2], row[3], row[0], row[1]))

    print("\n[10] cells the per-language table cannot hold apart (row key lacks a column)")
    by_key = collections.defaultdict(list)
    for c in scored:
        by_key[(c["model"], c["protocol"], c["lang"])].append((round(c["score"], 4), c["run_tag"]))
    lost = {k: v for k, v in by_key.items() if len({s for s, _t in v}) > 1}
    same = sum(1 for v in by_key.values() if len(v) > 1) - len(lost)
    print("    (model, protocol, language) keys: %d from %d scored rows; %d keys repeat the "
          "same value (duplicate ingest), %d keys disagree" % (len(by_key), len(scored), same, len(lost)))
    for k, v in lost.items():
        print("      ONE ROW HIDES OTHERS: %s %s %s -> %s" % (k[0], k[1], k[2], v))

    print("    OPEN (i02): a row key without the varied column hides the other rows; the "
          "sampling axis measures that column, this table cannot" if lost else
          "    every repeated key repeats the same value")

    ok = not untraced and not bad and not drift and not stale and not relabel
    print("\n%s" % ("PASS: every scored cell traces to a stored artefact, no all-Exception cell "
                    "carries a score, no stored protocol lost a setting, the prompt set matches "
                    "its pin, and every cell the report prints belongs to its own protocol row"
                    if ok else
                    "FAIL: see the untraced / all-Exception / relabelled / drift / mismatch rows above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
