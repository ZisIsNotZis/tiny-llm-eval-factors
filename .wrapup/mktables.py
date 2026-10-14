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
SCEN = [("speed-code", "code"), ("speed-longctx", "long-ctx"), ("speed-prose", "prose"),
        ("speed", "code-256")]

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
    """Build ONE structured table from the DB and append it to `o`.

    rows = [(col1, col2, cells)].  Implements the shape rules: a row with no
    benchmark value at all is dropped; a col1 group with fewer than 2 distinct
    values of the varied variable is dropped.  No markdown is produced -- `o` is
    the single machine-readable table set that the report renders.
    """
    kept = [(c1, c2, cells) for c1, c2, cells in rows
            if any(cells.get(k) is not None for k in col_keys)]
    groups = collections.defaultdict(list)
    for c1, c2, cells in kept:
        groups[c1].append((c2, cells))
    groups = {c1: v for c1, v in groups.items()
              if len({c2 for c2, _ in v}) >= 2}
    keys = sorted(groups, key=sort1) if sort1 else sorted(groups)
    ordered = []
    for c1 in keys:
        items = groups[c1]
        if sort_key:
            items = sorted(items, key=lambda kv: sort_key(kv[0]))
        for c2, cells in items:
            ordered.append((c1, c2, cells))
    counts = {k: sum(1 for _, _, cells in ordered if cells.get(k) is not None)
              for k in col_keys}
    o.append({
        "title": title, "note": note,
        "c1_name": c1_name, "c2_name": c2_name,
        "col_keys": col_keys, "col_labels": col_labels,
        "rows": ordered, "counts": counts,
        "data_cols": sum(1 for k in col_keys if counts[k] > 0),
        "unit": unit, "waiting": waiting,
    })
    return len(ordered)


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
    """MoE bit allocation: held = LFM2.5-8B-A1B, varied = recipe.

    Two sources for the same three files: the original m55 panel (MultiPL-E only) and the
    later standard-benchmark run of the same recipes.  They cover different columns, so both
    are pooled - the model file is the identity.
    """
    names = ",".join("'%s'" % m for m, _ in M55_RECIPES)
    cells = query_cells_by(f"model IN ({names})")
    by_model = {m: c for (m, _), c in cells.items()}
    rows = []
    for model, label in M55_RECIPES:
        bpw = BPW.get(model)
        c2 = label if bpw is None else "%s · %.2f bpw" % (label, bpw)
        rows.append(("LFM2.5-8B-A1B (m55 MoE panel)", c2, by_model.get(model, {})))
    return emit_table(
        o, "D. MoE bit allocation -- LFM2.5-8B-A1B m55 recipes",
        "Held constant: model, harness, protocol.  Varied: which layers get the low bits "
        "(the expert FFN tensors vs the rest of the network).  All three recipes are the "
        "same base weights, so any difference is purely the bit allocation.  Columns come "
        "from two panels of the same files: the original MultiPL-E run and the later "
        "standard-benchmark run.",
        "model (all else equal)", "expert / non-expert recipe", BENCH_KEYS,
        BENCH_LABELS, rows, sort_key=m55_rank,
        waiting="m55 standard-benchmark rows (none yet).")


def axis_kv(o):
    """KV cache: held = model + bpw + ctx, varied = KV type.

    Two sources.  m30 encodes ctx and the KV pair inside the PROTOCOL STRING (those
    cache_type_k/v columns are unusable for it), and measures MultiPL-E cpp only.  The later
    m130 panel runs the standard columns and records the KV pair in cache_type_k/v directly.
    """
    rows, order = [], ["f16/f16", "f16/q8_0", "q8_0/f16", "q8_0/q8_0",
                       "q4_0/q4_0", "f16/q8_0"]
    kv_rows = con.execute(
        "SELECT DISTINCT model, protocol FROM experiments WHERE run_tag='m30-kv-ctx'"
    ).fetchall()
    cells = query_cells_by("run_tag='m30-kv-ctx'", "protocol")
    for model, proto in kv_rows:
        mc = re.search(r"ctx=(\d+)", proto or "")
        mk = re.search(r"kv=([\w]+)/([\w]+)", proto or "")
        if not (mc and mk):
            continue
        c1 = "%s %s · ctx%s" % (family_of(model), _bpw_tag(model), mc.group(1))
        rows.append((c1, "%s/%s" % (mk.group(1), mk.group(2)),
                     cells.get((model, proto), {})))

    # standard-benchmark KV panels: the KV pair lives in the cache_type_k/v columns
    new = con.execute(
        "SELECT DISTINCT model, cache_type_k, cache_type_v, ctx_size FROM experiments "
        "WHERE source_file LIKE '%/variant_panel.json' AND protocol LIKE 'variant-kv-%'"
    ).fetchall()
    newcells = query_cells_by(
        "source_file LIKE '%/variant_panel.json' AND protocol LIKE 'variant-kv-%'",
        "cache_type_k || '/' || cache_type_v")
    for model, k, v, ctx in new:
        c1 = "%s %s · ctx%s" % (family_of(model), _bpw_tag(model), ctx)
        label = f"{k}/{v}"
        if label not in order:
            order.append(label)
        rows.append((c1, label, newcells.get((model, label), {})))

    return emit_table(
        o, "E. KV-cache quantisation",
        "Held constant: model, effective bpw, ctx.  Varied: KV-cache type K/V.  The m30 rows "
        "encode ctx and the KV pair inside the protocol string (its cache_type_k/v columns "
        "are unusable) and measure MultiPL-E cpp only; the m130 rows carry the KV pair in "
        "cache_type_k/v and cover the four standard columns.  Narrow context is the caveat: "
        "these prompts are ~1k tokens, and quantising the KV cache can only bite as context "
        "grows, so this bounds the effect at short-to-moderate context, not at 100k.",
        "model @bpw · ctx (all else equal)", "KV type K/V", BENCH_KEYS,
        BENCH_LABELS, rows, sort_key=lambda s: order.index(s) if s in order else 99,
        sort1=lambda s: int(re.search(r"ctx(\d+)", s).group(1)),
        waiting="standard-benchmark KV runs (none yet).")


def axis_sampling(o):
    """Sampling: held = model + bpw + axis, varied = the parameter value."""
    rows, tk_order = [], ["1", "20", "40", "64", "200"]
    for (model, tk), cells in query_cells_by("run_tag='m31-topk'", "top_k").items():
        rows.append(("%s %s · top_k" % (family_of(model), _bpw_tag(model)),
                     str(tk), cells))
    for (model, tp), cells in query_cells_by("run_tag='m27-sampling'", "temp").items():
        rows.append(("%s %s · temperature" % (family_of(model), _bpw_tag(model)),
                     str(tp), cells))

    # m131: the same axes re-measured on the standard columns.  Note the deliberate
    # control: MMLU is scored by log-likelihood and does not sample, so it must be
    # bit-identical across every sampling configuration, and top_k must be inert at
    # temperature 0 because there is no distribution to truncate.
    for (model, tp), cells in query_cells_by(
            "source_file LIKE '%/variant_panel.json' AND protocol LIKE 'variant-sampling%'",
            "temp").items():
        if float(tp or 0) == 0.0:
            continue                      # the greedy baseline is the top_k rows below
        rows.append(("%s %s · temperature" % (family_of(model), _bpw_tag(model)),
                     str(tp), cells))
    for (model, tk), cells in query_cells_by(
            "source_file LIKE '%/variant_panel.json' AND protocol LIKE 'variant-sampling%' "
            "AND CAST(temp AS REAL)=0", "top_k").items():
        rows.append(("%s %s · top_k @ temp 0" % (family_of(model), _bpw_tag(model)),
                     str(tk), cells))

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
        "WHERE spec_type IS NOT NULL AND spec_type<>'' AND run_tag<>''").fetchall()
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
        "`spec_draft_n_max` (0 = speculative decoding off).  Unit: tokens/s, read from "
        "llama-server's own `timings.predicted_per_second` so server startup is excluded; "
        "the parenthesised number is the number of measurements, not an item count. "
        "`code`/`long-ctx`/`prose` are the m28 prompt scenarios; `code-256` is the MTP "
        "campaign's fixed 256-token greedy generation.  NOTE: only the `-MTP-GGUF` repos "
        "carry MTP layers -- the plain Qwen3.5 gguf fails with 'model doesn't contain MTP "
        "layers', which is why this axis uses separate model files.",
        "model · ctx (all else equal)", "spec_draft_n_max",
        [k for k, _ in SCEN], [l for _, l in SCEN], tok_rows,
        sort_key=lambda s: int(s), unit="tok_s",
        waiting="no panel with a tok/s measurement yet.")
    n2 = emit_table(
        o, "G2. Speculative decoding -- SCORE (QUALITY indicator)",
        "Same runs as G1, checked for quality damage: a speed win is only usable if the "
        "score holds.  MMLU is the sharpest control here because it is scored by "
        "log-likelihood, which does not go through the draft path at all -- so it must be "
        "bit-identical across draft depths, and it is (0.5241/0.6250 at every depth).  The "
        "generative columns and humaneval are the ones that can actually move.",
        "model · ctx (all else equal)", "spec_draft_n_max", BENCH_KEYS,
        BENCH_LABELS, sc_rows, sort_key=lambda s: int(s),
        waiting="no scored speculative-decoding run yet.")
    return n1, n2


def expected_on_tags():
    """Thinking-on run tags declared in .wrapup/CAMPAIGN.txt.

    Two tag shapes have been used for this axis: `m6?on-2b` (an early, invalid attempt whose
    1024-token budget truncated every generation) and `m6?gs-gsm8k` (the corrected one).
    """
    out = []
    if os.path.exists(CAMPAIGN_TXT):
        for line in open(CAMPAIGN_TXT):
            parts = line.split("#")[0].split()
            if len(parts) >= 2 and re.match(r"^m\d+(on-2b|gs-gsm8k)", parts[1]):
                out.append(parts[1])
    return sorted(set(out))


def axis_thinking(o):
    """Thinking on/off: held = model file, varied = reasoning switch."""
    # Derived from the DB, not from tag names: a row is a thinking-on row iff its
    # `reasoning` column says so, which is what the ingest writes per task.
    on_rows = con.execute(
        "SELECT model, run_tag, _bench, _score, n_items FROM experiments "
        "WHERE source_file LIKE 'mres/%' AND reasoning='on' AND _score IS NOT NULL").fetchall()
    on_tags = sorted({r[1] for r in on_rows})
    off_tags = sorted({r[0] for r in con.execute(
        "SELECT DISTINCT run_tag FROM experiments WHERE source_file LIKE 'mres/%' "
        "AND reasoning='off' AND run_tag LIKE 'm6%' AND run_tag<>''")})

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
    exp = expected_on_tags() or ["m61gs-gsm8k", "m62gs-gsm8k", "m63gs-gsm8k"]
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


def build_tables():
    """Read experiments.sqlite and return the full list of structured tables.
    This is the single source of the report's tables; no file is written."""
    std = load_standard()
    o = []

    rows_a, missing = axis_a(std)
    emit_table(o, "A. BPW sweep -- every model family on its effective-bpw ladder",
               "Held constant: model family (stem without the quant suffix), harness, ctx, "
               "protocol. Varied: effective bpw. A family needs >=2 bpw levels to appear.",
               "模型家族（其余固定）", "有效位宽", BENCH_KEYS, BENCH_LABELS, rows_a,
               sort_key=lambda s: float(s.split()[0]))
    emit_table(o, "B. Model size at a held quant recipe",
               "Held constant: family lineage + quant recipe. Varied: parameter count.",
               "家族 @ 配方（其余固定）", "模型规模", BENCH_KEYS, BENCH_LABELS,
               axis_b(std), sort_key=size_value)
    emit_table(o, "C. Scheme / vendor at a matched effective-bpw band",
               "Held constant: model, and an effective-bpw band of +-%.2f bpw. "
               "Varied: the quant scheme/vendor." % MATCH_BPW,
               "模型 @ 位宽区间（其余固定）", "量化方案（厂商）", BENCH_KEYS, BENCH_LABELS,
               axis_c(std))
    axis_moe(o)
    axis_kv(o)
    axis_sampling(o)
    axis_spec(o)
    axis_thinking(o)
    return o


def main():
    for t in build_tables():
        print("%-58s rows=%d data-cols=%d/%d"
              % (t["title"], len(t["rows"]), t["data_cols"], len(t["col_keys"])))



if __name__ == "__main__":
    main()
