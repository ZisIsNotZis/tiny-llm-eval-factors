"""Ridge baseline at every held-out regime, for an apples-to-apples comparison.

The structural model's headline "beats ridge 0.210" was checkpoint-only. This
script recomputes the linear baseline under the same four regimes so the two are
comparable, and writes `ridge_generalization.json`.

Usage:  python3 ridge_baseline.py
"""
from __future__ import annotations

import json
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, KFold

import refit_formula as rf


def design(data):
    families = sorted({d["family"] for d in data})
    datasets = sorted({d["dataset"] for d in data})
    fi = {f: i for i, f in enumerate(families)}
    di = {d: i for i, d in enumerate(datasets)}
    rows = []
    for d in data:
        v = [0.0] * (len(families) - 1)
        if fi[d["family"]] > 0:
            v[fi[d["family"]] - 1] = 1.0
        w = [0.0] * (len(datasets) - 1)
        if di[d["dataset"]] > 0:
            w[di[d["dataset"]] - 1] = 1.0
        rows.append(v + w + [
            d["size_b"], d["act_ratio"], d["quant_ratio"],
            d["k_ratio"], d["v_ratio"], float(d["qat"]), d["reason_off"],
            d["temp"], d["log_top_k"],
        ])
    return np.array(rows), np.array([d["score"] for d in data]), fi, di


def main():
    loaded = rf.load_rows(rf.DB_PATH)
    data = loaded["rows"]
    X, y, fi, di = design(data)
    n = len(y)

    groups = {
        "checkpoint": np.array([{m: i for i, m in enumerate(sorted({d["model"] for d in data}))}[d["model"]] for d in data]),
        "family": np.array([fi[d["family"]] for d in data]),
        "family_dataset": np.array([fi[d["family"]] * len(di) + di[d["dataset"]] for d in data]),
    }

    out = {"n_dedup": n, "alpha": 100.0, "ridge_cv": {}}
    for mode in ("random", "checkpoint", "family", "family_dataset"):
        pred = np.zeros(n)
        if mode == "random":
            splits = KFold(5, shuffle=True, random_state=7).split(y)
        else:
            splits = GroupKFold(5).split(y, groups=groups[mode])
        for tr, te in splits:
            m = Ridge(alpha=100.0).fit(X[tr], y[tr])
            pred[te] = m.predict(X[te])
        rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
        out["ridge_cv"][mode] = rmse
        print(f"  ridge CV[{mode:15s}] RMSE = {rmse:.5f}")

    model = json.loads((rf.OUT_DIR / "cv_generalization.json").read_text())
    print("\n  structural model for comparison:")
    for k, v in model["cv"].items():
        r = out["ridge_cv"][k]
        print(f"  {k:15s} model {v:.4f} | ridge {r:.4f} | {'model wins' if v < r else 'RIDGE WINS'}")

    (rf.OUT_DIR / "ridge_generalization.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print("\nwrote ridge_generalization.json")


if __name__ == "__main__":
    main()
