# i01 判分与基准有效性 — 计划

计划层的唯一 home。目标 / 用途 / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 i01 行定义，本文件不复述；本文件只写里程碑、工作包、状态与派工。
结果与证据在 `RESULT.md`；孙 agent 的窄规则在 `AGENTS.md`。

## 里程碑：研究结束

- 终点状态：注册表给的三条 AC 同时有可复算证据——(1) 每个 harness 一份判分审计且每份带负控；(2) chat 协议单次测量的噪声地板是一个实测数；(3) 同一格跨 run 的 6/161 量级差异有裁决（写明来自生成、判分还是未记录的输入差，或写明为什么测不出）。
- done 判据：`python3 "docs/subprojects/i01-判分与基准有效性/audits/run_all.py"` 退出 0（四族审计各就位、每份带负控结果、地板与裁决两个数在 `RESULT.md` 里带复算命令）。
- 只有一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`、`WP2`（EvalPlus）、`WP3`（lm-eval）、`WP4`（BFCL）、`WP5`（MultiPL-E）四份审计 + 负控，以及 `WP6` 的 `np1` arm。
- 在办：无 GPU 任务。`WP6` 的 `np1`（2 pass）与 `npauto`（2 pass，历史原旗标）都已完成且四臂逐字节相同；`plan15` 已裁决。
- 下一个派给谁：`WP7`（chat 单次噪声地板）——MultiPL-E 一族的重复数据已由 `np1`×2 与 `npauto`×2 覆盖（同配置 2 次、跨槽位共 4 次，全相同），剩下 EvalPlus/lm-eval/BFCL 三族要各补一个代表 cell 的重复；其中 EvalPlus 的 `w1-repeat` 已有 3 次 temp=0 复跑可直接引用（DB 可查），所以真正要占 GPU 的只有 lm-eval 与 BFCL 两族。`WP3` 留下的 GPU 负控（`lmeval_run.py --selftest`）与 `WP7` 的补跑一起排。本会话没有派孙工具，所以 `WP9` 的独立复核必须由 meta 派 fresh-context reviewer，不得自评通过。
- **`np1` 已把 plan15 的嫌疑压到四槽批处理上**：同一提示集、`-np 1`、贪心、chat 关思考、每槽 2048 ctx，两次独立生成得到逐字节相同的完成物与相同的 145/161（`RESULT.md::res25`）。所以差异不可能来自「贪心生成本身不稳定」；剩下的是 4 槽批处理（`np4`/`np4b` 待测）或提示集（旧集已删，不可测）。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | i01 编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`plan.yaml`/`result.yaml` 已迁入并删除；`git grep -n 'i01-判分与基准有效性/\(plan\|result\)\.yaml'` 无输出；提交在 main | — | 1 会话 | 完成 |
| WP6 槽位可复现裁决（plan15） | i01 编排者 | 同一提示集下 plan15 那个 cell 在 `-np 1` 与 `-np 4` 各跑 2 次，四份 `_eval.json` + 一份逐题翻转对照表；按预先写死的判定规则给裁决，写进 `RESULT.md` | WP1 | ≤90 GPU 分钟 | 进行中 |
| WP7 chat 单次噪声地板 | i01 编排者 | 四族各一个代表 cell 同配置重复 ≥3 次，给出覆盖率极差 + 逐题通过集合一致率 + 适用协议串；不可测处写不可测 | WP6（共用槽位开关与落盘装置） | ≤120 GPU 分钟 | 未开始 |
| WP2 EvalPlus 判分审计 + 负控 | i01 编排者 | `audits/evalplus.md` 四问逐问有裁决 + 复现命令；负控两侧都观测到；审计脚本 `exit=0`，45 条 HumanEval+ 与 9 条 MBPP+ 预期全部成立 | WP1 | ≤60 CPU 分钟 | **完成** |
| WP3 lm-eval 判分审计 + 负控 | i01 编排者 | `audits/lmeval.md`：五任务的失真条件/方向/幅度 + 负控两侧；审计脚本 `exit=0`，18 条预期成立；一项需 GPU 的负控（echo shim `--selftest`）显式记未测 | WP1 | ≤60 CPU 分钟 | **完成**（缺口：shim selftest 待 GPU） |
| WP4 BFCL 判分审计 + 负控 | i01 编排者 | `audits/bfcl.md`：单轮自研匹配器逐条负控 + 两个金口径的差 + `live_relevance` 整类白拿；多轮 checker 与「自研 vs 官方一致率」显式记未测 | WP1 | ≤60 CPU 分钟 | **完成**（缺口：多轮负控与一致率未测） |
| WP5 MultiPL-E 判分审计 + 负控 | i01 编排者 | `audits/multipl-e.md`：后处理位置、缩进、状态直方图、假阳性（提前退出通道）+ 9 条负控；`exit=0` | WP1 | ≤60 CPU 分钟 | **完成** |
| WP8 RESULT 与报告一致 | i01 编排者 | `RESULT.md` 新事实逐条带证据与复算命令；若写了库则先编号备份 + 完整性/清洁检查 + 重生成 `report.html` 并给「报告数 = 库数」的核对命令；未改库则明写未改 | WP2–WP7 | ≤30 CPU 分钟 | 未开始 |
| WP9 独立复核 | fresh-context reviewer（meta 派） | 每包一份裁决（接受 / 接受带注解 / 不接受），阻塞项带位置与复现；reviewer 的结论取代本人自评 | 对应包完成 | ≤30 CPU 分钟/份 | 待派 |

调度原则：GPU 全局串行且是稀缺资源，所以 `WP6` 先起，`WP7` 紧随共用装置；`WP2`–`WP5` 是 CPU 活，在 GPU 段跑的 8 分钟里并行做，重活并发 ≤2。

## WP6 槽位可复现裁决（plan15 的迁移与裁决设计）

问题（原 `plan.yaml::plan15`）：同一个 cell `q38-27b-q3 py chat`（protocol `mpl-chat-nothink-greedy-768`）记录过三个值——m26 按旧后处理判分 131/161，用修正后处理重判同一批落盘完成物 139/161，m161 新生成 145/161（现入库值）。131→139 由判分缺陷解释（`RESULT.md::res20`）；139→145 的 6 道题只能来自生成侧，两个候选原因未裁决：(a) m161 用的是 2026-10-14 重建的 `.wrapup/prompts`，m26 用的是已被清理的 `/tmp/MultiPL-E/prompts`；(b) 两次都是 4 槽 server（日志 `n_slots = 4` 各 9 行），贪心批处理不保证逐 token 可复现。

裁决设计（不求证已消失的旧提示集，只分离当前可控的变量）：

| 臂 | 配置 | 次数 | 目的 |
|---|---|---|---|
| A | 当前提示集（`.wrapup/prompts`，跑前 `sha256sum -c SHA256SUMS`），`-np 1`，chat 关思考，贪心，768 | 2 | 无批处理时贪心是否逐题可复现 |
| B | 当前提示集，`-np 4`，其余同 A | 2 | 批处理是否引入差异 |

判定规则（先写死，避免事后挑解释）：

1. A 内两次逐题一致、B 内两次不一致 → 归因 (b)：4 槽贪心批处理不可复现；plan15 的 6/161 由它解释；噪声地板必须按生产槽位数定。
2. A、B 各自内部一致但 A≠B → 差异由槽位数这种「记录里没被当成输入」的配置造成，计入「未记录的输入差」，不归给模型。
3. 四臂全部逐题一致 → 生成侧在当前配置下可复现，6/161 的残余只能来自提示集或另一个未记录的输入；此时 (a) 成为唯一存活解释，并必须写明「旧提示集已删除、无法逐字节比对」这一不可测边界，不得把 (a) 说成已证。
4. 其它组合按观测如实写，不硬套上表。

AC：四份落盘完成物与四份 `_eval.json` 存在；一份逐题对照表（哪些题在哪些臂翻转）；一条可复现整条实验的命令；结论进 `RESULT.md`，`plan15` 随之关闭。
预算：4 个 cell × ~8 GPU 分钟（m161 的 cpp chat cell 实测 21:36:26→21:43:54）+ 起停开销，≤90 GPU 分钟。

### WP6 的 arm 清单与实测占用（2026-10-20 22:52 起跑，每个 arm 单独持锁）

| arm | 配置 | pass 数 | 实测 GPU 占用 | 状态 |
|---|---|---|---|---|
| np1 | `-np 1 -c 2048`，一个 server | 2 | 22:52→23:06 ≈ 14 分钟 | **完成**：两次都是 145/161 = 0.9006，完成物逐字节相同 |
| npauto | `-c 2048`，**不带 `-np`**（历史配置：server 默认 → `n_slots = 4, n_ctx_slot = 2048`），一个 server | 2 | 23:49:23→00:06:57 ≈ 18 分钟 | **完成**：两次都是 145/161，且完成物与 np1 逐字节相同 |
| ~~npauto-b~~ | 同 npauto 的第二实例（跨实例检查） | 1 | — | **放弃**（meta 裁决：与 npauto 同一件事，只跑一次） |
| 合计 | 3 次模型加载 + 5 次生成 | — | ≈35 GPU 分钟；**剩约 21 分钟** | — |

### WP6 四槽臂的三次不成立与诊断（不得当成测量）

1. **23:06:54→23:09:33，`rc=143`**：被编排者自己的 30 分钟硬上限 SIGTERM，不是模型/harness 失败；且那一次带的是错的 ctx 旗标（显式 `-np 4` 时 `-c` 是总 ctx，`-c 2048` 只给每槽 512）。无 `_eval.json`。
2. **23:48:03，`arm=np4 server DIED`**：显存分配失败，**死在模型加载、不在 KV**。日志原文（`.wrapup/i01_slot_repro.log` 行 3311-3318）：

```
0.03.345.270 E ggml_backend_cuda_buffer_type_alloc_buffer: allocating 11671.15 MiB on device 0: cudaMalloc failed: out of memory
0.03.345.429 E alloc_tensor_range: failed to allocate CUDA0 buffer of size 12238090240
0.04.019.556 E llama_model_load: error loading model: unable to allocate CUDA0 buffer
0.04.019.576 E srv    load_model: failed to load model, '/home/z/hf/Qwen3.8-27B-UD-Q3_K_XL.gguf'
0.04.019.579 I srv operator(): operator(): cleaning up before exit...
```

3. **根因是锁换手时的显存竞争，不是「四槽不可行」**：a12 的 `m163` 面板结束时间戳是 `panel end Tue Oct 20 23:48:03`，与本 arm 的 `start 23:48:03` 同一秒——flock 由 shell 释放，而死进程的 `cudaFree` 还没完成。同一台机器、同一个模型在 23:06 曾成功以 `-np 4` 加载（server 自报 `n_slots = 4, n_ctx_slot = 512`），m161 更有 9 次 `n_slots = 4, n_ctx_slot = 2048` 的成功加载，所以「四槽在 24GB 上装不下」这一假设被直接反例推翻。当时空出来的量：现在整机空闲时 `nvidia-smi --query-gpu=memory.free` = **22381 MiB**（24,564 MiB 总量，两个外部 386 MiB context 常驻），而模型需要 11,671 MiB 权重缓冲 + KV + compute，余量 ~10 GiB。

处置（已写进 `slot_repro_arm.sh`）：

- 每个 arm 开 server 前等显存达到**算出来的需求**（上限 300 s，超时以 exit 4 记「显存被占」而不是当作测量）。需求推导（全部实测，不拍数）：
  - 权重缓冲：日志 OOM 原文 `allocating 11671.15 MiB`（= 12,238,090,240 B）；模型文件本身 13,146,393,504 B = 12,537.4 MiB，缓冲比文件小是因为部分张量未按此粒度分配，两个数都按各自单位写清，不互相换算当同一个量。
  - KV + compute + prompt cache：四槽 2048ctx 加载并生成时，加载前 `memory.free = 22,627 MiB`，生成中 `memory.free = 7,872 MiB` → 整机占用 **14,755 MiB**；减去权重缓冲得 **3,084 MiB**。
  - 需求 = 11,671 + 3,084 + 1,536（1.5 GiB 余量）= **16,291 MiB**，门禁取 **16,384 MiB（16 GiB）**。
  - 该门禁会挡住 npauto-b：当时 `free` 在 12,957–13,204 MiB 之间（被另一仓库的 `train_sft.py` 占着），所以历史上限是**放行判断**而不是「饿死」：16,384 这个数是算出来的，低于它真会 OOM。
- 只有在日志尾部确实出现 `cudaMalloc failed: out of memory` 时，才 30 s 后重试一次加载（仍然是一个 arm、一次测量）；其它死法不重试，以 exit 3 报原文；
- 起 server 后校验 server 自报的 `n_slots` 与 arm 预期一致，不一致以 exit 5 中止（「配置不符」不是测量）。

### 历史那几次的 np / ctx 到底是多少（先回答再跑）

- `m26`、`m160`、`m161` 的日志里，`n_slots = 4, n_ctx_slot = 2048` 分别出现 9 / 13 / 9 次，**没有别的取值**：131（m26）、139（m26 样本重判）、145（m161）三次全部是**四槽 + 每槽 2048 ctx**。
- 脚本也印证：`run_m26.sh` 与 `run_m161_chat_py.sh` 都是 `llama-server ... -c "$CTX"`（`CTX=2048`）且**不传 `-np`**，四槽来自 server 默认。
- 所以「四槽能不能复现历史那一次」的答案是**能，只要用历史原旗标**：`-c 2048` 且不传 `-np`。这也修正了之前 `-c 8192 -np 4` 的写法：两者每槽 ctx 都是 2048，但只有前者是逐字复现；arm `npauto` 就用原旗标，并断言 server 自报 `n_slots = 4`——实跑自报 `n_slots = 4, n_ctx_slot = 2048`，与历史一致。

### plan15 的裁决口径（先写死，两种结果都算结论）

| 观测 | 裁决 |
|---|---|
| 四槽两次都复现 145/161，且与单槽逐题相同 | 批处理不是原因；131/139 与 145 的差只能来自**未被记成输入的差**（候选：已删除的旧提示集 `.wrapup/prompts` vs `/tmp/MultiPL-E/prompts`），旧集已删 → 该归因**不可证**，记「未测边界」而不是结论 |
| 四槽两次彼此不同 | 「多槽贪心批处理不保证逐题一致」，并给出逐题差异统计（多少题不同、哪些题） |
| 四槽复现 139 附近 | 批处理直接解释那 6 题 |

**实跑结果落入口径 1**，且第 3 条关于「6 道题」的说法**撤回**：在存活工件上 139→145 是 **16 题翻转（11 上 / 5 下）**，不是 6 题单向。详见 `RESULT.md::res29`。

锁粒度：每个 arm 自己持一次 `flock`（`slot_repro_arm.sh <arm>` 由 `gpu_locked.sh` 包住），不是整段实验一次长锁，排在后面的子项目（a12 的 m163）可以在两个 arm 之间插入。理由是 `@machine` 的有限并发与 `@scheduling` 的 queue_behind：一个 arm 是一个可被抢占的完整测量单元，而整段实验不是。

锁粒度：每个 arm 自己持一次 `flock`（`slot_repro_arm.sh <arm>` 由 `gpu_locked.sh` 包住），不是整段实验一次长锁，排在后面的子项目（a12 的 m163）可以在两个 arm 之间插入。理由是 `@machine` 的有限并发与 `@scheduling` 的 queue_behind：一个 arm 是一个可被抢占的完整测量单元，而整段实验不是。

## 非目标

- 不重生成任何提示集：`.wrapup/prompts` 与 `SHA256SUMS` 是唯一来源；旧 `/tmp` 提示集已删除，逐字节比对登记为不可测，不去复原。
- 不修生产判分器：审计发现缺陷时写进 `audits/*.md` 与 `RESULT.md`，改判分器要单独的工作包与一次重判成本核算（res20 的教训：改判分等于改所有历史格）。
- 不补测缺失的语言 / 模型覆盖：那是 a12 的轴；本层只判「已有分数的判分是否可审计」。
- 不做判分器的性能 / 并发改造，不碰别的 subproject 目录与 `docs/plan/subprojects.md`。
- 不把「判分对」当成「基准有效」：本层只回答「同一份完成物会不会被记成错的数」，不回答「这道题是否测到了能力」。

## 已记录的设计判断（本层自行决定）

1. **裁决不追旧提示集**：`/tmp/MultiPL-E/prompts` 已删除，逐字节比对不可能；`WP6` 因此只分离「槽位数」这一个当前可控变量，把「提示集是否变过」写成不可测边界，而不是猜。理由：缺数据时记缺失优于编一个归因（`@absent`）。
2. **噪声地板的主指标是逐题通过集合一致率，不是分数极差**：6/161 的分数差来自 6 道题翻转，而同样的分数差可以由不同题目组合抵消；只看分数会低估不稳定。理由：本 subproject 的问题正是「同一分数是不是同一件事」。
3. **审计脚本放本目录 `audits/`，不改生产 harness**：审计要跑真实判分路径，但改 `mpl_run.py` / `lmeval_run.py` / `bfcl_run.py` 会让审计与生产同时变，违反 `@controlled`。审计只 import 与调用。
4. **不写 0 表示未测**：没跑出来的格子写「未测」并说明原因（`@absent`、`RESULT.md::res17`）。
5. **`WP6` 先于 `WP2`–`WP5`**：GPU 串行、且 plan15 是注册表的在办节点，审计可以在 GPU 跑的 8 分钟里并行做。
6. **不靠 sleep 轮询等 GPU**：`np4`/`np4b` 的驱动进程自己在锁上等，编排者只在 meta 通知 GPU 空出后 `tail .wrapup/i01_slot_repro2.out` 取结果，不用长前台等待占住回合。理由：一次被硬上限 kill 的回合会把这个回合里未提交的东西一起丢掉（`@steerable`、`@checkpoint`）。
7. **`-c` 的含义随 `-np` 变，所以每个 arm 都显式写总 ctx**：显式 `-np 4` 时 `-c` 是**总** ctx（每槽 = `-c/np`，实测 `-c 2048` 给每槽 512），而 `-np` 取默认值(auto) 时 `-c` 表现为每槽大小（m161 日志 9 次加载全是 `n_slots = 4, n_ctx_slot = 2048`）。要控制的是「每槽 ctx = 2048」这个与历史 cell 同值的量，所以 arm 脚本按 `-c $((2048*np))` 传并把它与 server 自报的 `n_slots / n_ctx_slot` 一起写进 `i01-slot-<arm>-meta.json`。这条本身就是一个「未被记成输入的配置差」样本，写进审计结论。

## 跨子项目依赖（不由本层修，必须让 meta 知道）

1. **`make_report.py::load_docs` 只读 `docs/subprojects/*/{plan,result}.yaml`。** 本层迁成 Markdown 后，报告「数据质量」节里引用 res16–res21 / an5 / an7 的条目会消失，报告不会报错、只会变空——这是静默回归（a12 迁移时同样发生）。修法是让 `load_docs` 也读各子项目的 Markdown，属于 i02 的报告代码或 meta 的裁决，本层不擅自改共享构建脚本。
2. **`RESULT.md::res18` 的受控复测未跑**：面板内 raw vs chat 的同模型同语言对照是 m160 的任务，m160 没有产出测量（`RESULT.md::res19`）。该复测属于 a12 的协议轴，本层只把 res18 保持 provisional。
