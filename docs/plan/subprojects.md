# 子项目目录（meta 层唯一 SSOT）

这一层只拥有**研究由哪些单元组成、每个单元的 goal / purpose / AC / 资源 / 依赖、以及谁在做**。
研究内容本身——工作包、实验、结论、证据——属于各子项目自己的 `docs/subprojects/<id>-<name>/`，不在本文件里复述。
本文件不放任何测量数字：数字的当前值在子项目的结果节点里。

## 划分依据

单元 = `report.html` 的节（用户确认的权威编号）：一节一个自变量 X，Y = 基准分，其余固定成 series（`product.prod2`）。
§7 投机解码（速度）与 §8（质量）同一个 X，由同一子项目 `a07` 拥有两节。

## 资源（我分配，子项目不得自行扩张）

| 资源 | 容量 | 政策 |
|---|---|---|
| GPU | 1× RTX 4090 24 GB | **全局 1 个并发任务**，必须持 `/tmp/llama_gpu.lock`（`bash .wrapup/gpu_locked.sh`）；下表 GPU% 是 4 周周期的分配权重，不是并发权 |
| CPU | 12 核 | 重活 ≤ 2 并发（编译/评测/绘图），其余让路 |
| 内存 | 125 GB（可用 ~108） | 单任务 > 30 GB 前先算一次峰值；不得同时起两个大模型服务 |
| 磁盘 | 191 GB 可用 | 大产物按 `artifacts.tsv` 声明，不进 git |
| GPU 并发例外 | 锁是小任务的地狱 | 当持有者要跑很久、而另一个任务需求 ≤4 GB 显存且 ≤3 GPU 分钟时，可以**并行**跑：条件是 `nvidia-smi` 空闲显存 ≥ 需求 + 2 GB、起服后断言 `n_slots`、并把「并行于谁、实测占用」写进该次记录。锁仍防止两个大任务同时抢显存，但它不该让一个 1 分钟的控制实验等 2 小时 |
| GPU 的外部占用 | 不受本仓库锁管理 | 起服前先看 `nvidia-smi` 的 `memory.free` 与 `--query-compute-apps`：别的仓库的任务（例如 `scripts/train_sft.py`）也在同一张卡上，本仓库的 `/tmp/llama_gpu.lock` 只管自己。**绑定约束是空闲显存**，不是锁；起服后断言 server 自报的 `n_slots` 与配置相符，不符即作废该次测量 |
| 活跃 orchestrator | ≤ 3 | 未启动的单元排队，由 meta 按依赖放行 |

## 我发给子项目的契约（每次派工都含这些，缺一不可）

goal、purpose、AC、资源额度、边界（可写哪些路径）、**递归授权**（可派孙 worker/reviewer）、
「停止条件只有外部硬阻塞」（缺资源/缺授权/不可逆操作），以及报告格式。
子项目自己的计划里必须随时能读出：还剩哪些工作包、当前在哪个、下一个派给谁。
回到「下一步做什么」视为它计划的缺陷。

**长活不得阻塞 worker**：编译、镜像拉取、模型下载、整批评测这类会跑过 20 分钟的动作，
一律用 `setsid nohup … > log 2>&1 &` 起在后台、把 pid 与日志路径写进报告，然后**继续做下一件不依赖它的事**；
轮询用带超时的短检查，不要 `sleep 长值`。理由：2026-10-27 两个 worker 分别在「编 lama.cpp CUDA」与
「拉 Terminal-Bench 镜像」上被 30 分钟上限掐死，已经跑出来的事实（构建成功、镜像在盘）差点没有人接手。

## 单元

| id | 子项目 | goal（要成为真的状态） | purpose（服务哪个决定） | AC（可证伪） | GPU% | CPU% | 依赖 | 在办节点 |
|---|---|---|---|---|---|---|---|---|
| i01 | 判分与基准有效性 | 每个 harness 的判分可审计，单次测量的噪声有数 | 已有数字还能不能用 | 每个 harness 一份审计+负控；chat 单次噪声地板定出；同一格跨 run 差异有裁决 | 15 | 20 | — | **已结项**：四族审计各带可打红的负控；确定性解码地板 = 0 道题（四族 161/164/100/40 全同）；temp=0.3 五跑逐题 Jaccard 0.53–0.67 而分数只摆 6/164；`plan15` 判为「四槽批处理被排除、131 不可复现、未记录输入差可致 ±16/161」；缺输入一律 exit 2 并由 gate 自检。已记录限制：EvalPlus 无逐题产物、BFCL micro 不可从库算、多轮题量无产物来源 |
| i02 | 测量基础设施 | 干净 clone 一条命令复现报告与数据 | 别人能否信任并重跑 | DB 幂等+完整性检查绿；提示集/哈希可查；报告从库复现；表格行键与陈旧根路径修完 | 5 | 25 | — | **已结项**：AC 五条达成，证据在它的 `RESULT.md`（res24/res31/res26/res28/res32），干净 clone 15 PASS / 0 SKIP；两条已记录限制：行键容纳不下 `top_k`（res41）、审计只能证明值在面板多重集里而非逐格归属（F4） |
| a01 | 量化位宽 | 每家族的有效位宽曲线与拐点成立，极低位宽是否离轨有定论 | 选哪一档量化 | 每家族可复算曲线+拐点+CI；三元/极低位宽假设有支持/否定/有界结论；12B MMLU 异常归位 | 13 | 8 | i01 | **已结项**：21 条 series 全部可复算；带区间的拐点只有 Qwen3.5-2B（其余 3 点给「中间点、区间宽 0」的退化拐点、<3 点不估，分档写明）。B1 反例裁决：3.961→4.109 只有 HumanEval+ 的区间排除 0（+0.1341 [+0.0345,+0.2303]），判分通道被排除（两格围栏 164/164、低分格 sanitize 后更干净、零 timeout），T4 复现负控 40/40 逐字节（低分格）；三元：GLM TQ1 低 29.9 pp、原生三元「不可判」、2.23–2.28 带跨 40.9 pp；`Q2_0` 可加载，`PQ2_0`（ggml type 142）**mainline 不支持、prism fork 可加载并生成**（14.1 s / 572 MiB）；12B MMLU 两次逐位 `0.643640350877193` ⇒ +22.6 pp 是文件/协议性质 |
| a02 | 模型规模 | 判定规模能否作为 X，并给出可用的替代 | 固定显存下选多大模型 | MoE 双变量回归或明确不可测；每家族规模曲线可复算 | 7 | 5 | i01 | **已结项**：原「规模」列 7 条取数通道被逐行归因，仅 659/3233 行可信；替代 X = 入库 fixture 的 GGUF 张量参数量（76 文件 / 169 组）；`plan5` 判不可识别（稠密秩亏、MoE 内 VIF 13.3、合并系数是两团点云假象）；63 条同族同配方曲线 + 265 个单档组逐条登记 |
| a03 | 量化方案与厂商 | 判定同字节下方案/厂商标签能否分辨 | 换方案值不值 | 方案差与厂商差各有 CI；至少一个跨供应商同尺寸受控对 | 4 | 3 | i01 | **已结项**：同字节下方案/厂商系数 9/9 跨 0，但只能判到 0.10–0.49 的精度，故结论是「此设计下不可分辨」；标签被证明是比特分配的代理（同一对总量差 0.025 bpw、分配差 0.381）；跨厂商受控对成立且 9/9 跨 0；`res7` 的 +0.056 已按规则撤回。已记录限制：厂商效应只由单一家族识别、干净 clone 里靠入库的 fixture 复现 |
| a04 | MoE 各层比特分配 | 判定层比特分配能否与总比特预算分离 | 专家层该压多低 | ≥3 种分配策略受控结论；Tier-1A 判定并给出资源结论 | 7 | 5 | i01 | **已结项**：均匀 4.531 vs 专家优先 4.483 的钉住对照在六列可分辨（HE+ +0.4695，配对 99 vs 22，discordant 77:0，p=1.3e-23），预算项按固定效应斜率只有 [0.0017,0.0155]，所以**分配独立于预算**；但「均匀 > 专家优先」是 **n=1** 且对手是已知病态臂（exq4 在 4.48 bpw 上 HE 0.14），被否定的只是「把非专家层砍到 ~2.95 喂专家仍安全」；Tier-1A 剩余价值（桶内结构）价格修正为 **44.9 min/臂** |
| a05 | KV 缓存精度 | KV 精度与长度的效应覆盖到长上下文 | KV 能不能省显存 | 短上下文结论保留；长上下文覆盖，或显式未测并说明代价 | 9 | 5 | i01 | **已结项**：短上下文改为两口径（24 对里 6 对分数相同而通过集不同，q8_0 vs q4_0 都 90/164 却 12 丢 12 得）——「KV 省显存几乎免费」只在分数层面成立；长上下文用针检索实测 8k 17vs13、16k 20vs20、32k 14vs15，**「越长越贵」无支持**，可观测下限 4/20；对照经「留针去指令」重跑实测 0/20（峰值 3.7 GB，与 a04 并行）；q8_0 未重跑、≥40k 未测、K/V 分开量化未测 |
| a06 | 采样与解码参数 | 判定采样是否改变任何量化结论 | 固定协议是不是 confound | 厂商推荐采样 vs 固定协议受控检查完成；温度/top-k 结论可复算 | 7 | 5 | i01 | **已结项**：厂商推荐档不是「温和采样」而是**塌陷**——MultiPL-E 六格 −17~−36 题、EvalPlus −35；损失是**绝对丢题**不是按比例塌陷（「10 倍」只是基线 39–44 题造成的相对放大）。单变量探针否掉两个假设：`presence_penalty=0` 仍 2/40、再加 `top_p=0.95/min_p=0.05` 仍 3/40（且 40 题里 20 题状态互换，总数只是净抵消）→ 主因是 `temperature=1.0`。温度轴 161 题四点 39/28/24/10 单调、`0.3→0.6` p=0.524、`0.6→1.0` p=0.009 而两步之差 p=0.26，所以只能说「最后一步是唯一与零可分的一步」。限制：单模型 2B、单语言 cpp |
| a07 | 投机解码 | 判定投机解码的速度/质量权衡 | 开不开投机 | 速度-深度-质量三点结论，独立可复算 | 4 | 3 | i01 | **已结项**：字节同一性判据成立且是封闭的——四个 `none` 会话（跨 9 天、不同进程）**164/164 逐字节相同（地板 0）**，投机臂 `draft-mtp:2` 与 `none` **相同 91/164、差异 73**，而投机臂跨会话**164/164 逐字节相同**（两侧都可复现 ⇒ 差异可归因于该路径）；差异集合完全相同、首次分歧位 42–1809、字符 0–4 内分歧 0（提示/模板一致）。速度 0.8B **423.45 → 534.88 tok/s（+26.3%）**；运行期草稿成本 9B +376 MiB / 0.8B +96 MiB（与 MTP 头权重 +14.2 MB 是两个口径，不许相加）。承重完成物已入库（6 臂 × 164 条 + 逐题 sha256），干净 clone 可证明地板；伪造一条即退 1 并点名 |
| a08 | 思考开关 | 判定思考开关是否值得默认开 | 开关该不该默认关 | 每类基准开/关对照；未测项显式 | 2 | 2 | i01 | **已结项**：结论是「**思考不改变答得好不好，而是吃掉生成预算**」——对数似然类（mmlu n=912）聚合分与 stderr 相同、completions 端点逐字无反应；生成类在 4096 预算下，开思考用 **7.1×（gsm8k）/ 15.0×（ifeval）** 的 token，换来 **−33/100 与 −14/25**，其中 ifeval 的差**至少 93%** 由 23/25 题截断强制产生、gsm8k 的差**至多 79%**。墙钟比不作协议比（同配置两臂 188 vs 314 tok/s）。未测：8192/16384（需同时抬 ctx，逐臂报价）与 code 类 |
| a09 | 量化感知训练 QAT | QAT 相对原生档的位置有定论 | 该不该专门找 QAT 版 | 同标称配方配对结论（含低位宽档）；12B 异常归位 | 4 | 3 | i01 | **已结项**：库内无任何一对 QAT/原生同比特——QAT 文件小 0.359–0.953 bpw 且分配轮廓与格式都变了；按实测比特插到同族阶梯上，4-bit 档持平或更好（E2B 9/9、E4B 8/9 列正、12B 7/8 在 ±0.03），2-bit 档更低（13/15）但少 0.36–0.55 比特且分配反向，不能归给训练；12B 的 MMLU −0.197 判不可分辨（该族 Q3→Q4 一步就 +0.226，残差 −0.088 窄于方案不可分辨带）；`res12` 的「原生档位存疑」改为指向它那一列。m145 未买（价格已修正为 **≈74 GPU 分钟**）；张量清单比对把 E2B/E4B 四对判为 `GRAPH_DIFF`（缺 `attn_k/v` 各 20/18 层）并从归因中排除，结论只由 12B 那一对支撑 |
| a10 | 第三方量化方案 | 第三方方案在原生阶梯上的位置可判 | 值不值得用第三方 | 与最近原生档/插值档比较的 CI 结论 | 3 | 2 | i01 | **已结项**：GSQ-RCO 两档 vs 原生三档，36 个格 32 个有区间，**只有 1 格排除 0**（IQ3_S 的 HumanEval +0.0671，且少花 0.301 比特、方向与预算相反），独立比较 ≤18 而非 32（报 p=0.0379 而非「期望 1.6 格」）；方案标签不是独立变量而是**一套逐张量分配配方的名字**（同配方 0/866 张量不同，但同字节 ≠ 同分配：0.209/0.300 比特/参数）；「同字节+同分配+不同方案」的臂本库**不存在（0/0）**→ 未测；`res13` 已撤回 |
| a11 | 扩散式解码 | 判定扩散式解码能否在本机比较 | 要不要为它换运行时 | 要么测出对照，要么 GATE-FAIL 且门槛可复现 | 3 | 2 | i02 | **门槛已解除（2026-10-27），尚无分数**：上游 PR #24423 分支（`ggml-org/llama.cpp`）的 `llama-diffusion-cli` 能加载本机 diffusiongemma-26B-A4B-Q4_K_M 并生成（`1+1=`→`2`，两次独立运行同答案，352 tok/s，显存峰值 21.1 GiB/24 GiB），但该运行器只有 CLI 没有 server，工具调用类基准用不了；协议对齐（`PLAN.md::plan4`）之前不给分数。原 GATE-FAIL 读数对 mainline 构建仍成立（`RESULT.md::res13`）**：文件确是块扩散解码器（非因果 + canvas 256 + MASK + self-cond；比自回归孪生多 34 个张量，是严格父集）；两棵 llama.cpp 的架构名表都没有 `diffusion-gemma`，`-ngl 0` 现场 1 秒内 rc=1 报 `unknown model architecture`（负控 gemma4-E2B 能起服）；价格按**真 KV** 复核：权重 15.638 + 0.273 GiB = 15.911 ≤ 当时空闲 → **当时其实装得下**，原「17.5 GiB 需求」是上界（上界/真值 6.86×）已作废；compute buffer 未算、许可未查、位宽匹配对照 m145 未买 |
| a12 | 多语言代码 MultiPL-E | 逐语言与生成协议的结论可靠 | 代码能力能不能只用 python | 语言集与协议受控、无跨语言池化；每模型每语言都有来源 | 9 | 5 | i01 | **已结项**：标准列拆双列不池化、250 格 / 246 已评分 / 0 未追溯、缺口登记区分「未测 / 已测但按规则排除 / 已测但整批未入库」三类；两条已记录限制：审计的追溯是面板多重集成员检查而非逐格绑定、行键容纳不下 `top_k` |
| a13 | 工具调用 BFCL | 协议×类别结论成立且跨家族 | 工具调用能不能按单点结论外推 | 多轮跨家族覆盖或有界结论；类别覆盖表 | 6 | 4 | i01 | **已结项**：单轮换官方 AST checker 后 2,788 题改判、35 反向（官方 ≥ 自研在全部可打分格），第一名从 Bonsai 换成 gemma-4-E4B-Q3（macro 差 0.0100、micro 0.0057，方向相反）→「三值 Bonsai 最好」不成立；排序大体保留（4/55 逆序）但绝对值与 ≤0.05 间距不可沿用；多轮只支持组内比较（4 组 handler，唯一跨族对照仅 base@98304 三行），跨族无证据、2×2 定价≈50 GPU 分钟未买；判分器四条控制（含正控）成立，边界写明只覆盖 multi_turn_base |
| a14 | 部分给分 | 判定更细的 Y 是否消解二元判分的模糊 | 二元判分是不是丢了信号 | 与二元判分的对照结论及其噪声 | 2 | 2 | i01 | **已结项**：部分给分**不消解**二元模糊——排序几乎不变（Spearman 0.888–1.000，108 对里 7 对翻号），两把尺不同（比例 ≥ 二元，中位 lift +0.1115、最大 +0.238）；9 个近差对只分开 3 个、其中**只有 1 个**与二元相反；逐题 SE 不比二项小（中位 0.957，26/76 格 ≥1）——因为一个错函数通常整题失败，7 个测试不是 7 份信息。**附带发现**：历史 py 格用的是旧测试语料，钉住语料重评 98 格 → 50 格改分、151/15516 题翻转（最大一支是 `HumanEval_95` 的 int 键断言，32 格 OK→Exception，四种 hash seed 确定复现）；旧期望值已不在盘上，`HumanEval_79` 那支只能标推断。取代由 `i02` 按五元组重定位入库 |

合计 GPU% = 100，CPU% = 97（余量留给 meta 的巡检与复核）。

## 写权（谁提交谁的）

同一棵工作树里可以有多个子项目同时写不同路径（`i01`/`i02`/`a12` 各自的目录与各自负责的脚本），所以**提交时按路径点名，绝不用 `git add -A`**：`git add -A` 会把别人正在改的中间态一起定型，让 main 上出现一个没人能解释、也没人负责的半成品提交。meta 只提交 meta 自己的路径，子项目的步由子项目自己提交。

## 里程碑状态（第一版报告交付）

**这不是目标的终点**：本节记的是第一版报告的交付面。目标见 `docs/need/need.yaml::n1`，这一版覆盖到哪里、缺口在哪，见 `docs/subprojects/i02-测量基础设施/RESULT.md::res72` 末段；不在此复述。

十六个单元全部结项。交付面是 `report.html`：21 节 / 86 图，从库与入库派生索引重建，干净 clone 里**逐字节可复现**。整合验证（由 meta 独立跑，不复用子项目的清单）：`./reproduce.sh` exit 0，逐行结论由该命令当场产生，本文件不写那份计数；`c19c168` 与 `bc1eeb0` 上都是 exit 0，唯一一条非 PASS 行是下面 `p-entry1` 登记的 `size_claims` 漂移。各单元自己的验收装置在干净树里全 rc=0，只有 `a13`（缺 `bfclenv`）与 `i01`（按其契约 exit 2 = 逻辑与门绿、真实数据不可得）如实报不可得。

未测分三类，读法不同：`BLOCKED-on-VRAM`（已定价、未买）、`GATE-FAIL`（本环境缺运行时；扩散解码那一条 2026-10-27 已解除，见 a11 `RESULT.md::res13`，现等协议对齐）、「本环境不可测」（没有逐题产物、没有对照臂、跨语料不可比）。统一入口在 `docs/subprojects/i02-测量基础设施/RESULT.md::res72`。

## entry — 下一个里程碑：根目录的两道门说真话

研究交付物已经能被一条命令重建，但**读者进入仓库的那两道门没有跟着改建**：`STATUS.md` 与 `FINDINGS.md` 仍指向 `021e6b8` 搬走的 `docs/plan/plan.yaml` 与 `docs/result/result.yaml`，实测 42 条节点引用里只有 1 条解析得到（`python3 checks/router_refs.py`）。里程碑 `entry` 结束时，从根目录读起的人不会踩到任何一条死路径，而且这件事由一条会自己变红的检查守着，不靠谁记得。

| 包 | 内容 | 验收（命令） | 依赖 |
|---|---|---|---|
| `r-entry1` | `checks/router_refs.py` 与它的负控：三份根路由里每条 `docs/…::id` 与每个 `docs/…` 路径都必须在树上解析得到；看不到输入不算通过 | `python3 checks/router_refs_negative_control.py` exit 0（二十一条期望，逐条列在脚本头部：未改动副本绿；围栏里的标题不算 id、注释里的不算、行内代码里的注释开标记不算注释；跨行拆开的引用与 `::` 两侧带空格的引用都留在分母里并各自报红；缺 id、缺文件、空扫描、缺路由文件、路由器里未闭合的围栏或注释各自红） | — |
| `r-entry2` | `FINDINGS.md` 每行指到 HEAD 上真实存在的节点，状态取该节点自己的 `状态：` 行；已退役或被修掉的项进「撤回记录」并写死因 | `python3 checks/router_refs.py` exit 0，且 `grep -c 'docs/result/result.yaml\|docs/plan/plan.yaml' FINDINGS.md` 为 0 | r-entry1 |
| `r-entry3` | `STATUS.md` 与 HEAD 对齐：只引用能解析的路径，当前状态与下一步按本文件写 | `python3 checks/router_refs.py` exit 0 | r-entry1 |
| `r-entry4` | 根目录无未归类路径：运行日志按类忽略，逐题产物按 README 的判据入库 | `git status --porcelain` 无输出 | — |
| `p-entry1` | `report_inputs/size_claims.json` 与 a02 的产物不一致（`python3 report_inputs/build_size_claims.py --check` exit 1），而 `./reproduce.sh` 只记 WARN 就继续：报告第二节停在这个旧值上仍判绿 | 该命令 exit 0，且报告重建后逐字节相同（或第二节的改动经复核后重新入库） | — |
| `p-entry2` | **已结项**：13 条「输入与其来源不一致」的判断收进 `checks/report_inputs_drift.py`，`./reproduce.sh` 只把它翻成核对表里的行——漂移=FAIL（整条命令非零退出），看不到来源=SKIP（rc=2 或来源不在场；缺席不是漂移）。判定比对上：只有三个 builder 自报 rc=2，其余十个由脚本先查来源在不在，查不到才 SKIP | `python3 checks/report_inputs_drift_negative_control.py` exit 0：未改动绿 → 改坏 `open_questions.json` 一个字节后 `./reproduce.sh` exit 1 并点名它 → 移走 `gsq.json` 仍 exit 0 且该行为 SKIP → 原字节写回、sha256 不变。负控走 `REPRODUCE_INPUTS_ONLY=1 ./reproduce.sh`（只跑这一节，约 2 秒）：整条链路两分钟且路径由脚本自身位置推出、不能在临时树上跑，故给它一个「只跑这一节」的开关，而不是复制一份判断逻辑 | p-entry1 |
| `p-entry3` | **已结项**：处置选「入库」而不是清单——被点名的证据随仓库走：9 个 `.log` 以 gzip 存到原路径旁的 `.log.gz`（`gzip -dc | sha256sum` 与原文件逐个相同，原 `.log` 删除）；`RESULT.md` 里作 `evidence:`/`repro:` 点名的聚合产物（`evalplus.json` / `lmeval_panel.json` / `ident_control.json` / 探针输出）原样入库，`.gitignore` 里逐份 `!` 放行；面板的 per-task `lmeval_*.json` 邻居一起入库（`migrate_db.ingest_campaign` 从里面取 metric 名并重算分数，缺了它干净 clone 里会把面板那几行重写成 `… #None`，`checks/refresh_guard_differential_control.py` 会因此变红）；**没被点名**的运行目录产物才按已声明的可重建缓存类忽略。第二轮复核后补入库了 19 份被点名、却一直没入库的聚合产物（a01 七档面板里 m61/m62/m65/m66/m67 的 `evalplus.json`，a10 五个面板的 `{cmd.txt,evalplus.json}`，a03 跨上传者受控对 m101/m103 的两份 `evalplus.json` 与 `cmd.txt`）；同目录其余运行期产物不动。第三轮复核后补入库：a01 以目录 token 点名的 m64 面板的 `lmeval_panel.json` 与它的 5 份 per-task 邻居（缺邻居时 `ingest_campaign` 在干净 clone 里会把 6 行重写成 `… #None` 并合并成 5 行）；a03 点名的 m101/m103 `evalplus.json` 与 `cmd.txt` 已在第二轮入库。逐题评测产物不按类忽略：被点名却没入库的 `*_eval.json` 必须红。类的唯一清单是 `checks/evidence_logs.py` 的 `REBUILDABLE_CLASSES`；token 按 exact / dir / pattern 三种形状判，exact 这一档只认那张表里的规则**加上**该类允许的形状，`mres/` 的 catch-all 不算处置；pattern 一档把花括号一律展开成候选（没有单选项例外），指名一个文件的候选也过同一张形状表（否则同一个未入库文件写成 exact 红、写成模式绿）；dir 一档的判据是「目录里有入库 / 压缩入库 / 按类可重建的文件，或该目录本身是已声明的可重建运行目录（空目录也算）」，本机会走进目录按形状判，盘上是无扩展名文件时按 exact 形状表判——**目录 token 不保证目录内每份文件入库**，哪些是本地产物、不入库要在使用点写明（`a01-量化位宽/RESULT.md` 的 `panel.log` / `lmeval_panel.json` 那条就是样板）。**两端语义不同**：本机（盘上有未入库的 run 文件）逐条核到文件；干净 clone 里只能按声明/索引判，报 `BLOCKED` 并 exit 2（不可得），不是绿。条数与字节合计不写在这里，由验收命令的结论行当场算。这几份日志载着无法重算的事实（`n_ctx_slot = 4096`、两行 OOM、`creating MTP draft context`、`CORRUPT` 与 `FileNotFoundError` 计数） | `python3 checks/evidence_logs.py` exit 0：逐条判每条被点名的 `.wrapup/…` 路径有没有处置，并在结论行给出「条数 / 原始字节合计 / gzip 字节合计」（9 个登记的 `.log` 逐个解开与登记值比字节）；负控 `python3 checks/evidence_logs_negative_control.py` exit 0（**真树基线 exit 0；干净 clone 基线 exit 2 = 不可得**；换字节数→多一条并点名该 `.log`；聚合产物未入库 / 落到未声明的类下→「无处置」；精确点名的未入库 `lmeval_panel.json`→过形状表判无处置；逐题样本落到未声明的类下→「无处置」；模式或目录点名的未入库 `evalplus.json`→「无处置」并点名该文件；空扫描→断言只有该守卫会打的 `BLOCKED 空扫描` 行；每一例「删掉它守着的那段代码→该例变红」的反证结果列在脚本头部）；两条都由 `./reproduce.sh` 按 PASS/BLOCKED/FAIL 调用 | — |

`p-entry3` 的取证：下面这条打印「被 `RESULT.md` 点名、在盘上、但未入库」的文件清单——它现在只应剩下可重建缓存（被点名的 `.log` 早已以 `.gz` 入库，被点名的聚合产物已入库），行数由命令当场给出，本文件不抄。每条「有处置 / 无处置」的判定与 `.log` 的字节合计不走这条 shell，走 `python3 checks/evidence_logs.py`：它的结论行就是那两个数。

    grep -ho '\.wrapup/[A-Za-z0-9._/-]*' docs/subprojects/*/RESULT.md | sort -u | while read -r p; do if [ -f "$p" ] && ! git ls-files --error-unmatch "$p" >/dev/null 2>&1; then echo "$p"; fi; done

**本包判据的边界**（三条，别读成比实际更强的断言）：① **目录 token 不保证目录内每份文件入库**——`dir` 一档只要目录里有入库/按类可重建的文件就算有处置，哪些是本地产物、不入库在使用点写明；② `pattern` 指目录时只按声明判，不走进候选目录看内容；③ 干净 clone 只按声明/索引判，报 `BLOCKED` 并 exit 2（不可得，不是绿）。

里程碑的验收命令：`python3 checks/router_refs.py && ./reproduce.sh && git status --porcelain`（前两条 exit 0，第三条无输出）。

已结项：`r-entry1`–`r-entry4`、`p-entry1`、`p-entry2`、`p-entry3`。**结果 revision 是 `3287b76bc47e3164ab8d237febd54bceda66817c`**
（`git rev-parse 6 位以上前缀` 就能验：`3287b76`；它之后的提交只动文档——本节这一段与
`docs/plan/evidence/entry/` 下的捕获——不动代码、数据与结论）。七个包与整条链各一份捕获，门 3 的四件齐全（被审 revision / 命令 /
捕获的输出 / 产物 sha256）：

**干净 clone 的结论（本轮按实情分开）**：本机是「逐条核到文件」的那一端——`.wrapup` 里有未入库的
run 文件，`checks/evidence_logs.py` 走到文件、exit 0。干净 clone 里盘上一个未入库的 run 文件都没有，
`pattern`/`dir`/`exact` 只能按声明/索引判：同一条命令在
`git clone <结果 revision> /tmp/clone && cd /tmp/clone && python3 checks/evidence_logs.py` 下报
**BLOCKED 并 exit 2（不可得）**，结论行给出「本次 189 条只能按声明/索引判，无法用盘上文件核」。
上一包写的「干净 clone 里 exit 0、与真树同一结论」是本轮推翻的说法：它把「不可得」当成了绿。
另外，`REBUILDABLE_CLASSES` 里那条 `mres 运行目录本身` 的形状 `(?:^|/)[^./]+$` 已删掉——它在
`exact` 档不可达（`exact` token 必带扩展名），留着只会成为「无扩展名文件被当目录放过」的借口。
捕获见 `docs/plan/evidence/entry/p-entry3-evidence-logs-3287b76.txt`。

| 包 | 命令（在 `3287b76` 上） | 捕获 | 承重产物 sha256（前 12 位，全长在捕获尾部） |
|---|---|---|---|
| `r-entry1` | `python3 checks/router_refs_negative_control.py`（二十一条期望逐条 `ok`），rc=0 | `docs/plan/evidence/entry/r-entry1-router-refs-nc-3287b76.txt` | `checks/router_refs.py` `23dd4bb73817`、负控脚本 `95b0215d0504` |
| `r-entry2` | `python3 checks/router_refs.py`；`grep -c 'docs/result/result.yaml\|docs/plan/plan.yaml' FINDINGS.md` → 计数 0，rc=0 | `docs/plan/evidence/entry/r-entry2-router-refs-3287b76.txt` | `FINDINGS.md` `689da1190a23` |
| `r-entry3` | `python3 checks/router_refs.py`，rc=0 | `docs/plan/evidence/entry/r-entry3-router-refs-status-3287b76.txt` | `STATUS.md` `17b604c615ea` |
| `r-entry4` | `git status --porcelain`——在该 revision 的干净 clone 里无输出（捕获文件本身不在那个 clone 里，见捕获里的说明） | `docs/plan/evidence/entry/r-entry4-git-status-3287b76.txt` | `STATUS.md` `17b604c615ea`、`FINDINGS.md` `689da1190a23`、`.gitignore` `e292e250527a`；tree `86b2db7c5ac2`（README 的引用由 `r-entry1`/`r-entry2`/`r-entry3` 的 `router_refs` 捕获覆盖） |
| `p-entry1` | `python3 report_inputs/build_size_claims.py --check`；`./reproduce.sh` 末行判报告逐字节相同，rc=0 | `docs/plan/evidence/entry/p-entry1-size-claims-3287b76.txt` + 整条链 `docs/plan/evidence/entry/reproduce-3287b76.txt` | `report_inputs/size_claims.json` `c9c0a8cce1bb`、`report.html` `6288338f54b3` |
| `p-entry2` | `python3 checks/report_inputs_drift_negative_control.py`，rc=0 | `docs/plan/evidence/entry/p-entry2-drift-nc-3287b76.txt` | `checks/report_inputs_drift.py` `57e947664d4c` |
| `p-entry3` | `python3 checks/evidence_logs.py`（本机 exit 0）；它的负控（含干净 clone 基线，exit 2）；干净 clone 里再跑一次 `checks/evidence_logs.py`（exit 2 = BLOCKED）；`git ls-files '<三组 .log.gz 选择器>' -z \| xargs -0 gzip -dc \| wc -c`；`git ls-files '<三组 .log.gz 选择器>' -z \| xargs -0 ls -l \| awk '{s+=$5} END {print s}'` | `docs/plan/evidence/entry/p-entry3-evidence-logs-3287b76.txt` | `checks/evidence_logs.py` `b013f5cba7c3`、负控脚本 `33dc8ced6827`、9 个入库 `.log.gz` 逐个 sha256 在该文件尾部 |

`./reproduce.sh` 在同一 revision 上 exit 0（本机：53 PASS、0 FAIL/WARN/SKIP/BLOCKED）；PASS 行数与非 PASS
行数不写在这里，由 `grep -c` 从 `docs/plan/evidence/entry/reproduce-3287b76.txt`（那次运行的原始输出）
当场数。同一 revision 的干净 clone 里 `./reproduce.sh` 也能跑：exit 0，非 PASS 是两条——设计内的
一条 SKIP（`.wrapup` 的 KV 证据来源不在 clone 里，按设计报「来源不可得」）与一条 BLOCKED（`evidence_logs`
在 clone 里只能按声明判，报不可得）——计数由那份 clone 的输出当场给出，本文件不抄。

旧绑定 `ba817d7`（`p-entry1`）与 `9e89f91`（`p-entry2`、`p-entry3`）、`00be81d`（七个包的上一次结果
revision）、`5e6df26`（第二轮结果 revision）、`e338f4b`（更早一次结果 revision）作为历史保留：它们是
那次推进当时的读数，在 HEAD 上已不是当前值——`p-entry3` 的那两个字节数与「26 个按类忽略」正是
里程碑复核判掉的两条假证据；`5e6df26` 的捕获在干净 clone 里声称 `evidence_logs` exit 0，第二轮复核指出
那只能按声明判、看不到盘上文件，本轮改成报 `BLOCKED`。

**第三轮独立复核的判词与处置**：被审 revision `e53ba5a`，判「不接受」（P1×2、P2×3、P3×2）。已逐条修掉：
① 单选项花括号白名单删除（`{…}` 一律按正常路径展开，唯一真模板改写为 `<run_tag>`）；
② `dir` 档判据照实写明为「目录里有入库证据，或该目录本身是已声明的可重建运行目录」，并补入 m64 面板；
③ 模块说明与代码对齐（顶层 `.wrapup/<x>/` 也走进目录按形状判）；
④ 负控第 9 例改断言只有空扫描守卫会打的行，且每例都做了「删掉守卫→该例变红」的反证（表在
`checks/evidence_logs_negative_control.py` 文件头）；
⑤ `STATUS.md` 的前向引用落到本节；`checks/README.md` 随第一、二条同步。反证/命令/捕获均绑定本轮的
结果 revision（见下）。

**第四轮独立复核的判词**：被审 revision `3287b76`，判**接受**（P1 = 0；P2×1、P3×2）。它在接受后留下的三处已顺手修掉，并单独提交：① `a14-部分给分/RESULT.md` 的复现命令在第三轮被改成 `<run_tag>` 占位后成了空转（`compared 0` → 永远 `disagreements 0`），恢复成真比对（76 格、0 不一致，本机实跑）；② `p-entry3` 行里 dir 判据的摘要比代码窄（漏了「按类可重建」与空目录），照代码写全；③ 负控末行「真树未被本控制改动」失败时空诊断，改为打印前后内容。三处都只动文档与负控诊断，结果 revision 仍是 `3287b76`。

`entry` 的验收命令在结果 revision 上：`python3 checks/router_refs.py && ./reproduce.sh && git status --porcelain`——前两条 exit 0、第三条无输出；干净 clone 里 `evidence_logs` 报 `BLOCKED`（不可得）、其余绿，两端语义写在本节末「本包判据的边界」。

未结项：无。里程碑 `entry` 已在 `3287b76` 上通过四轮独立复核（第一轮不接受：p-entry3 的字节数与归类为假、无负控；第二轮不接受：pattern/dir 两档绕开形状表、空扫描仍绿；第三轮不接受：负控不隔离守卫、单选项花括号白名单、dir 判据文档强于代码；第四轮接受）。

## agentic — 下一个里程碑：真实 agentic 基准上的端到端分数

目标（`docs/need/need.yaml::n1`）的 Y 端是「真实的 agentic 基准，多种类型、多种难度」。第一版报告的 Y 以静态代码/知识/指令类为主（覆盖与缺口见 `docs/subprojects/i02-测量基础设施/RESULT.md::res72` 末段）。本里程碑把 Y 端补齐到可以在 X（模型架构/版本/规模/激活、量化、运行时）上扫的水平。

第一批基准与理由（环境事实与可达性见 `docs/subprojects/i02-测量基础设施/RESULT.md::res73`）：**Terminal-Bench 2.0**（终端/运维，`task.toml` 原生 easy/medium/hard 与 `expert_time_estimate_min`，Docker 现成）、**τ-bench v1 / τ²-bench**（多轮规划+用户对话，纯 Python，无 Docker）、**BFCL v4 离线类别**（工具调用，`bfclenv` 已装、数据自带）。AppWorld / SWE-bench / WebArena / OSWorld / GAIA / Cybench 本周不进：数据在 HF（现连不通）或要浏览器/VM 与百 GB 镜像。

| 包 | 内容 | 验收（命令） | 依赖 |
|---|---|---|---|
| `p-ag1`（**取用受阻 2026-10-27**：仓库 `git clone`/codeload 超时，仅 `git ls-remote` 通，见 `i02 RESULT.md::res74`；先做 `p-ag3`） | Terminal-Bench 2.0 的 24 题分层子集（easy/medium/hard 各 8）在**一个最小本地模型**上跑通：llama-server + harbor 的 OpenAI 兼容 provider，分数、每题耗时、镜像拉取量、总 GPU 分钟落到本机日志 | 一条可重跑命令产出该模型的 24 题分层分数表（三档各一行），日志在 `.wrapup/agentic/tb2-<model>-<date>/`；本机 `./reproduce.sh` 不受影响（不碰库） | — |
| `p-ag2` | τ-bench v1 的 airline+retail（165 题）在同一模型上跑通，判分用上游自带 checker | 一条可重跑命令产出两域分数；日志同目录 | p-ag1 |
| `p-ag3` | **已结项（2026-10-27）**：BFCL v4 离线的 7 个类别在 `Qwen3.5-0.8B-UD-Q4_K_XL` 上跑通（tools 协议）+ 其中 3 类做了 prompt 协议对照 + 5 类做了 KV f16/q8_0 对照；15 行入库（`m171`/`m172`，`db_check` 绿），`web_search*`/`memory*` 各自登记不可得 | `python3 docs/subprojects/a13-工具调用\ BFCL/audits/run_all.py` exit 0；`python3 checks/db_check.py` 绿；结论与每格数在 `docs/subprojects/a13-工具调用 BFCL/RESULT.md` | — |
| `r-ag1` | 难度分层的口径。**已核实的现状**：本机可跑的两种 agentic 基准都没有原生难度分层——BFCL v4 只有类别（simple/multiple/parallel/live/多轮）；τ-bench v1 的 `Task` 只有 user_id / instruction / actions / outputs 加 `annotator`，没有 easy/medium/hard 字段。唯一带原生三档的是 Terminal-Bench 2.0（`task.toml` 的 `difficulty` 与 `expert_time_estimate_min`），而它今天取不下来（`i02 RESULT.md::res74`）。所以第一批只能用**代理分层**：`gold_actions` 数、用户轮数、工具调用数。必须同时写明代理量与 X 的共线风险（轮数多 → 吃 `ctx_size` 与生成长度；长上下文档撞上限会把「难度」变成「预算不足」，a08 已有一例：思考开 = 吃生成预算），并给出一条反例检查：按代理量分档后，同一 X 取值在相邻档上方向相反。 | 一条判据 + 一个反例（`docs/subprojects/i02-测量基础设施/RESULT.md::res75` 记本案：难度代理量清单与共线检查）；TB2 一旦可取，原生三档优先于代理量 | — |
| `p-ag5` | 把「难度代理量」写进库：每条 agentic 行带上 `gold_actions` / 用户轮数 / 工具调用数的分布，使「难度」可被查询而不是只活在报告文字里 | 一条 SQL 能按代理档聚合分数；派生列与单独对照表二选一，不许两处各写一份 | `r-ag1`、`p-ag2` |
| `p-ag4` | 首条 X 扫描：在 TB2 子集上扫一列 X（先做**量化档**：同族 UD Q2/Q3/Q4 各一档；再做**运行时**：ctx 8k / 32k） | 每个 X 取值一行分数，同一 series 内其余量固定；库内新增行走 `migrate_db.py` 且 `db_check` 绿 | p-ag1 |

里程碑达成的判据：TB2 三档 + τ 两域 + BFCL 离线类别在第一模型上有分数；`p-ag4` 至少给出两档量化与两档 ctx 的同 series 对照；难度分层口径（`r-ag1`）写进 `docs/method/method.yaml`。

## 共享仓库的写权（避免互相踩）

1. **push 归 meta**：子项目只提交自己的路径，**不 `git push`**、不 `git reset`、不 rebase 共享历史。提交必须带显式路径——`git commit -m … -- <path>…`，**不要用裸 `git commit`**：索引是共享的，别人 `git add` 之后你一提交就会把他的暂存一起定型（已经发生过两次：`i01` 的 PLAN 被扫进 `a06` 的提交，`a06` 的四个文件被扫进 `i01` 的提交）。分支修复只有 meta 做，且在独立 worktree 里做。这条是踩出来的：一次并发 `push` 把远端 rebase 了一份提交、本地又留了一份，另有一次 `reset` 让别人已提交的两个提交从 main 上消失。
2. **改库前后行数必须相等**，除非本次变更明确就是删行，并且按测量身份逐条对上；「身份去重」把另一个测量当重复删掉过一次（BFCL 的 prompt 协议 20 行被当成 native 的重复），从备份恢复后才修好。任何删除都要先算「应剩多少行」，跑完对账。
3. 数据库是单一写入点：入库走 `migrate_db.py`，改完立刻 `db_check`，并且在下一次别的子项目入库前确认 skip ledger 为空。

## 复核门（meta 自用，判子项目交回来的包）

1. 复核者必须**能执行**：派工前确认它在当前上下文有 shell；派工契约里写明「先跑命令再判」并要求贴命令与输出，一个只读代码、不执行任何命令的复核不算证据。
2. 判级不看复核者的结论词，看缺陷等级：存在 P1（证据未绑定到被审 revision、负控不成立、证据句为假、AC 条目无人满足）即**不接受**，返回原 owner 修，不靠复核者的 ACCEPT WITH NOTES 兜底。
3. 每个包回到我这里的证据必须绑定 revision：`git rev-parse HEAD` + 产物 sha256 + 运行命令 + 输出捕获，四件缺一即 P1。
6. 结项 = 干净 clone 里验收装置绿：结项提交本身必须让 `run_all.py`/验收脚本 exit 0，而不只是在作者工作树里绿。这条已因同一个类被抓到四次（`a02`、`a03`、`a04`、`i01`）：**结论与它的数据必须在同一个提交里**，数据后提交或留在工作树里就等于没结项。
4. 负控至少一次：用一份已知错误的副本证明检查会失败；做不到就在结论里写「未验证」，不算通过。
5. 看不到输入的检查必须失败：一个在缺 `.wrapup/mres`、缺数据集、缺 venv 时打印 `UNMEASURED` 然后 exit 0 的脚本，等于「结果不可得」也能冒充「结论成立」——这类假绿已在 `a02`、`a03`、`i01` 各出现一次。缺输入时退出码必须非 0（2 = 不可得），并且不得把它算进 PASS 计数。

## 启动顺序与队列

1. **在跑**：`a01`（量化位宽）、`a06`（采样与解码参数，厂商臂测量中）。`a04`、`a05` 已结项。`a12`、`a03` 已结项；`i02` 转为报告面的常驻服务（其 AC 已达成，现只承接「结论进入报告」的改动）。
2. **第二波**：`a01`、`a02`、`a04` 已放行；`a05`、`a06` 待 GPU 空闲显存稳定后再放行。
3. **第三波**：`a02`、`a03`、`a06`、`a09`、`a13`。
4. **收尾波**：`a07`、`a08`、`a10`、`a11`、`a14`。

## 迁移状态

原 `docs/plan/plan.yaml` 与 `docs/result/result.yaml` 的全部节点（12 + 32）已按轴搬进各自目录，meta 层不再持有任何研究节点；
`make_report.py::load_docs` 已改为读取 `docs/subprojects/*/{plan,result}.yaml`。仓库内既有文档仍是 yaml，
按 `@migrate_on_touch` 由各子项目在自己那一份上改成 Markdown，不做大爆炸迁移。
