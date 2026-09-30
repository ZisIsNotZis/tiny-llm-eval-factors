# Task Queue

| task_id | state | priority | description |
|---|---|---:|---|
| kv-kvctx-factorial-r2 | completed | 1 | KV quant factorial at `ctx=8192` across `k_quant/v_quant` and `parallel_slots` on Humaneval+MBPP. |
| reasoning-validity-decomp-r2 | completed | 2 | Extract `valid_output_rate` and `pass|valid` for reasoning modes from existing result JSONs. |
| sampling-second-contrast-r2 | completed | 3 | Second high-contrast sampling run to test HumanEval/MBPP split persistence. |
| evalperf-generalization-r2 | blocked | 4 | Blocked in current environment: EvalPerf requires Linux perf permissions (`perf_event_paranoid`) and fails without privileged sysctl change. |
| sampling-orthogonal-panel-r2 | completed | 4 | Complete the 2x2 sampling panel by adding `t=0.6,k=20` and `t=0.3,k=64` under fixed server-side controls. |
| arch-decouple-panel-r2 | completed | 5 | Matched-size/matched-quant cross-architecture anchors completed at 2B and 4B under the same strict protocol. |
| quant-shape-fit-r2 | completed | 6 | Held-out check completed on current quant-rich `pass_rate` panels (linear > simple quadratic/hinge); primary `pass@1_plus` quant ladder still needed for final claim. |
| walltime-residual-backfill-r2 | completed | 7 | Residual nulls classified: 42 rows still have `wall_time_sec IS NULL` with `source_file`, and none have recoverable direct `.txt` timing logs in `evalplus_results`. |
| qat-factor-anchors-r3 | completed | 1 | QAT anchors inserted for Gemma E2B and E4B at `ctx8192/par1/reaoff/temp0.0`: E2B (`fp16/fp16`) HE `0.06098`, MBPP `0.20899`; E4B (`q8_0/q8_0`) HE `0.82927`, MBPP `0.65344` (vs non-QAT E4B: HE `0.80488`, MBPP `0.66667`). |
| kv-longctx-separate-kv-r3 | completed | 1 | Long-context separate-K/V probe at `ctx24576` with numeric KV ratios (from `llama.cpp`) completed on Humaneval for `Qwen3.6-27B-UD-IQ2_M`: K-only (`ctk=q8_0,ctv=f16`) `pass@1_plus=0.00610`, V-only (`ctk=f16,ctv=q8_0`) `pass@1_plus=0.00000`. |
| qat-e2b-strict-kv-match-r4 | completed | 1 | Strict E2B QAT match completed under `q8_0/q8_0`, `ctx8192/par1/reaoff` on Humaneval+MBPP: QAT vs non-QAT deltas = HE `+0.62805`, MBPP `+0.34656`; rows include explicit `start_time` and `reason` metadata. |
| collision-prone-legacy-rerun-r4 | pending | 2 | Re-run highest-impact collision-prone legacy slices with unique sample identities to replace cache-collision artifacts in old Qwen3.6-27B quant/KV/MTP labels. |
| automated-coverage-sweep-r4 | blocked | 1 | Stopped by directive: fixed-loop GGUF sweep is disallowed. Replace with manually selected high-EIG runs only; each launch must record explicit `start_time` and `reason` in DB. |
| manual-orthogonal-sampling-panel-r5 | completed | 1 | Manual single-variable sampling panel completed on `LFM2.5-230M-UD-Q4_K_XL` (`ctx2048`, `q8_0/q8_0`, no MTP): baseline + `{temp,top_p,top_k,min_p,presence}` one-at-a-time on Humaneval+MBPP with explicit `start_time`/`reason` per row. |
| manual-orthogonal-kv-panel-r5 | completed | 1 | Manual one-sided KV panel completed on `LFM2.5-230M-UD-Q4_K_XL` (`ctx2048`, fixed sampling): `f16/f16` baseline, `q8_0/f16`, `f16/q8_0` on Humaneval+MBPP with explicit `start_time`/`reason`. |
| manual-reasoning-onoff-panel-r5 | completed | 1 | Manual strict reasoning on/off pair completed on `LFM2.5-230M-UD-Q4_K_XL` at fixed settings (`ctx2048`, `q8_0/q8_0`, baseline sampling) for Humaneval+MBPP with explicit `start_time`/`reason`. |
| manual-nemotron-sampling-reasoning-panel-r6 | completed | 1 | Manual unseen-architecture panel completed on `NVIDIA-Nemotron-3-Nano-4B-UD-Q4_K_XL` (`ctx2048`, `q8_0/q8_0`, no MTP): baseline, `top_k 40->20`, and strict reasoning on/off across Humaneval+MBPP with explicit `start_time`/`reason`. |
| manual-granite-kv-onesided-panel-r7 | completed | 1 | Manual unseen-architecture one-sided KV panel completed on `granite-4.1-3b-UD-Q3_K_XL` (`ctx2048`, fixed sampling, reasoning off): `f16/f16`, `q8_0/f16`, `f16/q8_0` on Humaneval+MBPP with explicit `start_time`/`reason`. |
| manual-granite-longctx-kv-onesided-panel-r8r9 | completed | 1 | Manual unseen-architecture long-context one-sided KV panel completed on `granite-4.1-3b-UD-Q3_K_XL` (`ctx24576`, fixed sampling, reasoning off): Humaneval (`manualeig8`) and MBPP (`manualeig9`) each with `f16/f16`, `q8_0/f16`, `f16/q8_0`; all rows include explicit `start_time`/`reason`. |
| manual-qwen4b-quantmix-r10 | completed | 1 | Manual Qwen3.5-4B quant ladder + KV contrast completed: `Q2_K_XL/q8_0/q8_0`, `Q3_K_XL/q8_0/q8_0`, and `Q3_K_XL/q8_0/q5_1` across Humaneval+MBPP with explicit `start_time`/`reason`. |
| manual-gemma12b-quantmix-r11a | failed | 2 | Initial Gemma-12B quant-mix attempt was stopped due poor throughput relative to information gain under current constraints; partial rows exist and are kept as low-priority auxiliary evidence. |
| manual-gemmae2b-quantmix-r11 | completed | 1 | Manual Gemma-E2B quant ladder + KV contrast completed: `Q2_K_XL/q8_0/q8_0`, `Q3_K_XL/q8_0/q8_0`, and `Q3_K_XL/q8_0/q5_1` across Humaneval+MBPP with explicit `start_time`/`reason`. |
| manual-qwen2b-quantmix-r13 | completed | 1 | Manual Qwen3.5-2B quant ladder + KV contrast completed: `Q2_K_XL/q8_0/q8_0`, `Q3_K_XL/q8_0/q8_0`, and `Q3_K_XL/q8_0/q5_1` across Humaneval+MBPP with explicit `start_time`/`reason`. |
| serial-cap-family-search-r14 | completed | 1 | Serial timing-tracked exact-formula cap search completed (27 combinations over `{rational,exp,tanh}` for size/activation/quant caps), results stored in `.serial_formula_search_caps.csv`; best CV RMSE `0.119596` at `(rational,rational,tanh)`. |
| manual-high-eig-benchmark-runs-r15 | running | 1 | Continue serial manual high-EIG benchmark launches (one GPU job at a time) with explicit `start_time` and `reason`, prioritizing unresolved assumptions that block generic coefficient claims. |
| larger-scale-quantmix-anchor-r15 | pending | 1 | Run same quant-mix ladder (`Q2->Q3` at `q8/q8` plus `Q3 q8/q5_1`) on largest feasible Qwen/Gemma anchor to test scale generalization of weight-dominant local effect. |
| third-family-longctx-kv-r15 | pending | 1 | Run one additional long-context one-sided KV panel on a third family anchor (`f16/f16`, `q8_0/f16`, `f16/q8_0`) to resolve contradictory long-context KV behavior. |
| additional-reasoning-strict-pair-r15 | pending | 2 | Run one strict reasoning on/off pair on another family anchor with fixed controls to strengthen reasoning sign/time generalization. |
| **wrapup-resolution-analysis-r16** | completed | 1 | Measured resolution floors + MDE (`resolution.py`/`resolution.md`); tagged all 36 claims (`claims_ledger.py`/`CLAIMS_RESOLUTION.md`). |
| **wrapup-archive-manifest-r16** | completed | 1 | Inventoried surviving evidence (`archive_manifest.py`/`ARCHIVE_MANIFEST.md`): 22/181 models, 63/1881 eval results. |
| **wrapup-reanalysis-r16** | completed | 1 | Strict re-check of headline claims (`reanalysis.py`/`REANALYSIS.md`): falsified the validity-collapse claim; verified matched reasoning + weight-quant ladders. |
| **wrapup-w1-repeat-noise-r16** | running | 1 | Repeat-noise experiment on frozen protocol (`Qwen3.5-2B-UD-Q4_K_XL`, HE greedy x3 + sampling x5, MBPP sampling x3): the measurement the DB never had. |
| **wrapup-w2-scale-ladder-r16** | pending | 1 | Scale-generalisation ladder on restored weights: `Qwen3.5-9B` Q2/Q3 and `Qwen3.5-4B` Q2/Q3 on HumanEval, 2 reps each. |
| **wrapup-report-r16** | completed | 1 | Honest closing report (`build_wrapup.py`/`WRAPUP.md`) + README rewrite; blocked items formally closed. |
| **db-schema-replicates-r17** | completed | 1 | Schema upgrade (`migrate_db.py`): added `run_tag, rep, ctx_size, parallel_slots, seed, protocol, language, bench_family, max_tokens, source_file, completed_at`; dropped the unique index that forbade replicates. |
| **multipl-e-harness-r17** | completed | 1 | Built `mpl_run.py` (raw-completion generation + per-language execution) and generated 7 language datasets locally from the MultiPL-E translators. |
| **multipl-e-resolution-panel-m1-r17** | completed | 1 | `Qwen3.5-4B` Q2/Q3 × 6 languages (~957 items/side). Result: `Q2->Q3 = +0.142` 95% CI [+0.110,+0.174], positive in every language. |
| **multipl-e-scale-panel-m2-r17** | completed | 1 | `Qwen3.5-9B` Q2/Q3 × 3 languages. Result: `+0.143` 95% CI [+0.104,+0.182] — confirms the effect at 9B and shows the HumanEval 9B "flip" was a chat-protocol artifact. |
| **db-ingest-wrapup-runs-r17** | completed | 1 | Ingested W1 (11) + W2 (8) + M1 (12) + M2 (6) = 37 new rows; DB now 1918 rows, held-out schema for protocol/ctx/rep. |
