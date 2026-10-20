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
`OK：报告可从库重建…` 是完成信号；`BLOCKED` 行表示该项未验证（当前是 `docs@1` schema 标准不在本机）。
本机实测：报告构建约 35 s；`./reproduce.sh` 全流程 41.1 / 49.9 / 60.2 s（干净 clone，12 核 CPU、无 GPU；差异来自字体缓存与负载）。

**CJK 字体是被复现条件的一部分**：`/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`
（来自 `fonts-noto-cjk`，sha256 `b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a`）。
缺它或版本不对时构建**直接失败**并说明装什么，不静默换字体——换字体后 86 张图的字形与度量都变，
报告就不再逐字节相同。`./reproduce.sh` 会把这一条当单独一步核对。

它不能重建的东西：模型权重（`.gguf` 不在仓库内，也不在 `artifacts.tsv` 里，因为原始权重文件已不在本机）、
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
- `.wrapup/` contains local run outputs, downloaded corpora, and other regenerable or resumable experiment artifacts; its ignore rules keep those out of Git unless a specific durable evidence artifact is intentionally promoted. The prompt set (`.wrapup/prompts/`) and the report's inputs (`report_inputs/`) are deliberately tracked.

Unknown, blocked, or unmeasured results must remain distinct from zero or a negative result. Consult the owning plan/result entries before interpreting any number, and preserve the recorded workload and protocol alongside comparisons.

## License

Original code and documentation retain the repository's existing MIT license; see `LICENSE`. Model weights, benchmark datasets, and other third-party materials keep their own licenses and are not relicensed by this notice.
