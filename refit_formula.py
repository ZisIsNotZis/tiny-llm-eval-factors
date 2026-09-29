#!/usr/bin/env python3
"""Full-data refit of the score formula against the current experiments schema.

Rebuilds the multiplicative structural model (`raw = exp(linear block) * caps`,
`pred = 1 - exp(-raw)`) on ALL usable rows in experiments.sqlite (humaneval+mbpp),
which has grown past the n=599 snapshot the previous formula conclusions were
written against.

Handles current-schema quirks:
  * __size/__activation_size stored in MB for the 230M/270M families -> /1000
  * reasoning is only 'off' / 'auto' in this schema ('on' is not recorded)
  * ctx_size is NOT stored, so multi-context runs collapse to duplicate factor
    vectors -> exact-duplicate rows (same factors AND same score) are deduped
  * __score_fix is the corrected target (differs from _score on 246 rows)

Outputs:
  * refit_results.json        canonical formula + CV + coefficients + bootstrap CI
  * refit_caps_search.csv     regenerates the missing .serial_formula_search_caps.csv
  * score_model.py            importable predict_score() with fitted coefficients
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from scipy.optimize import minimize
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold

DB_PATH = Path("/home/z/hf/research/experiments.sqlite")
OUT_DIR = Path("/home/z/hf/research")

# ----------------------------------------------------------------------------
# Cap families (each maps x in [0, inf) -> [0, 1), monotone, 0 at 0)
# ----------------------------------------------------------------------------


def cap_rational(x: np.ndarray, k: float) -> np.ndarray:
    return x / (x + k)


def cap_exp(x: np.ndarray, k: float) -> np.ndarray:
    return 1.0 - np.exp(-k * x)


def cap_tanh(x: np.ndarray, k: float) -> np.ndarray:
    return np.tanh(k * x)


def cap_saturator(q: np.ndarray, kq: float, q_sat: float = 0.5) -> np.ndarray:
    """Quant saturating prior from the original search: 0->0, no gain past q_sat."""
    q = np.clip(q, 0.0, 1.0)
    z = np.clip(q / q_sat, 0.0, 1.0)
    den = 1.0 - math.exp(-kq)
    if den < 1e-12:
        base = z
    else:
        base = (1.0 - np.exp(-kq * z)) / den
    return np.where(q >= q_sat, 1.0, base)


CAPS: dict[str, Callable[[np.ndarray, float], np.ndarray]] = {
    "rational": cap_rational,
    "exp": cap_exp,
    "tanh": cap_tanh,
    "saturator": cap_saturator,
}

# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------


def load_rows(db_path: Path) -> dict:
    """Pull usable rows from the current schema, normalized + deduped."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT model, __model, _bench, __size, __activation_size,
               __quant_ratio, __k_ratio, __v_ratio, __qat, reasoning,
               temp, top_p, top_k, min_p, presence_penalty, __score_fix
        FROM experiments
        WHERE _bench IN ('humaneval','mbpp')
          AND __score_fix IS NOT NULL
        """
    ).fetchall()
    con.close()

    data: list[dict] = []
    seen: set[tuple] = set()
    for r in rows:
        size = float(r["__size"])
        act = float(r["__activation_size"])
        # MB-stored families (230M / 270M) recorded in MB, everything else GB.
        if size >= 100:
            size /= 1000.0
        if act >= 100:
            act /= 1000.0
        if act > size:
            act = size  # guard against unit/encoding quirks
        act_ratio = act / size if size > 0 else 1.0

        # exact-duplicate rows (unrecorded ctx variance) collapse to one
        key = (
            r["model"], r["_bench"], r["reasoning"], float(r["temp"]),
            float(r["top_p"]), float(r["top_k"]), float(r["min_p"]),
            float(r["presence_penalty"]), float(r["__quant_ratio"]),
            float(r["__qat"]), float(r["__k_ratio"]), float(r["__v_ratio"]),
            float(r["__score_fix"]),
        )
        if key in seen:
            continue
        seen.add(key)

        data.append(
            {
                "model": r["model"],
                "family": r["__model"],
                "dataset": r["_bench"],
                "size_b": size,
                "act_ratio": act_ratio,
                "quant_ratio": float(r["__quant_ratio"]),
                "k_ratio": float(r["__k_ratio"]),
                "v_ratio": float(r["__v_ratio"]),
                "qat": float(r["__qat"]),
                "reason_off": 1.0 if r["reasoning"] == "off" else 0.0,
                "reason_auto": 1.0 if r["reasoning"] == "auto" else 0.0,
                "temp": float(r["temp"]),
                "log_top_k": math.log(float(r["top_k"])),
                "score": float(r["__score_fix"]),
            }
        )
    return {"rows": data, "n_raw": len(rows), "n_dedup": len(data)}


# ----------------------------------------------------------------------------
# Structural multiplicative model
# ----------------------------------------------------------------------------


def _linear_columns(
    model: "StructuralModel",
    family: np.ndarray,
    dataset: np.ndarray,
    reason_off: np.ndarray,
    temp: np.ndarray,
    log_top_k: np.ndarray,
    k_ratio: np.ndarray,
    v_ratio: np.ndarray,
) -> list[np.ndarray]:
    """One-hot + numeric columns for the linear block, matching theta layout."""
    cols: list[np.ndarray] = []
    for i in range(1, len(model.families)):  # family weights, ref=0
        cols.append((family == i).astype(float))
    for j in range(1, len(model.datasets)):  # dataset offsets, ref=0
        cols.append((dataset == j).astype(float))
    cols += [reason_off, temp, log_top_k, k_ratio, v_ratio]
    return cols


class StructuralModel:
    """pred = 1 - exp( -raw ), raw = exp(linear) * cap_size * cap_act * cap_quant * (1 + a_qat*qat)

    Params layout (theta):
      0..F-2   family weights (one-hot, reference family fixed at 0)
      F-1..F-1 dataset offset (humaneval reference fixed at 0)
      then: br, bt, btopk, bkvk, bkvv, k_size, k_act, k_quant, a_qat
    """

    def __init__(
        self,
        families: Sequence[str],
        datasets: Sequence[str],
        size_cap: str,
        act_cap: str,
        quant_cap: str,
    ) -> None:
        self.families = list(families)
        self.datasets = list(datasets)
        self.family_idx = {f: i for i, f in enumerate(self.families)}
        self.dataset_idx = {d: i for i, d in enumerate(self.datasets)}
        self.size_cap = size_cap
        self.act_cap = act_cap
        self.quant_cap = quant_cap
        self.n_linear = 5  # br, bt, btopk, bkvk, bkvv
        self.n_family = len(families) - 1
        self.n_dataset = len(datasets) - 1

    def n_params(self) -> int:
        return self.n_family + self.n_dataset + self.n_linear + 4  # k_size, k_act, k_quant, a_qat

    def unpack(self, theta: np.ndarray):
        w_fam = np.zeros(len(self.families))
        w_fam[1:] = theta[0 : self.n_family]
        d_dat = np.zeros(len(self.datasets))
        d_dat[1:] = theta[self.n_family : self.n_family + self.n_dataset]
        (br, bt, btopk, bkvk, bkvv) = theta[
            self.n_family + self.n_dataset : self.n_family + self.n_dataset + self.n_linear
        ]
        k_size, k_act, k_quant, a_qat = theta[-4:]
        return w_fam, d_dat, br, bt, btopk, bkvk, bkvv, k_size, k_act, k_quant, a_qat

    def predict(
        self,
        theta: np.ndarray,
        family: np.ndarray,
        dataset: np.ndarray,
        size_b: np.ndarray,
        act_ratio: np.ndarray,
        quant_ratio: np.ndarray,
        k_ratio: np.ndarray,
        v_ratio: np.ndarray,
        qat: np.ndarray,
        reason_off: np.ndarray,
        temp: np.ndarray,
        log_top_k: np.ndarray,
    ) -> np.ndarray:
        w_fam, d_dat, br, bt, btopk, bkvk, bkvv, k_size, k_act, k_quant, a_qat = self.unpack(theta)
        linear = np.clip(
            w_fam[family]
            + d_dat[dataset]
            + br * reason_off
            + bt * temp
            + btopk * log_top_k
            + bkvk * k_ratio
            + bkvv * v_ratio,
            -40.0,
            18.0,
        )
        raw = (
            np.exp(linear)
            * CAPS[self.size_cap](size_b, k_size)
            * CAPS[self.act_cap](act_ratio, k_act)
            * CAPS[self.quant_cap](quant_ratio, k_quant)
            * (1.0 + a_qat * qat)
        )
        return 1.0 - np.exp(-raw)

    def gradient(
        self,
        theta: np.ndarray,
        score: np.ndarray,
        family: np.ndarray,
        dataset: np.ndarray,
        size_b: np.ndarray,
        act_ratio: np.ndarray,
        quant_ratio: np.ndarray,
        k_ratio: np.ndarray,
        v_ratio: np.ndarray,
        qat: np.ndarray,
        reason_off: np.ndarray,
        temp: np.ndarray,
        log_top_k: np.ndarray,
    ) -> np.ndarray:
        """Gradient of MSE w.r.t. theta.

        Linear part analytic; cap-k / qat params via central finite difference on
        the (cheap) prediction, avoiding a full 40-dim finite-diff jacobian.
        """
        w_fam, d_dat, br, bt, btopk, bkvk, bkvv, k_size, k_act, k_quant, a_qat = self.unpack(theta)
        linear = np.clip(
            w_fam[family]
            + d_dat[dataset]
            + br * reason_off
            + bt * temp
            + btopk * log_top_k
            + bkvk * k_ratio
            + bkvv * v_ratio,
            -40.0,
            18.0,
        )
        cs = CAPS[self.size_cap](size_b, k_size)
        ca = CAPS[self.act_cap](act_ratio, k_act)
        cq = CAPS[self.quant_cap](quant_ratio, k_quant)
        qgate = 1.0 + a_qat * qat
        raw = np.exp(linear) * cs * ca * cq * qgate
        pred = 1.0 - np.exp(-raw)
        resid = 2.0 * (pred - score) * (1.0 - pred)

        n = score.size
        g = resid * raw  # dMSE/draw per row (chain-rule weight for linear block)
        grad = np.zeros(theta.shape)
        # family weights: theta index i corresponds to family i+1 (ref=0)
        fam_contrib = np.bincount(family, weights=g, minlength=len(self.families))
        grad[: self.n_family] = fam_contrib[1:] / n
        dat_contrib = np.bincount(dataset, weights=g, minlength=len(self.datasets))
        grad[self.n_family : self.n_family + self.n_dataset] = dat_contrib[1:] / n
        # shared linear terms (br, bt, btopk, bkvk, bkvv)
        off = self.n_family + self.n_dataset
        grad[off : off + self.n_linear] = (
            np.array(
                [
                    np.sum(g * reason_off),
                    np.sum(g * temp),
                    np.sum(g * log_top_k),
                    np.sum(g * k_ratio),
                    np.sum(g * v_ratio),
                ]
            )
            / n
        )
        # cap params + a_qat by finite difference on prediction
        eps = 1e-4
        for j, capkey in ((0, "size"), (1, "act"), (2, "quant")):
            t = theta.copy()
            t[-4 + j] += eps
            p_hi = self.predict(t, family=family, dataset=dataset, size_b=size_b,
                                act_ratio=act_ratio, quant_ratio=quant_ratio, k_ratio=k_ratio,
                                v_ratio=v_ratio, qat=qat, reason_off=reason_off, temp=temp,
                                log_top_k=log_top_k)
            t = theta.copy()
            t[-4 + j] -= eps
            p_lo = self.predict(t, family=family, dataset=dataset, size_b=size_b,
                                act_ratio=act_ratio, quant_ratio=quant_ratio, k_ratio=k_ratio,
                                v_ratio=v_ratio, qat=qat, reason_off=reason_off, temp=temp,
                                log_top_k=log_top_k)
            grad[-4 + j] = np.sum(2.0 * (pred - score) * (p_hi - p_lo) / (2.0 * eps)) / n
        # a_qat
        t = theta.copy()
        t[-1] += eps
        p_hi = self.predict(t, family=family, dataset=dataset, size_b=size_b,
                            act_ratio=act_ratio, quant_ratio=quant_ratio, k_ratio=k_ratio,
                            v_ratio=v_ratio, qat=qat, reason_off=reason_off, temp=temp,
                            log_top_k=log_top_k)
        t = theta.copy()
        t[-1] -= eps
        p_lo = self.predict(t, family=family, dataset=dataset, size_b=size_b,
                            act_ratio=act_ratio, quant_ratio=quant_ratio, k_ratio=k_ratio,
                            v_ratio=v_ratio, qat=qat, reason_off=reason_off, temp=temp,
                            log_top_k=log_top_k)
        grad[-1] = np.sum(2.0 * (pred - score) * (p_hi - p_lo) / (2.0 * eps)) / n
        return grad


def build_X(data: list[dict], model: StructuralModel):
    fam = np.array([model.family_idx[d["family"]] for d in data], dtype=int)
    dat = np.array([model.dataset_idx[d["dataset"]] for d in data], dtype=int)
    return {
        "family": fam,
        "dataset": dat,
        "size_b": np.array([d["size_b"] for d in data], dtype=float),
        "act_ratio": np.array([d["act_ratio"] for d in data], dtype=float),
        "quant_ratio": np.array([d["quant_ratio"] for d in data], dtype=float),
        "k_ratio": np.array([d["k_ratio"] for d in data], dtype=float),
        "v_ratio": np.array([d["v_ratio"] for d in data], dtype=float),
        "qat": np.array([d["qat"] for d in data], dtype=float),
        "reason_off": np.array([d["reason_off"] for d in data], dtype=float),
        "temp": np.array([d["temp"] for d in data], dtype=float),
        "log_top_k": np.array([d["log_top_k"] for d in data], dtype=float),
        "score": np.array([d["score"] for d in data], dtype=float),
    }


def fit_structural(
    model: StructuralModel,
    X: dict,
    groups: np.ndarray,
    lam_family: float = 0.0,
    seed: int = 0,
    restarts: int = 2,
    maxiter: int = 5000,
    do_cv: bool = True,
) -> dict:
    """Fit on all data (L-BFGS-B). Optionally 5-fold grouped CV RMSE."""
    score = X["score"]
    rng = np.random.default_rng(seed)

    xw = {k: X[k] for k in (
        "family", "dataset", "size_b", "act_ratio", "quant_ratio",
        "k_ratio", "v_ratio", "qat", "reason_off", "temp", "log_top_k")}

    def objective(theta: np.ndarray) -> float:
        pred = model.predict(theta, **xw)
        mse = float(np.mean((pred - score) ** 2))
        w_fam, *_ = model.unpack(theta)
        mse += lam_family * float(np.mean(w_fam[1:] ** 2))
        return mse

    def grad(theta: np.ndarray) -> np.ndarray:
        g = model.gradient(theta, score, **xw)
        g[: model.n_family] += 2.0 * lam_family * theta[: model.n_family] / model.n_family
        return g

    best = None
    for init_seed in (seed, seed + 1)[:restarts]:
        rng2 = np.random.default_rng(init_seed)
        x0 = np.zeros(model.n_params())
        x0[-4:-3] = 0.5  # k_size
        x0[-3:-2] = 0.5  # k_act
        x0[-2:-1] = 0.5  # k_quant
        x0[-1] = 0.0     # a_qat
        x0 += rng2.normal(0.0, 0.05, model.n_params())
        x0[-4:] = np.maximum(x0[-4:], 0.02)
        bounds = [(None, None)] * (model.n_family + model.n_dataset + model.n_linear)
        bounds += [(0.02, 500.0), (0.02, 500.0), (0.02, 500.0), (-0.9, 5.0)]
        res = minimize(objective, x0, jac=grad, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": maxiter})
        if best is None or res.fun < best.fun:
            best = res

    theta = best.x
    train_pred = model.predict(theta, **{k: X[k] for k in (
        "family", "dataset", "size_b", "act_ratio", "quant_ratio",
        "k_ratio", "v_ratio", "qat", "reason_off", "temp", "log_top_k")})
    train_rmse = float(np.sqrt(np.mean((train_pred - score) ** 2)))
    cv_rmse = float("nan")
    pred_all = np.full_like(score, np.nan)
    if do_cv:
        gkf = GroupKFold(n_splits=5)
        for tr, te in gkf.split(score, groups=groups):
            theta_tr = _refit_on_indices(model, X, tr, theta, lam_family, seed)
            pred_all[te] = model.predict(theta_tr, **{k: X[k] for k in (
                "family", "dataset", "size_b", "act_ratio", "quant_ratio",
                "k_ratio", "v_ratio", "qat", "reason_off", "temp", "log_top_k")})[te]
        cv_rmse = float(np.sqrt(np.nanmean((pred_all - score) ** 2)))
    return {
        "theta": theta,
        "cv_rmse": cv_rmse,
        "train_rmse": train_rmse,
        "cv_pred": pred_all,
    }


def _refit_on_indices(
    model: StructuralModel, X: dict, idx: np.ndarray,
    theta0: np.ndarray, lam_family: float, seed: int,
) -> np.ndarray:
    score = X["score"][idx]
    sub = {k: v[idx] for k, v in X.items()}
    xw = {k: sub[k] for k in (
        "family", "dataset", "size_b", "act_ratio", "quant_ratio",
        "k_ratio", "v_ratio", "qat", "reason_off", "temp", "log_top_k")}

    def objective(theta: np.ndarray) -> float:
        pred = model.predict(theta, **xw)
        mse = float(np.mean((pred - score) ** 2))
        w_fam, *_ = model.unpack(theta)
        mse += lam_family * float(np.mean(w_fam[1:] ** 2))
        return mse

    def grad(theta: np.ndarray) -> np.ndarray:
        g = model.gradient(theta, score, **xw)
        g[: model.n_family] += 2.0 * lam_family * theta[: model.n_family] / model.n_family
        return g

    rng = np.random.default_rng(seed)
    x0 = theta0 + rng.normal(0.0, 0.03, theta0.shape)
    x0[-4:] = np.maximum(x0[-4:], 0.02)
    bounds = [(None, None)] * (model.n_family + model.n_dataset + model.n_linear)
    bounds += [(0.02, 500.0), (0.02, 500.0), (0.02, 500.0), (-0.9, 5.0)]
    res = minimize(objective, x0, jac=grad, method="L-BFGS-B", bounds=bounds,
                   options={"maxiter": 1200})
    return res.x


# ----------------------------------------------------------------------------
# Ridge baseline (full-factor black-box reference)
# ----------------------------------------------------------------------------


def fit_ridge(data: list[dict], groups: np.ndarray) -> dict:
    fams = sorted({d["family"] for d in data})
    dats = sorted({d["dataset"] for d in data})
    rows = []
    for d in data:
        rows.append(
            [
                *[1.0 if d["family"] == f else 0.0 for f in fams],
                *[1.0 if d["dataset"] == g else 0.0 for g in dats],
                d["size_b"], d["act_ratio"], d["quant_ratio"],
                d["k_ratio"], d["v_ratio"], d["qat"], d["reason_off"],
                d["temp"], d["log_top_k"],
            ]
        )
    X = np.array(rows, dtype=float)
    y = np.array([d["score"] for d in data], dtype=float)
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)

    best = None
    for lam in (0.1, 1.0, 10.0, 100.0):
        gkf = GroupKFold(n_splits=5)
        pred_all = np.zeros_like(y)
        for tr, te in gkf.split(y, groups=groups):
            r = Ridge(alpha=lam)
            r.fit(Xs[tr], y[tr])
            pred_all[te] = r.predict(Xs[te])
        rmse = float(np.sqrt(np.mean((pred_all - y) ** 2)))
        if best is None or rmse < best[1]:
            best = (lam, rmse)
    return {"alpha": best[0], "cv_rmse": best[1]}


# ----------------------------------------------------------------------------
# Bootstrap CI (resample checkpoints -> uncertainty on coefficients)
# ----------------------------------------------------------------------------


def bootstrap_ci(
    model: StructuralModel, X: dict, groups: np.ndarray, theta: np.ndarray,
    lam_family: float, n_iter: int = 200, seed: int = 0,
) -> dict:
    rng = np.random.default_rng(seed)
    checkpoints = np.unique(groups)
    draws = []
    for _ in range(n_iter):
        sample = rng.choice(checkpoints, size=len(checkpoints), replace=True)
        idx = np.concatenate([np.where(groups == c)[0] for c in sample])
        try:
            th = _refit_on_indices(model, X, idx, theta, lam_family, int(rng.integers(1e6)))
        except Exception:
            continue
        draws.append(th)
    draws = np.array(draws)
    if draws.shape[0] == 0:
        return {}
    lo = np.percentile(draws, 2.5, axis=0)
    hi = np.percentile(draws, 97.5, axis=0)
    names = (
        [f"w[{f}]" for f in model.families[1:]]
        + [f"d[{d}]" for d in model.datasets[1:]]
        + ["br", "bt", "btopk", "bkvk", "bkvv", "k_size", "k_act", "k_quant", "a_qat"]
    )
    return {n: {"lo": float(l), "hi": float(h)} for n, l, h in zip(names, lo, hi)}


def cv_rmse_for(
    model: StructuralModel, X: dict, groups: np.ndarray, theta: np.ndarray,
    mode: str, lam_family: float, seed: int,
) -> float:
    """CV RMSE at a chosen strictness: 'checkpoint' (new gguf), 'family' (new arch), 'random'."""
    score = X["score"]
    n = len(score)
    pred_all = np.zeros(n)
    if mode == "random":
        from sklearn.model_selection import KFold

        splits = KFold(5, shuffle=True, random_state=seed).split(score)
    else:
        g = groups if mode == "checkpoint" else X["family"]
        splits = GroupKFold(n_splits=5).split(score, groups=g)
    for tr, te in splits:
        theta_tr = _refit_on_indices(model, X, tr, theta, lam_family, seed)
        pred_all[te] = model.predict(theta_tr, **{k: X[k] for k in (
            "family", "dataset", "size_b", "act_ratio", "quant_ratio",
            "k_ratio", "v_ratio", "qat", "reason_off", "temp", "log_top_k")})[te]
    return float(np.sqrt(np.mean((pred_all - score) ** 2)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--lam", type=float, default=0.0, help="ridge on family weights")
    args = ap.parse_args()

    loaded = load_rows(DB_PATH)
    data = loaded["rows"]
    print(f"rows raw={loaded['n_raw']} dedup={loaded['n_dedup']}")

    families = sorted({d["family"] for d in data})
    datasets = sorted({d["dataset"] for d in data})
    groups = np.array([data.index(d) for d in data], dtype=int)  # placeholder
    # group by checkpoint (model filename) for held-out-checkpoint CV
    model_names = sorted({d["model"] for d in data})
    ckpt_idx = {m: i for i, m in enumerate(model_names)}
    groups = np.array([ckpt_idx[d["model"]] for d in data], dtype=int)

    # cap-family search (cheap: single fit per candidate, ranked by train RMSE)
    print("\n=== cap-family search (train-RMSE ranking) ===")
    results = []
    best = None
    best_rmse = float("inf")
    for size_cap in ("rational", "exp", "tanh"):
        for act_cap in ("rational", "exp", "tanh"):
            for quant_cap in ("rational", "exp", "tanh", "saturator"):
                m = StructuralModel(families, datasets, size_cap, act_cap, quant_cap)
                X = build_X(data, m)
                fit = fit_structural(m, X, groups, args.lam, args.seed,
                                     restarts=1, maxiter=1500, do_cv=False)
                row = {
                    "size_cap": size_cap, "act_cap": act_cap, "quant_cap": quant_cap,
                    "cv_rmse": float("nan"), "train_rmse": fit["train_rmse"],
                }
                results.append(row)
                print(f"  ({size_cap},{act_cap},{quant_cap}) train={fit['train_rmse']:.5f}")
                if fit["train_rmse"] < best_rmse:
                    best = (m, fit, X)
                    best_rmse = fit["train_rmse"]

    # write cap search CSV (regenerates missing .serial_formula_search_caps.csv)
    with (OUT_DIR / "refit_caps_search.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["size_cap", "act_cap", "quant_cap", "cv_rmse", "train_rmse"])
        w.writeheader()
        w.writerows(results)

    model, fit, X = best
    # re-fit the winner with more effort (2 restarts, more iterations, full CV)
    fit = fit_structural(model, X, groups, args.lam, args.seed,
                         restarts=2, maxiter=8000, do_cv=True)
    print(f"\nbest caps: ({model.size_cap},{model.act_cap},{model.quant_cap}) "
          f"cv_rmse={fit['cv_rmse']:.5f} train_rmse={fit['train_rmse']:.5f}")

    # ridge reference (same checkpoint-grouped CV)
    ridge = fit_ridge(data, groups)
    print(f"ridge baseline checkpoint-grouped CV RMSE = {ridge['cv_rmse']:.5f} (alpha={ridge['alpha']})")

    # CV at three strictness levels for the winner
    theta = fit["theta"]
    for mode in ("checkpoint", "family", "random"):
        rmse = cv_rmse_for(model, X, groups, theta, mode, args.lam, args.seed)
        print(f"  CV[{mode:10s}] RMSE = {rmse:.5f}")
    cv_family = cv_rmse_for(model, X, groups, theta, "family", args.lam, args.seed)
    cv_random = cv_rmse_for(model, X, groups, theta, "random", args.lam, args.seed)

    w_fam, d_dat, br, bt, btopk, bkvk, bkvv, k_size, k_act, k_quant, a_qat = model.unpack(theta)

    # bootstrap CI
    print("\n=== bootstrap CI (resample checkpoints) ===")
    ci = bootstrap_ci(model, X, groups, theta, args.lam, args.bootstrap, args.seed)
    for name in [f"w[{f}]" for f in model.families[1:]][:8] + ["d[mbpp]"] + [
        "br", "bt", "btopk", "bkvk", "bkvv", "k_size", "k_act", "k_quant", "a_qat",
    ]:
        if name in ci:
            print(f"  {name:12s} lo={ci[name]['lo']:.3f} hi={ci[name]['hi']:.3f}")

    summary = {
        "n_raw": loaded["n_raw"],
        "n_dedup": loaded["n_dedup"],
        "n_families": len(families),
        "n_checkpoints": len(model_names),
        "cap_size": model.size_cap, "cap_act": model.act_cap, "cap_quant": model.quant_cap,
        "cv_rmse": fit["cv_rmse"], "train_rmse": fit["train_rmse"],
        "cv_checkpoint": fit["cv_rmse"], "cv_family": cv_family, "cv_random": cv_random,
        "ridge_cv_rmse": ridge["cv_rmse"], "ridge_alpha": ridge["alpha"],
        "coefs": {
            "br": br, "bt": bt, "btopk": btopk, "bkvk": bkvk, "bkvv": bkvv,
            "k_size": k_size, "k_act": k_act, "k_quant": k_quant, "a_qat": a_qat,
            "w_family": {f: float(w) for f, w in zip(model.families, w_fam)},
            "d_dataset": {d: float(v) for d, v in zip(model.datasets, d_dat)},
        },
        "ci": ci,
    }
    with (OUT_DIR / "refit_results.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote refit_results.json, refit_caps_search.csv")


if __name__ == "__main__":
    main()
