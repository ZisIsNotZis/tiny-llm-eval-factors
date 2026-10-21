# a08 思考开关 — 计划

## 现在（每次改动都要让这一节为真）

- **里程碑 M1「研究结束」未达成**；只剩一个里程碑，结项条件是下面 AC 全绿。
- **在做**：WP2 最后一条臂 `a08-ifeval-on-25` 在锁队列里（`A08_LOCK_WAIT=1800`）；已得数 4 条臂见下。
- **已得数**（都进了库、都写进 `RESULT.md` 的 res7–res11）：`--probe` 端点探针、`a08-gsm8k-off-4096`（0.67，
  与 `m66gs-gsm8k` 的 0.34 构成预算对齐对）、`a08-mmlu-off-16`、`a08-mmlu-on-16`（两者 0.622807 逐位相同）、
  `a08-ifeval-off-25`（0.6）。`a08-gsm8k-on-4096`（复现臂，≈11 min）仍可砍。
- **剩余**：WP2 的 `a08-ifeval-on-25`；WP3 的第二次入库（把 ifeval-on 那一格写进库并重算 fixture）；
  WP4 的结论收口（`RESULT.md` 已写 5 条新事实，抽出类要等那条臂）；WP5 独立复核。
- **下一个派给谁**：a08 worker 收 ifeval-on → 第二次入库 → 收口；之后派 fresh reviewer 做 WP5。
- **需要 meta 知道**：WP3 第一次入库用的是共享 `migrate_db.py`，refresh 把 14 行 BFCL 多轮格的 `n_items`
  抹成 NULL、并给 32 行 `variant-*` 的协议串加上了 `;sampling=default`（分数不变）。改前状态在
  `experiments.sqlite.bak30`，a13/i02 需要决定是否回填（见 `RESULT.md::res11`）。

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
| WP2 | 跑预算对齐的受控臂，**一次调用一条臂**：gsm8k off@4096、mmlu off/on（16/科）、ifeval off/on（25 题） | a08 worker | WP1；GPU 锁 | ≈28 GPU 分钟合计（单臂 3–10 min，见 GPU 队列），CPU ≈1 核 | 每条臂的 `lmeval_panel.json` 里 `reasoning`/`max_gen_toks`/`ctx` 与臂定义一致，`server.log` 有 `n_slots = 1`；起服后 30 s 内 `/props` 答 200（preflight）；每臂单独 `rc` 记在 `fixtures/arm_runs.tsv` | **进行中** |
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

**一次调用一条臂**：`bash "docs/subprojects/a08-思考开关/run_arm.sh" <臂>`。锁等待上限 600 s
（`A08_LOCK_WAIT` 可调），超时打印持锁 pid 并 exit 2，不留僵住的进程；拿锁后第一行是
`[arm <tag>] starting server: model=… task=… limit=… reasoning=… max_gen_toks=… ctx=… port=…`，
起服后 30 s 内 preflight（`/props` 200 + 日志里 `n_slots = 1,`）不成立就打印原因并 exit 1。

| 臂（批） | 任务 | limit | reasoning | max_gen_toks | ctx | 预估 | 触发条件 |
|---|---|---|---|---|---|---|---|
| `--probe` | chat + completions 各一次真实请求（off 与 on 各一轮） | — | off, on | 512 / 64 | 8192 | 2–3 min | 先做；它同时验证起服/preflight 链路 |
| `a08-gsm8k-off-4096` | gsm8k | 100 | off | 4096 | 16384 | 3–4 min | probe 绿后 |
| `a08-mmlu-off-16` / `a08-mmlu-on-16` | mmlu | 16/科（912 题） | off / on | 1024 | 8192 | 3–4 min 每臂 | 各自单独一次调用 |
| `a08-ifeval-off-25` | ifeval | 25 | off | 4096 | 8192 | 3 min | — |
| `a08-ifeval-on-25` | ifeval | 25 | on | 4096 | 8192 | 8–10 min | 本轴唯一贵臂；见下 |
| `a08-gsm8k-on-4096` | gsm8k | 100 | on | 4096 | 16384 | ≈11 min | 复现臂（`m66gs-gsm8k` 已是同协议格），**可砍** |

预估依据（不是拍脑袋）：2B Q4 加载 ≈20 s；生成吞吐 ≈300 token/s（`m66gs` 日志的逐请求 `tg`）；
prompt 侧 5-shot ≈1100 token/题。`a08-ifeval-on-25` 之所以不能更小到无条件：25 题是这一臂的最小可比单位
（IFEval prompt-level strict 的粒度是 4%），而要判的方向是「判分器是否看到推理流」（历史记录说会掉到 0.00），
量级远大于粒度；再小就只剩 3–4 题的判别力。
资源说明：显存需求 ≈3.5 GB（2B Q4 + 16k ctx），独占锁内不与他人并行，所以不启用「≤4 GB 旁跑」例外。

## 踩过的坑

5. **一次 `flock` 串六条臂 = 静默排队 27 分钟**（2026-10-21）。证据：`bash .wrapup/gpu_locked.sh python3
   run_thinking_arms.py` 的进程在 `a06` 的厂商臂后面等了 27 分钟，`.tmp/a08_arms.out` **0 字节**、
   `fixtures/endpoint_probe/` 与 `.wrapup/mres/a08-*` 都不存在、GPU 上没有我们的 server —— 也就是说脚本
   连第一条臂的起服都没走到，它只是排在别人的锁后面。原因不是脚本卡住：`flock -w 21600` 的等待期内
   python 进程根本还没被 `exec`。改法：一次调用一条臂 + 600 s 有界等待 + 起服前后两行可见输出（见 GPU 队列）。

## 未测（不是 0，见 `RESULT.md` 的同一清单）

- 代码类（humaneval/mbpp/MultiPL-E）的开/关对照：库里 619 个 `auto` 格（EvalPlus）根本没记录 reasoning 设置，
  31 个 `off` 格有明确协议但无对应 on 格。解除条件：每族一个模型 × 两条臂 × 768–4096 token ≈ 20–60 min GPU，
  且要先用小样本确认 `--reasoning on` 时 completion 里不带推理流（raw 模式下 gemma 曾输出 `<|channel>thought`）。
- 前沿大模型族（27B–35B）的开关效应：跑一臂 27B @4096 约 10–25 min/100 题，未排进本轮 2% 预算。
- 历史 on 格的逐题产物（`log_samples` 未开启）：i01 已记 EvalPlus 无逐题产物，本轴同样没有，所以「哪些题翻转」不可得。

## 迁移

本目录原先没有 `plan.yaml`（`docs/subprojects/a08-思考开关/` 在本轮之前不存在，meta 的 16 单元表只给了 id 与 AC），
所以没有 yaml 节点要搬。`docs/plan/subprojects.md` 的 a08 行由 meta 维护，本子项目不改它。
