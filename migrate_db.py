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


def ingest_mpl(con, path, run_tag, source, model_map=None):
    model_map = model_map or MPL_MODELS
    if not os.path.exists(path):
        print(f"  (no {source})")
        return 0
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in model_map:
            continue
        lang = r["lang"]
        row = base_row(model_map[r["model"]], f"humaneval-{lang}", 0.0, r["score"], None)
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


def ingest_m9(con):
    """Multi-turn BFCL via the official bfcl-eval harness (one row per model x category)."""
    path = ".wrapup/m9_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m9 summary)")
        return 0
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in M9_MODELS or r.get("accuracy") is None:
            continue
        row = base_row(M9_MODELS[r["model"]], f"bfcl-{r['category']}", 0.0, r["accuracy"], None)
        row.update({"run_tag": "m9-bfcl-multiturn", "rep": 1, "ctx_size": 98304,
                    "parallel_slots": 2,
                    "protocol": r.get("protocol", "bfcl-official-multiturn-temp0"),
                    "language": "python", "bench_family": "bfcl-multiturn",
                    "source_file": "m9_summary.jsonl"})
        insert(con, row)
        n += 1
    return n


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
    n5 = once("m3-quant-ladder", ingest_m3)
    n6 = once("m4-tool-calling", ingest_m4)
    n6b = once("m4b-tool-calling-native", ingest_m4b)
    n7 = once("m5-family-ladder", ingest_m5)
    n8 = once("m6-family-ladder", ingest_m6)
    n9 = once("m7-tool-calling-native", ingest_m7)
    n10 = once("m8-bfcl-live", ingest_m8)
    n11 = once("m10-family-ladder", ingest_m10)
    n12 = once("m10-granite-q34", ingest_m10g)
    n13 = once("m9-bfcl-multiturn", ingest_m9)
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    print(f"  inserted w1={n1} w2={n2} m1={n3} m2={n4} m3={n5} m4={n6} m4b={n6b} m5={n7} m6={n8} m7={n9} m8={n10} m10={n11} m10g={n12} m9={n13}  rows {before} -> {after}")
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
