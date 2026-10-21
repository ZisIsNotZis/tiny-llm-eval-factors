# a07 投机解码 — 计划

计划层的唯一 home。goal / purpose / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a07 行定义，本文件不复述；
本文件只写里程碑、工作包、状态、派工与判据。数字的当前值在 `RESULT.md`，这里只写判据和状态。

本轴拥有报告的两节：**七（速度）**与**八（质量）**，同一个自变量（草稿深度）下两列必须分开答。
理由是它们是两个不同的测量问题，且第二个不能由第一个推出：投机解码在贪心下的输出是否与不开投机逐字节相同，
是一个必须单独测的事实（`RESULT.md::byte-identity-fails` 给出答案：不是）。

## 里程碑：研究结束

- 终点状态：a07 的 AC（`速度-深度-质量三点结论，独立可复算`）三条同时成立——
  1. **速度**：tok/s 随草稿深度的结论给出，并说明它在哪些情形下不成立（深度不是单调收益、长上下文反向）；
     每条带重复次数与「同卡上还有什么在跑」，缺记录就登记为缺。
  2. **质量**：贪心输出在投机下是否逐字节同一有数；若不同一，则「质量列不能从深度 0 抄」被写成结论，
     且逐题判决移动的题数与 i01 的地板并排给出。
  3. **可复算**：`python3 "docs/subprojects/a07-投机解码/spec_evidence.py"` 退出 0 并打印四段；
     缺任一输入时打印 `UNMEASURED` 并退出 **2**；`--check` 在干净 clone 退出 0；`--selftest` 证明检查会变红。
- 只有这一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`（层文档归位 + 三问提取器 + fixture + 负控）。`res11` 已从 `result.yaml` 迁成 `RESULT.md::res11`
  并按其证据重写了两句断言。
- 在办：`WP2`（装置内字节负控，GPU 队列第一槽）与 `WP3`（草稿的运行期显存成本，第二槽）。
  两个都只有几分钟，串行跑在 `bash .wrapup/gpu_locked.sh` 下。
- 下一步派给谁：`WP2`/`WP3` 由本编排者自己跑（各 ≤15 GPU 分钟，不值得再切一层）；
  `WP4`（结论落文档 + 报告口径上报）在同一次会话里接着做；`WP5`（独立复核）由 meta 派 fresh-context reviewer。
- 真正未做的：`WP2`、`WP3`、`WP5`；`WP1` 与 `WP4` 的文档部分已落地。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 层文档归位 + 三问提取器 | a07 编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在且 `result.yaml` 已删除、`res11` 以 `## res11 :: …` 存活；`spec_evidence.py` 打印 [A] 速度-深度、[A2] 第二份速度、[B] 质量-深度含逐题翻转、[C] 逐字节同一性、[D] 装置事实；缺 `.wrapup/mres/*-spec-*/spec_panel.json` 或 `m28_speed.jsonl` 时退出 **2**；`--check` 退出 0（fixture 对库、逐题通过率复原 humaneval 分数、每臂 `n_slots=1`）；`--selftest` 把分数改坏后 `--check` 退出 1 | — | 1 会话，0 GPU | 进行中：脚本与 6 份 fixture 已落盘，捕获待提交 |
| WP2 装置内字节负控 | a07 编排者（GPU 槽 1） | 同一 -MTP 文件、同一 server 旗标（`--spec-type none`、`-c 8192 -np 1 -ngl 99`）、同一 humanEval 164 题跑两次，两次完成物**逐字节相同**（逐题 sha256 全等、翻转 0 道）；若不同，登记「本装置的字节地板未知」并让 `[C]` 的差异不可归因——不许默默沿用 i01 的地板 | `WP1` 的 `[C]` 结论；GPU 锁 | 9B 两臂约 15 GPU 分钟（实测 7.4 分钟/臂，含起服） | 在办 |
| WP3 草稿的运行期显存成本 | a07 编排者（GPU 槽 2） | 同一模型 `--spec-type none` 与 `draft-mtp n=2` 各起服一次，`nvidia-smi` 的 `memory.used` 差与 server 自报的 `n_slots=1` 并列记录；与 [D] 的**权重**字节差（MTP 头）分开写，不许把两者相加成一个「草稿成本」；9B/35B 的权重差标 UNKNOWN（普通仓库不在本机） | `WP2`（同一会话，锁复用） | 约 6 GPU 分钟 | 待派 |
| WP4 结论落文档 + 报告口径上报 | a07 编排者 | `RESULT.md` 的每条事实带 `- evidence:` 与 `- repro:`；报告第八节里与实测冲突的句子（「所有深度分数无差别」「可以放心开：它买速度，不伤质量」）在 `RESULT.md::report-wording-defect` 里逐字引用并给出替代文本；不手改 `make_report.py`/`report.html` | `WP2`、`WP3` | 0 GPU | 待派 |
| WP5 独立复核 | fresh-context reviewer（meta 派） | 先跑命令再判：`spec_evidence.py`（期望退出 0）、`--check`（0）、`--selftest`（0）、以及在空临时树里跑主命令（期望 2）；贴命令与输出，指出证据缺口；其裁决取代本人自评 | `WP1`–`WP4` 落地 | 一次复核 | 待派 |

### res11 的迁移与终态

- author: measurement
- scope: general
- status: current
- domain: kind: measured
- 终态判定：**已重写**。原句「草稿深度越大速度越快（0.8B 约 +36%、9B 约 +93%）；分数随深度几乎不变，MMLU 在每个深度逐位相同」
  两半都要改：速度不是单调（2B 在 n4 掉头、长上下文在**每一个**深度都更慢），MMLU 逐位相同是结构事实
  （对数似然，不生成 token），不能当质量证据。数字与证据见 `RESULT.md::speed-depth-panels`、
  `::speed-depth-longctx-negative`、`::quality-mmlu-inert`、`::byte-identity-fails`。
- 节点本体与 `from:` 链在 `RESULT.md::res11`；本节只记它的终态判定。

## 判据（写死，避免事后挑解释）

1. **一格的协议 = 它的身份**：`spec_type` + `spec_draft_n_max` + `protocol` 串 + `max_tokens` + `ctx_size` + `n_items`
   任一不同就是两个测量（a06 的约束）。投机格永不与贪心格池化，深度 0 与深度 k 也永不平均。
2. **「同一」只有两种可接受的定义**：分数同一（逐题判决相同）或字节同一（完成物逐字节相同）。
   两者互不推出，写结论时必须点名是哪一种。
3. **地板由 i01 给**：确定性解码的地板是 **0 道题**（同一 cell 重跑逐题差异 0、完成物 sha256 相同）。
   所以投机下的逐题差异不是重复噪声——但这条地板是在**另一个文件、另一个 harness** 上测的，
   `WP2` 要在本装置上补一次，补不上就写「归因依赖 i01 的地板，未在本装置复验」。
4. **时间claims要三件套**：重复次数、逐次值（不只均值）、同卡上还有什么在跑。缺哪件就写缺哪件，不写「更快」了事。
5. **未测 ≠ 0**：`memory.free` 不够、普通仓库不在本机、没有逐题产物——一律记 UNKNOWN 并写解除条件。

## 未解问题

- 投机解码 + 采样（`temp>0`）没有任何一格：全部投机格都是贪心。温度与投机是否交互（采样接受/拒绝路径不同）未测。
- `-np>1`（多槽）与投机解码同时使用的行为未测；全部投机格都是 `-np 1`。
- gsm8k / ifeval 的逐题完成物没有落盘（`lm_eval` 未带 `--log_samples`），所以「字节同一性」只在 humanEval 上可判，
  这两个基准只有分数层面的移动。
- 9B 与 35B 的 MTP 头**权重**开销 UNKNOWN：普通（非 MTP）仓库不在本机磁盘上，文件字节差算不出来。
- 各投机格的 tok/s 只存了 3 次重复的均值，逐次值未落盘；同卡竞争负载没有记录 → 速度结论没有 CI。

## 非目标

- 不重跑既有 5 个 spec panel（`.wrapup/mres/m12*-spec-*` 是既有资产，`WP1` 只读）。
- 不测块级/独立草稿模型（`--model-draft` 另一文件）：本仓只有 `draft-mtp`（模型自带 MTP 头）这一条路径，
  「另起一个 0.8B 草稿模型」是另一条轴，超出 4% GPU 份额。
- 不改 `make_report.py` / `.wrapup/mktables.py` / `report.html`：报告第八节的措辞属 i02 与 meta 的呈现面，a07 只提供证据与替代文本。
- 不改其他子项目目录、不改 `docs/plan/subprojects.md`。
- 不动库里的历史行（含 `m28-speed` 的协议串缺陷）：只登记，修法是 i02 的库整洁范围。

## GPU 队列（触发条件 + 逐格预算）

预算从实测算：humanEval 164 题（evalplus codegen + evaluate）在 9B 上是 **7.4 分钟/臂**
（`m128` 的 `panel.log`：23:30:16 ifeval 结束 → 23:37:42 humaneval 结束），起服 17 秒；0.8B 是 2.5 分钟/臂。
显存门槛：起服前看 `nvidia-smi --query-gpu=memory.free`，要求 ≥ 该模型文件字节 + 4 GiB（KV 与 compute buffer 的余量）；
起服后断言 `server.log` 里 `n_slots = 1`，不符即作废该次测量。锁是 `bash .wrapup/gpu_locked.sh`。

| 槽 | 格 | 模型 | 分钟 |
|---|---|---|---|
| 1（WP2） | `--spec-type none` × 2 次，humanEval 164 | `/home/z/hf/Qwen3.5-9B-UD-Q4_K_XL.gguf`（实际指向 -MTP 仓库） | 2 × 7.4 |
| 2（WP3） | `none` 与 `draft-mtp n=2` 各起服一次，只读 VRAM，不跑 benchmark | 同上 | 2 × 0.5 |
