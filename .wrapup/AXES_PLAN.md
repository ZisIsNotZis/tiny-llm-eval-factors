# AXES_PLAN.md — three NEW research axes: QAT, GSQ-RCO, DiffusionGemma

Prepared for /home/z/hf/research (quant-vs-score study). Driver: `.wrapup/campaign.sh`
with `CAMPAIGN_FILE=.wrapup/AXES_CAMPAIGN.txt`. GPU discipline unchanged:
`/tmp/llama_gpu.lock` via `flock` (`.wrapup/gpu_locked.sh` / panel scripts).

## 0. What is being added and why

| Axis | Treatment | Control | Held fixed |
|---|---|---|---|
| 1.6 QAT | `gemma-4-<size>-it-qat-UD-Q4_K_XL` | same size native `gemma-4-<size>-it-UD-Q4_K_XL` | size + 4-bit recipe |
| 1.5 GSQ-RCO | `Qwen3.8-27B-GSQ-RCO-IQ3_XXS/IQ3_S` | standard Qwen3.8-27B quants (UD-Q2/Q3/IQ4_XS) | base model 27B |
| 7 DiffusionGemma | `diffusiongemma-26B-A4B-it-Q4_K_M` | `gemma-4-26B-A4B-it` native UD-Q4_K_XL | size + quant class |

The QAT axis isolates the QAT bit: the treatment and control differ only by whether the
weights were QAT-trained. The GSQ-RCO axis compares new GGUF quant types against the
standard Qwen3.8-27B quants that bracket them in bpw. The diffusion axis asks whether
diffusion decoding loses quality at equal size/quant; **it cannot be measured here** because
no local runtime accepts the architecture (see §3).

## 1. Coverage (step A) — what was already in `experiments.sqlite`

Coverage is judged on the canonical protocols from `bpw_sensitivity.py` `BENCH`
(humaneval-plus, mbpp-plus, mmlu, arc_challenge, truthfulqa_mc2, gsm8k reasoning=off, ifeval),
restricted to rows ingested from `.wrapup/mres/` (`source_file LIKE 'mres/%'`).

| model file | canonical cells present | action |
|---|---|---|
| `Qwen3.8-27B-UD-Q2_K_XL.gguf` (m91) | all 7 | control; **not re-run** |
| `Qwen3.8-27B-UD-Q3_K_XL.gguf` (m100) | all 7 | control; **not re-run** |
| `Qwen3.8-27B-UD-IQ4_XS.gguf` | none | new control **m152** |
| `Qwen3.8-27B-GSQ-RCO-IQ3_XXS/IQ3_S` | none | new **m150/m151** |
| `gemma-4-{12B,31B,26B-A4B}-it-qat-UD-Q4_K_XL` | none (only legacy raw humaneval/mbpp) | new |
| `gemma-4-{E2B,E4B}-it-qat-UD-Q2/Q4_K_XL` | none (only legacy raw) | new |
| `gemma-4-E2B-it-UD-Q2_K_XL` (m119), `-E4B-` Q2 (m121), 12B/26B-A4B/E2B/E4B Q2+Q3 natives | all 7 | reused as Q2 native controls; **not re-run** |
| native `gemma-4-<size>-it-UD-Q4_K_XL` | absent from disk + DB | downloaded, new controls |

No canonical cell is re-run. `UD-Q4_K_XL` native controls for the five sizes were neither on
disk nor in the DB, so they are the only new control files.

## 2. Downloads (step B)

`hf download` was the requested transport but is unusable from this host: `huggingface.co`
resolves to a poisoned address and `hf-mirror.com` hangs (`curl` connect fails / times out),
while the xet CDN times out mid-file. The project's own acquisition path for these exact
repos was ModelScope (`.wrapup/dl_fam.sh`), so the missing native Q4 files were fetched with
`.wrapup/axes_dl_mirror.sh` (identical repo ids/filenames; sizes verified against the HF API).
Log: `.wrapup/axes_dl.log`, markers: `.wrapup/dl_ready/*.ready`, symlinks in `/home/z/hf/`.

| file | expected bytes | downloaded | verified |
|---|---|---|---|
| `gemma-4-E2B-it-UD-Q4_K_XL.gguf` | 3184496736 | yes | exact |
| `gemma-4-E4B-it-UD-Q4_K_XL.gguf` | 5126306944 | yes | exact |
| `gemma-4-12b-it-UD-Q4_K_XL.gguf` | 7366423360 | yes | exact |
| `gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf` | 17010980576 | yes | exact |
| `gemma-4-31B-it-UD-Q4_K_XL.gguf` | 18822970304 | yes | exact |

No QAT file was downloaded: the repos only publish `UD-Q4_K_XL` for 12B/31B/26B-A4B, and
E2B/E4B Q2+Q4 were already on disk.

## 3. Gate (step C) — CPU load gate, `.wrapup/loadgate.jsonl`

Gate = `.wrapup/loadgate_cpu.sh` (`llama-server -ngl 0`, one real completion, no GPU lock);
DiffusionGemma uses `llama-diffusion-cli` per the diffusion runtime. A file that fails is
excluded and never written as a null row.

| tag | file | result |
|---|---|---|
| m140-qat-gemma12b-q4 | gemma-4-12B-it-qat-UD-Q4_K_XL.gguf | PASS |
| m141-native-gemma12b-q4 | gemma-4-12b-it-UD-Q4_K_XL.gguf | PASS |
| m142-qat-gemma31b-q4 | gemma-4-31B-it-qat-UD-Q4_K_XL.gguf | PASS |
| m143-native-gemma31b-q4 | gemma-4-31B-it-UD-Q4_K_XL.gguf | PASS |
| m144-qat-gemma26b-a4b-q4 | gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf | PASS |
| m145-native-gemma26b-a4b-q4 | gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf | PASS |
| m146-qat-gemma-e2b-q2 | gemma-4-E2B-it-qat-UD-Q2_K_XL.gguf | PASS |
| m147-qat-gemma-e2b-q4 | gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf | PASS |
| m148-native-gemma-e2b-q4 | gemma-4-E2B-it-UD-Q4_K_XL.gguf | PASS |
| m149-qat-gemma-e4b-q2 | gemma-4-E4B-it-qat-UD-Q2_K_XL.gguf | PASS |
| m150-qwen38-gsqrco-iq3xxs | Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf | PASS |
| m151-qwen38-gsqrco-iq3s | Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf | PASS |
| m152-qwen38-27b-iq4xs | Qwen3.8-27B-UD-IQ4_XS.gguf | PASS |
| m154-diffusiongemma-26b-a4b-q4km | diffusiongemma-26B-A4B-it-Q4_K_M.gguf | **FAIL → excluded** |
| m155-qat-gemma-e4b-q4 | gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf | PASS |
| m156-native-gemma-e4b-q4 | gemma-4-E4B-it-UD-Q4_K_XL.gguf | PASS |

DiffusionGemma reason (`.wrapup/axes_diffusion_gate.log`):
`llama_model_load: error loading model: unknown model architecture: 'diffusion-gemma'`.
Both local llama.cpp builds (installed 0.4.1-dev build 4399; `/home/z/llama-bonsai` build
0.2.0) predate the architecture and no source tree contains it, so the file cannot be loaded
by any available runtime. Recorded as FAIL, excluded from the campaign; no axis-7 number will
be fabricated. The autoregressive control (m145) still runs for axis 1.6.

## 4. Campaign file (step D) — `.wrapup/AXES_CAMPAIGN.txt`

Format identical to `.wrapup/CAMPAIGN.txt`: `<abs_gguf_path> <tag> <limit> <mmlu_limit>`
(limit=100, mmlu_limit=16, matching the standard campaign). 15 entries, all gate-PASS and all
with `mres/<tag>/{DONE,code.DONE}` absent. Tags continue numbering after m134.

Axis 1.6 (QAT vs native):
m140-qat-gemma12b-q4 · m141-native-gemma12b-q4 · m142-qat-gemma31b-q4 ·
m143-native-gemma31b-q4 · m144-qat-gemma26b-a4b-q4 · m145-native-gemma26b-a4b-q4 ·
m146-qat-gemma-e2b-q2 · m147-qat-gemma-e2b-q4 · m148-native-gemma-e2b-q4 ·
m149-qat-gemma-e4b-q2 · m155-qat-gemma-e4b-q4 · m156-native-gemma-e4b-q4
Axis 1.5 (GSQ-RCO):
m150-qwen38-gsqrco-iq3xxs · m151-qwen38-gsqrco-iq3s · m152-qwen38-27b-iq4xs

Excluded: m154-diffusiongemma-26b-a4b-q4km (gate FAIL).

## 5. Ingest (step E) — `migrate_db.py`

* DB backed up first: `experiments.sqlite.bak33` (next free after bak32).
* Added `AXES_TAG_MODELS` (tag → canonical logical gguf name) and `ingest_axes(con)`,
  registered in the REFRESH registry immediately after `ingest_campaign`. The generic
  campaign ingest already reads every `.wrapup/mres/<tag>/` panel (that is how m91–m134 are
  ingested — there are no per-tag parsers for them), so these tags land on their own; this
  block pins the axis contract so a resolved-path or blob-hash name can never become an
  analysis key, and reports how many names it corrected.
* Validated: `python3 migrate_db.py` → `integrity: ok | fk issues: 0`. With m140's panel
  present the run ingested `campaign=665` rows including m140 with model
  `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` and the canonical protocols
  (`lmeval-0.4.13-gguf-shim-reasoning-off` / `lmeval-0.4.13-chat-reasoning-off`); `axes=0`
  corrections were needed (names already canonical).

## 6. Arming (step F)

Armed detached and idempotently:

```
CAMPAIGN_FILE=/home/z/hf/research/.wrapup/AXES_CAMPAIGN.txt \
  setsid nohup bash /home/z/hf/research/.wrapup/campaign.sh \
  > /home/z/hf/research/.wrapup/axes_campaign.out 2>&1 < /dev/null &
```

Driver PID 3850304; takes `/tmp/llama_gpu.lock` itself and waits for it. It skips any
stage whose `DONE`/`code.DONE` is present, so re-running is safe. Logs:
`.wrapup/campaign.log` (driver), `.wrapup/axes_campaign.out` (panel stdout).

## 7. Readout scaffold

`.wrapup/axes_analysis.py` prints the paired QAT-vs-native table (per benchmark), the GSQ-RCO
rows against the standard Qwen3.8-27B quants, and the axis-7 gate-fail note. It prints
`pending` for any cell not yet in the DB and never fabricates a value.
