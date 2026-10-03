#!/usr/bin/env python3
"""Tier-2A: does MoE *active* parameter count predict quantised MultiPL-E score
better than *total* parameter count?

Read-only analysis of experiments.sqlite (protocol MultiPL-E raw-greedy-768).
Model structure (expert_count / expert_used) is read from GGUF metadata, the
only authoritative source we have.

Writes .wrapup/moe_structure.json and prints a text report.

Protocol discipline (RESEARCH_METHOD.md §3):
  * one protocol only: multipl-e-raw-greedy-768
  * gemma-4 under *raw* completion is a verified harness failure (see
    t4_gemma_repair.log: all raw variants probe 0/40; completions are 2-5x
    longer markdown reasoning prose, not code). Those rows are marked
    harness_invalid and excluded from the fits, not silently dropped.
"""
from __future__ import annotations

import json
import math
import sqlite3
import struct
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path("/home/z/hf/research")
WR = ROOT / ".wrapup"
DB = ROOT / "experiments.sqlite"
OUT = WR / "moe_structure.json"

# ---------------------------------------------------------------- GGUF metadata


def _read_str(f):
    n = struct.unpack("<Q", f.read(8))[0]
    return f.read(n).decode("utf-8", "replace")


def _read_val(f, t):
    if t == 0: return struct.unpack("<B", f.read(1))[0]
    if t == 1: return struct.unpack("<b", f.read(1))[0]
    if t == 2: return struct.unpack("<H", f.read(2))[0]
    if t == 3: return struct.unpack("<h", f.read(2))[0]
    if t == 4: return struct.unpack("<I", f.read(4))[0]
    if t == 5: return struct.unpack("<i", f.read(4))[0]
    if t == 6: return struct.unpack("<f", f.read(4))[0]
    if t == 7: return struct.unpack("<B", f.read(1))[0]
    if t == 8: return _read_str(f)
    if t == 9:
        et = struct.unpack("<I", f.read(4))[0]
        n = struct.unpack("<Q", f.read(8))[0]
        return [_read_val(f, et) for _ in range(n)]
    if t == 10: return struct.unpack("<Q", f.read(8))[0]
    if t == 11: return struct.unpack("<q", f.read(8))[0]
    if t == 12: return struct.unpack("<d", f.read(8))[0]
    raise ValueError(t)


def gguf_structure(path: str) -> dict:
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return {}
            struct.unpack("<I", f.read(4))
            struct.unpack("<Q", f.read(8))
            nkv = struct.unpack("<Q", f.read(8))[0]
            meta = {}
            for _ in range(nkv):
                k = _read_str(f)
                t = struct.unpack("<I", f.read(4))[0]
                meta[k] = _read_val(f, t)
    except OSError:
        return {}
    arch = meta.get("general.architecture", "")
    def one(suffix):
        for k, v in meta.items():
            if k.endswith(suffix):
                return v
        return None
    return {
        "arch": arch,
        "expert_count": int(one(".expert_count") or 0),
        "expert_used": int(one(".expert_used_count") or 0),
        "block_count": int(one(".block_count") or 0),
    }


# ---------------------------------------------------------------- dataset

# gemma-4 under *raw* completion is a verified harness failure for the models whose
# template primes a reasoning channel: t4_gemma_repair.log shows all raw probe
# variants scoring 0/40, and the m10 completions are 2-5x longer markdown reasoning
# prose (fence/bold present, no code) for 12B and 26B-A4B. The smaller gemma-4
# dense models (E2B/E4B) do NOT show it -- their raw scores are 0.19-0.74, i.e.
# not the harness floor -- so they stay in. Flagged by exact file, not by family.
HARNESS_INVALID = {
    "gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf",
    "gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf",
}


def load_points() -> list[dict]:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = list(con.execute(
        """select model, __model, __size, __activation_size, __quant, __quant_ratio,
                  _score, language, run_tag
           from experiments where protocol='multipl-e-raw-greedy-768'"""))
    # dedup (model, quant, lang): identical duplicated runs keep one value
    cells = defaultdict(list)
    for r in rows:
        if r["language"] in ("cpp", "py"):
            cells[(r["model"], r["__quant"], r["language"])].append(r)
    models = sorted({k[0] for k in cells})
    struct = {m: gguf_structure(f"/home/z/hf/{m}") for m in models}
    by_mq = defaultdict(dict)
    for (m, q, lang), rs in cells.items():
        vals = [x["_score"] for x in rs]
        by_mq[(m, q)][lang] = sum(vals) / len(vals)
    points = []
    for (m, q), lang in by_mq.items():
        if "cpp" not in lang or "py" not in lang:
            continue
        r0 = cells[(m, q, "cpp")][0]
        s = struct[m]
        n = 322
        passes = round((lang["cpp"] + lang["py"]) / 2 * 161) * 2  # pooled cpp+py
        p = (lang["cpp"] + lang["py"]) / 2
        se = math.sqrt(max(p * (1 - p), 1e-9) / 161) / math.sqrt(2)
        points.append({
            "model": m, "moe_model": r0["__model"], "quant": q,
            "size": r0["__size"], "active": r0["__activation_size"],
            "quant_ratio": r0["__quant_ratio"],
            "cpp": round(lang["cpp"], 4), "py": round(lang["py"], 4),
            "score": round(p, 4), "se": round(se, 4), "n": n,
            "is_moe": s["expert_count"] > 0,
            "expert_count": s["expert_count"], "expert_used": s["expert_used"],
            "block_count": s["block_count"], "arch": s["arch"],
            "harness_invalid": m in HARNESS_INVALID,
        })
    points.sort(key=lambda d: (d["size"], d["quant"]))
    return points


# ---------------------------------------------------------------- OLS

def ols(y, X):
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, k = X.shape
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = n - k
    rss = float(resid @ resid)
    sigma2 = rss / dof
    # cov = sigma2 (X'X)^-1
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.clip(np.diag(xtx_inv) * sigma2, 0, None))
    t = beta / np.where(se == 0, np.nan, se)
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - rss / tss if tss > 0 else float("nan")
    adj = 1 - (1 - r2) * (n - 1) / dof if dof > 0 else float("nan")
    ll = -0.5 * n * (math.log(2 * math.pi * sigma2) + 1) if sigma2 > 0 else float("-inf")
    aic = 2 * k - 2 * ll
    bic = k * math.log(n) - 2 * ll
    return {"beta": beta.tolist(), "se": se.tolist(), "t": t.tolist(),
            "r2": r2, "adj_r2": adj, "aic": aic, "bic": bic, "rss": rss, "n": n, "k": k}


def fit(name, y, feats, points):
    X = [[1.0] + [f(p) for f in feats] for p in points]
    m = ols(y, X)
    m["name"] = name
    m["features"] = ["const"] + [f.__name__ for f in feats]
    return m


def ln_size(p):     return math.log(p["size"])
def ln_active(p):   return math.log(p["active"])
def ln_quant(p):    return math.log(p["quant_ratio"])
def is_moe(p):      return 1.0 if p["is_moe"] else 0.0
def ln_experts(p):  return math.log(1 + p["expert_count"])
def used_frac(p):   return p["expert_used"] / p["expert_count"] if p["expert_count"] else 0.0
def moe_x_quant(p): return ln_quant(p) if p["is_moe"] else 0.0


def vif(points):
    # 2-variable VIF only (total vs active)
    a = np.array([ln_size(p) for p in points])
    b = np.array([ln_active(p) for p in points])
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    r = float(np.corrcoef(a, b)[0, 1])
    if abs(r) >= 1:
        return float("inf")
    return 1.0 / (1.0 - r * r)


def main():
    all_points = load_points()
    valid = [p for p in all_points if not p["harness_invalid"]]
    y_all = [p["score"] for p in valid]

    models = []
    models.append(fit("total_only", y_all, [ln_size, ln_quant], valid))
    models.append(fit("active_only", y_all, [ln_active, ln_quant], valid))
    models.append(fit("total+active", y_all, [ln_size, ln_active, ln_quant], valid))
    models.append(fit("total+moe", y_all, [ln_size, ln_quant, is_moe], valid))
    models.append(fit("active+moe+experts", y_all, [ln_active, ln_quant, is_moe, ln_experts], valid))
    models.append(fit("total+moe+moe_x_quant", y_all,
                      [ln_size, ln_quant, is_moe, moe_x_quant], valid))
    models.append(fit("total+active+moe+experts", y_all,
                      [ln_size, ln_active, ln_quant, is_moe, ln_experts], valid))

    # leave-one-family-out CV (families with >=2 points exercise size, singletons
    # still test prediction). Compare total_only vs active_only vs combined.
    fams = sorted({p["moe_model"] for p in valid})
    def loo_family(feats):
        preds, obs = [], []
        for fam in fams:
            tr = [p for p in valid if p["moe_model"] != fam]
            te = [p for p in valid if p["moe_model"] == fam]
            if not tr or not te:
                continue
            X = [[1.0] + [f(p) for f in feats] for p in tr]
            beta, *_ = np.linalg.lstsq(np.asarray(X, float),
                                       np.asarray([p["score"] for p in tr], float), rcond=None)
            for p in te:
                preds.append(sum(b * v for b, v in zip(beta, [1.0] + [f(p) for f in feats])))
                obs.append(p["score"])
        preds, obs = np.array(preds), np.array(obs)
        return float(np.sqrt(np.mean((preds - obs) ** 2)))

    cv = {
        "total_only": loo_family([ln_size, ln_quant]),
        "active_only": loo_family([ln_active, ln_quant]),
        "total+active": loo_family([ln_size, ln_active, ln_quant]),
    }

    # dense reference curve: fit dense-only, then locate each MoE on it by
    # inverting for the "effective dense size" at its quant.
    dense = [p for p in valid if not p["is_moe"]]
    dense_model = fit("dense_size_curve", [p["score"] for p in dense],
                      [ln_size, ln_quant], dense)
    b = dense_model["beta"]
    moe_rows = []
    for p in valid:
        if not p["is_moe"]:
            continue
        # invert: score = b0 + b1*ln(S) + b2*ln(q)  ->  S = exp((score-b0-b2*ln q)/b1)
        eff = math.exp((p["score"] - b[0] - b[2] * ln_quant(p)) / b[1])
        moe_rows.append({
            "model": p["moe_model"] + "/" + p["quant"], "size": p["size"],
            "active": p["active"], "expert_count": p["expert_count"],
            "expert_used": p["expert_used"], "score": p["score"],
            "pred_from_total": round(float(np.exp(0)), 4) if False else None,
            "effective_dense_size_b": round(eff, 2),
            "eff_over_active": round(eff / p["active"], 2),
            "eff_over_total": round(eff / p["size"], 2),
        })

    out = {
        "protocol": "multipl-e-raw-greedy-768",
        "langs": ["cpp", "py"], "n_per_lang": 161,
        "n_points_all": len(all_points), "n_points_valid": len(valid),
        "harness_invalid_points": [f"{p['model']}/{p['quant']}" for p in all_points if p["harness_invalid"]],
        "anchors": all_points,
        "fits": models,
        "family_loo_rmse": cv,
        "vif_total_active": vif(valid),
        "dense_curve": dense_model,
        "moe_effective_dense_size": moe_rows,
    }
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)

    # ---- text report ----
    print(f"\npoints: {len(all_points)} total, {len(valid)} valid "
          f"({len(all_points)-len(valid)} gemma-4 raw flagged harness-invalid)")
    _v = vif(valid)
    print(f"\ncorr(length) total vs active = {math.sqrt(max(0.0, 1-1/_v)):.4f} (VIF {_v:.2f})")
    print("\n== OLS fits (score, pooled cpp+py, n per obs 322) ==")
    for m in models:
        print(f"  {m['name']:26s} adjR2={m['adj_r2']:.3f} AIC={m['aic']:6.1f} BIC={m['bic']:6.1f}")
        for nm, bb, ss, tt in zip(m["features"], m["beta"], m["se"], m["t"]):
            print(f"      {nm:10s} {bb: .4f} +- {ss:.4f}  t={tt: .2f}")
    print("\n== leave-one-family-out RMSE ==")
    for k, v in cv.items():
        print(f"  {k:16s} {v:.4f}")
    print("\n== MoE anchors: position on the dense size curve ==")
    for r in moe_rows:
        print(f"  {r['model']:34s} total={r['size']:>4}B active={r['active']:>3}B "
              f"E={r['expert_count']:>3}(top{r['expert_used']}) score={r['score']:.3f} "
              f"-> effective_dense={r['effective_dense_size_b']:>5}B "
              f"({r['eff_over_active']}x active, {r['eff_over_total']}x total)")


if __name__ == "__main__":
    main()
