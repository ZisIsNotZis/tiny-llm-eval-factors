# a03 量化方案与厂商 — 计划

计划层的唯一 home。goal / purpose / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a03 行定义，本文件不复述。
本文件写里程碑、工作包、派工与判定口径。结果与证据在 `RESULT.md`；孙 agent 的窄规则在 `AGENTS.md`；
可执行的复算装置在 `analysis/`。

## 里程碑：研究结束

- 终点状态：注册表给的两条 AC 同时有可复算证据——(1) **方案差**（IQ 系列 vs K 系列，同厂商内、同字节）有逐基准区间，方向与大小可读；(2) **厂商/上传者差**有逐基准区间，且至少一对**跨供应商、同尺寸、同协议**的受控对；两条都要写明「厂商」在这份数据里到底能不能与「比特分配」分开。
- done 判据：`python3 "docs/subprojects/a03-量化方案与厂商/analysis/run_all.py"` 退出 0（配对装置、方案归因、厂商归因、比特分配审计四组预期逐条打印是否成立），且 `RESULT.md` 的每个数字后面都有一条别人能重跑的命令。
- 只有一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`（三层文档 + `result.yaml` 迁入并删除）、`WP2`（`analysis/pairs.py`）、`WP3`（方案归因：`scheme-2b`/`scheme-4b`/`scheme-27b`）、`WP4`（厂商归因：`vendor-qwen36`/`vendor-lfm`/`attrib`/`label-audit`）、`WP5`（`analysis/alloc.py` 的 `alloc-qwen36`/`alloc-scheme`/`alloc-m55`）。
- 在办：`WP6` 收口——`analysis/run_all.py` 现在 17 条预期全部成立、`--selftest` 能翻红 3 条（退出码 1）；剩下两件：把 `report.html` 第三节的建议文本写进 `PLAN.md`，以及 `RESULT.md` 的数字与 `run_all.py` 的断言逐条对齐。
- 下一个派给谁：本层编排者收 `WP6`；收完请 **meta 派 fresh-context reviewer** 做 `WP7`（本层运行时没有派孙工具，不得自评通过）。
- **递归不可用（运行时不提供 subagent 接口）**：本层编排者只有 shell/读写工具，没有派孙工具，所以分析、脚本与测量由编排者自己执行。这与派工契约里「可派孙」不一致，按 `@fail_loud` 写在这里而不是假装派过；独立复核因此必须由 meta 派。
- 未测（不是 0）：`WP6` 的复现负控（同一格重跑）没跑——GPU 被别的仓占着（见下面「GPU 队列」）。所有配对都是**单次运行**，区间只含逐题二项项，不含跨 run 项；这一条在 `RESULT.md` 的每条事实里都写着。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | 本层编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`result.yaml` 的 `res7`/`an4` 已迁入并删除该文件；`python3 docs/check_docs.py` 退出 0 且 a03 的文件被解析成事实；提交在 main 且按路径点名 | — | 1 会话 | **完成** |
| WP2 同字节配对装置 | 本层编排者 | `analysis/pairs.py` 一条命令枚举族内全部配对，逐对打印 Δbpw、配对性质（方案/厂商/两者/仅预算）、逐基准差值 + Newcombe 区间 + 该格 `n_items`；协议不一致的格判「不可比」并打印而不是静默丢弃；`--slopes` 打印每基准的同族每比特斜率 | WP1 | ≤20 CPU 分钟 | **完成**（`RESULT.md::pair-device`、`inventory`、`slopes`） |
| WP3 方案归因（IQ vs K，同厂商内） | 本层编排者 | 每条 IQ-vs-K 配对逐基准给差值 + 区间；跨族汇总只用「同号族数 + 逐族区间」，并打印参与汇总的族数；给出「方案效应在多少 bpw 内可分辨」的实测下界 | WP2 | ≤30 CPU 分钟 | **完成**（`scheme-2b`/`scheme-4b`/`scheme-27b`；跨族归因见 `attrib`） |
| WP4 厂商归因（含跨供应商受控对） | 本层编排者 | 厂商从面板写入的模型路径取（不从文件名猜），打印每个文件的来源；给出 ≥1 对跨供应商同尺寸同协议配对的逐基准区间；机械证明「是否存在把比特分配也钉死的跨厂商对」（有/无都要打印计数） | WP2 | ≤30 CPU 分钟 | **完成**（`vendor-qwen36` 达成 AC 第二条；`attrib` 打印识别族：IQ 3 族、bartowski 1 族、local 1 族——没有同时钉死分配的跨厂商对） |
| WP5 比特分配解释力 | 本层编排者 | `analysis/alloc.py` 直接读 gguf 头，按张量类别打印每个文件的实测 bits/参数与分配轮廓；对每组配对给出两份文件的分配轮廓差；写明报告的 `MATCH_BPW = 0.45` 允许的比特预算效应有多大 | WP2 | ≤45 CPU 分钟 | **完成**（`alloc-qwen36` 0.381、`alloc-scheme` 0.337–0.427、`alloc-m55`；位宽尺子见 `slopes`） |
| WP6 收口与报告建议 | 本层编排者 | `RESULT.md` 每条事实带证据与复算命令；`analysis/run_all.py` 全部预期成立（`--selftest` 能翻红）；`report.html` 第三节的文本建议（`换方案测得出 / 换厂商测不出`）按本层证据给出「保留 / 收窄 / 撤回」与其否证条件；不写库、不改 `report.html` | WP3–WP5 | ≤30 CPU 分钟 | 进行中（`run_all.py` 17 条成立、`--selftest` 翻红 3 条；剩报告建议文本 + 复现负控排队） |
| WP7 独立复核 | fresh-context reviewer（meta 派） | 每包一份裁决（接受 / 接受带注解 / 不接受），阻塞项带位置与复现命令 | WP2–WP6 | ≤30 CPU 分钟/份 | 待派 |

调度原则：`WP2` 是 `WP3`/`WP4`/`WP5` 的公共装置，先做；三包都是 CPU 只读，重活并发 ≤2。GPU 只在 `WP6` 的复现负控需要（≤25 分钟，见 GPU 队列）。

## 判定口径（先写死，避免事后挑解释）

1. **配对只在一族内**：一族 = 同一套 base 权重只换量化文件（`mktables.family_of`，保留尺寸）。跨族的同字节点不是受控比较。
2. **匹配字节的判据分三档写死**：`|Δbpw| ≤ 0.45`（报告第三节 / `mktables.MATCH_BPW` 的现行口径）、`≤ 0.15`（本层收紧）、`≤ 0.05`（字节几乎相同）。同一结论必须在至少两档下一致，否则写明只在哪一档成立。
3. **区间 = 两比例差的 Newcombe method 10**，`n` 取该格自己的 `n_items`；TruthfulQA 的 `acc` 是概率质量均值（`i01::res26`），那一列只报差值不套二项区间。区间是**非配对**（逐题结果没有落库），所以「跨 0」只能说测不出，不能说相等。
4. **配对前先验协议**：`protocol / n_items / ctx_size / parallel_slots / temp / reasoning` 逐列相等，不等即该格「不可比」并打印。
5. **厂商不可从文件名推断**：厂商取面板 json 里写入的模型绝对路径（`mscache/<vendor>/…` 或 `models--<vendor>--…`），文件名里的 `UD-` 前缀只说明上传者的**配方**（unsloth dynamic），不说明来源，而且 `Phi-4-mini-instruct-Q2_K.gguf` 就是反例（非 UD 命名、实际来自 unsloth）。
6. **`n_items` 先看再用**：`ifeval/gsm8k/arc/truthfulqa` 是 `limit 100` 的子集，`mmlu` 是 912，`humaneval` 164，`mbpp` 378；缺格写「缺」，不写 0。
7. **不池化**：语言、协议、基准之间绝不平均；跨族汇总只用计数与同号检验。

## 给 `report.html` 第三节的建议文本（`WP6`；本层不改 `make_report.py`，由 meta 转 i02）

现有三句话逐条给裁决。每条都带否证条件，写进报告时保留。

1. 现文「在文件字节接近的前提下，换方案（例如 IQ 系列 vs 传统 K 系列）分数会出现可测的差异」——**收窄**。匹配字节下它不是水平移动：≤0.15 档的 4 对 × 9 列 = 36 个格里只有 3 格区间不含 0，而且同一对内部的显著格方向不一致（LFM 那对 MBPP −0.103 与 MMLU +0.114）。建议改为：「同字节换方案只在个别格上分得开（本库 36 格里 3 格），且方向随基准变；把比特预算与家族钉住后，方案标签本身测不出水平差」。否证条件：补出第二个同字节方案对后同一方向的差在多数列上重复出现。
2. 现文「而换厂商标签（同一模型、大小差不到 1%）基本测不出差异」——**保留结论、限定证据量**。本库跨上传者、同尺寸、同协议的受控对只有 **1 对**（Qwen3.6-35B-A3B，Δbpw 0.025，九列全跨 0），而 `attrib.py` 的 `bartowski` 系数只由这一族识别；而那一对同时换了比特分配，所以它约束的是「上传者 + 分配这一整包」的上限。建议改为：「本库只有一对跨上传者受控对，九列测不出差异；样本 1 族，且该对同时换了分配」。否证条件：出现第二对并测出区间不含 0 的差。
3. 现文「结论：挑量化时应该比字节 / 方案，而不是比厂商标签」——**前半保留、后半改口径**。字节是唯一在本库 9 列上稳定不含 0 的变量（`slopes`）；「比方案」作为一个分数声明不成立（见第 1 条）；而标签真正代理的是**比特分配**（同字节下分配轮廓可差 0.34–0.43 比特/参数）。建议改为：「比字节（有效位宽）和比特落在哪类层上，不比档位名或厂商名」。否证条件：出现同分配、不同标签而分数差稳定显著的配对。
4. 现文「一眼可见 Qwen3.5-2B 组里 IQ2_XXS 明显垫底」——**保留观察、补语境**。那一组的单链聚类跨度是 0.843 比特/权重（3.266–4.109），按位宽尺子本身就值 0.150 的 HumanEval+ 分，而那 0.335 的实跳里有 45% 是预算；IQ2_XXS 同时也是组内位宽最低的那份（`cluster-2b`）。

## 未解问题（plan 层的事实；答完即改写或删除）

### a03-q1 :: 「换厂商测不出差异」这句话（报告第三节、原 `res7`）没有可重跑的来源——它的 origin `.scratch/originals/L2-结果.md` 已退役，区间类型未记录，所以当前只能按 provisional 持有，等 `WP4` 用本层装置重算。
- author: agent
- scope: specific
- status: provisional
- evidence: `docs/subprojects/a03-量化方案与厂商/result.yaml`（迁移前）唯一持有的两条事实都是 `.scratch` 来源；`.scratch` 已按 `@scratch` 停用
- repro: 未就位——`WP4` 建好后填入

### a03-q2 :: 报告第三节按 `MATCH_BPW = 0.45` 分组，而本库同族每 +1 比特/权重的分数变化在 HumanEval+ 是 0.178 ± 0.073（`pair-device::slopes`），即这一档匹配本身就允许 ~0.08 的分数差；组内「换方案」的差是否被比特预算吃掉要由 `WP5` 判定。
- author: agent
- scope: specific
- status: provisional
- evidence: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --slopes`
- repro: 同上（`WP5` 建好后补分配轮廓）

## 非目标

- 不重跑量化阶梯：本轴的回答是「已有数字能读出什么」，不是补测量。只在复现负控需要时跑一格（GPU 队列），且登记未测比补一个数更可取。
- 不做 `a04` 的层比特分配结论（专家层该压多低）：本层只用分配轮廓当**混杂变量**，判分配策略本身是 a04 的活。
- 不做 `a09`（QAT）、`a10`（第三方 GSQ-RCO）、`a02`（规模）：它们的行只在需要当混杂变量时被引用，不出结论。
- 不改别的 subproject 目录、不改 `docs/plan/subprojects.md`、不改 `make_report.py`/`mktables.py`/`report.html`（i02 拥有）。
- 不用 `.scratch/originals/*` 当证据来源：那里的数只能标「不可复现」并写明原件已退役。

## GPU 队列（未测，不是 0）

| 排队项 | 配置 | 判据 | 预算 | 继续触发的条件 |
|---|---|---|---|---|
| WP6 复现负控 | Qwen3.5-4B：`UD-Q2_K_XL` 与 `UD-IQ3_XXS` 各跑一次 HumanEval+（164 题），同一脚本同一协议（`evalplus-0.3.1-openai-chat-greedy-plus`，`ctx 8192`、`np 1`、`temp 0.0`、`reasoning off`） | 两格各自复现入库值（MMLU 那 0.0592 与其余列的 0.00–0.01）⇒ 单次运行的差不是运行抖动；出现 >0.05 的偏离 ⇒ 该族配对降级为 provisional | ≤25 GPU 分钟 | `nvidia-smi` 的 `memory.free` ≥ 计算出的需求（4B Q4 ≈ 2.6 GB 权重 + KV ≈ 1 GB，取 6 GB 余量）且 `bash .wrapup/gpu_locked.sh` 拿到锁；起服后断言 server 自报 `n_slots = 1` |

## 跨子项目依赖（不由本层修，必须让 meta 知道）

1. **`a01` 拥有区间与家族定义**：`analysis/pairs.py` 直接 `import curves` 借用 `newcombe_diff` / `wilson` / `family_of`，不复制；a01 改了这两个函数的名字，本层会**报错**而不是静默用另一套口径（`@fail_loud`）。
2. **`i01` 的判分审计是本层的约束**：TruthfulQA 的概率质量、GSM8K 的 `flexible-extract`、IFEval 的 9 分地板、MMLU/ARC 的似然打平都写在 `i01::res26`；本层引用这些列时必须写明通道状态。`i01::res29` 给出「未记录的输入差能移动一格 ±16/161」，所以本层任何小于该量级的方案差都只能说「测不出」。
3. **`report.html` 第三节的文本由 i02 生成**：本层只提交「应写成什么 + 否证条件」，不动 `make_report.py`。
