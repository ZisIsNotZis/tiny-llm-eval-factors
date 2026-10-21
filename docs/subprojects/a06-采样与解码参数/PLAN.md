# a06 采样与解码参数 — 计划

计划层的唯一 home。goal / purpose / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a06 行定义，本文件不复述；
本文件只写里程碑、工作包、状态、派工与判据。数字的当前值在 `RESULT.md`，这里只写判据和状态。

## 里程碑：研究结束

- 终点状态：a06 的 AC 全部有可复算证据——「厂商推荐采样 vs 固定协议」的受控检查有结论（或显式登记为不可得并说明代价），
  温度 / top_k 的每条结论都能由 `RESULT.md` 里的一条命令重算出来。
- done 判据（四条同时成立）：
  1. `python3 "docs/subprojects/a06-采样与解码参数/sampling_census.py"` 退出 0，并打印协议普查、固定协议的参数、可用比较清单；
  2. `RESULT.md` 的每条事实都带 `- evidence:` 与 `- repro:`，且 `repro` 是一条命令；
  3. 三条轴的结论都在 `RESULT.md` 里有数：分数移动、逐题判决移动、量化档/规模次序是否存活；
  4. `plan3` 有终态：要么「厂商推荐臂已测且结论如下」，要么「厂商推荐值不可得（原因）+ 已有温度臂给出什么」，
     不许停在「待跑」。
- 只有这一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`（文档归位 + 协议普查）与 `WP2`（逐题判决移动）。
  两个只读脚本都退出 0，捕获在 `evidence/`：`census-6fc5b0c.txt`（267 行）、`peritem-2552615.txt`（36 对），
  各自带一份负控（空临时树里跑同一脚本 → 输入全缺、exit 2）。
- 在办：`WP3`（厂商推荐臂）**值已就位、测量未跑**，由 i02 加档（meta 已裁决：a06 不碰 `.wrapup/variant_panel.py`）。
  i02 的加档尚未落 main（`.wrapup/variant_panel.py` 里还没有 `vendor` 串），所以 `WP3` 的触发条件是「i02 的提交落地 + 锁可用」，见下面的 GPU 队列。
- 下一步派给谁：`WP3` 的测量派给一个 GPU worker（契约在下面的 GPU 队列，逐格可执行，不需要再设计）；
  `WP4`（规模次序）同队列第二槽，可裁；`WP5`（独立复核）由 meta 派 fresh-context reviewer，**按 meta 的裁决等 `WP3` 落地后再派**。
- 真正未做的只剩两件：`WP3` 的厂商档测量 + `WP4` 的规模次序。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 + 协议普查 | a06 编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`plan.yaml` 与 `result.yaml` 已删除且 `plan3`/`res10` 以 `## <id> :: <text>` 事实存活；`sampling_census.py` 退出 0，缺任一输入（库 / `m27_summary.jsonl` / `m31_summary.jsonl` / `variant_panel.json`）时退出 2；`python3 docs/check_docs.py` 退出 0 | — | 1 会话 | 完成 |
| WP2 逐题判决在协议改变时移动多少 | a06 worker（CPU 槽） | 对 `.wrapup/mres/m27-*_eval.json` 与 `m31-*_eval.json` 逐题比 greedy 锚点与每个 temp>0 / top_k 设置，给出每 (模型, 语言, 设置) 的 up/down 翻转数与 Jaccard，并回答「净分数移动 vs 逐题翻转」是否与 i01 的 temp=0.3 五跑地板同量级；缺产物时 exit 2 | WP1 | 0.2 CPU 时 | 完成：`peritem_moves.py` 比完 36 对（3 档 × 2 语言 × 6 设置）退出 0；Jaccard 0.40–0.69，23/36 对净移动 ≤ 6 道题（与 i01 五跑地板不可分），最极端一格净 +1 而 15 上/14 下；负控在空临时树里 exit 2 |
| WP3 厂商推荐采样臂（`plan3` 的受控检查） | GPU worker 跑（i02 只提供 R2 的臂） | 队列 A 的 10 个格全部入库并按 `rank_survival.py --check` 通过：R1 的 MultiPL-E 6 格 + EvalPlus 1 格，R2 的 GSM8K/IFEval/MMLU 3 格；MMLU 必须仍为 `0.6075`（正控）；「厂商档下 cpp 的 Q3-vs-Q4 是否仍反转」由 `rank_survival.py` 的 `vendor` 行给出 survived/inverted | 队列 A 的触发条件（见下） | 63 GPU 分钟（R1 59 + R2 4，均含 25% 余量） | 待派（值已就位，等 i02 的加档提交落 main） |
| WP4 规模次序在采样下是否存活 | GPU worker | 队列 B 落地后在 `rank_survival.py` 里多一条 `axis=size` 的 ladder（0.8B/2B/4B，Q2 与 Q3 各一条），`--check` 通过，并打印每个规模对的 survived/inverted——与量化档结论分开报告，不得合并成一个「排序结论」 | 队列 B 的触发条件；另需第二个模型家族的厂商值 | 34 GPU 分钟（4 格 × 6.7 × 1.25） | 待派（可裁：AC 不依赖它） |
| WP5 独立复核 | fresh-context reviewer（meta 派） | 对本目录三份文档、`sampling_census.py`、`peritem_moves.py`、`rank_survival.py --check` 的输出给裁决，指出证据缺口；reviewer 的结论取代本人的自评 | meta 的裁决要求等 `WP3` 落地后再派 | 一次复核 | 待派（按 meta 裁决排在 WP3 之后） |
| WP6 排序判据机械化 | a06 编排者 | `rank_survival.py --check` 退出 0；三个 fixture 入库；两处负控成立（篡改一个分值 → exit 1；缺库 → exit 2）；RESULT 的「py 45 个非平比较 0 反序 / cpp Q3-vs-Q4 5 个反序」由 fixture 一行一行吐出而非散文 | WP2 | 0.2 CPU 时 | 完成 |

## plan3 :: 假设 B2（厂商推荐采样）：unsloth 给每个模型发布推荐运行/采样参数，而我们固定协议；做一次受控检查，看厂商推荐采样会不会改变任何量化结论（即我们的协议是否是 confound）。

- author: agent
- scope: general
- status: provisional
- domain: kind: hypothesis
- 当前判定：**输入已就位，测量未跑**。厂商推荐值已逐字取得并存成 `RESULT.md::res-vendor-value`：
  非思考文本任务 `temperature=1.0, top_p=1.00, top_k=20, min_p=0.0, presence_penalty=2.0, repetition_penalty=1.0`。
  它落在本研究测过的**每一个**设置之外（温度 1.0 不在 0/0.3/0.6/0.7 里；`top_p` 1.00 对钉住的 0.95；`min_p` 0.0 对 0.05；`presence_penalty=2.0` 对恒为 0），
  所以已有的五档采样格**代理不了**它——这正是本假设必须真跑一档的理由。
- 取值过程与限制：`huggingface.co` 在本机只解析到 IPv6 且到达不了（`curl` 15 秒超时，exit 28），值是从公共镜像 `hf-mirror.com` 读的，
  原件摘录、字节数与 sha256 存在 `evidence/vendor-card-excerpt-*.md`；因此这是二手证据，只用它取参数值，不拿它证明别的。
- 预期方向（推断，不是结论）：若温度 0.3–1.0 在代码列是一个平台（已测 0.3 与 0.7 在 HumanEval 上给出同一分数 0.5122），
  则厂商档的代码分也在 −10/164 附近；但同一档还改了 `top_p`/`min_p`/`presence_penalty` 三个从未变过的维度，所以这个外推未经验证。

## 判据（写死，避免事后挑解释）

1. **一格的协议 = 它的身份**：`protocol` 串（含 `;ctx=` `;kv=` `;tmpl=` 段）、`max_tokens`、`ctx_size`、`n_items` 任一不同就是两个测量。
   不跨协议池化，不跨语言池化，60 题探针不与 161 题满格比。
2. **可以读的列与不可以读的列**：`temp`/`top_k` 只在取值属于本仓声明过的设置时才当作采样设置读（普查 `[A]` 段）。
   落在声明集合之外的行，其采样设置是 UNKNOWN，不读它的列值。
3. **分数的移动要按题数读**：`Δscore × n_items` 才是移动了几道题；n_items 缺失时先证明分母（MultiPL-E 的 cpp/py 满格 161，
   可由 `score × 161` 全是整数验证），证不出来就不读。
4. **「噪声」与「效应」的分界**由 i01 的地板决定：确定性解码地板 = 0 道题；temp=0.3 同一格五跑的净分数摆动上限 6/164。
   净移动超过地板、且靠近或超过 6/164 的，只有拿到逐题产物才能下结论（`WP2`）。
5. **次序存活**用成对比较数（concordant / discordant / tie），不用单个模型的一个数。一个格的方向不算次序。

## 非目标

- 不重测固定协议：`multipl-e-raw-greedy-768` 的 180 格与 `evalplus-*` 的 148 格是既有资产，普查只读。
- 不补 `top_p` 轴：`top_p` 在每一条已测协议里都钉在 0.95，从不是变量；把它变成变量是一条新轴，超出 7% GPU 份额。
- 不改 `make_report.py` / `.wrapup/mktables.py`：报告第六节的呈现问题（`top_k` 撞标签）属 i02，a06 只提供证据。
- 不改其他子项目目录、不改 `docs/plan/subprojects.md`。
- 不重生成提示集：`.wrapup/prompts` 是唯一来源。
- 不修那 490 行采样列不可信的历史行的库值：修法是 i02 的库整洁范围，a06 只登记「这些行的采样设置 UNKNOWN」并保证自己的比较不依赖它们。

## GPU 队列（触发条件 + 逐格预算）

预算全部从实测吞吐算，不用圆整数：MultiPL-E 每格（161 题，gen+eval）按 **6.7 分钟**
（`m27` 实测：14 格 93.9 分钟，含每档一次 server 启动；`m3` 的 16 格是 5.4 分钟/格，`m2` 的 9B 6 格也是 5.4，所以取较慢的那个）；
标准列一档（MMLU 456 + GSM8K 50 + IFEval 50 + HumanEval 164）按 **6.3 分钟**（`m131` 实测 `panel.log`：01:57:03→02:28:44 五档 31.7 分钟）。
两者都乘 **1.25** 的余量，因为厂商档是本研究没跑过的采样值，序列长度可能变，而 temp 1.0 的思考串更长。

显存要求按实测：Qwen3.5-2B `UD-Q4_K_XL`（1.340 GB 权重）在 `-c 8192 -np 1 -ngl 99` 下让 `memory.free` 从 23088 降到 21198 MiB，**实测占用 1.89 GiB**；
所以门槛写成「`memory.free ≥ 2 × 1.89 GiB = 3800 MiB`」（2 倍是给同卡上别的仓库任务的增长留头，不是圆整数偏好）。
起服后必须断言 server 自报 `n_slots = 1`（`/tmp/a06_vram_probe.log` 里 `load_model: initializing, n_slots = 1, n_ctx_slot = 8192`）。

**队列 A（`WP3`，AC 核心，必须先跑）** —— 分两条路线，因为参数到达采样器的方式不同

| 路线 | 格 | cell | 题数 | 分钟 |
|---|---|---|---|---|
| R1 服务端参数（`m31` 模式） | A1–A6 | Qwen3.5-2B `UD-Q2_K_XL`/`UD-Q3_K_XL`/`UD-Q4_K_XL` × cpp/py，MultiPL-E raw，`-c 4096` | 161 × 6 | 50 |
| R1 | A7 | 同上 Q3，EvalPlus HumanEval（`evalplus.codegen --temperature 1.0`） | 164 | 9 |
| R2 逐请求参数（i02 的 `variant_panel` 臂） | A8–A10 | Qwen3.5-2B Q3，GSM8K / IFEval / MMLU，`-c 8192` | 50 / 50 / 456 | 4 |
| 合计 | | | | **≈63 分钟** |

- **为什么必须分两条路线**：`mpl_run.py` 的 raw 请求只带 `temperature`（`run_m31.sh` 的注释与代码都写了这一点），
  `evalplus.codegen` 的 CLI 只有 `--temperature`。所以代码列上 `top_p/top_k/min_p/presence_penalty` 只能**在起服时**传：
  `llama-server … -c 4096 --top-p 1.00 --top-k 20 --min-p 0.0 --presence-penalty 2.0 --seed 1234` + `mpl_run.py gen --temperature 1.0`，
  与 `m31` 完全同一模式（`run_m31.sh:66-68`）。这条路线下 `/props` 会显示全部五个量，**`/props` 就是生效证明**。
- **A7 是 i02 的 `CODEGEN_UNSUPPORTED` 漏掉的一格**：那道 guard 挡的是 `variant_panel` 自己的 codegen 调用；
  走 R1 时 EvalPlus 拿到的是服务端默认的 `top_p/top_k/min_p/presence_penalty` 加 CLI 的 `--temperature 1.0`，四个量没有被丢。
  若不愿走 R1，就把 A7 登记为「该臂的 code 列显式未测 + 理由」，**不要**用 temp 0.7 顶替。
- **ctx 不同就不能混**：R1 用 `-c 4096` 是为了与 `m3`/`m27`/`m31` 的 cpp/py 锚点逐列同协议；R2 用 `-c 8192` 是为了与 `m131` 同协议。
  两边的格**不许**互相池化，协议串会带 `sampling=` 段与各自的 ctx。
- **A10 是正控不是测量**：MMLU 走对数似然、不采样，所以它在厂商档上必须仍是 `0.6075`；变了说明链路坏了，不是采样效应。
- **seed 固定为 1234**：与 `m27`/`m31` 同 seed，使 R1 的六个格与既有锚点只差采样参数这一项。代价是单次抽样，分不开「一次抽样」与「分布」，
  所以 R1 的结论只能写「在这一档取值下」，要分布就得加重复（见 `WP4` 之外的后续）。
- 入库后的判据：`rank_survival.py` 的 `SELECTION` 加一行 `("vendor", …, WHERE run_tag = '<新 tag>' AND temp = '1.0'`, True)，
  `--write` 后 `--check` 退出 0；`rank_summary.tsv` 的 cpp `Q3>Q4` 行由 `inverts` 或 `survives` 给出答案。
- 触发条件（三条全满足才起服）：① `.wrapup/variant_panel.py` 的 `vendor-recommended` 改动**已提交到 main**（当前它还是工作区的 ` M`，不算数）；
  ② `bash .wrapup/gpu_locked.sh true` 能立刻拿到锁；③ `nvidia-smi --query-gpu=memory.free` ≥ 3800 MiB。
  任一不满足就排队，不占用槽。

**队列 B（`WP4`，可裁）**

| 格 | cell | 题数 | 分钟 |
|---|---|---|---|
| B1–B4 | 另一家族的 ≥2 档 × cpp/py，厂商档 | 161 × 4 | 34 |

- 首选 `Llama-3.2-3B-Instruct` 的 `Q2_K`（1.364 GB）+ `Q3_K_M`（1.687 GB）：它是唯一「跨家族 + 成本低 + cpp 与 py 两语言在贪心下都有两档」的组合；
  门槛按 1.687 GB 权重折算出约 2.2 GiB，取 `memory.free ≥ 4500 MiB`。
- 它需要**自己的**厂商值（Llama 的卡与 Qwen 的不同），所以 `SELECTION` 会多一行 setting，不共用 A 的值。
- 规模阶梯（0.8B / 4B / 9B 各两档 × 两语言 = 12 格 ≈ 100 分钟）**显式不做**：AC 不依赖它，且要给三个尺寸各取一次厂商卡。
  它记在这里是为了让人知道代价，而不是被忘掉。

**已做但不占额的先行检查**：起服一次读 `/props` 与 `n_slots`（10 秒，已做，见 `RESULT.md::res-vram-and-props`）。

## 资源实测（对批准预算的对照）

| 项 | 批准 | 实测 | 差 |
|---|---|---|---|
| R2 三格 | 4 分钟 | 6.3 分钟（08:08:06→08:14:23） | +2.3，原因：temp 1.0 下生成更长 |
| R1 单格（`q2`） | 7.1 分钟（6.7 × 1.25） | q2-cpp 8.5、q2-py 6.0 | −1.1 ~ +1.4 |
| R1 单格（`q3`） | 7.1 分钟 | q3-cpp 10.3 | **+3.2** |
| R1 七格 + EvalPlus | 59 分钟 | 预计 68–75 分钟 | **+9 ~ +16** |

- **估算偏低的原因（写进资源实测）**：单格成本主要由**输出长度**决定，而输出长度随量化档上升——厂商档下 q2 的平均补全 115 词量级、q3 更长且更啰嗦（`vendor-collapse-mechanism` 的 115.4 词 vs 贪心 71.9 词），生成时间与 `SyntaxError` 格的重编译时间一起膨胀。批准时的 6.7 分钟/格 是从 `m27`/`m31` 的**贪心与 temp 0.3** 面板量出来的，那两档的输出长度比厂商档短，所以这个外推在跑之前不可能准确。
- 复算：`grep -aE "^\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] (server|gen|DONE)" .wrapup/mres/m165-vendor/vendor_r1.log`

## 排队：机制判别（价格，待批）

| 项 | 内容 | 价格 |
|---|---|---|
| M1（**已批准，已排队**） | `q3-cpp` 的 40 题**探针**：只把 `presence_penalty` 置 0，其余不动 | **3–4 分钟**（按 q3-cpp 全格 10.3 分钟 × 40/161 + 起服约 40 秒）|
| M2 | 同上的 161 题全格（若 M1 方向明确且需要可与 39/161 并列的数） | 11 分钟 |
| M3（可选） | 补 2×2 的第四格：`presence_penalty=2.0` + `top_p=0.95` + `min_p=0.05` | 11 分钟 |
| 合计（M1+M2 或 M1+M3） | 二选一即可回答「H-A 主因还是 H-B 主因」；M1+M2+M3 才能分别归因 | 14–26 分钟 |

- 探针（M1）**不是分数**，不与 161 题格同权读；它只用来定方向（`AGENTS.md` 的探针规则）。
- **M2（已批准，已排队）**：`TAG=m2 TOP_P=0.95 MIN_P=0.05 PRES=0.0`，即保持 `presence_penalty=0`、`temp 1.0`，只把两个截断量回到固定协议的值，同样 40 题。塌陷消失 ⇒ H-B（无约束尾部）成立；仍塌 ⇒ 指向温度 1.0 本身。脚本已参数化（同一份 `run_m1_probe.sh`，五个量与环境变量可覆盖），排队进程 `flock` 在 a07 的 `m167/m168` 之后，**触发条件 = 拿到锁**。
- **M1 的排队状态**：脚本 `run_m1_probe.sh` 已经以 `bash .wrapup/gpu_locked.sh bash run_m1_probe.sh` 提交（pid 3701095），当前在 `/tmp/llama_gpu.lock` 上等 a07 的 `m166-spec-ident` 任务；**触发条件 = 拿到锁**（`flock` 自动继续，不需要人再操作）。产物目录 `.wrapup/mres/m165-mechanism/`，日志 `m1_probe.log`，结果行 `m1_summary.jsonl`。
- 判别逻辑与两侧结论写在 `RESULT.md::vendor-collapse-mechanism`，跑之前不得改。

## 派工与资源

- GPU：占 4 周周期的 7%，全局串行，任何 GPU 任务必须在 `bash .wrapup/gpu_locked.sh` 下跑，一次一个；
  起服前看 `nvidia-smi` 的 `memory.free`（同一张卡上还有别的仓库的任务，`/tmp/llama_gpu.lock` 只管本仓库），
  起服后断言 server 自报的 `n_slots` 与 `-np` 相符，不符即作废该次测量。
- CPU：5%，两个并发以内；普查与逐题分析都是秒级只读脚本。
- 改库前做编号备份（`experiments.sqlite.bakN`），入库只走 `migrate_db.py`（见 `AGENTS.md`）。

## 已测未入库（`m165-vendor`）：入库前排序判据不含这些格

- 进度（按格追加，完成一格记一行；GPU 分钟按 `[HH:MM:SS]` 行计差）：

| 格 | 分数 | 协议串 | 状态 |
|---|---|---|---|
| R2 mmlu（正控） | 0.6075（= 贪心，未变） | — | 完成 |
| R2 gsm8k | 0.40（贪心 0.60 / t0.3 0.64 / t0.7 0.62） | — | 完成 |
| R2 ifeval | 0.60（贪心 0.62 / t0.3 0.70 / t0.7 0.66） | — | 完成 |
| R1 q2-cpp | **1/161 = 0.0062**（贪心 18/161 = 0.1118） | `mpl-raw-t1.0-768;ctx=4096;sampling=temp=1.0,top_p=1.0,top_k=20,min_p=0.0,presence_penalty=2.0` | 完成，8.5 GPU 分钟；状态 `SyntaxError=142,Exception=18,OK=1` |
| R1 q2-py | **3/161 = 0.0186**（贪心 22/161 = 0.1366） | 同上 | 完成，3.8 GPU 分钟；状态 `Exception=158,OK=3` |
| R1 q3-cpp | **4/161 = 0.0248**（贪心 39/161 = 0.2422） | 同上 | 完成，10.3 GPU 分钟；状态见 `histograms.jsonl` |
| R1 q3-py | **7/161 = 0.0435**（贪心 43/161 = 0.2671） | 同上 | 完成，3.3 GPU 分钟（输出短，故快）；状态见 `histograms.jsonl` |
| R1 q4-cpp | **6/161 = 0.0373**（贪心 37/161 = 0.2298） | 同上 | 完成，12.7 GPU 分钟；状态见 `histograms.jsonl` |
| R1 q4-py | **12/161 = 0.0745**（贪心 44/161 = 0.2733；`Exception=147`，阈值之上但同属例外地板） | 同上 | 完成，4.4 GPU 分钟 |
| R1 q3-EvalPlus HumanEval | **59/164 = 0.3598**（贪心 94/164 = 0.5732），plus 0.329 | 同上 + `;bench=evalplus-humaneval` | 完成，14.3 GPU 分钟（temp 1.0 下每题约 950 token） |
| **R1 合计** | — | — | **七格完成，08:14:36→09:14:09 = 59.6 GPU 分钟**（批准 59，几乎持平；单格方差 3.3–14.3） |

- **cpp 侧的预注册结局已触发**：Q3（4/161）与 Q4（6/161）都 `at_floor`，所以 cpp 的结论是「该采样值下 cpp 阶梯不可分辨」，不写 survives 也不写 inverts。py 侧等 q4-py。

- 状态直方图由 `cell_histograms.py` 从 `*_eval.json` 重算，写入 `.wrapup/mres/m165-vendor/histograms.jsonl`（幂等，可随跑随算）。
- 两个已完成格的塌陷形态**不同**：cpp 是 `SyntaxError=142`（输出不是合法 C++），py 是 `Exception=158`（代码能解析但跑不起来）。所以「塌陷」的证据是状态分布，不是分数。

## 预注册的判定规则（在看到 q3/q4 之前写死，不得事后改口）

「厂商档下量化阶梯是否存活」按下面三档判，判据只用 `histograms.jsonl` 的 `at_floor` 与 `score`：

| 情形 | 结论怎么写 | 禁止写法 |
|---|---|---|
| Q3 与 Q4 **都** `at_floor`（pass share < 0.05） | **「该采样值下 cpp/py 阶梯不可分辨」**：这一档的分数落在地板上，地板格之间的差不是能力差 | 不写 `survives`，也不写 `inverts`；不把地板格与贪心格并列做「差了多少」 |
| 只有 Q2 `at_floor`，Q3/Q4 在地板之上 | 「阶梯在**一档不可测**的前提下存活/反序」，并给出 Q3-vs-Q4 的 survived/inverted | 不把 Q2 纳入档对比较（它是地板格） |
| 三档都在地板之上 | 按 `rank_survival.py` 的口径照常给 survived/inverted | 不因为「方向符合预期」就省掉反序计数 |

- 这条规则的依据：`vendor-arm-is-not-a-perturbation` 已经证明地板存在（cpp 1/161、py 3/161），所以「先看数再选口径」的风险是真的。
- **`0.05` 不是一个通用阈值，它来自这条阶梯自己的数**：该阶梯最低的贪心格是 Q2 cpp 18/161 = 0.1118（其余贪心格更高），而已测的两格塌陷是 1/161 = 0.0062 与 3/161 = 0.0186，所以 0.05 落在两者之间、离两边都超过 2 倍。换一条阶梯或换一个基准就必须重新算，不能照搬。
- **直方图优先于阈值**：若某格分数落在 0.05 附近，但 `status_histogram` 显示的是另一种失效机制（例如 `Timeout` 主导、或 `OK` 占比高而分数低），按直方图判并在 `RESULT.md` 写明，不硬套 0.05。阈值只是把「明显塌陷」和「明显没塌陷」分开的粗线，判据的最后一句由状态分布说。
- 该规则与 `rank_survival.py` 的关系：地板格**不进** `SELECTION`；`--check` 通过只说明 fixture 与库一致，不说明地板格可以参与排序。

- 产物目录 `.wrapup/mres/m165-vendor/`；逐格清单 `.wrapup/mres/m165-vendor/vendor_r1_summary.jsonl`（R1）与 `variant_panel.json`（R2）；
  运行脚本 `run_vendor_arm.sh`（R1）与 `vendor_arm_r2.py`（R2）。
- **在 `migrate_db.py` 补上 `vendor-recommended` 的 ingest 之前，这 10 个格不进 `experiments` 表，因此也不在 `rank_survival.py` 的判据里。**
  这不是通过，是尚未纳入：`rank_survival.py --check` 现在退出 0 而它根本看不到这批格。补 ingest 之后必须把 `SELECTION` 加一行再 `--write` + `--check`。
- 已做的生效判别与依据见 `RESULT.md::vendor-param-effect`（`/props` 回显五个量 + `top_k=1`/`top_p=0.1` 重现贪心的塌缩判据，两条端点各 2 个 prompt，32 项检查 31 项 PASS）。
