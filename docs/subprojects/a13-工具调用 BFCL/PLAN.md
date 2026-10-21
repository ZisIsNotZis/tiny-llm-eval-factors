# a13 工具调用 BFCL — 计划

计划层的唯一 home。目标 / 用途 / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a13 行定义，本文件不复述；本文件只写里程碑、工作包、状态与派工。
结果与证据在 `RESULT.md`；孙 agent 的窄规则在 `AGENTS.md`。

## 里程碑：研究结束

- 终点状态：注册表给的 AC 同时成立——(1) **类别覆盖表**（哪族 × 哪协议 × 哪类别有数、哪格没有，缺的写明是未测还是已测但按规则排除）；(2) **多轮跨家族覆盖或有界结论**（`plan4`）；并回答本轴必须回答的四问：逐类别列支持什么、没有唯一总分时跨模型比较还剩什么、固定协议（native tools / 单轮 vs 多轮）如何改变排序、单轮换官方判分器后哪些已报数字会动。
- done 判据：`python3 "docs/subprojects/a13-工具调用 BFCL/audits/run_all.py"` 退出 0（覆盖表、判分器对照、聚合口径、排序稳定性四份证据各就位且每份带可打红的负控），且 `RESULT.md` 里每条结论有一行陈述 + 证据路径 + 复现命令。
- 只有一个里程碑：它是用户同步点，之前不再切分。
- **不得写 BFCL 总分**：任何跨协议、跨类别的单一数字都不进结论（`docs/plan/subprojects.md` 的资源与政策 + i01 `res27`/`res30` 已判定不存在唯一总分）。

## 当前状态

- 已完成：`WP1`（文档归位）、`WP2`（单轮判分器替换，res11）、`WP3`（覆盖/聚合/排序，res1/res3/res9/res11/res12）、`WP7`（n_items 回填，res2/res4）、`WP8`（官方分入库，res13）。
- 在办：无。`WP4` 的有界结论已达成，2×2 受控对不买（见上表）；`WP5` 已完成（res14）。剩余只有 `WP6`（meta 派 fresh-context reviewer）。
- **判定入口**：`python3 "docs/subprojects/a13-工具调用 BFCL/audits/run_all.py"`（实跑 `EXIT=0`），它就是里程碑 done 判据；行数/哈希只作快照打印，判据是「库与证据一致」的关系。
- **终审 ACCEPT WITH NOTES 的七处已改（待复审）**：①`official_vs_homegrown.py` 改成「先校验后写证据」（写 tmp + `os.replace`，绑定漂移时 exit 3 且证据字节不变）、`run_all.py` 把子检查崩溃记 FAIL 不抛异常；②`res14` 的边界按实测重写（类别被 entry id 覆盖、`long_context` 支路未触及、`miss_func`/`miss_param` 各有 203/934 空 GT 轮被 `continue`、`multi_turn_irrelevance_checker` 无调用点）；③`res12` 加 ctx/`-partial` 条件，跨族受控只剩 base@98304 三行；④`未测#3` 改为已测并写残留；⑤`res9` 计数改为 base 11 行/10 模型、long_context 7 行/4 模型，审计表头改「5 non-live」；⑥「不可分」补上 0.0125 摆动的推导并标明 macro/micro；⑦新增 `res15` 类别覆盖表，把 7/11 模型与 prompt 的 `live_*` 缺口明确写成「未测」而非「协议不产出」。
- **结论层已就位**：`RESULT.md` 开头三句（单轮 / 多轮 / 换判分器后改变的具体判断），每条指回 res11–res13，供报告第十四节直接引用；其中两条是给报告文本的输入（§14 的「micro 不可从库复算」已过时；表内数值已是官方 checker 值、行标签带判分器身份）。
- **AC 状态**：类别覆盖表（res1/res9）+ 多轮跨家族有界结论（res12）都成立；本轴四问分别落在 res11（换判分器动哪些列）、res12（协议与 handler 如何改变可比性）、res3（逐类别列支持什么、无唯一总分）、res13（入库后的当前值）。
- **派工形态**：本会话只有 read/grep/find/ls/bash/write/edit 工具，**没有派孙工具**，所以 `WP2`–`WP5` 由编排者自己执行（与 i01 同样的处境）。`WP6` 的独立复核因此必须由 meta 派 fresh-context reviewer，不得自评通过。
- 下一个派给谁：`WP3` → `WP4`（多轮的 GPU 臂）→ meta 派 `WP6` 复核。
- GPU：无本轴任务在跑。`WP4` 起跑前必须 `nvidia-smi` 记录空闲显存，并在 `.wrapup/gpu_locked.sh` 下运行。
- **`WP4` 的 2×2 受控对：已定价、未测、不买**（2026-10-21 记录）。价格与做法留在下表与 `RESULT.md::res12`：4 臂 × 200 题 ≈ 50 GPU 分钟（参 m12 的 8B 实测 11:40/臂 + 四次加载），买的是「跨族可比」。不买的理由：AC 是「跨家族覆盖**或**有界结论」，有界结论已达成；GPU 上 a01 的 12B MMLU 与 a06 的厂商臂剩余五格在排队。谁要买，按 WP4 表逐臂跑 `bash .wrapup/gpu_locked.sh bash .wrapup/run_m9_panel.sh <tag> <gguf> <handler> multi_turn_base`（`SMOKE=1` 先要一次真实 completion）。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | a13 编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`plan.yaml` 的 `plan4` 已迁入并删除该 yaml；`git grep -n 'a13-工具调用 BFCL/plan.yaml'` 无输出；按路径提交在 main | — | 1 会话 | **完成** |
| WP2 单轮：官方 AST checker vs 自研匹配器 | a13 编排者 | 用同一批落盘预测重判 15 个存活 cell，逐 (模型, 类别) 给出「自研准确率 / 官方准确率 / 向上翻 / 向下翻」，并给出每条已知会动的已报数字；负控两侧都观测到（正确调用判对、错名/缺参/多参/布尔数字混用各判错）；缺输入 exit≠0 | WP1 | ≤90 CPU 分钟 | **完成**（res11：60 可比格全上行，中位 +0.04~+0.33，34 上行 / 2788 下行，2534 条是 missing_optional；4/55 对逆序） |
| WP3 覆盖表 + 聚合口径 + 排序稳定性 | a13 编排者 | 族×协议×类别矩阵 + 每格 n 的来源；micro/macro 复算值与面板 summary 对齐（或说明为何对不齐）；跨类别排序逆序数；native vs prompt 协议下排序是否变 | WP1 | ≤90 CPU 分钟 | **完成**（res1/res3/res9 覆盖与聚合、res11 排序 4/55 逆序、res12 按 handler 的可比性分组）；残留：native vs prompt 的排序对照只有库里 20 行、无预测可重判 |
| WP4 多轮跨家族（`plan4`） | a13 编排者 | **有界结论已达**：跨族差与模板差不可分离、库内只有 4 个 handler 组内可比、granite 无对照、gemma 补了也只补覆盖（res12）。可选的 2×2 受控对**已定价、未测**：4 臂 × 200 题 ≈ 50 GPU 分钟，买的是「跨族可比」，现不买（GPU 排队给 a01 的 12B MMLU 与 a06 剩余五格） | WP3、GPU | 50 GPU 分钟（未授权） | **有界结论达成** |
| WP5 多轮判分器的可执行负控 | a13 编排者 | 用官方 `multi_turn_checker` 对构造的坏实例判错、对正确实例判对，两侧都观测到 | WP2 | ≤60 CPU 分钟 | **完成**（res14：正控 PASS，改错/坏格式/空答三条全 FAIL；A 与 B 的 `error_type` 相同，所以失败原因不可按 error_type 归因） |
| WP6 独立复核 | fresh-context reviewer（meta 派） | 每包一份裁决（接受 / 接受带注解 / 不接受），阻塞项带位置与复现 | 对应包完成 | ≤30 CPU 分钟/份 | 待派 |
| WP8 单轮官方分入库（取代自研分） | a13 编排者 | 79 格 `_score` 换官方值、协议串区分两套判分器、编号备份 + `integrity_check` + `db_check` PASS、重跑幂等、REFRESH 收敛在库副本上实测；列级新旧对照与「4/55 逆序」的复算命令进 `RESULT.md` | WP2 | ≤30 CPU 分钟 | **完成**（res13：旧值 retracted） |
| WP7 `n_items` 回填 | a13 编排者 → `migrations/backfill_n_items.py` | `bfcl%` 的 NULL 从 29 降到 15，剩下的每一行有写定的原因；编号备份 + integrity_check ok + 第二次 dry-run 幂等 0 行 | WP3 | ≤30 CPU 分钟 | **完成**（res2/res4：14 行回填，剩 15 行多轮因台账只留最后一次运行而不可溯源） |

调度原则：`WP2`/`WP3` 全 CPU、无 GPU、互相独立，先并行；`WP4` 要 GPU 且要等锁，放在 `WP3` 之后；`WP5` 复用 `WP2` 的判分器加载装置。

## WP4 的形状（迁入的 `plan4` 与本轴对它的修正）

原节点 `plan4`（自 `docs/plan/plan.yaml` 迁入，该 yaml 已删）：

> 假设 B3（跨家族多轮）：BFCL 多轮只在一个锚点（Qwen3.5-2B）跑过；扩到 granite/gemma/MoE 锚点，及其它多轮类别（miss_func / miss_param / long_context）。

这个前提**已被数据否掉，不再保留**（`RESULT.md::res9`）：多轮已有 10 个模型、4 个族，`multi_turn_base` 9 个模型，`long_context` / `miss_func` / `miss_param` 各 3–4 个。真正的问题不是覆盖，而是**可比**（`RESULT.md::res12`）：每个族、甚至每个 Qwen 尺寸都跑在不同的官方 handler 下，handler 决定多轮 prompt 的模板与响应解析，所以这一列的跨族差 = 族差 + 模板差，分不开。

所以 WP4 改成 2 模型 × 2 handler 的受控对，外加一次同配置重复：

| 臂 | 模型 | handler | cats | ctx | 目的 |
|---|---|---|---|---|---|
| A1 | `Qwen3.5-2B-UD-Q3_K_XL.gguf` | `Qwen/Qwen3-1.7B-FC`（自家模板） | `multi_turn_base` | 98304 | 模板内基线，且是重复地板的第一跑 |
| A2 | 同上 | `ibm-granite/granite-4.0-350m`（外来模板） | `multi_turn_base` | 98304 | 同模型换模板 → **模板效应** |
| B1 | `gemma-4-E2B-it-UD-Q3_K_XL.gguf` | `Qwen/Qwen3-1.7B-FC` | `multi_turn_base` | 98304 | 补 gemma 覆盖 + 与 A1 同模板 → **族效应** |
| B2 | 同上 | `ibm-granite/granite-4.0-350m` | `multi_turn_base` | 98304 | 同模型换模板 → 模板效应的第二点 |

（A1 的对照是库里已有的 m9 = 0.185，同一 handler 同一 ctx；若 A1 重跑得 0.185，则多轮地板 = 0，res7 的 `0.095` vs `0.11` 只能归给未记录的输入差。）

判定规则（先写死）：

1. A1 两次不同 → 多轮在确定性解码下**不**逐题可复现，地板是实测非零值；此后任何多轮跨模型差必须大于它才能读。
2. A1 两次相同 → 地板也是 0，res7 的 0.095/0.11 归给未记录的输入差（不是噪声）。
3. A1 与 A2 的差 = 模板效应；B1 与 A1 的差 = 族效应（同模板）；B1 与 B2 的差是模板效应的复现。三者同时给出才算「分开」，否则只报「差存在且未分离」。
4. 任一臂整类 0 且日志出现 `Failed to decode the model response` → 写「模板不兼容」，不写「该模型不会工具调用」。

AC：`score/*/multi_turn/*_score.json` 出现 4 条新汇总行 + 4 份 `.wrapup/m*.log` + 一行三分量结论进 `RESULT.md`；`plan4` 随之关闭。预算：4 臂 × 200 题，参 m12 的 8B 实测 11:40 生成 + ~10 s 判分；E2B/2B 量级估 ≤12 分钟/臂，加四次加载 ≈ **50 GPU 分钟**，走 `gpu_locked.sh`。`WP5`（多轮判分器负控）复用这四臂的 `_score.json` 逐题记录，不必另跑。

## WP2 的形状（判分器替换的度量）

同一批记录（`.wrapup/mres/m4-*.jsonl` 11 个 × 1240 条、`m8-*.jsonl` 4 个 × 2251 条）过两条判分路径：自研侧 import `.wrapup/bfcl_run.py` 的 `call_ok`/`arg_ok`；官方侧用 bundled `bfcl_eval.eval_checker.ast_eval.ast_checker`（`bfclenv` 解释器）。交付：

- 逐 (文件, 类别) 的自研准确率、官方准确率、两向上翻条数；只有 `simple_python / multiple / parallel / parallel_multiple / live_simple / live_multiple / live_parallel / live_parallel_multiple` 八类可对照，`irrelevance / live_irrelevance / live_relevance` 三类无 `possible_answer`，写不可对照（`RESULT.md::res6`）。
- 把差异绑回已报数字：库里受影响的只有那 15 个 cell 的单轮行；prompt 协议 20 行无法重判，写明。
- 负控：构造 50 条已知对/错的预测（正确调用、错函数名、缺必需参数、多一个乱参数、布尔 vs 1、数字 vs 字符串），两套判分器各跑一次，两侧都看得到。


## 边界的固定口径（不得漂移）

1. **不跨协议、不跨类别池化**：`bfcl-native-tools-nothink-greedy`、`bfcl-prompt-nothink-greedy`、`bfcl-official-multiturn-temp0` 是三个测量，任何平均数只在同一协议内取。
2. **截断的 run 不与完整 run 可比**：`--limit` 出来的格只能当抽样，不能当类别分数；`-partial` 协议同理。
3. **`n_items` NULL 是声明的缺失，不是 0**；已回填的值是 i02 派生出来的引用，不是测量（见 `RESULT.md`）。
4. **确定性解码下重复地板 = 0**（i01 `res32`）只对「输入相同、单轮、`--limit 40`」这一格成立；多轮与全类别的地板本次自己测（`WP4`）。
5. `report.html` 是生成物，永不手改；`make_report.py`/`mktables.py` 不是我改的对象。

## 与别的子项目的关系

- 依赖 `i01`：本轴的判分审计（`audits/bfcl.md`、`bfcl_audit.py`）由 i01 做出，`res27`/`res30` 是准入前提。本轴发现 i01 那两条的两个具体缺口（存活预测文件被漏检、多轮其实有逐题产物），修正在 `RESULT.md` 里以「对 i01 结论的修正」单列，不修改 i01 目录。
- 依赖 `i02`：`n_items` 回填与报告渲染归 i02；本轴只提供可导出来源，不直接写库。
