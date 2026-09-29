# Resources

* 4090 24G
* 100Mbps internet — **international routes are intermittently blocked.**
  * `huggingface.co` and `hf-mirror.com` both fail intermittently (TLS handshake timeouts).
  * Working routes (verified 2026-09-29): **ModelScope** (`modelscope.cn`) for model weights,
    **GitHub via `https://ghfast.top/` proxy** for dataset tarballs, **PyPI via
    `https://pypi.tuna.tsinghua.edu.cn/simple`** for packages.
* 1.8TB ssd at ~/hf, holding models and datasets (1.3T free)
* ~/.local/bin/llama-server (build 4399)
* ~/evalplus/ — **no longer present**; `evalplus` (0.3.1) reinstalled in `.wrapup/evalpy`
* `experiments.sqlite` is the source-of-truth DB; numbered backups exist up to `.bak43`
  (`.bak1` created at wrap-up start).
* **Model weights recoverable:** 22/181 DB-referenced files survive (~12%). See `ARCHIVE_MANIFEST.md`.
  Re-fetched during wrap-up via ModelScope: `Qwen3.5-2B/4B/9B` UD-Q2/Q3, `gemma-4-E4B` UD-Q3.
  Local `~/hf/<name>.gguf` symlinks were rebuilt by `.wrapup/link_models.sh` (73 links).
* **Eval data:** `HumanEvalPlus-v0.1.10` (164) + `MbppPlus-v0.2.0` (378) restored into
  `~/.cache/evalplus/`.
* Wrap-up tooling: `.wrapup/evalpy` (evalplus), `.wrapup/msenv` (modelscope).
* Environment limitations (closed):
  - strict 35B q8/q8 same-scale continuation OOMs on this 24GB host
  - EvalPerf requires privileged `perf_event_paranoid` change (blocked here, `=4`)
