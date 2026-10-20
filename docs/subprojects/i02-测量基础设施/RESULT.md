# i02 测量基础设施 — 结果

本文件是 i02 的当前事实。每条事实一行标题（`## <id> :: <事实>`），其下的 bullet 是它的坐标：
`kind`、`status`、`from`、`evidence`、`producer`。没有 `producer` 的数字不得引用。
`make_report.py::load_docs` 读这个格式，所以标题里的 ` :: ` 是唯一分隔符，事实本身写一行。

## res14 :: 非测量是缺席而不是 0：gemma-4-31B 的 QAT / 原生 Q4 对、gemma-4-26B-A4B 的原生 Q4、以及扩散式解码 DiffusionGemma 都没有库内行。

- kind: citation
- status: current
- evidence: 三条 run_tag（m142/m143/m145）在 `experiments` 里 0 行；DiffusionGemma 在本机运行时加载不了该架构，本轴登记为 `GATE-FAIL`。
- producer: `sqlite3 experiments.sqlite "SELECT count(*) FROM experiments WHERE run_tag IN ('m142-qat-gemma31b-q4','m143-native-gemma31b-q4','m145-native-gemma26b-a4b-q4')"` → `0`
- 登记册: `non_measurements.tsv` 逐格给出状态、原因与证据；报告把它渲染成独立登记表。

## res15 :: 当前规模：`experiments.sqlite` 3231 行、211 个模型文件名、60 种非空协议；另有 1881 行是 `protocol` 为空的历史行。

- kind: citation
- status: current
- producer: `sqlite3 experiments.sqlite "SELECT count(*), count(DISTINCT model), count(DISTINCT protocol), sum(protocol IS NULL OR protocol='') FROM experiments"` → `3231|211|60|1881`

## res23 :: 重复测量行缺陷已修：重复的 bare 副本按测量身份去重，`ingest_mpl` 改为入库前按 `MEASUREMENT_IDENTITY` 预检，重跑插入 0 行。

- kind: measured
- status: current
- evidence: 行数 3311→3231；enriched 副本 2172 行前后不变，只存一份的 bare cell 未动；按身份分组的重复组从 80 降到 0；`PRAGMA integrity_check` ok；备份 `experiments.sqlite.bak40`。
- producer: `python3 migrate_db.py` 连跑两次，第二次打印 `rows 3231 -> 3231` 且 `removed 0 bare duplicate(s)`

## res24 :: 干净 clone 一条命令重建 `report.html`，与已提交版本逐字节相同。

- kind: measured
- status: current
- evidence: 在 `git clone` 出的空树里执行 `./reproduce.sh` 退出 0；报告 9.2 MB、82 张图；本机实测构建 33 s（12 核）。
- producer: `./reproduce.sh`（依次核对依赖、提示集哈希、报告输入、`checks/db_check.py`、陈旧根路径、文档检查、构建并 `git diff --exit-code report.html`）

## res25 :: 报告除数据库外的输入是有限的、都随仓库分发，缺任何一个都会让构建失败而不是渲染出 0。

- kind: citation
- status: current
- evidence: 三个输入：`.wrapup/mktables.py`（建表逻辑）、`.wrapup/bpw_map.json`（有效位宽）、`report_inputs/eval_status.json`（评测状态直方图，由 `report_inputs/build_eval_status.py` 从不可入库的 `.wrapup/mres/*_eval.json` 抽取）。提示集 `.wrapup/prompts/humaneval-{cpp,py,js,java,rb,rs}.jsonl` 与 `SHA256SUMS` 随仓库分发。
- producer: `grep -n "open(\|import mktables\|mres/" make_report.py`

## res26 :: 提示集及其 SHA256 可核对：6 份 HumanEval 多语言提示在仓库内，`sha256sum -c` 通过。

- kind: citation
- status: current
- producer: `cd .wrapup/prompts && sha256sum -c SHA256SUMS`
- evidence: `humaneval-py.jsonl` = `ac14c3b0abfa218c8442807b729acdce30a165d9e2f79b9dfa7bf78e6aa26edb`；其余五份见 `SHA256SUMS`。

## res27 :: `.wrapup/` 的可执行脚本不再引用已退役的绝对根路径；历史记录类文件（`*.log`/`*.txt`/`*.json`）保持原样，改写它们会伪造运行记录。

- kind: measured
- status: current
- evidence: 118 个 `*.sh` 与 11 个 `*.py` 改成脚本自身相对路径（`REPO_ROOT`），每个都过 `bash -n` / `py_compile`；检查脚本把记录类文件列为豁免。
- producer: `python3 checks/stale_roots.py`

## res28 :: MultiPL-E 两处表格缺陷按行键修复：行键从 `(model, protocol)` 改为「模型 + 全部区分列的取值」，显示标签仍省掉不参与区分的附加段。

- kind: measured
- status: current
- evidence: 修复前同一模型的两个协议串（`multipl-e-raw-t0.3-768` 与 `mpl-raw-t0.3-768;topk-set=…;anchors …`）落到同一标签 `raw·temp=0.3`，Qwen3.5-2B 的三个量化档各出现两行同名同值；合并后这三组各剩一行。同标签而数值不一致的情况在构建时报错，不静默取其一。
- producer: `python3 checks/report_check.py`

## res29 :: 标准基准列不再把 MultiPL-E 的 C++ 与 Python 池化成一个数，而是两列各自成列；单语言只有格的模型，另一列留空。

- kind: measured
- status: current
- evidence: 池化会掩盖符号反转（py−cpp 在 51 个双语言模型上从 −0.267 到 +0.186），故列名带语言，缺失格渲染 `-`。
- producer: `python3 checks/report_check.py`（逐格核对每个 MultiPL-E 列等于其语言子集的聚合）

## res30 :: 数据库变更前的编号备份与变更后的检查都由工具执行，不靠记忆。

- kind: measured
- status: current
- evidence: `migrate_db.py` 启动时先复制出下一个未占用的 `experiments.sqlite.bakN`，结束时打印 `integrity` 与 `fk issues`；`checks/db_check.py` 只读地复核完整性、外键、非空/取值域和重复身份组。
- producer: `python3 migrate_db.py && python3 checks/db_check.py`

## res31 :: 文档检查的 schema 标准缺失是外部阻断：`/home/z/vibe/AGENTS.docs.schema.yaml` 不存在，`docs/check_docs.py` 因此不能宣称通过。

- kind: citation
- status: current
- evidence: 各层 schema 以 `$ref: "docs@1"` 引用该标准；仓库内没有任何副本。集合级不变量（id 唯一、`from` 可解析、`_text` 唯一且非空）不依赖它，仍在跑。
- producer: `python3 docs/check_docs.py` → 打印不变量结果并以退出码 2 点名缺失路径
- 需要谁的授权: 该标准属于 `/home/z/vibe` 的策略层，不在本仓库内；解除需要 meta 决定是补上该文件，还是授权把 `docs@1` 的当前内容落到本仓库并改写 `RESEARCH_DOCS_STANDARD` 默认值。
