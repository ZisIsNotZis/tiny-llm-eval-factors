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

> **Read every number below against `resolution.md`.** The honest headline of the wrap-up is
> that most of this study's claims sit *below its own noise floor*: with HumanEval+MBPP (542
> items) a single-config capability effect below ~0.084 cannot be resolved, and only **4 of 36**
> documented conclusions clear that bar. See `WRAPUP.md` and `CLAIMS_RESOLUTION.md`.

Score model, compared with a linear ridge baseline under the **same** held-out
regime (`python3 cv_generalization.py` + `python3 ridge_baseline.py`):

| held-out regime | meaning | structural model | ridge baseline | winner |
|---|---|---|---|---|
| random | random rows (optimistic; same-run leakage) | 0.194 | 0.224 | model |
| checkpoint | new GGUF of a seen family | 0.195 | 0.225 | model |
| family + dataset | new architecture AND new benchmark | 0.277 | 0.256 | **ridge** |
| family | new architecture | 0.294 | 0.282 | **ridge** |

**Honest reading:** the physical-constraint model wins in-distribution and on a
new checkpoint of a seen family, but it does **not** beat a plain linear baseline
once the split is strict enough to hold out a whole architecture. The value of
the study is the **controlled effect estimates and the negative results**, not a
generalizing predictor.

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

- **Frozen / archived as of the wrap-up.** Not expected to resume on this host.
- **Evidence base is no longer end-to-end reproducible:** only 22/181 model files (12%) and
  63/1881 raw eval results (3%) survive. See `ARCHIVE_MANIFEST.md`.
- **The dominant limitation is item count, not benchmark difficulty.** HumanEval+MBPP = 542
  items → single-config MDE ≈ 0.084. Resolving the 0.03–0.05 effects the study cares about needs
  ~1,500–4,000 items. The right addition is *more items at similar difficulty* (MultiPL-E,
  18×164 ≈ 2952 items → MDE ≈ 0.036), **not** a harder harness benchmark — BigCodeBench / SWE /
  Terminal-Bench would floor the 0.2B–9B panel near 0 and are compute-hostile.
- `ctx_size`, `parallel_slots`, `start_time`, `reason` and `seed` are **absent from the DB schema**,
  so every conclusion phrased with `ctx=`/`parallel=` is unauditable, and run stochasticity was
  unmeasured until the `W1` repeat experiment (`.wrapup/run_w1.sh`).
- 25 families / 181 checkpoints are **downloaded weights evaluated**, not self-trained; this is an
  evaluation study, not a training study.

## Wrap-up artifacts

| file | purpose |
|---|---|
| `resolution.py` → `resolution.json` / `resolution.md` | measured noise floors + MDE table |
| `claims_ledger.py` → `claims_ledger.csv` / `CLAIMS_RESOLUTION.md` | every claim tagged by resolvability |
| `archive_manifest.py` → `archive_manifest.json` / `ARCHIVE_MANIFEST.md` | what evidence still exists |
| `build_wrapup.py` → `WRAPUP.md` | the honest closing report |
| `.wrapup/run_w1.sh` | repeat-noise experiment (the measurement the study lacked) |

```sh
python3 resolution.py && python3 claims_ledger.py
python3 archive_manifest.py && python3 build_wrapup.py
```

## License

MIT (see `LICENSE`).
