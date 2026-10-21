# a08 思考开关 — 结果

每条事实的形状：结论 / `- evidence:`（可重跑的命令或落盘文件）/ `- repro:`。
未测的写「未测 + 理由 + 解除条件」，不填默认值。数字只从
`analysis/thinking_pairs.py --write` 产出（`--check` 复算，`--selftest` 证明会变红）。

## 答案摘要（每落地一条臂就更新这一节）

问题：报告的聊天协议固定关思考，那么**分数里有多少可归因于这个协议选择**？

| 基准类 | 开/关对照 | 同预算下的差 | 生成 token（成本，实测） | 墙钟（实测，**不作协议比**，见 res4） | 状态 |
|---|---|---|---|---|---|
| 推理类 gsm8k | `a08-gsm8k-off-4096` 0.67 vs `m66gs-gsm8k` 0.34（都 4096） | **−33 题 / 100**（非配对 95% 区间 [−0.46, −0.20]，可分） | 关 27 967 → 开 199 025，**7.1×**；撞满 4096：关 **1/100**、开 **26/100** | 198.0 s → 664.3 s | 已测 |
| 抽取类 ifeval | `a08-ifeval-off-25` 0.60 vs `a08-ifeval-on-25` 0.04（都 4096，25 题） | **−14 题 / 25**（截断强制失败至少解释 **93%**） | 关 6 645 → 开 99 335，**15.0×**；撞满 4096：关 **0/25**、开 **23/25** | 64.3 s → 558.8 s | 已测 |
| 知识-对数似然类 mmlu | `a08-mmlu-off-16` 0.622807 vs `a08-mmlu-on-16` 0.622807（n=912，该对记录在 `max_gen_toks=1024`） | **0（聚合值相同）** | 不生成（prompt logprob）；原始 completions 端点对开关逐字无反应 | 238 s ↔ 195 s（同一张卡的负载波动） | 已测（一个模型、一个任务） |
| 代码类 humaneval/mbpp/MultiPL-E | 无 | 不可得 | — | — | **未测**（619 个 EvalPlus `auto` 格没记 reasoning；`off` 格无 on 对照）|

**本轴主结论（凡涉及预算处都只在「生成预算 4096」这一档成立；对数似然类不生成、不涉及预算）**：
打开思考改的不是「答得好不好」，而是**把生成预算吃掉**。

| 类 | 机制（同一对臂里被测量到的） | 实测差 |
|---|---|---|
| 知识-对数似然（mmlu，n=912） | 不生成：分数来自 prompt logprob；原始 completions 端点对 `--reasoning` 逐字无反应 | 0.622807 vs 0.622807，**0 题（逐位相同）** |
| 抽取（ifeval，n=25） | 23/25 题把 4096 全花在思考上，`content` 拿不到完整响应 | 0.60 → **0.04**（−14 题），token 15×，墙钟 8.7× |
| 推理（gsm8k，n=100） | 26/100 题撞满 4096，其余题也付 ≈1990 token/题 | 0.67 → **0.34**（−33 题），墙钟 3.35× |

所以「报告的聊天分数里有多少可归因于关思考」的答案是：**对数似然类是 0**（同一批题的聚合分与 stderr 都相同；
逐题集合**未验证**，见 res7），**生成类则基本是「预算够不够」的函数**——在 4096 这一档，关思考只用
1/7.1（gsm8k）与 1/15（ifeval）的生成 token 就多拿 33/100 与 14/25 题。

差里有多少是**预算饥饿**、多少是「思考更笨」，这份数据能做的是给**上下界**（不是点估计）：
- ifeval：23/25 题撞满 4096，这 23 题**必然**判错，所以开思考侧的理论上限是 2/25 = 0.08；
  于是差距的 **≥93%**（(0.60−0.08)/(0.60−0.04)）是被截断强制掉的，剩下的 ≤7% 才是「换答案」。
- gsm8k：撞满的 26 题最多贡献 26 题，所以**至多 79%**（26/33）的差距能归给截断，
  **至少 7 题**是没被截断的题真的答错了 —— 这一类里「预算饥饿」不能解释全部。
- granite-4.1-3b-Q2_K 是有 10/100 撞满却**分数与关思考相同**（0.12 对 0.12）的一档，说明截断未必落到判分上
  （那些被截断的题在关思考下本来也错）。

要把「饥饿」与「思考更笨」分开，只能把预算提到 8192/16384 重跑同一对：**未测**，
逐臂报价（含必须同时抬 ctx 的约束）见 res11 第 6 条。

**AC 状态（对 PLAN.md 的四条 AC 逐条）**
1. 每类基准一对开关：推理类 ✓（gsm8k 100 题）、抽取类 ✓（ifeval 25 题）、知识-对数似然类 ✓（mmlu 912 题，
   一个模型一个任务）、代码类 ✗ **未测**（报价见 res11 第 1 条）。
2. 开/关是**两个协议**、永不池化：写在 `analysis/thinking_pairs.py` 的配对规则里（`reasoning` 与
   `protocol`/`max_tokens`/`ctx` 同级进身份），由 `fixtures/thinking_pairs.tsv` 的 `budget_matched` 列与
   `--check`/`--selftest` 守住（res5）。
3. 未测项列全：res11 六条，每条带「为什么现在测不了 + 解除条件 + 报价」。
4. 复算入口在干净 clone 里 rc=0（res5）。


## res1 :: 历史上 13 个思考开的格全部落在 gsm8k；本轮补了 ifeval 与 mmlu 各一格，代码类仍是 0

这是这一轴最硬的一条：**在本轮补测之前，报告的聊天分数里只有推理类（gsm8k）有开/关两种测量**，
抽取类（ifeval）、知识-对数似然类（mmlu/arc/truthfulqa）、代码类（humaneval/mbpp）在库里只有关思考的格。
数字（以提交态的库为准）：gsm8k `off` **105** / `on` 13；gsm8k-strict `off` 76 / `on` 13；
ifeval `off` **109** / `on` **1**（本轮补的那格）；mmlu `off` **109** / `on` **1**（本轮补的那格）；
arc_challenge `off` 72、truthfulqa_mc2 `off` 79（`on` 都是 0）；humaneval `off` 845 + `auto` 400，mbpp `off` 612 + `auto` 219。
- evidence: `fixtures/reasoning_census.tsv`（每类每个 reasoning 值的格数与模型数）
- 具体见 `fixtures/reasoning_census.tsv`（每类每个 reasoning 值的格数与模型数）——上面那串数字就是它。
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`
- 推论（标为推断）：报告里抽取类与代码类的分数**完全不携带思考开关的信息**——不是因为开关无效应，
  而是因为从来没有测过开的那一侧。`auto` 的 619 个 EvalPlus 格尤其不能说成「开」或「关」：
  它们的 `protocol` 是 NULL，reasoning 设置不可知。

## res2 :: 13 个历史开关对里 8 对能配上关思考的基线，差是负的；但这 8 对预算不同，所以差不是纯思考效应

配上的 8 对（Qwen3.5-2B 族 7 档 + granite-4.1-3b-Q2_K），开侧 `max_gen_toks=4096`、
关侧 1024（关侧库列 NULL，预算取自它自己的 `lmeval_panel.json`）。分数差（flexible-extract，换成题数，n=100）：

| 模型 | off | on | Δ题数（flexible） | Δ题数（strict） |
|---|---|---|---|---|
| Qwen3.5-2B-UD-IQ2_M | 0.38 | 0.02 | −36 | 0 |
| Qwen3.5-2B-UD-IQ2_XXS | 0.06 | 0.01 | −5 | −1 |
| Qwen3.5-2B-UD-IQ3_XXS | 0.52 | 0.13 | −39 | +11 |
| Qwen3.5-2B-UD-Q2_K_XL | 0.44 | 0.09 | −35 | −30 |
| Qwen3.5-2B-UD-Q3_K_XL | 0.65 | 0.19 | −46 | −39 |
| Qwen3.5-2B-UD-Q4_K_XL | 0.66 | 0.34 | −32 | −5 |
| Qwen3.5-2B-UD-Q5_K_XL | 0.73 | 0.12 | −61 | −50 |
| granite-4.1-3b-Q2_K | 0.12 | 0.12 | 0 | 0 |

- evidence: `fixtures/thinking_pairs.tsv`（每对带 `budget_matched` 列，这 8 对全是 0）
- repro: 上表的每一行都能用 `awk -F'\t' '$2=="gsm8k" && $8==0' fixtures/thinking_pairs.tsv` 复读；
  中位数与极值：`python3 -c "..."` 见 res2b。
- **读法**：Δ 里同时含「开关」与「预算」两个变量，所以这 8 对**不能**读成「思考让 GSM8K 掉 32–61 题」。
  它们能读出的只有一件事：在这个研究实际用的小预算下，打开思考的 GSM8K 一律不高于关思考（8 对里 7 对更低，1 对相同）。
- 另有 5 个 on 格**没有**同模型同题量的关思考格（Qwen3.5-4B 三档、granite-4.1-3b-Q3_K_M/Q4_K_M），
  它们的基线率在本库里不可得，因此不参与任何结论：`fixtures/thinking_pairs.tsv` 里标 `NO-OFF-CELL`。

## res2b :: 这 8 对的分数差在这份数据里的中心与极值

- evidence: flexible 差（题数）排序 = [−61, −46, −39, −36, −35, −32, −5, 0]，中位数 −35.0；
  strict 差排序 = [−50, −39, −30, −5, −1, 0, 0, +11]，中位数 −1.0。
  **两把尺子给出不同的中心**（−35 对 −1），因为 strict-match 要求字面 `#### N`：开思考的响应即使答对也常常不带这个格式。
  这就是 res1 里「同一批响应在两把尺子下不同」的机制，也是本研究只用 flexible 作主列的理由。
- repro: fixtures 里逐对可查；`python3 -c` 汇总见下一条命令的输出
  （`--check` 只保证 fixture 与重算一致，不重算这两个统计量，所以它们是**从 fixture 读出的派生值**）。

## res3 :: 打开思考的生成代价是每题 1.6k–4k token，而且最差的几档直接把 4096 预算打满

7 个 2B 档的 on 格可以逐请求数出来（它们的 panel 只跑了 gsm8k，日志能归给这一格）：

| 模型 | 生成 token/题 | 打满 4096 的题数 | 分数 | 墙钟 |
|---|---|---|---|---|
| IQ2_M | 3403 | 82/100 | 0.02 | 1507.7 s |
| IQ2_XXS | 4017 | 98/100 | 0.01 | 1454.6 s |
| IQ3_XXS | 1596 | 36/100 | 0.13 | 590.7 s |
| Q2_K_XL | 3299 | 78/100 | 0.09 | 994.7 s |
| Q3_K_XL | 1746 | 27/100 | 0.19 | 569.5 s |
| Q4_K_XL | 1990 | 26/100 | 0.34 | 664.3 s |
| Q5_K_XL | 2369 | 40/100 | 0.12 | 815.1 s |
| granite-4.1-3b-Q2_K | 491 | **10/100** | 0.12 | 211.0 s |
| Q5_K_XL | 2369 | 40/100 | 0.12 | 815.1 s |
| granite-3b-Q2_K | 491 | 0/100 | 0.12 | 211.0 s |

- evidence: `fixtures/thinking_cells.tsv` 的 `gen_tokens` / `gen_per_item` / `cap_hits` 列；
  原始日志随仓库走（`fixtures/logs/<tag>.server.log.gz` 加 `log_sha256`）。
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`
- 读法：**打满预算的题数就是「靠增大预算能不能救回来」的上界**。IQ2_XXS 有 98/100 题在 4096 处被截断，
  它的 0.01 不是「思考答错了」，而是「思考没写完」。
- **granite-4.1-3b-Q2_K 这一档要小心读**：它 491 token/题、但仍有 **10/100** 题撞满 4096
  （`zcat fixtures/logs/m68gs-gsm8k.server.log.gz | grep -c "/ 4096 tokens"` = 10），而分数与关思考相同
  （0.12 对 0.12）。所以「它没打满预算，因此 Δ=0 是干净的」这个推论**不成立**（早先版本这样写过，已撤回）：
  正确的说法是「它 10 题被截断、分数却没变，说明那些题在关思考下本来也错」。
- 于是 13 对里的负差至少有两条机制（截断 / 真的换了答案），而现有的逐题产物不足以分开它们
  （`log_samples` 没开，见 res11）。上下界见「答案摘要」那三条。

## res4 :: 成本要用生成 token 比，不能用墙钟比；墙钟比被吞吐差与固定开销污染

- token 比（稳健）：gsm8k 关 27 967 → 开 199 025 = **7.1×**；ifeval 关 6 645 → 开 99 335 = **15.0×**。
  evidence: `fixtures/thinking_cells.tsv` 的 `gen_tokens` / `gen_per_item`。
- 墙钟比（同样实测，但**不是干净的协议比**）：gsm8k 198.0 s → 664.3 s（3.35×）、ifeval 64.3 s → 558.8 s（8.7×）。
  两个原因，都从同一份日志读得到：
  1. **两臂的生成吞吐不同**：gsm8k 关臂 188 token/s、开臂 314 token/s（`gen_tokens / gen_ms`），
     而两条臂的 gguf blob、`llama-server` 版本、启动参数、`n_threads = 6` 都相同。
     时间上关臂跑的那一刻，卡上还有一个别的仓库的 `llama-server`（0.8B，见当时的 `ps`/`nvidia-smi` 记录），
     所以「吞吐差」最可能是**外部占用**；这一点**未证实**，不能当成协议效应。
  2. **固定开销稀释了小臂**：ifeval 两臂各含 ≈27 s 的加载与 prefill，于是 8.7× 的墙钟比小于 15.0× 的 token 比。
- **撤回**：早先版本写过「墙钟的超线性来自长序列解码的后段变慢」——被自己的日志否掉：
  逐请求 `tg` 在整个 4096 token 的生成里基本恒定（314 t/s 上下），没有后段变慢。
- 口径提醒：同一次 gsm8k 的 `timings_s` 是 1507.7 s，而 lm_eval 结果 json 的
  `total_evaluation_time_seconds` 是 662.6 s，两者不是同一件事；本轴一律用前者并只把它当「这一项要跑多久」的观测。
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`

## res5 :: 配对判据与复算入口（WP1 的 AC）

- evidence: `analysis/thinking_pairs.py` 三份 fixture 与两个模式 + `analysis/run_all.py`。
- 判据（写在脚本里，不靠记忆）：`reasoning` 不同的两格才配对；模型/基准/`n_items` 必须相同；
  `max_tokens` 不同则整对标 `budget_matched=0` 保留；库里 `max_tokens` 为 NULL 的格从它自己的 panel json 取值并记 `mt_source`。
- 复算：`--check` 在**没有** `.wrapup/mres` 的环境里也绿（`A08_MRES=/nonexistent ... --check` 实测 rc=0），
  因为面板 json 与日志 gz 随仓库走、sha256 绑定原文件。
- 负控：`--selftest` 把一份 fixture 副本改一行，检查必须变红（实测 rc=0 且打印 `PASS negative control`）。
- **干净 clone 里绿**：`git archive HEAD | tar -x -C /tmp/clone` 后在该目录跑
  `python3 "docs/subprojects/a08-思考开关/analysis/run_all.py"` → **rc=0**（28 对逐字一致、负控变红、
  5 条 rc=0 的臂身份闭合、三类基准各一对）。clone 里没有 `.wrapup/`，所以这条绿不依赖作者工作树。
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/run_all.py"`

## res6 :: 预算对齐的对照（WP2 的第一刀）：同一模型、同一 4096 预算，只改 `--reasoning`

Qwen3.5-2B-UD-Q4_K_XL、gsm8k、`--limit 100`、贪心、ctx 16384、`max_gen_toks=4096`，两条臂除
`--reasoning off/on` 外逐字相同：

| 臂 | 协议 | 分数（flexible） | 分数（strict） | 墙钟 |
|---|---|---|---|---|
| `a08-gsm8k-off-4096` | `lmeval-0.4.13-chat-reasoning-off` | **0.67** | 0.37 | **198.0 s** |
| `m66gs-gsm8k` | `lmeval-0.4.13-chat-reasoning-on` | **0.34** | 0.32 | **664.3 s** |

- 差 = **−33 题（n=100）**；非配对两比例 95% 区间（正态近似，差 −0.33、se = 0.067）≈ **[−0.46, −0.20]**，
  跨 0 之外；独立复核用另一种近似给出 [0.193, 0.450]（绝对值），结论一致。
- 成本用 token 比：27 967 → 199 025 = **7.1×**（墙钟 198.0 → 664.3 s 也实测，但按 res4 不作协议比）。
  这一对 `budget_matched=1`（两臂都 4096），所以这个差里只有「开关」一个变量。
- evidence: `fixtures/thinking_pairs.tsv` 里 `bench=gsm8k` 且 `off_tag=a08-gsm8k-off-4096` 的行；
  两条臂的 panel json 与 server.log 副本在 `fixtures/logs/`，`server.log` 里有 `n_slots = 1,`。
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`
- 同一模型的关思考格还有一档 1024 预算（`m66-qwen-2b-q4kxl`，0.66）。1024 → 4096 只让关思考多答对 1 题
  （+1 题，确定性解码下这是协议差而不是噪声），**所以 −33 题不是「关思考的预算太小」，而是思考串把预算吃掉了**：
  同一 on 臂 26/100 题在 4096 处被截断（res3 的 `cap_hits`）。
- 未测：4096 以上（8192/16384）能否救回被截断的 26 题 —— 且**必须同时抬 ctx**（见 res11 第 6 条）。

## res7 :: 知识-对数似然类：开关**逐位不改分**，而且机制上到不了那条路（两重证据）

同模型、mmlu `--limit 16`（每科，n=912）两条臂，只有 `--reasoning` 不同：

| 臂 | 协议 | 分数 | 墙钟 |
|---|---|---|---|
| `a08-mmlu-off-16` | `lmeval-0.4.13-gguf-shim-reasoning-off` | **0.6228070175438597** | 238.3 s |
| `a08-mmlu-on-16` | `lmeval-0.4.13-gguf-shim-reasoning-on` | **0.6228070175438597** | 195.3 s |

- 两个分数**聚合值相同**（0.6228070175438597，stderr 也相同），墙钟差 43 s 与协议无关（同一张卡的负载波动）。
- **未验证的是逐题集合**：判分是 912 题的对数似然 argmax，聚合值相同**不证明**两臂答对的题是同一批
  （`log_samples` 没开，没有逐题产物）。所以「开关对知识类零影响」这条要读成「聚合分与 stderr 相同」，
  不能读成「逐题完全相同」。
- 机制证据（`fixtures/endpoint_probe/`）：在原始 completions 端点上，`--reasoning on` 与 `off` 的响应**逐字相同**
  （`completions_on.json` 与 `completions_off.json` 的 `text` 一致，5 行重复文本一模一样），
  而在 chat 端点上同一提示的响应完全不同（on 有 `reasoning_content` 字段、292 token；off 只有 4 token 的 `content`）。
  也就是说：这一类的分数走的是 prompt logprob，开关到不了那条路。
- evidence: `fixtures/thinking_pairs.tsv`（`bench=mmlu` 行，`budget_matched=1`，`delta_items=0`）、
  `fixtures/endpoint_probe/{chat,completions}_{off,on}.json`
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`
- 结论的边界：这只测了 mmlu 一个任务、一个模型；arc_challenge / truthfulqa_mc2 未测（同类机制，但没测）。

## res8 :: 端点差分：`--reasoning on` 把推理流放进 `reasoning_content`，`content` 仍是最终答案

- chat 端点、同一提示（Natalia 卖夹子那道题）：
  - `off`：`content='192'`，`completion_tokens=4`，没有 `reasoning_content` 字段 —— **答错**（正确答案 72）。
  - `on`：`content='72'`，`reasoning_content` 是一整段 `Thinking Process:`（292 token）—— **答对**。
- evidence: `fixtures/endpoint_probe/chat_off.json`、`chat_on.json`、`README.txt`
- 读法：这是 n=1 的机制演示，不是分数结论；它证明两件事：(1) 开关真的改变了生成（不是空操作）；
  (2) 判分器看到的 `content` 里**没有**推理流，所以「IFEval 因为判分器看到推理流而掉到 0.00」这个旧解释
  在 build 4399 上不成立 —— 更可能的机制是推理流把预算吃光、`content` 返回空（finish_reason=length）。
  哪一种成立由 `a08-ifeval-on-25` 臂判：**判出来了，是预算被吃光**（res9：23/25 题撞满 4096）。

## res9 :: 抽取类：同一 4096 预算下，开思考把 IFEval 从 0.60 打到 0.04，代价 8.7× 墙钟

同模型、ifeval、`--limit 25`、贪心、`max_gen_toks=4096`、ctx 8192，两条臂只有 `--reasoning` 不同：

| 臂 | 协议 | prompt-level strict | inst-level strict | 生成 token/题 | 撞满 4096 的题数 | 墙钟 |
|---|---|---|---|---|---|---|
| `a08-ifeval-off-25` | `lmeval-0.4.13-chat-reasoning-off` | **0.60**（15/25） | 0.703 | 265.8 | **0/25** | 64.3 s |
| `a08-ifeval-on-25` | `lmeval-0.4.13-chat-reasoning-on` | **0.04**（1/25） | 0.054 | 3973.4 | **23/25** | 558.8 s |

- 差 = **−14 题 / 25**，墙钟 **8.7×**，token **15×**。这一对 `budget_matched=1`。
- 机制：关思考的 25 条响应最长 769 token、0 条撞满；开思考 23/25 条在 4096 处被截断（`server.log` 的逐请求
  `eval time = … / 4096 tokens`）。所以这个 0.04 是**「思考没写完」**，不是「指令检查器看到了推理流」——
  后者是 `docs/method/method.yaml` 协议表里的旧解释，在 build 4399 上被 res8 的端点差分推翻（推理流进
  `reasoning_content`，`content` 仍是干净的答案字段）。这条更正对报告有影响：旧的「开思考时 IFEval 0.00」
  不能再说成判分器缺陷。
- evidence: `fixtures/thinking_pairs.tsv`（`bench=ifeval` 行）、`fixtures/thinking_cells.tsv`（两格的
  `gen_per_item` / `cap_hits`）、`fixtures/logs/a08-ifeval-{off,on}-25.*`
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`
- 限制：n=25（prompt-level 粒度 4%）；IFeval 的严格判分还要求格式，截断必然连带格式失败，两者在现有产物里分不开。
- **这条贵臂的成本（实测，不是估计）**：`a08-ifeval-on-25` 一次 = 25 题 / **99 335 生成 token** /
  **gen 侧 531.4 s** / **整臂墙钟 558.8 s ≈ 9.3 min**（含 ≈20 s 加载与 25 次 prompt prefill），
  即 **187 token/s**；同题的关思考臂只要 64.3 s。按这个吞吐外推：25 题的 on 臂在 8192 预算下 ≈17 min、
  16384 下 ≈34 min（上界，假设撞满预算的 23 题都跑满新预算）。这也解释了为什么本轴把「一次调用一条臂」写死：
  单条贵臂就吃掉一次 turn 量级的时间，串六条臂必然被掐断。

## res10 :: 入库的账（WP3）：+8 行 = 本轴 5 格 + 别的子项目 3 格；同时发现共享入库路径有副作用

- 改库前：3323 行（其中 `source_file LIKE 'mres/%'` 915 行）；改后：3331 行（mres 923 行）。
  差额 +8 = 本轴 5 行（`a08-gsm8k-off-4096` 的 gsm8k 与 gsm8k-strict 两行、`a08-mmlu-off-16`、
  `a08-mmlu-on-16`、`a08-ifeval-off-25`）**+ `m165-vendor` 的 3 行**（a06 新面板，被同一次 refresh 读到）。
- 备份：`experiments.sqlite.bak30`（改前 3323 行，integrity ok，sha256 已打印在 `.tmp/a08_ingest1.out`）。
- **副作用（不是本轴代码引起，是共享 `migrate_db.py` 的当前状态）**：
  1. 32 行的 `protocol` 串被加上 `;sampling=default`（`variant-kv-*`、`variant-sampling-*`、`variant-multiturn` 等，
     分数不变、身份串变）——这是别的子项目已经改好但库里还没生效的那一版；
  2. **14 行 BFCL 多轮格的 `n_items` 从 200/其它值变成 NULL**（`m11/m14/m17/m19/m20/m22/m32/m36`），
     即当前 `ingest_*` 不再写这一列，refresh 把它抹了。
  这两条都不属于 a08 的写权范围，已上报 meta；`bak30` 是改前状态，可整库回滚或按格回填。
- 第二次入库（补 `a08-ifeval-on-25`）：备份 `experiments.sqlite.bak48`（3355 行，integrity ok），
  `rows 3355 -> 3355`，全列多重集差异 **added 0 / removed 0** —— 因为那一格在我入库前已被别的子项目
  的 refresh 写进去了（`campaign` 计数 788 → 789）。库里现在有本轴 6 格：
  `a08-gsm8k-off-4096`（gsm8k 0.67 / gsm8k-strict 0.37）、`a08-ifeval-off-25`（0.60）、
  `a08-ifeval-on-25`（0.04）、`a08-mmlu-off-16` 与 `a08-mmlu-on-16`（都是 0.622807）。
- evidence: `.tmp/a08_ingest1.out` 与 `.tmp/a08_ingest2.out`（备份行数与 sha256、逐 ingest 插入数、
  `rows … -> …`）、以及两次入库前后整库的全列多重集差异（脚本见提交前的命令记录）
- repro: 上面两个库（`bak30` 与当前库）的全列多重集差异命令见 `.tmp/a08_diff.py` 所在的记录；重跑即同结果。

## res11 :: 未测（不是 0）

1. **代码类（humaneval/mbpp/MultiPL-E）的开/关对照 —— 完全没有**：619 个 EvalPlus 格记的是 `reasoning='auto'`
   且 `protocol` 为 NULL（既不能算「开」也不能算「关」），31 个 `off` 格有协议但没有同模型的 `on` 格。
   解除条件：每族一个模型 × 两条臂，**且先证明 raw 补全模式下推理流不污染 completion**
   （a12 记过 gemma 在 raw 模式输出 `<|channel>thought`，那个 0 分不是量化效应）。报价：每臂
   raw 768 token、161 题 ≈8–12 min，每族两条臂 ≈20 min，三族 ≈60 min GPU。
2. **对数似然类的另外两个任务与其它模型族**：`arc_challenge`、`truthfulqa_mc2` 与除 Qwen3.5-2B-Q4_K_XL 外的
   任何模型都**没有**开关对照。机制上它们与 mmlu 同类（都走 EchoShim 的 prompt logprob、不生成），
   所以预期同样是 0，但**预期不是测量**。解除条件：一对臂 ≈4 min/任务/模型。
3. **前沿大模型族（27B–35B）**：一臂 27B @4096 ≈10–25 min/100 题（未实测，按 2B 的 ≈300 token/s 外推会低估），
   未排进本轮 2% 配额。
4. **逐题产物**：`log_samples` 没开，所以「哪些题翻转」不可得，只有聚合分与 token 计数。
   这直接限制了两条机制的分离（截断 vs 换答案），见 res3 与 res9。
5. **n 的粒度**：ifeval 只有 25 题（prompt-level 粒度 4%）；gsm8k 100 题、mmlu 912 题。
   若要把 ifeval 的差缩到 ±2% 以内，需要 100 题版本（on 臂 ≈37 min，off 臂 ≈4 min）。
6. **把预算提到 8192/16384（唯一能分开「预算饥饿」与「思考更笨」的实验）—— 未测，逐臂报价**：
   按 res9 实测吞吐（on 臂 187 token/s、off 臂 ≈300 token/s）与撞满预算的题数外推：

   | 臂 | 预算 | 生成 token（外推） | 墙钟（外推） | 需要的 ctx | 依据 |
   |---|---|---|---|---|---|
   | gsm8k on ×100 题 | 8192 | ≈305 k | **≈17 min** | 16384 够（1085+8192=9 277） | 26 题撞满 4096 → 各多跑 4096 |
   | gsm8k on ×100 题 | 16384 | ≈520 k（上界） | **≈29 min** | **必须抬到 ≥20 480**（1085+16384=17 469 > 16 384） | 26 题各多跑 12 288 |
   | ifeval on ×25 题 | 8192 | ≈193 k | **≈17 min** | **必须抬 ctx**（50+8192=8 242 > 8 192） | 23 题撞满 4096 |
   | ifeval on ×25 题 | 16384 | ≈382 k | **≈34 min** | **必须抬到 ≥20 480**（50+16384=16 434 > 16 384） | 23 题各多跑 12 288 |
   | 每对臂的关思考一侧 | 同预算 | 几乎不变（≈28 k / ≈7 k） | 3–4 min（gsm8k）/ 1 min（ifeval） | 同上 | 关侧只有 1/100 与 0/25 撞满 |

   **ctx 不是免费的一句备注**：早期版本的报价漏了它 —— 8192 预算在 ctx 8192 上根本跑不起来（提示已经占掉 ≈50–1085 token），
   而抬 ctx 会按比例增加每槽 KV 显存与 prefill 时间；所以上面每一行的墙钟仍然是**下界**，
   真实成本还要加上「ctx 翻倍带来的 KV 与 prefill」这一项（未测，2B + 20 480 ctx 实测显存占用见 a05 的记录可外推）。
   一对（开+关）在 8192 上 ≈20 min、在 16384 上 ≈32 min（都未含 ctx 抬升的代价）；两个类都做 ≈40–65 min GPU，超出本轴 2% 配额
   （≈13 h 四周）的单轮余量，所以本轮**没做**，报给 meta 决定要不要开。
