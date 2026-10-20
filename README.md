# Local Language-Model Research

This repository is a reproducible research workbench for measuring local language-model inference factors, including quantization, model size, decoding protocols, and benchmark behavior. It is research evidence, not a model release or a claim that every planned comparison is complete.

## Run it from a clean clone

```bash
sudo apt-get install -y fonts-noto-cjk       # 图表字体：被复现条件的一部分，见下
python3 -m pip install -r requirements.txt   # 首次约 1 分钟（本机实测，含 matplotlib 依赖）
./reproduce.sh                               # 核对输入并从库重建报告，约 40 秒
```

`./reproduce.sh` 依次核对运行时依赖、提示集 SHA256（`.wrapup/prompts/SHA256SUMS`）、报告输入、数据库
完整性与清洁度、是否还有脚本硬编码退役路径、文档检查，然后从 `experiments.sqlite` 重建 `report.html`
并与仓库里那份**逐字节**对比，最后用 `checks/report_check.py` 核对报告与产物一致。最后一行
`OK：报告可从库重建…` 是完成信号。`SKIP`/`BLOCKED` 行表示该项未验证（例如干净 clone 里没有本机的
`.wrapup/mres/` 落盘产物）。文档检查这一项现在是绿的：`docs@1` 标准在 `docs/docs.schema.yaml`，
`python3 docs/check_docs.py` 以 0 通过。
本机实测：报告构建约 35 s；`./reproduce.sh` 全流程 41.1 / 49.9 / 60.2 s（干净 clone，12 核 CPU、无 GPU；差异来自字体缓存与负载）。

**CJK 字体是被复现条件的一部分**：`/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`（来自 `fonts-noto-cjk`）。
它的路径与期望 sha256 只有一个家：`make_report.py` 的 `CJK_FONT` / `CJK_FONT_SHA256`；构建末行的
`cjk font: <路径> sha256=<哈希>` 就是本次实际用的那一份，`./reproduce.sh` 也把这一条当单独一步核对。
缺它或版本不对时构建**直接失败**并说明装什么，不静默换字体——换字体后 86 张图的字形与度量都变，
报告就不再逐字节相同。

它不能重建的东西：模型权重（`.gguf` 不在仓库内，原始权重文件已不在本机；本仓库没有
`artifacts.tsv`，也不打算为它们建一份——那些字节已丢失）、
`/tmp/MultiPL-E` 提示缓存、CJK 字体（系统包，按上面的命令装）、以及评测运行本身（需要 GPU 与模型文件）。`.wrapup/mres/*_eval.json` 是逐题
落盘产物、不入库，其所需的判读摘要随仓库分发在 `report_inputs/eval_status.json`，所以干净 clone 得到的
报告与本机相同。

## Source of truth

- `experiments.sqlite` is the data source of truth for recorded measurements.
- `docs/plan/subprojects.md` owns the research split: which unit owns which section, its goal and acceptance.
- `docs/subprojects/<id>-<name>/PLAN.md` owns that unit's milestone and work packages; `RESULT.md` owns its
  current facts, each with its evidence and the command that reproduces it.
- `docs/<layer>/<layer>.yaml` owns the layers that are not cut per unit (pain, need, product, architecture, method).
- `AGENTS.md` defines data-trust, experiment, and database-safety rules.
- `make_report.py` produces the derived `report.html`; do not edit the generated report by hand.
- `checks/` holds the infrastructure checks: database integrity and cleanliness, report-versus-artefact
  agreement, and retired absolute paths.
- `.wrapup/` holds run outputs, downloaded corpora and other regenerable experiment artifacts. What ships is decided by one criterion (`@regeneration_cost`): **an artefact ships when it carries an assertion and cannot be recomputed from what ships; it stays out when it is a rebuildable distribution.**
  - **Ships (evidence):** `.wrapup/prompts/` (the prompt set plus `SHA256SUMS`), `.wrapup/mres/*_eval.json` (the per-item eval artefacts: 337 files, 3.45 MB — they are what makes "no all-Exception cell carries a score" and every printed item count checkable in a fresh clone), the panel scripts and `*_summary.jsonl` they produced, `bpw_map.json`, and everything under `report_inputs/`.
  - **Does not ship (rebuildable cache):** `.wrapup/mres/*.jsonl` per-item samples, venvs (`lmenv/`, `msenv/`, `evalpy/`, `bfclenv/`, `mplenv/`), `jars/`, run logs, `dl_ready/`, `ppl_corpora/`.

Unknown, blocked, or unmeasured results must remain distinct from zero or a negative result. Consult the owning plan/result entries before interpreting any number, and preserve the recorded workload and protocol alongside comparisons.

## License

Original code and documentation retain the repository's existing MIT license; see `LICENSE`. Model weights, benchmark datasets, and other third-party materials keep their own licenses and are not relicensed by this notice.
