# i02 测量基础设施 — 结果

本文件是 i02 的当前事实。每条事实一行标题（`## <id> :: <事实>`），其下的 bullet 是它的坐标：
`kind`、`status`、`from`、`evidence`、`producer`。没有 `producer` 的数字不得引用。
`make_report.py::load_docs` 读这个格式，所以标题里的 ` :: ` 是唯一分隔符，事实本身写一行。

## res14 :: 非测量是缺席而不是 0：gemma-4-31B 的 QAT / 原生 Q4 对、gemma-4-26B-A4B 的原生 Q4、以及扩散式解码 DiffusionGemma 都没有库内行。

- kind: citation
- status: current
- evidence: 三条 run_tag（m142/m143/m145）在 `experiments` 里 0 行；`m144`（同模型 QAT 臂）有 8 行，说明差异在文件而非模型；DiffusionGemma 在本机运行时加载不了该架构，登记为 `GATE-FAIL`。
- producer: `sqlite3 experiments.sqlite "SELECT count(*) FROM experiments WHERE run_tag IN ('m142-qat-gemma31b-q4','m143-native-gemma31b-q4','m145-native-gemma26b-a4b-q4')"` → `0`
- 登记册: `non_measurements.tsv` 逐格给出状态、发生了什么、证据与对应事实；报告把它渲染成独立登记表，`checks/report_check.py` 逐条核对在场。

## res15 :: 当前规模：`experiments.sqlite` 3231 行、211 个模型文件名、60 种非空协议；另有 1881 行是 `protocol` 为空的历史行；MultiPL-E 有 192 个「模型 / 协议 / 语言」格。

- kind: citation
- status: current
- producer: `sqlite3 experiments.sqlite "SELECT count(*), count(DISTINCT model), count(DISTINCT protocol), sum(protocol IS NULL OR protocol='') FROM experiments"` → `3231|211|60|1881`；192 由 `python3 checks/db_check.py` 打印

## res23 :: 重复测量行缺陷已修：重复的 bare 副本按测量身份去重，`ingest_mpl` 改为入库前按 `MEASUREMENT_IDENTITY` 预检，重跑插入 0 行。

- kind: measured
- status: current
- evidence: 行数 3311→3231；enriched 副本 2172 行前后不变；按身份分组的重复组从 80 降到 0；`PRAGMA integrity_check` ok。
- producer: `python3 migrate_db.py` 连跑两次：两次都打印 `rows 3231 -> 3231`、`removed 0 bare duplicate(s)`、`integrity: ok | fk issues: 0`

## res24 :: 干净 clone 一条命令重建 `report.html`，与已提交版本逐字节相同。

- kind: measured
- status: current
- evidence: 在 `git clone` 出的空树里 `./reproduce.sh` 退出 0，重建的 `report.html` 与仓库里那份逐字节相同（10281006 字节、86 张图）；本机实测报告构建约 35 s、全流程本机 50 s / 干净 clone 60 s（12 核 CPU，无 GPU）。唯一的 BLOCKED 行是 `docs@1` 标准不在本机（见 res32）。
- producer: `git clone <repo> x && cd x && ./reproduce.sh`

## res25 :: 报告除数据库外的输入是有限的、都随仓库分发；缺任何一个都让构建失败或让检查变红，不会渲染出 0。

- kind: citation
- status: current
- evidence: 四个输入：`.wrapup/mktables.py`（建表逻辑）、`.wrapup/bpw_map.json`（有效位宽）、`report_inputs/eval_status.json`（317 份评测的状态直方图，由 `report_inputs/build_eval_status.py` 从不可入库的 `.wrapup/mres/*_eval.json` 抽取）、`docs/subprojects/i02-测量基础设施/non_measurements.tsv`（非测量登记册）。`report_inputs/eval_status.py` 是它们唯一的读取口。
- producer: `python3 report_inputs/build_eval_status.py --check`；`./reproduce.sh` 的「报告输入」一行

## res26 :: 提示集及其 SHA256 可核对：6 份 HumanEval 多语言提示在仓库内，`sha256sum -c` 通过。

- kind: citation
- status: current
- evidence: `humaneval-py.jsonl` = `ac14c3b0abfa218c8442807b729acdce30a165d9e2f79b9dfa7bf78e6aa26edb`；其余五份见 `SHA256SUMS`。
- producer: `cd .wrapup/prompts && sha256sum -c SHA256SUMS`

## res27 :: `.wrapup/` 的可执行脚本不再引用已退役的绝对根路径；历史记录类文件保持原样，改写它们会伪造运行记录。

- kind: measured
- status: current
- evidence: 118 个 `*.sh` 改成 `REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"` 并逐个过 `bash -n`；11 个 `*.py` 改成按 `__file__` 定位并逐个过 `py_compile`。`*.log`/`*.txt`/`*.json`/`*.out`/`*.args` 保留当时的路径，检查里声明为豁免。
- producer: `python3 checks/stale_roots.py`（`--fix` 是幂等迁移）

## res28 :: 逐语言表的行键从 `(model, protocol)` 改为「模型 + 显示标签」，同标签同值合并，同标签不同值逐条列出。

- kind: measured
- status: current
- evidence: 修复前按 `(model, protocol)` 分组得到 83 行，其中 3 组两行同标签；现在 80 行，行标签唯一。3 个格的同一条协议串下存着两个不同分数（m31 的 top_k 扫描把 K=1 与 K=200 写进同一串），报告把两个值都印出来并在该节逐条说明，不静默取其一。
- producer: `python3 checks/report_check.py`（行标签唯一性 + 多值格的两个值都必须出现）

## res29 :: 标准基准列不再把 MultiPL-E 的 C++ 与 Python 池化：基准列 10→11、整表 12→13 列，轴 A/B/C 等 8 张表各多一条 series。

- kind: measured
- status: current
- evidence: 池化会掩盖语言层反转：51 个双语言模型上，符号检验有 169/1275 对模型在两语言下给出严格相反的次序，py−cpp 的区间与中位数以 a12 的 `RESULT.md` 现值为准。单语言有格的模型另一列留空并渲染 `-`，不填 0、不用另一语言代替。
- producer: `python3 checks/report_check.py`（逐格核对每个 MultiPL-E 列等于其语言子集自己的取值）

## res30 :: 印在分数旁边的题量来自该格自己的产物，不来自全局默认题数。

- kind: measured
- status: current
- evidence: 通过率列按「通过数 / 题数 == 分数」找候选，再用该格协议串给出的 facet（`ctx=`、`kv=`）在产物文件名里消歧——`pass=0` 时分数本身分不开 60 题探针与 161 题整格，facet 能分开；部分给分列按 `m41_summary.jsonl` 记的 `mean_frac` 配对。实测 rs 格印 155、java 格印 158、m30 的零探针与 0.0167 格都印 60；确实定不下来的格印「题量未知」，不退化成裸分数、也不填默认题数（当前 2 个）。
- producer: `python3 checks/report_check.py`（416 个格逐格核对）

## res31 :: 数据库变更由工具保证：`migrate_db.py` 启动时先产生下一个编号备份，结束时打印完整性；`checks/db_check.py` 只读复核完整性与清洁度。

- kind: measured
- status: current
- evidence: 在库副本上连跑两次，两次都打印 `rows 3231 -> 3231`、`integrity: ok | fk issues: 0`，且两次运行后的数据逐行相同（按 rowid 排序的整表摘要相同）；每次运行前自动生成 `experiments.sqlite.bak1`、`.bak2`。
- producer: `python3 migrate_db.py`（在库副本目录里跑）；`python3 checks/db_check.py`

## res32 :: 文档检查的 schema 标准缺失是外部阻断：`/home/z/vibe/AGENTS.docs.schema.yaml` 不存在，`docs/check_docs.py` 因此不能宣称通过，但它把不依赖 schema 的集合级不变量真跑并打印。

- kind: citation
- status: current
- evidence: 各层 schema 以 `$ref: "docs@1"` 引用该标准，仓库内没有任何副本。不依赖它的集合级不变量照常跑并打印：id 在文件内唯一、每个 `from` 可解析、`_text` 互不相同且非空。
- producer: `python3 docs/check_docs.py` → 打印不变量结果并以退出码 2 点名缺失路径
- 需要谁的授权: 该标准属于 `/home/z/vibe` 的策略层，不在本仓库内；解除需要 meta 决定是补上该文件，还是授权把 `docs@1` 的当前内容落到本仓库并改写 `RESEARCH_DOCS_STANDARD` 的默认值。

## res33 :: 各子项目的 Markdown 事实形状尚未统一，因此只有 i02 的 `PLAN.md`/`RESULT.md` 的节点会进入报告；另有四个文件（`a12`、`i01` 各两份）不提供可解析的事实。

- kind: citation
- status: current
- evidence: `docs/check_docs.py` 的 `shape not parsed` 一行逐文件点名；报告「待分析」一节的节点数因此少于各子项目实际登记的节点数。
- producer: `python3 docs/check_docs.py`
