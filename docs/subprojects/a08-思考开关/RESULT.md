# a08 思考开关 — 结果

每条事实的形状：结论 / `- evidence:`（可重跑的命令或落盘文件）/ `- repro:`。
未测的写「未测 + 理由 + 解除条件」，不填默认值。数字只从
`analysis/thinking_pairs.py --write` 产出（`--check` 复算，`--selftest` 证明会变红）。

## res1 :: 库里有 13 个思考开的格，全部是 gsm8k；另外三类基准一个 open 格都没有

这是这一轴最硬的一条：**报告的聊天分数里，只有推理类（gsm8k）有开/关两种测量**，抽取类（ifeval）、
知识-对数似然类（mmlu/arc/truthfulqa）、代码类（humaneval/mbpp）在库里只有关思考的格。
- evidence: `fixtures/reasoning_census.tsv`（每类每个 reasoning 值的格数与模型数）
- 具体：gsm8k `on` 13 格 / 13 个模型，`off` 103 格 / 66 个模型；ifeval `off` 107 格 / 70 个模型、`on` 0；
  mmlu `off` 107、`on` 0；arc_challenge `off` 72、`on` 0；truthfulqa_mc2 `off` 79、`on` 0；
  humaneval `off` 845 + `auto` 400（EvalPlus 时代根本没记 reasoning），mbpp `off` 612 + `auto` 219。
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
| granite-3b-Q2_K | 491 | 0/100 | 0.12 | 211.0 s |

- evidence: `fixtures/thinking_cells.tsv` 的 `gen_tokens` / `gen_per_item` / `cap_hits` 列；
  原始日志随仓库走（`fixtures/logs/<tag>.server.log.gz` 加 `log_sha256`）。
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`
- 读法：**打满预算的题数就是「靠增大预算能不能救回来」的上界**。IQ2_XXS 有 98/100 题在 4096 处被截断，
  它的 0.01 不是「思考答错了」，而是「思考没写完」；granite-3b 一题都没打满（491 token/题），
  分数与关思考**逐位相同**（0.12 对 0.12），说明在它身上开关既没有帮助也没有伤害。
  所以 13 对里的负差至少有两条不同的机制（截断 / 真的换了答案），而现有的逐题产物不足以分开它们
  （`log_samples` 没开，见 res12）。

## res4 :: 墙钟代价 2.2×–11.2×，且与 token 数不成比例

- evidence: `fixtures/thinking_cells.tsv` 的 `wall_s`（harness 包住 `lm_eval` 的墙钟，
  来源 `lmeval_panel.json` 的 `timings_s`），配对比值在 `fixtures/thinking_pairs.tsv` 的 `wall_ratio` 列：
  2.23 / 3.73 / 4.71 / 5.58 / 5.62 / 6.20 / 8.05 / 11.24。
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`
- 注意两个口径不能混：同一次 gsm8k 的 `timings_s` 是 1507.7 s，而 lm_eval 结果 json 的
  `total_evaluation_time_seconds` 是 662.6 s。本轴一律用前者（面板包住整个 `lm_eval` 调用的墙钟，
  与用户感受到的「这一项要跑多久」对齐），并且不把两者混算。
- 2B 档的生成吞吐约 300 token/s（日志的逐请求 `tg` 列），所以 token 数并不解释全部墙钟：
  预算变大同时让 prompt 侧也要重算（`prompt_tokens` 全为 108490，说明 5-shot 提示是同一份），
  墙钟的超线性来自长序列解码的后段变慢，这一点**没有单独测量**，只是从同一份日志读到的形状。

## res5 :: 配对判据与复算入口（WP1 的 AC）

- evidence: `analysis/thinking_pairs.py` 三份 fixture 与两个模式 + `analysis/run_all.py`。
- 判据（写在脚本里，不靠记忆）：`reasoning` 不同的两格才配对；模型/基准/`n_items` 必须相同；
  `max_tokens` 不同则整对标 `budget_matched=0` 保留；库里 `max_tokens` 为 NULL 的格从它自己的 panel json 取值并记 `mt_source`。
- 复算：`--check` 在**没有** `.wrapup/mres` 的环境里也绿（`A08_MRES=/nonexistent ... --check` 实测 rc=0），
  因为面板 json 与日志 gz 随仓库走、sha256 绑定原文件。
- 负控：`--selftest` 把一份 fixture 副本改一行，检查必须变红（实测 rc=0 且打印 `PASS negative control`）。
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/run_all.py"`

## res7 :: 预算对齐的对照（WP2 的第一刀）：同一模型、同一 4096 预算，只改 `--reasoning`

Qwen3.5-2B-UD-Q4_K_XL、gsm8k、`--limit 100`、贪心、ctx 16384、`max_gen_toks=4096`，两条臂除
`--reasoning off/on` 外逐字相同：

| 臂 | 协议 | 分数（flexible） | 分数（strict） | 墙钟 |
|---|---|---|---|---|
| `a08-gsm8k-off-4096` | `lmeval-0.4.13-chat-reasoning-off` | **0.67** | 0.37 | **198.0 s** |
| `m66gs-gsm8k` | `lmeval-0.4.13-chat-reasoning-on` | **0.34** | 0.32 | **664.3 s** |

- 差 = **−33 题（n=100）**，墙钟 **3.35×**。这一对 `budget_matched=1`（两臂都 4096），所以这个差里
  只有「开关」一个变量 —— 这是本轴第一条能归因于思考开关的分数差。
- evidence: `fixtures/thinking_pairs.tsv` 里 `bench=gsm8k` 且 `off_tag=a08-gsm8k-off-4096` 的行；
  两条臂的 panel json 与 server.log 副本在 `fixtures/logs/`，`server.log` 里有 `n_slots = 1,`。
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`
- 同一模型的关思考格还有一档 1024 预算（`m66-qwen-2b-q4kxl`，0.66）。1024 → 4096 只让关思考多答对 1 题
  （+1 题，确定性解码下这是协议差而不是噪声），**所以 −33 题不是「关思考的预算太小」，而是思考串把预算吃掉了**：
  同一 on 臂 26/100 题在 4096 处被截断（res3 的 `cap_hits`）。
- 未测：4096 以上（8192/16384）能否救回被截断的 26 题。成本 ≈45–90 min/100 题，未排。

## res8 :: 知识-对数似然类：开关**逐位不改分**，而且机制上到不了那条路（两重证据）

同模型、mmlu `--limit 16`（每科，n=912）两条臂，只有 `--reasoning` 不同：

| 臂 | 协议 | 分数 | 墙钟 |
|---|---|---|---|
| `a08-mmlu-off-16` | `lmeval-0.4.13-gguf-shim-reasoning-off` | **0.6228070175438597** | 238.3 s |
| `a08-mmlu-on-16` | `lmeval-0.4.13-gguf-shim-reasoning-on` | **0.6228070175438597** | 195.3 s |

- 两个分数**逐位相同**（同一个 912 题的正确答案集合），墙钟差 43 s 与协议无关（同一张卡上的负载波动）。
- 机制证据（`fixtures/endpoint_probe/`）：在原始 completions 端点上，`--reasoning on` 与 `off` 的响应**逐字相同**
  （`completions_on.json` 与 `completions_off.json` 的 `text` 一致，5 行重复文本一模一样），
  而在 chat 端点上同一提示的响应完全不同（on 有 `reasoning_content` 字段、292 token；off 只有 4 token 的 `content`）。
  也就是说：这一类的分数走的是 prompt logprob，开关到不了那条路。
- evidence: `fixtures/thinking_pairs.tsv`（`bench=mmlu` 行，`budget_matched=1`，`delta_items=0`）、
  `fixtures/endpoint_probe/{chat,completions}_{off,on}.json`
- repro: `python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check`
- 结论的边界：这只测了 mmlu 一个任务、一个模型；arc_challenge / truthfulqa_mc2 未测（同类机制，但没测）。

## res9 :: 端点差分：`--reasoning on` 把推理流放进 `reasoning_content`，`content` 仍是最终答案

- chat 端点、同一提示（Natalia 卖夹子那道题）：
  - `off`：`content='192'`，`completion_tokens=4`，没有 `reasoning_content` 字段 —— **答错**（正确答案 72）。
  - `on`：`content='72'`，`reasoning_content` 是一整段 `Thinking Process:`（292 token）—— **答对**。
- evidence: `fixtures/endpoint_probe/chat_off.json`、`chat_on.json`、`README.txt`
- 读法：这是 n=1 的机制演示，不是分数结论；它证明两件事：(1) 开关真的改变了生成（不是空操作）；
  (2) 判分器看到的 `content` 里**没有**推理流，所以「IFEval 因为判分器看到推理流而掉到 0.00」这个旧解释
  在 build 4399 上不成立 —— 更可能的机制是推理流把预算吃光、`content` 返回空（finish_reason=length）。
  哪一种成立由 `a08-ifeval-on-25` 臂判（见 res10）。

## res10 :: 抽取类的关思考基线已经测到，开思考一侧待一条臂

- `a08-ifeval-off-25`：ifeval、25 题、`max_gen_toks=4096`、贪心 → **prompt_level_strict 0.6**，墙钟 64.3 s。
- 开思考那一臂（同 25 题、同 4096 预算）**尚未得数**：第一次尝试被记录为 `rc=port-busy`（上一条臂的 server
  还在退出时端口仍被占用，`fixtures/arm_runs.tsv` 有这一行），第二次在锁队列里等（`A08_LOCK_WAIT=1800`）。
  在它落地之前，`RESULT` 里**没有**任何 ifeval 的开关结论。
- evidence: `fixtures/arm_runs.tsv` 的 `a08-ifeval-off-25` / `a08-ifeval-on-25` 两行

## res11 :: 入库的账（WP3）：+8 行 = 本轴 5 格 + 别的子项目 3 格；同时发现共享入库路径有副作用

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
- evidence: `.tmp/a08_ingest1.out`（备份行数与 sha256、逐 ingest 插入数、`rows 3323 -> 3331`）、
  本文件上一条命令的全列多重集差异
- repro: 上面两个库（`bak30` 与当前库）的全列多重集差异命令见 `.tmp/a08_diff.py` 所在的记录；重跑即同结果。

## res12 :: 未测（不是 0）

1. **抽取类（ifeval）的开/关对照**：库里 `on` 格 0 个。历史笔记说开思考时 IFEval 跌到 0.00、
   每题 27 s 对 5 s（`docs/method/method.yaml` 的协议表，出处是早期 campaign 的口头记录），
   **没有可复算的产物**，所以本文件不引用它作为结果。解除条件：一句 `run_thinking_arms.py` 的臂，
   ≈25–35 min GPU（本轮已排）。
2. **知识-对数似然类（mmlu/arc/truthfulqa）的开关**：这类走 EchoShim 的 prompt logprob，
   不是自由生成，`--reasoning` 是否触及它**没有测量**。解除条件：一对 mmlu 臂，≈8 min GPU（本轮已排）。
3. **代码类（humaneval/mbpp/MultiPL-E）**：619 个 EvalPlus `auto` 格没记 reasoning，31 个 `off` 格有协议但无 on 对照。
   解除条件：每族一个模型 × 两条臂，且先证明 raw 补全模式下推理流不污染 completion（gemma 曾输出 `<|channel>thought`）。
   预算 ≈20–60 min GPU。
4. **前沿大模型族（27B–35B）**：一臂 27B @4096 ≈10–25 min/100 题，未排进本轮 2% 配额。
5. **逐题产物**：`log_samples` 没开，所以「哪些题翻转」不可得，只有聚合分与 token 计数。
   这直接限制了两条机制的分离（截断 vs 换答案），见 res3。
6. **预算响应的形状**：关思考在 1024 与 4096 两个预算下的差已测（+1 题，见 res7），
   以及开思考在 8192/16384 下是否能救回被截断的题——后者成本 ≈45–90 min/100 题，**未排**。
