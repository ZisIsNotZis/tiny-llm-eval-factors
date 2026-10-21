# a08 思考开关 — 计划

## 现在（每次改动都要让这一节为真）

- **里程碑 M1「研究结束」未达成**；只剩一个里程碑，结项条件是下面 AC 全绿。
- **在做**：WP2「预算对齐的受控臂」——六条臂在 GPU 锁里排队（在 `a06` 的厂商臂之后）。
- **剩余**：WP3 入库、WP4 结论与未测清单、WP5 独立复核。
- **下一个派给谁**：a08 worker 继续 WP2（臂跑完 → WP3）；WP3 落地后派 fresh reviewer 做 WP5。

## 这一轴要回答什么

项目的聊天协议固定 `enable_thinking: false`。要判的是：**开关思考会改变分数、生成 token 数与延迟吗**，按基准类与模型族分开，
以及「报告里的聊天分数有多大比例可以归因于这个协议选择」。

AC（可证伪）：
1. **每一类基准都有一对只差开关的对照**，或显式记「未测 + 理由 + 解除条件」。类 = 推理类（gsm8k）、抽取类（ifeval）、
   知识-对数似然类（mmlu/arc/truthfulqa）、代码类（humaneval/mbpp/MultiPL-E）。
2. 每个对照给 **分数差（题数）、生成 token 数、墙钟**，并说明该对的预算是否对齐（`max_tokens` 相同才算对齐）。
3. 每条结论在 `RESULT.md` 里带 `- repro:`，由 `analysis/thinking_pairs.py --check` 与 `analysis/run_all.py` 复算。
4. 未测项写清「为什么现在测不了、解除要多少钱/什么条件」，不填默认值。
5. 独立复核在干净 clone 里跑 `run_all.py` 并贴命令与输出。

判据来源（不自造分界）：
- **确定性解码地板 = 0 道题**（i01：四族 161/164/100/40 逐题全同），所以固定协议下的逐格差是真实协议效应，不是噪声；
  但那是同协议重复的地板，跨协议比较不需要它。
- **量化标签效应的分辨率 0.10–0.49**（a03）：小于这个量级的差在旧设计里没有分辨力，本轴的效应若落在这个区间，
  只能说「与标签效应不可分辨」，不能说「没有效应」。
- **`--reasoning off` 忘掉的活故障**（i01）：某次漏掉 `--reasoning off` 让整批响应变 `[invalid]`。
  所以本轴任何 `on` 臂都必须同时记录「响应是否还是有效文本」，否则 0.00 无法与「判分器吃掉了推理流」区分。

## 工作包

| id | 工作包 | owner | 依赖 | 预算 | AC（可证伪） | 状态 |
|---|---|---|---|---|---|---|
| WP1 | 清点库里已有的开/关格，定配对与预算混淆的判据，落三份 fixture | a08 worker | — | 0 GPU，CPU 分钟级 | `analysis/thinking_pairs.py --check` 与 `--selftest` 退出 0；`fixtures/thinking_pairs.tsv` 每对都标出 `budget_matched` | **完成** |
| WP2 | 跑预算对齐的受控臂：gsm8k off/on @4096、ifeval off/on @4096（50 题）、mmlu off/on（16/科） | a08 worker | WP1；GPU 锁 | ≈70 GPU 分钟（≤4 GB 显存、独占锁内），CPU ≈1 核 | 每条臂的 `lmeval_panel.json` 里 `reasoning`/`max_gen_toks`/`ctx` 与臂定义一致，`server.log` 有 `n_slots = 1`；六臂全得数或显式失败 | **进行中** |
| WP3 | 入库：编号备份 → `migrate_db.py` → 行数对账 → 重算 fixture | a08 worker | WP2 | CPU 分钟级 | 改库前后行数差 = 本轴新增格数（逐条列出）；`db_check` 绿；skip ledger 为空 | 待 WP2 |
| WP4 | `RESULT.md` 结论 + 未测清单 + 报告面交接说明 | a08 worker | WP3 | CPU 分钟级 | 每条结论一条 `- evidence:` 一条 `- repro:`；未测项带理由与解除条件；不出现无出处数字 | 待 WP3 |
| WP5 | 独立复核（fresh reviewer，非本 worker） | meta 派 | WP4 | 一次复核预算 | 干净 clone 里 `python3 "docs/subprojects/a08-思考开关/analysis/run_all.py"` 贴出命令与退出码；P1 类缺陷为零 | 待 WP4 |

## 已知的坑（从别的子项目继承，不改）

1. **历史 on 格全部预算混淆**：13 个 gsm8k `on` 格跑在 `max_gen_toks=4096`，对应的 `off` 格是 1024。
   两者之差同时含「开关」与「预算」两个变量，所以只能作为观测记录，不能读成思考效应 —— WP2 就是补这一刀。
2. **`lmeval_run.py` 的 `--ctx`/`--max-gen-toks` 会被它自己的 `DEFAULT_PROFILE` 覆盖**（`run_panel` 用 profile 重设 globals），
   所以臂预算只能从 `TASK_PROFILE` 给。这不是本子项目的文件，`run_thinking_arms.py` 通过导入模块设 `TASK_PROFILE` 绕开，
   不去改共享脚本；此处记录以供 i02 修。
3. **多任务 panel 的 `server.log` 不能按格归属**：五种任务的请求混在一个日志里，逐格 token 数记 `shared-log`，不猜。
4. **`total_evaluation_time_seconds` 与 panel 的 `timings_s` 不同**（同一次 gsm8k：662.6 s 对 1507.7 s）。
   本轴一律用 panel `timings_s`（harness 包住 lm_eval 的墙钟），并在 `RESULT.md` 说明这一选择，避免两种延迟口径混用。

## GPU 队列

| 臂 | 任务 | limit | reasoning | max_gen_toks | ctx | 预估 | 触发条件 |
|---|---|---|---|---|---|---|---|
| endpoint probe | chat + completions 各一次真实请求 | — | off, on | 512 / 64 | 8192 | 1 min | 拿到锁即刻 |
| a08-gsm8k-off-4096 | gsm8k | 100 | off | 4096 | 16384 | 3 min | probe 之后 |
| a08-ifeval-off-50 | ifeval | 50 | off | 4096 | 8192 | 3 min | 同上 |
| a08-mmlu-off-16 | mmlu | 16/科 | off | 1024 | 8192 | 4 min | 同上 |
| a08-mmlu-on-16 | mmlu | 16/科 | on | 1024 | 8192 | 4 min | 同上 |
| a08-ifeval-on-50 | ifeval | 50 | on | 4096 | 8192 | 25–35 min | 同上 |
| a08-gsm8k-on-4096 | gsm8k | 100 | on | 4096 | 16384 | 25 min | 最后；可砍 |

一次 `bash .wrapup/gpu_locked.sh python3 "docs/subprojects/a08-思考开关/run_thinking_arms.py"` 串行跑完全部臂；
每臂追加一行到 `fixtures/arm_runs.tsv`。资源说明：显存需求 ≈3.5 GB（2B Q4 + 16k ctx），独占锁内不与他人并行，
所以不启用「≤4 GB 旁跑」例外。

## 未测（不是 0，见 `RESULT.md` 的同一清单）

- 代码类（humaneval/mbpp/MultiPL-E）的开/关对照：库里 619 个 `auto` 格（EvalPlus）根本没记录 reasoning 设置，
  31 个 `off` 格有明确协议但无对应 on 格。解除条件：每族一个模型 × 两条臂 × 768–4096 token ≈ 20–60 min GPU，
  且要先用小样本确认 `--reasoning on` 时 completion 里不带推理流（raw 模式下 gemma 曾输出 `<|channel>thought`）。
- 前沿大模型族（27B–35B）的开关效应：跑一臂 27B @4096 约 10–25 min/100 题，未排进本轮 2% 预算。
- 历史 on 格的逐题产物（`log_samples` 未开启）：i01 已记 EvalPlus 无逐题产物，本轴同样没有，所以「哪些题翻转」不可得。

## 迁移

本目录原先没有 `plan.yaml`（`docs/subprojects/a08-思考开关/` 在本轮之前不存在，meta 的 16 单元表只给了 id 与 AC），
所以没有 yaml 节点要搬。`docs/plan/subprojects.md` 的 a08 行由 meta 维护，本子项目不改它。
