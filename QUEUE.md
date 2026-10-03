# QUEUE.md — persisted panel queue (SSOT; see RESEARCH_METHOD.md §6b)

State lives here, not in a session. A chain's last step must launch the next entry and mark the
finished one `done`. If nothing is running and no entry is `running`/`armed`, arm the top `pending`.

Legend: `done` | `running` | `armed` (launched, queued on the GPU lock) | `pending` | `blocked`

| # | panel | script | summary | state | note |
|---|---|---|---|---|---|
| 1 | ✅DONE Ternary SIZE SERIES (Bonsai 1.7B/8B group-64 Q2_0, MultiPL-E cpp+py) | `.wrapup/run_m24.sh` (worker-built) | `.wrapup/m24_summary.jsonl` | running | turns our one ternary point into a curve; 27B row already in DB (`m21-bonsai-ternary`) |
| 2 | RUNNING Compute-precision factorial (FA on/off × V-cache f16/q8_0, 2B Q2/Q3, cpp+py) | worker-built | `.wrapup/m29_summary.jsonl` | armed | 3 cells (the FA-off+V-q8_0 cell is impossible in build 4399) |
| 3 | Expert-wise precursor (same MoE base, two vendor recipes at ~equal size) | — | `.wrapup/m25b_summary.jsonl` | pending | only if an existing pair exists ≤15 GB download |
| 4 | ARMED KV-quant × ctx grid (K vs V asymmetry at 8k/24k/48k, one model) | `.wrapup/run_m30.sh` | `.wrapup/m30_summary.jsonl` | armed | 2B Q3 × ctx{8192,24576,49152} × KV{f16/f16,q8_0/f16,f16/q8_0,q8_0/q8_0}, cpp 161; `-fa on` fixed (quantised V needs FA); chain step 2/3 |
| 5 | ARMED Sampling × quant, widen to top_k (2B Q2/Q3/Q4 × top_k 20/40/64 at temp 0.3) | `.wrapup/run_m31.sh` | `.wrapup/m31_summary.jsonl` | armed | top_k server-side, seed 1234, cpp+py; top_k=40 column anchors m27's temp-0.3 cells; chain step 3/3 |
| 6 | ARMED Ternary Bonsai on multi-turn + long-context (does off-curve survive the hard axis?) | `.wrapup/run_m32.sh` | `.wrapup/m32_summary.jsonl` | armed | 27B Q2_g64, native-FC handler, `-c 196608 -np 2` (98 304/slot), `multi_turn_base,multi_turn_long_context`; base re-run = noise floor vs m22's 0.695; chain step 1/3 |
| 7 | More architecture families on MultiPL-E (MiniCPM5, Nemotron-3, Ornith, GLM-4.7) | — | `.wrapup/m33_summary.jsonl` | pending | breadth; run when nothing higher is armed (Tier 5A) |
| 8 | TernaryQuench-Qwen3.8-27B (third-party ternary/1-bit, new family) | — | `.wrapup/m34_summary.jsonl` | pending | download ~9.3 GB; tests whether ternary-off-curve generalises beyond Bonsai |
| 9 | ModelScope sweep for other sub-2-bit/IQ1 releases | — | `.wrapup/m35_summary.jsonl` | pending | any new ternary/IQ1 family found gets the standard panel |

## Armed chain

`.wrapup/run_m32_30_31_chain.sh` (launched detached 2026-10-03 09:02, logs `.wrapup/m30_32.log`) waits for the
`m29_launch.sh` panel to exit, then runs **#6 → #4 → #5**, each inside its own `bash gpu_locked.sh ...`. Its tail
launches `run_m33.sh` if that script exists, else logs a STOP banner — **#7..#9 still have no script**, so the GPU
idles after #5 until one is built (next build candidate: #7).

## Standing rules

* One GPU job at a time (`flock /tmp/llama_gpu.lock` via `.wrapup/gpu_locked.sh`).
* Verify the model loads (one real completion) before committing a long panel.
* A panel writes only its own summary; the integrator owns `migrate_db.py` and git.
* 0.00 ⇒ suspect the harness (per-slot ctx, handler dialect, stale result file) before capability.
