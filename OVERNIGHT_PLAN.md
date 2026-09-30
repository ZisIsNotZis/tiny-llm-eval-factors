# Overnight research plan (2026-09-30) — orchestrated by the main agent

## Mission

Settle two open questions and broaden coverage:

* **Q-A ("≥ Q3 is enough" paradox).** Our MultiPL-E panels say there is no measurable
  score gain above Q3, yet local-deployment advice universally says Q4/Q5/Q6, and PPL keeps
  improving above Q3. Resolve *why*.
* **Q-B (agentic depth).** Our tool-calling panel is single-turn BFCL. Test multi-turn /
  harder agentic categories across models, and check whether our conclusion survives.

Plus: broaden model/architecture diversity, and repair the excluded `gemma-4-12B` case.

## Hypotheses for Q-A

* **H1 saturation** — these benchmarks are too easy/coarse: PPL keeps improving while
  pass@1 hits a ceiling.
* **H2 metric resolution** — binary pass@1 on ~161–400 items cannot resolve the remaining
  differences; a continuous metric (per-test fraction) would.
* **H3 task mismatch** — Q4/Q5 gains live on harder/longer tasks (multi-turn, long context,
  instruction following), not on short single-function synthesis.
* **H4 different source** — the Q4/Q5 advice comes from PPL/NL quality, not code benchmarks.

Tests: T1 = PPL ladder (code + NL corpora); T2 = continuous code metric; T3 = multi-turn /
live BFCL; T4 = more families.

## Environment (do not rediscover)

* llama.cpp: `/home/z/.local/bin/llama-server`, `/home/z/llama.cpp/build/bin/llama-perplexity`.
* Model files (symlinks with `.gguf`): `/home/z/hf/<name>.gguf`.
* MultiPL-E harness: `/home/z/hf/research/.wrapup/mpl_run.py` (gen + per-language eval).
* BFCL harness: `/home/z/hf/research/.wrapup/bfcl_run.py` (prompt + native tools modes).
* BFCL data (bundled): `/home/z/hf/research/.wrapup/bfclenv/lib/python3.11/site-packages/bfcl_eval/data/`.
* MultiPL-E prompts (generated locally): `/tmp/MultiPL-E/prompts/humaneval-<lang>.jsonl`.
* ModelSource downloads: `/home/z/hf/research/.wrapup/msenv/bin/modelscope download --model <repo> <file> --local_dir /home/z/hf/mscache/<repo>` then symlink to `/home/z/hf/<file>`.
* GitHub proxy: `https://ghfast.top/https://github.com/...`. PyPI: `https://pypi.tuna.tsinghua.edu.cn/simple`.
* Working dir for runs: `/home/z/hf/research/.wrapup`. DB: `/home/z/hf/research/experiments.sqlite`.

## MANDATORY: GPU is serial

**One llama-server / llama-perplexity at a time.** Wrap every GPU section:

```bash
flock -w 21600 /tmp/llama_gpu.lock <your-command>
```

Use `.wrapup/gpu_locked.sh` (created) as `bash gpu_locked.sh <cmd...>`.
Do **not** run a second server while another is up. Check
`ss -ltnp | grep :8080` and `nvidia-smi` before starting.

## Protocol rules (non-negotiable)

1. Every run must record: model, quant, ctx, KV type, protocol string, sampling, dataset.
2. **Never mix protocols** in a comparison (raw vs chat vs tools; forced vs native).
3. Greedy (temperature 0) unless stated; ctx 2048–4096; KV `q8_0/q8_0`; `--jinja`.
4. Do not modify llama.cpp or other upstream projects.
5. Write results to the paths below; append one JSON object per line.

---

## T1 — PPL ladder (priority 1; answers H1/H4)

Deliverable: `.wrapup/ppl_summary.jsonl`, `.wrapup/ppl_corpora/*.txt`, `PPL_REPORT.md`.

Corpora (build once, from local data; keep ~200k–2M tokens each):
* `code_python.txt` — HumanEval+ / MBPP canonical solutions + tests (from
  `~/.cache/evalplus/*.jsonl` and `/tmp/MultiPL-E/datasets/originals/`).
* `code_multi.txt` — MultiPL-E cpp/java/js/rs prompts+tests (`/tmp/MultiPL-E/prompts/`).
* `nl_english.txt` — BFCL question text (`bfcl_eval/data/BFCL_v4_*.json`).
* Optional if reachable: a slice of wikitext via `ghfast.top` — do not block on it.

Measure with:
```bash
llama-perplexity -m /home/z/hf/<model>.gguf -f <corpus.txt> -c 2048 --chunks 40
```
(Keep flags identical across models/quants; capture the final `Final estimate: PPL = ...`.)

Ladder (run every point):
| anchor | quants |
|---|---|
| Qwen3.5-2B | UD-IQ2_XXS, UD-IQ2_M, UD-Q2_K_XL, UD-Q3_K_XL, UD-Q4_K_XL, UD-Q5_K_XL |
| Qwen3.5-0.8B | UD-Q2_K_XL, UD-Q3_K_XL, UD-Q4_K_XL, UD-Q5_K_XL |
| Qwen3.5-4B | UD-Q2_K_XL, UD-Q3_K_XL, UD-Q4_K_XL, UD-Q5_K_XL |
| gemma-4-E2B-it | UD-Q2_K_XL, UD-Q3_K_XL |
| granite-4.1-3b | Q2_K, Q3_K_M, Q4_K_M |

Download any missing quant with ModelScope (e.g. `unsloth/Qwen3.5-2B-GGUF` has UD-Q5_K_XL etc.).

Output per line: `{"model","quant","corpus","ppl","n_chunks","ctx"}`.
Then join with existing pass@1 (`experiments.sqlite`, `bench_family='humaneval-multipl-e'`)
and report: **does PPL keep improving where pass@1 is flat?** Plot/table both.

## T2 — continuous code metric (answers H2)

Deliverable: `.wrapup/testfrac_*.jsonl`, section in `PPL_REPORT.md`.

For each completion in `.wrapup/mres/m1-*.jsonl` / `m3-*.jsonl` / `m5-*.jsonl` / `m6*.jsonl`
(they contain the model completions), compile+run and count **fraction of provided tests that
pass** instead of binary pass. Reuse `mpl_run.py eval_one`, but instrument the test harness to
report how many assertions ran vs failed. If per-test instrumentation is too invasive, instead
report **pass@k with k = 1, 5** by generating 5 samples per item for one anchor
(`Qwen3.5-2B` Q3 vs Q4 vs Q5, 2 languages) and measuring whether the *distribution* differs.
Whichever is cheaper — but do produce a non-binary view.

## T3 — harder agentic coverage (answers Q-B / H3)

Deliverable: `.wrapup/m8_summary.jsonl`, `.wrapup/m9_summary.jsonl`, section in `MULTIPLE.md`-style report.

1. **Live BFCL categories** (single-turn, already AST-matchable, just add to `bfcl_run.py`
   `VALID` + run): `live_simple`, `live_multiple`, `live_parallel`,
   `live_parallel_multiple`, `live_irrelevance`, `live_relevance`.
   Run native tools on: Qwen3.5-2B Q2/Q3, Qwen3.5-4B Q2/Q3, gemma-4-E2B Q2/Q3,
   granite-4.1-3b Q2/Q3. (Note: `live_irrelevance` may have no GT file → treat as "no call".)
2. **Multi-turn BFCL** (`multi_turn_base`, `multi_turn_miss_func`, `multi_turn_miss_param`,
   `multi_turn_long_context`) if you can wire the bundled function implementations
   (`bfcl_eval/eval_checker/multi_turn_eval/func_source_code`). If not feasible in the time
   budget, say so explicitly in the report — do not fake it.

## T4 — diversity + repairs

Deliverable: new MultiPL-E rows for new anchors; fix `gemma-4-12B`.

1. **gemma-4-12B repair**: it emits `<|channel>thought` in raw mode. Add `"<|channel>"` and
   `"<channel|>"` to the stop list (and/or run chat mode with
   `chat_template_kwargs={"enable_thinking": false}`). Re-run `cpp`+`py` for Q2 and Q3 and
   record. Report whether the earlier ~0 scores were protocol-only.
2. **More anchors** (download via ModelScope, then MultiPL-E cpp/py/js): prioritise *new
   architecture families or clearly different sizes*: `unsloth/Qwen3.8-27B-GGUF` (Q2/Q3),
   `unsloth/gemma-4-26B-A4B-it-GGUF` (Q2/Q3), and search ModelScope for
   MiniCPM5 / NVIDIA-Nemotron-3-Nano-4B / Ornith / LFM2.5 with any **two adjacent quant levels**
   (they need not be Q2/Q3 — record which pair you used).
   Skip anything that OOMs; reduce `-c` to 2048 first, and record failures.

---

## Reporting

Append findings as new bullets to `conclusions.md` with the standard format
`* **[VERIFIED, wrap-up <tag>] claim.** | evidence reference: <file> | scope/conditions: ...`.

Also write a short `PPL_REPORT.md` (for T1/T2) with the PPL-vs-score table and a verdict on
H1–H4. Then stop; the main agent will integrate and commit. Keep raw artifacts under
`.wrapup/`; do not commit.

## Guardrails

* If a model fails to load (OOM / unsupported arch), record it and move on — never hang.
* Always `kill` your llama-server before releasing the GPU lock.
* Prefer 2–3 languages per anchor over 6 when time is tight; count is less important than
  cross-family consistency for T4.
* Keep every command's output in a `.log` under `.wrapup/` so the main agent can audit.
