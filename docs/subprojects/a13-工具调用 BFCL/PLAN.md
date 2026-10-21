# a13 工具调用 BFCL — 计划

计划层的唯一 home。目标 / 用途 / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a13 行定义，本文件不复述；本文件只写里程碑、工作包、状态与派工。
结果与证据在 `RESULT.md`；孙 agent 的窄规则在 `AGENTS.md`。

## 里程碑：研究结束

- 终点状态：注册表给的 AC 同时成立——(1) **类别覆盖表**（哪族 × 哪协议 × 哪类别有数、哪格没有，缺的写明是未测还是已测但按规则排除）；(2) **多轮跨家族覆盖或有界结论**（`plan4`）；并回答本轴必须回答的四问：逐类别列支持什么、没有唯一总分时跨模型比较还剩什么、固定协议（native tools / 单轮 vs 多轮）如何改变排序、单轮换官方判分器后哪些已报数字会动。
- done 判据：`python3 "docs/subprojects/a13-工具调用 BFCL/audits/run_all.py"` 退出 0（覆盖表、判分器对照、聚合口径、排序稳定性四份证据各就位且每份带可打红的负控），且 `RESULT.md` 里每条结论有一行陈述 + 证据路径 + 复现命令。
- 只有一个里程碑：它是用户同步点，之前不再切分。
- **不得写 BFCL 总分**：任何跨协议、跨类别的单一数字都不进结论（`docs/plan/subprojects.md` 的资源与政策 + i01 `res27`/`res30` 已判定不存在唯一总分）。

## 当前状态

- 已完成：`WP1`（文档归位）。
- 在办：`WP2`（单轮官方 vs 自研判分器对照），接着 `WP3`。
- **派工形态**：本会话只有 read/grep/find/ls/bash/write/edit 工具，**没有派孙工具**，所以 `WP2`–`WP5` 由编排者自己执行（与 i01 同样的处境）。`WP6` 的独立复核因此必须由 meta 派 fresh-context reviewer，不得自评通过。
- 下一个派给谁：`WP3` → `WP4`（多轮的 GPU 臂）→ meta 派 `WP6` 复核。
- GPU：无本轴任务在跑。`WP4` 起跑前必须 `nvidia-smi` 记录空闲显存，并在 `.wrapup/gpu_locked.sh` 下运行。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | a13 编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`plan.yaml` 的 `plan4` 已迁入并删除该 yaml；`git grep -n 'a13-工具调用 BFCL/plan.yaml'` 无输出；按路径提交在 main | — | 1 会话 | **完成** |
| WP2 单轮：官方 AST checker vs 自研匹配器 | a13 编排者 | 用同一批落盘预测重判 15 个存活 cell，逐 (模型, 类别) 给出「自研准确率 / 官方准确率 / 向上翻 / 向下翻」，并给出每条已知会动的已报数字；负控两侧都观测到（正确调用判对、错名/缺参/多参/布尔数字混用各判错）；缺输入 exit≠0 | WP1 | ≤90 CPU 分钟 | 未开始 |
| WP3 覆盖表 + 聚合口径 + 排序稳定性 | a13 编排者 | 出 `audits/coverage.md`：族×协议×类别矩阵 + 每格 n 的来源；micro/macro 两个口径在单轮面板上的复算值与面板 summary 的 `score` 对齐（或给出为何对不齐）；同一模型跨类别排序的逆序数；native vs prompt 协议下排序是否变；缺输入 exit≠0 | WP1 | ≤90 CPU 分钟 | 未开始 |
| WP4 多轮跨家族（`plan4`） | a13 编排者 | 跨家族受控对成立：同一 handler、同一 ctx、同一 temp/max_tokens 下两个不同族的模型各跑一次 `multi_turn_base`，并给出该配置下多轮的重复地板（同配置第 2 次）；做不到就写有界结论 + 代价 | WP3（先知道缺哪族）、GPU | ≤60 GPU 分钟（2 臂 × ~12 分钟 + 起停） | 未开始 |
| WP5 多轮判分器的可执行负控 | a13 编排者 | 用官方 `multi_turn_checker` 对构造的坏实例判错、对正确实例判对，两侧都观测到；`Failed to decode the model response` 通道的方向与幅度有实测 | WP2 | ≤60 CPU 分钟 | 未开始 |
| WP6 独立复核 | fresh-context reviewer（meta 派） | 每包一份裁决（接受 / 接受带注解 / 不接受），阻塞项带位置与复现 | 对应包完成 | ≤30 CPU 分钟/份 | 待派 |
| WP7 `n_items` 回填交接 | a13 编排者 → i02 的 `migrate_db.py` | 多轮 24 行的 `n_items` 有可导出来源（200/类别）且来源被写成一行证据；回填本身走 i02 的摄入路径，动手前编号备份 | WP3 | ≤30 CPU 分钟 | 未开始 |

调度原则：`WP2`/`WP3` 全 CPU、无 GPU、互相独立，先并行；`WP4` 要 GPU 且要等锁，放在 `WP3` 之后；`WP5` 复用 `WP2` 的判分器加载装置。

## WP4 的形状（迁入的 `plan4` 与本轴对它的修正）

原节点 `plan4`（自 `docs/plan/plan.yaml` 迁入，该 yaml 已删）：

> 假设 B3（跨家族多轮）：BFCL 多轮只在一个锚点（Qwen3.5-2B）跑过；扩到 granite/gemma/MoE 锚点，及其它多轮类别（miss_func / miss_param / long_context）。

实测后这个描述已不准确（`RESULT.md::res9`）：多轮已有 10 个模型、4 个族，granite 与 MoE 都跑过 `multi_turn_base`，`long_context` / `miss_func` / `miss_param` 也各有 3–4 个模型。**真正缺的是 gemma 族（0 行）**；而 `RESULT.md::res8` 又说不同族的行用了不同 handler，所以直接补一行 gemma 只会把「族」与「模板」再混一次。

所以 WP4 改成受控对加地板：

| 臂 | 模型 | handler | cats | ctx | 目的 |
|---|---|---|---|---|---|
| G | `gemma-4-E2B-it-UD-Q3_K_XL.gguf` | `Qwen/Qwen3-1.7B-FC`（与 Qwen 2B 锛点同一 handler） | `multi_turn_base` | 98304 | 跨族受控对：与 m9 的 Qwen3.5-2B-Q3 = 0.185 对照 |
| Q | `Qwen3.5-2B-UD-Q3_K_XL.gguf` | 同上 | `multi_turn_base` | 98304 | 同配置第二次，给多轮重复地板（res7 的那个 0.095 vs 0.11 就在这里裁决） |

判定规则（先写死）：

1. Q 臂的两次值不同 → 多轮在确定性解码下**不**逐题可复现，地板是实测的非零值；此后任何多轮跨模型差必须大于它才能读。
2. Q 臂两次相同 → 多轮地板也是 0，`RESULT.md::res7` 的 0.095/0.11 只能归给未记录的输入差（不是噪声）。
3. G 臂跑完（无论分数高低）→ gemma 族多轮覆盖成立；如果 G 臂整类 0 且日志出现模板/解析失败（`Failed to decode the model response`），那写「模板不兼容」而不是「gemma 不会工具调用」，并退回有界结论。

AC：两个 `score/*/multi_turn/*_score.json` 台账新行 + 两份 `.wrapup/m*.log` + 一行结论回 `RESULT.md`；`plan4` 随之关闭。预算：每臂 200 题，参 m12 的 8B 实测 ~11:40 生成 + ~10 s 判分；E2B/2B 估 ≤12 分钟/臂。

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
