#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize
from sklearn.model_selection import GroupKFold


DB_PATH = Path("/home/z/hf/research/experiments.sqlite")


def _softplus(x: np.ndarray | float) -> np.ndarray | float:
    return np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0.0)


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


def _ver_str(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.6g}"


def quant_saturator(q: np.ndarray, kq: float, q_sat: float = 0.5) -> np.ndarray:
    q = np.clip(q, 0.0, 1.0)
    z = np.clip(q / q_sat, 0.0, 1.0)
    den = 1.0 - math.exp(-kq)
    if den < 1e-12:
        base = z
    else:
        base = (1.0 - np.exp(-kq * z)) / den
    return np.where(q >= q_sat, 1.0, base)


@dataclass(frozen=True)
class Candidate:
    name: str
    likelihood_tier: int
    include_quant_act_interaction: bool
    include_reason_model: bool
    include_reason_dataset: bool
    include_sampling_main: bool
    include_reason_sampling_interaction: bool
    include_quant_size_interaction: bool
    include_sampling_dataset_adjust: bool


class Dataset:
    def __init__(self, rows: Sequence[sqlite3.Row], ctx_mode: str) -> None:
        model = np.array([f"{r['model_arch']}|{_ver_str(r['version'])}" for r in rows], dtype=object)
        dataset = np.array([r["dataset"] for r in rows], dtype=object)
        size = np.array([float(r["size_b"]) for r in rows], dtype=float)
        act = np.array([float(r["activated_size_b"]) for r in rows], dtype=float)
        quant_ratio = np.array([float(r["quant_ratio"]) for r in rows], dtype=float)
        qat = np.array([float(r["qat_bool"]) for r in rows], dtype=float)
        reasoning = np.array([float(r["reasoning_bool"]) for r in rows], dtype=float)
        score_fix = np.array([float(r["score_fix"]) for r in rows], dtype=float)
        ctx = np.array([float(r["ctx_size"]) for r in rows], dtype=float)
        temperature = np.array([float(r["temperature"]) for r in rows], dtype=float)
        top_p = np.array([float(r["top_p"]) for r in rows], dtype=float)
        top_k = np.array([float(r["top_k"]) for r in rows], dtype=float)
        min_p = np.array([float(r["min_p"]) for r in rows], dtype=float)
        presence = np.array([float(r["presence_penalty"]) for r in rows], dtype=float)

        size = np.maximum(size, 1e-9)
        act = np.clip(act, 0.0, size)
        act_ratio = np.clip(act / size, 0.0, 1.0)
        quant_ratio = np.clip(quant_ratio, 0.0, 1.0)

        if ctx_mode == "model_p75":
            keep = np.zeros(len(rows), dtype=bool)
            for m in np.unique(model):
                m_mask = model == m
                p75 = np.quantile(ctx[m_mask], 0.75)
                keep[m_mask] = ctx[m_mask] >= p75
        elif ctx_mode == "ctx8192":
            keep = ctx >= 8192.0
        else:
            raise ValueError(f"Unsupported ctx_mode: {ctx_mode}")

        model = model[keep]
        dataset = dataset[keep]
        size = size[keep]
        act_ratio = act_ratio[keep]
        quant_ratio = quant_ratio[keep]
        qat = qat[keep]
        reasoning = reasoning[keep]
        score_fix = score_fix[keep]
        temperature = temperature[keep]
        top_p = top_p[keep]
        top_k = top_k[keep]
        min_p = min_p[keep]
        presence = presence[keep]

        self.model_names = sorted(set(model.tolist()))
        self.dataset_names = sorted(set(dataset.tolist()))
        self.model_to_idx = {m: i for i, m in enumerate(self.model_names)}
        self.dataset_to_idx = {d: i for i, d in enumerate(self.dataset_names)}
        self.model_idx = np.array([self.model_to_idx[m] for m in model], dtype=int)
        self.dataset_idx = np.array([self.dataset_to_idx[d] for d in dataset], dtype=int)

        self.model = model
        self.dataset = dataset
        self.size = size
        self.act_ratio = act_ratio
        self.quant_ratio = quant_ratio
        self.qat = qat
        self.reasoning = reasoning
        self.score_fix = score_fix
        self.sample_t = temperature - 0.30
        self.sample_top_p = top_p - 0.95
        self.sample_top_k = (top_k - 40.0) / 100.0
        self.sample_min_p = min_p - 0.05
        self.sample_presence = presence
        self.groups = model.copy()

    @property
    def n_models(self) -> int:
        return len(self.model_names)

    @property
    def n_datasets(self) -> int:
        return len(self.dataset_names)

    @property
    def n_rows(self) -> int:
        return len(self.score_fix)


class FormulaModel:
    def __init__(self, ds: Dataset, cand: Candidate, qat_floor: float = 0.0) -> None:
        self.ds = ds
        self.cand = cand
        self.qat_floor = qat_floor

        self._offset = {}
        p = 0
        for name in ("ks", "ka", "kq", "aqat"):
            self._offset[name] = (p, p + 1)
            p += 1
        self._offset["model_w"] = (p, p + ds.n_models)
        p += ds.n_models
        self._offset["dataset_w"] = (p, p + ds.n_datasets)
        p += ds.n_datasets
        if cand.include_quant_act_interaction:
            self._offset["qact_beta"] = (p, p + 1)
            p += 1
        if cand.include_quant_size_interaction:
            self._offset["qsize_beta"] = (p, p + 1)
            p += 1
        self._offset["reason_global"] = (p, p + 1)
        p += 1
        if cand.include_reason_model:
            self._offset["reason_model"] = (p, p + ds.n_models)
            p += ds.n_models
        if cand.include_reason_dataset:
            self._offset["reason_dataset"] = (p, p + ds.n_datasets)
            p += ds.n_datasets
        if cand.include_sampling_main:
            self._offset["sampling_main"] = (p, p + 5)
            p += 5
            if cand.include_sampling_dataset_adjust:
                self._offset["sampling_dataset_adjust"] = (p, p + 5 * self.ds.n_datasets)
                p += 5 * self.ds.n_datasets
        if cand.include_reason_sampling_interaction:
            self._offset["sampling_reason"] = (p, p + 5)
            p += 5
        self.n_params = p

    def init_params(self) -> np.ndarray:
        p = np.zeros(self.n_params, dtype=float)
        p[self._slice("ks")] = math.log(math.exp(0.08) - 1.0)
        p[self._slice("ka")] = math.log(math.exp(0.5) - 1.0)
        p[self._slice("kq")] = math.log(math.exp(6.0) - 1.0)
        p[self._slice("aqat")] = math.log(math.exp(0.05) - 1.0)
        p[self._slice("model_w")] = math.log(max(float(np.mean(self.ds.score_fix)), 1e-3))
        if "sampling_main" in self._offset:
            p[self._slice("sampling_main")] = 0.0
        if "sampling_reason" in self._offset:
            p[self._slice("sampling_reason")] = 0.0
        return p

    def _slice(self, key: str) -> slice:
        lo, hi = self._offset[key]
        return slice(lo, hi)

    def _value(self, key: str, p: np.ndarray) -> np.ndarray:
        return p[self._slice(key)]

    def predict(self, p: np.ndarray, idx: np.ndarray | None = None) -> np.ndarray:
        if idx is None:
            idx = np.arange(self.ds.n_rows, dtype=int)
        d = self.ds
        m_idx = d.model_idx[idx]
        ds_idx = d.dataset_idx[idx]

        ks = float(_softplus(self._value("ks", p))[0])
        ka = float(_softplus(self._value("ka", p))[0])
        kq = float(_softplus(self._value("kq", p))[0])
        aqat = float(_softplus(self._value("aqat", p))[0]) + self.qat_floor

        model_w = self._value("model_w", p)
        dataset_w = self._value("dataset_w", p)

        size = d.size[idx]
        act_ratio = d.act_ratio[idx]
        q = d.quant_ratio[idx]
        qat = d.qat[idx]
        reason = d.reasoning[idx]

        cap_size = 1.0 - np.exp(-ks * size)
        cap_act = np.power(np.clip(act_ratio, 1e-9, 1.0), 1.0 / (1.0 + ka))
        cap_quant = quant_saturator(q, kq, q_sat=0.5)
        cap_qat = 1.0 + aqat * qat

        mw = np.clip(model_w[m_idx], -12.0, 12.0)
        dw = np.clip(dataset_w[ds_idx], -12.0, 12.0)
        raw = np.exp(mw) * np.exp(dw) * cap_size * cap_act * cap_quant * cap_qat

        if "qact_beta" in self._offset:
            qact_beta = float(_softplus(self._value("qact_beta", p))[0])
            qact = np.exp(-qact_beta * (1.0 - cap_quant) * (1.0 - act_ratio))
            raw = raw * qact
        if "qsize_beta" in self._offset:
            qsize_beta = float(_softplus(self._value("qsize_beta", p))[0])
            qsize = np.exp(-qsize_beta * (1.0 - cap_quant) * np.exp(-0.1 * size))
            raw = raw * qsize

        reason_term = float(self._value("reason_global", p)[0])
        if "reason_model" in self._offset:
            reason_term = reason_term + self._value("reason_model", p)[m_idx]
        if "reason_dataset" in self._offset:
            reason_term = reason_term + self._value("reason_dataset", p)[ds_idx]
        raw = raw * np.exp(np.clip(reason * reason_term, -20.0, 20.0))

        if "sampling_main" in self._offset:
            b = self._value("sampling_main", p)
            samp_base = (
                b[0] * d.sample_t[idx]
                + b[1] * d.sample_top_p[idx]
                + b[2] * d.sample_top_k[idx]
                + b[3] * d.sample_min_p[idx]
                + b[4] * d.sample_presence[idx]
            )
            samp = samp_base
            if "sampling_dataset_adjust" in self._offset:
                bd = self._value("sampling_dataset_adjust", p).reshape(self.ds.n_datasets, 5)
                bds = bd[ds_idx]
                samp = (
                    samp
                    + bds[:, 0] * d.sample_t[idx]
                    + bds[:, 1] * d.sample_top_p[idx]
                    + bds[:, 2] * d.sample_top_k[idx]
                    + bds[:, 3] * d.sample_min_p[idx]
                    + bds[:, 4] * d.sample_presence[idx]
                )
            raw = raw * np.exp(np.clip(samp, -20.0, 20.0))

        if "sampling_reason" in self._offset:
            c = self._value("sampling_reason", p)
            rs = (
                c[0] * d.sample_t[idx]
                + c[1] * d.sample_top_p[idx]
                + c[2] * d.sample_top_k[idx]
                + c[3] * d.sample_min_p[idx]
                + c[4] * d.sample_presence[idx]
            )
            raw = raw * np.exp(np.clip(reason * rs, -20.0, 20.0))

        # Natural saturation: y = 1 - exp(-raw), so approaching 1 gets progressively harder.
        raw = np.clip(raw, 0.0, 60.0)
        return -np.expm1(-raw)

    def objective(
        self,
        p: np.ndarray,
        idx: np.ndarray | None = None,
        l2: float = 1e-3,
    ) -> float:
        if idx is None:
            idx = np.arange(self.ds.n_rows, dtype=int)
        pred = self.predict(p, idx)
        y = self.ds.score_fix[idx]
        mse = float(np.mean((pred - y) ** 2))
        reg = l2 * float(np.mean(p**2))
        return mse + reg


def load_rows(db_path: Path) -> List[sqlite3.Row]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT
          model_arch, version, dataset,
          size_b, activated_size_b, qat_bool, quant_ratio,
          reasoning_bool, ctx_size, score_fix,
          temperature, top_p, top_k, min_p, presence_penalty
        FROM experiments
        WHERE score_kind='pass@1_plus'
          AND score_fix IS NOT NULL
          AND model_arch IS NOT NULL
          AND version IS NOT NULL
          AND dataset IS NOT NULL
          AND size_b IS NOT NULL
          AND activated_size_b IS NOT NULL
          AND qat_bool IS NOT NULL
          AND quant_ratio IS NOT NULL
          AND reasoning_bool IS NOT NULL
          AND ctx_size IS NOT NULL
          AND temperature IS NOT NULL
          AND top_p IS NOT NULL
          AND top_k IS NOT NULL
          AND min_p IS NOT NULL
          AND presence_penalty IS NOT NULL
        """
    ).fetchall()
    con.close()
    return list(rows)


def candidate_space(mode: str) -> List[Candidate]:
    compact = [
        Candidate("tier1_core", 1, False, False, False, False, False, False, False),
        Candidate("tier1_core_reason_model", 1, False, True, False, False, False, False, False),
        Candidate("tier1_core_reason_dataset", 1, False, False, True, False, False, False, False),
        Candidate("tier1_core_reason_model_dataset", 1, False, True, True, False, False, False, False),
        Candidate("tier2_add_sampling", 2, False, True, True, True, False, False, False),
        Candidate("tier2_add_quant_act", 2, True, True, True, False, False, False, False),
        Candidate("tier2_sampling_quant_act", 2, True, True, True, True, False, False, False),
        Candidate("tier3_add_reason_sampling", 3, True, True, True, True, True, False, False),
    ]
    if mode == "compact":
        return compact

    expanded: List[Candidate] = []
    for include_quant_act_interaction in (False, True):
        for include_quant_size_interaction in (False, True):
            for include_reason_model in (True,):
                for include_reason_dataset in (False, True):
                    for include_sampling_main in (False, True):
                        for include_reason_sampling_interaction in (False, True):
                            if include_reason_sampling_interaction and not include_sampling_main:
                                continue
                            for include_sampling_dataset_adjust in (False, True):
                                if include_sampling_dataset_adjust and not include_sampling_main:
                                    continue
                                complexity = (
                                    int(include_quant_act_interaction)
                                    + int(include_quant_size_interaction)
                                    + int(include_reason_dataset)
                                    + int(include_sampling_main)
                                    + int(include_reason_sampling_interaction)
                                    + int(include_sampling_dataset_adjust)
                                )
                                tier = 1 if complexity <= 1 else (2 if complexity <= 3 else 3)
                                name = (
                                    f"t{tier}"
                                    f"_qa{int(include_quant_act_interaction)}"
                                    f"_qs{int(include_quant_size_interaction)}"
                                    f"_rd{int(include_reason_dataset)}"
                                    f"_sm{int(include_sampling_main)}"
                                    f"_rs{int(include_reason_sampling_interaction)}"
                                    f"_sd{int(include_sampling_dataset_adjust)}"
                                )
                                expanded.append(
                                    Candidate(
                                        name=name,
                                        likelihood_tier=tier,
                                        include_quant_act_interaction=include_quant_act_interaction,
                                        include_reason_model=include_reason_model,
                                        include_reason_dataset=include_reason_dataset,
                                        include_sampling_main=include_sampling_main,
                                        include_reason_sampling_interaction=include_reason_sampling_interaction,
                                        include_quant_size_interaction=include_quant_size_interaction,
                                        include_sampling_dataset_adjust=include_sampling_dataset_adjust,
                                    )
                                )
    return expanded


def _single_fit(
    model: FormulaModel,
    start: np.ndarray,
    train_idx: np.ndarray | None = None,
    maxiter: int = 500,
    l2: float = 1e-3,
) -> Tuple[float, np.ndarray]:
    res = minimize(
        lambda z: model.objective(z, train_idx, l2=l2),
        start,
        method="L-BFGS-B",
        options={"maxiter": maxiter},
    )
    return float(res.fun), np.array(res.x, dtype=float)


def fit_candidate(
    ds: Dataset,
    cand: Candidate,
    qat_floor: float,
    n_splits: int,
    n_starts: int,
    fold_starts: int,
    seed: int,
    l2: float,
) -> Dict[str, object]:
    model = FormulaModel(ds, cand, qat_floor=qat_floor)
    p0 = model.init_params()

    best = None
    rng = np.random.default_rng(seed)
    starts = [p0, p0 + 0.01, p0 - 0.01]
    for _ in range(max(0, n_starts - 3)):
        starts.append(p0 + rng.normal(0.0, 0.08, size=p0.shape[0]))
    for s in starts:
        f, x = _single_fit(model, s, None, maxiter=700, l2=l2)
        if best is None or f < best[0]:
            best = (f, x)
    assert best is not None
    p = best[1]
    train_rmse = float(np.sqrt(np.mean((model.predict(p) - ds.score_fix) ** 2)))

    groups = ds.groups
    unique_groups = np.unique(groups)
    splits = min(n_splits, len(unique_groups))
    if splits < 2:
        raise RuntimeError("Not enough model groups for grouped CV.")

    gkf = GroupKFold(n_splits=splits)
    fold_rmse = []
    fold_param_sets = []
    for tr, te in gkf.split(np.arange(ds.n_rows), groups=groups):
        best_fold = None
        fold_candidates = [p]
        for _ in range(max(0, fold_starts - 1)):
            fold_candidates.append(p + rng.normal(0.0, 0.05, size=p.shape[0]))
        for fs in fold_candidates:
            f, x = _single_fit(model, fs, tr, maxiter=450, l2=l2)
            if best_fold is None or f < best_fold[0]:
                best_fold = (f, x)
        assert best_fold is not None
        p_fold = best_fold[1]
        fold_param_sets.append(p_fold)
        yhat = model.predict(p_fold, te)
        rmse = float(np.sqrt(np.mean((yhat - ds.score_fix[te]) ** 2)))
        fold_rmse.append(rmse)

    cv_rmse = float(np.mean(fold_rmse))
    cv_std = float(np.std(fold_rmse))
    complexity = model.n_params
    prior_penalty = 0.002 * (cand.likelihood_tier - 1) + 0.0002 * complexity
    total_score = cv_rmse + prior_penalty

    return {
        "candidate": cand.name,
        "tier": cand.likelihood_tier,
        "n_params": complexity,
        "train_rmse": train_rmse,
        "cv_rmse": cv_rmse,
        "cv_std": cv_std,
        "prior_penalty": prior_penalty,
        "search_score": total_score,
        "params": p.tolist(),
        "offsets": model._offset,
        "fold_rmse": fold_rmse,
        "l2": l2,
    }


def fit_candidate_stable(
    ds: Dataset,
    cand: Candidate,
    qat_floor: float,
    n_splits: int,
    n_starts: int,
    fold_starts: int,
    seed: int,
    l2: float,
    seed_repeats: int,
    stability_weight: float,
    gap_weight: float,
) -> Dict[str, object]:
    runs: List[Dict[str, object]] = []
    for r in range(seed_repeats):
        runs.append(
            fit_candidate(
                ds=ds,
                cand=cand,
                qat_floor=qat_floor,
                n_splits=n_splits,
                n_starts=n_starts,
                fold_starts=fold_starts,
                seed=seed + r * 104729,
                l2=l2,
            )
        )

    cv_vals = np.array([x["cv_rmse"] for x in runs], dtype=float)
    tr_vals = np.array([x["train_rmse"] for x in runs], dtype=float)
    gap_vals = cv_vals - tr_vals
    cv_mean = float(np.mean(cv_vals))
    cv_seed_std = float(np.std(cv_vals))
    tr_mean = float(np.mean(tr_vals))
    gap_mean = float(np.mean(gap_vals))

    best_idx = int(np.argmin(cv_vals))
    rep = dict(runs[best_idx])
    rep["cv_rmse"] = cv_mean
    rep["cv_rmse_seed_std"] = cv_seed_std
    rep["train_rmse"] = tr_mean
    rep["generalization_gap"] = gap_mean
    rep["seed_repeats"] = seed_repeats
    rep["seed_runs"] = [
        {
            "cv_rmse": float(r["cv_rmse"]),
            "train_rmse": float(r["train_rmse"]),
            "fold_rmse": r["fold_rmse"],
        }
        for r in runs
    ]
    rep["robust_score"] = (
        float(rep["cv_rmse"])
        + float(rep["prior_penalty"])
        + stability_weight * cv_seed_std
        + gap_weight * max(0.0, gap_mean)
    )
    return rep


def write_results(
    out_json: Path,
    out_csv: Path,
    spec_json: Path,
    ds: Dataset,
    results: List[Dict[str, object]],
    ctx_mode: str,
    qat_floor: float,
    candidate_mode: str,
    selection: str,
    l2: float,
    seed_repeats: int,
    stability_weight: float,
    gap_weight: float,
) -> None:
    payload = {
        "meta": {
            "db_path": str(DB_PATH),
            "rows_after_ctx_gate": ds.n_rows,
            "models": ds.model_names,
            "datasets": ds.dataset_names,
            "ctx_mode": ctx_mode,
            "qat_floor": qat_floor,
            "target": "score_fix",
            "score_kind": "pass@1_plus",
            "candidate_mode": candidate_mode,
            "selection": selection,
            "l2": l2,
            "seed_repeats": seed_repeats,
            "stability_weight": stability_weight,
            "gap_weight": gap_weight,
            "notes": [
                "model_enum=arch|version",
                "ctx handled as adequacy gate only",
                "mtp excluded from formula by design",
                "quant uses bounded saturator with q_sat=0.5 and cap at 1",
                "output link uses natural saturation y=1-exp(-raw), no clip01",
            ],
        },
        "results": results,
    }
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "rank",
                "candidate",
                "tier",
                "n_params",
                "train_rmse",
                "cv_rmse",
                "cv_rmse_seed_std",
                "cv_std",
                "prior_penalty",
                "search_score",
                "generalization_gap",
                "robust_score",
            ]
        )
        for i, r in enumerate(results, start=1):
            w.writerow(
                [
                    i,
                    r["candidate"],
                    r["tier"],
                    r["n_params"],
                    f"{r['train_rmse']:.6f}",
                    f"{r['cv_rmse']:.6f}",
                    f"{r.get('cv_rmse_seed_std', 0.0):.6f}",
                    f"{r['cv_std']:.6f}",
                    f"{r['prior_penalty']:.6f}",
                    f"{r['search_score']:.6f}",
                    f"{r.get('generalization_gap', 0.0):.6f}",
                    f"{r.get('robust_score', r['search_score']):.6f}",
                ]
            )

    spec = {
        "search_process": {
            "type": "constrained-grammar-search",
            "stages": [
                "tier-1 high-likelihood structural candidates",
                "tier-2 medium-likelihood interaction candidates",
                "tier-3 low-likelihood expansion candidates",
            ],
            "selection": "grouped-cv-rmse + prior penalty",
            "grouping": "GroupKFold by model_enum",
            "convergence_control": [
                "multi-start optimization per fit",
                "multi-seed repeated structure evaluation",
                "stability and generalization-gap penalties in robust ranking",
            ],
        },
        "possible_vs_impossible": {
            "possible_now": [
                "prior-constrained score_fix formula search",
                "quant saturation around q=0.5",
                "non-negative qat effect constraint",
            ],
            "impossible_now": [
                "exact empty-output decomposition on pass@1_plus (bad_rate missing there)",
            ],
        },
        "priors_as_constraints": {
            "size_b": {"monotone_positive": True, "zero_anchor": True},
            "activated_size_b": {"monotone_positive": True, "zero_anchor": True, "bounded_by_size": True},
            "quant_ratio": {
                "bounded_0_1": True,
                "zero_anchor": True,
                "saturate_near_q8": True,
                "cap_at_1": True,
            },
            "qat_bool": {"boolean": True, "non_negative_effect": True, "floor": qat_floor},
            "mtp": {"excluded_from_score_formula": True},
            "ctx_size": {"binary_adequacy_gate_only": True, "mode": ctx_mode},
            "model_version": {"inside_model_enum": True},
        },
    }
    spec_json.write_text(json.dumps(spec, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Formal constrained formula search for score_fix.")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--ctx-mode", choices=["model_p75", "ctx8192"], default="model_p75")
    ap.add_argument("--qat-floor", type=float, default=0.0)
    ap.add_argument("--cv-splits", type=int, default=5)
    ap.add_argument("--candidate-mode", choices=["compact", "expanded"], default="compact")
    ap.add_argument("--selection", choices=["search_score", "cv_rmse", "robust_score"], default="robust_score")
    ap.add_argument("--starts", type=int, default=3)
    ap.add_argument("--fold-starts", type=int, default=1)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--l2", type=float, default=1e-3)
    ap.add_argument("--seed-repeats", type=int, default=1)
    ap.add_argument("--stability-weight", type=float, default=0.5)
    ap.add_argument("--gap-weight", type=float, default=0.25)
    ap.add_argument("--out-json", type=Path, default=Path("/home/z/hf/research/.formula_search_results.json"))
    ap.add_argument("--out-csv", type=Path, default=Path("/home/z/hf/research/.formula_search_ranked.csv"))
    ap.add_argument("--spec-json", type=Path, default=Path("/home/z/hf/research/.formula_search_spec.json"))
    args = ap.parse_args()

    rows = load_rows(args.db)
    if not rows:
        raise RuntimeError("No usable rows found in experiments for score_fix search.")
    ds = Dataset(rows, ctx_mode=args.ctx_mode)
    if ds.n_rows < 50:
        raise RuntimeError("Too few rows after ctx gate.")

    cands = candidate_space(args.candidate_mode)
    results = []
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            fut = {
                ex.submit(
                    fit_candidate_stable,
                    ds,
                    cand,
                    args.qat_floor,
                    args.cv_splits,
                    args.starts,
                    args.fold_starts,
                    args.seed + i * 1009,
                    args.l2,
                    args.seed_repeats,
                    args.stability_weight,
                    args.gap_weight,
                ): cand
                for i, cand in enumerate(cands)
            }
            for f in as_completed(fut):
                fit = f.result()
                results.append(fit)
                print(
                    f"{fit['candidate']}: cv_rmse={fit['cv_rmse']:.6f} "
                    f"train_rmse={fit['train_rmse']:.6f} "
                    f"score={fit['search_score']:.6f} robust={fit.get('robust_score', fit['search_score']):.6f}"
                )
    else:
        for i, cand in enumerate(cands):
            fit = fit_candidate_stable(
                ds,
                cand,
                qat_floor=args.qat_floor,
                n_splits=args.cv_splits,
                n_starts=args.starts,
                fold_starts=args.fold_starts,
                seed=args.seed + i * 1009,
                l2=args.l2,
                seed_repeats=args.seed_repeats,
                stability_weight=args.stability_weight,
                gap_weight=args.gap_weight,
            )
            results.append(fit)
            print(
                f"{cand.name}: cv_rmse={fit['cv_rmse']:.6f} "
                f"train_rmse={fit['train_rmse']:.6f} "
                f"score={fit['search_score']:.6f} robust={fit.get('robust_score', fit['search_score']):.6f}"
            )

    if args.selection == "cv_rmse":
        key = "cv_rmse"
    elif args.selection == "search_score":
        key = "search_score"
    else:
        key = "robust_score"
    results.sort(key=lambda r: r[key])
    write_results(
        args.out_json,
        args.out_csv,
        args.spec_json,
        ds,
        results,
        args.ctx_mode,
        args.qat_floor,
        args.candidate_mode,
        args.selection,
        args.l2,
        args.seed_repeats,
        args.stability_weight,
        args.gap_weight,
    )
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.spec_json}")
    best = results[0]
    print(
        f"best={best['candidate']} cv_rmse={best['cv_rmse']:.6f} "
        f"train_rmse={best['train_rmse']:.6f} params={best['n_params']}"
    )


if __name__ == "__main__":
    main()
