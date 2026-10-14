# AXES campaign — VRAM-blocked tags (option (a): no end-of-run retry pass)

Operator decision: the AXES campaign is **not** retried for the tags below. They are recorded
BLOCKED-on-VRAM (the repo's existing `m32 multi_turn_long_context` precedent, see
`FINAL_REPORT.md` §6 / `QUEUE.md`). The driver already attempted each stage exactly once and
moved on; no loop-retry was performed and no retry pass will be run.

Context: a **foreign server on port :8834** (`llama-server -m .../Spark-X2.5-4B-Q4_K_M.gguf`,
pid 145968, up since Oct 8, ~12 GB RSS) is co-resident and holds several GB of the single
24 GiB GPU, so the two largest gemma-4 files cannot fit once their own weights + KV are added.

| tag | file | bytes (GiB) | outcome | evidence |
|---|---|---:|---|---|
| m142-qat-gemma31b-q4 | gemma-4-31B-it-qat-UD-Q4_K_XL.gguf | 17287670048 (16.10) | **BLOCKED-on-VRAM** | `.wrapup/mres/m142-qat-gemma31b-q4/server.log` — `allocating 1200.00 MiB on device 0: cudaMalloc failed: out of memory` / `failed to allocate buffer for kv cache` / `llama_server: exiting due to model loading error` |
| m143-native-gemma31b-q4 | gemma-4-31B-it-UD-Q4_K_XL.gguf | 18822970304 (17.53) | **BLOCKED-on-VRAM** (≥ m142's footprint, same co-resident server) | `.wrapup/mres/m143-native-gemma31b-q4/server.log` (see below) |
| m145-native-gemma26b-a4b-q4 | gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf | 17010980576 (15.84) | pending attempt; BLOCKED-on-VRAM if its `server.log` shows the same `cudaMalloc failed` | `.wrapup/mres/m145-native-gemma26b-a4b-q4/server.log` (see below) |

Free VRAM with only the foreign server resident was measured at **~18.4 GB (17.9 GiB)**;
m143 needs ≥17.5 GiB of weights alone plus KV, so it cannot fit under the same conditions that
OOM'd m142. These are non-measurements, not null results — no number is fabricated.

Axis-1.6 impact: the 31B QAT/native pair (m142/m143) is unmeasurable here, so the QAT-vs-native
analysis is carried by the pairs that fit: 12B (m140/m141), 26B-A4B (m144/m145), E2B Q4
(m147/m148), E2B Q2 (m146/m119), E4B Q4 (m155/m156), E4B Q2 (m149/m121). Axis 7 is already
gate-failed (no runtime for `diffusion-gemma`).
