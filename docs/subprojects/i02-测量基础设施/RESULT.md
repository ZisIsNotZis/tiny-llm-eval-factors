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
- evidence: 在 `git clone` 出的空树里 `./reproduce.sh` 退出 0，重建的 `report.html` 与仓库里那份逐字节相同（10281006 字节、86 张图）；本机实测报告构建约 35 s；全流程三次实测 41.1 / 49.9 / 60.2 s（差异来自 matplotlib 字体缓存与机器负载），12 核 CPU、无 GPU。唯一的 BLOCKED 行是 `docs@1` 标准不在本机（见 res32）。
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
- evidence: 修复前按 `(model, protocol)` 分组得到 83 行，其中 3 组两行同标签；现在 80 行，行标签唯一。3 个格的行标签下有 6 行测量（来自 2 条协议串），分数有两个值（m31 的 top_k 扫描把 K=1 与 K=200 写进同一串）；表里显示其中出现行数较多的那一个，并在该节写明「这个行标签下有 6 行测量（来自 2 条协议串），其中 5 行是 X，表中就显示它；另外还印出 Y（1 行）」，两个值都印出、规则也写清，不静默取其一。
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

## res32 :: `docs@1` 标准落进本仓库 `docs/docs.schema.yaml`，`docs/check_docs.py` 因此能真做 schema 校验并以 0 退出；它有负控证明自己会失败。

- kind: citation
- status: current
- evidence: 解析顺序是 `RESEARCH_DOCS_STANDARD` → 仓库内 `docs/docs.schema.yaml` → 旧的共享路径 `/home/z/vibe/AGENTS.docs.schema.yaml`；若共享路径以后重新出现这份标准，本仓库改为指向它并删除本地副本（同一事实不许有两份）。各层 refinement schema 仍以 `allOf: [{$ref: "docs@1"}, …]` 引用它，标准本身约束必填坐标（`_text`/`author`/`origin`/`scope`/`status`）、`author`/`scope`/`status` 的取值域、`from` 的 `layer.fact` 书写形式，并禁止未声明的坐标；`_text` 必须是一行。
- producer: `python3 docs/check_docs.py`（PASS）；`python3 checks/docs_schema_negative_control.py`（未改动副本 PASS，删掉 `author` 与写成 `status: bogus` 各以 1 退出并点名）
- 顺带修掉的真实违规: `docs/method/method.yaml::m48` 的 `_text` 里两处 `\n` 被 YAML 双引号解释成真换行，事实因此跨了两行；已改回字面量。

## res33 :: 报告不解析子项目的 `PLAN.md` / `RESULT.md`，读者需要的「未解问题」改由派生索引 `report_inputs/open_questions.json` 提供。

- kind: citation
- status: current
- evidence: 索引由 `report_inputs/build_open_questions.py` 扫各子项目 `PLAN.md` 生成，只认**二级标题**（`## `）且标题文字本身以「未解 / 未决 / 待解 / 开放问题 / open question」开头，代码围栏里的行一律跳过（`## wp98 :: 未解决的…` 这类工作包标题不算一节）；每条带子项目 id 与来源路径，没有这一节的文件被跳过并计数（当前跳过 2 个：a12、i01），连跑两次字节相同；报告据它渲染「未解问题」节，索引缺失时构建失败。
- producer: `python3 report_inputs/build_open_questions.py --check`

## res34 :: CJK 字体是被复现条件的一部分：缺它或版本不对时构建直接失败，不静默换字体。

- kind: measured
- status: current
- evidence: 字体 `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`（`fonts-noto-cjk`），sha256 `b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a`；换掉它 86 张图的字形与度量全变、报告从 10280329 字节变成另一个哈希。构建末行印出真字节数与字体指纹。
- producer: `python3 -c "import make_report as m; print(m.CJK_FONT, m.CJK_FONT_SHA256)"`；`./reproduce.sh` 的「CJK 字体」一步（把 `make_report.py` 的 `CJK_FONT` 改成不存在的路径时，该步失败并念出字体名、安装命令与期望哈希）

## res35 :: 报告不再把已退役路径当作来源引用；仍有 89 条事实的来源是 `.scratch/originals`，它们由各自的持有层迁移。

- kind: measured
- status: current
- evidence: `make_report.py` 的 `render_fact_list` 对退役根（`.scratch/`、`/tmp/MultiPL-E/`、`/home/z/hf/`）改成显示「已退役历史原件（该子项目尚未迁移到当前家）」并优先给出该事实自己的 `producer`/`evidence`；`checks/report_check.py` 断言报告里没有退役根的字符串。规模：19 个文件 89 条事实仍带该来源，其中共享层 65 条（method 43、product 15、architecture 6、need 1）、子项目 24 条（a01 8、a02 3、a03 2、a09 2、a04 2、a05 2、a06 2、a07 1、a10 1、a13 1）。
- producer: `python3 -c "import yaml,glob,collections;c=collections.Counter();[c.update({p:sum(1 for k,v in (yaml.safe_load(open(p,encoding='utf-8')) or {}).items() if isinstance(v,dict) and '.scratch/originals' in str(v.get('origin','')))}) for p in glob.glob('docs/**/*.yaml',recursive=True)];print(sum(c.values()),len([k for k,v in c.items() if v]))"`；`python3 checks/report_check.py`
