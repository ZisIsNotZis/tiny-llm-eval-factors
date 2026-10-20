# a02 模型规模 — 计划

计划层的唯一 home。goal / purpose / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a02 行定义，本文件不复述；本文件只写里程碑、工作包、状态与派工。
结果与证据在 `RESULT.md`；孙 agent 的窄规则在 `AGENTS.md`；可执行的复算脚本在 `analysis/`。

## 里程碑：研究结束

- 终点状态：注册表给的两条 AC 同时有可复算证据——(1) MoE 的「总参 + 激活参」双变量回归**成立**，或**明确不可测**并给出不可识别的证据（相关 / VIF / 设计矩阵），不允许交一个识别不出来的双变量拟合；(2) 每个家族的规模曲线可复算（同家族、同配方、同一基准，逐格 `n_items` 做分母，不跨语言不跨协议）。
- done 判据：`python3 "docs/subprojects/a02-模型规模/analysis/run_all.py"` 退出 0（逐条打印预期是否成立），且 `RESULT.md` 里每个数字后面都有一条别人能重跑的命令。
- 只有一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`（文档归位）、`WP2`（规模这一列归位：7 条取数通道 + 逐族可用性裁决）、`WP3`（plan5 判为**不可识别**，理由与最小补测已入 `RESULT.md`）、`WP4`（63 条同族同配方规模曲线，逐格 `n_items` + Wilson 区间）、`WP5`（同激活参数下 MoE 的等效稠密规模）、`WP6`（验收入口 `analysis/run_all.py`：5 个脚本 67 条断言 + 负控，5/5 绿）。
- 复核返修（ACCEPT WITH NOTES）已处理：`size-null` 措辞、`169 组 / 76 个文件` 口径、GLM-4.7-Flash 8 个文件、永真断言改成真检查、`thin_curves` 记录 265 个无曲线组、真值 fixture 让检查不依赖 `/home/z/hf`。
- 在办：`WP7` 独立复核（等 meta 派 fresh-context reviewer；本层没有派孙工具，不能自评通过）。
- 已回收的登记：plan5 已在 `WP3` 裁决（`RESULT.md::moe-design-not-identified`），不再作为未解问题挂着。
- 下一个派给谁：`WP4` 由本层编排者做；`WP4` 出曲线后 `WP5`（同激活参数下 dense/MoE 的位置）与 `WP6`（收口与报告建议文本）由本层编排者接着做，最后请 meta 派 fresh-context reviewer 做 `WP7`。
- 本层没有派孙工具（运行时不提供 subagent 接口），所以实现与分析由编排者自己执行；独立复核必须由 meta 派 fresh-context reviewer，不得自评通过。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | 本层编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`plan.yaml`/`result.yaml` 已迁入并删除；`python3 docs/check_docs.py` 退出 0 且 a02 的事实被解析（`shape not parsed` 列表里不出现 a02 的文件）；提交在 main 且按路径点名 | — | 1 会话 | **完成** |
| WP2 「规模」这一列到底是谁给的（X 的归位） | 本层编排者 | 对库里每个 model 文件给出四项并逐项与库对照：GGUF 张量元素求和得到的真参数量、文件名 size token、`2 × 文件字节数` 回退值、库里的 `__size`；输出一张「每一行 `__size` 来自哪条通道」的表 + 每通道行数；并给出「同一 model 文件在 `__size` 上出现几个不同值」的清单（>1 即该通道与量化耦合） | WP1 | ≤40 CPU 分钟 | **完成**（`analysis/size_provenance.py` 7 条通道、`other`=0、3233 行全部归位；`analysis/size_ladder.py` 给出逐族三个候选 X 的可用性；真值做成入库 fixture（`analysis/fixtures/gguf_truth.json`，76 个模型文件）使检查不依赖 `/home/z/hf`；结论在 `RESULT.md::size-channel-inventory`…`::report-size-claims-audit`） |
| WP3 plan5 双变量回归的可识别性 | 本层编排者 | 在 WP2 判为「`__size` 是真参数」的行集上，给出 `log(总参)` 与 `log(激活参)` 的相关系数、VIF、设计矩阵非对角结构的计数（同总参不同激活的对数、同激活不同总参的对数）；结论必须是「可识别并给出系数+区间」或「不可识别并写明缺哪类受控对」，二者之一 | WP2 | ≤40 CPU 分钟 | **完成**：判为**不可识别**——稠密点上激活≡总参（去掉 MoE 后秩亏），MoE 内部总参系数 +0.122±0.141 与 0 不可分；被识别的只有合并斜率 0.210±0.023。`analysis/size_regression.py --check` 9 条全真 |
| WP4 每家族规模曲线（an3 的一半） | 本层编排者 | 每家族每基准一条（规模, 分数）序列，同家族同配方，逐格用该行自己的 `n_items` 算二项区间；点数 <2 的家族记「无曲线」；跨语言/跨协议的格子不入同一条线（a12），lm-eval 全 timeout 无法与真 0 区分的格子标不可用（i01 res26） | WP2 | ≤60 CPU 分钟 | **完成**：328 个带配方的组 = 63 条曲线 + 265 个「无曲线」组（已记录）；63 条里 40 单调、23 有反向，其中仅 4 处超出噪声且全在 gemma-4 Q2_K_XL 的 12B 档，3 处由 MultiPL-E raw 的已知 harness 失败解释，逐基准打印 i01 的通道限制 |
| WP5 同激活参数下 dense 与 MoE 的位置 | 本层编排者 | 把每个 MoE 锚点按 dense 曲线反解出「等效 dense 规模」并给出区间，或证明库内没有可比的 dense/MoE 对并写明缺什么 | WP3, WP4 | ≤40 CPU 分钟 | **完成**：稠密曲线 `0.2223+0.2375·ln(B)`；三个大 MoE 的等效稠密规模是自身激活参数的 2.9–5.8×，LFM2.5-8B-A1B 约 1×；跨家族边界写死 |
| WP6 收口与报告能说什么 | 本层编排者 | `RESULT.md` 每条新事实带证据与复算命令；`report.html` §2 的两句硬编码断言（`make_report.py:1674-1675`）逐句判定「成立 / 需改写 / 超出证据」，改写文本交 meta 转 i02，本层不改 `make_report.py` | WP3–WP5 | ≤30 CPU 分钟 | **完成**：`analysis/run_all.py --selftest` 5/5 绿 + 负控成立；报告六处「规模当 X」逐条裁决与建议文本入 `RESULT.md::report-size-claims-audit` |
| WP7 独立复核 | fresh-context reviewer（meta 派） | 每包一份裁决（接受 / 接受带注解 / 不接受），阻塞项带位置与复现命令；reviewer 必须实跑命令并贴输出 | 对应包完成 | ≤30 CPU 分钟/份 | 待派 |

调度原则：`WP2` 是其余各包的公共前提（X 错了，Y 的拟合没有意义），所以它先做且只有它一个在跑。`WP3`/`WP4` 都只读 `experiments.sqlite`，可并发 ≤2；`WP5` 依赖两者。

## 资源与 GPU

- 分配额度 7% GPU / 5% CPU。本轴是纯分析，**不需要 GPU**：全部工作读 `experiments.sqlite` 与 `/home/z/hf` 的 GGUF 头，不启服务、不评测。
- 唯一的例外情形写在这里以免事后临时扩张：若 `WP5` 里「同激活参数」的 dense 对照在库里根本不存在的假设被确认，需要补一格测量才能回答，那要一个新的工作包、要 meta 批 GPU 窗口，并先看 `nvidia-smi` 的 `memory.free` 再持 `bash .wrapup/gpu_locked.sh` 起服。本层不预先占用。

## 未解问题

- an3 :: 「小模型低比特时困难 agentic 任务整体触底」这条 analysis 的证据链是否牢——它引的是 `result.res1`（a01 的位宽事实），本层只能判「在规模轴上是否复现」，判不了位宽轴本身（`WP4`）。
- 缺受控对 :: 要让 `plan5` 的双变量回归可识别，需要至少两对「同总参、不同激活」的受控点（同一 MoE 权重换 `expert_used`，或同总参的稠密/MoE 对）；库内一对也没有，本轮记未测，补测要 GPU 窗口（`WP3` 已写明最小补测）。

## 非目标

- 不做量化位宽轴（a01）、不做方案/厂商轴（a03）、不做 MoE 层比特分配（a04）、不做采样轴（a06）：本层只在判 confound 时借用它们的行，并在原处标注属于哪个轴。
- 不改 `experiments.sqlite`：本层只读。理由同 a01 —— 本层要判的是库里的 X 是否被正确解释，改数会连带作废报告里其它节。若确实发现必须修的数，写成给 meta 的提案，附编号备份方案。
- 不碰 `make_report.py` / `mktables.py` / `report.html`（i02 拥有）：报告文本要改也必须走 meta → i02。
- 不重跑评测来「让曲线好看」：缺的点记未测，不补。

## 跨子项目依赖

1. **报告 §2 的两句结论是 `make_report.py:1674-1675` 的硬编码文本**，不是从库里算的，且它引的「小模型之间差距更大」在本层的 `WP6` 之前没有逐家族证据。本层只交证据与建议文本。
2. **`__size` 不是参数量的行，会污染报告 §2 的表**：`mktables.py` 给 §2 的行键用的是 `__size`（`家族 @ 配方` × 规模）。本层若判定某家族的行必须排除，改法在 i02 一侧。
3. **`report_inputs/build_open_questions.py` 只从 `PLAN.md` 的 `## 未解问题` 一节取条目**：因此本文件保留该二级标题，条目被删时同步重生成 `open_questions.json`（i02 拥有该生成物，本层只保证输入节存在）。
