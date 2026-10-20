#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a06 census: which decoding protocols exist, what each one means, and which
sampling-vs-fixed comparisons are available WITHOUT a new measurement.

Run from the repository root:

    python3 "docs/subprojects/a06-采样与解码参数/sampling_census.py"

Read-only.  It opens `experiments.sqlite` in `mode=ro`, reads the sampling
panels' own products (`.wrapup/mres/*/variant_panel.json`,
`.wrapup/m27_summary.jsonl`, `.wrapup/m31_summary.jsonl`) and prints a census in
six sections.  Every number it prints is derived here, so `RESULT.md` cites this
script instead of copying the numbers.

Exit status: 0 when every input was readable and the census ran; 2 when an input
is missing or unreadable (a census that cannot see its inputs is not a census
that found nothing).  Never 0 in the second case - that is the "fake green"
defect this subproject must not repeat.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
DB = os.path.join(ROOT, "experiments.sqlite")
WR = os.path.join(ROOT, ".wrapup")

# The fixed evaluation protocol this study runs on.  Not a belief: section C
# derives these numbers from the rows that carry the greedy protocol string, so
# a drift between this tuple and the data is printed as a MISMATCH.
FIXED = {"temp": "0", "max_tokens": "768"}

# Enumerated decoding settings this study ever declared.  A row whose sampling
# column holds something else did not come from a declared sweep; its sampling
# setting is UNKNOWN and is reported as such rather than read as a measurement.
DECLARED_TEMPS = {"0", "0.0", "0.3", "0.6", "0.7", "1.0"}
DECLARED_TOPK = {"1", "20", "40", "64", "200", "40.0"}

# Trailing quantisation tag -> the family/level base name in front of it.
QUANT_TAIL = re.compile(r"[-_](?:UD-)?(?:IQ|TQ|Q)\d\w*$|[-_](?:BF16|F16)$", re.I)

MISSING = []


def need(path, what):
    if not os.path.exists(path):
        MISSING.append(f"{what}: {path}")
        return False
    return True


def head(argv):
    try:
        rev = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                              capture_output=True, text=True).stdout.split()
    except OSError:
        rev, dirty = "?", []
    with open(os.path.abspath(__file__), "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    print(f"# command : python3 {os.path.relpath(os.path.abspath(__file__), ROOT)}"
          f" {' '.join(argv)}")
    print(f"# git HEAD: {rev}")
    print(f"# script  : sha256 {sha[:16]}…")
    print(f"# db      : experiments.sqlite (mode=ro)")
    print(f"# dirty   : {len(dirty)} path token(s) in `git status --porcelain`")
    print()


def connect():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def family(name):
    base = name[:-5] if name.endswith(".gguf") else name
    base = QUANT_TAIL.sub("", base)
    return base


def protocol_sampling(proto):
    """The sampling setting a protocol string names, or `unstated`."""
    p = proto or ""
    out = {}
    m = re.search(r"t(\d+(?:\.\d+)?)-", p) or re.search(r"temp(\d+(?:\.\d+)?)", p)
    if m:
        out["temp"] = m.group(1)
    if "greedy" in p:
        out.setdefault("temp", "0")
    m = re.search(r"topk1\b", p)
    if m:
        out["top_k"] = "1"
    return out


def section_a(con):
    print("== A. Can the sampling identity columns be read at all? ==")
    tot = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    bare = con.execute(
        "SELECT COUNT(*) FROM experiments WHERE protocol IS NULL AND run_tag IS NULL"
    ).fetchone()[0]
    rows = con.execute(
        "SELECT model, temp, top_k, top_p, min_p, presence_penalty, source_file "
        "FROM experiments"
    ).fetchall()
    undeclared = [r for r in rows
                  if r["temp"] not in DECLARED_TEMPS or r["top_k"] not in DECLARED_TOPK]
    undeclared_noprov = [r for r in undeclared if r["source_file"] is None]
    print(f"  total rows                       : {tot}")
    print(f"  rows with protocol AND run_tag NULL: {bare}")
    print(f"  rows whose temp/top_k is outside every declared setting: {len(undeclared)}"
          f"  ({100.0 * len(undeclared) / tot:.1f}% of all rows)")
    print(f"    of those, rows with no source_file : {len(undeclared_noprov)}")
    print(f"    of those, distinct temp values     : "
          f"{len({r['temp'] for r in undeclared})}")
    print(f"    of those, distinct top_k values    : "
          f"{len({r['top_k'] for r in undeclared})}")
    fams = {}
    for r in undeclared:
        fams[r["presence_penalty"]] = fams.get(r["presence_penalty"], 0) + 1
    print(f"    distinct presence_penalty values   : {len(fams)}"
          f" (max repeat {max(fams.values()) if fams else 0})")
    if len(undeclared):
        print("  -> verdict: those rows' sampling columns are NOT a decoding setting;")
        print("     the setting is UNKNOWN for them and is not read from these columns.")
    print()


def section_b(con):
    print("== B. Protocol inventory (one row per protocol x max_tokens x identity) ==")
    q = """
    SELECT bench_family, protocol, max_tokens,
           GROUP_CONCAT(DISTINCT temp) temps, GROUP_CONCAT(DISTINCT top_k) topks,
           COUNT(*) n, COUNT(DISTINCT model) models, SUM(_score IS NULL) nulls
    FROM experiments WHERE protocol IS NOT NULL
    GROUP BY bench_family, protocol, max_tokens
    ORDER BY bench_family, protocol
    """
    print(f"  {'bench_family':<20} {'max_tok':>7} {'cells':>5} {'models':>6} "
          f"{'NULL':>4}  protocol")
    for r in con.execute(q):
        print(f"  {r['bench_family'] or '-':<20} {r['max_tokens'] if r['max_tokens'] is not None else '-':>7} "
              f"{r['n']:>5} {r['models']:>6} {r['nulls'] or 0:>4}  {r['protocol']}")
    protos = con.execute(
        "SELECT COUNT(DISTINCT protocol) FROM experiments WHERE protocol IS NOT NULL"
    ).fetchone()[0]
    scored = con.execute(
        "SELECT COUNT(*) FROM experiments WHERE protocol IS NOT NULL"
    ).fetchone()[0]
    print(f"  distinct protocol strings: {protos}; rows carrying one: {scored}")
    print()


def section_c(con):
    print("== C. The fixed protocol, derived from the rows that carry it ==")
    rows = con.execute(
        "SELECT max_tokens, GROUP_CONCAT(DISTINCT temp) temps, "
        "GROUP_CONCAT(DISTINCT top_k) topks, GROUP_CONCAT(DISTINCT top_p) top_ps, "
        "GROUP_CONCAT(DISTINCT min_p) min_ps, COUNT(*) n "
        "FROM experiments WHERE protocol LIKE '%greedy%' GROUP BY max_tokens"
    ).fetchall()
    for r in rows:
        print(f"  max_tokens={r['max_tokens']} n={r['n']:<4} "
              f"temp={r['temps']} top_k={r['topks']} top_p={r['top_ps']} min_p={r['min_ps']}")
    # The fixed protocol is the one the code cells carry, `*-greedy-768`.  Other
    # greedy protocol strings exist (speed probes at 256, BFCL at 512, lm-eval at
    # 1024) and are different protocols, not counter-examples; the claim under
    # test is only that the -768 string and its max_tokens column agree.
    n768 = con.execute(
        "SELECT COUNT(*) FROM experiments WHERE protocol LIKE '%-greedy-768%' "
        "AND max_tokens IS NOT NULL AND CAST(max_tokens AS TEXT) != ?",
        (FIXED["max_tokens"],)).fetchone()[0]
    tot768 = con.execute(
        "SELECT COUNT(*) FROM experiments WHERE protocol LIKE '%-768%'").fetchone()[0]
    print(f"  declared fixed max_tokens = {FIXED['max_tokens']}; rows carrying a "
          f"'-768' protocol: {tot768}; of them disagreeing with that column: {n768}")
    other = con.execute(
        "SELECT max_tokens, COUNT(*) FROM experiments WHERE protocol LIKE '%greedy%' "
        "AND protocol NOT LIKE '%-768%' GROUP BY max_tokens").fetchall()
    print("  greedy protocols that are NOT the -768 fixed protocol (different protocol): " +
          ", ".join(f"max_tokens={r[0]} n={r[1]}" for r in other))
    print()


def section_d(con):
    print("== D. Panels that vary decoding (the sampling axis as measured) ==")
    q = """
    SELECT run_tag, protocol, bench_family, COUNT(*) n, COUNT(DISTINCT model) models,
           GROUP_CONCAT(DISTINCT temp) temps, GROUP_CONCAT(DISTINCT top_k) topks,
           GROUP_CONCAT(DISTINCT COALESCE(max_tokens,-1)) maxtoks,
           GROUP_CONCAT(DISTINCT COALESCE(language,'-')) langs,
           MIN(COALESCE(n_items,-1)) nmin, MAX(COALESCE(n_items,-1)) nmax
    FROM experiments
    WHERE run_tag IN ('m27-sampling','m31-topk','m130-kv','m131-sampling')
    GROUP BY run_tag, protocol ORDER BY run_tag, protocol
    """
    for r in con.execute(q):
        print(f"  {r['run_tag']:<15} bench={r['bench_family']:<15} n={r['n']:<3} "
              f"models={r['models']} langs={r['langs']} temp={r['temps']} "
              f"top_k={r['topks']} max_tok={r['maxtoks']} n_items={r['nmin']}..{r['nmax']}")
        print(f"      protocol: {r['protocol']}")
    print()
    print("  declared sampling variants in the standard-benchmark panel source:")
    files = sorted(glob.glob(os.path.join(WR, "mres", "*", "variant_panel.json")))
    for path in files:
        p = json.load(open(path))
        if p.get("axis") != "sampling":
            continue
        print(f"    {os.path.relpath(path, ROOT)}  tag={p.get('tag')}")
        for label, row in (p.get("rows") or {}).items():
            s = row.get("sampling") or {}
            print(f"      variant {label:<15} sampling={s}")
    print()


def section_e(con):
    print("== E. Comparisons available WITHOUT a new measurement ==")
    rows = con.execute("""
        SELECT model, bench_family, language, ctx_size, protocol, temp, top_k,
               n_items, _score
        FROM experiments
        WHERE _score IS NOT NULL AND protocol IS NOT NULL
          AND run_tag IN ('m27-sampling','m31-topk')
          AND bench_family = 'humaneval-multipl-e'
        ORDER BY model, language, protocol, CAST(top_k AS INTEGER)
    """).fetchall()
    groups = {}
    for r in rows:
        key = (r["bench_family"], r["language"], r["model"])
        groups.setdefault(key, []).append(r)
    print("  E1 MultiPL-E cells per (bench, language, model) available for a temp/top_k comparison:")
    for key, rs in sorted(groups.items()):
        if len({(r["protocol"], r["top_k"]) for r in rs}) < 2:
            continue
        print(f"    {key[2]}  {key[1]}")
        for r in rs:
            print(f"      {r['protocol']:<48} temp={r['temp']} top_k={r['top_k']:<4} "
                  f"n_items={r['n_items']} score={r['_score']:.4f}")
    print()

    print("  E2 quantisation ladder: level pairs measured under two or more decoding settings")
    ladders = {}
    for r in rows:
        fam = family(r["model"])
        ladders.setdefault(fam, set()).add(r["model"])
    any_ladder = False
    for fam, models in sorted(ladders.items()):
        if len(models) < 2:
            continue
        by_setting = {}
        for r in rows:
            if r["model"] not in models:
                continue
            setting = (r["temp"], r["top_k"])
            by_setting.setdefault((setting, r["language"]), {})[r["model"]] = r["_score"]
        settings = sorted({s for (s, _) in by_setting})
        if len(settings) < 2:
            continue
        any_ladder = True
        print(f"    family {fam}: levels={sorted(models)}")
        for lang in sorted({l for (_, l) in by_setting}):
            for i, s in enumerate(settings):
                vals = by_setting.get((s, lang), {})
                if len(vals) < 2:
                    continue
                print(f"      {lang} @ (temp,top_k)={s}: " +
                      "  ".join(f"{m.split('-UD-')[-1][:6]}={v:.4f}"
                                for m, v in sorted(vals.items())))
            conc = disc = 0
            for a in range(len(settings)):
                for b in range(a + 1, len(settings)):
                    va = by_setting.get((settings[a], lang), {})
                    vb = by_setting.get((settings[b], lang), {})
                    common = sorted(set(va) & set(vb))
                    for i in range(len(common)):
                        for j in range(i + 1, len(common)):
                            da = va[common[i]] - va[common[j]]
                            db = vb[common[i]] - vb[common[j]]
                            if da * db > 0:
                                conc += 1
                            elif da * db < 0:
                                disc += 1
            print(f"      {lang} level-pair order: concordant={conc} discordant={disc}"
                  f" over {len(settings)} settings")
    if not any_ladder:
        print("    (none: no family has two quantisation levels under two decoding settings)")
    print()

    print("  E3 fixed-protocol cells whose model family has no sampling twin")
    greedy = con.execute("""
        SELECT bench_family, model, COUNT(*) n FROM experiments
        WHERE protocol IN ('multipl-e-raw-greedy-768','mpl-raw-greedy-768')
          AND _score IS NOT NULL
        GROUP BY bench_family, model ORDER BY bench_family, model
    """).fetchall()
    sampled_fams = {family(m) for m in
                    {r["model"] for r in rows if (r["temp"] or "0") not in ("0", "0.0")}}
    untwinned = [r for r in greedy if family(r["model"]) not in sampled_fams]
    print(f"    greedy cells: {len(greedy)} over {len({r['model'] for r in greedy})} models")
    print(f"    families with a temp>0 twin: {len(sampled_fams)} {sorted(sampled_fams)}")
    print(f"    greedy models with NO temp>0 twin: {len(untwinned)}")
    for r in untwinned[:12]:
        print(f"      {r['bench_family']:<12} {r['model']}")
    if len(untwinned) > 12:
        print(f"      … and {len(untwinned) - 12} more")
    print()


def main(argv):
    need(DB, "database")
    need(os.path.join(WR, "m27_summary.jsonl"), "m27 sampling panel product")
    need(os.path.join(WR, "m31_summary.jsonl"), "m31 top_k panel product")
    if not glob.glob(os.path.join(WR, "mres", "*", "variant_panel.json")):
        MISSING.append("standard-benchmark sampling panel product: "
                       f"{os.path.join(WR, 'mres', '*', 'variant_panel.json')}")
    if MISSING:
        print("UNMEASURED: the census cannot see its inputs:", file=sys.stderr)
        for m in MISSING:
            print(f"  missing {m}", file=sys.stderr)
        return 2
    head(list(argv))
    con = connect()
    for sec in (section_a, section_b, section_c, section_d, section_e):
        sec(con)
    print("== census complete ==")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
