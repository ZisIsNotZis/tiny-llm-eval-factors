#!/usr/bin/env python3
"""DB schema upgrade + ingestion of the wrap-up run data.

Why the schema must change
--------------------------
The original unique index `uq_experiments_args_bench` covers every decoding
factor, so two runs of *the same* configuration are impossible. That is exactly
why the study had zero replicates. Replicates are now first-class.

Changes
-------
* ADD COLUMNs: run_tag, rep, ctx_size, parallel_slots, seed, protocol, language,
  bench_family, max_tokens, source_file, completed_at.
* DROP the restriction-style unique index; add plain indexes instead.
* Backfill language='python', bench_family for legacy rows.
* Ingest W1 (repeat noise) and W2 (scale ladder) runs from their summaries.

Run:  python3 migrate_db.py
"""
import ast
import collections
import csv
import json
import os
import re
import sqlite3
import sys

# `MIGRATE_DB` 只给负控用：让一次完整的 refresh 跑在**库副本**上，而不是改共享主库。
DB = os.environ.get("MIGRATE_DB") or "experiments.sqlite"

# Logical gguf names known to the study (the bpw map is the canonical roster).
try:
    BPW_KEYS = set(json.load(open(".wrapup/bpw_map.json")))
except Exception:  # noqa: BLE001
    BPW_KEYS = set()
HF = "/home/z/hf"

NEW_COLS = [
    ("run_tag", "TEXT"),
    ("rep", "INTEGER"),
    ("ctx_size", "INTEGER"),
    ("parallel_slots", "INTEGER"),
    ("seed", "INTEGER"),
    ("protocol", "TEXT"),
    ("language", "TEXT DEFAULT 'python'"),
    ("bench_family", "TEXT"),
    ("max_tokens", "INTEGER"),
    ("source_file", "TEXT"),
    ("completed_at", "TEXT"),
    # Timing probe only: `_score` has a CHECK in [0, 1], so the MTP speed panel
    # (m28) stores generation tok/s here with `_score` NULL.
    ("_tok_s", "REAL"),
    # Item count behind `_score`.  SSOT section 2 makes significance item-level, and
    # SE = sqrt(p(1-p)/n), so n is not optional metadata - without it no CI can be
    # computed from the DB alone.  `limit_spec` records the lm_eval --limit used
    # (MMLU's is per subject, hence the separate mmlu entry).
    ("n_items", "INTEGER"),
    ("limit_spec", "TEXT"),
    # 行状态，不是行数据：非 NULL 时它**指向本表内另一行的 protocol 串**，说明这一格被
    # 哪个测量取代了（a14 的 py 重评：同一批落盘完成物 × 钉住的测试语料）。旧行的
    # `_score` 与 `protocol` 一个字不改，历史可查；报告只取 `superseded_by IS NULL` 的行。
    # a13 先例只能靠协议串区分新旧行，表达不出「谁取代了谁」；两个消费者各自持一份就会漂。
    ("superseded_by", "TEXT"),
]


def cols(con):
    return [r[1] for r in con.execute("PRAGMA table_info(experiments)")]


def migrate_schema(con):
    have = cols(con)
    for name, typ in NEW_COLS:
        if name not in have:
            con.execute(f"ALTER TABLE experiments ADD COLUMN {name} {typ}")
            print(f"  + column {name}")
    con.execute("DROP INDEX IF EXISTS uq_experiments_args_bench")
    con.execute("CREATE INDEX IF NOT EXISTS idx_experiments_run_tag ON experiments(run_tag)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_experiments_language ON experiments(language)")
    # backfill
    con.execute("UPDATE experiments SET bench_family=_bench "
                "WHERE bench_family IS NULL AND _bench IN ('humaneval','mbpp')")
    # 只回填**并入 run_tag 之前**的老行：那时候 language 列还不存在，「这台机器上跑的都是
    # python 代码」是成立的。并入之后的行（gsm8k/mmlu/ifeval…）`language` 为空是**事实**
    # ——它们不是代码基准；给它们写 `python` 等于替另一个 ingester 改它自己的行。
    con.execute("UPDATE experiments SET language='python' "
                "WHERE language IS NULL AND run_tag IS NULL")
    con.commit()


def file_size_gb(name):
    if not name.endswith(".gguf"):
        name = name + ".gguf"
    p = os.path.join(HF, name)
    try:
        return round(os.path.getsize(p) / 1e9, 6)
    except OSError:
        return None


def norm_model(name):
    return name if name.endswith(".gguf") else name + ".gguf"


ROW_COLS = ["model", "cache_type_k", "cache_type_k_draft", "cache_type_v",
            "cache_type_v_draft", "reasoning", "spec_type", "spec_draft_n_max",
            "temp", "top_p", "top_k", "min_p", "presence_penalty", "_bench",
            "_score", "_bad_rate", "_wall_time", "_tok_s", "_file_size",
            "run_tag", "rep", "ctx_size", "parallel_slots", "seed", "protocol",
            "language", "bench_family", "max_tokens", "source_file", "completed_at",
            "n_items", "limit_spec"]


def insert(con, row):
    assert set(row) <= set(ROW_COLS), set(row) - set(ROW_COLS)
    full = {c: row.get(c) for c in ROW_COLS}
    if full["_file_size"] is None:
        full["_file_size"] = file_size_gb(full["model"])
    con.execute(
        f"INSERT INTO experiments ({','.join(ROW_COLS)}) "
        f"VALUES ({','.join('?' * len(ROW_COLS))})",
        tuple(full[c] for c in ROW_COLS),
    )


# A cell's identity is WHAT WAS RUN, not what it scored: the model, protocol,
# language, benchmark, replicate, run configuration (ctx, max_tokens,
# parallel_slots, seed, reasoning/spec/cache settings) and every variant column
# that distinguishes runs under one protocol -- the sampling parameters top_p,
# top_k, min_p, presence_penalty and temp, so a top-k or temperature axis under a
# single protocol string stays N distinct cells instead of collapsing into one.
# `_score` and `_bad_rate` are the cell's VALUE, `_wall_time`/`_tok_s` are timing,
# `source_file`, `completed_at`, `n_items`, `limit_spec` are provenance and
# `_file_size` is read from disk, so none of them names the cell.  The derived
# `__*` block is absent on purpose: `ingest_mpl` cannot compute it, and ignoring it
# is what lets a re-read of a summary recognise the enriched copy `exp.py` already
# inserted instead of appending a bare duplicate.
# Consequence: a rerun never refreshes a score.  A corrected score needs an
# explicit delete-then-reinsert, as ingest_m26 / ingest_m6b / ingest_m161 do.
# MultiPL-E summary 若某行没有 protocol 字段时退回的协议串；用了它会被明确报出。
DEFAULT_MPL_PROTOCOL = "multipl-e-raw-greedy-768"

# 本次入库跳过了哪些行：run_tag → {(原因, 名字): 行数}。静默跳过比错数更危险——数据在、结论不在，
# 却没人知道。每个 ingest_* 在跳过一行时记一笔，main() 在末尾把整张账打出来。
INGEST_SKIPS = {}


# 哪些 ingester 因为看不到自己的输入而**放弃了删除**（保留现状）。main() 据此以 2 退出：
# 「读不到输入」是「不可得」，不是「没有变化」——两者混成一个退出码，假绿就回来了。
UNAVAILABLE = []

# `MIGRATE_WIDE_DELETE=1` 只给**差分负控**用：把三个面板 ingester 的删除范围换回旧写法
# （`source_file LIKE 'mres/%'` 这类共享前缀），用来证明「读不到输入就不删」这条 guard 是承重的
# ——去掉它在没有面板落盘产物的环境里会丢行，带上它一行不丢。
WIDE_DELETE = os.environ.get("MIGRATE_WIDE_DELETE") == "1"


def note_skip(run_tag, reason, name=""):
    INGEST_SKIPS.setdefault(run_tag, collections.Counter())[(reason, name)] += 1


MEASUREMENT_IDENTITY = [
    "model", "cache_type_k", "cache_type_k_draft", "cache_type_v",
    "cache_type_v_draft", "reasoning", "spec_type", "spec_draft_n_max", "temp",
    "top_p", "top_k", "min_p", "presence_penalty", "_bench", "run_tag", "rep",
    "ctx_size", "parallel_slots", "seed", "protocol", "language", "bench_family",
    "max_tokens",
]


def measurement_present(con, row):
    """True when this measurement cell already exists, enriched or bare."""
    # `IS` rather than `=` so a NULL-valued factor (seed) still matches.
    where = " AND ".join(f"{c} IS ?" for c in MEASUREMENT_IDENTITY)
    return con.execute(
        f"SELECT 1 FROM experiments WHERE {where} LIMIT 1",
        [row.get(c) for c in MEASUREMENT_IDENTITY],
    ).fetchone() is not None


def repair_duplicate_bare_copies(con):
    """Delete the bare copy of a cell when an enriched copy of the same cell exists.

    `ingest_mpl` used to append on every full run, so 17 MultiPL-E panels hold two
    copies of each cell: the enriched one (`exp.py` computed `__*`) and a bare one.
    Keep the enriched row, drop only the bare duplicate: a cell that has no enriched
    copy is a legitimate measurement and is never touched.  Idempotent, because after
    one run no bare row has an enriched twin left.
    """
    same_cell = " AND ".join(f"e.{c} IS b.{c}" for c in MEASUREMENT_IDENTITY)
    cur = con.execute(
        "DELETE FROM experiments WHERE rowid IN ("
        " SELECT b.rowid FROM experiments b JOIN experiments e ON " + same_cell +
        " WHERE b.__model IS NULL AND e.__model IS NOT NULL)"
    )
    return cur.rowcount


def base_row(model, bench, temp, score, bad):
    return {
        "model": model, "cache_type_k": "q8_0", "cache_type_k_draft": "q8_0",
        "cache_type_v": "q8_0", "cache_type_v_draft": "q8_0",
        "reasoning": "off", "spec_type": "none", "spec_draft_n_max": "0",
        "temp": str(temp), "top_p": "0.95", "top_k": "40", "min_p": "0.05",
        "presence_penalty": "0.0", "_bench": bench, "_score": score,
        "_bad_rate": bad, "_wall_time": None,
    }


def ingest_w1(con):
    path = ".wrapup/w1_summary.jsonl"
    if not os.path.exists(path):
        print("  (no w1 summary)"); return 0
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("score") is None:
            continue
        row = base_row(norm_model(r["model"]), r["bench"], r["temp"], r["score"], r["bad_rate"])
        row.update({"run_tag": "w1-repeat", "rep": r["rep"], "ctx_size": 2048,
                    "parallel_slots": 1, "protocol": "evalplus-0.3.1-openai-chat",
                    "language": "python", "bench_family": r["bench"],
                    "max_tokens": 768, "source_file": "w1_summary.jsonl"})
        insert(con, row)
        n += 1
    return n


def ingest_w2(con):
    path = ".wrapup/w2_summary.jsonl"
    if not os.path.exists(path):
        print("  (no w2 summary)"); return 0
    model_of = {
        "qwen9b-q2": "Qwen3.5-9B-UD-Q2_K_XL.gguf",
        "qwen9b-q3": "Qwen3.5-9B-UD-Q3_K_XL.gguf",
        "qwen4b-q2": "Qwen3.5-4B-UD-Q2_K_XL.gguf",
        "qwen4b-q3": "Qwen3.5-4B-UD-Q3_K_XL.gguf",
    }
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("score") is None or r["model"] not in model_of:
            continue
        row = base_row(model_of[r["model"]], r["bench"], r["temp"], r["score"],
                       r.get("bad_rate"))
        row.update({"run_tag": "w2-scale-ladder", "rep": r["rep"], "ctx_size": 2048,
                    "parallel_slots": 1, "protocol": "evalplus-0.3.1-openai-chat",
                    "language": "python", "bench_family": r["bench"],
                    "max_tokens": 768, "source_file": "w2_summary.jsonl"})
        insert(con, row)
        n += 1
    return n


MPL_MODELS = {
    "qwen4b-q2": "Qwen3.5-4B-UD-Q2_K_XL.gguf",
    "qwen4b-q3": "Qwen3.5-4B-UD-Q3_K_XL.gguf",
    "qwen9b-q2": "Qwen3.5-9B-UD-Q2_K_XL.gguf",
    "qwen9b-q3": "Qwen3.5-9B-UD-Q3_K_XL.gguf",
}


# 逐题产物（`mres/*_eval.json`）的状态直方图索引，随仓库分发（`build_eval_status.py` 生成）。
# 用途：一条 summary 行写 `pass=0, score=0.0` 时，要分清「一个都没通过」和「一个都没被判分」——
# 前者是测量，后者是没有测量。summary 自己常常不带 `statuses`，所以退到这份索引上按
# (模型键, 语言, 题量) 找它的逐题产物。
ARTEFACT_STATUS_INDEX = os.path.join("report_inputs", "eval_status.json")
_ARTEFACT_CACHE = None


def artefact_statuses(model_key, lang, n):
    """同一模型键 + 语言 + 题量的逐题产物状态直方图；多个候选必须一致，否则当作分不出。"""
    global _ARTEFACT_CACHE
    if _ARTEFACT_CACHE is None:
        try:
            doc = json.load(open(ARTEFACT_STATUS_INDEX, encoding="utf-8"))
            _ARTEFACT_CACHE = doc.get("files") or []
        except (OSError, ValueError):
            _ARTEFACT_CACHE = []
    suffix = f"-{model_key}-{lang}_eval.json"
    hits = [f["status"] for f in _ARTEFACT_CACHE
            if (f.get("file") or "").endswith(suffix) and f.get("n") == n]
    if not hits:
        return None
    if any(h != hits[0] for h in hits[1:]):
        return None                  # 候选口径不一致 → 分不出，不猜
    return hits[0]


def summary_score(row, model_key):
    """summary 行 → 入库的 `_score`；分不出分数时返回 None（写 NULL，不写 0.0）。

    两条规则，都来自「`@absent`：未记录的输入不能补一个默认值充当事实」：
      1. 行里没有 `score`（缺失或 None）→ NULL，并在 ledger 记「summary 没记分数」；
      2. `score == 0` 且逐题产物**全是 Exception**（一个都没被判分）→ NULL。
         注意只认「全 Exception」：全 SyntaxError 是模型写不出能编译的代码，那是一次实测的 0，
         `a05` 的加长前缀网格就靠它当楼层，不能一起抹成 NULL。
    """
    score = row.get("score")
    if score is None:
        return None
    if score != 0:
        return score
    statuses = row.get("statuses") or artefact_statuses(model_key, row["lang"], row.get("n"))
    if statuses and set(statuses) == {"Exception"}:
        return None
    return score


def ingest_mpl(con, path, run_tag, source, model_map=None):
    """Ingest a MultiPL-E summary, inserting only cells that are not in the DB yet.

    A full `python3 migrate_db.py` re-reads every summary; before this presence check
    each re-read appended a second (bare) copy of every cell `exp.py` had already
    inserted enriched, so the DB grew by one copy per run.  `insert` itself stays
    additive -- callers that refresh a run delete their rows first.
    """
    model_map = model_map or MPL_MODELS
    if not os.path.exists(path):
        print(f"  (no {source})")
        return 0
    n = 0
    skipped = 0
    unknown = collections.Counter()
    defaulted = collections.Counter()
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in model_map:
            unknown[r["model"]] += 1
            note_skip(run_tag, "unknown_model", r["model"])
            continue
        lang = r["lang"]
        # 每行自带的协议串原样入库：带因子的面板（m29 的 fa/kv）就是靠它各成一格，
        # 写成同一个默认值会把不同的格合并成一个，等于静默丢数据。
        proto = (r.get("protocol") or "").strip()
        if not proto:
            proto = DEFAULT_MPL_PROTOCOL
            defaulted[proto] += 1
            note_skip(run_tag, "default_protocol_used", proto)
        score = summary_score(r, r["model"])
        if score is None:
            note_skip(run_tag, "全 Exception 或 summary 没记分数 → 写 NULL（不写 0.0）",
                      f"{r['model']}:{lang}")
        row = base_row(model_map[r["model"]], f"humaneval-{lang}", 0.0, score, None)
        row.update({"run_tag": run_tag, "rep": 1, "ctx_size": 4096,
                    "parallel_slots": 1, "protocol": proto,
                    "language": lang, "bench_family": "humaneval-multipl-e",
                    "max_tokens": 768, "source_file": source})
        if measurement_present(con, row):
            skipped += 1
            note_skip(run_tag, "already_present")
            continue
        insert(con, row)
        n += 1
    if skipped:
        print(f"  {run_tag}: {skipped} cell(s) already present, not re-inserted")
    if unknown:
        print(f"  {run_tag}: skipped_rows={sum(unknown.values())} reason=unknown_model "
              f"names={','.join(sorted(unknown))} (在 model_map 里没有这些名字)")
    if defaulted:
        print(f"  {run_tag}: {sum(defaulted.values())} row(s) 没有 protocol 字段 → 用了默认协议 "
              f"{DEFAULT_MPL_PROTOCOL}（该次 summary 未记录协议）")
    return n


def ingest_m1(con):
    return ingest_mpl(con, ".wrapup/m1_summary.jsonl", "m1-multipl-e", "m1_summary.jsonl")


def ingest_m2(con):
    return ingest_mpl(con, ".wrapup/m2_summary.jsonl", "m2-multipl-e", "m2_summary.jsonl")


M_LADDER_MODELS = {
    "iq2xxs": "Qwen3.5-2B-UD-IQ2_XXS.gguf",
    "iq2m": "Qwen3.5-2B-UD-IQ2_M.gguf",
    "q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf",
    "q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "q4": "Qwen3.5-2B-UD-Q4_K_XL.gguf",
    "q5": "Qwen3.5-2B-UD-Q5_K_XL.gguf",
}


def ingest_m3(con):
    return ingest_mpl(con, ".wrapup/m3_summary.jsonl", "m3-quant-ladder",
                      "m3_summary.jsonl", model_map=M_LADDER_MODELS)


M4_MODELS = {
    "q2": "Qwen3.5-4B-UD-Q2_K_XL.gguf",
    "q3": "Qwen3.5-4B-UD-Q3_K_XL.gguf",
    "q4": "Qwen3.5-4B-UD-Q4_K_XL.gguf",
    "q5": "Qwen3.5-4B-UD-Q5_K_XL.gguf",
    "2bq4": "Qwen3.5-2B-UD-Q4_K_XL.gguf",
    "2bq3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "2bq5": "Qwen3.5-2B-UD-Q5_K_XL.gguf",
    "2bq2": "Qwen3.5-2B-UD-Q2_K_XL.gguf",
    "iq2m": "Qwen3.5-2B-UD-IQ2_M.gguf",
}


M5_MODELS = {
    "e2b-q2": "gemma-4-E2B-it-UD-Q2_K_XL.gguf",
    "e2b-q3": "gemma-4-E2B-it-UD-Q3_K_XL.gguf",
    "e4b-q2": "gemma-4-E4B-it-UD-Q2_K_XL.gguf",
    "e4b-q3": "gemma-4-E4B-it-UD-Q3_K_XL.gguf",
    "gr3b-q2": "granite-4.1-3b-Q2_K.gguf",
    "gr3b-q3": "granite-4.1-3b-Q3_K_M.gguf",
    "gr4b-q2": "granite-4.1-3b-Q2_K.gguf",
    "gr4b-q3": "granite-4.1-3b-Q3_K_M.gguf",
}


def ingest_m5(con):
    return ingest_mpl(con, ".wrapup/m5_summary.jsonl", "m5-family-ladder",
                      "m5_summary.jsonl", model_map=M5_MODELS)


def ingest_m4b(con):
    return _ingest_bfcl(con, ".wrapup/m4b_summary.jsonl", "m4b-tool-calling-native",
                        "bfcl-native-tools-nothink-greedy", "m4b_summary.jsonl")


M7_MODELS = {
    "e2b-q2": "gemma-4-E2B-it-UD-Q2_K_XL.gguf", "e2b-q3": "gemma-4-E2B-it-UD-Q3_K_XL.gguf",
    "e4b-q2": "gemma-4-E4B-it-UD-Q2_K_XL.gguf", "e4b-q3": "gemma-4-E4B-it-UD-Q3_K_XL.gguf",
    "gr3b-q2": "granite-4.1-3b-Q2_K.gguf", "gr3b-q3": "granite-4.1-3b-Q3_K_M.gguf",
}


def ingest_m7(con):
    return _ingest_bfcl(con, ".wrapup/m7_summary.jsonl", "m7-tool-calling-native",
                        "bfcl-native-tools-nothink-greedy", "m7_summary.jsonl",
                        model_map=M7_MODELS)


M6_MODELS = {
    "q08b-q2": "Qwen3.5-0.8B-UD-Q2_K_XL.gguf", "q08b-q3": "Qwen3.5-0.8B-UD-Q3_K_XL.gguf",
    "q36-35b-q2": "Qwen3.6-35B-A3B-UD-Q2_K_XL.gguf", "q36-35b-q3": "Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf",
    # gemma-4-12B is intentionally EXCLUDED: in raw-completion mode it emits its
    # <|channel>thought thinking channel, which breaks code generation at every quant,
    # so its Q2/Q3 scores are not a quantization measurement.
}


def ingest_m6(con):
    return ingest_mpl(con, ".wrapup/m6_summary.jsonl", "m6-family-ladder",
                      "m6_summary.jsonl", model_map=M6_MODELS)


M8_MODELS = {
    "qwen2b-q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf", "qwen2b-q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "qwen4b-q2": "Qwen3.5-4B-UD-Q2_K_XL.gguf", "qwen4b-q3": "Qwen3.5-4B-UD-Q3_K_XL.gguf",
    "e2b-q2": "gemma-4-E2B-it-UD-Q2_K_XL.gguf", "e2b-q3": "gemma-4-E2B-it-UD-Q3_K_XL.gguf",
    "gr3b-q2": "granite-4.1-3b-Q2_K.gguf", "gr3b-q3": "granite-4.1-3b-Q3_K_M.gguf",
}


def ingest_m8(con):
    return _ingest_bfcl(con, ".wrapup/m8_summary.jsonl", "m8-bfcl-live",
                        "bfcl-native-tools-nothink-greedy", "m8_summary.jsonl",
                        model_map=M8_MODELS)


M10_MODELS = {
    "q38-27b-q2": "Qwen3.8-27B-UD-Q2_K_XL.gguf", "q38-27b-q3": "Qwen3.8-27B-UD-Q3_K_XL.gguf",
    "g26b-q2": "gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf", "g26b-q3": "gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf",
    "nem4b-q2": "NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL.gguf", "nem4b-q3": "NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL.gguf",
    "mcp5-2b-q2": "MiniCPM5-2B-Q2_K.gguf", "mcp5-2b-q3": "MiniCPM5-2B-Q3_K_M.gguf",
    "lfm25-8b-q2": "LFM2.5-8B-A1B-UD-Q2_K_XL.gguf", "lfm25-8b-q3": "LFM2.5-8B-A1B-UD-Q3_K_XL.gguf",
    "orn9b-q4": "Ornith-1.5-9B-Q4_K_M.gguf", "orn9b-q5": "Ornith-1.5-9B-Q5_K_M.gguf",
}


# The MultiPL-E *chat* panels (m6b, m26, m161) share the m10 roster plus the
# gemma-4-12B chat pair, which no raw-completion panel can measure: in raw mode the
# model emits its <|channel>thought channel at every quant (see M6_MODELS), so its
# raw scores are a protocol artifact, not a quantization measurement.  A sibling map
# keeps `M10_MODELS` meaning exactly the roster m10_summary.jsonl contains.
MPL_CHAT_MODELS = dict(M10_MODELS, **{
    "g12b-q2": "gemma-4-12b-it-UD-Q2_K_XL.gguf",
    "g12b-q3": "gemma-4-12b-it-UD-Q3_K_XL.gguf",
})


def ingest_m10(con):
    return ingest_mpl(con, ".wrapup/m10_summary.jsonl", "m10-family-ladder",
                      "m10_summary.jsonl", model_map=M10_MODELS)


M10G_MODELS = {"gr3b-q3": "granite-4.1-3b-Q3_K_M.gguf", "gr3b-q4": "granite-4.1-3b-Q4_K_M.gguf"}


def ingest_m10g(con):
    return ingest_mpl(con, ".wrapup/m10_granite_summary.jsonl", "m10-granite-q34",
                      "m10_granite_summary.jsonl", model_map=M10G_MODELS)


M9_MODELS = {
    "qwen2b-q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf", "qwen2b-q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "gr3b-q2": "granite-4.1-3b-Q2_K.gguf", "gr3b-q3": "granite-4.1-3b-Q3_K_M.gguf",
}


MMT_MODELS = {
    # Qwen3.5 anchors (native <tool_call> FC handler works)
    "qwen2b-q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf", "qwen2b-q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    # M12 long-context anchor: same weights as qwen2b-q3 but a distinct
    # multi_turn_long_context cell (tag comes from run_m12.sh).
    "qwen2b-lc": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "qwen2b-lc2": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "qwen2b-lc3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "bonsai-q2g64": "Ternary-Bonsai-27B-Q2_g64.gguf",
    "m18-q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf",
    "m18-q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "m19-q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf",
    "m19-q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "m19-4bq2": "Qwen3.5-4B-UD-Q2_K_XL.gguf",
    "m19-4bq3": "Qwen3.5-4B-UD-Q3_K_XL.gguf",
    "m20-q2": "Qwen3.6-35B-A3B-UD-Q2_K_XL.gguf",
    "m20-q3": "Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf",
    "qwen4b-q2": "Qwen3.5-4B-UD-Q2_K_XL.gguf", "qwen4b-q3": "Qwen3.5-4B-UD-Q3_K_XL.gguf",
    # other families (handler support varies)
    "gr3b-q2": "granite-4.1-3b-Q2_K.gguf", "gr3b-q3": "granite-4.1-3b-Q3_K_M.gguf",
    # M14 re-run of granite under the granite-4 handler (Granite4FCHandler).
    "gr4b-q2": "granite-4.1-3b-Q2_K.gguf", "gr4b-q3": "granite-4.1-3b-Q3_K_M.gguf",
    "e2b-q2": "gemma-4-E2B-it-UD-Q2_K_XL.gguf", "e2b-q3": "gemma-4-E2B-it-UD-Q3_K_XL.gguf",
    "mcp5-2b-q2": "MiniCPM5-2B-Q2_K.gguf", "mcp5-2b-q3": "MiniCPM5-2B-Q3_K_M.gguf",
    "qwen9b-q2": "Qwen3.5-9B-UD-Q2_K_XL.gguf", "qwen9b-q3": "Qwen3.5-9B-UD-Q3_K_XL.gguf",
    "lfm25-8b-q2": "LFM2.5-8B-A1B-UD-Q2_K_XL.gguf", "lfm25-8b-q3": "LFM2.5-8B-A1B-UD-Q3_K_XL.gguf",
}


def _ingest_bfcl_mt(con, path, run_tag, source, model_map=None, ctx_size=98304):
    """Multi-turn BFCL rows (one per model x category)."""
    model_map = model_map or MMT_MODELS
    if not os.path.exists(path):
        print(f"  (no {source})")
        return 0
    # Refresh semantics: these panels append rows for hours across checkpoints
    # (m11/m12), so re-ingest replaces the run's rows instead of being one-shot.
    con.execute("DELETE FROM experiments WHERE run_tag = ?", (run_tag,))
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in model_map:
            note_skip(run_tag, "unknown_model", r["model"])
            continue
        if r.get("accuracy") is None:
            note_skip(run_tag, "missing_field", "accuracy")
            continue
        row = base_row(model_map[r["model"]], f"bfcl-{r['category']}", 0.0, r["accuracy"], None)
        row.update({"run_tag": run_tag, "rep": 1, "ctx_size": ctx_size, "parallel_slots": 2,
                    "protocol": r.get("protocol", "bfcl-official-multiturn-temp0"),
                    "language": "python", "bench_family": "bfcl-multiturn",
                    "source_file": source})
        insert(con, row)
        n += 1
    return n


def ingest_m9(con):
    return _ingest_bfcl_mt(con, ".wrapup/m9_summary.jsonl", "m9-bfcl-multiturn",
                           "m9_summary.jsonl")


def ingest_m11(con):
    return _ingest_bfcl_mt(con, ".wrapup/m11_summary.jsonl", "m11-bfcl-multiturn",
                           "m11_summary.jsonl")


def ingest_m12(con):
    return _ingest_bfcl_mt(con, ".wrapup/m12_summary.jsonl", "m12-bfcl-multiturn",
                           "m12_summary.jsonl")


def ingest_m13(con):
    # run_m13.sh launched llama-server with -c 131072 -np 2.
    return _ingest_bfcl_mt(con, ".wrapup/m13_summary.jsonl", "m13-bfcl-multiturn",
                           "m13_summary.jsonl", ctx_size=131072)


def ingest_m14(con):
    # run_m14.sh launched llama-server with -c 131072 -np 2.
    return _ingest_bfcl_mt(con, ".wrapup/m14_summary.jsonl", "m14-bfcl-multiturn",
                           "m14_summary.jsonl", ctx_size=131072)


def ingest_m15(con):
    # run_m15.sh launches llama-server with -c 196608 -np 2.
    return _ingest_bfcl_mt(con, ".wrapup/m15_summary.jsonl", "m15-bfcl-multiturn",
                           "m15_summary.jsonl", ctx_size=196608)


def ingest_m16(con):
    return _ingest_bfcl_mt(con, ".wrapup/m16_summary.jsonl", "m16-bfcl-multiturn",
                           "m16_summary.jsonl")


def ingest_m17(con):
    # run_m17.sh launches llama-server with -c 131072 -np 2.
    return _ingest_bfcl_mt(con, ".wrapup/m17_summary.jsonl", "m17-bfcl-multiturn",
                           "m17_summary.jsonl", ctx_size=131072)


def ingest_m18(con):
    # run_m18.sh launches llama-server with -c 131072 -np 2 (65536 ctx/slot).
    return _ingest_bfcl_mt(con, ".wrapup/m18_summary.jsonl", "m18-bfcl-multiturn",
                           "m18_summary.jsonl", ctx_size=131072)


def ingest_m19(con):
    # run_m19.sh launches llama-server with -c 196608 -np 2 (98304 ctx/slot).
    return _ingest_bfcl_mt(con, ".wrapup/m19_summary.jsonl", "m19-bfcl-multiturn",
                           "m19_summary.jsonl", ctx_size=196608)


def ingest_m20(con):
    # run_m20.sh launches llama-server with -c 131072 -np 2 (65536 ctx/slot).
    # Sparse-MoE anchor (Qwen3.6-35B-A3B) on multi_turn_base, Q2/Q3 pair.
    return _ingest_bfcl_mt(con, ".wrapup/m20_summary.jsonl", "m20-bfcl-multiturn",
                           "m20_summary.jsonl", ctx_size=131072)


def ingest_m22(con):
    """M22: ternary Bonsai across task types — single-turn (per-category) + multi-turn."""
    path = ".wrapup/m22_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m22 summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = 'm22-bonsai-ternary'")
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("kind") == "single-turn":
            for cat, d in (r.get("per_category") or {}).items():
                row = base_row("Ternary-Bonsai-27B-Q2_g64.gguf", f"bfcl-{cat}", 0.0,
                               d["acc"], None)
                row.update({"run_tag": "m22-bonsai-ternary", "rep": 1, "ctx_size": 131072,
                            "parallel_slots": 2, "protocol": r.get("protocol"),
                            "language": "python", "bench_family": "bfcl",
                            "source_file": "m22_summary.jsonl"})
                insert(con, row); n += 1
        elif r.get("kind") == "multi-turn":
            row = base_row("Ternary-Bonsai-27B-Q2_g64.gguf", f"bfcl-{r['category']}", 0.0,
                           r["accuracy"], None)
            row.update({"run_tag": "m22-bonsai-ternary", "rep": 1, "ctx_size": 131072,
                        "parallel_slots": 2, "protocol": r.get("protocol"),
                        "language": "python", "bench_family": "bfcl-multiturn",
                        "source_file": "m22_summary.jsonl"})
            insert(con, row); n += 1
    return n


M24_MODELS = {
    "bonsai17b-g64": "Ternary-Bonsai-1.7B-Q2_0_g64.gguf",
    "bonsai8b-g64": "Ternary-Bonsai-8B-Q2_0_g64.gguf",
}


def ingest_m24(con):
    return ingest_mpl(con, ".wrapup/m24_summary.jsonl", "m24-bonsai-series",
                      "m24_summary.jsonl", model_map=M24_MODELS)


def ingest_m29(con):
    return ingest_mpl(con, ".wrapup/m29_summary.jsonl", "m29-flash-attn",
                      "m29_summary.jsonl")


# a06 的厂商推荐采样 R1：summary 用短名 q2/q3。映射由同一 cell 的贪心格对上：m165 的 q2-cpp 贪心
# 18/161、q2-py 22/161，与库里 `Qwen3.5-2B-UD-Q{2,3}_K_XL` 的 m29 格逐位相同；Q3 同理。
M165_MODELS = {
    "q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf",
    "q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    # q4 之前漏在这里，q4-cpp/q4-py 以 unknown_model 被跳过（有 ledger，但不是「不该入」）。
    # 同一族的 Q4_K_XL 在库里与 bpw_map 里都有：rowid 1931 `Qwen3.5-2B-UD-Q4_K_XL.gguf`。
    "q4": "Qwen3.5-2B-UD-Q4_K_XL.gguf",
}


def ingest_m165(con):
    """厂商推荐采样臂的 R1 七格：五个采样量 + seed + ctx 全进身份列与协议串。

    summary 每行自带 `protocol`（形如 `mpl-raw-t1.0-768;ctx=4096;sampling=temp=1.0,…`），
    原样入库；同时把五个量写进各自的列——测量身份包含这些列，所以它不会与贪心格合并。
    """
    path = ".wrapup/mres/m165-vendor/vendor_r1_summary.jsonl"
    tag = "m165-vendor-r1"
    if not os.path.exists(path):
        print("  (no m165-vendor/vendor_r1_summary.jsonl)")
        return 0
    n = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("model") not in M165_MODELS:
            note_skip(tag, "unknown_model", str(r.get("model")))
            continue
        proto = (r.get("protocol") or "").strip()
        if not proto:
            proto = DEFAULT_MPL_PROTOCOL
            note_skip(tag, "default_protocol_used", proto)
        row = base_row(M165_MODELS[r["model"]], f"humaneval-{r['lang']}", 0.0,
                       summary_score(r, r["model"]), None)
        row.update({
            "run_tag": tag, "rep": 1, "ctx_size": r.get("ctx"), "parallel_slots": 1,
            "seed": r.get("seed"),
            "temp": str(r.get("temp")), "top_p": str(r.get("top_p")),
            "top_k": str(r.get("top_k")), "min_p": str(r.get("min_p")),
            "presence_penalty": str(r.get("presence_penalty")),
            "protocol": proto, "language": r["lang"],
            "bench_family": "humaneval-multipl-e", "max_tokens": 768,
            "n_items": r.get("n"), "source_file": "mres/m165-vendor/vendor_r1_summary.jsonl",
        })
        if measurement_present(con, row):
            note_skip(tag, "already_present")
            continue
        insert(con, row)
        n += 1
    print(f"  {tag}: inserted {n} cell(s)")
    return n


def ingest_m32(con):
    return _ingest_bfcl_mt(con, ".wrapup/m32_summary.jsonl", "m32-bonsai-ternary-mt",
                           "m32_summary.jsonl")


M33_MODELS = {
    "minicpm5-2b-q3": "MiniCPM5-2B-Q3_K_M.gguf",
    "nemotron3-4b-q3": "NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL.gguf",
    "ornith9b-q4": "Ornith-1.5-9B-Q4_K_M.gguf",
    "glm47flash-q3": "GLM-4.7-Flash-UD-Q3_K_XL.gguf",
}
M35_MODELS = {
    "bonsai4b-ternary": "Ternary-Bonsai-4B-Q2_0_g64.gguf",
    "bonsai27b-1bit": "Bonsai-27B-Q1_0.gguf",
    "qwen35-35a3b-iq1m": "Qwen_Qwen3.5-35B-A3B-IQ1_M.gguf",
}


def ingest_m33(con):
    return ingest_mpl(con, ".wrapup/m33_summary.jsonl", "m33-family-breadth",
                      "m33_summary.jsonl", model_map=M33_MODELS)


def ingest_m35(con):
    return ingest_mpl(con, ".wrapup/m35_summary.jsonl", "m35-sub2bit",
                      "m35_summary.jsonl", model_map=M35_MODELS)


M38_MODELS = {
    "qwen2b-q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf",
    "qwen2b-q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
}
M39_MODELS = {
    "glm47flash-tq1": "GLM-4.7-Flash-UD-TQ1_0.gguf",
    "glm47flash-q2kxl": "GLM-4.7-Flash-UD-Q2_K_XL.gguf",
}


def ingest_m38(con):
    return ingest_mpl(con, ".wrapup/m38_summary.jsonl", "m38-statpower-javajs",
                      "m38_summary.jsonl", model_map=M38_MODELS)


def ingest_m39(con):
    return ingest_mpl(con, ".wrapup/m39_summary.jsonl", "m39-glm-ternary",
                      "m39_summary.jsonl", model_map=M39_MODELS)


M30_MODELS = {"qwen2b-q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf"}
M31_MODELS = {"q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf", "q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
              "q4": "Qwen3.5-2B-UD-Q4_K_XL.gguf"}


def _ingest_mpl_ctx(con, path, run_tag, source, model_map, extra_cols):
    if not os.path.exists(path):
        print(f"  (no {source})")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?", (run_tag,))
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        m = model_map.get(r.get("model"))
        if not m or r.get("score") is None:
            continue
        bench = f"humaneval-{r.get('lang', 'cpp')}"
        row = base_row(m, bench, float(r.get("temp", 0.3) or 0.3),
                       summary_score(r, r.get("model")), None)
        row.update({"run_tag": run_tag, "rep": 1, "protocol": r.get("protocol", "mpl-raw"),
                    "language": r.get("lang", "cpp"), "bench_family": "humaneval-multipl-e",
                    "source_file": source})
        row.update(extra_cols(r))
        insert(con, row); n += 1
    return n


def ingest_m30(con):
    return _ingest_mpl_ctx(con, ".wrapup/m30_summary.jsonl", "m30-kv-ctx", "m30_summary.jsonl",
                           M30_MODELS, lambda r: {"ctx_size": r.get("ctx")})


def ingest_m31(con):
    return _ingest_mpl_ctx(con, ".wrapup/m31_summary.jsonl", "m31-topk", "m31_summary.jsonl",
                           M31_MODELS, lambda r: {"top_k": str(r.get("top_k"))})


M37_MODELS = {"qwen36-35a3b-udq3kxl": "Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf",
              "qwen36-35a3b-q3km": "Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf"}
M42_MODELS = {"qwen2b-q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf", "qwen2b-q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf"}
M45_MODELS = {"lfm25-8a1b-q2": "LFM2.5-8B-A1B-UD-Q2_K_XL.gguf",
              "lfm25-8a1b-q3": "LFM2.5-8B-A1B-UD-Q3_K_XL.gguf"}


def ingest_m37(con):
    return ingest_mpl(con, ".wrapup/m37_summary.jsonl", "m37-vendor-matched-size",
                      "m37_summary.jsonl", model_map=M37_MODELS)


def ingest_m42(con):
    return ingest_mpl(con, ".wrapup/m42_summary.jsonl", "m42-rust-ruby-power",
                      "m42_summary.jsonl", model_map=M42_MODELS)


def ingest_m45(con):
    return ingest_mpl(con, ".wrapup/m45_summary.jsonl", "m45-lfm-moe",
                      "m45_summary.jsonl", model_map=M45_MODELS)


M50_MODELS = {
    "qwen4b-iq3xxs": "Qwen3.5-4B-UD-IQ3_XXS.gguf",
    "qwen4b-q2kxl": "Qwen3.5-4B-UD-Q2_K_XL.gguf",
    "qwen2b-iq3xxs": "Qwen3.5-2B-UD-IQ3_XXS.gguf",
    "qwen2b-q2kxl": "Qwen3.5-2B-UD-Q2_K_XL.gguf",
}


def ingest_m50(con):
    """M50 (N1): IQ (imatrix) vs K-quant at MATCHED file size -- does IQ buy score per byte?"""
    return ingest_mpl(con, ".wrapup/m50_summary.jsonl", "m50-imatrix-vs-k",
                      "m50_summary.jsonl", model_map=M50_MODELS)


M51_MODELS = {
    "gemma12b-q2": "gemma-4-12b-it-UD-Q2_K_XL.gguf",
    "gemma12b-q3": "gemma-4-12b-it-UD-Q3_K_XL.gguf",
}


def ingest_m51(con):
    """M51 (N2): third-family (gemma-4-12B) java+js code anchor -- Tier 5B power."""
    return ingest_mpl(con, ".wrapup/m51_summary.jsonl", "m51-gemma-java-js",
                      "m51_summary.jsonl", model_map=M51_MODELS)


M54_MODELS = M51_MODELS  # same gemma-4-12B Q2_K_XL / Q3_K_XL files as m51, other languages


def ingest_m54(con):
    """M54 (N5): gemma-4-12B rust+ruby code anchor -- extends m51 (java+js)."""
    return ingest_mpl(con, ".wrapup/m54_summary.jsonl", "m54-gemma-rust-ruby",
                      "m54_summary.jsonl", model_map=M54_MODELS)


M52_MODELS = {
    "gemma12b-q3": "gemma-4-12b-it-UD-Q3_K_XL.gguf",
    "gemma12b-q3-draft": "gemma-4-12b-it-UD-Q3_K_XL.gguf",
    "qwen9b-q3": "Qwen3.5-9B-UD-Q3_K_XL.gguf",
}


def ingest_m52(con):
    """M52 (N3): decode/prefill tok/s for code vs prose, with an MTP draft-length sweep.

    Timing only (no benchmark score): `_score` is NULL and decode tok/s lives in
    `_tok_s` (bench_family='speed'), the same convention as ingest_m28.
    """
    path = ".wrapup/m52_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m52 summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?", ("m52-speed",))
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in M52_MODELS:
            continue
        draft_n = int(r.get("draft_n") or 0)
        row = base_row(M52_MODELS[r["model"]], f"speed-{r['prompt_type']}", 0.0, None, None)
        row.update({"run_tag": "m52-speed", "rep": 1, "ctx_size": 4096,
                    "parallel_slots": 1, "seed": 1234,
                    "spec_type": "draft-mtp" if draft_n else "none",
                    "spec_draft_n_max": str(draft_n),
                    "protocol": r.get("protocol", "speed-greedy-256-tps"),
                    "language": "python", "bench_family": "speed",
                    "max_tokens": r.get("n_decoded"),
                    "_tok_s": r.get("decode_tps"),
                    "source_file": "m52_summary.jsonl"})
        insert(con, row)
        n += 1
    return n


# What m26 still owns in the chat protocol, as (pass, n) re-derived from the stored
# completions under the fixed postprocess -- mpl_run.py::strip_fences at commit
# b57a71f, reproduced per cell by
#   python3 .wrapup/mpl_run.py eval --lang cpp \
#       --samples .wrapup/mres/m26-<tag>-cpp_fixed.jsonl
# whose "pass"/"n" are the numbers below.  Everything else m26 measured is gone:
# m161 re-generated the six chat py cells with the fixed harness and measured the
# q38-27b-q3 cpp control cell, so m161 is their single home and an m26 copy would be
# a second home for one fact.  gemma-4-26B's cpp completions carry no markdown fence,
# so their scores are unchanged; Qwen3.8-27B Q2 cpp's old 0.2174 was the fence defect.
M26_CHAT_CELLS = {
    ("g26b-q2", "cpp"): (134, 161),      # 0.8323, unchanged by the postprocess fix
    ("g26b-q3", "cpp"): (134, 161),      # 0.8323, unchanged
    ("q38-27b-q2", "cpp"): (102, 161),   # 0.6335, was 0.2174 (fence scored as SyntaxError)
}


def ingest_m26(con):
    """M26 / M43 (QUEUE #17): Tier-2C dense vs MoE at matched TOTAL size.

    The 2026-10-02 panel (run_m26.sh) completed on disk but never wrote a summary;
    run_m43.sh rebuilt m26_summary.jsonl from the per-cell evals (CPU-only, no
    re-run). Chat protocol, greedy, ctx 4096 -- protocol is read per row so the
    chat-vs-raw distinction is preserved.

    Only M26_CHAT_CELLS are ingested, and their scores come from that table rather
    than from the summary, because the summary was scored by the defective
    postprocess (see the table's comment for the re-derivation).
    """
    path = ".wrapup/m26_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m26 summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?", ("m26-tier2c-dense-moe",))
    n = 0
    seen = set()
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        cell = (r["model"], r["lang"])
        if cell not in M26_CHAT_CELLS:
            continue
        passed, total = M26_CHAT_CELLS[cell]
        row = base_row(MPL_CHAT_MODELS[r["model"]], f"humaneval-{r['lang']}", 0.0,
                       passed / total, None)
        row.update({"run_tag": "m26-tier2c-dense-moe", "rep": 1, "ctx_size": 4096,
                    "parallel_slots": 1,
                    "protocol": r.get("protocol", "mpl-chat-nothink-greedy-768"),
                    "language": r["lang"], "bench_family": "humaneval-multipl-e",
                    "max_tokens": 768, "source_file": "m26_summary.jsonl"})
        insert(con, row); n += 1
        seen.add(cell)
    missing = set(M26_CHAT_CELLS) - seen
    if missing:
        print(f"  ! m26 summary lacks declared cells {sorted(missing)}")
    return n


M6B_CHAT_CELLS = {
    # pass/n re-derived from the stored completions under the fixed postprocess:
    #   python3 .wrapup/mpl_run.py eval --lang cpp \
    #       --samples .wrapup/mres/m6b-g12b-q2-cpp_fixed.jsonl    -> pass 4
    #   python3 .wrapup/mpl_run.py eval --lang cpp \
    #       --samples .wrapup/mres/m6b-g12b-q3-cpp_fixed.jsonl    -> pass 130
    # m6b_summary.jsonl holds the pre-fix counts (2 and 130), because it was written
    # before strip_fences was fixed; the _fixed evals are the authoritative numbers.
    ("g12b-q2", "cpp"): (4, 161),
    ("g12b-q3", "cpp"): (130, 161),
}

# m6b ran a different server configuration from m26/m161 -- ctx 4096 per
# n_ctx_slot in m6b.log, not 2048 -- so its rows must not pool into the m161 chat
# column: the suffix is the visible reason they are not comparable, and it is part
# of the cell key the report groups on.
M6B_PROTOCOL = "mpl-chat-nothink-greedy-768;ctx=4096;tmpl=unverified"


def ingest_m6b(con):
    """M6B: gemma-4-12B chat panel (2026-09-30), ingested for the cpp cells only.

    The two py cells are deliberately absent, and no zero stands in for them: the
    old `strip_fences` ran `text.strip()` over the completion, so the first line's
    indentation was destroyed *when the completions were generated* (e.g.
    mres/m6b-g12b-q3-py.jsonl starts `for i in range(...)` at column 0 while its
    following lines keep theirs).  Python completions are function bodies, so the
    stored text cannot compile for reasons the postprocess now handles, and no
    re-score can restore the removed bytes.  A cell whose score is unrecoverable
    stays absent rather than being recorded as 0.

    Configuration actually recorded here, and what is only partly established:
      * ctx_size 4096 and four slots -- m6b.log prints `n_slots = 4, n_ctx_slot =
        4096`, so this is observed, not assumed.
      * cache_type_k/v q8_0 -- taken from the launch line of run_m6b.sh, which is
        the only survived record of the panel's server flags; the log itself does
        not print them.  The script cannot be trusted for everything (it says raw
        completion and writes samples under different names than the ones on disk,
        so the invocation that produced these cells was a modified copy), hence a
        weaker provenance than m161's.
      * --jinja / the chat-template path -- NOT established.  m6b.log has no
        template-init line, and the corresponding line in m161.log is model-
        dependent, so its absence is not proof of absence; the protocol string
        therefore marks the template as unverified instead of implying it matched.
    cpp scores come from M6B_CHAT_CELLS (re-derived, see there).
    """
    path = ".wrapup/m6b_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m6b summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?", ("m6b-chat-gemma12b",))
    n = 0
    seen = set()
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        cell = (r["model"], r["lang"])
        if cell not in M6B_CHAT_CELLS:
            continue
        passed, total = M6B_CHAT_CELLS[cell]
        row = base_row(MPL_CHAT_MODELS[r["model"]], f"humaneval-{r['lang']}", 0.0,
                       passed / total, None)
        row.update({"run_tag": "m6b-chat-gemma12b", "rep": 1, "ctx_size": 4096,
                    "parallel_slots": 4, "protocol": M6B_PROTOCOL,
                    "language": r["lang"], "bench_family": "humaneval-multipl-e",
                    "max_tokens": 768, "source_file": "m6b_summary.jsonl"})
        insert(con, row); n += 1
        seen.add(cell)
    missing = set(M6B_CHAT_CELLS) - seen
    if missing:
        print(f"  ! m6b summary lacks declared cells {sorted(missing)}")
    return n


def ingest_m161(con):
    """M161: the six MultiPL-E chat py cells re-generated with the FIXED postprocess,
    plus the q38-27b-q3 cpp cell that end-to-end controls the fix.

    run_m161_chat_py.sh ran the pinned prompt set (.wrapup/prompts, hash-checked
    before GPU time) at ctx 2048 with four parallel slots, greedy, 768 max tokens.
    Unlike m26, these are fresh generations: the pre-fix samples could not be
    re-scored, because the damaged text was the generation itself (method.m48).

    An all-Exception cell keeps `_score` NULL.  Exception means the program compiled
    and then failed, so a cell where every item raised is not a measured zero; m48
    keeps SyntaxError / Exception / Timeout as distinct outcomes and forbids folding
    them into one 0.
    """
    path = ".wrapup/m161_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m161 summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?",
                ("m161-chat-postprocess-fixed",))
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in MPL_CHAT_MODELS:
            continue
        statuses = r.get("statuses") or {}
        score = None if statuses and set(statuses) == {"Exception"} else r["score"]
        row = base_row(MPL_CHAT_MODELS[r["model"]], f"humaneval-{r['lang']}", 0.0,
                       score, None)
        row.update({"run_tag": "m161-chat-postprocess-fixed", "rep": 1,
                    "ctx_size": 2048, "parallel_slots": 4,
                    "protocol": r.get("protocol", "mpl-chat-nothink-greedy-768"),
                    "language": r["lang"], "bench_family": "humaneval-multipl-e",
                    "max_tokens": 768, "source_file": "m161_summary.jsonl"})
        insert(con, row); n += 1
    return n


# The two gemma-4-12B chat *cpp* cells m163 measured, and nothing else: m163 exists
# because 12B's only cpp cells sat under the m6b protocol string
# (`;ctx=4096;tmpl=unverified`) while its py cells were re-measured under
# `mpl-chat-nothink-greedy-768`, leaving it without a cpp+py pair under one protocol.
# The run id is m163, not m162, because i01's slot-reproduction experiment already
# writes its status file as `m162`; two experiments under one tag cannot be told apart.
M163_CHAT_CELLS = {("g12b-q2", "cpp"), ("g12b-q3", "cpp")}


def ingest_m163(con):
    """M163: gemma-4-12B MultiPL-E chat **cpp** Q2/Q3 under the canonical protocol.

    run_m163_chat_cpp_12b.sh copies run_m161_chat_py.sh's server and generator flags
    verbatim (ctx 2048, ``--jinja``, greedy, 768 max tokens, ``--strip-thought``,
    ``{"enable_thinking": false}``), so the protocol string is the canonical
    `mpl-chat-nothink-greedy-768` with no suffix: nothing deviates, and a suffix is
    reserved for a cell that does.  These are the cells that give the model a
    same-protocol cpp+py pair against its m161 py rows.

    An all-Exception cell keeps `_score` NULL, as in m161.
    """
    path = ".wrapup/m163_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m163 summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?",
                ("m163-chat-cpp-gemma12b",))
    n = 0
    seen = set()
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        cell = (r["model"], r["lang"])
        if cell not in M163_CHAT_CELLS:
            continue
        statuses = r.get("statuses") or {}
        score = None if statuses and set(statuses) == {"Exception"} else r["score"]
        row = base_row(MPL_CHAT_MODELS[r["model"]], f"humaneval-{r['lang']}", 0.0,
                       score, None)
        row.update({"run_tag": "m163-chat-cpp-gemma12b", "rep": 1,
                    "ctx_size": 2048, "parallel_slots": 4,
                    "protocol": r.get("protocol", "mpl-chat-nothink-greedy-768"),
                    "language": r["lang"], "bench_family": "humaneval-multipl-e",
                    "max_tokens": 768, "source_file": "m163_summary.jsonl",
                    "n_items": r["n"]})
        insert(con, row); n += 1
        seen.add(cell)
    missing = M163_CHAT_CELLS - seen
    if missing:
        print(f"  ! m163 summary lacks declared cells {sorted(missing)}")
    return n


M44_MODELS = {
    "qwen2b-q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf",
    "qwen2b-q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
}


def ingest_m44(con):
    """M44 (QUEUE #18) -- compute-precision PROBE: does `-fa` on/off (and the V-cache
    positive control) provably change greedy text? Stored as bench_family='fa-probe'
    so it is never read as a benchmark score. `_score` = fraction of probe prompts
    whose greedy text changed vs the reference cell (0.0 => that manipulation is a
    no-op for that cell -- m29's `-fa` axis is unmeasured where this is 0).
    """
    path = ".wrapup/m44_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m44 summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?", ("m44-fa-probe",))
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in M44_MODELS:
            continue
        prompts = max(int(r.get("prompts") or 1), 1)
        frac = (r.get("prompts_changed_vs_reference") or 0) / prompts
        row = base_row(M44_MODELS[r["model"]], f"fa-probe-{r['cell']}", 0.0, frac, None)
        row.update({"run_tag": "m44-fa-probe", "rep": 1, "ctx_size": 16384,
                    "parallel_slots": 1,
                    "protocol": r.get("protocol", "m44-probe-greedy-256"),
                    "language": "python", "bench_family": "fa-probe",
                    "max_tokens": 256, "source_file": "m44_summary.jsonl"})
        insert(con, row); n += 1
    return n


def _m41_model(filebase):
    """Resolve a testfrac sample name to its gguf basename.

    m41 reuses already-generated samples from many panels, so the sample file
    encodes the model (e.g. 'm21-bonsai-q2g64-cpp', 'pan-glm47flash-q3-js').
    The old ingest hardcoded 'Ternary-Bonsai-27B-Q2_g64' for every ternary row
    and the literal 'TODO.gguf' for every conventional row, which destroyed the
    model identity.  Resolve through the union of the panel model maps; return
    None when unknown so the row is dropped rather than mislabelled.
    """
    s = re.sub(r"-(cpp|py|js|java|rs|rb)$", "", filebase)
    union = {}
    for name, val in list(globals().items()):
        if name.endswith("_MODELS") and isinstance(val, dict):
            union.update(val)
    cands = [s]
    for pre in ("m3", "m21", "m24", "mt1", "pan", "m33", "m35", "m37", "m38", "m39"):
        if s.startswith(pre + "-"):
            cands.append(s[len(pre) + 1:])
    for c in cands:
        if c in union:
            return union[c]
    return None


def ingest_m41(con):
    """Partial-credit (mean fraction of tests passed) -- a CONTINUOUS metric, stored as
    bench_family='testfrac' so it is never confused with binary pass@1."""
    path = ".wrapup/m41_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m41 summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = 'm41-testfrac'")
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        mf = r.get("mean_frac")
        if mf is None:
            continue
        model = _m41_model(r.get("file", ""))
        if model is None:
            print("  [m41] unresolved sample", r.get("file"))
            continue
        row = base_row(model, f"testfrac-{r.get('arm')}", 0.0, mf, None)
        row.update({"run_tag": "m41-testfrac", "rep": 1, "ctx_size": 4096,
                    "protocol": "mpl-raw-greedy-768 + per-test fraction",
                    "language": r.get("lang", "cpp"), "bench_family": "testfrac",
                    "source_file": "m41_summary.jsonl"})
        insert(con, row); n += 1
    return n


def ingest_m36(con):
    return _ingest_bfcl_mt(con, ".wrapup/m36_summary.jsonl", "m36-bonsai-ternary-mt2",
                           "m36_summary.jsonl")


M56_MODELS = {"lfm25-8a1b-q2": "LFM2.5-8B-A1B-UD-Q2_K_XL.gguf", "lfm25-8a1b-q3": "LFM2.5-8B-A1B-UD-Q3_K_XL.gguf"}
M57_MODELS = {"nem4b-q2": "NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL.gguf", "nem4b-q3": "NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL.gguf"}
M58_MODELS = {"llama32-3b-q2": "Llama-3.2-3B-Instruct-Q2_K.gguf", "llama32-3b-q3": "Llama-3.2-3B-Instruct-Q3_K_M.gguf"}
M59_MODELS = {"phi4mini-q2": "Phi-4-mini-instruct-Q2_K.gguf", "phi4mini-q3": "Phi-4-mini-instruct-Q3_K_M.gguf"}
M60_MODELS = {"orn9b-q4": "Ornith-1.5-9B-Q4_K_M.gguf", "orn9b-q5": "Ornith-1.5-9B-Q5_K_M.gguf"}


def ingest_m56(con):
    return ingest_mpl(con, ".wrapup/m56_summary.jsonl", "m56-lfm-power", "m56_summary.jsonl", model_map=M56_MODELS)


def ingest_m57(con):
    return ingest_mpl(con, ".wrapup/m57_summary.jsonl", "m57-nem-power", "m57_summary.jsonl", model_map=M57_MODELS)


def ingest_m58(con):
    return ingest_mpl(con, ".wrapup/m58_summary.jsonl", "m58-llama32-family", "m58_summary.jsonl", model_map=M58_MODELS)


def ingest_m59(con):
    return ingest_mpl(con, ".wrapup/m59_summary.jsonl", "m59-phi4mini-family", "m59_summary.jsonl", model_map=M59_MODELS)


def ingest_m60(con):
    return ingest_mpl(con, ".wrapup/m60_summary.jsonl", "m60-ornith-power", "m60_summary.jsonl", model_map=M60_MODELS)


M55_MODELS = {"lfm25-8a1b-m55-q3base": "LFM2.5-8B-A1B-m55-Q3_K_M.gguf",
              "lfm25-8a1b-m55-exq2": "LFM2.5-8B-A1B-m55-exq2.gguf",
              "lfm25-8a1b-m55-exq4": "LFM2.5-8B-A1B-m55-exq4.gguf"}


def ingest_m55(con):
    return ingest_mpl(con, ".wrapup/m55_summary.jsonl", "m55-expertwise",
                      "m55_summary.jsonl", model_map=M55_MODELS)


def ingest_m4(con):
    return _ingest_bfcl(con, ".wrapup/m4_summary.jsonl", "m4-tool-calling",
                        "bfcl-prompt-nothink-greedy", "m4_summary.jsonl")


def _ingest_bfcl(con, path, run_tag, protocol, source, model_map=None):
    model_map = model_map or M4_MODELS
    """One DB row per BFCL category (so per-capability behaviour is visible)."""
    if not os.path.exists(path):
        print("  (no m4 summary)")
        return 0
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in model_map:
            continue
        for cat, d in r.get("per_category", {}).items():
            row = base_row(model_map[r["model"]], f"bfcl-{cat}", 0.0, d["acc"], None)
            row.update({"run_tag": run_tag, "rep": 1, "ctx_size": 8192,
                        "parallel_slots": 1, "protocol": protocol,
                        "language": "python", "bench_family": "bfcl",
                        "max_tokens": 512, "source_file": source})
            insert(con, row)
            n += 1
    return n


M23_MODELS = {
    "iq3-4b": "Qwen3.5-4B-UD-IQ3_XXS.gguf",
    "iq3-2b": "Qwen3.5-2B-UD-IQ3_XXS.gguf",
}


def ingest_m23(con):
    """M23: IQ3_XXS scheme vs the K-quant level at ~matched file size (raw greedy)."""
    return ingest_mpl(con, ".wrapup/m23_summary.jsonl", "m23-scheme-iqk",
                      "m23_summary.jsonl", model_map=M23_MODELS)


M25_MODELS = {
    "q36-35b-bartq3": "Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf",
}


def ingest_m25(con):
    """M25: same MoE base, bartowski Q3_K_M vs unsloth UD-Q3_K_XL (raw greedy)."""
    return ingest_mpl(con, ".wrapup/m25_summary.jsonl", "m25-vendor",
                      "m25_summary.jsonl", model_map=M25_MODELS)


M27_MODELS = {
    "q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf",
    "q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf",
    "q4": "Qwen3.5-2B-UD-Q4_K_XL.gguf",
}


def _mpl_protocol(proto):
    """Normalise the panel's `mpl-raw-*` string to the DB's `multipl-e-*` convention."""
    proto = proto or "mpl-raw-greedy-768"
    return proto.replace("mpl-raw-", "multipl-e-raw-", 1)


def ingest_m27(con):
    """M27: sampling x quant -- Qwen3.5-2B at Q2/Q3/Q4 x temp {0, 0.3, 0.6}.

    Temperature is the axis under test and is carried per row; the temp=0.0 Q2
    cell reproduces the m3 frozen-greedy anchor, so the two agree where they
    overlap.  Sampling rows keep a distinct protocol string (`multipl-e-raw-
    t0.3-768`) so the greedy quant ladder is not averaged with them.
    """
    path = ".wrapup/m27_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m27 summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?", ("m27-sampling",))
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in M27_MODELS:
            continue
        row = base_row(M27_MODELS[r["model"]], f"humaneval-{r['lang']}",
                       r["temp"], summary_score(r, r["model"]), None)
        row.update({"run_tag": "m27-sampling", "rep": 1, "ctx_size": 4096,
                    "parallel_slots": 1, "seed": 1234,
                    "protocol": _mpl_protocol(r.get("protocol")),
                    "language": r["lang"], "bench_family": "humaneval-multipl-e",
                    "max_tokens": 768, "source_file": "m27_summary.jsonl"})
        insert(con, row)
        n += 1
    return n


M28_MODELS = {"qwen3.5-2b-q4": "Qwen3.5-2B-UD-Q4_K_XL.gguf"}


def ingest_m28(con):
    """M28: MTP/draft-length speed curve (timing only, no benchmark score).

    `_score` has a DB CHECK in [0, 1] and tok/s does not fit, so speed rows keep
    `_score` NULL and carry generation tok/s in the `_tok_s` timing column
    (bench_family='speed').  The [0, 1] range invariant therefore applies to the
    benchmark families, not to this probe.
    """
    path = ".wrapup/m28_speed.jsonl"
    if not os.path.exists(path):
        print("  (no m28 speed file)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?", ("m28-speed",))
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in M28_MODELS:
            continue
        draft_n = int(r["draft_n"])
        row = base_row(M28_MODELS[r["model"]], f"speed-{r['mode']}", 0.0,
                       None, None)
        row.update({"run_tag": "m28-speed", "rep": 1, "ctx_size": 16384,
                    "parallel_slots": 1, "seed": 1234,
                    "spec_type": "draft-mtp" if draft_n else "none",
                    "spec_draft_n_max": str(draft_n),
                    "protocol": "m28-mtp-speed-greedy",
                    "language": "python", "bench_family": "speed",
                    "max_tokens": r.get("n_predict"),
                    "_tok_s": r["tok_s"],
                    "source_file": "m28_speed.jsonl"})
        insert(con, row)
        n += 1
    return n


CAMPAIGN_ROOT = ".wrapup/mres"

# The runners load the model by its RESOLVED path (llama.cpp needs the real file), so a
# result json can carry a bare `blobs/<sha256>` basename.  That breaks every analysis keyed
# on the model name (bpw map, family grouping).  Recover the logical name from the HF cache
# snapshot symlinks, which point at exactly those blobs.
def build_blob_map():
    import glob as _glob
    m = {}
    pats = ["/home/z/hf/models--*/snapshots/*/*.gguf",
            "/home/z/hf/mscache/*/*/*.gguf",
            "/home/z/hf/*.gguf"]
    for pat in pats:
        for snap in _glob.glob(pat):
            try:
                real = os.path.realpath(snap)
            except OSError:
                continue
            m.setdefault(os.path.basename(real), os.path.basename(snap))
    return m


BLOB_MAP = None


def canonical_model(path_or_name):
    """Logical gguf basename for a result record, dereferencing blob hashes."""
    global BLOB_MAP
    if not path_or_name:
        return None
    b = os.path.basename(str(path_or_name))
    if b in BPW_KEYS:
        return b
    if BLOB_MAP is None:
        BLOB_MAP = build_blob_map()
    return BLOB_MAP.get(b, b)

# lm-eval task -> (bench_family, protocol).  The loglikelihood tasks are scored through the
# exact echo shim (llama-server build 4399 ignores OpenAI `echo`), the generative ones through
# the chat endpoint.  Thinking is disabled at the SERVER level with --reasoning off, which is
# why an instruct model does not return an empty `content`.
LMEVAL_TASKS = {
    "mmlu":            ("mmlu",            "lmeval-0.4.13-gguf-shim-reasoning-off"),
    "arc_challenge":   ("arc_challenge",   "lmeval-0.4.13-gguf-shim-reasoning-off"),
    "truthfulqa_mc2":  ("truthfulqa_mc2",  "lmeval-0.4.13-gguf-shim-reasoning-off"),
    "gsm8k":           ("gsm8k",           "lmeval-0.4.13-chat-reasoning-off"),
    "ifeval":          ("ifeval",          "lmeval-0.4.13-chat-reasoning-off"),
}

# Headline metric per task, in preference order.  gsm8k is the important one: lm_eval reports
# both `strict-match` (requires the model to emit the '#### N' marker) and `flexible-extract`
# (extracts the final number however it is written).  Taking strict-match first measures format
# compliance, not arithmetic -- measured on Qwen3.5-2B IQ2_M: strict 0.01 but flexible 0.38, and
# on IQ3_XXS: strict 0.01 but flexible 0.52.  flexible-extract is therefore the primary and the
# strict variant is stored separately as `gsm8k-strict` so both remain auditable.
PRIMARY_METRIC = {
    "mmlu": ["acc,none", "acc"],
    "arc_challenge": ["acc_norm,none", "acc_norm", "acc,none"],
    "truthfulqa_mc2": ["acc,none", "acc"],
    "gsm8k": ["exact_match,flexible-extract", "exact_match,none", "exact_match,strict-match"],
    "ifeval": ["prompt_level_strict_acc,none", "prompt_level_strict_acc",
               "inst_level_strict_acc,none"],
}
# extra (task, variant, metric-key) rows recorded alongside the primary
EXTRA_ROWS = [("gsm8k", "gsm8k-strict", "exact_match,strict-match")]


def extract_metric(results: dict, task: str, prefer: list[str] | None = None):
    """First present metric from the preference list, or any exact_match/acc key."""
    node = results.get(task) or (results.get("groups", {}) or {}).get(task) or {}
    for key in (prefer or PRIMARY_METRIC.get(task, [])):
        if isinstance(node, dict) and node.get(key) is not None:
            return node[key], key
    for key, val in (node or {}).items():
        if isinstance(val, (int, float)) and (
                key.startswith("exact_match") or key.startswith("acc")):
            return val, key
    return None, None


def newest_task_json(out_dir, tag_dir, task):
    import glob
    fs = sorted(glob.glob(f"{out_dir}/lmeval_{task}_*.json"), key=os.path.getmtime)
    return fs[-1] if fs else None


def ingest_campaign(con):
    """Ingest the standard-benchmark campaign from .wrapup/mres/<tag>/{
    lmeval_panel.json,evalplus.json}.  REFRESH: panels are re-read as the campaign drains.

    Data contract (SSOT 2b): a task that produced no number is NOT written as 0.0.  It is
    simply not inserted; the raw error stays in the panel json.  Every inserted score keeps
    its numerator/denominator where the harness provides one.
    """
    if not os.path.isdir(CAMPAIGN_ROOT):
        note_skip("campaign", "输入不可得（无 .wrapup/mres），保留现状不删", CAMPAIGN_ROOT)
        UNAVAILABLE.append("campaign")
        print("  (no campaign results)"); return 0
    # drop previous **campaign** rows, then re-read (REFRESH semantics).
    # 删的范围只能是本 ingester 自己产出的那两种文件名（`mres/<tag>/lmeval_panel.json#<metric>`
    # 与 `mres/<tag>/evalplus.json`）。这里曾经写成 `source_file LIKE 'mres/%'`，于是同一轮里
    # 把排在 ONCE 里的其它 ingester 刚插的行一并删掉——m165 的 5 格就是这么没了，而 mres/ 下
    # 一共 923 行（含 spec/variant 面板与 a08 的面板格）都共享这个前缀。宽前缀是所有写 mres/ 的
    # ingester 的公共资源，不是任何一个 ingester 的私有范围。
    # 「读不到输入就不删」：只删**这一轮确实会重建**的那些行的来源。干净 clone 里
    # `.wrapup/mres` 没有随仓库完整分发，按前缀删会把读不回来的行一起删掉（实测 924 行）。
    rebuildable = []
    for tag_dir in sorted(os.listdir(CAMPAIGN_ROOT)):
        d = os.path.join(CAMPAIGN_ROOT, tag_dir)
        if not os.path.isdir(d) or tag_dir.startswith("p0-"):
            continue
        if os.path.exists(os.path.join(d, "lmeval_panel.json")):
            rebuildable.append(f"mres/{tag_dir}/lmeval_panel.json#%")
        if os.path.exists(os.path.join(d, "evalplus.json")):
            rebuildable.append(f"mres/{tag_dir}/evalplus.json")
    if WIDE_DELETE:
        con.execute("DELETE FROM experiments WHERE source_file LIKE 'mres/%'")
    elif rebuildable:
        con.execute("DELETE FROM experiments WHERE " + " OR ".join(
            "source_file LIKE ?" for _ in rebuildable), rebuildable)
    else:
        note_skip("campaign", "输入不可得（没有任何可重建的面板），保留现状不删", CAMPAIGN_ROOT)
        UNAVAILABLE.append("campaign")
        print("  campaign: 没有可重建的面板文件，保留现状不删")
        return 0
    n = 0
    for tag_dir in sorted(os.listdir(CAMPAIGN_ROOT)):
        d = os.path.join(CAMPAIGN_ROOT, tag_dir)
        if not os.path.isdir(d):
            continue
        # p0-* are calibration/smoke panels (tiny limits, throwaway models); they are not
        # campaign measurements and must not enter the DB as if they were.
        if tag_dir.startswith("p0-"):
            continue

        # ---- lm-evaluation-harness panel ----
        lp = os.path.join(d, "lmeval_panel.json")
        if os.path.exists(lp):
            try:
                p = json.load(open(lp))
            except Exception:
                p = None
            if p:
                model = canonical_model(p.get("model", "")) or None
                lim = p.get("limit_per_task")
                prof = p.get("profiles") or {}
                for task, score in (p.get("tasks") or {}).items():
                    if score is None or task not in LMEVAL_TASKS:
                        continue
                    fam, _proto = LMEVAL_TASKS[task]
                    tp = prof.get(task) or {}
                    # Reasoning mode is per task: gsm8k runs with thinking ON (without it the
                    # model does not terminate its answer and the score measures format
                    # compliance), while ifeval collapses with thinking ON.  Recording the
                    # per-task value is what keeps the two protocols from being conflated.
                    reason = tp.get("reasoning", p.get("reasoning", "off"))
                    proto = f"lmeval-0.4.13-{'chat' if task in ('gsm8k', 'ifeval') else 'gguf-shim'}-reasoning-{reason}"
                    # Re-derive the number from the task's own json rather than trusting the
                    # panel's stored pick, so a metric-preference fix applies retroactively
                    # without re-running an hour-long panel.
                    score, metric = score, None
                    tj = newest_task_json(d, tag_dir, task)
                    avail = {}
                    if tj:
                        try:
                            doc = json.load(open(tj))
                            score, metric = extract_metric(doc.get("results", {}), task)
                            for _t, _v, key in EXTRA_ROWS:
                                if _t != task:
                                    continue
                                avail[_v] = extract_metric(doc.get("results", {}), task, [key])[0]
                        except Exception:
                            pass
                    if score is None:
                        continue
                    row = base_row(norm_model(model), task, 0.0, score, None)
                    row.update({
                        "_bench": task, "bench_family": fam, "run_tag": p.get("tag", tag_dir),
                        "rep": 1, "ctx_size": tp.get("ctx", p.get("ctx_size", 8192)),
                        "parallel_slots": 1,
                        "protocol": proto, "language": None,
                        "max_tokens": (tp.get("max_gen_toks") if task in ("gsm8k", "ifeval") else None),
                        "source_file": f"mres/{tag_dir}/lmeval_panel.json#{metric}",
                        "completed_at": None,
                        "n_items": (p.get("n") or {}).get(task),
                        "limit_spec": None if lim is None else str(lim),
                    })
                    row["reasoning"] = reason
                    insert(con, row)
                    n += 1
                    for vname, vscore in avail.items():
                        if vscore is None:
                            continue
                        vrow = dict(row)
                        vrow["_bench"] = vname
                        vrow["_score"] = vscore
                        vrow["source_file"] = f"mres/{tag_dir}/lmeval_panel.json#{vname}"
                        vrow["completed_at"] = None
                        insert(con, vrow)
                        n += 1

        # ---- EvalPlus panel (base and plus are separate benchmarks) ----
        ep = os.path.join(d, "evalplus.json")
        if os.path.exists(ep):
            try:
                e = json.load(open(ep))
            except Exception:
                e = None
            if e:
                model = canonical_model(e.get("model_arg") or e.get("model", "")) or None
                for bench, v in (e.get("benches") or {}).items():
                    for variant in ("base", "plus"):
                        score = (v or {}).get(variant)
                        if score is None:
                            continue
                        name = bench if variant == "base" else f"{bench}-plus"
                        row = base_row(norm_model(model), name, 0.0, score, v.get("bad_rate"))
                        row.update({
                            "_bench": name, "bench_family": bench,
                            "run_tag": e.get("tag", tag_dir), "rep": 1,
                            "ctx_size": 8192, "parallel_slots": 1,
                            "protocol": f"evalplus-0.3.1-openai-chat-greedy-{variant}",
                            "language": "python",
                            "max_tokens": (e.get("protocol") or {}).get("max_new_tokens"),
                            "source_file": f"mres/{tag_dir}/evalplus.json",
                            "completed_at": None,
                            "n_items": v.get("n"),
                            "limit_spec": "full",
                        })
                        insert(con, row)
                        n += 1
    return n


# The three NEW research axes of this campaign, keyed by campaign tag -> canonical logical gguf
# name.  Axis 1.6 (QAT) and axis 7 (DiffusionGemma) each pair a treatment file with a CONTROL
# of the same size and the same UD-Q4_K_XL recipe; axis 1.5 (GSQ-RCO) pairs new ggml-type quants
# with the standard Qwen3.8-27B quants already measured.  Every analysis keys on the logical
# gguf name, so this is the one place that name is pinned.
#
# m141/m143/m145/m148/m156 are the native (non-QAT) controls downloaded for axis 1.6; m145
# (gemma-4-26B-A4B native UD-Q4_K_XL) also serves as the autoregressive control for axis 7, so
# it runs only once.  m150/m151 are the GSQ-RCO quants; m152 is the standard Qwen3.8-27B
# UD-IQ4_XS control (the other two controls, UD-Q2_K_XL and UD-Q3_K_XL, were already measured
# canonically as m91/m100 and are deliberately NOT re-run).  m154 is DiffusionGemma; it is
# ingested only if it passes the gate with the diffusion runtime.
AXES_TAG_MODELS = {
    "m140-qat-gemma12b-q4":        "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
    "m141-native-gemma12b-q4":     "gemma-4-12b-it-UD-Q4_K_XL.gguf",
    "m142-qat-gemma31b-q4":        "gemma-4-31B-it-qat-UD-Q4_K_XL.gguf",
    "m143-native-gemma31b-q4":     "gemma-4-31B-it-UD-Q4_K_XL.gguf",
    "m144-qat-gemma26b-a4b-q4":    "gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf",
    "m145-native-gemma26b-a4b-q4": "gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf",
    "m146-qat-gemma-e2b-q2":       "gemma-4-E2B-it-qat-UD-Q2_K_XL.gguf",
    "m147-qat-gemma-e2b-q4":       "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf",
    "m148-native-gemma-e2b-q4":    "gemma-4-E2B-it-UD-Q4_K_XL.gguf",
    "m149-qat-gemma-e4b-q2":       "gemma-4-E4B-it-qat-UD-Q2_K_XL.gguf",
    "m150-qwen38-gsqrco-iq3xxs":   "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf",
    "m151-qwen38-gsqrco-iq3s":     "Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf",
    "m152-qwen38-27b-iq4xs":       "Qwen3.8-27B-UD-IQ4_XS.gguf",
    "m154-diffusiongemma-26b-a4b-q4km": "diffusiongemma-26B-A4B-it-Q4_K_M.gguf",
    "m155-qat-gemma-e4b-q4":       "gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf",
    "m156-native-gemma-e4b-q4":    "gemma-4-E4B-it-UD-Q4_K_XL.gguf",
}


def ingest_axes(con):
    """Pin the AXES-campaign rows to their canonical logical model names (REFRESH).

    The generic campaign ingest above already reads every .wrapup/mres/<tag>/ panel, so these
    tags land without a dedicated parser.  What this block guarantees is the axis contract:
    tag -> logical gguf name is fixed by `AXES_TAG_MODELS`, so a resolved path or blob-hash
    name can never become an analysis key.  It does not invent rows: a tag with no results
    yet is simply skipped.  Returns the number of names corrected (0 when already correct).
    """
    n = 0
    for tag, name in AXES_TAG_MODELS.items():
        want = norm_model(name)
        cur = con.execute(
            "UPDATE experiments SET model = ? WHERE run_tag = ? AND model <> ?",
            (want, tag, want))
        n += cur.rowcount
    return n


def ingest_spec(con):
    """Speculative-decoding panel: TIME and QUALITY side by side.

    The operator's point was that draft/MTP depth is a SPEED knob, so the table needs tok/s;
    but it also needs scores, because the draft path changes the sampled sequence.  The old
    m28 panel measured tok/s only and never scored anything, so this closes that gap.

    Note the models: the plain Qwen3.5 GGUF has no MTP layers (llama-server: "model doesn't
    contain MTP layers"), so this axis can only run on the -MTP-GGUF repos.
    """
    import glob
    n = 0
    paths = sorted(glob.glob(".wrapup/mres/*-spec-*/spec_panel.json"))
    if not paths:
        note_skip("spec", "输入不可得（无 spec_panel.json），保留现状不删",
                  ".wrapup/mres/*-spec-*/spec_panel.json")
        UNAVAILABLE.append("spec")
        print("  spec: 没有 spec_panel.json，保留现状不删")
        return 0
    # 只删这一轮会重建的那几个 tag 的产物，不用会被别的 ingester 共用的宽前缀。
    if WIDE_DELETE:
        con.execute("DELETE FROM experiments WHERE source_file LIKE 'mres/%-spec-%'")
    else:
        con.execute("DELETE FROM experiments WHERE " + " OR ".join(
            "source_file = ?" for _ in paths),
            [f"mres/{os.path.basename(os.path.dirname(p))}/spec_panel.json" for p in paths])
    for path in paths:
        try:
            p = json.load(open(path))
        except Exception:
            continue
        tag = p.get("tag") or os.path.basename(os.path.dirname(path))
        model = canonical_model(p.get("model", "")) or None
        for nstr, row in (p.get("rows") or {}).items():
            depth = int(row.get("draft_n", nstr))
            spec_type = "none" if depth == 0 else "draft-mtp"
            common = {
                "model": norm_model(model), "cache_type_k": "q8_0", "cache_type_k_draft": "q8_0",
                "cache_type_v": "q8_0", "cache_type_v_draft": "q8_0", "reasoning": "off",
                "spec_type": spec_type, "spec_draft_n_max": str(depth),
                "temp": "0.0", "top_p": "0.95", "top_k": "40", "min_p": "0.05",
                "presence_penalty": "0.0", "_bad_rate": None, "_wall_time": None,
                "_file_size": None, "run_tag": tag, "rep": 1, "ctx_size": 8192,
                "parallel_slots": 1, "seed": None, "language": None,
                "bench_family": None, "max_tokens": None,
                "source_file": f"mres/{os.path.basename(os.path.dirname(path))}/spec_panel.json",
                "completed_at": None, "n_items": None, "limit_spec": "1",
            }
            if row.get("tok_s"):
                r = dict(common)
                r.update({"_bench": "speed", "_score": None,
                          "_tok_s": round(float(row["tok_s"]), 2),
                          "protocol": f"spec-mtp-{spec_type}-n{depth}-greedy-256",
                          "bench_family": "speed", "max_tokens": 256,
                          "n_items": 3})
                insert(con, r)
                n += 1
            for bench in ("mmlu", "gsm8k", "ifeval", "humaneval"):
                val = row.get(bench)
                if val is None:
                    continue
                r = dict(common)
                fam = "humaneval" if bench == "humaneval" else bench
                # mmlu's --limit is per SUBJECT (57), the others are plain item counts
                nit = {"humaneval": row.get("humaneval_n", 164), "mmlu": 456,
                       "gsm8k": 50, "ifeval": 50}[bench]
                r.update({"_bench": bench, "_score": val,
                          "_tok_s": (round(float(row["tok_s"]), 2) if row.get("tok_s") else None),
                          "protocol": f"spec-mtp-{spec_type}-n{depth}-{'evalplus' if bench == 'humaneval' else 'lmeval'}",
                          "bench_family": fam,
                          "max_tokens": (None if bench == "humaneval" else 1024),
                          "language": ("python" if bench == "humaneval" else None),
                          "n_items": nit})
                insert(con, r)
                n += 1
    return n


def ingest_variant(con):
    """KV-cache and sampling panels on the standard benchmark set.

    Tables E (KV) and F (sampling) were previously backed only by the old MultiPL-E panel, so
    they had one column of ten.  This brings them onto the same four standard columns the rest
    of the study uses: mmlu (loglikelihood), gsm8k, ifeval and EvalPlus humaneval.
    """
    import glob
    n = 0
    paths = sorted(glob.glob(".wrapup/mres/*/variant_panel.json"))
    if not paths:
        note_skip("variant", "输入不可得（无 variant_panel.json），保留现状不删",
                  ".wrapup/mres/*/variant_panel.json")
        UNAVAILABLE.append("variant")
        print("  variant: 没有 variant_panel.json，保留现状不删")
        return 0
    if WIDE_DELETE:
        con.execute("DELETE FROM experiments WHERE source_file LIKE 'mres/%/variant_panel.json'")
    else:
        con.execute("DELETE FROM experiments WHERE " + " OR ".join(
            "source_file = ?" for _ in paths),
            [f"mres/{os.path.basename(os.path.dirname(p))}/variant_panel.json" for p in paths])
    for path in paths:
        try:
            p = json.load(open(path))
        except Exception:
            continue
        tag = p.get("tag") or os.path.basename(os.path.dirname(path))
        axis = p.get("axis") or "variant"
        model = canonical_model(p.get("model", "")) or None
        for label, row in (p.get("rows") or {}).items():
            extra = row.get("llama_args") or []
            kv = "/".join(extra[i + 1] for i, a in enumerate(extra) if a == "--cache-type-k") \
                if "--cache-type-k" in extra else "q8_0"
            kvt = "/".join(extra[i + 1] for i, a in enumerate(extra) if a == "--cache-type-v") \
                if "--cache-type-v" in extra else "q8_0"
            kpart, vpart = (kv.split("/") + [kv])[:2]
            samp = row.get("sampling") or {}
            for bench in ("mmlu", "gsm8k", "ifeval", "humaneval"):
                val = row.get(bench)
                if val is None:
                    continue
                nit = {"mmlu": 456, "gsm8k": 50, "ifeval": 50,
                       "humaneval": row.get("humaneval_n", 164)}[bench]
                r = {
                    "model": norm_model(model),
                    "cache_type_k": kpart, "cache_type_v": vpart,
                    # The schema carries a legacy CHECK (cache_type_*_draft = cache_type_*).
                    # This panel runs with spec_type=none, so the draft cache is unused and
                    # mirroring the main one is honest rather than a workaround for data we
                    # would otherwise want to record.
                    "cache_type_k_draft": kpart, "cache_type_v_draft": vpart,
                    "reasoning": "off", "spec_type": "none", "spec_draft_n_max": "0",
                    # 采样参数一律从面板行里取；缺省只在面板确实没记时才用（并留痕）。
                    # 之前 top_p/min_p/presence_penalty 被写死成 0.95/0.05/0.0，于是
                    # 「厂商推荐采样」那一臂会与 greedy 落成同一个测量身份。
                    "temp": str(samp.get("temperature", 0.0)),
                    "top_p": str(samp.get("top_p", 0.95)),
                    "top_k": str(samp.get("top_k", 40)),
                    "min_p": str(samp.get("min_p", 0.05)),
                    "presence_penalty": str(samp.get("presence_penalty", 0.0)),
                    "_bench": bench, "_score": val, "_bad_rate": None,
                    "_wall_time": None, "_tok_s": None, "_file_size": None,
                    "run_tag": tag, "rep": 1, "ctx_size": 8192, "parallel_slots": 1,
                    "seed": samp.get("seed"),
                    # 采样参数写进协议串：只写标签名会让「厂商推荐」「greedy」在报告行里合并
                    # （top_k 与 fa 都踩过这个坑）。`sampling=` 段来自面板的 variant_panel.json。
                    # 采样段只在面板**记了**的时候才写。以前缺省写成 `sampling=default`，
                    # 那是把「没记录采样」写成「采样=默认」——同一个坑的另一面（`@absent`）：
                    # 未记录的输入不能补一个默认值充当事实。要不要区分两条臂，由 label 与服务
                    # 在采样参数列里承担；编造一个段反而不许。
                    "protocol": (f"variant-{axis}-{label}-"
                                 f"{'evalplus' if bench == 'humaneval' else 'lmeval'}"
                                 + (f";{spec}" if (spec := (row.get('sampling_spec') or '').strip())
                                    else "")),
                    "language": ("python" if bench == "humaneval" else None),
                    "bench_family": ("humaneval" if bench == "humaneval" else bench),
                    "max_tokens": (None if bench == "humaneval" else 1024),
                    "source_file": f"mres/{os.path.basename(os.path.dirname(path))}/variant_panel.json",
                    "completed_at": None, "n_items": nit, "limit_spec": "50",
                }
                insert(con, r)
                n += 1
    return n


# refresh 是「删了重插」，而重插只写各 ingester 自己读到的那几个字段。下面这些列是**修正**
# （别的 ingester 从官方 ledger、逐题产物回填出来的），不属于任何一次重插的产物：
#   * `n_items` 被 a13 从 BFCL 官方台账的 `total_count` 回填过 14 行，重插把它们抹回 NULL。
# 规则：删除前按测量身份读出来，重插后**为空才补写**，并在 ledger 里记「补写」。
PRESERVED_COLS = ("n_items",)


def snapshot_preserved(con):
    """refresh 之前记住被别人修正过的列：测量身份 → {列: 值}。"""
    sel = ",".join(MEASUREMENT_IDENTITY) + "," + ",".join(PRESERVED_COLS)
    saved = {}
    for row in con.execute(f"SELECT {sel} FROM experiments"):
        key, vals = tuple(row[:len(MEASUREMENT_IDENTITY)]), row[len(MEASUREMENT_IDENTITY):]
        if any(v is not None for v in vals):
            saved[key] = dict(zip(PRESERVED_COLS, vals))
    return saved


def restore_preserved(con, saved):
    """重插之后把被抹掉的修正值补回去（只在现值为空时写），并记 ledger。"""
    sel = "rowid," + ",".join(MEASUREMENT_IDENTITY) + "," + ",".join(PRESERVED_COLS)
    fixed = 0
    for row in con.execute(f"SELECT {sel} FROM experiments").fetchall():
        rowid = row[0]
        key = tuple(row[1:1 + len(MEASUREMENT_IDENTITY)])
        vals = dict(zip(PRESERVED_COLS, row[1 + len(MEASUREMENT_IDENTITY):]))
        old = saved.get(key)
        if not old:
            continue
        for col in PRESERVED_COLS:
            if vals[col] is None and old.get(col) is not None:
                con.execute(f"UPDATE experiments SET {col}=? WHERE rowid=?", (old[col], rowid))
                note_skip("refresh-preserve", f"补写 {col}（重插把它抹掉了，旧值保留）",
                          f"{key[0]}:{key[14]}")
                fixed += 1
    return fixed


def numbered_backup(path=DB):
    """变更前先产生下一个编号备份 `experiments.sqlite.bakN`，并断言它真的可用。

    库是 WAL 模式：只 `copy2` 主文件会漏掉还没检查点的那一段（实测一次 24,752 B 的 `-wal`），
    备份会回到一个**不是**变更前状态的库。所以用 SQLite 的在线备份 API（`Connection.backup()`）
    把已提交内容整体取出来，再打开备份逐项核对：integrity ok、行数与主库一致，并打印
    备份时的行数与 sha256，供事后比对。

    备份是变更的前置条件而不是事后步骤：`assert_backup_usable()` 在这一层就把关，所以任何
    调用点（`migrate_db.main()`、`migrations/backfill_n_items.py`）都拿到同一个门禁。
    """
    import hashlib
    n = 1
    while os.path.exists(f"{path}.bak{n}"):
        n += 1
    dst = f"{path}.bak{n}"
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    try:
        source_rows = src.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
        src.backup(out)                        # 在线备份：把已提交内容整体写进 dst
    finally:
        out.close()
        src.close()

    rows = assert_backup_usable(dst, source_rows)
    return dst, rows


def assert_backup_usable(dst, source_rows):
    """核对一份备份：能打开、integrity ok、行数与源库当时一致；否则抛错，不再改库。

    单独成函数是为了能被负控直接喂一份「行数不符」的备份来证明它会拒绝。
    """
    import hashlib
    probe = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
    try:
        ic = probe.execute("PRAGMA integrity_check").fetchone()[0]
        rows = probe.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    finally:
        probe.close()
    with open(dst, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    print(f"  backup: {dst} rows={rows} integrity={ic} sha256={digest[:16]}… "
          f"(源库当时 {source_rows} 行)")
    if ic != "ok":
        raise SystemExit(f"备份不可用：{dst} 的 integrity_check 返回 {ic}")
    if rows != source_rows:
        raise SystemExit(f"备份不可用：{dst} 有 {rows} 行，而源库当时是 {source_rows} 行；"
                         f"不在这种状态下改库")
    return rows


def print_ingest_skips():
    """把本次入库跳过的行按 (run_tag, 原因, 名字) 打出来；没有跳过就明说没有。"""
    total = sum(sum(c.values()) for c in INGEST_SKIPS.values())
    if not total:
        print("== ingest skips == none (每一行都入库或按测量身份去重)")
        return
    print(f"== ingest skips == total skipped_rows={total}")
    for run_tag in sorted(INGEST_SKIPS):
        for (reason, name), n in sorted(INGEST_SKIPS[run_tag].items()):
            label = f" name={name}" if name else ""
            print(f"  {run_tag}: skipped_rows={n} reason={reason}{label}")


def main():
    print("== backup ==")
    _dst, backup_rows = numbered_backup()
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    before = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    if backup_rows != before:
        raise SystemExit(f"备份与主库行数不一致：备份 {backup_rows}，主库 {before}；"
                         f"不在这种状态下改库")
    print("== migrating schema ==")
    migrate_schema(con)
    print("== repairing duplicate bare cells ==")
    repaired = repair_duplicate_bare_copies(con)
    print(f"  removed {repaired} bare duplicate(s) that an enriched copy already covered")
    print("== snapshot preserved columns ==")
    preserved = snapshot_preserved(con)
    print(f"  {len(preserved)} row(s) carry a column another ingester corrected")
    print("== ingesting ==")
    existing = {r[0] for r in con.execute(
        "SELECT DISTINCT run_tag FROM experiments WHERE run_tag IS NOT NULL")}

    def once(tag, fn):
        if tag in existing:
            print(f"  {tag}: already ingested, skipped")
            return 0
        return fn(con)

    # Ingest registry. ONE-SHOT entries are keyed by run_tag (skipped if present);
    # REFRESH entries delete-then-reinsert, because multi-turn BFCL panels append
    # rows over many hours and must be re-read on every checkpoint.
    ONCE = [
        ("w1", "w1-repeat", ingest_w1), ("w2", "w2-scale-ladder", ingest_w2),
        ("m1", "m1-multipl-e", ingest_m1), ("m2", "m2-multipl-e", ingest_m2),
        ("m3", "m3-quant-ladder", ingest_m3), ("m4", "m4-tool-calling", ingest_m4),
        ("m4b", "m4b-tool-calling-native", ingest_m4b), ("m5", "m5-family-ladder", ingest_m5),
        ("m6", "m6-family-ladder", ingest_m6), ("m7", "m7-tool-calling-native", ingest_m7),
        ("m8", "m8-bfcl-live", ingest_m8), ("m10", "m10-family-ladder", ingest_m10),
        ("m10g", "m10-granite-q34", ingest_m10g),
        ("m23", "m23-scheme-iqk", ingest_m23), ("m25", "m25-vendor", ingest_m25),
    ]
    REFRESH = [
        ("m9", ingest_m9), ("m11", ingest_m11), ("m12", ingest_m12),
        ("m13", ingest_m13), ("m14", ingest_m14), ("m15", ingest_m15),
        ("m16", ingest_m16), ("m17", ingest_m17), ("m18", ingest_m18),
        ("m19", ingest_m19), ("m20", ingest_m20), ("m21", ingest_m21),
        ("m22", ingest_m22), ("m27", ingest_m27), ("m28", ingest_m28),
        ("m24", ingest_m24), ("m29", ingest_m29), ("m32", ingest_m32),
        ("m30", ingest_m30), ("m31", ingest_m31),
        ("m37", ingest_m37), ("m41", ingest_m41), ("m42", ingest_m42), ("m45", ingest_m45),
        ("m55", ingest_m55), ("m56", ingest_m56), ("m57", ingest_m57),
        ("m58", ingest_m58), ("m59", ingest_m59), ("m60", ingest_m60),
        ("m50", ingest_m50), ("m51", ingest_m51), ("m52", ingest_m52),
        ("m54", ingest_m54), ("m26", ingest_m26), ("m6b", ingest_m6b),
        ("m161", ingest_m161), ("m163", ingest_m163), ("m44", ingest_m44),
        ("m36", ingest_m36),
        ("m33", ingest_m33), ("m35", ingest_m35), ("m165", ingest_m165),
        ("m38", ingest_m38), ("m39", ingest_m39),
        ("campaign", ingest_campaign),
        ("axes", ingest_axes),
        ("spec", ingest_spec),
        ("variant", ingest_variant),
    ]
    tally = {}
    for label, tag, fn in ONCE:
        tally[label] = once(tag, fn)
    for label, fn in REFRESH:
        tally[label] = fn(con)
    # 放在 REFRESH 之后：REFRESH 的 ingest 会用历史协议串重新插入行，这一步每次都把
    # 单轮 BFCL 收敛到官方判分身份，所以重复跑是幂等的。
    tally["a13-bfcl-rescore"] = ingest_bfcl_official_rescore(con)
    # 放在最后：它只改别的 ingest 已经落好的 py 行（写 `superseded_by`）并加新行。
    tally["a14-py-regrade"] = ingest_py_regrade(con)
    tally["a14-py-testfrac"] = ingest_py_testfrac_regrade(con)
    restored = restore_preserved(con, preserved)
    if restored:
        print(f"  refresh-preserve: 补写回 {restored} 个被重插抹掉的修正值")
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    print_ingest_skips()
    print("  inserted " + " ".join(f"{k}={v}" for k, v in tally.items())
          + f"  rows {before} -> {after}")
    ic = con.execute("PRAGMA integrity_check").fetchone()[0]
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    print("  integrity:", ic, "| fk issues:", len(fk))
    print("== run_tag coverage ==")
    for r in con.execute("SELECT COALESCE(run_tag,'<legacy>'), COUNT(*) FROM experiments "
                         "GROUP BY 1 ORDER BY 2 DESC"):
        print("   ", r)
    con.close()
    if UNAVAILABLE:
        print("UNAVAILABLE: 这些 ingester 读不到自己的输入，已保留现状未删："
              + ", ".join(sorted(set(UNAVAILABLE))))
        return 2
    return 0


BONSAI_MODELS = {
    "bonsai-q2g64": "Ternary-Bonsai-27B-Q2_g64.gguf",
}


def ingest_m21(con):
    # Refresh semantics: the panel appends one row per language, so a checkpoint
    # taken mid-panel must replace rather than lock in the partial row set.
    con.execute("DELETE FROM experiments WHERE run_tag = ?", ("m21-bonsai-ternary",))
    return ingest_mpl(con, ".wrapup/m21_summary.jsonl", "m21-bonsai-ternary",
                      "m21_summary.jsonl", model_map=BONSAI_MODELS)


# ---------------------------------------------------------------------------
# BFCL 单轮：官方 AST checker 的重打分取代自研匹配器的分数
#
# 为什么必须改：`possible_answer` 用 `["units", ""]` 表示「该参数可省略」，而仓库自研的
# `.wrapup/bfcl_run.py::call_ok` 要求标准答案里的**每个**键都出现在预测里，于是「正确但省略
# 可选参数」被判错。实测：同一批 15 个格、16,404 条可对照题里 2,788 条自研判错而官方判对，
# 其中 2,534 条是这个原因；反向只有 34 条。净效应是历史单轮 BFCL 数字系统性偏低。
#
# 两条身份不许合并：`_score` 存的是**哪套判分器**给出的值，由 `protocol` 说明。
#   * ...-official-ast-checker   = bundled bfcl_eval 的 ast_checker（含存在性判据的那三类）
#   * ...-homegrown-matcher      = 本仓自研匹配器（prompt 协议 20 行没有预测文件，无法重判）
# 重打分只在**同一批落盘预测**上换判分器，不重跑模型，所以差异可归给判分而不是生成。
#
# 幂等：先把该格上仍带自研协议串的行（REFRESH 类 ingest 会重新插入）删掉，再把剩下那一行
# 改成官方身份与官方分数；重复跑改动 0 行。
BFCL_RESCORE_ARTIFACT = os.path.join(
    "docs", "subprojects", "a13-工具调用 BFCL", "audits", "official_vs_homegrown.json")
BFCL_HOMEGROWN_PROTOCOL = "bfcl-native-tools-nothink-greedy"
BFCL_OFFICIAL_PROTOCOL = "bfcl-native-tools-nothink-greedy-official-ast-checker"
BFCL_PROMPT_HOMEGROWN_PROTOCOL = "bfcl-prompt-nothink-greedy-homegrown-matcher"
BFCL_PROMPT_OLD_PROTOCOL = "bfcl-prompt-nothink-greedy"


def ingest_bfcl_official_rescore(con):
    """把单轮 BFCL 的 `_score` 换成官方 checker 的值，并让协议串说明判分器身份。"""
    tag = "a13-bfcl-official-rescore"
    if not os.path.exists(BFCL_RESCORE_ARTIFACT):
        note_skip(tag, "重打分产物缺失", BFCL_RESCORE_ARTIFACT)
        print(f"  {tag}: MISSING {BFCL_RESCORE_ARTIFACT} -- 不动任何行")
        return 0
    doc = json.load(open(BFCL_RESCORE_ARTIFACT, encoding="utf-8"))
    changed = renamed = 0
    for fname, cats in doc["per_file"].items():
        model = doc["binding"][fname]["model"]
        for cat, rec in cats.items():
            if not rec.get("comparable", True):
                note_skip(tag, "该类无官方判据（无 possible_answer）", f"{fname}:{cat}")
                continue
            bench = f"bfcl-{cat}"
            # 只在这一对协议串内找重复：prompt 协议是**另一个测量**（同一模型、
            # 另一套工具呈现方式），把它当重复删掉就是数据丢失。本条是有代价学到的。
            rows = con.execute(
                "SELECT rowid,_score,protocol FROM experiments WHERE model=? AND _bench=? "
                "AND bench_family='bfcl' AND protocol IN (?,?)",
                (model, bench, BFCL_HOMEGROWN_PROTOCOL, BFCL_OFFICIAL_PROTOCOL)).fetchall()
            if not rows:
                note_skip(tag, "库里没有该格", f"{model}:{bench}")
                continue
            target = [r for r in rows if r[2] == BFCL_OFFICIAL_PROTOCOL] or rows
            for rowid, _score, proto in rows:
                if rowid != target[0][0] and proto != BFCL_OFFICIAL_PROTOCOL:
                    con.execute("DELETE FROM experiments WHERE rowid=?", (rowid,))
            rowid, old_score, old_proto = target[0]
            new_score = rec["official_acc"]
            if old_proto == BFCL_OFFICIAL_PROTOCOL and old_score == new_score:
                continue
            con.execute(
                "UPDATE experiments SET _score=?, protocol=?, "
                "__score_fix=CASE WHEN __score_fix IS NULL THEN NULL ELSE ? END, "
                "source_file=? WHERE rowid=?",
                (new_score, BFCL_OFFICIAL_PROTOCOL, new_score,
                 f"a13/official_vs_homegrown.json#{fname}:{cat}", rowid))
            changed += 1
    # prompt 协议：没有预测文件可重判，值不动，但身份必须写明是自研匹配器。
    renamed = con.execute(
        "UPDATE experiments SET protocol=? WHERE bench_family='bfcl' AND protocol=?",
        (BFCL_PROMPT_HOMEGROWN_PROTOCOL, BFCL_PROMPT_OLD_PROTOCOL)).rowcount
    con.commit()
    print(f"  {tag}: rescored {changed} row(s), relabelled {renamed} prompt row(s) "
          f"as {BFCL_PROMPT_HOMEGROWN_PROTOCOL}")
    return changed + renamed


# ---------------------------------------------------------------------------
# py 格的语料代次取代（a14 的 py 重评；meta 已授权，见 a14 PLAN「取代执行包」）
#
# 问题：2026-10-14 之前入库的 py 格，它们的完成物是在**另一份测试语料**上判分的。同一批落盘
# 完成物用今天钉住的语料重判，50/98 格换分（151/15516 题翻转，全在 py），cpp/java/js 0 翻转。
# 结论：旧的 py 分数不是「另一个模型」也不是「判分侧不稳」，而是**没记录自己读的是哪一代语料**。
#
# 落地：只入**能唯一确定行身份**的改分格，协议串按该格实际协议加两段
#   `<old_proto>;corpus=ac14c3b0abfa;gen_corpus=pre-2026-10-14`
# 两段缺一不可：`corpus=` 说判定真值来自哪一代语料，`gen_corpus=` 说完成物生成在旧语料上
# （所以它不是一次重跑，是同一批完成物换了真值）。旧行一个字不改，只在 `superseded_by`
# 里写下取代它的那行的协议串——这是「行状态」，不是删除。
#
# 红线（a14 与 meta 都点名过）：**绝不按 `_score` 认行**。73 格的同一个分数落在多行上，
# 按分数改会连带改错别的格。认行只用清单的 `db_rowids` → `db_models` → `db_run_tags`
# → （`protocol_old`，否则 `db_source_files`）；任何一步剩下多于一行就进 skip ledger。
PY_REGRADE_MANIFEST = os.path.join(
    "docs", "subprojects", "a14-部分给分", "evidence", "py_regrade_manifest.tsv")
PY_REGRADE_SUFFIX = "corpus=ac14c3b0abfa;gen_corpus=pre-2026-10-14"


def models_of(rec):
    """清单的 `db_models`：有的是 JSON 数组，有的是单引号 Python 字面量，两种都读。"""
    raw = (rec.get("db_models") or "").strip()
    if not raw:
        return []
    try:
        return list(json.loads(raw))
    except json.JSONDecodeError:
        return list(ast.literal_eval(raw))


def _regrade_candidates(con, rec):
    """清单的一行 → 活库里这条改分格的候选行；判据只用身份列，不用 rowid、不用分数。

    **不能用清单里的 `db_rowids`**：清单是快照，并发入库（以及本脚本自己插的行）会把 rowid 漂走
    ——实测 14083/14129 两个 rowid 在几十分钟内就消失了，按 rowid 找会把 `m26-q38-27b-q2-py`
    判成 `unique` 并对上另一族模型（Nemotron）。判据是五元组
    (model, bench, language, protocol_old, n_items)，再用 `source_file` 切分：

      * 候选唯一 → 直接用；
      * 候选多于一行 → 用清单的 `summary_file` 的文件名过滤一次（那是 a14 找到这批完成物的
        summary，也就是 `a12` 的 `mpl_cell_audit.py` 第 [1] 段「逐格能不能追溯到一份产物」用的键）；
      * 清单自己的 `summary_file` 与 `db_source_files` 指向不同文件时**不猜**：这种情况说明清单
        两列互相矛盾（同一模型在两份 summary 里都出现过），交回调用方记进 skip ledger。
    """
    models = models_of(rec)
    n = int(rec["n"])
    if not models:
        return []
    tries = ([rec["protocol_old"]] if rec["protocol_old"] else []) + \
            [[p for p in (rec["db_protocols"] or "").split("|") if p]]
    summary = os.path.basename((rec.get("summary_file") or "").strip())
    declared = {x for x in (rec.get("db_source_files") or "").split(",") if x}
    saved_factory = con.row_factory
    con.row_factory = sqlite3.Row
    try:
        for prots in tries:
            if not prots:
                continue
            # 清单的 `bench` 是族名（`humaneval-multipl-e` / `humaneval-py`），库里同一族的行
            # 两种 `_bench` 都有，所以按族匹配，不按 `_bench` 字面匹配。
            q = ("SELECT rowid, * FROM experiments WHERE model IN (%s) "
                 "AND _bench IN ('humaneval-py','humaneval-multipl-e') "
                 "AND language='py' AND bench_family='humaneval-multipl-e' "
                 "AND protocol IN (%s) AND (n_items IS NULL OR n_items=?) "
                 # 取代行自己不能当「旧行」再去取代一次（否则协议串会被加两遍后缀）
                 "AND protocol NOT LIKE '%%;corpus=%%'"
                 % (",".join("?" * len(models)), ",".join("?" * len(prots))))
            rows = con.execute(q, [*models, *prots, n]).fetchall()
            if not rows:
                continue
            if summary:
                rows = [r for r in rows if r["source_file"] == summary]
                if not rows:
                    continue
            elif declared:
                rows = [r for r in rows if r["source_file"] in declared]
                if not rows:
                    continue
            return rows
        return []
    finally:
        con.row_factory = saved_factory


PY_TESTFRAC_REGRADE = os.path.join(
    "docs", "subprojects", "a14-部分给分", "evidence", "py_testfrac_regrade.json")


def ingest_py_testfrac_regrade(con):
    """把 a14 用钉住语料重算的**每测试通过比例**按同一代次入一行（旧行标指针、不删）。

    二元列（通过/不通过）与比例列（每题通过的测试比例均值）必须同代：a14 的 res22 说得很清楚，
    比例的分母也是测试语料，语料换一代，两列就各说一代。所以这里与 `ingest_py_regrade` 用同一条
    身份串后缀，把比例值也上一次新行。

    认行判据：比例行的 `_score` 就是 `mean_frac`，所以按 (run_tag='m41-testfrac', _score=旧比例)
    找，要求**唯一**；找不到或撞多行 → skip ledger，理由写清。不需要 model 名——比例行自带那个值。
    """
    tag = "a14-py-testfrac-regrade"
    if not os.path.exists(PY_TESTFRAC_REGRADE):
        note_skip(tag, "重算产物缺失", PY_TESTFRAC_REGRADE)
        print(f"  {tag}: MISSING {PY_TESTFRAC_REGRADE} -- 不动任何行")
        return 0
    doc = json.load(open(PY_TESTFRAC_REGRADE, encoding="utf-8"))
    saved_factory = con.row_factory
    con.row_factory = sqlite3.Row
    inserted = linked = 0
    try:
        for cell in doc.get("cells") or []:
            old_score = cell["mean_frac_old"]
            rows = con.execute(
                "SELECT rowid, * FROM experiments WHERE run_tag='m41-testfrac' "
                "AND abs(_score - ?) < 1e-6 AND protocol NOT LIKE '%%;corpus=%%'",
                (old_score,)).fetchall()
            if len(rows) != 1:
                note_skip(tag, "比例行候选不唯一或找不到", f"{cell['tag']}（候选 {len(rows)}）")
                continue
            old = rows[0]
            new_proto = f"{old['protocol']};{PY_REGRADE_SUFFIX}"
            row = {c: old[c] for c in ROW_COLS}
            row.update({"_score": float(cell["mean_frac_new"]), "protocol": new_proto})
            if not measurement_present(con, row):
                insert(con, row)
                inserted += 1
            linked += con.execute(
                "UPDATE experiments SET superseded_by=? WHERE rowid=? AND "
                "(superseded_by IS NULL OR superseded_by <> ?)",
                (new_proto, old["rowid"], new_proto)).rowcount
    finally:
        con.row_factory = saved_factory
    con.commit()
    print(f"  {tag}: +{inserted} 行（比例列同代），旧行写指针 {linked} 行")
    return inserted


def ingest_py_regrade(con):
    """把 a14 清单里**定得下身份**的改分格按新协议串入一行，并给旧行写下取代指针。"""
    tag = "a14-py-regrade"
    if not os.path.exists(PY_REGRADE_MANIFEST):
        note_skip(tag, "取代清单缺失", PY_REGRADE_MANIFEST)
        print(f"  {tag}: MISSING {PY_REGRADE_MANIFEST} -- 不动任何行")
        return 0
    manifest = list(csv.DictReader(open(PY_REGRADE_MANIFEST, encoding="utf-8"),
                                   delimiter="\t"))
    inserted = linked = 0
    unchanged = 0
    claimed = {}                 # 旧行 rowid → 已经认领它的格；两格抢同一行说明对账有歧义
    for rec in manifest:
        cell = rec["tag"]
        if int(rec["delta"]) == 0:
            unchanged += 1          # 没改分：旧行就是新值，不需要新行，也不标 superseded
            continue
        if rec["db_match"] == "none":
            note_skip(tag, "该格从未入库，不新造行", cell)
            continue
        n = int(rec["n"])
        cand = _regrade_candidates(con, rec)
        if len(cand) != 1:
            note_skip(tag,
                      "两处映射都不可唯一（五元组 + source_file 后仍有多个候选）" if cand
                      else "活库里找不到该格（模型/协议/题量/来源都对不上）",
                      f"{cell}（候选 {len(cand)}；清单 summary_file={rec.get('summary_file')}，"
                      f"db_source_files={rec.get('db_source_files')}）")
            continue
        chosen = cand[0]
        if chosen["_score"] is None or abs(chosen["_score"] - float(rec["score_old"])) > 1e-6:
            note_skip(tag, "旧行分数与清单 score_old 不符（不覆盖）",
                      f"{cell}（库里 {chosen['_score']}，清单 {rec['score_old']}）")
            continue
        if chosen["rowid"] in claimed:
            note_skip(tag, f"两个格解析到同一行（另一格是 {claimed[chosen['rowid']]}）", cell)
            continue
        claimed[chosen["rowid"]] = cell
        new_proto = f"{chosen['protocol']};{PY_REGRADE_SUFFIX}"
        row = {c: chosen[c] for c in ROW_COLS}
        row.update({"_score": int(rec["pass_new"]) / n, "protocol": new_proto,
                    "n_items": n, "language": "py",
                    "bench_family": "humaneval-multipl-e"})
        if not measurement_present(con, row):
            insert(con, row)
            inserted += 1
        linked += con.execute(
            "UPDATE experiments SET superseded_by=? WHERE rowid=? AND "
            "(superseded_by IS NULL OR superseded_by <> ?)",
            (new_proto, chosen["rowid"], new_proto)).rowcount
    con.commit()
    print(f"  {tag}: +{inserted} 行（新协议串），旧行写指针 {linked} 行，"
          f"{unchanged} 格未改分不入库")
    return inserted


if __name__ == "__main__":
    sys.exit(main())
