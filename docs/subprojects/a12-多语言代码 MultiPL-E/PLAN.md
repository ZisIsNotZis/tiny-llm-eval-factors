# a12 多语言代码 MultiPL-E — 计划

计划层的唯一 home。目标 / 用途 / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a12 行定义，本文件不复述；本文件只写里程碑、工作包、状态与派工。

## 里程碑：研究结束

- 终点状态：a12 的 AC 全部有可复算证据，未测的格都带着理由登记，报告里的每个 model×language 格都能追到落盘产物。
- done 判据：`python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"` 退出 0（谱系、全 Exception、协议设置、提示集哈希、报告行归属五项全绿，当前已满足），`bash "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_negative_control.sh"` 退出 0（两处篡改都被拒），RESULT.md 的覆盖登记把每个空格归入「已测」或「显式未测 + 理由」，且审计 `[8]` 段报告 0 个标准表带 cpp+py 池化列（当前 0 个池化、8 个已拆）。
- 未结的 `WP8` 不是 done 判据的一部分：它登记一个报告表示缺陷（3 个被同一行标签遮住的格），修法在 i02 的报告代码里。
- 只有这一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`、`WP2`、`WP3`、`WP4`。
- 已落地但未提交（i02 在工作树里，HEAD 上还没有）：`WP7` 拆列、`WP9` 题量，见 `RESULT.md`「HEAD 的报告有两处缺陷」与两份按 revision 命名的捕获。
- 在办：`WP8`（逐语言表 3 个格被同一行标签遮住）归 i02，a12 只提供 `[10]` 段的证据；`WP5` 由 GPU worker 在跑（见 WP5 行），入库步骤尚未做，接手者按该行命令继续。`WP6` 的首轮结论是 ACCEPT WITH NOTES + 3 个 P1，已修完（见「复核整改」）。
- 下一个派给谁：`WP8` 与 `WP5` 的产物→a12 复核；其余无待派工作。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | a12 编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；迁移后的 `result.yaml` 已删除；每条事实带证据与复算命令；提交在 main | — | 1 会话 | 完成 |
| WP2 单元格谱系审计 | a12 编排者 | `mpl_cell_audit.py` 对库中 248 个格给出「已评分 244 全部追溯、0 未追溯、无全 Exception 格带分数」，退出 0 | WP1 | 0.5 CPU 时 | 完成 |
| WP3 覆盖缺口登记 | a12 编排者 | 54 个模型 × 6 语言的矩阵、4 个 NULL 格、未测格的理由全部写进 `RESULT.md` | WP2 | 0.5 CPU 时 | 完成 |
| WP4 协议 / 语言受控审计 | a12 编排者（语言池化的改法落在报告代码，已由 meta 裁决） | 报告的逐语言表行键 =(模型, 协议) 有代码与数据证据；标准列只取 canonical raw-greedy 协议；cpp+py 均值与两语言各自排序的不一致率有具体数 | WP2 | 0.5 CPU 时 | 完成 |
| WP7 报告标准列拆成 C++ / Python 两列 | i02 | 标准表 11→12 列、轴 A/B/C 各多一条 series；重生成 `report.html` 后无池化列 | WP4 裁决 A | 一次报告改动 | 工作树已落地、未提交（`[8]`：0 池化 / 8 已拆）；HEAD 仍是池化 |
| WP9 报告不得给格编题数，也不能让探针格看起来像满格 | i02 | 有 n 的格印出的题量等于该语言的满格题数（java 158 / rs 155）；m30 的六格是 60 题探针，题量必须印出来或被显式标成探针——「没有 n 就不印 n」不算修好，因为它让 60 题的结果读成一个 161 题的 0；`[7]` 的「因 n 缺失而跳过」计数必须为 0，或逐个对应已标注的探针 | `[7]` 的 HEAD 捕获与工作树捕获里的跳过计数（当前 6 个） | 一次报告改动 | 工作树把 32 格改对、未提交；6 个探针格仍未标出 |
| WP8 逐语言表的标签要带上被采样的一维 | i02 | m31 的 `top_k` 格不再与 m27 的 `t0.3` 格撞成同一行；库中 192 个 (模型, 协议串, 语言) 键全部能被单独渲染 | `[10]` 的证据 | 一次报告改动 | 待派 |
| WP5 补测 gemma-4-12b 的 chat cpp 两格 | GPU worker（meta 已派） | Q2/Q3 两格以 `mpl-chat-nothink-greedy-768`（`ctx=2048`、`--jinja`）入库并留下 `_eval.json`；审计仍退出 0；12b 首次有同协议 cpp+py 对 | 一个 GPU 槽（`bash .wrapup/gpu_locked.sh`）；提示集用 `.wrapup/prompts` 不许重生成 | ≤15 GPU 分钟（m161 实测 7 格 39 分钟） | 在跑（detached，父进程退出后仍继续）：driver pid `2570701` = `bash .wrapup/gpu_locked.sh bash .wrapup/run_m163_chat_cpp_12b.sh`，其 flock 外壳 pid `2559808` 持 `/tmp/llama_gpu.lock`，llama-server 在 tcp/8091 载 Q2。log `.wrapup/m163.log`；两格产物 `mres/m163-g12b-q{2,3}-cpp-chat.jsonl` + `_eval.json`，汇总 `.wrapup/m163_summary.jsonl`。结果 pending：入库与报告尚未做；两格落盘后 `python3 migrate_db.py`（自带 `bakN` 备份）→ `python3 make_report.py` → 审计。 |
| WP6 独立复核 | fresh-context reviewer（meta 已派） | 对本目录三份文档与审计输出给裁决，指出证据缺口；reviewer 的结论取代本人的自评 | WP1–WP4 | 一次复核 | 已派，待结论 |

## 已裁决：标准列拆成 C++ / Python 两列（选项 A）

- 裁决：meta 取选项 A —— 标准列的「多语言代码」格拆成 C++ 与 Python 两列，不再把 cpp+py 加权成一个数。
- 理由：51 个同有 cpp+py 的模型里，两语言对 169/1275 对模型（13.3%）给出相反的次序，py−cpp 从 −0.2671 到 +0.1863（中位数 +0.0186，|差值|>0.05 的 29 个），所以均值会掩盖语言层面的符号反转；而「标准列不跨语言或协议池化」是 AC 里的规则，不是可选项。
- 拒绝 B（只留 Python）：丢掉 cpp 一整维，覆盖表里 cpp 的 52 个格白测。
- 拒绝 C（保留均值 + 标注）：只是把违规写清楚，均值本身仍会让读者把两个语言当成一个结论。
- 落地：i02 已改 `.wrapup/mktables.py` 的 `BENCH`/`query_cells_by` 与 `make_report.py` 的 LBL，标准表现在各带「多语言代码 C++」「多语言代码 Python」两列；审计 `[8]` 段现在报告 0 个池化表、8 个已拆表。`load_standard` 取 MultiPL-E 时仍只读 `protocol='multipl-e-raw-greedy-768'`。
- 复算：`python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"` 的 `[5]` 段。

## 复核整改（首轮 WP6：ACCEPT WITH NOTES + 3 个 P1，按 meta 口径不接受）

- P1-a 证据未绑定版本：审计现在在输出首行打印 `git HEAD`、脚本自身 sha256、完整命令与脏路径，捕获存到 `evidence/`，文件名带短 revision；`.tmp` 里的旧捕获作废。
- P1-b NULL 的证据是假的：`m51_summary.jsonl`/`m54_summary.jsonl` 对这四格记的是 `"score": 0.0`，所以 summary 不能当 NULL 的证据；`RESULT.md` 改成引 per-item eval 的状态直方图（`pan-gemma12b-q{2,3}-{js,rb}_eval.json` 各 `{'Exception': 161}`），审计 `[4]` 段直接打印这个配对。
- P1-c 审计没有负控能力：`[7]` 现在保留报告行的协议标签并把标签映射回库中该 (模型, 语言) 的协议，再比对值与题量；`mpl_negative_control.sh` 制造两处篡改（把 chat 格的值挪进 raw 行、把 `(161)` 改成 `(160)`），干净报告退出 0、两处篡改各退出 1。
- P1-c 的副产品：新的题量比对在 HEAD 的报告上抓到 32 个格印着 `(161)`，而这些格的产物题量是 java 158 / rs 155 / m30 探针 60——登记为 `WP9`（i02 工作树已修）。这一条正好证明检查会失败，不是空转。
- 第二遍复核（3 个 P1 全清）留下 4 条 note，已落：`[9]` 改成全串比对（含 `;` 字段）并把 m6b 那处不一致登记为显式例外；`WP9` 的 AC 收紧为「探针格必须印题量或被标注」并让 `[7]` 打印跳过计数；566/1275 的撤回写进 `RESULT.md`（旧数作废 + 错因 + 新口径，三种口径 169/182/177 都由本人重算）；`[7]`/`[9]`/`[10]` 的清单上限改为 200 行，HEAD 的 32 行现在全部在捕获里。
- P2：删掉随拆列失效的两句话；改正「java 格没有 per-item eval」的说法（`pan-gemma12b-q2-java_eval.json` 存在，158/158 `SyntaxError`）；把 `AGENTS.md` 的规则收窄成「全 Exception 记 NULL，跑过但没通过记 0 并标注成因」；把 `(语言, 通过数, 题数)` 配对的局限写进审计打印与 `RESULT.md`。

## 非目标

- 不为 js / java / rs / rb 补 chat 协议格：那是 4 语言 × 6 模型的 24 格，超出 9% GPU 份额，且这几个语言的判分有效性还没有 i01 的审计。
- 不改 m30-kv-ctx 的 6 个 0.0 格：它们属于 a05 的 KV 轴，改值会改 a05 的结论；a12 只登记缺陷（`RESULT.md`「8 个 0.0 格」）。
- 不改其他子项目目录、不改 `docs/plan/subprojects.md`、不重跑历史面板的旧后处理分数。
- 不重生成提示集：`.wrapup/prompts` 与 `SHA256SUMS` 是唯一来源。

## 已记录的判断（本会话自行决定）

- 补测先做 gemma-4-12b 的 chat cpp 两格，而不是先补语言维度：它把 12b 从「任何协议下都没有 cpp+py 对」变成「同一协议下有对」，是覆盖表里唯一能用一个协议内的两格填补的模型。
- 谱系审计的判据写成「panel summary 命中，或按 (语言, 通过数, 题数) 命中的 per-item eval 文件」，因为有两格的库值是修正后处理重判出来的（summary 里留的是旧判分值），把 eval 文件当第二等证据而不是降级。
- 报告里的 4 处引用（`docs/result/result.yaml::res5/res17b/res22/res24`）指向 meta 迁移后已不存在的路径，属报告代码的死引用；a12 不改报告代码，登记给 meta（见 `RESULT.md`「迁移到 Markdown 的后果与死引用」）。

## 派工与资源

- GPU：占 4 周周期的 9%，全局串行，任何 GPU 任务必须在 `bash .wrapup/gpu_locked.sh` 下跑，一次一个。
- CPU：5%；本目录的审计脚本只读数据库，秒级。
- 任何入库走 `migrate_db.py`，改库前做编号备份，改完跑完整性与洁净检查（见 `AGENTS.md`）。
