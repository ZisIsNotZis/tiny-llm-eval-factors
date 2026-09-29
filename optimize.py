#!/usr/bin/env python3
"""Config optimizer for LLM benchmarks.

Searches over quant × KV cache configurations for a given model and
GPU memory budget, ranks by predicted score, and filters by latency.

Usage:
  uv run python optimize.py --family Qwen3.6 --size 27 --gpu-mem 24 --ctx 8192
  uv run python optimize.py --family Qwen3.5 --size 4  --gpu-mem 24 --max-latency 120
  uv run python optimize.py --family gemma-4  --size 12 --gpu-mem 24 --reasoning auto
  uv run python optimize.py --family Qwen3.6 --size 27 --list-sizes  # show available sizes
"""
from __future__ import annotations

import argparse
import importlib.util
import math
import sqlite3
import sys
from pathlib import Path
from pathlib import Path

import numpy as np
from sklearn.linear_model import LinearRegression

HERE = Path(__file__).resolve().parent

# ── quant profiles (name, quant_ratio, tier) ──────────────────────────
QUANT_CONFIGS: list[tuple[str, float, str]] = [
    ("IQ1_S",      0.313, "extreme"),
    ("IQ1_M",      0.325, "extreme"),
    ("IQ2_XXS",    0.354, "low"),
    ("IQ2_M",      0.408, "low"),
    ("IQ3_S",      0.446, "medium"),
    ("IQ3_XXS",    0.452, "medium"),
    ("Q2_K_XL",    0.493, "medium"),
    ("IQ4_XS",     0.533, "medium"),
    ("IQ4_NL",     0.530, "medium"),
    ("Q3_K_XL",    0.573, "medium"),
    ("Q4_K_S",     0.627, "high"),
    ("Q4_K_XL",    0.663, "high"),
    ("Q5_K_XL",    0.768, "high"),
]
TIER_RANK = {"extreme": 0, "low": 1, "medium": 2, "high": 3}

# ── KV cache profiles (label, k_ratio, v_ratio) ───────────────────────
KV_CONFIGS: list[tuple[str, float, float]] = [
    ("q4_0/q4_0", 0.34375, 0.34375),
    ("q4_0/q5_1", 0.34375, 0.375),
    ("q4_0/q8_0", 0.34375, 0.53125),
    ("q4_0/f16",  0.34375, 1.0),
    ("q5_1/q5_1", 0.375,   0.375),
    ("q5_1/q8_0", 0.375,   0.53125),
    ("q5_1/f16",  0.375,   1.0),
    ("q8_0/q8_0", 0.53125, 0.53125),
    ("q8_0/q5_1", 0.53125, 0.375),
    ("q8_0/f16",  0.53125, 1.0),
    ("f16/f16",   1.0,     1.0),
]


def _normalise_size(raw: float) -> float:
    """Handle the MB-vs-GB size bug in the database."""
    return raw / 1000 if raw >= 100 else raw


def _load_score_model():
    spec = importlib.util.spec_from_file_location("score_model", HERE / "score_model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fit_time_model(db_path: str):
    """Fit log(wall_time) ~ log(size) + quant_ratio + k_ratio + v_ratio + reasoning + bench."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT __size, __quant_ratio, __k_ratio, __v_ratio,
               CASE WHEN reasoning = 'off' THEN 0 ELSE 1 END,
               _bench, _wall_time
        FROM experiments
        WHERE _wall_time IS NOT NULL AND __quant_ratio > 0.1 AND _wall_time > 0
    """).fetchall()
    conn.close()

    X, y = [], []
    for r in rows:
        s = _normalise_size(r[0])
        if s < 0.1:
            continue
        X.append([math.log(s), r[1], r[2], r[3], r[4], 1.0 if r[5] == "mbpp" else 0.0])
        y.append(math.log(r[6]))

    Xa, ya = np.array(X), np.array(y)
    model = LinearRegression().fit(Xa, ya)
    rmse = math.sqrt(np.mean((model.predict(Xa) - ya) ** 2))
    return model, rmse


def estimate_vram_gb(
    size_b: float, quant_ratio: float,
    k_ratio: float, v_ratio: float,
    ctx_size: int, overhead: float = 2.0,
) -> float:
    """VRAM estimate: model weights + KV cache + overhead.

    Model weights: size_b * quant_ratio (quant_ratio is bytes-per-param).
    KV cache heuristic: calibrated from known architectures.
      KV ∝ n_layers * d_model * ctx * (k+v)/2
      For typical transformers, KV scales roughly as ~sqrt(size_b).
      Calibrated: 27B q8/q8 ctx=8192 → ~3.5 GB.
    Overhead: ~2 GB for framework, buffers, etc.
    """
    weights = size_b * quant_ratio
    # KV heuristic: 3.5 * sqrt(size_b / 27) * (ctx/8192) * ((k+v)/2 / 0.53125)
    kv = 3.5 * math.sqrt(size_b / 27.0) * (ctx_size / 8192.0) * ((k_ratio + v_ratio) / 2.0 / 0.53125)
    return weights + kv + overhead


def _get_family_sizes(db_path: str) -> dict[str, list[float]]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT __model, __size FROM experiments WHERE __quant_ratio > 0.1"
    ).fetchall()
    conn.close()
    fams: dict[str, set[float]] = {}
    for model, s in rows:
        fams.setdefault(model, set()).add(_normalise_size(s))
    return {f: sorted(v) for f, v in fams.items()}


# ══════════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(description="LLM benchmark config optimizer")
    p.add_argument("--family", default="Qwen3.6", help="Model family name")
    p.add_argument("--size", type=float, default=None,
                   help="Model size in billions of params (auto-detected if omitted)")
    p.add_argument("--gpu-mem", type=float, default=24.0, help="GPU VRAM in GB")
    p.add_argument("--ctx", "--ctx-size", type=int, default=8192, dest="ctx",
                   help="Context window size")
    p.add_argument("--max-latency", type=float, default=None,
                   help="Max wall time in seconds")
    p.add_argument("--reasoning", choices=["off", "auto"], default="off")
    p.add_argument("--dataset", choices=["humaneval", "mbpp"], default="humaneval")
    p.add_argument("--min-tier", choices=list(TIER_RANK), default="low",
                   help="Minimum quant tier")
    p.add_argument("--top-n", type=int, default=10, help="Configs to show")
    p.add_argument("--db", default=str(HERE / "experiments.sqlite"),
                   help="Path to experiments.sqlite")
    p.add_argument("--list-sizes", action="store_true",
                   help="Show available sizes for the family and exit")
    args = p.parse_args()

    # ── load models ───────────────────────────────────────────────────
    print("Loading score model...", end=" ", flush=True)
    sm = _load_score_model()
    print("done")

    print("Fitting time model...", end=" ", flush=True)
    time_model, rmse_log = _fit_time_model(args.db)
    print(f"done (RMSE(log)={rmse_log:.3f}, ~{math.expm1(rmse_log) * 100:.0f}% error)")

    # ── resolve size ──────────────────────────────────────────────────
    fam_sizes = _get_family_sizes(args.db)
    if args.family not in fam_sizes:
        print(f"Error: family '{args.family}' not found.")
        print("Available families:", file=sys.stderr)
        for f in sorted(fam_sizes):
            print(f"  {f}  sizes={fam_sizes[f]}", file=sys.stderr)
        sys.exit(1)

    avail = fam_sizes[args.family]
    if args.list_sizes:
        print(f"Available sizes for {args.family}: {avail}")
        return

    size_b = args.size if args.size is not None else avail[0]  # smallest
    if size_b not in avail:
        print(f"Warning: size {size_b}B not in observed sizes {avail} for {args.family}")

    # ── filter quants by tier ────────────────────────────────────────
    min_tier = TIER_RANK[args.min_tier]
    quants = [(n, qr) for n, qr, t in QUANT_CONFIGS if TIER_RANK[t] >= min_tier]

    # ── enumerate & score ────────────────────────────────────────────
    reasoning_int = 0 if args.reasoning == "off" else 1
    is_mbpp = 1 if args.dataset == "mbpp" else 0
    scored = []

    for qname, qr in quants:
        for kvname, kr, vr in KV_CONFIGS:
            vram = estimate_vram_gb(size_b, qr, kr, vr, args.ctx)
            if vram > args.gpu_mem:
                continue

            t_sec = math.exp(time_model.predict(
                np.array([[math.log(size_b), qr, kr, vr, reasoning_int, is_mbpp]])
            )[0])
            if args.max_latency and t_sec > args.max_latency:
                continue

            score = sm.predict_score(
                family=args.family, dataset=args.dataset,
                size_b=size_b, quant_ratio=qr,
                k_ratio=kr, v_ratio=vr, reasoning=args.reasoning,
            )
            scored.append((score, vram, t_sec, qname, kvname))

    scored.sort(key=lambda x: -x[0])

    # ── output ────────────────────────────────────────────────────────
    print(f"\n{args.family}  {size_b:.1f}B  |  "
          f"{args.gpu_mem}GB GPU  ctx={args.ctx}  "
          f"reasoning={args.reasoning}  {args.dataset}")
    print()

    if not scored:
        print("No config fits within constraints. Try a larger GPU or smaller model.")
        print(f"  (smallest model weight alone: {size_b * quants[0][1]:.1f}GB "
              f"+ KV ~{estimate_vram_gb(size_b, quants[0][1], 0.53125, 0.53125, args.ctx) - size_b * quants[0][1] - 2.0:.1f}GB + 2GB overhead)")
        sys.exit(1)

    header = f"{'Rank':>4}  {'Score':>6}  {'VRAM':>5}  {'Time':>7}  {'Quant':<12}  {'KV':<12}"
    print(header)
    print("─" * len(header))
    for i, (score, vram, t_sec, qname, kvname) in enumerate(scored[: args.top_n]):
        t_str = f"{t_sec:.0f}s" if t_sec < 3600 else f"{t_sec / 3600:.1f}h"
        print(f"{i + 1:>4}  {score:.4f}  {vram:.1f}GB  {t_str:>7}  {qname:<12}  {kvname:<12}")

    print(f"\n{len(scored)} configs within budget  |  tier≥{args.min_tier}")
    if args.max_latency:
        print(f"latency ≤ {args.max_latency}s")


if __name__ == "__main__":
    main()