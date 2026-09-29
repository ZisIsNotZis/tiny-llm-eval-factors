# tiny-llm-eval-factors

**What actually moves benchmark scores for small quantized LLMs — a controlled, compute-light factor study.**

This project quantifies how *quantization ratio*, *KV-cache quantization*, *sampling parameters*,
*reasoning mode*, *MTP*, *context length*, *concurrency*, *model size* and *architecture family*
affect **downstream benchmark scores and wall time** on code-generation tasks (HumanEval / MBPP).

It is deliberately **not** a leaderboard. The point is methodology under a hard compute budget:
every experiment is chosen by expected information gain, every claim carries a confidence tag, and
negative / confounded results are reported as such.

> **Core stance: PPL is easy to measure and benchmarks are not — and lower PPL does not mean a higher
> score. So model the benchmark directly, not a perplexity proxy.**

## Data

- **1,749 deduplicated experiment rows** (1,880 raw) in `experiments.sqlite`.
- **25 model families / 181 checkpoints** (Qwen, Gemma, GLM, LFM, MiniCPM, Nemotron, SmolLM, …).
- Factors: `model_arch, version, size_b, activated_size_b, qat, quant_ratio, k_quant, v_quant,
  reasoning, mtp, temperature, top_p, top_k, min_p, presence_penalty, parallel_slots, ctx_size, dataset`.
- Outcomes: `score (pass@1_plus)`, `bad_rate`, `wall_time_sec`.

## Method

1. **EIG-ranked, serial experiments.** No blind / random sweeps: each run is chosen to resolve the
   weakest evidence point. One GPU job at a time keeps timing attribution clean.
2. **Matched controls + orthogonalized residuals.** Exact matched pairs where possible; otherwise
   cross-fit residual-on-residual estimation with bootstrap CIs over a broad high-EIG panel.
3. **Physical-constrained model.** `pred = 1 - exp(-raw)` with saturating caps on size / activation /
   quant ratio, so `size, act, quant → 0 ⇒ score → 0`. Caps compared over 27–36 structural variants.
4. **Confidence tags everywhere.** Every claim in `assumptions.md` / `questions.md` / `conclusions.md`
   carries a confidence level and an evidence reference.

## Results

Score model (checkpoint-held-out RMSE **0.195**, vs ridge baseline 0.210). Generalization is graded by
how strictly the held-out split is chosen (`python3 cv_generalization.py`):

| held-out regime | meaning | RMSE |
|---|---|---|
| random | random rows (optimistic; same-run leakage) | 0.194 |
| checkpoint | new GGUF of a seen family | 0.195 |
| **family + dataset** | **new architecture AND new benchmark** | **0.277** |
| family | new architecture | 0.294 |

Wall-time model: all-factor ridge, CV RMSE(log) **0.311** (~36% multiplicative error).

Key findings (all with scope caveats, see `conclusions.md`):

- Enabling reasoning **collapses output validity** (`bad_rate ≈ 0.80`) — most raw-score loss is
  invalid-output, not inability.
- Quant-ratio has a **positive** pooled effect, but the **matched local ladders** are the correct
  source for its size (the pooled fit absorbs it into family/size weights).
- `top_k` is the dominant sampling knob; temperature is weak at fixed `top_k`.
- KV quantization is **asymmetric**: at extreme long context the **V side degrades more than K**.
- Cross-architecture ordering **flips with size** — no universal ranking.
- **QAT is not a universal win** (sign flips across datasets in the same model).
- Honest failures: the pooled quant attribution is unreliable; activated-size is near-inert under the
  fitted `tanh` cap.

## Reproduce

```sh
python3 -m pip install -r requirements.txt
python3 cv_generalization.py        # four held-out regimes + cv_generalization.json
python3 refit_formula.py --bootstrap 200   # full refit + coefficient CIs (slow)
python3 build_score_model.py        # emits score_model.py from refit_results.json
```

Data lives in `experiments.sqlite`. Raw per-run eval outputs under `evalplus_results/` are large and
regenerable, so they are git-ignored; the curated DB is committed.

## Layout

- `experiments.sqlite` — curated experiment rows (analysis input).
- `refit_formula.py` — structural model, GroupKFold CV, bootstrap CI, cap-family search.
- `cv_generalization.py` — checkpoint / family / family+dataset / random held-out RMSE.
- `score_model.py` — importable score predictor (`from score_model import predict_score`).
- `optimize.py`, `build_score_model.py`, `serial_high_eig_runner.py`, `exp.py` — experiment runner + model build.
- `conclusions.md` / `assumptions.md` / `questions.md` / `report.md` — knowledge base with confidence tags.
- `projections.csv` — end-to-end effect projections (quant ladder, KV shift, reasoning toggle, size sweep).

## Status & limitations

- **Ongoing, paused for compute** (single RTX 4090 + slow network). Conclusions are scoped to the
  observed panel; several are single-model local effects, not universal laws.
- HumanEval / MBPP are **too easy** to separate models at the margin — the next step is Harness-level
  benchmarks (Terminal-Bench / SWE-bench style), which are far slower here.
- 25 families / 181 checkpoints are **downloaded weights evaluated**, not self-trained; this is an
  evaluation study, not a training study.

## License

MIT (see `LICENSE`).
