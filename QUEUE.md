# QUEUE.md — persisted panel queue (SSOT; see RESEARCH_METHOD.md §6b)

State lives here, not in a session. The QUEUE driver (`QUEUE_DRIVER.sh`) runs the list
below, marks each entry done/FAIL/SKIP, and never stops on a failure. If nothing is
running and no entry is `running`/`armed`, arm the driver (see "Armed driver").

Legend: `done` | `running` | `armed` (launched, queued on the GPU lock) | `pending` | `blocked`

| # | panel | script | summary | state | note |
|---|---|---|---|---|---|
| 1 | ✅DONE Ternary size series (Bonsai 1.7B/8B g64 Q2_0, MultiPL-E cpp+py) | `.wrapup/run_m24.sh` | `.wrapup/m24_summary.jsonl` | done | 4 rows (1.7B/8B × cpp/py) |
| 2 | ✅DONE Compute-precision factorial (FA on/off × V-cache, 2B Q2/Q3, cpp+py) | `.wrapup/run_m29.sh` | `.wrapup/m29_summary.jsonl` | done | 24 rows |
| 3 | MERGED into #11 (Tier 1A expert-wise precursor) | — | `.wrapup/m37_summary.jsonl` | done | a matched-size pair exists on disk (no ≤15 GB download needed) |
| 4 | 🔧ARMED KV-quant × **input length** grid (K vs V asymmetry) — repaired | `.wrapup/run_m30.sh` | `.wrapup/m30_summary.jsonl` | armed | old 12 rows were a **null by construction** (short prompts, only the allocated `-c` moved); now each prompt is padded to just under the target ctx with other HumanEval prompts+solutions (`m30_build_pad.py`), 12 cells × 60 items, `prompt_tokens` recorded |
| 5 | 🔧ARMED Sampling × quant, top_k widened — repaired | `.wrapup/run_m31.sh` | `.wrapup/m31_summary.jsonl` | armed | old K {20,40,64} was **inside the noise** at temp 0.3 (2–4/161 completions differ, pass@1 identical); now K {1,20,40,64,200} at temp 0.3 seed 1234, 2B Q2/Q3/Q4 × cpp+py |
| 6 | 🔧ARMED Ternary Bonsai multi-turn (base) — repaired | `.wrapup/run_m32.sh` | `.wrapup/m32_summary.jsonl` | armed | FAILED twice: (1) both `accuracy:null` from a 2 h-truncated `generate` (138/200, 49/200) + official `evaluate` aborting on the row-count mismatch; (2) `SERVER FAIL` because `m32_preflight.sh` started its server at `-c 262144` and OOM'd (`cudaMalloc failed: out of memory`) while the foreign helpagent server (:8834) was co-resident, so no tool call was ever sent. Fixed: preflight now steps ctx down (32768→16384→8192, NP=1) with the server log tail printed on failure; after two attempts it writes `.wrapup/m32_BLOCKED.md` instead of a null row. `run_m32.sh` runs only `multi_turn_base` at `-c 65536 -np 1` (fallback 32768); `multi_turn_long_context` (~117k-token prompts, >16 GB KV) recorded BLOCKED-on-VRAM. Re-armed behind m31/m30b via `.wrapup/arm_m32_after_fixes.sh` |
| 7 | Architecture-family breadth (MiniCPM5, Nemotron-3, Ornith-1.5, GLM-4.7-Flash) | `.wrapup/run_m33.sh` | `.wrapup/m33_summary.jsonl` | armed | Tier 5A; 4 models × cpp+py = 8; GLM-4.7-Flash-UD-Q3_K_XL is the only download |
| 8 | Third-party ternary/1-bit family (generalise off-curve beyond Bonsai) | `.wrapup/run_m34.sh` | `.wrapup/m34_summary.jsonl` | armed | "TernaryQuench" is NOT on ModelScope (searched 2026-10-06) → probes it, falls back to Ternary-Bonsai-2-27B PTQ1_0/PQ2_0; load-gated |
| 9 | Sub-2-bit model sweep | `.wrapup/run_m35.sh` | `.wrapup/m35_summary.jsonl` | armed | Bonsai-4B-Q2_0_g64 (new size point), Bonsai-27B-Q1_0, Qwen3.5-35B-A3B-IQ1_M = 3 × cpp+py = 6 |
| 10 | 🆕ARMED Ternary Bonsai on other multi-turn types (miss_func / miss_param) — **repaired** | `.wrapup/run_m36.sh` | `.wrapup/m36_summary.jsonl` | armed | First run FAILed with 2 nulls: `bfcl evaluate` aborted on a row-count mismatch. Root cause was **truncated generation** (74/200 and 127/200 rows in `.wrapup/m36.log` — miss_func/miss_param are the slowest categories; the 2 h `GEN_TO` was too short), not the model. Fix: tool-call preflight first (`m32_preflight.sh`), ctx `-c 131072 -np 2` (65536/slot, as m22; the old `-c 196608` OOM'd once) w/ `FALLBACK_CTX=98304`, `GEN_TO=18000`, and `PARTIAL_EVAL=1` so a subset still yields a real `accuracy` + `n`. Re-armed behind the queue (`.wrapup/arm_m36_after_queue.sh`, log `.wrapup/m36_arm.log`) and as NEXT_DRIVER step N0 |
| 11 | Tier 1A expert-wise precursor: MoE scheme at matched size | `.wrapup/run_m37.sh` | `.wrapup/m37_summary.jsonl` | armed | Qwen3.6-35B-A3B `UD-Q3_K_XL` 17.23 GB vs `Q3_K_M` 17.12 GB, both on disk = 4 rows |
| 12 | Tier 5B statistical power: MultiPL-E java+js for 2 anchors | `.wrapup/run_m38.sh` | `.wrapup/m38_summary.jsonl` | armed | Qwen3.5-2B Q2/Q3 × {java,js} = 4; doubles items on the Q2→Q3 code step |
| 13 | ✅DONE Second ternary family: GLM-4.7-Flash-UD-TQ1_0 | `.wrapup/run_m39.sh` | `.wrapup/m39_summary.jsonl` | done | 4 rows; + in-family UD-Q2_K_XL reference; load-gated (TQ1_0 = ggml type 35) |
| 14 | 🆕ARMED Ternary generalisation: third-party **quantisers** (dealignai CRACK gen-1/gen-2) | `.wrapup/run_m40.sh` | `.wrapup/m40_summary.jsonl` | armed | Tier 1C/a; 2 rows per candidate that loads (ModelScope search 2026-10-06 found no other cross-architecture ternary); load-gated (gen-2 Prism/CRACK layout = ggml type 142, build 4399 rejects it, m34.log) |
| 15 | 🆕ARMED Partial-credit (T2 testfrac) for ternary vs conventional — fails *fewer* or *different* tests? | `.wrapup/run_m41.sh` | `.wrapup/m41_summary.jsonl` | armed | **CPU-only, 0 GPU**; per-file, cached; ≥10 rows over the ternary arms (m21/mt1 Bonsai, m35 1-bit/IQ1_M, m39 TQ1_0) + their conventional refs |
| 16 | 🆕ARMED Tier 5B power, step 2: MultiPL-E **rust+ruby** for Qwen3.5-2B Q2/Q3 | `.wrapup/run_m42.sh` | `.wrapup/m42_summary.jsonl` | armed | 4 rows; Q2→Q3 item count 644→966; rustc+ruby present, prompts present |
| 17 | 🆕ARMED Tier-2C provenance recovery: rebuild `m26_summary.jsonl` from the existing 2026-10-02 evals | `.wrapup/run_m43.sh` | `.wrapup/m26_summary.jsonl` | armed | **CPU-only, 0 GPU**; 8 rows (gemma-4-26B-A4B MoE vs Qwen3.8-27B dense, Q2/Q3, chat protocol); no re-run |
| 18 | 🆕ARMED Compute-precision probe: is `-fa on/off` a real manipulation? (fixes m29) | `.wrapup/run_m44.sh` | `.wrapup/m44_summary.jsonl` | armed | 6 rows; diffs greedy text between cells BEFORE any score is trusted; `faon_q8` is the positive control |
| 19 | 🆕ARMED Tier 5A/2B: LFM2.5-8B-A1B (Liquid MoE) Q2/Q3 — new family | `.wrapup/run_m45.sh` | `.wrapup/m45_summary.jsonl` | armed | 4 rows; 8B total / 1B active, both files on disk |

## Successor queue (runs when QUEUE_DRIVER.sh hands over to NEXT_DRIVER.sh)

The current driver ends after #19; `NEXT_DRIVER.sh` is the successor it `exec`s (already probed at
its tail). It holds the inherited GPU lock, runs each step under `locked()` (no nested `flock`
deadlock), is idempotent, never stops on failure, and logs START/DONE/FAIL/SKIP to
`.wrapup/NEXT_DRIVER.log`. Entries below are **new axes not covered by #1..#19**.

| # | panel | script | summary | state | note |
|---|---|---|---|---|---|
| 20 (N0) | 🔧ARMED m36 repair — Bonsai miss_func/miss_param (see #10) | `.wrapup/run_m36.sh` | `.wrapup/m36_summary.jsonl` | armed | preflight + `--partial-eval` + larger `GEN_TO`; also armed as a standalone watchdog (`.wrapup/arm_m36_after_queue.sh`) |
| 21 (N1) | 🆕ARMED **m50** imatrix-vs-K at **matched file size** (does IQ buy score per byte?) | `.wrapup/run_m50.sh` | `.wrapup/m50_summary.jsonl` | armed | BRAINSTORM 1B; Qwen3.5-4B IQ3_XXS 1859 MB vs Q2_K_XL 1851 MB (0.4%), Qwen3.5-2B IQ3_XXS 889 MB vs Q2_K_XL 922 MB (3.5%); 4 models × cpp+py = 8 rows |
| 22 (N2) | 🆕ARMED **m51** gemma-4-12B java+js — third-family multilingual-code anchor | `.wrapup/run_m51.sh` | `.wrapup/m51_summary.jsonl` | armed | Tier 5B/5C power on a new architecture family; gemma-4-12b Q2/Q3 × {java,js} = 4 rows |
| 23 (N3) | 🆕ARMED **m52** decode speed vs prompt type + MTP spec-draft length curve | `.wrapup/run_m52.sh` | `.wrapup/m52_summary.jsonl` | armed | BRAINSTORM 4B; records tokens/s (prefill+decode) for code vs prose on gemma-4-12B-Q3 + Qwen3.5-9B-Q3, then `--spec-draft-n-max {2,4,6}` with `mtp-gemma-4-12B-it.gguf` if it loads; ≤10 rows |
| 24 (N4) | 🆕ARMED **m53** ModelScope ternary/1-bit search + load-gated probe | `.wrapup/run_m53.sh` | `.wrapup/m53_summary.jsonl` | armed | BRAINSTORM 1C; best-effort search logged to `m53_search.log`, then resolve+probe up to 2 curated new families (SKIP if unavailable) |
| 25 (N5) | 🆕ARMED **m54** gemma-4-12B rust+ruby — third-family code-anchor power | `.wrapup/run_m54.sh` | `.wrapup/m54_summary.jsonl` | armed | Tier 5B/5C; extends m51 (java+js) to the rust+ruby pair already used for the Qwen3.5-2B power step (m42); no download (both gemma files on disk); 2 anchors × rust+ruby = 4 rows. Armed directly under `gpu_locked.sh` 2026-10-07 13:2x, right after NEXT_DRIVER drained N0–N4 and left the GPU idle at 12:33. |

Expected new work: N0 ≈ 3–8 h (27B, 2 slow categories, download-free), N1 ≈ 0.5 h (4B/2B),
N2 ≈ 0.5 h, N3 ≈ 0.3 h, N4 ≈ 0–1 h (download-gated). Total ≈ 5–10 GPU-h.

## Successor queue #2 — the refill (runs when NEXT_DRIVER.sh hands over to NEXT_DRIVER2.sh)

`NEXT_DRIVER.sh` now ends by handing over to `.wrapup/NEXT_DRIVER2.sh` (same `locked()` pattern,
idempotent, never stops on failure; log `.wrapup/NEXT_DRIVER2.log`). It exists because the previous
tail was non-viable: **m34 / m40 / m53 all fail the load gate with 0 rows** (unsupported ggml types
142/143; no ModelScope release), so the chain drained in ~20 min and the GPU idled. Every entry below
was chosen to be **certain to produce rows**; models are either already proven to serve or are
load-gated on the CPU BEFORE arming.

| # | panel | script | summary | state | note |
|---|---|---|---|---|---|
| E1 | 🆕ARMED **m56** Tier 5B power: LFM2.5-8B-A1B Q2/Q3 × {java,js} | `.wrapup/run_m56.sh` | `.wrapup/m56_summary.jsonl` | armed | same tags `lfm25-8a1b-q2/q3` + same protocol as m45 → doubles items on this MoE anchor; both files on disk, load-gated PASS |
| E2 | 🆕ARMED **m57** Tier 5B power: Nemotron-3-Nano-4B Q2/Q3 × {java,js} | `.wrapup/run_m57.sh` | `.wrapup/m57_summary.jsonl` | armed | same tags `nem4b-q2/q3` as m10 → doubles items on a non-Qwen family; files on disk, PASS |
| E3 | 🆕ARMED **m60** Tier 5B power: Ornith-1.5-9B Q4/Q5 × {rust,ruby} | `.wrapup/run_m60.sh` | `.wrapup/m60_summary.jsonl` | armed | same tags `orn9b-q4/q5` as m10; the rust+ruby pair lands on a different anchor than E1/E2's java+js |
| E4 | 🆕ARMED **m58** Tier 5A new family: Llama-3.2-3B Q2_K/Q3_K_M × cpp,py | `.wrapup/run_m58.sh` | `.wrapup/m58_summary.jsonl` | armed | first Llama-architecture anchor in the study; 3.0 GB fetch from `unsloth/Llama-3.2-3B-Instruct-GGUF`, CPU-load-gate required before the panel |
| E5 | 🆕ARMED **m59** Tier 5A new family: Phi-4-mini Q2_K/Q3_K_M × cpp,py | `.wrapup/run_m59.sh` | `.wrapup/m59_summary.jsonl` | armed | second new family (Phi); 3.8 GB fetch, same CPU gate |
| E6 | 🆕ARMED **m55** Tier 1A expert-wise / mixed-precision quantisation | `.wrapup/run_m55.sh` | `.wrapup/m55_summary.jsonl` | armed | the big untested axis: 3 recipes at matched total size (uniform-Q3_K_M baseline, experts Q2_K + rest ~Q4_K, experts Q4_K + rest ~Q2_K) built by `m55_prebuild.sh` from LFM2.5-8B-A1B **BF16 (16.9 GB, on ModelScope)** via `llama-quantize --tensor-type 'ffn_(gate\|up\|down)_exps'` (66 expert tensors over 22 MoE layers, verified); ≤6 rows |
| E7 | 🔧ARMED **m32** ternary Bonsai multi-turn_base (demoted repair) | `.wrapup/run_m32.sh` | `.wrapup/m32_summary.jsonl` | armed | moved here from NEXT_DRIVER N6 so it cannot block E1–E6; has failed 3× at 1/2 rows |

**Prebuild (CPU + network, no GPU lock):** `.wrapup/m55_prebuild.sh` (launched detached 2026-10-08
01:24, log `.wrapup/m55_prebuild.log`). It (A) CPU-load-gates the on-disk anchors of E1/E2/E3, (B)
downloads + gates the E4/E5 families, (C) downloads the 16.9 GB LFM2.5-8B-A1B BF16, (D) runs
`llama-quantize --dry-run` over a small candidate set to pick the two expert-wise recipes whose size
brackets uniform Q3_K_M, quantises and gates them, writing `.wrapup/m55_recipes.json`. Results are
recorded in `.wrapup/loadgate.jsonl`; `run_m55/58/59.sh` refuse to arm a model whose gate is not PASS.

**Watchdog:** `.wrapup/arm_next2.sh` (detached) polls `flock -n /tmp/llama_gpu.lock` and re-runs
`NEXT_DRIVER2.sh` with `RUN_M32=0` if the live chain dies before draining E1–E6.

Expected new work: E1 ≈ 0.3 h, E2 ≈ 0.2 h, E3 ≈ 0.3 h, E4 ≈ 0.2 h, E5 ≈ 0.2 h, E6 ≈ 0.7 h GPU
(plus ≈ 0.5 h CPU quantise + ≈ 25 GB downloads, done in parallel off-lock). Total ≈ 2 GPU-h, ≈ 22
new rows. **SKIPped:** a second *downloadable* ternary/1-bit family (ModelScope still has none beyond
Bonsai re-uploads + the unsloth GLM TQ1_0 already run in m39; PTQ1_0/PQ2_0/CRACK are ggml types
142/143), and any MoE F16 source >60 GB (gemma-4-26B/Qwen3.6-35B F16 would be 50–70 GB — only the
16.9 GB LFM2.5-8B-A1B BF16 was fetched).

**Integrator note:** the new summaries reuse the standard schema `{model,lang,n,pass,score,protocol}`;
they need one `ingest_mNN` + `REFRESH` line each in `migrate_db.py` with a `model_map` entry per tag
(`lfm25-8a1b-q2/q3`, `nem4b-q2/q3`, `orn9b-q4/q5`, `llama32-3b-q2/q3`, `phi4mini-q2/q3`,
`lfm25-8a1b-m55-*`). Protocol `mpl-raw-greedy-768` on E1–E3 joins the m45/m10 rows in the DB.

## Armed driver

`.wrapup/QUEUE_DRIVER.sh` (re-armed 2026-10-06 19:20; log `.wrapup/QUEUE_DRIVER.log`). It waits
for any running panel **and `run_fixes_after_driver.sh`** to drain, then runs **#7 → … → #19**, each
GPU step inside its own `bash gpu_locked.sh …`; #15 and #17 are CPU-only and run *without* the lock
(they start no server, so holding the lock would only stall the GPU steps). Per-step states are
logged `START` / `DONE` / `FAIL` / `SKIP`, and a failed step never stops the driver. It is
**idempotent**: a step whose summary already has its expected rows (and, for BFCL, zero
`accuracy:null`) is skipped, so re-running after a crash resumes in place.

The re-arm of 2026-10-06 fixes the false-positive idle gate: `wait_for_gpu_idle` no longer probes
`llama-server` by model path (another project serves models from `/home/z/hf/`), it probes
`flock -n /tmp/llama_gpu.lock` (the real ground truth) plus the running panel names. #8/#10/#11 had
logged `FAIL (0 rows)` on the 14:40 drain, so the re-armed driver retries them before the new
entries — that is the idempotent-resume behaviour, not a duplicate run.

Expected new work: #14 ~0.5–1 h (download-gated), #16 ~0.5 h, #18 ~0.5 h, #19 ~1 h, #15 ~0.5 h CPU,
#17 <1 min CPU. Total ≈ 3–4 GPU-h, ≈ 0.5 CPU-h.

The previous chain `.wrapup/run_m32_30_31_chain.sh` is complete; it ended 2026-10-03 23:21 with a
STOP banner because #7–#9 had no scripts. That STOP is exactly the anti-idle failure SSOT 6b warns
about — the GPU then sat idle ~59 h. The driver above replaces the chain tail.

## OPEN RISKS

* **Non-viable entries exhausted (2026-10-08): m34 / m40 / m53.** All three fail the load gate
  with 0 rows: the ternary/1-bit GGUFs on disk (`Ternary-Bonsai-2-27B-PTQ1_0` = ggml type 143,
  `Bonsai-2-27B-PQ2_0-CRACK` = type 142) are rejected by build 4399, and ModelScope has no other
  cross-architecture ternary release. They remain in the driver (idempotent, they just FAIL and move
  on), but the row-producing work now lives in the Successor queue #2 below (E1–E7).

* **#4/#5/#6 are being repaired and re-run** — runner is `.wrapup/run_fixes_after_driver.sh`
  (it waits for `QUEUE_DRIVER.sh` to exit, then takes `/tmp/llama_gpu.lock` per panel). The driver
  drained at 14:40, but the runner then stalled 14:40–16:16 on its "another panel still live" gate:
  the old clause `pgrep -f "[l]lama-server .*-m /home/z/hf/"` matched **another project's**
  long-lived `llama-server` (helpagent, serving a model from the shared `/home/z/hf/` model dir),
  so the hf queue was idle behind a false positive. Replaced with a non-blocking `flock -n`
  probe on `/tmp/llama_gpu.lock` (the real ground truth, since every panel runs under `gpu_locked.sh`)
  and relaunched 2026-10-06 16:16. The old m30/m31 summaries are still on disk and still look
  complete to the driver's row-count idempotency check; the repaired panels rewrite them in place
  (m31 now emits 30 rows, m30 12 rows with an added `prompt_tokens` field).
* **#6 (m32) was incomplete** — both rows `accuracy:null`, from a **2 h-truncated** `generate` (138/200 and
  49/200 result rows) plus 2 real ctx-overflows; official `evaluate` aborts on the row-count mismatch. The
  2026-10-06 retry then hit `SERVER FAIL`: the preflight server (`-c 262144`) OOM'd against the foreign
  helpagent server, so no tool call was sent. Fixed: light preflight (ctx stepped down + log tail) and
  `multi_turn_base`-only at `-c 65536 -np 1`; long_context is BLOCKED-on-VRAM. Re-armed via
  `.wrapup/arm_m32_after_fixes.sh` (waits for m31/m30b, then takes the lock). See OPERATIONS.md for the full diagnosis.
* **#8 name resolution** — "TernaryQuench-Qwen3.8-27B" was not found on ModelScope; #8 uses the
  nearest third-party ternary/1-bit family (Ternary-Bonsai-2-27B PTQ1_0/PQ2_0). If it fails the
  load gate (newer ggml tensor types, BACKLOG B1a) the step logs SKIP and the driver continues.

* **Tier 2C was measured but never ingested.** `run_m26.sh` (gemma-4-26B-A4B MoE vs
  Qwen3.8-27B dense, Q2/Q3, `mpl-chat-nothink-greedy-768`) completed 2026-10-02; its raw
  completions and `_eval.json` files are in `.wrapup/mres/m26-*`, but `m26_summary.jsonl` is
  empty and no `m26` rows are in the DB. #17 rebuilds the summary (CPU); the integrator still has
  to ingest it. Until then the 2C claim is unquotable.
* **Ternary families are scarce on ModelScope.** A 2026-10-06 search for `ternary`/`TQ1_0`/`TQ2_0`
  found only Bonsai-derived builds (prism-ml + re-uploads) and the unsloth GLM build already in #13;
  the one cross-architecture TQ1_0 (`nohurry/Qwen3.5-397B-A17B`, 95 GB) is out of host budget.
  #14 therefore varies the *quantiser* vendor on a fixed Bonsai base, which is the strongest
  available test of whether the off-curve residual is scheme-level or vendor-level.
* **m29 (compute precision) is suspect** — its fa on/off cells were flagged as a possible
  non-measurement. #18 probes the manipulation directly (byte-diff of greedy text) before any score
  is trusted; `faon_q8` (V-cache quant) is the positive control. Read #18 before quoting m29.

## Standing rules

* One GPU job at a time (`flock /tmp/llama_gpu.lock` via `.wrapup/gpu_locked.sh`).
* Verify the model loads (one real completion) before committing a long panel (`panel_mpl.sh`).
* A panel writes only its own summary; the integrator owns `migrate_db.py` and git.
* 0.00 ⇒ suspect the harness (per-slot ctx, handler dialect, stale result file) before capability.
