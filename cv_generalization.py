"""Generalization CV for the structural score model.

Computes held-out RMSE under four increasingly strict generalization regimes:

  random          -- random row split (optimistic; rows from the same run leak)
  checkpoint      -- hold out a whole GGUF checkpoint (new quant of a seen model)
  family          -- hold out a whole model family (new architecture)
  family_dataset  -- hold out a whole (family, dataset) cell (new architecture AND
                     new benchmark at once; the strictest available split)

Rationale: `refit_results.json` records checkpoint- and family-held-out CV, but
family-held-out still lets the model see the *same benchmark* it is scored on, so
the dataset offset is unidentifiable. The family+dataset split closes that and is
the number to quote when the claim is "generalizes to new models on new tasks".

Usage:
    python3 cv_generalization.py
"""
from __future__ import annotations

import json
import numpy as np
from sklearn.model_selection import GroupKFold, KFold

import refit_formula as rf


def cv_rmse(model, X, theta, groups, lam, seed, mode):
    score = X["score"]
    n = len(score)
    pred = np.zeros(n)
    if mode == "random":
        splits = KFold(5, shuffle=True, random_state=seed).split(score)
        grp = None
    else:
        grp = groups[mode]
        splits = GroupKFold(n_splits=5).split(score, groups=grp)
    for tr, te in splits:
        th = rf._refit_on_indices(model, X, tr, theta, lam, seed)
        p = model.predict(
            th,
            **{k: X[k] for k in (
                "family", "dataset", "size_b", "act_ratio", "quant_ratio",
                "k_ratio", "v_ratio", "qat", "reason_off", "temp", "log_top_k")},
        )
        pred[te] = p[te]
    return float(np.sqrt(np.mean((pred - score) ** 2)))


def main() -> None:
    loaded = rf.load_rows(rf.DB_PATH)
    data = loaded["rows"]
    print(f"rows raw={loaded['n_raw']} dedup={loaded['n_dedup']}")

    families = sorted({d["family"] for d in data})
    datasets = sorted({d["dataset"] for d in data})
    model_names = sorted({d["model"] for d in data})
    ckpt_idx = {m: i for i, m in enumerate(model_names)}
    fam_idx = {f: i for i, f in enumerate(families)}
    dat_idx = {d: i for i, d in enumerate(datasets)}

    groups = {
        "checkpoint": np.array([ckpt_idx[d["model"]] for d in data]),
        "family": np.array([fam_idx[d["family"]] for d in data]),
        "family_dataset": np.array(
            [fam_idx[d["family"]] * len(datasets) + dat_idx[d["dataset"]] for d in data]
        ),
    }

    # reuse the winning cap family from the last full refit
    prev = json.loads((rf.OUT_DIR / "refit_results.json").read_text())
    model = rf.StructuralModel(
        families, datasets, prev["cap_size"], prev["cap_act"], prev["cap_quant"]
    )
    X = rf.build_X(data, model)

    lam, seed = 0.0, 7
    fit = rf.fit_structural(model, X, groups["checkpoint"], lam, seed,
                            restarts=2, maxiter=4000, do_cv=False)
    theta = fit["theta"]
    print(f"train_rmse={fit['train_rmse']:.5f}  caps=({model.size_cap},{model.act_cap},{model.quant_cap})")

    out = {"n_dedup": loaded["n_dedup"], "n_families": len(families),
           "n_checkpoints": len(model_names), "n_datasets": len(datasets),
           "train_rmse": float(fit["train_rmse"]), "cv": {}}
    for mode in ("random", "checkpoint", "family", "family_dataset"):
        rmse = cv_rmse(model, X, theta, groups, lam, seed, mode)
        out["cv"][mode] = rmse
        print(f"  CV[{mode:15s}] RMSE = {rmse:.5f}")

    (rf.OUT_DIR / "cv_generalization.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n"
    )
    print("\nwrote cv_generalization.json")


if __name__ == "__main__":
    main()
