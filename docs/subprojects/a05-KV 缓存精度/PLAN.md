# a05 KV 缓存精度 — 计划

计划层的唯一 home。goal / purpose / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a05 行定义，本文件不复述。
本文件写里程碑、工作包、派工与判定口径。结果与证据在 `RESULT.md`；孙 agent 的窄规则在 `AGENTS.md`；
可执行的复算装置是 `analysis/kv_evidence.py`（一条命令，退出码就是结论）。

## 里程碑：研究结束

- 终点状态：注册表的两条 AC 各自有可复算证据——
  1. **短上下文结论保留且与数据一致**：KV 精度在短上下文（约 1k tokens）上的效应有逐格计数与逐题配对翻动，措辞不得与实测相反（旧措辞「无可测差异」已被实测推翻，见 `RESULT.md::kv-short-panel`）。
  2. **长上下文要么被覆盖，要么显式未测并写清代价**：覆盖的判据是**有分辨力**——所有被测 KV 配置在最长的 ctx 上必须都没落到地板，否则该次测量判「不可分辨」并登记，不算覆盖。
- done 判据：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 退出 0（12 条预期逐条成立，`A05_SELFTEST=1` 时退出 1），且 `RESULT.md` 的每个数字后面都有一条别人能重跑的命令或指向该装置的一段输出。
- 只有一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`（三层文档 + `plan.yaml`/`result.yaml` 迁入并删除）、`WP2`（短上下文结论按实测重写）、`WP3`（m29 入库裁决，裁决=不入库，理由有可复现证据）。
- 在办：无。下一个派给谁：**`WP4` 派给能占 GPU 的 worker（或本层下一会话）**，触发条件是 `/tmp/llama_gpu.lock` 空闲且 `nvidia-smi` 的 `memory.free` ≥ 3 GB；`WP5` 依赖 `WP4`，`WP6` 依赖全部。
- **递归不可用（运行时不提供 subagent 接口）**：本层执行时只有 shell 与读写工具，没有派孙工具，所以文档、装置与判定由本层直接做完；测量（`WP4`）与独立复核（`WP6`）因此必须由 meta 派。按 `@fail_loud` 写在这里，不假装派过。
- 未测（不是 0）：长上下文的 KV 效应（`WP4` 未派）。现有 `m30` 的 16k/49k 格不算覆盖，成因见 `RESULT.md::kv-ctx-padded-floor`。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | 本层（worker） | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`plan.yaml` 的 `plan7` 与 `result.yaml` 的 `res9` 已迁入并删除两个 yaml；`analysis/kv_evidence.py` 退出 0；提交在 main 且按路径点名 | — | 1 会话 | **完成** |
| WP2 短上下文结论按实测重写 | 本层（worker） | `RESULT.md::kv-short-panel` 给出 m130 面板逐格计数与 HumanEval 164 题的逐题配对翻动（base 与 plus 两套判分各一份），并写明「逐题翻动 15/11、净 −4」这类事实；把 `res9` 的「无可测差异」标为撤回并写死因 | WP1 | ≤10 CPU 分钟 | **完成**（装置 A1–A3 成立） |
| WP3 m29 入库裁决 | 本层（worker） | 在**库副本**上复现「入库会让 fa=on 与 fa=off 落到同一报告行标签」：1 格触发行键冲突、3 格静默合并；裁决与理由写进 `RESULT.md::kv-m29-ingest-decision`；真库不动 | WP1 | ≤15 CPU 分钟 | **完成**（装置 F1 成立；`checks/ingest_protocol_negative_control.py` 与 `checks/ingest_skip_negative_control.py` 两条负控都 PASS） |
| WP4 长上下文的可分辨测量 | 能占 GPU 的 worker（meta 派） | 一个模型 × ≥3 个 ctx（含 ≥32k）× 4 个 KV 配置，逐格给出可分辨的连续或饱和不封顶指标；**必须**打印 f16 基线在最长 ctx 上仍显著高于地板（否则该次测量判「不可分辨」并登记，不许写成结论）；同一提示内容跨 KV 配置逐字节相同；断言加载参数（ctx / KV / `-ngl`）与模型原生 ctx 上限；不池化 | WP1；GPU 锁空闲 | ≤30 GPU 分钟（按实测算，见「GPU 队列」） | **待派** |
| WP5 结论进报告 | meta（转 i02；本层不改 `make_report.py`） | 报告第五节文本按 `RESULT.md` 改：短上下文改成逐题翻动的措辞；E 图的 m30 行标注为「填充前缀伪像、不可分辨」；长上下文状态写明 | WP2、WP4 | ≤20 CPU 分钟 | 待派 |
| WP6 独立复核 | fresh-context reviewer（meta 派） | 每包一份裁决（接受 / 接受带注解 / 不接受），阻塞项带位置与复现命令；先跑 `analysis/kv_evidence.py` 与 `A05_SELFTEST=1` 再判 | WP1–WP5 | ≤30 CPU 分钟/份 | 待派 |

调度原则：`WP1` 是本层全部证据的装置，先做；`WP2`/`WP3` 是只读 CPU 活，可与 `WP4` 的 GPU 排队并行；`WP4` 是唯一要 GPU 的包，占锁即独占。

## 判定口径（先写死，避免事后挑解释）

1. **不池化**：语言、协议、基准、KV 配置、ctx 之间绝不平均。m30 只有 cpp，就只报 cpp。
2. **截断探针不与全量格比较**：`n_items = 50 / 60 / 100` 的格（m130 的 gsm8k·ifeval、m30 的 60 题、`--limit` 面板）只能与同一截断口径的格比；与 161/164 的全量格放在一起只说方向，不说数值。
3. **噪声地板（引用 `i01::res32`）**：贪心 + 同一提示集 + 同一后处理版本时，重复跑逐题相同（0 道题），所以同面板内不同设置的非零逐题差**不是**运行噪声；但它仍是单次抽样下的配置差，没有配对区间时只报计数，不报 p 值。
4. **输入差的量级（引用 `i01::res29`）不用于本层**：±16/161 是「提示集/后处理变了」导致的，本层所有组内比较都钉住了同一条 `protocol` 串的其余部分，所以它是不可比量级，不是本层地板。
5. **一格的测量身份包含协议串**：`protocol` 里的 `ctx= / kv= / fa= / prefix=` 是设置本身。哪个因子在报告行标签里被吞掉（`make_report.mpl_protocol_label` 只保留 `ctx= / kv= / tmpl=`），那个因子就**不得入库**，先让消费方学会它再谈入库。
6. **长上下文的「覆盖」必须有动态范围**：所有 KV 配置在最长 ctx 上都落到地板（0 / 1 out of n）时，该次测量判「不可分辨」，登记而不当结论；报告里出现的 `0.0` 格先查成因再读值（本层的 6 个 0.0 格成因见 `RESULT.md::kv-ctx-padded-floor`）。
7. **未测 ≠ 0**：`.scratch/originals/*` 已退役，那里的数只能标「不可复现」并写下原件已退役；本层不复用它们当证据。
8. **入 metric 之前先看判分口径**：m130 面板的 `humaneval` 列是 **base** 判分（`i01::res31` 说 EvalPlus 的 base/plus 是两个数），所以逐题配对必须两套都算一遍，不能拿 base 的分去对 plus 的题。
9. **写库纪律**：只有 `migrate_db.py` 是入库路径；真库要写时先做编号备份（`.bakN`），再跑两次证明幂等，并跑 `checks/ingest_*_negative_control.py` 两条负控。本层目前**不写库**（裁决见 `WP3`）。

## GPU 队列（未测，不是 0）

| 排队项 | 配置 | 判据 | 预算 | 继续触发的条件 |
|---|---|---|---|---|
| WP4 长上下文 KV 网格 | `llama-passkey`（本机 `/home/z/.local/bin/llama-passkey`，vendor 二进制，不改源码）对 Qwen3.5-2B UD-Q3_K_XL：`-ngl 99 -c {8192,16384,32768} -ctk/-ctv ∈ {f16/f16, q8_0/f16, f16/q8_0, q8_0/q8_0}`，每个格同一前缀内容逐字节相同 | f16/f16 在 32768 上的检索准确率仍明显高于地板，且 q8_0/q8_0 与它的差超出逐格抽样波动 ⇒ 长上下文有可分辨的 KV 效应；f16 自己也掉到地板 ⇒ 该模型/该 ctx 不可分辨，登记并降 ctx 或换模型 | 提示处理吞吐实测 23 800 tok/s（中位，见下）⇒ 32k 提示约 1.4 s 提示处理 + 生成 + 一次模型加载；12 格 ≤30 GPU 分钟 | 锁当前被 a04 的 `m164-a04-uni45`（`lmeval_run.py`，`llama-server -c 8192 -np 1`）持着，属同一张卡上的兄弟子项目；按 `@scheduling.queue_behind` 排队，不抢锁、不在前台等 |

显存需求按实测算，不用固定阈值：Qwen3.5-2B UD-Q3_K_XL 文件 1.2 GB 量级 + KV 按 `-c 32768` 的 f16 计 + compute buffer 余量；起跑前看 `nvidia-smi` 的 `memory.free`（观测值 10 504 MiB），要求 ≥3 GB，占锁用 `bash .wrapup/gpu_locked.sh`。
**`n_slots` 断言的适用性**：`llama-passkey` 是单进程 CLI，不经过 llama-server 的 slot 分配，所以本包没有 `n_slots` 可断言；断言改成「命令行里 `-c`/`-ctk`/`-ctv` 与格子一致，且加载日志里报告的 ctx 与 KV 类型相符」，做不到就作废该次测量。
提示处理吞吐的实测来源：`.wrapup/m30b.log` 里 480 条 >4000 token 的 `prompt eval time` 行，中位 23 800 tok/s、最小 20 795 tok/s（同一模型、同一张卡）。

## 跨子项目依赖（不由本层修，必须让 meta 知道）

1. **`i01` 定的是解释口径**：`res32` 给噪声地板（确定性解码 0 道题），`res29` 给输入差量级（±16/161），`res31` 给 EvalPlus 的 base/plus 双判分。本层引用这三条，不重算。
2. **`a12` 已经把两批格子登记到本层名下**：m29 的 FA × KV（24 行 / 12 配置）与 m30 的 6 个 0.0 格。`a12` 只登记不改值，处置权在本层；本层的处置分别落在 `RESULT.md::kv-m29-ingest-decision`（不入库，理由与证据）与 `RESULT.md::kv-ctx-padded-floor`（不可分辨，登记）。
3. **`make_report.py` / `mktables.py` / `report.html` 归 i02/meta**：本层只提交「应写成什么 + 否证条件」，不改这三个文件。m29 入库的前置条件（让 `mpl_protocol_label` 保留 `fa=`）也只能由它们改。
4. **`docs/plan/subprojects.md` 的 a05 行仍写着在办节点 `plan7, res9`**：这两个节点已迁进本目录并被删除，该表由 meta 维护，本层不改；请 meta 顺手更新。
5. **`FINDINGS.md` 第 18 行指向 `docs/result/result.yaml::res9`**：该路径在迁移后已失效（原根 `docs/result/` 不再有事实），本层不改那份文件，请 meta/i02 把指向改为 `docs/subprojects/a05-KV 缓存精度/RESULT.md::kv-short-panel`。

## 非目标

- 不做权重位宽与厂商（`a01`/`a03`）、不做层比特分配（`a04`）、不做采样参数（`a06`）、不做投机解码（`a07`）。本层的 X 只有 KV 精度与 ctx 长度。
- 不给 FA（flash-attn）下结论：m29 的 `fa=on/fa=off` 在本层只用来证明「协议串是测量身份」这件事，FA 的效应不属本层 AC。
- 不重跑 m30 的填充设计「再试一次」：它的混杂（模型续写填充段）是结构性的，换 KV 或换 ctx 都改不了；要重做得换测量方式（`llama-passkey` 或等价连续指标）。
- 不把 m130 的 50/164 截断列外推到全量，也不为补区间去重跑面板：本层 AC 不要求区间，只要求计数与措辞一致。
- 不改别的 subproject 目录、不改 `docs/plan/subprojects.md`、不改 `make_report.py`/`mktables.py`/`report.html`。

## 未解问题

本节的**列表项**就是条目（`report_inputs/build_open_questions.py` 只按这个形状索引）。答完即改写或删除。

- **长上下文的 KV 效应仍未测，且现有 m30 的 16k/49k 格不能当覆盖。** 12 个加长格里 49k 的四个 KV 配置逐题状态完全相同（同哈希），16k 只到 0–1/60，而 58/60 与 56/60 个完成物在以填充段的注释开头——它测的是「模型续写前缀」这个伪像。要判定，需要一个有动态范围的测量（`llama-passkey` 类），预算 ≤30 GPU 分钟，按实测提示处理吞吐 23 800 tok/s 估，32k 提示约 1.4 s/格。
- **m29 进不了库：报告行标签会把 `fa=` 吞掉。** 在库副本上入库 12 个格后，`raw·kv=q8_0/f16` 这一个行标签下同时有 fa=on 与 fa=off 两条协议串：1 个格触发行键冲突提示（q2 cpp 18 vs 17），另 3 个格分数相同因而**静默合并**。前置条件是把 `make_report.mpl_protocol_label` 的保留段加上 `fa=`（i02/meta 拥有），在此之前入库等于让 a12 已经登记过的那个缺陷再长一遍。
- **短上下文的 KV 差只有点估计，没有配对区间。** m130 面板每配置单次运行，gsm8k/ifeval 是 `--limit 50`、mmlu 是 `--limit 8`/科目；只有 HumanEval 有逐题落盘（`eval_results.json`），lm-eval 三列按 `i01::res26` 不落逐题，所以那三列的差只能报计数（最多 4/50），不能报区间。
- **KV 效应到底靠 K 还是靠 V 分不开。** m30 的 4 个组合里 f16/f16 与 f16/q8_0 的逐题状态同哈希、q8_0/f16 与 q8_0/q8_0 同哈希（16k 格），说明在这条链路上是 K 在起作用；但这是被填充伪像污染的格，不能当结论。要分开需要 `WP4` 的同一网格。
