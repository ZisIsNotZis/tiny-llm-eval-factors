#!/usr/bin/env python3
"""Generate score_model.py (importable predict_score) and projections CSV
from the canonical refit (refit_results.json)."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

OUT_DIR = Path("/home/z/hf/research")
RESULTS = json.loads((OUT_DIR / "refit_results.json").read_text())


def main() -> None:
    c = RESULTS["coefs"]
    caps = (RESULTS["cap_size"], RESULTS["cap_act"], RESULTS["cap_quant"])
    w_family = c["w_family"]
    d_dataset = c["d_dataset"]
    br, bt, btopk, bkvk, bkvv = (c[k] for k in ("br", "bt", "btopk", "bkvk", "bkvv"))
    k_size, k_act, k_quant, a_qat = (c[k] for k in ("k_size", "k_act", "k_quant", "a_qat"))
    n_dedup = RESULTS["n_dedup"]
    cv = RESULTS["cv_checkpoint"]
    cv_fam = RESULTS["cv_family"]
    cv_rand = RESULTS["cv_random"]
    ridge = RESULTS["ridge_cv_rmse"]

    # fallback for unseen families: average family weight (closer to "typical"
    # than the reference level of 0)
    avg_w = float(sum(w_family.values()) / len(w_family))

    caps_str = repr({"size": caps[0], "act": caps[1], "quant": caps[2]})
    fam_keys_sample = list(w_family.keys())[:6]

    mod = f'''#!/usr/bin/env python3
"""Canonical score formula from the full-data refit ({n_dedup} rows, {caps[0]}/{caps[1]}/{caps[2]} caps).

pred = 1 - exp(-raw)
raw  = exp(linear) * cap_size(size_b) * cap_act(act_ratio) * cap_quant(quant_ratio) * (1 + a_qat*qat)
linear = w[family] + d[dataset] + br*reason_off + bt*temp + btopk*log(top_k)
         + bkvk*k_ratio + bkvv*v_ratio

CV RMSE: checkpoint-held-out {cv:.4f} | family-held-out {cv_fam:.4f} | random {cv_rand:.4f}
(ridge reference on the same splits: {ridge:.4f}; irreducible floor from unrecorded ctx ~0.088)

Usage:
  from score_model import predict_score
  s = predict_score(size_b=27.0, quant_ratio=0.548, k_ratio=0.53125, v_ratio=0.53125,
                    family="Qwen3.6", dataset="humaneval", reasoning="off")
"""
from __future__ import annotations
import math

CAPS = {caps_str}

def cap_rational(x: float, k: float) -> float:
    return x / (x + k)

def cap_exp(x: float, k: float) -> float:
    return 1.0 - math.exp(-k * x)

def cap_tanh(x: float, k: float) -> float:
    return math.tanh(k * x)

def _cap(kind: str, x: float, k: float) -> float:
    return {{"rational": cap_rational, "exp": cap_exp, "tanh": cap_tanh}}[kind](x, k)

W_FAMILY = {w_family!r}
D_DATASET = {d_dataset!r}
BR = {br:.6f}
BT = {bt:.6f}
BTOPK = {btopk:.6f}
BK_VK = {bkvk:.6f}
BK_VV = {bkvv:.6f}
K_SIZE = {k_size:.6f}
K_ACT = {k_act:.6f}
K_QUANT = {k_quant:.6f}
A_QAT = {a_qat:.6f}
MEAN_FAMILY_W = {avg_w:.4f}

def predict_score(
    *,
    family: str = "unseen",
    dataset: str = "humaneval",
    size_b: float,
    activated_size_b: float | None = None,
    quant_ratio: float,
    k_ratio: float = 0.53125,
    v_ratio: float = 0.53125,
    qat: float = 0.0,
    reasoning: str = "off",
    temp: float = 0.0,
    top_k: float = 40.0,
) -> float:
    """Predicted pass@1_plus on the given benchmark.

    family: use one of {fam_keys_sample!r} ...; "unseen" uses the mean
      family weight (best guess for a family not in the fit).
    reasoning: "off" / "auto" (only these two are recorded in the data).
    size_b / quant_ratio / k_ratio / v_ratio: bytes-per-param ratios (fp16=1.0).
    """
    w = W_FAMILY.get(family, MEAN_FAMILY_W)
    d = D_DATASET.get(dataset, 0.0)
    act_ratio = activated_size_b / size_b if activated_size_b else 1.0
    reason_off = 1.0 if reasoning == "off" else 0.0
    linear = (
        w + d + BR * reason_off + BT * temp + BTOPK * math.log(top_k)
        + BK_VK * k_ratio + BK_VV * v_ratio
    )
    linear = max(-40.0, min(18.0, linear))
    raw = (
        math.exp(linear)
        * _cap(CAPS["size"], size_b, K_SIZE)
        * _cap(CAPS["act"], act_ratio, K_ACT)
        * _cap(CAPS["quant"], quant_ratio, K_QUANT)
        * (1.0 + A_QAT * qat)
    )
    return 1.0 - math.exp(-raw)
'''

    (OUT_DIR / "score_model.py").write_text(mod)
    print("wrote score_model.py")

    # ---- end-to-end effect projections ----
    syspath = OUT_DIR
    import importlib.util

    spec = importlib.util.spec_from_file_location("score_model", OUT_DIR / "score_model.py")
    sm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sm)

    rows = []
    # (a) weight-quant ladder at fixed size, per family
    for fam, size in (("Qwen3.6", 27.0), ("Qwen3.5", 4.0), ("gemma-4", 2.0)):
        base = {"size_b": size, "k_ratio": 0.53125, "v_ratio": 0.53125,
                "dataset": "humaneval", "reasoning": "off"}
        for qr, qname in ((0.354, "IQ2_XXS"), (0.446, "Q2_K_XL"), (0.548, "Q3_K_XL"), (0.663, "Q4_K_XL")):
            rows.append(("quant_ladder", fam, f"{size}B-{qname}", round(sm.predict_score(family=fam, quant_ratio=qr, **base), 4)))
    # (b) KV shift at Q3, fixed size
    for fam, size in (("Qwen3.6", 27.0), ("Qwen3.5", 4.0)):
        base = {"size_b": size, "quant_ratio": 0.548, "dataset": "humaneval", "reasoning": "off"}
        rows.append(("kv_shift", fam, "q8/q8", round(sm.predict_score(family=fam, k_ratio=0.53125, v_ratio=0.53125, **base), 4)))
        rows.append(("kv_shift", fam, "q8/q5_1", round(sm.predict_score(family=fam, k_ratio=0.53125, v_ratio=0.375, **base), 4)))
        rows.append(("kv_shift", fam, "f16/f16", round(sm.predict_score(family=fam, k_ratio=1.0, v_ratio=1.0, **base), 4)))
    # (c) reasoning off vs auto
    for fam, size in (("Qwen3.6", 27.0), ("Qwen3.5", 4.0)):
        base = {"size_b": size, "quant_ratio": 0.548, "k_ratio": 0.53125, "v_ratio": 0.53125, "dataset": "humaneval"}
        rows.append(("reasoning", fam, "off", round(sm.predict_score(family=fam, reasoning="off", **base), 4)))
        rows.append(("reasoning", fam, "auto", round(sm.predict_score(family=fam, reasoning="auto", **base), 4)))
    # (d) size sweep at matched quant (Q4) for a generic family
    base = {"quant_ratio": 0.663, "k_ratio": 0.53125, "v_ratio": 0.53125,
            "dataset": "humaneval", "reasoning": "off"}
    for size in (2.0, 9.0, 27.0, 35.0):
        rows.append(("size_sweep_Q4", "Qwen3.6", f"{size}B", round(sm.predict_score(family="Qwen3.6", size_b=size, **base), 4)))
    rows.append(("size_sweep_Q4", "unseen-family", "2B", round(sm.predict_score(family="unseen", size_b=2.0, **base), 4)))
    rows.append(("size_sweep_Q4", "unseen-family", "27B", round(sm.predict_score(family="unseen", size_b=27.0, **base), 4)))

    with (OUT_DIR / "projections.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["group", "family", "setting", "pred_score"])
        w.writerows(rows)
    print("wrote projections.csv")


if __name__ == "__main__":
    main()
