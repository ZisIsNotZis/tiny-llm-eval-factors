# checks — i02 的基础设施检查

这个目录归 i02（测量基础设施）。每个脚本证明一件事，都以退出码说话。「谁调它」这一栏只有两种：
`./reproduce.sh`（一条命令核全部，`PASS`/`FAIL` 成对——负控不接进来的检查只证明「今天打印了绿」），
或「按需」= 由某个结果节点在它的 `producer:` 行里点名、需要时才跑（不是每次都跑的守卫）。
`checks/*.py` 有 43 个文件，下表逐条覆盖，一个不漏。

| 命令 | 证明什么 | 谁调它 |
|---|---|---|
| `python3 checks/db_check.py` | 库结构完好、外键无冲突、必填字段非空、取值域不越界、没有重复的测量身份 | `./reproduce.sh`（第 5 步） |
| `python3 checks/report_check.py` | `report.html` 与产物一致：行标签唯一、印出的题量等于该格产物的题量、非测量登记册在场、无法区分两个值的格把两个值都印出来 | `./reproduce.sh`（第 10 步）与 `superseded_filter_negative_control.py` |
| `python3 checks/stale_roots.py` | 没有可执行脚本再引用已退役的绝对根路径（`--fix` 是幂等迁移，改完自动 `bash -n` / `py_compile`） | `./reproduce.sh`（第 6 步） |
| `python3 checks/readme_counts.py` | 根 `README.md` 关于「哪些产物入库」的说法与 `git ls-files` 一致（数字由命令当场数） | `./reproduce.sh` |
| `python3 checks/report_inputs_drift.py` | 报告输入是否还跟它的来源一致：13 条判断的**唯一** home，漂移=FAIL、看不到来源=SKIP | `./reproduce.sh`（第 4 步，经 `check_report_inputs` 翻成核对表的行） |
| `python3 checks/report_inputs_drift_negative_control.py` | 上一条真的会红：改坏 `open_questions.json` 一个字节 → `./reproduce.sh` 非零退出并点名；移走 `gsq.json` → 该行 SKIP 且整体仍绿 | `./reproduce.sh` |
| `python3 checks/model_sources.py` | 报告附录的「模型来源」列只由随仓库分发的 `report_inputs/model_sources.json` 决定（`res77` 的守卫）：每个被印出的 gguf 都有条目，量化发布方 / GGUF 仓库 / 加载路径三列与索引逐字相同，渲染集是库内模型集的子集，报告里不许再出现「未知（本地文件，未找到下载来源）」；空扫描判 FAIL，`report.html` 不在场报 `BLOCKED`（exit 2） | `./reproduce.sh`（第 11 步）与 `model_sources_negative_control.py` |
| `python3 checks/recap_consistency.py` | 报告末尾的结论索引只做索引：16 行与 16 个编号节一一对应，每行「详见 §N」都落在真实节上，且表里不出现已撤回/被推翻的措辞（「同大小下方案有差」「全部差值都测不出」「所有深度分数无差别」）；空扫描判 FAIL | `./reproduce.sh` 与 `recap_consistency_negative_control.py` |
| `python3 checks/recap_consistency_negative_control.py` | 上一条真的会红：注入撤回措辞 → 红；删一行 → 红；把「详见」改成不存在的节号 → 红；未改动副本 → 绿 | `./reproduce.sh` |
| `python3 checks/model_sources_negative_control.py` | 上一条真的会红：改坏一条条目的仓库名 → 检查非零退出并点名该模型；删一条条目 / 索引写成非法 JSON / 索引整个不在场 → **真的** `python3 make_report.py` 非零退出并点名（缺条目在画图之前由 `require_sources()` 点名，几秒内失败）；每次失败都发生在写盘之前，`report.html` 的 sha256 全程不变，索引按原字节写回 | `./reproduce.sh` |
| `python3 checks/router_refs.py` | 三个路由文件（`STATUS.md`/`FINDINGS.md`/`README.md`）里印出的每条 `docs/…::id` 引用与每个 `docs/…` 路径都在树里解析得到；扫空不算通过 | `./reproduce.sh`（第 6b 步） |
| `python3 checks/router_refs_negative_control.py` | 上一条真的会红：二十一条期望逐条列在脚本头部（缺 id、缺文件、围栏/注释里的假 id、跨行与带空格的 `::`、空扫描、缺路由文件、未闭合遮蔽） | `./reproduce.sh` |
| `python3 checks/evidence_logs.py` | `docs/subprojects/*/RESULT.md` 点名的每个 `.wrapup/…` 路径都有处置（入库 / 压缩入库 / 目录 / 模式 / 按已声明的类忽略），并把「条数、原始字节合计、gz 字节合计」当场算在结论行上；**可重建缓存类的唯一清单**是它的 `REBUILDABLE_CLASSES`。两端语义不同：本机（盘上有未入库的 run 文件）逐条核到文件，pattern 一档把花括号一律展开成候选（没有单选项例外）、指名文件的候选按形状表判，dir 一档走进目录——**目录 token 不保证目录内每份文件入库**（目录里有一份入库 / 按类可重建的文件即算有处置，哪些是本地产物、不入库在使用点写明），exit 0；干净 clone 里只能按声明/索引判，报 `BLOCKED` 并 **exit 2**（不可得，不是绿） | `./reproduce.sh`（本机 PASS / 干净 clone BLOCKED）与 `evidence_logs_negative_control.py` |
| `python3 checks/evidence_logs_negative_control.py` | 上一条真的会红：在临时 clone 里——干净 clone 基线 exit 2（不可得）；换个字节数不同的 `.gz` → 多一条并点名该 `.log`；把已入库的被点名路径从索引里拿掉 → 判「无处置」；把精确点名的路径移到一条未声明的 ignore 规则下 → 判「无处置」；把一份未入库的 `evalplus.json` 用**模式**（`.wrapup/mres/m58-*/evalplus.json`）或**目录**（`.wrapup/mres/m58-fake-run/`）点名 → 判「无处置」并点名该文件；空扫描 → 断言**只有空扫描守卫会打的**那条 `BLOCKED 空扫描` 行（不是只断言 exit 2）。每一例「删掉它守着的那段代码 → 该例变红」的验证结果写在脚本文件头 | `./reproduce.sh` |
| `python3 checks/docs_schema_negative_control.py` | `docs/check_docs.py` 真的会失败：未改动副本 PASS，缺必填字段 / 枚举外取值都以 1 退出并点名（在临时目录里做） | `./reproduce.sh` |
| `python3 checks/docs_dup_id_negative_control.py` | 事实 id 的唯一性是**文件作用域**：同文件重复 → FAIL 并点名，跨文件同名 → PASS | `./reproduce.sh` |
| `python3 checks/venv_shebang.py` | venv 入口点的 shebang 都指向存在的解释器 | `./reproduce.sh` 与 `bootstrap_venv.sh` |
| `python3 checks/venv_shebang_negative_control.py` | 上一条真的会红：假入口点 → FAIL 并点名，指向 `env` 的不误报 | `./reproduce.sh` |
| `python3 checks/spec_decode_negative_control.py` | 第七/八节（投机解码）的句子由 a07 的派生索引决定：差异改 0 → 正文改口，地板改有差异 → 构建失败 | `./reproduce.sh` |
| `python3 checks/sampling_collapse_negative_control.py` | §6 厂商档口径：逐格丢题数改 0 → 结论必须从「绝对丢题」改口成「与固定协议无差」 | `./reproduce.sh` |
| `python3 checks/gsq_negative_control.py` | §11 第三方方案：「1 格分得开」由计数决定，改成 0 则全部测不出 | `./reproduce.sh` |
| `python3 checks/bfcl_judge_negative_control.py` | §14 判分器口径：改判计数改 0 → 与判分器无关 | `./reproduce.sh` |
| `python3 checks/moe_feasibility_negative_control.py` | §4 可行性：超界计数改 0 则从「预算比较」变「分配比较」 | `./reproduce.sh` |
| `python3 checks/kv_evidence_negative_control.py` | §5 KV：丢/得改 0 则从「逐题在翻」变「无差异」 | `./reproduce.sh` |
| `python3 checks/kv_evidence_unavailable_control.py` | §5 KV 索引「不可得 ≠ 过期」：缺 `.wrapup/mres` → exit 2 并点名路径 | `./reproduce.sh` |
| `python3 checks/size_claims_negative_control.py` | §2 规模说法：区间改重叠则从「反驳」变「分不出」 | `./reproduce.sh` |
| `python3 checks/scheme_effects_negative_control.py` | 方案/厂商结论句：显著则改口、区间加宽则精度跟着变 | `./reproduce.sh` |
| `python3 checks/reproducibility_negative_control.py` | 可复现性边界：幅度改 0 正文改口、删条件后生成失败 | `./reproduce.sh` |
| `python3 checks/paired_delta_negative_control.py` | §1 因果叙述是生成的：区间全跨 0 时报告改口，不声称掉点 | `./reproduce.sh` |
| `python3 checks/open_questions_negative_control.py` | 未解问题索引：工作包标题与围栏里的标题都不算一节 | `./reproduce.sh` |
| `python3 checks/ingest_protocol_negative_control.py` | 入库协议：只有 `fa` 不同的两行各成一格；缺协议时明说用了默认值 | `./reproduce.sh` |
| `python3 checks/ingest_skip_negative_control.py` | 入库跳过报告：未知名逐条报出、认得的名字跳过计数为 0 | `./reproduce.sh` |
| `python3 checks/all_exception_null_negative_control.py` | 全 `Exception` 的格入库写 NULL 不写 0.0（写侧保证）：四形状逐条判 | `./reproduce.sh` |
| `python3 checks/refresh_preserve_negative_control.py` | 一轮完整 refresh 只动自己的行：三行探针跑两次逐字未变、第二次净改动 0 行 | `./reproduce.sh` |
| `python3 checks/refresh_guard_differential_control.py` | 「读不到输入就不删」这条 guard 在承重（差分）：干净 clone 里带 guard 丢 0 行，去掉 guard 丢数百行 | `./reproduce.sh` |
| `python3 checks/mres_prefix_delete_negative_control.py` | 任何 ingester 的 REFRESH 删除都不碰别人的行：探针行跑完两次 migrate 仍在、`mres/%` 行一条不丢 | `./reproduce.sh`（输入不可得时该行 SKIP） |
| `python3 checks/superseded_pointer_negative_control.py` | `superseded_by` 是指针：悬空指针 → `db_check` 变红并点名 | `./reproduce.sh` |
| `python3 checks/superseded_filter_negative_control.py` | 报告必须过滤被取代的行：去掉过滤 → 被取代的行以第二个分数回到表里 | `./reproduce.sh` |
| `python3 checks/py_corpus_regrade_check.py` | 已入库的 py 语料取代行与 a14 的改分清单逐条一致、旧行未被改写 | `./reproduce.sh` |
| `python3 checks/backup_wal_negative_control.py` | WAL 里有未检查点数据时，`migrate_db.numbered_backup()` 的备份是变更前状态 | 按需（`docs/subprojects/i02-测量基础设施/RESULT.md` 的 `producer:` 行） |
| `python3 checks/m165_ingest_negative_control.py` | m165（厂商推荐采样 R1）按五个采样量区分身份入库，skip ledger 可见 | 按需（同上的 `producer:` 行，与 `migrate_db.py` 末尾的 `== ingest skips ==` 配对） |
| `python3 checks/vendor_arm_negative_control.py` | `vendor-recommended` 臂的五个采样量真的进协议串，且不与 greedy 合并 | 按需（a06 的 `vendor-effect-control-open` 与 i02 `RESULT.md` 的 `producer:` 行） |
| `python3 checks/variant_ingest_negative_control.py` | 两份只差 `presence_penalty` 的 variant 面板入库为两格，不与 greedy 合并 | 按需（仓库里没有调用点，也没有节点点名——这是它的现状，登记在这里而不是假装它被接了） |

不属于这里的检查：`docs/check_docs.py` 属于文档层（在 `docs/` 下），`report_inputs/build_eval_status.py --check`
属于输入本身（在 `report_inputs/` 下）。
