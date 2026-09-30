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
import json
import os
import sqlite3
import sys

DB = "experiments.sqlite"
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
    con.execute("UPDATE experiments SET language='python' WHERE language IS NULL")
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
            "_score", "_bad_rate", "_wall_time", "_file_size",
            "run_tag", "rep", "ctx_size", "parallel_slots", "seed", "protocol",
            "language", "bench_family", "max_tokens", "source_file", "completed_at"]


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


def ingest_mpl(con, path, run_tag, source):
    if not os.path.exists(path):
        print(f"  (no {source})")
        return 0
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in MPL_MODELS:
            continue
        lang = r["lang"]
        row = base_row(MPL_MODELS[r["model"]], f"humaneval-{lang}", 0.0, r["score"], None)
        row.update({"run_tag": run_tag, "rep": 1, "ctx_size": 4096,
                    "parallel_slots": 1, "protocol": "multipl-e-raw-greedy-768",
                    "language": lang, "bench_family": "humaneval-multipl-e",
                    "max_tokens": 768, "source_file": source})
        insert(con, row)
        n += 1
    return n


def ingest_m1(con):
    return ingest_mpl(con, ".wrapup/m1_summary.jsonl", "m1-multipl-e", "m1_summary.jsonl")


def ingest_m2(con):
    return ingest_mpl(con, ".wrapup/m2_summary.jsonl", "m2-multipl-e", "m2_summary.jsonl")


def main():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    before = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    print("== migrating schema ==")
    migrate_schema(con)
    print("== ingesting ==")
    existing = {r[0] for r in con.execute(
        "SELECT DISTINCT run_tag FROM experiments WHERE run_tag IS NOT NULL")}

    def once(tag, fn):
        if tag in existing:
            print(f"  {tag}: already ingested, skipped")
            return 0
        return fn(con)

    n1 = once("w1-repeat", ingest_w1)
    n2 = once("w2-scale-ladder", ingest_w2)
    n3 = once("m1-multipl-e", ingest_m1)
    n4 = once("m2-multipl-e", ingest_m2)
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    print(f"  inserted w1={n1} w2={n2} m1={n3} m2={n4}  rows {before} -> {after}")
    ic = con.execute("PRAGMA integrity_check").fetchone()[0]
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    print("  integrity:", ic, "| fk issues:", len(fk))
    print("== run_tag coverage ==")
    for r in con.execute("SELECT COALESCE(run_tag,'<legacy>'), COUNT(*) FROM experiments "
                         "GROUP BY 1 ORDER BY 2 DESC"):
        print("   ", r)
    con.close()


if __name__ == "__main__":
    main()
