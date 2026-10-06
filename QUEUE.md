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
| 6 | 🔧ARMED Ternary Bonsai multi-turn + long-context — repaired | `.wrapup/run_m32.sh` | `.wrapup/m32_summary.jsonl` | armed | was FAILED: both `accuracy:null` because the 2 h `timeout` truncated `generate` (138/200, 49/200) and official `evaluate` aborts on the row-count mismatch. Now a tool-call preflight + per-slot ctx from observed lengths (`-c 32768` base, `-c 262144`[fallback 196608] long) + `GEN_TO` 4 h/10 h |
| 7 | Architecture-family breadth (MiniCPM5, Nemotron-3, Ornith-1.5, GLM-4.7-Flash) | `.wrapup/run_m33.sh` | `.wrapup/m33_summary.jsonl` | armed | Tier 5A; 4 models × cpp+py = 8; GLM-4.7-Flash-UD-Q3_K_XL is the only download |
| 8 | Third-party ternary/1-bit family (generalise off-curve beyond Bonsai) | `.wrapup/run_m34.sh` | `.wrapup/m34_summary.jsonl` | armed | "TernaryQuench" is NOT on ModelScope (searched 2026-10-06) → probes it, falls back to Ternary-Bonsai-2-27B PTQ1_0/PQ2_0; load-gated |
| 9 | Sub-2-bit model sweep | `.wrapup/run_m35.sh` | `.wrapup/m35_summary.jsonl` | armed | Bonsai-4B-Q2_0_g64 (new size point), Bonsai-27B-Q1_0, Qwen3.5-35B-A3B-IQ1_M = 3 × cpp+py = 6 |
| 10 | Ternary Bonsai on other multi-turn types (miss_func / miss_param) | `.wrapup/run_m36.sh` | `.wrapup/m36_summary.jsonl` | armed | BFCL, handler `Qwen/Qwen3-1.7B-FC`, temp 0, `-c 196608 -np 2`; 2 categories |
| 11 | Tier 1A expert-wise precursor: MoE scheme at matched size | `.wrapup/run_m37.sh` | `.wrapup/m37_summary.jsonl` | armed | Qwen3.6-35B-A3B `UD-Q3_K_XL` 17.23 GB vs `Q3_K_M` 17.12 GB, both on disk = 4 rows |
| 12 | Tier 5B statistical power: MultiPL-E java+js for 2 anchors | `.wrapup/run_m38.sh` | `.wrapup/m38_summary.jsonl` | armed | Qwen3.5-2B Q2/Q3 × {java,js} = 4; doubles items on the Q2→Q3 code step |
| 13 | Second ternary family: GLM-4.7-Flash-UD-TQ1_0 | `.wrapup/run_m39.sh` | `.wrapup/m39_summary.jsonl` | armed | + in-family UD-Q2_K_XL reference; load-gated (TQ1_0 = ggml type 35) |

## Armed driver

`.wrapup/QUEUE_DRIVER.sh` (armed 2026-10-06; log `.wrapup/QUEUE_DRIVER.log`). It waits for
any running panel to drain, then runs **#7 → #8 → #9 → #10 → #11 → #12 → #13**, each inside its
own `bash gpu_locked.sh …`. Per-step states are logged `START` / `DONE` / `FAIL` / `SKIP`, and a
failed step never stops the driver. It is **idempotent**: a step whose summary already has its
expected rows (and, for BFCL, zero `accuracy:null`) is skipped, so re-running after a crash resumes
in place. Expected 17–20 h total (dominated by the 27B/35B ternary + MoE panels).

The previous chain `.wrapup/run_m32_30_31_chain.sh` is complete; it ended 2026-10-03 23:21 with a
STOP banner because #7–#9 had no scripts. That STOP is exactly the anti-idle failure SSOT 6b warns
about — the GPU then sat idle ~59 h. The driver above replaces the chain tail.

## OPEN RISKS

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
  49/200 result rows) plus 2 real ctx-overflows; official `evaluate` aborts on the row-count mismatch. Fixed
  as above; see OPERATIONS.md for the full diagnosis.
* **#8 name resolution** — "TernaryQuench-Qwen3.8-27B" was not found on ModelScope; #8 uses the
  nearest third-party ternary/1-bit family (Ternary-Bonsai-2-27B PTQ1_0/PQ2_0). If it fails the
  load gate (newer ggml tensor types, BACKLOG B1a) the step logs SKIP and the driver continues.

## Standing rules

* One GPU job at a time (`flock /tmp/llama_gpu.lock` via `.wrapup/gpu_locked.sh`).
* Verify the model loads (one real completion) before committing a long panel (`panel_mpl.sh`).
* A panel writes only its own summary; the integrator owns `migrate_db.py` and git.
* 0.00 ⇒ suspect the harness (per-slot ctx, handler dialect, stale result file) before capability.
