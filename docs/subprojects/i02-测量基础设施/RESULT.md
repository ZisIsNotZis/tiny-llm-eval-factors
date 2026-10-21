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
## res46 :: 报告新增「测量可复现性边界」一节，数字与适用条件都由 i01 的事实生成；BFCL 一节说清 micro/macro 且不给总分。

- kind: measured
- status: current
- evidence: 新节由 `report_inputs/reproducibility.json` 渲染（该索引由 `report_inputs/build_reproducibility.py` 从 `i01/RESULT.md` 的 `res32` / `res29` 抽取，2 条事实、2 族地板、1 个幅度）：地板是「同配置重复 161/161、164/164 逐题相同、翻转 0、Jaccard 1.0」，判读规则是「同一提示集哈希 + 同一后处理版本下任何非零跨 run 差异都不是噪声」；输入变更时是「16 题双向翻转（11 上 / 5 下、净 +6）、±16/161 ≈ 0.10、76/161 文本不同、66 题 token 不同」，并写明适用条件（只有提示集哈希 + 后处理版本都钉住才可比，两个数字不得相加）。BFCL 一节新增口径说明：没有唯一总分、本表不给汇总列、面板 micro 与类别列 macro 不可混用；两者在本仓最大差 `0.2028`（`gr3b-q2`：micro 0.3905 vs macro 0.1877，当场从 `m8_summary.jsonl` 算出），并说明多轮 21/123 行仍无题量、micro 不可从库复算。
- producer: `python3 report_inputs/build_reproducibility.py --check`；`python3 checks/reproducibility_negative_control.py`（幅度改 0 → 正文改口；删适用条件 → 生成失败）

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

