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
| 4 | ✅DONE KV-quant × ctx grid (K vs V asymmetry) | `.wrapup/run_m30.sh` | `.wrapup/m30_summary.jsonl` | done | 12 rows |
| 5 | ✅DONE Sampling × quant, top_k (2B Q2/Q3/Q4 × top_k 20/40/64) | `.wrapup/run_m31.sh` | `.wrapup/m31_summary.jsonl` | done | 18 rows |
| 6 | ⚠️FAILED Ternary Bonsai multi-turn + long-context (accuracy null) | `.wrapup/run_m32.sh` | `.wrapup/m32_summary.jsonl` | failed | 2 rows both `accuracy:null`; long_context ctx-overflow (117648 tok > 98304/slot). See OPEN RISKS |
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

* **#6 (m32) is incomplete** — both rows are `accuracy:null`. The log shows `multi_turn_long_context`
  prompts reaching 117 648 tokens against a 98 304-token per-slot window (`-c 196608 -np 2`), so
  generation aborted and `evaluate` hit "Length of model result does not match length of test
  entries". Re-running with a larger per-slot ctx is a *protocol change* to an existing panel and is
  not part of this build; #6 is left `failed` and flagged for the integrator.
* **#8 name resolution** — "TernaryQuench-Qwen3.8-27B" was not found on ModelScope; #8 uses the
  nearest third-party ternary/1-bit family (Ternary-Bonsai-2-27B PTQ1_0/PQ2_0). If it fails the
  load gate (newer ggml tensor types, BACKLOG B1a) the step logs SKIP and the driver continues.

## Standing rules

* One GPU job at a time (`flock /tmp/llama_gpu.lock` via `.wrapup/gpu_locked.sh`).
* Verify the model loads (one real completion) before committing a long panel (`panel_mpl.sh`).
* A panel writes only its own summary; the integrator owns `migrate_db.py` and git.
* 0.00 ⇒ suspect the harness (per-slot ctx, handler dialect, stale result file) before capability.
