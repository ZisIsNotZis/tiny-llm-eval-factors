# a01 量化位宽 — 计划

计划层的唯一 home。goal / purpose / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a01 行定义，本文件不复述；本文件只写里程碑、工作包、状态与派工。
结果与证据在 `RESULT.md`；孙 agent 的窄规则在 `AGENTS.md`；可执行的复算脚本在 `analysis/`。

## 里程碑：研究结束

- 终点状态：注册表给的三条 AC 同时有可复算证据——(1) 每个家族一条「有效位宽 → 分数」曲线 + 拐点 + 区间，且拐点不可估的家族写明「不可估」及其原因（而不是补一个数）；(2) 三元/极低位宽是否离轨有支持、否定或有界结论；(3) gemma-4-12B 原生档的 MMLU 异常归位（复测值，或显式登记为未测并写明代价）。
- done 判据：`python3 "docs/subprojects/a01-量化位宽/analysis/run_all.py"` 退出 0（跑曲线/拐点、B1 反例裁决、三元离轨、12B MMLU 四项检查，逐条打印预期是否成立），且 `RESULT.md` 每个数字后面都有一条能被别人重跑的命令。
- 只有一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`、`WP2`、`WP4`；`WP3` 的 T1/T2/T3 与 `WP5` 的 CPU 部分（见 `RESULT.md` 的 `b1-heplus-only`、`t2-channel-excluded`、`q2kxl-iq3-4b`、`ternary-offcurve`、`lowbit-spread`、`m55-exq-inversion`、`gemma12b-mmlu-uniform`）。
- 在办：`WP6` 收口（`run_all.py` 已经 38 条预期全绿、`--selftest` 能失败；剩下把 PLAN/RESULT 的口径对齐）。
- 卡住（等 GPU，见下面「GPU 队列」）：`WP3::T4` 与 `WP5` 的复测都还没跑，登记为**未测**，不是 0。GPU 现在被别的仓占满（`memory.free` 204 MiB，`/tmp/llama_gpu.lock` 有 5 个持有者），按 `@scheduling.queue_behind` 排队而不是占住回合。
- 下一个派给谁：本层编排者做 `WP6`；GPU 空出来后依次跑 `WP3::T4`、`WP5`；两包完成后请 meta 派 fresh-context reviewer 做 `WP7`。
- 本层没有派孙工具（运行时不提供 subagent 接口），所以实现与测量由编排者自己执行；独立复核必须由 meta 派 fresh-context reviewer，不得自评通过。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | 本层编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`plan.yaml`/`result.yaml` 已迁入并删除；`git grep -n 'a01-量化位宽/\(plan\|result\)\.yaml' -- ':!report.html'` 只剩 i02 的一行陈旧引用（已登记为跨子项目依赖）；`python3 docs/check_docs.py` 退出 0 且 a01 的四个文件都被解析成事实；提交在 main 且按路径点名 | — | 1 会话 | **完成** |
| WP2 曲线 + 拐点 + 区间 | 本层编排者 | `analysis/curves.py` 一条命令产出每家族每基准的（有效位宽, 分数, 区间）序列 + 拐点估计 + 拐点 95% 区间；点数不足以估拐点的家族逐条打印「不可估 + 原因」 | WP1 | ≤60 CPU 分钟 | **完成**（`--panel`/`--pair`/`--all`/`--adjacent`；21 条 series 里只有 Qwen3.5-2B 能估拐点，其余记不可估，见 `RESULT.md::knee-estimable`） |
| WP3 B1 反例裁决（plan2） | 本层编排者 | 四项各自有裁决：(T1) ✅ 只有 HumanEval+ 的差区间不含 0（`b1-heplus-only`）；(T2) ✅ 落盘完成物审计：两格围栏率相同、无 timeout、分数低的那格 sanitize 后更干净（`t2-channel-excluded`）——判分通道不能解释；(T3) ✅ 4B 同字节对方向一致但只有 MMLU 显著（`q2kxl-iq3-4b`），外加同 base 权重的 m55 exq 反向（`m55-exq-inversion`）；(T4) ⏳ 同配置重跑的复现负控**未跑**（GPU 排队）。结论：主因是「比特分配/方案」而不是判分通道，但**幅度**只在 HumanEval+ 成立 | WP2 | ≤90 CPU + ≤40 GPU 分钟 | 进行中（T4 等 GPU） |
| WP4 三元与极低位宽离轨（plan2 的另一半） | 本层编排者 | 逐条给「在家族曲线上/下」或「不可判」：GLM-4.7-Flash 的 TQ1_0 在家族内低 29.9 pp（`ternary-offcurve`）；2.23–2.28 比特带里 HumanEval+ 跨 40.9 pp（`lowbit-spread`）→ 原生三元模型不可判、非原生 TQ1 离轨；`Q2_0`/`PQ2_0` 加载失败**未测**（要 GPU + 更新的 llama.cpp，见 GPU 队列） | WP2 | ≤45 CPU 分钟 | **完成**（加载失败一项登记未测） |
| WP5 12B 原生档 MMLU 异常（plan7b） | 本层编排者 | CPU 部分 ✅：+22.59 pp 的跳在 61 个科目上均匀（51 升、中位 +0.250、无全对/全错），两次运行的命令行逐字相同、912 题集合相同、该文件只有一次测量（`gemma12b-mmlu-uniform`）。GPU 部分 ⏳：同 shim 复测或生成式 MMLU 对照**未跑** | WP2 | ≤45 CPU + ≤30 GPU 分钟 | 进行中（GPU 排队） |
| WP6 收口与报告一致 | 本层编排者 | `RESULT.md` 每条新事实带证据与复算命令；本层没写库就明写「未写库」；若写了库则先编号备份 + `PRAGMA integrity_check` + 清洁检查 + 重生成 `report.html` 并给「报告数 = 库数」核对命令 | WP2–WP5 | ≤30 CPU 分钟 | 未开始 |
| WP7 独立复核 | fresh-context reviewer（meta 派） | 每包一份裁决（接受 / 接受带注解 / 不接受），阻塞项带位置与复现命令；reviewer 的结论取代本人自评 | 对应包完成 | ≤30 CPU 分钟/份 | 待派 |

调度原则：`WP2` 是其它三包的公共装置（曲线与区间算法只写一次），所以它先做；`WP3` 的 T2 与 `WP4`/`WP5` 都是 CPU 只读，重活并发 ≤2；GPU 全局串行，T4 与 12B 复测各自单独持锁，每段 ≤30 分钟并在里面自己等显存。

## WP3 的裁决设计（先写死判定规则，避免事后挑解释）

被审的说法（`report.html` 第一节「重点解释」的当前文本）：Qwen3.5-2B 的 `UD-Q2_K_XL`（4.11 比特/权重）分数低于 `UD-IQ3_XXS`（3.96），**原因是方案不同**——unsloth 的 `Q2_K_XL` 动态分配（保住少数关键层、其余层压到极低），`IQ3_XXS` 是信息论量化 + imatrix，按重要性较均匀地分比特。

四个竞争解释与各自的判别观测：

| 解释 | 判别观测 | 若成立则 |
|---|---|---|
| E1 统计噪声 / 功效不足 | 逐基准 3.96→4.11 的差与二项区间（用该格自己的 `n_items`） | 差值落在区间内 → 用「测不出」替换掉点说法；有差值的基准单独留 |
| E2 判分通道失真 | 同一批落盘完成物按 raw / sanitized 两条路径重判，逐题翻转数与超时直方图 | 翻转量与差值同量级 → 归判分通道，必须改报告 |
| E3 单文件对（不可外推） | 其它家族里 |Δbpw|≤0.15 的 Q2_K_XL 类 vs IQ3_XXS 类对的符号；Qwen3.5-4B 对照 | 符号不一致 → 撤回「方案普遍如此」，改成「这一个文件对如此」 |
| E4 方案本身（报告当前的说法） | 上述三条都不成立，且差值在 T4 的复现负控里稳定 | 保留方案解释，但把措辞降为「与本数据相容」并写明未被孤立的机制 |

硬性要求：结论必须写明「什么观测会推翻它」。不允许出现「因为方案不同，所以分数低」这种把机制当证据的句子。

## 已记录的设计判断（本层自行决定）

1. **有效位宽用 `8 × 文件字节数 ÷ 参数量` 的实测值，且横轴只有这一个口径**：厂商档位名在不同模型上跨度不同（同名 `Q3_K_M` 在 Llama-3.2-3B 是 4.20、在 Phi-4-mini 是 4.42），用档位名当 X 会把不同字节的东西画成一个点。参数量取 `.wrapup/bpw_map.json` 的精确值（由 gguf 元数据算），不取库里四舍五入到 0.1 B 的 `__size`，因为后者会把 1.88 B 的模型写成 2.0 B、把 3.27 算成 3.07。
2. **区间用逐题二项区间（Clopper–Pearson），不用模型间残差**：每一格都有自己的 `n_items`，逐题通过是伯努利，所以「这一格能不能和那一格分开」是二项问题；跨家族的残差区间会把模型差当成噪声。
3. **拐点只在家族内点数 ≥4 时估**，且必须同时给出「不可估」路径：多数家族在库里只有 2 个位宽点，2 点连线的「拐点」是过拟合。
4. **不写库**：本层只读 `experiments.sqlite`，结论落 `docs/subprojects/a01-量化位宽/`。理由：本层要否定的是库里的数是否被正确解释，不是改数；改数会连带作废报告里其它节。
5. **不碰 `make_report.py` / `mktables.py` / `report.html`**：报告文本要改（第一节那句「原因」）也必须走 meta → i02，本层只提交「文本应为 X」的建议与证据。

## GPU 队列（未测，不是 0）

GPU 现在是别人的（`nvidia-smi` 空闲 204 MiB；`/tmp/llama_gpu.lock` 有持有者；另一仓的 `waiter2.sh` 在等窗口）。按 `@scheduling.queue_behind` 记成排队请求，不占住回合、不抢锁：

| 排队项 | 配置 | 判据 | 预算 | 继续触发的条件 |
|---|---|---|---|---|
| WP3::T4 复现负控 | Qwen3.5-2B `UD-Q2_K_XL` 的 HumanEval+ 格，历史原旗标（`-c 8192`、服务器默认槽位），跑 2 次 | 两次题数一致 ⇒ 那 22 题不是随机噪声；不一致 ⇒ 该格的值本身不稳定，`b1-heplus-only` 必须降级 | ≤25 GPU 分钟 | `memory.free ≥ 20000 MiB` 且 `bash .wrapup/gpu_locked.sh` 能拿到锁 |
| WP5 复测 | gemma-4-12B 原生 `UD-Q4_K_XL` 的 MMLU，同 shim 同协议跑 2 次；再加一格生成式 MMLU（同一批 200 题，chat 协议，取答案字母） | 复测值 ≈ 0.6436 ⇒ 文件性质；明显偏离 ⇒ 该格作废并改报告；生成式若与 Q3 相当而似然差 22 pp ⇒ 判分通道 | ≤30 GPU 分钟 | 同上；`Q2_0`/`PQ2_0` 加载测试另需 ≤15 分钟与更新的 llama.cpp |

## 未解问题（plan 层的事实；答完即改写或删除）

下面两条是注册表登记的待办；它们的工作包在上表，结论进 `RESULT.md`。


### plan2 :: 假设 B1：三元/极低位宽的「异常点」——三元（Bonsai）与 Q1/Q2 可能根本不在平滑的「更多比特→更高分」曲线上；剩余工作：查 `Q2_0` 加载失败、`PQ2_0`（ggml type 142）需更新的 llama.cpp、同模型内的干净方案对照，用匹配比特/权重而非匹配量化名比较。
- author: agent
- scope: specific
- status: provisional
- evidence: 三元文件的有效位宽在 `.wrapup/bpw_map.json`（`Bonsai-27B-Q1_0.gguf` = 1.131、`GLM-4.7-UD-TQ1_0.gguf` = 2.226）
- repro: 未就位——`WP4` 建好后填入

### plan7b :: 12B 原生档的 MMLU 异常需复测确认（原 plan7 的一部分）。
- author: agent
- scope: specific
- status: provisional
- evidence: 当前值见 `gemma12b-mmlu-jump`
- repro: `WP5` 的复测命令建好后填入

## 非目标

- 不重跑整条量化阶梯：库里的 7 个面板（`m61`–`m67`）已是同协议同配置的一列（见 `RESULT.md::qw2b-panel`），重跑是浪费 GPU 配额；只补「功效不足」与「复现负控」两处必需的格。
- 不做方案轴的一般结论（那是 `a03`），不做 QAT 轴（`a09`），不做 MoE 层比特分配（`a04`）；本层只在需要判 E3 时借用它们的行。
- 不追已退役的 `.scratch/originals/*` 原稿：其中不可复算的数一律标「无可重算命令」，由本层脚本重算或撤回。
- 不改别的 subproject 目录、不改 `docs/plan/subprojects.md`。

## 跨子项目依赖（不由本层修，必须让 meta 知道）

1. **`report.html` 第一节的因果句需要 i02 改**：本层的 `WP3` 若判定 E2/E3 成立，报告那句「原因是这是两个不同方案」必须替换；`make_report.py` 由 i02 拥有，本层只交证据与建议文本。
2. **`make_report.py::load_docs` 只读 `docs/subprojects/*/{plan,result}.yaml`**：本层迁成 Markdown 后，报告「客观结果 / 分析结论 / 待分析」三节里引用 `res1`–`res5`、`an1`–`an3`、`plan2`、`plan7b` 的条目会消失且不报错（静默变空）。`docs/check_docs.py` 已经支持 Markdown 事实（`## <id> :: <text>` + `- key: value`），所以修法在 `load_docs` 一侧，属 i02。
3. **`i01` 的判分审计是本层的约束而不是本层的活**：`RESULT.md::res26`–`res28` 给出 EvalPlus / lm-eval / MultiPL-E 各自的失真通道；本层的任何曲线点在引用处必须写明它的通道状态（`AGENTS.md` 第 2 条）。
