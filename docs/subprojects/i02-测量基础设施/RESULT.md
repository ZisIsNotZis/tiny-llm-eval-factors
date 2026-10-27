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
- evidence: 在 `git clone` 出的空树里 `./reproduce.sh` 退出 0，重建的 `report.html` 与仓库里那份逐字节相同（10274885 字节、86 张图）；本机实测报告构建约 35 s；全流程三次实测 41.1 / 49.9 / 60.2 s（差异来自 matplotlib 字体缓存与机器负载），12 核 CPU、无 GPU。唯一的 BLOCKED 行是 `docs@1` 标准不在本机（见 res32）。
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

## res35 :: 报告里每条事实的来源都按「查得到就打印，查不到就说不存在」给出，标签不再是固定断言。

- kind: measured
- status: current
- evidence: 规则是：先打印事实本体所在文件（它随仓库分发，永远可查）；`origin` 里记录下来的路径若在**被 git 跟踪的文件集**里就一并打印（`.scratch/` 下的加「该目录已按策略退役」标注），一个都不存在时给该事实的 `producer`/`evidence` 并写明「来源路径在本仓库不存在」。用跟踪集判断而不是 `os.path.exists`，否则只在本机存在的 `.wrapup/mres/*` 会让干净 clone 得到不同的报告。当前报告：24 条带退役标注且各自先给出本体文件、1 条（`plan7b`，其 origin 指的是已迁走的 `docs/plan/plan.yaml`）打印「来源路径在本仓库不存在」并给出本体 `docs/subprojects/a01-量化位宽/plan.yaml`、0 条再出现「已退役历史原件」这种断言。
- producer: `python3 checks/report_check.py`；报告内 `该目录已按策略退役` / `来源路径在本仓库不存在` 的计数

## res36 :: `reproduce.sh` 的报告一致性检查只在本次真的产出了报告时运行，构建失败时是 SKIP 而不是拿旧文件冒充。

- kind: measured
- status: current
- evidence: 构建成功后置 `BUILD_OK=1` 才跑 `checks/report_check.py`；把 CJK 字体路径改成不存在的路径强制构建失败时，`reproduce.sh` 打印 `FAIL 报告构建失败` 与 `SKIP 报告与产物一致（第 9 步没有产出本次报告，不拿仓库里那份旧文件比对）`，整体 FAILED。
- producer: `./reproduce.sh`（强制构建失败一次，观察第 9、10 步）

## res37 :: 备份改成 SQLite 在线备份并自证可用：只复制主文件会漏掉 WAL 里已提交的行。

- kind: measured
- status: current
- evidence: `migrate_db.py::numbered_backup()` 用 `Connection.backup()` 把已提交内容整体写进 `experiments.sqlite.bakN`，随后打开备份核对 `integrity_check` 与行数，并打印备份时的行数与 sha256；行数与主库不一致就不往下改库。负控在库副本上制造「已提交行只存在于 -wal」的状态：`shutil.copy2` 主文件得到 3233 行（少一条），在线备份得到 3234 行 = 变更前状态。
- producer: `python3 checks/backup_wal_negative_control.py`

## res38 :: `n_items` 从产物回填：已评分行的 NULL 从 2297 降到 30，剩余的每一条都有显式原因，没有任何默认值。

- kind: measured
- status: current
- evidence: `migrations/backfill_n_items.py` 逐族回填且有可证伪判据——`humaneval`/`mbpp` 只在分数恰好等于 `k/164`、`k/378` 时认（1141/1142、756/757 满足，各 1 行不满足则留空）；`humaneval-multipl-e` 用 `eval_status.n_for` 配产物（244/244 全中，含 m6b 两格 chat cpp：它们的 `ctx4096` 不出现在任何产物文件名里，故 facet 过滤取不到时退回到「同分数的候选给出同一个 n」）；`bfcl` 用 run 汇总的 `per_category[类别].n`（99 全中）；`bfcl-multiturn` 用多轮汇总的扁平记录 `{category, accuracy, n}`（3/24）；`testfrac` 用 `m41_summary.jsonl` 的 `mean_frac`（24 全中）。仍为 NULL 的 30 行：`bfcl-multiturn` 21（其类别在汇总里没有匹配「类别 + 分数」的记录）、`fa-probe` 6、空 family 1、`humaneval` 1 与 `mbpp` 1（分数不是 k/n，该行被限题跑过）。逐行溯源在 `audits/n_items_backfill.tsv`；连跑两次第二次改动 0 行；每次改库前后各一次在线备份（`bak13`/`bak14`），`checks/db_check.py` 绿；报告里 MultiPL-E 的 188 个格全部印出题量（审计脚本第 7 项「跳过 0 格」）。
- producer: `python3 migrations/backfill_n_items.py --dry-run`；`sqlite3 experiments.sqlite "select bench_family,count(*) from experiments where _score is not null and n_items is null group by 1"`；`python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"`

## res39 :: BFCL 只有类别级题量，micro 不可得——不是用 macro 代替。

- kind: citation
- status: current
- evidence: 回填只能拿到每个类别自己的 `n`（`per_category[cat].n`，如 `simple_python` 400、`multiple` 200、`live_multiple` 1053）；micro 需要逐题正确数，`*_summary.jsonl` 只存类别级 `acc`/`n`，逐题结果不在库也不在产物里，因此 micro 无法从现有数据算出。
- producer: `python3 migrations/backfill_n_items.py --dry-run`（`per_category[...].n` 行）

## res40 :: 报告第一节的「掉点」叙述不再写死：只有 HumanEval+ 的配对区间支持差异，方案差异降级为机制假设。

- kind: measured
- status: current
- evidence: 三个点估计（HumanEval+ 0.3720 → 0.2378 等）改成从库查 `cell_point()`，查不到就不印；区间与显著性来自 `a01` 的 `b1-heplus-only` 事实，经 `report_inputs/build_paired_deltas.py` 抽成 `paired_deltas.json`（6 个基准里只有 HumanEval+ 的区间不含 0，其余 5 个跨 0）。报告据此生成文字：被支持的只有 HumanEval+，其余写「区间跨 0、分不出差别、不能说同时下降」；方案差异写成机制假设并给出否证方式。负控把这条事实的区间全部改成跨 0，报告随即改成「区间全部跨 0、不声称任何方向的掉点」。
- producer: `python3 report_inputs/build_paired_deltas.py --check`；`python3 checks/paired_delta_negative_control.py`

## res41 :: MultiPL-E 逐语言表的行键容纳不下 `top_k` 是一个已记录的限制，不是缺陷——meta 已裁决接受。

- kind: citation
- status: current
- evidence: 那张表的行键是「模型 + 显示协议标签」，标签有意省掉不参与区分的附加段；m31 的 `top_k` 扫描把 K=1（贪心地板）与 K=200（不截断）写进同一条协议串，于是 3 个格在一个标签下存了两个分数。报告第十三节把两个值并排印出并写明取用规则，**没有数值丢失**；给行键加 `top_k` 维度要改库结构，代价远大于收益，因此 meta 裁决按已记录的限制结项，不改数据模型。审计脚本据此把该项从「OPEN (i02)」视为已记录限制。
- producer: `python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"`（`[10]` 三个 `ONE ROW HIDES OTHERS`）；报告第十三节「行键无法区分的格」

## res42 :: per-item 评测产物随仓库分发，因此「每个已评分格都能追到落盘产物」这条断言在干净 clone 里可验证。

- kind: measured
- status: current
- evidence: 入库 `.wrapup/mres/*_eval.json` 337 个、3,621,143 字节（`.wrapup/mres/` 其余内容——逐题 samples `.jsonl`、探针转储——仍是可重算的分布物，继续忽略）。判据是 `@regeneration_cost`：承载断言且不能重算的产物随仓库走，能重算的分布物不入库。每个 `_eval.json` 自包含（`lang`/`n`/`pass`/`score`/`details[{name,pass,status}]`），不引用任何未入库文件，所以没有遗留的悬空依赖。干净 clone 里 `mpl_cell_audit.py` 从 exit 1 变 exit 0，`reproduce.sh` 的「eval_status.json 与落盘产物一致性」从 SKIP 变 PASS（15 PASS / 0 SKIP / 0 FAIL），报告哈希不变。
- producer: `git ls-files .wrapup/mres | wc -l`；干净 clone 里 `python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"`；`./reproduce.sh`

## res43 :: 入库跳过的行现在会被报出来，不再静默丢掉。

- kind: measured
- status: current
- evidence: `ingest_mpl` 遇到不在 `model_map` 里的模型名时逐条记入 `INGEST_SKIPS` 并当场打印 `skipped_rows=N reason=unknown_model names=…`（已存在的格记 `reason=already_present`，多轮入库的缺字段记 `reason=missing_field`）；`main()` 末尾统一打印 `== ingest skips ==` 账目，没有跳过时明说 `none`。实测样例：`m29-skip-probe: skipped_rows=24 reason=unknown_model names=q2,q3`（`m29_summary.jsonl` 的 24 行此前因此 0 行入库且无任何提示）。
- producer: `python3 checks/ingest_skip_negative_control.py`（三种情形：未知名被报出且不入库、配上映射后不再报未知名、全部认识时跳过计数为 0）；`python3 migrate_db.py` 末尾的 `== ingest skips ==` 一节

## res44 :: `ingest_mpl` 逐行尊重 summary 的协议串：带因子的面板（m29 的 fa/kv）因此各成一格。

- kind: measured
- status: current
- evidence: 每行的 `protocol` 字段原样入库；字段缺失时才退回 `DEFAULT_MPL_PROTOCOL`，并打印「N row(s) 没有 protocol 字段 → 用了默认协议 …」。测量身份 23 列里含 `protocol`，所以只有 `fa=on`/`fa=off` 不同的两行是两个格而不是一个。负控实测：两行只有 fa 不同 → 入库 2 行、库里分别是 `mpl-raw-greedy-768;fa=off,kv=q8_0/f16` 与 `…;fa=on,…`；同一文件重跑 → 新增 0 行；缺协议字段 → 入库行的协议是默认值且输出明说用了默认协议。
- producer: `python3 checks/ingest_protocol_negative_control.py`

## res45 :: 报告的内容来源是库、`report_inputs/` 的派生索引与产品层叙述，不含子项目的工作文档；子项目迁 Markdown 不会再改变报告。

- kind: measured
- status: current
- evidence: `make_report.py` 不再有 `load_docs()` / `_yaml_load()` / `render_fact_list()`，也不再有「客观结果 / 分析结论 / 引用与规模 / 待分析」这四个由 `docs/subprojects/*/{plan,result}.yaml` 支撑的子节；报告现由 21 个二级节组成（研究概述 + 15 个研究分析节 + 测量可复现性边界 + 数据质量与未解问题 + 2 个附录 + 结论），86 张图。研究成果的对外入口是 `FINDINGS.md`，不是报告里的内部事实清单。
- producer: `python3 make_report.py`（生成的 `report.html`）；`grep -c "<h2>" report.html`

## res46 :: 报告「测量可复现性边界」一节分三档：确定性解码地板 0、采样解码分数低估不稳定、输入变更 ±16/161；数字与适用条件都由 i01 的事实生成。

- kind: measured
- status: current
- evidence: 新节由 `report_inputs/reproducibility.json` 渲染（`report_inputs/build_reproducibility.py` 从 `i01/RESULT.md` 的 `res32`（重复测量表 + 采样边界）与 `res29`（输入变更）抽取）：**一档**确定性解码 4 个族 `identical==n`、翻转 0、Jaccard 1.0；**二档**采样解码（temp=0.3，5 次重复）Jaccard 0.53–0.67、每对上翻 8–15 题 / 下翻 6–12 题、分数只在 37→43（6/164）摆动——**分数摆动系统性低估逐题不稳定**，并点名受影响的协议标签（`mpl-raw-t0.3-768` 与「采样 / 解码参数」一节）；**三档**输入变更 16 题双向翻转（11 上 / 5 下、净 +6）、±16/161≈0.10、76/161 文本不同、66 题 token 不同。三档不得相加或互相替代。
- producer: `python3 report_inputs/build_reproducibility.py --check`；`python3 checks/reproducibility_negative_control.py`（四例：幅度改 0 → 正文改口；删适用条件 → 生成器拒绝；Jaccard 改 1.0 → 正文改说「与确定性解码同样稳定」、不再声称低估）
## res47 :: 报告第三节与 `FINDINGS.md` 不再出现已撤回的「换方案有可测差异 +0.056」，改由 `a03` 的归因脚本输出生成。

- kind: measured
- status: current
- evidence: 报告第三节的结论句由 `report_inputs/scheme_effects.json` 渲染，而该索引由 `report_inputs/build_scheme_effects.py` 直接跑 `a03` 的 `analysis/attrib.py` 并解析它的系数表得到（不抄散文）：三个标签系数在 9/9 基准上全跨 0，唯一九列都不含 0 的是位宽斜率（+0.03 至 +0.20 分/比特）；区间半宽最大到 IQ ≤0.27、local ≤0.36、bartowski ≤0.48，识别力最弱的两类在 ±0.4–0.5 量级以内不可分辨；识别来源各只有 1–3 族。`FINDINGS.md` 那一行改为指向 `docs/subprojects/a03-量化方案与厂商/RESULT.md::res7`（旧措辞在那里已标撤回）。
- producer: `python3 report_inputs/build_scheme_effects.py --check`；`python3 checks/scheme_effects_negative_control.py`（把 IQ 的 ARC-c 区间改成显著 → 正文改口成「探测到了」；把所有区间加宽一倍 → 精度数字从 0.48 变 0.95）
- 口径差异（以脚本为准）: a03 的散文写「区间半宽 0.23–0.57」，脚本当前输出按逐基准最大半宽算出来是 0.27 / 0.36 / 0.48（min 侧 0.06–0.13）；报告用脚本值。

## res48 :: 报告第二节的 X 是实测参数量（同族同 tokenizer 同配方内可比），带协议行与模型文件数按库当场算，两句话按配方加限定。

- kind: measured
- status: current
- evidence: 第二节由 `report_inputs/size_claims.json` 生成（`report_inputs/build_size_claims.py` 读 `a02` 的 `size_provenance.json`/`size_curves.json` 两个脚本产物，并对库直接查带协议行）：3233 行里可信的规模标签 659、`size-null` 1061（这 1061 行**全部**是带协议行，lm-eval 479/479 无 size；但带协议行共 1352，其中 **291** 行确实带 size——multipl-e-raw-greedy-768 178、bfcl-native-tools 74、bfcl-prompt 20、evalplus 19）、`undecidable` 1112、其余 401 行是与参数量无关的通道；实测参数量覆盖 **76 个不同模型文件**（169 个 (model,size) 组）/ 1970 行（60%），另有 12 个格无配方后缀。「越大越高」在 Q3_K_XL 成立、在 gemma-4 Q2_K_XL 被反驳（E4B 74.4% [67.2–80.5] → 12B 54.3% [46.6–61.7]，−20.1 pp，区间不重叠；同一个 12B 在 Q3_K_XL 是 93.9%，+39.6 pp，所以「13B 回折」删除）；「小模型差距更大」在 Q2_K_XL 不成立（最大正向步 1.88B→4.21B 的 +46.3 pp）；MultiPL-E cpp 的 −41.6/−71.4 pp 标明是 harness 失效。
- producer: `python3 report_inputs/build_size_claims.py --check`；`python3 checks/size_claims_negative_control.py`（区间改重叠→「分不出」；291→0 与 76→169 两个数改掉时正文跟着变）
- 与 a02 产物的口径: 上面两条修正（1352/291、76 vs 169）与库对得上（`select count(*) from experiments where protocol<>'' [and __size is not null]` → 1352 / 291），但 `a02` 的 `size_provenance.json` 目前只给出 169 条 gguf-tensors 组、不拆「带协议行」这一维，所以这两条由本子项目直接查库得到；等 `a02` 的真值 fixture 落地后改为读它（保持一个家）。

## res49 :: 报告第五节改成「分数差 与 逐题丢/得」两口径并排，长上下文标明未测，m29 未入库不等于没数据。

- kind: measured
- status: current
- evidence: 第五节由 `report_inputs/kv_evidence.json` 渲染，而该索引由 `report_inputs/build_kv_evidence.py` 跑 `a05` 的 `analysis/kv_evidence.py` 并解析其输出（不抄散文）：`f16→q4_0` 在 HumanEval base 丢 15 / 得 11（净 −4，分数 0.5732→0.5488）、plus 丢 14 / 得 11（净 −3），`f16→q8_0` base 丢 7 / 得 3；据此写明「分数相近 ≠ 判定相同」并接到「测量可复现性边界」一节；方向不一致（gsm8k/ifeval 上 q4_0 反而更高）保留原判断但改为按计数说话；长上下文标为未测并给出原因（两个 m30 网格都无信息量：一个由构造决定、一个是模型在续写填充前言）；m29 未入库单独说明「这属于未入库，不等于 KV 没有数据」。
- producer: `python3 report_inputs/build_kv_evidence.py --check`；`python3 checks/kv_evidence_negative_control.py`（把四类计数改成 0 → 正文从「逐题在双向翻动」变回「逐题判定完全相同、测不到影响」）

## res50 :: 报告的 BFCL micro/macro 差改读派生索引，报告不再随别人的新 summary 变字节。

- kind: measured
- status: current
- evidence: 新增 `report_inputs/bfcl_gap.json` 与生成器 `report_inputs/build_bfcl_gap.py`；`make_report.py::bfcl_micro_macro_gap()` 改为只读该索引（缺索引即 `SystemExit`），不再扫 `.wrapup/*_summary.jsonl`。性质验证：往 `.wrapup/m8_summary.jsonl` 追加一条带 `per_category` 的假记录后重建报告，字节哈希与追加前**完全相同**（`b35f94af…`），还原文件后仍一致——这正是派生索引要买到的：summary 变动要先显式重建索引，报告本身不动。
- producer: `python3 report_inputs/build_bfcl_gap.py --check`；`./reproduce.sh` 的「bfcl_gap.json 与现有 BFCL 汇总一致」一步

## res51 :: 第五节的长上下文改成实测结论（检索针 8k/16k/32k），并写明「上下文越长 KV 越贵」在本设计里不成立。

- kind: measured
- status: current
- evidence: `report_inputs/kv_evidence.json` 的 `long_context` 块由 `report_inputs/build_kv_evidence.py` 读 `a05` 的 `evidence/needle-retune/summary.json` 得出：8k f16 17/20 vs q4_0 13/20（−4）、16k 20/20 vs 20/20（0）、32k 14/20 vs 15/20（+1），阳性对照 0/20，可见性下限约 4/20。报告据此写：32k 上不可分辨、唯一 ≥4 的差出现在**最短**的 8k 上、方向证据不成立；局限写明（q8_0 本轮未重跑、40k 以上未测及代价）。
- producer: `python3 report_inputs/build_kv_evidence.py --check`；`python3 checks/kv_evidence_negative_control.py`（第三例：把三档 delta 全改成 0 → 正文不再声称 8k 上有 ≥4 的差）

## res52 :: venv 入口点的 shebang 有检查与 bootstrap：指向不存在的解释器一律 FAIL 并点名。

- kind: measured
- status: current
- evidence: 新增 `checks/venv_shebang.py`（扫 `.wrapup/*/bin`，shebang 里是绝对路径且文件不存在的入口点 → exit 1 并列出路径与解释器；`#!/usr/bin/env …` 不误报）与 `bootstrap_venv.sh`（`./bootstrap_venv.sh .wrapup/lmenv requirements.txt`，用创建时的解释器重建 venv，随后跑同一检查）；两者都已接进 `reproduce.sh`。负控 `checks/venv_shebang_negative_control.py`：造一个 shebang 指向 `/nonexistent/python3` 的假入口点 → FAIL 且点名该入口点、同时不误报 env 入口；只含 env 入口的目录 → PASS。
- producer: `python3 checks/venv_shebang.py`；`python3 checks/venv_shebang_negative_control.py`

## res53 :: 报告第四节写明「钉住总比特」这个前提与可行性上界：22 对里 18 对同基权重无法放在同一总比特上，配方对照是预算比较而非分配比较。

- kind: measured
- status: current
- evidence: 第四节由 `report_inputs/moe_feasibility.json` 渲染，该索引由 `report_inputs/build_moe_feasibility.py` 读 `a04` 的 `analysis/fixtures/pin_feasibility.json` 得出：上界公式 `(1−share_expert)/share_expert × layer_swing`，四族上界 GLM 0.025 / LFM 0.513 / Qwen3.6 0.251 / gemma 0.256；超出上界的那些对实测跨度 0.54–1.91，22 对里 18 对超界（4 对可钉住）；可用结论只到「策略分类是事实（非专家优先 12 / 均匀 2 / 专家优先 1）」与「2 对钉住对照 16 格全跨 0、最大半宽 0.135」，不写成「哪种分配更好」。
- producer: `python3 report_inputs/build_moe_feasibility.py --check`；`python3 checks/moe_feasibility_negative_control.py`（把 18 改成 0 → 正文从「预算比较」改口成「分配比较」）

## res54 :: 报告第四节把「分配」与「预算」分开：第三臂（均匀 4.531 vs 专家优先 4.483）6 列可分辨，差不是预算能解释的。

- kind: measured
- status: current
- evidence: 第四节新增段落由 `report_inputs/build_moe_feasibility.py` 读 `a04` 的 `RESULT.md::third-arm-pinned` 与 `fixtures/pin_feasibility.json` 生成：`Δbpw = +0.048`、`L1_pw = 0.176`，HumanEval+ +0.4695 [+0.3720,+0.5535]、HumanEval +0.4817、MBPP+ +0.3439、MBPP +0.4339、MMLU +0.1952、GSM8K +0.2400 六列不含 0，ARC-c/IFEval +0.0900 跨 0；按本族斜率 `Δbpw` 只值 HumanEval+ 0.0086（全部预算项 +0.0064…+0.0097），远小于观测，方向是均匀更好。适用边界写明「同族 LFM2.5-8B-A1B、同 base、单一家族，不外推」，并记 Tier-1A 桶内结构未测（约 47 GPU 分钟）。库侧核对：`experiments` 3323 行、`a04-uni45` 的 humaneval / humaneval-plus 两格各 164 题、分数 0.6220 / 0.6037，`checks/db_check.py` PASS，备份 `bak18`/`bak19` 在位。
- producer: `python3 report_inputs/build_moe_feasibility.py --check`；`python3 checks/moe_feasibility_negative_control.py`（第三例：把 +0.4695 改成预算项的 0.0086 → 正文改口成「这个差可由预算解释」）

## res55 :: `.wrapup/variant_panel.py` 新增 `vendor-recommended` 采样臂：五个采样量写进协议串、直传请求体，codegen 显式跳过。

- kind: measured
- status: current
- evidence: 臂名 `vendor-recommended`，采样 `temperature=1.0, top_p=1.00, top_k=20, min_p=0.0, presence_penalty=2.0`；`sampling_spec()` 把它们写成协议串的一段 `sampling=temperature=1.0,top_p=1.0,top_k=20,min_p=0.0,presence_penalty=2.0`，面板把它记进 `variant_panel.json` 的 `sampling_spec`，`migrate_db.ingest_variant` 把它接在 `variant-sampling-<label>-{lmeval,evalplus}` 后面，于是五个量随行入库、并落在 23 列测量身份里（不会与 greedy 合并）。lm-eval 一侧走 `--gen_kwargs`（即请求体字段，客户端不重采样）。**evalplus 的 CLI 只接受 `--temperature`**，其余四个量传不进去，所以该臂的 codegen 显式跳过并记 `codegen_skipped`，不用默认值顶替。`mpl_protocol_label` 的白名单加入 `sampling=`，厂商臂与 greedy 的显示标签不同。
- producer: `python3 checks/vendor_arm_negative_control.py`（协议串逐字含五个量、vendor ≠ greedy、top_k=1 ≠ top_k=200、标签不同）
- 未验证（硬阻塞）: 服务端是否真按这五个量采样需要模型文件，本机已无 gguf；要跑的命令是 `python3 .wrapup/variant_panel.py --model <X.gguf> --tag a06-vendor-sampling --axis sampling`，证据取 `variant_panel.json` 的 `sampling_spec`、`server.log` 的采样回显与五列分数。`seed` 未固定，所以该臂的协议里不带 seed，重跑不保证逐字节一致——这一点必须随结果一起写。

## res56 :: 厂商推荐采样臂的五个量确实进了采样：服务端 `/props` 回显 `got == want`，且用「塌缩判据」证明——单点 A/B 两个方向都会骗人。

- kind: measured
- status: current
- evidence: 服务端证据 `audits/vendor_arm_probe.json` 与 `a06` 面板的 `mres/m165-vendor/props/q2.json`：五个量 `got == want`、`mismatch: []`、`n_slots=1`，说明服务端持有的就是这五个值（不是默认 `temperature=0.8`）。参数**生效**的判据用结构性的那条（`a06` 的 32 项检查 31 PASS）：`top_k=1` 与 `top_p=0.1` 必须逐字重现 `temperature=0` 的输出，`/completion` 与 `/v1/chat/completions` 两端点都通过；同 seed 重复逐字相同、`temperature 0 vs 1.0` 逐字不同。唯一 FAIL 是短清单（8 token、无重复可罚）上的 `presence_penalty 0 vs 2.0`——**单点 A/B 两个方向都会骗人**：我先前用单点判据得「参数被吞」，`a06` 曾用单点得「改了变了」，两次都是巧合，所以判据要结构性。
- producer: `docs/subprojects/i02-测量基础设施/audits/vendor_arm_probe.py`；`a06` 的 32 项检查（含 `mres/m165-vendor/props/*.json`）
- 附带（塌陷而非扰动）: 厂商档在 `q2-cpp` 是 1/161（`SyntaxError 142 / Exception 18 / OK 1`）、贪心 18/161；塌陷来自 `top_p=1.0 / min_p=0.0 / presence_penalty=2.0` 那组而不是温度。报告第六节将来要按这个幅度写「固定协议比厂商档更宽容」。

## res57 :: `ingest_m165` 让厂商档 R1 的格能入库：五参数 + seed + ctx 进身份列与协议串，skip ledger 可见。

- kind: measured
- status: current
- evidence: `.wrapup/mres/m165-vendor/vendor_r1_summary.jsonl` 的每行自带 `protocol`（`mpl-raw-t1.0-768;ctx=4096;sampling=temp=1.0,…`），`migrate_db.ingest_m165` 原样入库，并把 `temp/top_p/top_k/min_p/presence_penalty/seed/ctx_size` 写进各自的列（都在 23 列测量身份里，不与贪心格合并）；未知模型名与「用了默认协议」都进 `INGEST_SKIPS` 总账。短名映射 `q2/q3 → Qwen3.5-2B-UD-Q{2,3}_K_XL` 的依据是同一 cell 的贪心格与 m29 逐位相同（18/161、22/161）。
- producer: `python3 checks/m165_ingest_negative_control.py`（真文件按行入库、只差 `presence_penalty` 的两行各成一格、未知模型进 ledger）；`python3 migrate_db.py` 末尾的 `== ingest skips ==`

## res58 :: 报告第十四节按官方 AST checker 重写：两套判分器不可混算、micro 与 macro 都可算不可混用、两处结论翻转写明。

- kind: measured
- status: current
- evidence: 第十四节新增段落由 `report_inputs/bfcl_judge.json` 渲染（`build_bfcl_judge.py` 从 `a13` 的 `RESULT.md` 抽数）：native 协议行是 `…-official-ast-checker`（79 格）、prompt 协议仍是 `…-homegrown-matcher`（20 格），两类不可混算；换判分器把 2,788 题由判错改判对、35 题反向，5 个非 live 类别合并的第一名从 `Bonsai-q2g64` 0.7053 换成 `gemma-4-E4B-Q3` 0.8908（vs Bonsai 0.8808，差 0.0100、方向相反），排序大体保留（4/55 对逆序）但绝对分数与 ≤0.05 邻近间距不可沿用；micro 与 macro 现在都可由库算（例 gemma-4-E4B-Q3 五类 micro 0.8944；两者仍相差约 0.2059），本表仍不给汇总列；多轮写成有界结论（4 组 handler 组内可比、granite 独立无对照、gemma 0 行、跨族无证据、2×2 未测≈50 GPU 分钟）。旧的「micro 不可从库复算」一句已删除。
- producer: `python3 report_inputs/build_bfcl_judge.py --check`；`python3 checks/bfcl_judge_negative_control.py`（改判计数改成 0 → 正文改口成「与判分器无关」）

## res59 :: README 里「哪些产物入库」的说法有检查兜着，不再随入库漂移。

- kind: measured
- status: current
- evidence: README 原先一边说 `.wrapup/mres/*_eval.json` 不入库、一边在 Ships 清单里列它们，且写死「337 files」（实际跟踪 341）。现在删掉「不入库」的说法、把文件数改成「以 `git ls-files '.wrapup/mres/*_eval.json' | wc -l` 计数为准」，并新增 `checks/readme_counts.py`：README 若再说这些产物不入库、或写的文件数与 `git ls-files` 不一致 → FAIL。已接进 `reproduce.sh`。
- producer: `python3 checks/readme_counts.py`

## res60 :: 事实 id 的作用域是文件，不是仓库；`docs/check_docs.py` 只要求同一文件内唯一。

- kind: measured
- status: current
- evidence: `res1`–`res6` 在 `a01` 与 `a08` 各有自己的一套、`res13` 与 `population/multiplicity/unmeasured` 在 `a03` 与 `a10` 各自编号——引用方式一直是 `path::id`，所以跨文件同 id 合法。检查器此前按「合并后的层」判重，报了 6 条假失败；现在改为 per-file：同一文件里重复声明直接报错（与 YAML 重复键等价），跨文件同名只统计不报错，输出里写明「身份是 path::id」。修完 `python3 docs/check_docs.py` 退出 0（此前的 6 条失败来自我自己的 `RESULT.md` 里一处陈旧重复节点 `res46`，已删）。
- producer: `python3 docs/check_docs.py`；`python3 checks/docs_dup_id_negative_control.py`（同文件重复 → 退出 1 并点名；跨文件同名 → 退出 0），已接进 `reproduce.sh` 成为门而不是基线容忍。

## res61 :: 报告第十一节按 a10 的四条建议改：1/32 格分得开并按多重比较读，方案标签不是独立变量，「同字节+同分配」对照臂本库不存在。

- kind: measured
- status: current
- evidence: 第十一节由 `report_inputs/gsq.json` 渲染（`build_gsq.py` 读 a10 的 `RESULT.md`）：9 列 32 个有区间的格里只有 1 个分得开（HumanEval +0.0671 [+0.0031,+0.1329]，且该档少花 0.301 比特/权重，方向与预算相反），**两侧 p = 0.043（由区间反推）**，同族可独立比较 ≤18，所以按多重比较读属偶然量级——是值得记下的信号、不是方案红利；同时写明「不能说没有红利」（那是把不可分辨读成相等），量出上限是二项半宽 0.032–0.076，并指出「同字节 ≠ 同分配」（两档差 0.209/0.301 比特/参数）与「同字节+同分配+不同方案」对照臂是 0/0（本库测不了），附否证条件。
- producer: `python3 report_inputs/build_gsq.py --check`；`python3 checks/gsq_negative_control.py`（1 格改成 0 → 正文改口成「全部测不出」）

## res62 :: 干净 clone 里 `A10_NO_GGUF=1` 写死，避免子项目「glob 到本机路径就假绿」。自查：我的七个子项目派生索引都只读随仓库分发的产物。

- kind: measured
- status: current
- evidence: `reproduce.sh` 顶部 `export A10_NO_GGUF=1`，让 a10 的 `build_fixture.py --check` 在 clone 里报「未核对 gguf 源」而不是通过。自查同类风险：`build_size_claims`（读 a02 的 `analysis/*.json`）、`build_moe_feasibility`（读 a04 的 `fixtures/*.json`）、`build_bfcl_judge`/`build_gsq`（读子项目 `RESULT.md`）、`build_bfcl_gap`（读 tracked 的 `.wrapup/*_summary.jsonl`）、`build_paired_deltas`/`build_reproducibility`（读 i01 `RESULT.md`）都只依赖入库文件；唯一执行外部脚本的是 `build_kv_evidence`（跑 a05 的 `kv_evidence.py`）与 `build_scheme_effects`（跑 a03 的 `attrib.py`），两者只读库与 tracked fixture，且 `--check` 不一致会 WARN 而不是通过。
- producer: `grep -n "A10_NO_GGUF" reproduce.sh`；`./reproduce.sh`

## res63 :: 报告第六节按 a06 的厂商臂实测改：是绝对丢题（−17~−36），不是比例塌陷，也不是温度。

- kind: measured
- status: current
- evidence: 第六节由 `report_inputs/sampling_collapse.json` 渲染（`build_sampling_collapse.py` 读 a06 的 `RESULT.md`）：MultiPL-E 六格 18→1/22→3/39→4/43→7/37→6/44→12（−17…−36），EvalPlus HumanEval 94→59（−35），损失不是常数；cpp 的直方图 `SyntaxError=142, Exception=18, OK=1`（语法塌陷）与 py 的「能解析跑不起来」是两种失效形态；temp 0.3/0.6 下 cpp 仍是 18/161，且把截断量改回固定协议、`presence_penalty` 置 0、只留 `temperature=1.0` 时该格仍是 2/40——所以不是温度、截断量也不是主因。「10 倍塌陷」只在相对意义成立，固定协议比厂商档宽容的正是这十几到三十几道题。
- producer: `python3 report_inputs/build_sampling_collapse.py --check`；`python3 checks/sampling_collapse_negative_control.py`（丢题数改成 0 → 正文改口成「与固定协议差距为零」）


## res64 :: 非代码基准的 `language` 必须是空——599 行曾是 `python`（全库回填的产物），现在按「重插即恢复」复原，并有一条查询可验证。

- kind: measured
- status: current
- evidence: 起因是 `refresh_preserve` 负控抓到的一处改别人的行：`migrate_schema()` 原来无条件
  `UPDATE experiments SET language='python' WHERE language IS NULL`，把 gsm8k/mmlu/ifeval/arc_challenge/
  truthfulqa_mc2 这五族**非代码基准**的 599 行（并入 run_tag 之后的行）也写成了 `python`。
  恢复方式是**重算而不是回滚**：这些行的 ingester（campaign / variant / lmeval 面板）重插时本来就写
  `language=None`，把回填收窄成 `WHERE language IS NULL AND run_tag IS NULL`（只回填并入 run_tag 之前的老行）
  之后，下一次 refresh 重插就把它们复原成 NULL；行数、分数、协议串一个字都没改。
  可验证的查询（非代码基准的 `language` 必须为空；返回 0 行才算成立）：
  `sqlite3 experiments.sqlite "SELECT bench_family, language, count(*) FROM experiments WHERE bench_family IN ('gsm8k','mmlu','ifeval','arc_challenge','truthfulqa_mc2') AND language IS NOT NULL GROUP BY 1,2"`。
  负控：`checks/refresh_preserve_negative_control.py` 造一行（variant 地盘、`language` 为空）探针，
  在这个回填还在时会红——本轮它确实先红后绿，这就是「恢复有据可查」的那条证据。
- producer: `python3 checks/refresh_preserve_negative_control.py`；`sqlite3 experiments.sqlite "PRAGMA table_info(experiments)"` 与上一条查询

## res65 :: py 语料取代从 11 格推进到 12 格：用清单的 `summary_file` 与 `source_file` 交叉认行，并撤回 4 个互相矛盾的绑定。

- kind: measured
- status: current
- evidence: 39 格定位不了的根因是「五元组（model/bench/language/protocol/n_items）落在多行」。清单的
  `db_source_files` 是那批候选行的来源集合，切不开；能切开的是清单的 `summary_file`（a14 找到这批完成物的
  那份 summary），也就是 `a12` 的 `mpl_cell_audit.py` 第 `[1]` 段「逐格能不能追溯到一份产物」用的键
  （只读调用它，未改其文件）。按 `source_file == basename(summary_file)` 过滤后：12 格唯一（新入 5 格，
  另 7 格此前已入），其余 38 格仍不唯一（同一 summary 内 mult行）或全无候选。
  **同时撤回了 4 个绑定**：`m3-e2b-q2-py`、`m3-e4b-q3-py`、`m3-q36-35b-q2-py`、`m3-gr3b-q4-py` 的旧行
  `source_file` 分别指向 m5/m6/m10_granite 的 summary，而清单 `summary_file` 说的是 m3——清单自己的两列互相矛盾，
  按「不猜」回滚（删新行、清指针，编号备份 `experiments.sqlite.bak71`）。
  现在每个指针都满足：旧行 `superseded_by` 指向的新行协议串 = 旧协议串 + `;corpus=ac14c3b0abfa;gen_corpus=pre-2026-10-14`，
  且旧行 `source_file` == 清单 `summary_file` 的 basename（可逐行复核）。
  报告 §13 表注随之写成「改分的 50 格里只有 12 格已取代，38 格定位不了、仍是旧语料值」。
- producer: `python3 migrate_db.py`（幂等）；`python3 checks/py_corpus_regrade_check.py --before experiments.sqlite.bak31`；`python3 docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py`

## res66 :: §15 的比例列与二元列现在同代：11 格比例行按钉住语料重算入新行，旧行标指针；13 格仍是旧语料。

- kind: measured
- status: current
- evidence: a14 的 res22 说比例的分母也是测试语料，所以比例列必须与二元列同代。`migrate_db.py::ingest_py_testfrac_regrade`
  按「`run_tag='m41-testfrac'` 且 `_score == mean_frac_old`」认行（要求唯一），把 a14 的 `mean_frac_new`
  按同一条身份串后缀入新行、旧行写 `superseded_by`：**11 格**（27 个重算格里有 16 个库里根本没有比例行）。
  报告 §15 的表注写明「11 格已按钉住语料重算、13 格仍是旧语料，不可直接比」，数字从库里读。
- producer: `python3 migrate_db.py`；`python3 report_inputs/../checks/report_check.py`；表注文本见 `make_report.py::testfrac_corpus_note`

## res67 :: 取代行会让 a12 的谱系审计把它们记成「untraced」——这是语料代次的必然结果，不是数据丢失。

- kind: measured
- status: provisional
- evidence: 只读跑 `mpl_cell_audit.py`：`[1] scored cells traced 337/345`，其中 **8 条 UNTRACED 全是 `;corpus=` 行**——
  重评后的分数不可能被旧 summary 复现（summary 记的是旧语料的通过数），它的证据物是 a14 的取代清单
  （逐格 `pass_new`）而不是 summary。同一份审计的 `[7] report cells read: 198; not belonging to their protocol row: 0`
  在报告重建后为 0，`[9] stored protocols that disagree ...: 0`。需 a12 决定是否在其 `[1]` 里把带 `corpus=` 的行算作
  「以清单为证据物」，i02 不改它的文件。
- producer: `python3 docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py`

## res68 :: 全 Exception 的格在入库时写 NULL——这是**写侧保证**，不是事后修缮。

- kind: measured
- status: current
- evidence: `m51`/`m54` 的 summary 给「一个都没被判分」的格写了 `pass=0, score=0.0`，而同一测量的
  canonical 孪生行是 NULL：同一格在库里存了两份，一份 0.0 一份 NULL。0.0 会被读成「测了、一个都没通过」，
  那是把「没有测量」写成「测量结果是 0」。
  写侧规则现在在 `migrate_db.py::summary_score`，由 `ingest_mpl` / `ingest_m27` / `ingest_m165` /
  `_ingest_mpl_ctx` 四处共用：
  （1）summary 行没有 `score`（缺失或 None）→ 写 NULL；
  （2）`score == 0` 且逐题产物**全是 Exception** → 写 NULL。证据先用 summary 自带的 `statuses`，
  没有就退到随仓库分发的逐题产物索引 `report_inputs/eval_status.json`，按 (模型键, 语言, 题量) 找；
  多个候选口径不一致就当作**分不出**，不猜（仍是 NULL 的判据不适用，按 summary 记的 0 入库并记 ledger）。
  **只认「全 Exception」**：全 SyntaxError 是模型写不出能编译的代码，那是一次实测的 0——`a05` 的加长前缀
  网格就靠它当楼层，规则不能把它一起抹成 NULL（实测：m51 gemma12b-q2 java `{'SyntaxError': 158}` 保持 0.0，
  m54 q3 rs `{'Exception': 1, 'SyntaxError': 154}` 保持 0.0，只有 js/rb 四格 `{'Exception': 161}` 变 NULL）。
  负控 `checks/all_exception_null_negative_control.py` 在**库副本**上造三行（全 Exception / 有通过 / 没记分数），
  断言 NULL / 实测 0.8075 / NULL；外加一条**差分**：把 `summary_score` 换成旧写法再入一次，那三行必须是
  `0.0`——两条结果不同才说明规则在承重。
  已排查同类：从 summary 直接写分数的 ingester 只有 `ingest_mpl` 一族（m1/m2/m3/m5/m6/m10/m21/m25/
  m33/m35/m50–m60 等）、`ingest_m27`、`ingest_m165`、`_ingest_mpl_ctx`，现在都走 `summary_score`；
  `ingest_campaign`（lmeval）本来就不写缺失分数、`ingest_variant` 只在面板给了值时才写、
  `ingest_m41`（比例）不写二元分数。库内那 4 行的数据修缮由 `a12` 的 `migrations/null_all_exception_cells.py` 做
  （备份 + 完整性 + 行数不变 + 幂等），i02 只保证**不再写出来**。
- producer: `python3 checks/all_exception_null_negative_control.py`；`python3 migrate_db.py`（幂等，第二次净改 0 行）

## res69 :: 承载断言的证据随仓库走：m165 的 R1 来源清单与三个 variant_panel.json 入库，干净 clone 里 a12 的审计 exit 0。

- kind: measured
- status: current
- evidence: `a12` 的审计在干净 clone 里 exit 1，卡在 3 条 m165 vendor 行——它们的 `source_file` 指向
  `.wrapup/mres/m165-vendor/vendor_r1_summary.jsonl`，而 `.gitignore` 只放行 `*_eval.json`，于是
  「库里有行、证据不在仓库里」。放行四个小文件（合 ~7 KB）：`m165-vendor/vendor_r1_summary.jsonl`（R1 七行清单）、
  `m165-vendor` / `m130-kv` / `m131-sampling` 的 `variant_panel.json`（§10 面板的采样规格，也是那些
  variant-* 行的唯一来源）。写法上父目录被 `.wrapup/mres/*` 忽略时文件级 `!` 不生效，所以先放行子目录
  `!.wrapup/mres/*/` 再放行文件，其余内容（samples、probe dump、面板原始 json）继续忽略。
  验证：干净 clone `db58584` 里 `python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"`
  **exit 0**（341/341 已评分格都追到证据：summary 251 / per-item eval 78 / a14 清单 12，untraced 0）；
  同 clone 里 `./reproduce.sh` exit 0（44 PASS / 0 WARN / 0 FAIL）。
- producer: `git check-ignore -v .wrapup/mres/m165-vendor/vendor_r1_summary.jsonl`（无输出＝已放行）；
  `python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"`

## res70 :: 「读不到输入就不删」的 guard 是承重的：干净 clone 里去掉它丢 898 行，带上它丢 0 行。

- kind: measured
- status: current
- evidence: 差分负控 `checks/refresh_guard_differential_control.py` 在**干净 clone**（`.wrapup/mres` 只有
  随仓库分发的 3 个面板文件）里跑两次完整 refresh：带 guard 时 `mres/%` 行 933 → 933（丢 0）、
  `migrate_db.py` exit 2；把 `MIGRATE_WIDE_DELETE=1` 打开（删除范围换回旧写法 `source_file LIKE 'mres/%'`）后
  933 → 35（丢 **898** 行）。同一个 clone、同一个库副本，只有这一处开关不同——所以丢行是那条删除范围造成的，
  不是环境差异。开关只给这条负控用，默认关闭。
- producer: `python3 checks/refresh_guard_differential_control.py`（输出里 `1)`/`2)`/`3)` 三行就是前后对照）

## res71 :: 全仓最终验收：九个子项目的入口逐棵树跑过——本机工作树 8 绿 + 1 红（`a08`），干净 clone 6 绿 + 2 个 2（不可得，按契约）+ 1 红。

- kind: measured
- status: current
- evidence: 同一份库、同一批命令，分别在本机工作树与干净 clone（`git clone` 后未改任何文件）里跑。
  三种退出码按仓库既有语义读：**0 = 测过且成立**；**2 = 不可得**（缺输入，不许当成通过）；1 = 有断言不成立。

| 子项目 | 入口 | 本机工作树 | 干净 clone | 说明 |
|---|---|---|---|---|
| a01 量化位宽 | `analysis/run_all.py` | 0 | 0 | 夹具随仓库分发 |
| a04 MoE 比特分配 | `analysis/run_all.py` | 0 | 0 | 同上 |
| a07 投机解码 | `spec_evidence.py` / `--check` | 0 | **2** / **0** | 裸跑要 `.wrapup/mres/*-spec-*` 与 `m28_speed.jsonl`（不随仓库分发）→ 2；`--check` 只读 fixtures + 库，clone 里 **0**（80 质量行 / 20 速度行 / 3280 逐题 / 15 字节对全部对上，入库 6 臂的字节 sha256 逐条对得上） |
| a08 思考开关 | `analysis/run_all.py` | **1** | **1** | `thinking_pairs --check`：census 记 131、重算 132。原因不是环境：它的 census 用 `count(*)` 数**行**，而 i02 的 py 语料取代给其中一格加了取代行（旧行保留、`superseded_by` 指新行）。修法在 a08 侧（census/pairs 查询加 `superseded_by IS NULL` 再重生成 fixture）；i02 不改别的子项目的文件，报告侧早已按同一规则过滤 |
| a10 第三方方案 | `analysis/run_all.py` | 0 | 0 | — |
| a11 扩散解码 | `analysis/run_all.py` | 0 | 0 | 门槛与价格都是入库事实（GATE-FAIL 不等于 0 分） |
| a12 MultiPL-E | `mpl_cell_audit.py` | 0 | 0 | clone 里 341/341 已评分格全部追到证据（summary 251 / per-item 78 / a14 清单 12），untraced 0 |
| a13 BFCL | `audits/run_all.py` | 0 | **2** | clone 里 `MISSING INPUT: .wrapup/bfclenv/bin/python`——它要一个本地 venv，二进制环境不随仓库分发，所以是「不可得」而不是通过；本机全绿 |
| a14 部分给分 | `py_regrade.py` | 0 | 0 | 取代清单与证据随仓库分发 |

- 结论：**唯一需要别人动手的一条是 a08 的 census 过滤**；两条 2 都是「输入不在场」的既定契约，不是失败也不是通过。
- producer: 上表每条命令；`./reproduce.sh`（干净 clone，47 PASS / 0 WARN / 0 FAIL / 1 SKIP=kv 输入不在场）

## res72 :: 十六轴总账：每轴一句结论 + 已记录的限制 + 未测的统一入口。

- kind: measured
- status: current
- evidence: 逐轴一句话（依据在各子项目的 `RESULT.md`，数字不复述）：

| 轴 | 一句话结论 | 已记录的限制 |
|---|---|---|
| a01 量化位宽 | 同一权重族内「比特越少越差」成立，但存在拐点与反例（三元在离轨点上不服从单调）；拐点位置逐族不同 | 只有少数族有 ≥4 个位宽档；单次运行的跨 run 上限未定（`a03` 复现负控未跑） |
| a02 模型规模 | 同族同配方下「越大越好」在 3/4 的曲线上成立，Q2_K_XL 上是反例；标签通道给的规模不可靠，真值来自张量求和 | `plan5` 的双变量回归**不可识别**（库里没有同总参不同激活的受控对） |
| a03 方案与厂商 | 换方案在部分基准上可分辨，换厂商**本库答不了**（唯一跨上传者受控族单点识别，逐列半宽 0.019–0.489 全跨 0） | 厂商效应是「测不出」不是「没有」；同一 gguf 名的分配不同则不可比 |
| a04 MoE 比特分配 | 专家层压到 2 比特、其余 5 比特这类分配与均匀档位差异在噪声内；「专家层该压多低」未被证据支持 | 只有 2 个受控分配对；「同字节+同分配+不同方案」对照臂是 0/0 |
| a05 KV 精度 | 短上下文下 KV 量化 q4_0 与 f16 的**分数**差在噪声内，但**逐题判定**在双向翻（丢 15 / 得 11） | 长上下文只测到 32k（8k 处才有 ≥4 的差，32k 不可分辨）；40k 以上未测 |
| a06 采样与解码 | 厂商推荐采样在代码基准上**绝对丢题 −17~−36**，两种失效形态（cpp 语法塌陷 / py 跑不起来）；温度不是主因 | 丢题数未在其它基准上复测；「10 倍塌陷」只在相对意义成立 |
| a07 投机解码 | 深度换速度（0.8B +26.3% @n2），但**输出逐字节变了**：164 题里 73 条不同、分数 52→49 ⇒ 质量列必须每次重测 | 速度是单一固定提示上的 3 次重复均值、无区间；草稿路径显存与头权重是两个口径 |
| a08 思考开关 | 思考开关**买的是 token 不是准确率**：开思考在 gsm8k 上不提升、成本 7.1×–15.0×；代码类库里没有「开」格 | 代码类整类无开臂（`census` 里 code 行的 on 侧为空） |
| a09 QAT | QAT 在本库**没有可分辨的增益**；唯一可比的 QAT/普通对差异落在噪声内 | 对照臂少（1 对），且 31B 那一臂 `BLOCKED-on-VRAM` |
| a10 第三方方案 | 32 个格里只有 1 个分得开（HumanEval +0.0671，且方向与预算相反），按多重比较读属偶然量级 | 「本库测不了」不是「没有红利」；0/0 对照臂说明同分配不同方案测不了 |
| a11 扩散解码 | 本机**测不了**：`GATE-FAIL`（两棵 llama.cpp 的架构表都没有 `diffusion-gemma`），不是低分 | 已定价未买：权重 15.638 GiB + KV 真值 0.273 GiB/cap 1.875 GiB；compute buffer 未算 |
| a12 MultiPL-E | cpp 与 py **不许池化**：同一模型的两种语言排序在 169/1275 对里相反，py−cpp 从 −0.2671 到 +0.1863 | 「12B 崩到 0」是语言集缺陷（不是分数）；逐语言表的行键装不下 `top_k` |
| a13 BFCL | 自研匹配器系统性偏低，换成官方 AST checker 后差异落在「可选参数省略」这一类；prompt 协议是另一套测量 | 多轮只有类别级数据，**micro 不可得**；`long_context` 支路未触及 |
| a14 部分给分 | 部分给分与二元判定逐题自洽，但它的分母是测试语料：语料换代让 50/98 格改分、151/15516 题翻转（全在 py） | 12/50 格已按钉住语料取代，38 格定位不了仍为旧值（报告 §13 有表注）；16 格库里没有比例行 |
| i01 判分与有效性 | 确定性解码的地板 = 0（同配置跨会话逐字节相同）；「噪声地板」类断言只在同语料内成立 | 跨语料不可比；CLI 上 `--log_samples` 从未开过，gsm8k/mmlu 逐题不可得 |

- **未测的统一入口**：`docs/subprojects/i02-测量基础设施/non_measurements.tsv`（报告里渲染成独立登记表，与「未测 ≠ 0」相邻）。三类分开读：
  `BLOCKED-on-VRAM`＝已排进队列但显存不够（nm1–nm3，属「已定价未买」）；`GATE-FAIL`＝本环境缺运行时（nm4，扩散）；
  其余「本环境不可测」的（BFCL micro、长上下文 >40k、gsm8k 逐题、跨语料比较）写在各轴的「限制」列里，
  因为它们的成因不同、补测价格也不同，合成一张表会抹掉差别。

- **对目标的覆盖**（目标本身见 `docs/need/need.yaml::n1`，此处只列覆盖，不复述目标）：十六轴的**已覆盖**：量化的位宽/方案/厂商/QAT/第三方（a01/a03/a09/a10）、模型规模与 MoE 分配（a02/a04）、运行时（a05 KV 精度、a06 采样、a08 思考开关、a07 投机）、解码方式（a11 扩散，GATE-FAIL）；**未覆盖**：模型**架构**与**版本**作为 X（没有一条「同一参数量、不同架构/不同代」的受控研究）、**激活规模**只在 a02 的 `plan5` 里以「不可识别」出现；**基准端**以静态代码/知识/指令类为主，agentic 只有 BFCL 工具调用（含多轮），且**没有难度维度**（同一任务族内按难度分层）。补齐这三块才是目标，不是把上述限制逐条清零。

## res73 :: 本机对外可达性与 agentic 评测依赖（2026-10-27 实测）：Docker 与 pypi/GitHub 通，HuggingFace 正站与镜像都不通，所以「数据只在 HF 上」的基准与模型这周进不来。

- kind: measured
- status: current
- evidence: Docker Engine 29.8.2 运行中且能从 Hub 拉镜像；pypi / api.github.com / git ls-remote / jsdelivr / modelscope 可达；`huggingface.co` 与 `hf-mirror.com` 均连不通（调研当日实测）；`/home/z/hf` 现有 842 GB / 57 个 `models--*`，`/home/z/hf/datasets--*` 为 0；`llama-server` = llama.cpp `0.4.1-dev build 4399`（含 `--tools`）；`bfclenv` 内 `bfcl_eval==2026.3.23` 自带 21 个 `BFCL_v4_*.json`（4693 条），离线类别可跑，`web_search*` 需 SerpAPI key、`memory*` 需 `all-MiniLM-L6-v2` 权重（未缓存）。
- producer: 调研工作包的实测记录（采集命令与输出在 `.wrapup/agentic/` 之前的调研日志里）；重申时刻 = 2026-10-27。
- 影响：模型**版本/架构**这一整类 X 需要新权重，HF 不通时只能走 modelscope；基准侧同理（AppWorld / SWE-bench / GAIA 的数据在 HF）。这条不是缺陷而是资源事实，决策见 `docs/plan/subprojects.md` 的 `agentic` 节。

## res74 :: agentic 基准的取用代价实测（2026-10-27）：BFCL 零网络可用；Terminal-Bench 2.0 的仓库今天取不下来（git clone 与 codeload tar 都超时，只有 `git ls-remote` 通），Docker Hub 与镜像站可拉、单题镜像数百 MB。

- kind: measured
- status: current
- evidence: `git clone --depth 1 https://github.com/harbor-framework/terminal-bench-2` 与 `curl codeload …/tar.gz` 各自 300 秒/90 秒超时；`git ls-remote` 同一仓库 2 秒返回 HEAD；`docker pull alexgshaw/fix-git:20251031` 成功（493 MB）；`/home/z/.venvs/tb` 里 `pip install terminal-bench` 走 pypi 仍在下载（当时未完成）；`.wrapup/bfclenv` 内 `bfcl_eval==2026.3.23` 与 21 个 `BFCL_v4_*.json` 就在盘上，`.wrapup/bfcl_run.py` 可直接跑 `--mode tools|prompt`。
- producer: 命令与日志见 `.wrapup/agentic/`（tb2 探路）与本条记录的时长；重申时刻 = 2026-10-27。
- 影响：agentic 第一批的顺序改成「BFCL 先、TB2 后」——这不是偏好，是当日可达性决定的；TB2 一旦仓库可取，`p-ag1` 的三题探路照原样做。
