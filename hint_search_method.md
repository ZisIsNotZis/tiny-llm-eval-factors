## Best End-to-End Combination (Closest to Your Exact Description)
### `adaptive` + `PySR`
This is the most direct match for "curvature-aware adaptive sampling + symbolic formula discovery with a fixed trial budget".

#### 1. `adaptive` — the intelligent sampling engine
`adaptive` is a dedicated Python library for **parallel active learning of mathematical functions** — it does exactly what you described: it automatically allocates more samples to regions with high curvature / nonlinearity / complex geometry, and wastes almost no samples on flat, linear, well-understood regions.

- Core behavior matches your requirements perfectly:
  - Automatically decorrelates parameter effects via space-filling + curvature-driven refinement
  - Spends fewer trials on linear variables, more trials on variables with complex response surfaces
  - Supports N-dimensional parameter spaces
  - Built for parallel/distributed evaluation (Ray-like philosophy)
  - Works with a fixed evaluation budget
- It does **not** discover formulas by itself — it only optimizes *where* to run your experiments to maximize information gain per trial.

#### 2. `PySR` — the formula discovery engine
PySR is the current state-of-the-art open-source symbolic regression library for Python (Julia backend, scikit-learn compatible API). It takes your `(X, y)` trial data and discovers interpretable mathematical formulas that predict the score.

- Key properties:
  - Outputs human-readable mathematical expressions (not black-box models)
  - Returns a Pareto front of formulas balancing accuracy vs. complexity
  - Supports arbitrary operators, constraints, and custom loss functions
  - Can run cross-validation to verify formula stability per variable

#### Combined workflow
1. Use `adaptive` to sample your hyperparameter space with your trial budget. It naturally concentrates samples on nonlinear/interacting regions.
2. Feed the resulting `(parameters, score)` dataset into `PySRRegressor.fit()`.
3. (Optional active learning loop) Take the top-K candidate formulas from PySR, compute their prediction disagreement across candidate points, and run additional trials at points of maximum disagreement (Query-by-Committee) to further refine formula accuracy.

## Standalone Adaptive Sampling / Experimental Design Libraries
If you want to swap out the formula engine, these libraries specialize in efficient, decorrelating adaptive sampling for surrogate model building:

### 1. `SMT` (Surrogate Modeling Toolbox)
- Industry-standard library from Airbus/Michigan State for surrogate construction
- Includes built-in adaptive sampling criteria: **IMSE (Integrated Mean Squared Error)**, maximum variance, and expected improvement for model refinement
- Supports D-optimal / A-optimal design criteria to explicitly decorrelate parameter effects
- Ships with Kriging, RBF, polynomial chaos and other surrogates; pair with PySR for formula output
- Reference: used widely in aerospace and automotive engineering for adaptive DoE

### 2. `modAL`
- General-purpose active learning framework with scikit-learn style API
- Supports Query-by-Committee, uncertainty sampling, and custom acquisition functions
- Most flexible if you want to implement your own "formula disagreement" acquisition criterion
- Requires more assembly than `adaptive`, but fully customizable

### 3. `PyApprox` (Sandia National Labs)
- Focused on adaptive surrogate construction and uncertainty quantification
- Implements advanced sequential design criteria (MICE, IMSE, cross-validation error minimization)
- Heavier and more engineering-focused; good if you also need sensitivity analysis / Sobol indices to identify which variables are linear vs. coupled

## Symbolic Regression Engines (Formula Discovery)
These all accept tabular trial data and output mathematical formulas:

| Library | Match Quality | Key Notes |
|---|---|---|
| **PySR** | Best overall | Highest performance, most configurable, actively maintained, scikit-learn API |
| **PySIPS (NASA)** | Good for uncertainty-aware | Bayesian symbolic regression with posterior uncertainty over formulas — naturally gives you confidence per region for active sampling |
| **mini-sisso** | Fast, sparse | Rust-accelerated SISSO algorithm, excels at finding low-complexity linear-in-feature formulas from high-dimensional data |
| **DSR (Deep Symbolic Regression)** | Research-grade | Neural-guided symbolic regression; good if you suspect very complex formula structures |

## Ray Ecosystem Integration
Ray Tune does **not** ship with a built-in "formula discovery" search algorithm — all built-in searchers (BOHB, Optuna, BoTorch) are designed for finding an optimum, not for building a globally accurate predictive formula.

However, you have two clean integration paths:
1. **Custom Ray Tune Searcher**: Wrap `adaptive`'s sampling logic (or your own QBC formula-disagreement logic) into a custom `Searcher` class. Ray handles distributed trial execution; your searcher decides which parameter configurations to run next.
2. **Ray Core + `adaptive`**: `adaptive` supports pluggable parallel executors. You can use Ray Actors as the execution backend instead of its default ipyparallel, giving you Ray-style distributed trial scheduling with adaptive sampling logic.

## Is There a One-Click Complete Tool?
No single Python library currently bundles "curvature-aware adaptive sampling + decorrelating design + symbolic formula discovery + uncertainty-driven refinement" into one pip-installable package. The pattern is always:
> **adaptive sampler → collects data → symbolic regressor → produces formula → (optional loop)**

That said, the `adaptive + PySR` combination requires less than 50 lines of glue code to implement the full loop, and both libraries are production-grade.
