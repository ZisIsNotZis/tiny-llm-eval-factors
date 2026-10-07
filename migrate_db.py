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
    # Timing probe only: `_score` has a CHECK in [0, 1], so the MTP speed panel
    # (m28) stores generation tok/s here with `_score` NULL.
    ("_tok_s", "REAL"),
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
            "_score", "_bad_rate", "_wall_time", "_tok_s", "_file_size",
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
        if r["model"] not in model_map or r.get("accuracy") is None:
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
        row = base_row(m, bench, float(r.get("temp", 0.3) or 0.3), r["score"], None)
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
        row = base_row("Ternary-Bonsai-27B-Q2_g64.gguf" if r.get("arm") == "ternary"
                       else "TODO.gguf", f"testfrac-{r.get('arm')}", 0.0, mf, None)
        row.update({"run_tag": "m41-testfrac", "rep": 1, "ctx_size": 4096,
                    "protocol": "mpl-raw-greedy-768 + per-test fraction",
                    "language": r.get("lang", "cpp"), "bench_family": "testfrac",
                    "source_file": "m41_summary.jsonl"})
        insert(con, row); n += 1
    return n


def ingest_m36(con):
    return _ingest_bfcl_mt(con, ".wrapup/m36_summary.jsonl", "m36-bonsai-ternary-mt2",
                           "m36_summary.jsonl")


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
                       r["temp"], r["score"], None)
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
        ("m50", ingest_m50), ("m51", ingest_m51), ("m52", ingest_m52),
        ("m36", ingest_m36),
        ("m33", ingest_m33), ("m35", ingest_m35),
        ("m38", ingest_m38), ("m39", ingest_m39),
    ]
    tally = {}
    for label, tag, fn in ONCE:
        tally[label] = once(tag, fn)
    for label, fn in REFRESH:
        tally[label] = fn(con)
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
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


BONSAI_MODELS = {
    "bonsai-q2g64": "Ternary-Bonsai-27B-Q2_g64.gguf",
}


def ingest_m21(con):
    # Refresh semantics: the panel appends one row per language, so a checkpoint
    # taken mid-panel must replace rather than lock in the partial row set.
    con.execute("DELETE FROM experiments WHERE run_tag = ?", ("m21-bonsai-ternary",))
    return ingest_mpl(con, ".wrapup/m21_summary.jsonl", "m21-bonsai-ternary",
                      "m21_summary.jsonl", model_map=BONSAI_MODELS)


if __name__ == "__main__":
    main()
