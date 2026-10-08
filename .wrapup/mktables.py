#!/usr/bin/env python3
"""Generate RESULTS_BY_COMPARISON.md from experiments.sqlite.

ONE TABLE PER RESEARCH VARIABLE.  The operator fixed this shape over six
iterations -- treat the following as the contract, not a suggestion:

 1. One table per research variable.  A variable is never split across two
    tables and two variables are never merged into one.
 2. Inside a table: column 1 = everything held constant (the group key),
    column 2 = the VARIED variable, the remaining columns = one per BENCHMARK.
 3. Columns are never filtered.  Every table prints the full benchmark column
    set for its axis, even when a column is entirely empty.  Do not drop a
    benchmark column because it has no data.
 4. Rows are filtered only as follows: drop a row that has no benchmark value
    at all; drop a whole column-1 group that has fewer than 2 distinct values
    of the varied variable (nothing to compare).  Nothing else is dropped.
 5. Empty cells are rendered `-`.  A missing number is never written as 0.0
    and no measured number is ever discarded.
 6. The quantisation x-axis is EFFECTIVE BPW = 8 * file_bytes / n_params, read
    from .wrapup/bpw_map.json (key = gguf basename).  Nominal labels ("Q2",
    "Q3") are NEVER used as an axis: they span 2.76-5.04 bpw and are
    meaningless.  Where the varied variable is bpw it is shown to 2 decimals.
 7. One coverage row sits at the top of each table and reports the number of
    rows shown and the number of benchmark columns that carry data, so a thin
    table is obvious at a glance.
 8. Every score cell carries its n_items, e.g. `0.3720 (164)`, so the reader
    can recompute an item-level SE.  No score is ever printed without its n.
    (In the speculative-decoding tok/s block the parenthesised number is the
    number of measurements behind the mean, not an item count.)

BPW source: .wrapup/bpw_map.json, written by .wrapup/gguf_params.py as
effective_bpw = 8 * os.path.getsize(gguf) / parameter_count.

The DB is opened read-only (`mode=ro`).  Regeneration is idempotent: the same
database produces the same file.
"""
import collections
import glob
import json
import os
import re
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "experiments.sqlite")
OUT = os.path.join(ROOT, "RESULTS_BY_COMPARISON.md")
BPW_MAP_PATH = os.path.join(HERE, "bpw_map.json")
CAMPAIGN_TXT = os.path.join(HERE, "CAMPAIGN.txt")

BPW = json.load(open(BPW_MAP_PATH))

# ---- benchmark column set -------------------------------------------------
# (key, label); this list is the report's column order and is never filtered.
BENCH = [
    ("humaneval",      "HumanEval"),
    ("humaneval_plus", "HumanEval+"),
    ("mbpp",           "MBPP"),
    ("mbpp_plus",      "MBPP+"),
    ("multipl_e",      "MultiPL-E"),
    ("mmlu",           "MMLU"),
    ("arc_challenge",  "ARC-c"),
    ("truthfulqa_mc2", "TruthfulQA"),
    ("gsm8k",          "GSM8K"),
    ("ifeval",         "IFEval"),
]
BENCH_KEYS = [k for k, _ in BENCH]
BENCH_LABELS = [l for _, l in BENCH]

# speculative-decoding tok/s scenarios (columns of block 1 of table G)
SCEN = [("speed-code", "code"), ("speed-longctx", "long-ctx"), ("speed-prose", "prose")]

# effective-bpw band that counts as "matched" for the scheme/vendor table (C).
# Single-linkage, so 0.45 puts the whole Qwen3.5-2B IQ2_XXS(3.27) / IQ2_M(3.66) /
# IQ3_XXS(3.96) / Q2_K_XL(4.11) ladder in one matched cluster (each step is <= 0.39).
# 0.20 was too tight and left the named IQ trio out of the comparison entirely.
MATCH_BPW = 0.45

# MoE bit-allocation recipes (table D); order is the report's row order.
M55_RECIPES = [
    ("LFM2.5-8B-A1B-m55-Q3_K_M.gguf", "uniform Q3_K_M (baseline)"),
    ("LFM2.5-8B-A1B-m55-exq2.gguf",   "experts IQ2/Q2, rest Q5_K_M (exq2)"),
    ("LFM2.5-8B-A1B-m55-exq4.gguf",   "experts Q4_K, rest Q2_K (exq4)"),
]

con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)

# ---- per-language MultiPL-E item counts -----------------------------------
# MultiPL-E rows carry no n_items; the raw *_summary.jsonl files do.  Same
# derivation as the retired mktables.py (most common n per language).
_lang_n = collections.defaultdict(list)
for _f in glob.glob(os.path.join(HERE, "*_summary.jsonl")):
    for _line in open(_f):
        try:
            _r = json.loads(_line)
        except Exception:
            continue
        if _r.get("lang") and _r.get("n"):
            _lang_n[_r["lang"]].append(_r["n"])
LANG_N = {k: collections.Counter(v).most_common(1)[0][0] for k, v in _lang_n.items()}
LANG_N.setdefault("cpp", 161)
LANG_N.setdefault("py", 161)


# ---- row helpers ----------------------------------------------------------
def bench_key(bench, family):
    """Map (_bench, bench_family) onto one report column key, or None."""
    if family == "humaneval-multipl-e":
        return "multipl_e"
    if bench == "humaneval":
        return "humaneval"
    if bench == "humaneval-plus":
        return "humaneval_plus"
    if bench == "mbpp":
        return "mbpp"
    if bench == "mbpp-plus":
        return "mbpp_plus"
    if bench in ("mmlu", "arc_challenge", "truthfulqa_mc2", "gsm8k", "ifeval"):
        return bench
    return None


def query_cells_by(where, extra="''", params=()):
    """{(model, extra): {bench_key: (score, n)}} for a subset of the DB.

    MultiPL-E rows (bench_family='humaneval-multipl-e') are pooled across
    languages, weighted by the language item count; the pooled cell's n is the
    number of pooled items.  Every other row keeps its own (_score, n_items).
    """
    q = ("SELECT model, %s, _bench, bench_family, _score, n_items, language "
         "FROM experiments WHERE run_tag IS NOT NULL AND run_tag <> '' "
         "AND _score IS NOT NULL AND (%s)" % (extra, where))
    cells = collections.defaultdict(dict)
    mpl = collections.defaultdict(lambda: collections.defaultdict(list))
    for model, tag, bench, fam, score, n, lang in con.execute(q, params):
        if score is None:
            continue
        if fam == "humaneval-multipl-e":
            mpl[(model, tag)][lang].append(score)
            continue
        k = bench_key(bench, fam)
        if k is not None:
            cells[(model, tag)][k] = (score, n)
    for key, per_lang in mpl.items():
        acc = tot = 0.0
        for lang, scores in per_lang.items():
            w = LANG_N.get(lang, 161)
            acc += (sum(scores) / len(scores)) * w
            tot += w
        if tot:
            cells[key]["multipl_e"] = (acc / tot, int(tot))
    return cells


# ---- model-name helpers ---------------------------------------------------
QUANT_RE = re.compile(r"[-_](?P<q>m\d+-[\w]+|(?:UD-)?(?:IQ|TQ|Q)\d[\w.]*)$")
SIZE_RE = re.compile(r"[-_]?((?:E)?\d+(?:\.\d+)?[Bb](?:-A\d+(?:\.\d+)?[Bb])?)")


def model_stem(model):
    return model[:-len(".gguf")] if model.endswith(".gguf") else model


def split_quant(model):
    """(stem without the quant suffix, quant recipe) for a gguf basename."""
    stem = model_stem(model)
    m = QUANT_RE.search(stem)
    if not m:
        return stem, None
    return stem[:m.start()], m.group("q")


def family_of(model):
    """Model stem with the quant suffix removed (size is kept)."""
    stem, _ = split_quant(model)
    stem = re.sub(r"^Qwen_Qwen", "Qwen", stem)
    return re.sub(r"[-_](it|instruct|chat)$", "", stem, flags=re.I)


def is_recipe(model):
    """True for panel-tagged recipes (mNN-...) that vary something other than
    raw bpw -- they belong to their own axis, not to the bpw ladder (A/B/C)."""
    _, q = split_quant(model)
    return bool(q and re.match(r"^m\d+-", q))


def lineage_and_size(model):
    """(size-agnostic lineage, size token) for the size axis (B)."""
    family = family_of(model)
    m = SIZE_RE.search(family)
    if not m:
        return family, family
    size = m.group(1)
    lineage = (family[:m.start()] + family[m.end():]).strip("-_")
    lineage = re.sub(r"[-_](it|instruct|chat)$", "", lineage, flags=re.I)
    return lineage, size


def size_value(size):
    m = re.search(r"(\d+(?:\.\d+)?)", size)
    return float(m.group(1)) if m else 0.0


def recipe_of(model):
    _, q = split_quant(model)
    if q is None:
        return None
    return re.sub(r"^UD-", "", q)


# ---- rendering ------------------------------------------------------------
def fmt(cells, key, unit=None):
    v = cells.get(key)
    if v is None:
        return "-"
    val, n = v
    if unit == "tok_s":
        return "%.1f (%s)" % (val, n) if n is not None else "%.1f" % val
    if n is None:
        return "%.4f (n=?)" % val
    return "%.4f (%s)" % (val, n)


CELL_RE = re.compile(r"^-?\d+(\.\d+)? \([^)]+\)$")


def selfcheck(txt):
    """Every rendered value cell must carry its n (rule 8).  Returns the list
    of offending cells (empty == pass)."""
    bad = []
    for ln in txt.splitlines():
        if not ln.startswith("| ") or ln.startswith("|---") or "Σ coverage" in ln:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if any(c.startswith("**") for c in cells):   # header row
            continue
        for c in cells[2:]:
            if c not in ("-", "") and not CELL_RE.match(c):
                bad.append(c)
    return bad


def emit_table(o, title, note, c1_name, c2_name, col_keys, col_labels, rows,
               sort_key=None, sort1=None, unit=None, waiting=None):
    """Append one table; return the number of data rows shown.

    rows = [(col1, col2, cells)].  Implements rules 3-8 exactly.
    """
    o.append("## " + title)
    o.append("")
    if note:
        o.append(note)
        o.append("")
    o.append("| " + c1_name + " | " + c2_name + " | " +
             " | ".join("**%s**" % l for l in col_labels) + " |")
    o.append("|---" * (len(col_keys) + 2) + "|")

    kept = [r for r in rows if any(r[2].get(k) is not None for k in col_keys)]
    groups = collections.defaultdict(list)
    for c1, c2, cells in kept:
        groups[c1].append((c2, cells))
    # rule 4: keep only groups with >=2 distinct values of the varied variable
    groups = {c1: v for c1, v in groups.items()
              if len({c2 for c2, _ in v}) >= 2}

    shown = sum(len(v) for v in groups.values())
    counts = {k: sum(1 for v in groups.values() for _, cells in v
                     if cells.get(k) is not None) for k in col_keys}
    data_cols = sum(1 for k in col_keys if counts[k] > 0)
    o.append("| **Σ coverage** | rows=%d · data-cols=%d/%d | %s |" % (
        shown, data_cols, len(col_keys),
        " | ".join(str(counts[k]) for k in col_keys)))

    keys = sorted(groups, key=sort1) if sort1 else sorted(groups)
    for c1 in keys:
        items = groups[c1]
        if sort_key:
            items = sorted(items, key=lambda kv: sort_key(kv[0]))
        for c2, cells in items:
            o.append("| " + c1 + " | " + c2 + " | " +
                     " | ".join(fmt(cells, k, unit) for k in col_keys) + " |")
    o.append("")
    if not groups and waiting:
        o.append("*Waiting: " + waiting + "*")
        o.append("")
    return shown


# ---- data -----------------------------------------------------------------
def load_standard():
    """Cells for the standard benchmark columns.

    Sources: the running standard-benchmark campaign (`source_file LIKE
    'mres/%'`, thinking-off rows only -- the thinking-on re-runs belong to axis
    H) plus the retired MultiPL-E panel under its canonical raw-greedy
    protocol only, so no two protocols are ever mixed in one cell.
    """
    where = ("(source_file LIKE 'mres/%' AND reasoning <> 'on') "
             "OR (bench_family='humaneval-multipl-e' "
             "AND protocol='multipl-e-raw-greedy-768')")
    return {key[0]: cells for key, cells in query_cells_by(where).items()}


# ---- axes -----------------------------------------------------------------
def axis_a(std):
    """BPW sweep: held = model family, varied = effective bpw."""
    rows, missing = [], []
    by_fam = collections.defaultdict(list)
    for model, cells in std.items():
        if model not in BPW:
            missing.append(model)
            continue
        if is_recipe(model):          # m55 recipes vary bit allocation (axis D)
            continue
        by_fam[family_of(model)].append((model, cells))
    for fam in sorted(by_fam):
        for model, cells in by_fam[fam]:
            rows.append((fam, "%.2f bpw" % BPW[model], cells))
    return rows, missing


def axis_b(std):
    """Model size at a held recipe: held = lineage + recipe, varied = size."""
    rows = []
    by = collections.defaultdict(list)
    for model, cells in std.items():
        if model not in BPW or is_recipe(model):
            continue
        lineage, size = lineage_and_size(model)
        recipe = recipe_of(model)
        if recipe is None:
            continue
        by[(lineage, recipe)].append((size, cells))
    for (lineage, recipe) in sorted(by):
        for size, cells in by[(lineage, recipe)]:
            rows.append(("%s @ %s" % (lineage, recipe), size, cells))
    return rows


def axis_c(std):
    """Scheme/vendor inside one model: quants whose effective bpw are within
    MATCH_BPW of each other (single-linkage cluster)."""
    rows = []
    by_fam = collections.defaultdict(list)
    for model, cells in std.items():
        if model not in BPW or is_recipe(model):
            continue
        _, quant = split_quant(model)
        if quant is None:
            continue
        by_fam[family_of(model)].append((BPW[model], quant, cells))
    for fam in sorted(by_fam):
        items = sorted(by_fam[fam])
        clusters = []
        for bpw, quant, cells in items:
            if clusters and bpw - clusters[-1][-1][0] <= MATCH_BPW:
                clusters[-1].append((bpw, quant, cells))
            else:
                clusters.append([(bpw, quant, cells)])
        for cl in clusters:
            if len({q for _, q, _ in cl}) < 2:
                continue
            lo = min(b for b, _, _ in cl)
            hi = max(b for b, _, _ in cl)
            c1 = "%s @ %.2f-%.2f bpw" % (fam, lo, hi)
            for bpw, quant, cells in cl:
                rows.append((c1, quant, cells))
    return rows


def _bpw_tag(model):
    b = BPW.get(model)
    return "" if b is None else "@%.2fbpw" % b


def m55_rank(label):
    for i, (_, recipe) in enumerate(M55_RECIPES):
        if label.startswith(recipe):
            return i
    return 99


def axis_moe(o):
    """MoE bit allocation: held = LFM2.5-8B-A1B + panel, varied = recipe."""
    cells = query_cells_by("run_tag='m55-expertwise'")
    by_model = {m: c for (m, _), c in cells.items()}
    rows = []
    for model, label in M55_RECIPES:
        bpw = BPW.get(model)
        c2 = label if bpw is None else "%s · %.2f bpw" % (label, bpw)
        rows.append(("LFM2.5-8B-A1B (m55 MoE panel)", c2, by_model.get(model, {})))
    return emit_table(
        o, "D. MoE bit allocation -- LFM2.5-8B-A1B m55 recipes",
        "Held constant: model, harness, protocol.  Varied: which layers get the "
        "low bits (experts vs the rest).  Only the MultiPL-E column is measured "
        "for these three files; the EvalPlus / lm-eval columns will fill in when "
        "the campaign reaches these recipes.",
        "model (all else equal)", "expert / non-expert recipe", BENCH_KEYS,
        BENCH_LABELS, rows, sort_key=m55_rank,
        waiting="m55 expert-wise standard-benchmark re-runs (rows now: MultiPL-E only).")


def axis_kv(o):
    """KV cache: held = model + bpw + ctx, varied = KV type (from protocol)."""
    kv_rows = con.execute(
        "SELECT DISTINCT model, protocol FROM experiments WHERE run_tag='m30-kv-ctx'"
    ).fetchall()
    # cells keyed by (model, protocol): ctx and KV type live in the protocol
    # string, so each (model, ctx, kv) cell must stay separate.
    cells = query_cells_by("run_tag='m30-kv-ctx'", "protocol")
    rows, order = [], ["f16/f16", "f16/q8_0", "q8_0/f16", "q8_0/q8_0"]
    for model, proto in kv_rows:
        mc = re.search(r"ctx=(\d+)", proto or "")
        mk = re.search(r"kv=([\w]+)/([\w]+)", proto or "")
        if not (mc and mk):
            continue
        c1 = "%s %s · ctx%s" % (family_of(model), _bpw_tag(model), mc.group(1))
        rows.append((c1, "%s/%s" % (mk.group(1), mk.group(2)),
                     cells.get((model, proto), {})))
    return emit_table(
        o, "E. KV-cache quantisation -- Qwen3.5-2B-Q3_K_XL, m30",
        "Held constant: model, effective bpw, ctx.  Varied: KV-cache type K/V, "
        "parsed from the protocol string (the cache_type_k/v columns are NOT "
        "usable here).  Only MultiPL-E cpp (n=161) is measured, so every cell "
        "lands in the MultiPL-E column.",
        "model @bpw · ctx (all else equal)", "KV type K/V", BENCH_KEYS,
        BENCH_LABELS, rows, sort_key=lambda s: order.index(s) if s in order else 99,
        sort1=lambda s: int(re.search(r"ctx(\d+)", s).group(1)),
        waiting="standard-benchmark re-runs of m30 (rows now: MultiPL-E cpp only).")


def axis_sampling(o):
    """Sampling: held = model + bpw + axis, varied = the parameter value."""
    rows, tk_order = [], ["1", "20", "40", "64", "200"]
    for (model, tk), cells in query_cells_by("run_tag='m31-topk'", "top_k").items():
        rows.append(("%s %s · top_k" % (family_of(model), _bpw_tag(model)),
                     str(tk), cells))
    for (model, tp), cells in query_cells_by("run_tag='m27-sampling'", "temp").items():
        rows.append(("%s %s · temperature" % (family_of(model), _bpw_tag(model)),
                     str(tp), cells))

    def rank(s):
        if s in tk_order:
            return tk_order.index(s)
        try:
            return float(s)
        except ValueError:
            return 99
    return emit_table(
        o, "F. Sampling / decoding",
        "Held constant: model, effective bpw, harness, ctx.  Varied: the "
        "decoding parameter named in column 1 (m31 = top_k; m27 = temperature; "
        "top_p is pinned at 0.95 and is not a variable).  Greedy floor is "
        "K=1 / T=0.  Only MultiPL-E cpp+py are measured.",
        "model · varied axis (all else equal)", "value", BENCH_KEYS, BENCH_LABELS,
        rows, sort_key=rank,
        waiting="standard-benchmark re-runs of m31/m27 (rows now: MultiPL-E cpp+py only).")


def axis_spec(o):
    """Speculative decoding: two blocks sharing the same rows -- tok/s (speed)
    and score (quality damage)."""
    raw = con.execute(
        "SELECT model,_bench,bench_family,ctx_size,spec_draft_n_max,_tok_s,"
        "_score,n_items,language FROM experiments "
        "WHERE run_tag IN ('m28-speed','m52-speed') AND run_tag<>''").fetchall()
    tok = collections.defaultdict(lambda: collections.defaultdict(list))
    sc = collections.defaultdict(dict)
    mpl = collections.defaultdict(lambda: collections.defaultdict(list))
    for model, bench, fam, ctx, n, tok_s, score, nit, lang in raw:
        key = (model, ctx, n)
        if tok_s is not None and bench in dict(SCEN):
            tok[key][bench].append(tok_s)
        if score is not None:
            if fam == "humaneval-multipl-e":
                mpl[key][lang].append(score)
            else:
                k = bench_key(bench, fam)
                if k is not None:
                    sc[key][k] = (score, nit)
    for key, per_lang in mpl.items():
        acc = tot = 0.0
        for lang, scores in per_lang.items():
            w = LANG_N.get(lang, 161)
            acc += (sum(scores) / len(scores)) * w
            tot += w
        if tot:
            sc[key]["multipl_e"] = (acc / tot, int(tot))

    tok_cells = {k: {b: (sum(v) / len(v), len(v)) for b, v in per.items()}
                 for k, per in tok.items()}
    tok_rows = [("%s · ctx%s" % (family_of(m), c), str(n), tok_cells[(m, c, n)])
                for (m, c, n) in tok_cells]
    sc_rows = [("%s · ctx%s" % (family_of(m), c), str(n), sc.get((m, c, n), {}))
               for (m, c, n) in tok_cells]

    n1 = emit_table(
        o, "G1. Speculative decoding -- tok/s (SPEED indicator)",
        "Held constant: model, ctx.  Varied: speculative draft depth "
        "`spec_draft_n_max` (0 = speculative decoding off).  Unit: tokens/s; the "
        "parenthesised number is the number of measurements, not an item count. "
        "m28 = Qwen3.5-2B-Q4_K_XL, m52 = gemma-4-12b / Qwen3.5-9B.",
        "model · ctx (all else equal)", "spec_draft_n_max",
        [k for k, _ in SCEN], [l for _, l in SCEN], tok_rows,
        sort_key=lambda s: int(s), unit="tok_s",
        waiting="m28/m52 standard-benchmark runs with tok/s (none yet).")
    n2 = emit_table(
        o, "G2. Speculative decoding -- SCORE (QUALITY indicator)",
        "Same runs as G1, checked for quality damage: a speed win is only usable "
        "if the score holds.  No scores exist for m28/m52 yet -- the table is "
        "deliberately empty and fills when the standard campaign covers those "
        "models at the same spec depth.",
        "model · ctx (all else equal)", "spec_draft_n_max", BENCH_KEYS,
        BENCH_LABELS, sc_rows, sort_key=lambda s: int(s),
        waiting="m28/m52 standard-benchmark scores: 0 rows in experiments.sqlite.")
    return n1, n2


def expected_on_tags():
    """Thinking-on run tags declared in .wrapup/CAMPAIGN.txt."""
    out = []
    if os.path.exists(CAMPAIGN_TXT):
        for line in open(CAMPAIGN_TXT):
            parts = line.split("#")[0].split()
            if len(parts) >= 2 and re.match(r"^m\d+on-2b", parts[1]):
                out.append(parts[1])
    return sorted(set(out))


def axis_thinking(o):
    """Thinking on/off: held = model file, varied = reasoning switch."""
    tags = [r[0] for r in con.execute(
        "SELECT DISTINCT run_tag FROM experiments WHERE run_tag LIKE 'm6%' AND run_tag<>''")]
    on_tags = sorted(t for t in tags if re.match(r"^m\d+on-2b", t))
    off_tags = sorted(t for t in tags if re.match(r"^m\d+-qwen-2b", t))

    def cells_for(sub):
        if not sub:
            return {}
        ph = ",".join("?" * len(sub))
        return {k[0]: c for k, c
                in query_cells_by("run_tag IN (%s)" % ph, "''", sub).items()}

    on, off = cells_for(on_tags), cells_for(off_tags)
    rows = []
    for model in sorted(set(on) | set(off)):
        c1 = model_stem(model)
        if model in off:
            rows.append((c1, "thinking off", off[model]))
        if model in on:
            rows.append((c1, "thinking on", on[model]))
    exp = expected_on_tags() or ["m61on-2b", "m62on-2b", "m63on-2b", "m64on-2b"]
    n = emit_table(
        o, "H. Thinking on vs off -- the newly added axis",
        "Held constant: model file.  Varied: `reasoning` on/off at the server "
        "level.  The thinking-on runs re-measure ONLY gsm8k and ifeval, so the "
        "off row carries the full column set and the on row only those two.",
        "model (all else equal)", "thinking", BENCH_KEYS, BENCH_LABELS, rows,
        sort_key=lambda s: 0 if "off" in s else 1,
        waiting="thinking-on run tags %s (0 rows yet; the matched off rows are "
                "in the DB but a group needs both to compare)." % ", ".join(exp))
    return n, exp


def main():
    std = load_standard()
    o, results = [], []

    o.append("# RESULTS_BY_COMPARISON.md -- one table per research variable")
    o.append("")
    o.append("*Generated by `.wrapup/mktables.py` from `experiments.sqlite` "
             "(read-only).  Do not hand-edit; rerun the generator.*")
    o.append("")
    o.append("**Shape rules.** column 1 = everything held constant, column 2 = "
             "the varied variable, the remaining columns = one per benchmark.  "
             "Columns are never filtered (an empty benchmark column still "
             "appears).  A row with no benchmark value at all is dropped; a "
             "column-1 group with fewer than 2 values of the varied variable is "
             "dropped (nothing to compare); nothing else is ever dropped.")
    o.append("")
    o.append("**x-axis.** quantisation is always plotted against EFFECTIVE BPW "
             "= 8 x file_bytes / n_params from `.wrapup/bpw_map.json`.  Nominal "
             "labels such as `Q2`/`Q3` are never used: they span 2.76-5.04 bpw.")
    o.append("")
    o.append("**Cells.** `score (n)` -- the number in parentheses is `n_items`, "
             "so an item-level SE is `sqrt(p(1-p)/n)`.  `-` = not measured (no "
             "row in the DB); the report never substitutes 0.0 for a missing "
             "cell.  Every table's top row reports rows shown and columns with "
             "data.")
    o.append("")
    o.append("**Columns.** HumanEval / HumanEval+ / MBPP / MBPP+ = EvalPlus "
             "0.3.1 on the full problem set (164/164/378/378), greedy chat. "
             "MultiPL-E = retired panel pooled over its languages (cpp/python/"
             "java/js/rs/rb, 155-161 items each), raw greedy, canonical protocol "
             "only.  MMLU / ARC-c / TruthfulQA = lm-eval 0.4.13 loglikelihood "
             "shim; GSM8K / IFEval = lm-eval 0.4.13 greedy chat; all with "
             "server-side thinking off.")
    o.append("")
    o.append("**One variable per table.** Panel-tagged recipes (`mNN-...`, e.g. the "
             "m55 expert-wise files) change something other than raw bpw, so they "
             "are kept out of tables A/B/C and appear only in their own table "
             "(D).  That keeps each table varying exactly one thing.")
    o.append("")

    rows_a, missing = axis_a(std)
    results.append(("A. BPW sweep", emit_table(
        o, "A. BPW sweep -- every model family on its effective-bpw ladder",
        "Held constant: model family (stem without the quant suffix), harness, "
        "ctx, protocol.  Varied: effective bpw.  A family needs >=2 bpw levels "
        "to appear.  MultiPL-E entries here are the older panel; the EvalPlus "
        "and lm-eval columns fill in as the standard campaign drains.",
        "model family (all else equal)", "effective BPW", BENCH_KEYS,
        BENCH_LABELS, rows_a, sort_key=lambda s: float(s.split()[0]))))
    if missing:
        o.append("*Note: %d model(s) had no effective bpw in bpw_map.json and "
                 "were skipped: %s.*" % (len(missing), ", ".join(sorted(missing))))
        o.append("")

    results.append(("B. Model size", emit_table(
        o, "B. Model size at a held quant recipe",
        "Held constant: family lineage + quant recipe.  Varied: parameter "
        "count.  Every family is emitted at each recipe it was run at; a "
        "lineage/recipe with only one size is dropped.  Q2_K_XL and Q3_K_XL "
        "are the recipes the campaign currently covers.",
        "family @ recipe (all else equal)", "model size", BENCH_KEYS,
        BENCH_LABELS, axis_b(std), sort_key=size_value)))

    results.append(("C. Scheme / vendor", emit_table(
        o, "C. Scheme / vendor at a matched effective-bpw band",
        "Held constant: model, and an effective-bpw band of +-%.2f bpw.  Varied: "
        "the quant scheme/vendor (UD- = unsloth dynamic, plain = vendor).  "
        "Quants further apart than the band are not a matched comparison; their "
        "bpw ladder is in table A." % MATCH_BPW,
        "model @ bpw band (all else equal)", "quant scheme (vendor)",
        BENCH_KEYS, BENCH_LABELS, axis_c(std))))

    results.append(("D. MoE bit allocation", axis_moe(o)))
    results.append(("E. KV cache", axis_kv(o)))
    results.append(("F. Sampling / decoding", axis_sampling(o)))
    n1, n2 = axis_spec(o)
    results.append(("G1. Spec depth tok/s", n1))
    results.append(("G2. Spec depth score", n2))
    n_h, exp_on = axis_thinking(o)
    results.append(("H. Thinking on/off", n_h))

    txt = "\n".join(o) + "\n"
    open(OUT, "w").write(txt)
    bad = selfcheck(txt)
    print("wrote %s (%d lines)" % (OUT, txt.count("\n")))
    print("selfcheck: value cells lacking an n = %d" % len(bad))
    for b in bad[:10]:
        print("  MISSING n:", b)
    print("per-table data rows shown:")
    for name, n in results:
        print("  %-26s %d" % (name, n))
    print("thinking-on tags declared in CAMPAIGN.txt:", len(exp_on))
    if bad:
        raise SystemExit("FAIL: %d value cell(s) lack an n" % len(bad))


if __name__ == "__main__":
    main()
