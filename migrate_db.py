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


def ingest_m26(con):
    """M26 / M43 (QUEUE #17): Tier-2C dense vs MoE at matched TOTAL size.

    The 2026-10-02 panel (run_m26.sh) completed on disk but never wrote a summary;
    run_m43.sh rebuilt m26_summary.jsonl from the per-cell evals (CPU-only, no
    re-run). Chat protocol, greedy, ctx 4096 -- protocol is read per row so the
    chat-vs-raw distinction is preserved.
    """
    path = ".wrapup/m26_summary.jsonl"
    if not os.path.exists(path):
        print("  (no m26 summary)")
        return 0
    con.execute("DELETE FROM experiments WHERE run_tag = ?", ("m26-tier2c-dense-moe",))
    n = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["model"] not in M10_MODELS:
            continue
        lang = r["lang"]
        row = base_row(M10_MODELS[r["model"]], f"humaneval-{lang}", 0.0, r["score"], None)
        row.update({"run_tag": "m26-tier2c-dense-moe", "rep": 1, "ctx_size": 4096,
                    "parallel_slots": 1,
                    "protocol": r.get("protocol", "mpl-chat-nothink-greedy-768"),
                    "language": lang, "bench_family": "humaneval-multipl-e",
                    "max_tokens": 768, "source_file": "m26_summary.jsonl"})
        insert(con, row); n += 1
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
        print("  (no campaign results)"); return 0
    # drop previous campaign rows, then re-read (REFRESH semantics)
    con.execute("DELETE FROM experiments WHERE source_file LIKE 'mres/%'")
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
    con.execute("DELETE FROM experiments WHERE source_file LIKE 'mres/%-spec-%'")
    for path in sorted(glob.glob(".wrapup/mres/*-spec-*/spec_panel.json")):
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
    con.execute("DELETE FROM experiments WHERE source_file LIKE 'mres/%/variant_panel.json'")
    for path in sorted(glob.glob(".wrapup/mres/*/variant_panel.json")):
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
                    "temp": str(samp.get("temperature", 0.0)),
                    "top_p": "0.95", "top_k": str(samp.get("top_k", 40)),
                    "min_p": "0.05", "presence_penalty": "0.0",
                    "_bench": bench, "_score": val, "_bad_rate": None,
                    "_wall_time": None, "_tok_s": None, "_file_size": None,
                    "run_tag": tag, "rep": 1, "ctx_size": 8192, "parallel_slots": 1,
                    "seed": None,
                    "protocol": f"variant-{axis}-{label}-{'evalplus' if bench == 'humaneval' else 'lmeval'}",
                    "language": ("python" if bench == "humaneval" else None),
                    "bench_family": ("humaneval" if bench == "humaneval" else bench),
                    "max_tokens": (None if bench == "humaneval" else 1024),
                    "source_file": f"mres/{os.path.basename(os.path.dirname(path))}/variant_panel.json",
                    "completed_at": None, "n_items": nit, "limit_spec": "50",
                }
                insert(con, r)
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
        ("m55", ingest_m55), ("m56", ingest_m56), ("m57", ingest_m57),
        ("m58", ingest_m58), ("m59", ingest_m59), ("m60", ingest_m60),
        ("m50", ingest_m50), ("m51", ingest_m51), ("m52", ingest_m52),
        ("m54", ingest_m54), ("m26", ingest_m26), ("m44", ingest_m44),
        ("m36", ingest_m36),
        ("m33", ingest_m33), ("m35", ingest_m35),
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
