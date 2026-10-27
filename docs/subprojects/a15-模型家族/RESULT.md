# a15 模型家族（架构代理）— 结果

每条事实一行一个陈述；数字后面跟一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
本层只读 `experiments.sqlite`（以 `mode=ro` 打开），真参数量与逐张量位宽取 a02 入库的 GGUF fixture；
**家族 = 规范家族（canonical family）**：`mktables.family_of` 再把「同实测参数量 + 家族名加尾巴」的臂合并到
不动点（`.wrapup/mktables.py` 随仓库分发）。口径与实现说明在 `analysis/` 的脚本头部；计划与派工在 `PLAN.md`；
本层的窄规则在 `AGENTS.md`。

## 本层的三件东西

### res1 :: 本层的唯一验收入口是一条命令 `python3 "docs/subprojects/a15-模型家族/analysis/run_all.py" --selftest`，它当场跑受控对清单、效应与交互、以及两个负控，三十二条自检全绿，整条链在本机 10 秒内跑完

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/run_all.py`
- evidence: 输出末尾一行 `OK 32/32 checks green | candidates=26335 label_matched=1454 bpw_matched=152 family_bpw_matched=152 family_resolvable=69 readable_pairs=6/27 flips=8 quant_label_missing=1408 canonical_families=54/58 same_scaffold=0 recipe_controls=76 excluded=24881`（行尾还有一个秒数，随负载浮动）。两个负控各自打印自己的结论行（清单侧 30/30、效应侧 13/13 绿）。自检里有九条是**关系式或定义**而不是快照常量：候选数 = 被排除候选数 + 产出受控格的候选数、每一格的 `bpw_matched` 必须等于 `bpw_gap ≤ 容差`、每个配方对照必须同权重且位宽匹配且落在同一个规范家族内、清单里不许有同族格、规范家族映射必须闭合（不存在「同参数量、名字加尾巴却未合并」的对）、规范家族数 = 原始标签数 − 被吃掉的标签数、`pairs.py` 与 `effects.py` 数出的家族对数必须相等、效应侧家族格数必须等于 `bpw_matched − same_n_params`、两侧的 `quant_label_missing` 必须相等；另有两项确定性断言：两个负控把同样的输入重跑到临时目录，得到的 JSON 与入库的那两份**逐字节相同**。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/run_all.py" --selftest`（实跑输出：`OK 32/32 checks green | candidates=26335 label_matched=1454 bpw_matched=152 … excluded=24881`，rc=0）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs_negative_control.py"`（实跑输出：`30/30 checks green` + `NEGATIVE CONTROL OK: the inventory loses the mutated pair and names the reason; the unmodified run is green`，rc=0；六处改动是改 `temp`、把尺寸差改成 11%、删掉真值、同权重尾巴必须并成一个家族、改掉尾巴的参数量后必须不再合并、真库字节不变）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects_negative_control.py"`（实跑输出：`13/13 checks green`，其中 `family_resolvable 69 → 68` 与 `flips 8 → 7` 两处改动都被点名）
- 边界：本层**不启任何模型**、不重建 `report.html`、不跑 `./reproduce.sh`；它只读一个已经在盘上的 `experiments.sqlite`，所以「结论成立」这句话的范围是这些已测的格，不是新测量（见 `result.res7`）。

## 受控对清单：家族、两层口径

### res2 :: 从库里的 3379 行（212 个文件）枚举出 26335 个跨家族候选（同基准 + 同量化档标签 + 两个不同规范家族），其中 1454 个通过十六条身份栏与 `protocol`/`_score` 非空成为 `label_matched` 格，24881 个被逐条登记原因排除；`label_matched` 只是**标签**相同——其中 1408 个格的量化档标签是 NULL，所以「同一比特预算」必须另立一层，按实测 bpw 加闸门后是 152 格 `bpw_matched`，且这 152 格全部是两侧实测参数量不同的格（同参数量的对子已被家族合并吃掉，见 `result.res8`）

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res1
- origin: `analysis/pairs.py`（读库 + a02 的 GGUF fixture + `.wrapup/mktables.py`，写 `analysis/pairs.json`）
- evidence: 家族先按 `mktables.family_of` 取标签（58 个），再做后缀合并到不动点：**54 个规范家族 / 58 个原始标签 / 4 个标签被吃掉**，合并表逐条打印——`LFM2.5-8B-A1B` ← `LFM2.5-8B-A1B-a04-uni45`；`Qwen3.8-27B` ← `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`、`-IQ3_XXS-mtp`；`gemma-4-26B-A4B` ← `gemma-4-26B-A4B-it-qat`——并打印完整规范家族列表（每个家族吃掉的原始标签数 / 文件数 / 标签格数 / 位宽格数）。漏斗：同一基准上跨家族的文件对 63514 个，其中 37179 个从不共享量化档（交互轴的原料，不是受控对照），剩下的 26335 个成为候选。排除原因逐条计数（同一候选只记第一条成立的）：`size_gt_10pct=17842`、`protocol_null=3030`、`identity_mismatch:*` 合计 3941（点名最多的是 `max_tokens=1102`、`protocol=595`、`protocol,n_items=560`、`reasoning,max_tokens=540`）、`score_null=56`、`score_ambiguous=12`。三层口径：`label_matched=1454`（标签缺失 1408）、`bpw_matched=152`（标签缺失 144）、家族层 = 152（同参数量格在 bpw 层为 0）。清单确定性：格按 (基准, 两个文件名, 身份键) 排序后发 `famNNNN` 号，同样输入第二次跑出逐字节相同的 JSON。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py"`（实跑输出：`db rows read / files / families : 3379 / 212 / 54 (canonical; 58 raw family_of labels, 4 absorbed in 2 round(s))` + 三行合并表；`candidates …: 26335`、`label_matched cells: 1454`、`bpw_matched cells (<= 0.25 bpw): 152`、`quant label missing: 1408 label_matched, 144 of them bpw_matched`、`same true n_params (same scaffold): 39 cells, 0 of them bpw_matched`、`COUNT candidates=26335 label_matched=1454 bpw_matched=152 recipe_controls=76 excluded=24881`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" | sed -n '/excluded by reason/p'`（实跑输出即上面那串逐原因计数）
- 已记录的限制：**这些格不是独立样本**。1454 个标签格落在 283 个 (家族对, 基准) 组里，最大的组 15 格；家族层的 152 格来自 6 个家族对 × 12 个基准，逐组格数由 `effects.py` 的 (g) 段打印。所以「152 格、69 格可分辨」是**格的计数，不是 n**，不能当独立重复次数做二项检验。

### res3 :: 「实测参数量相差 ≤10%」这一条单独拒掉了 17842 个候选、覆盖 323 个家族对；被拒的主力是同一条产品线只差尺寸的配对，也就是尺寸轴本身，而不是「判据太严」

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res2
- origin: `analysis/pairs.py` 的 `counts.family_pairs_rejected_by_size`
- evidence: 被尺寸判据拒掉的家族对按候选数排序，前几名为 `LFM2.5-8B-A1B | Qwen3.5-2B` 310、`LFM2.5-8B-A1B | Qwen3.8-27B` 299、`Qwen3.5-2B | Qwen3.8-27B` 251、`Qwen3.5-2B | Qwen3.5-4B` 232、`GLM-4.7-Flash | LFM2.5-8B-A1B` 197。判据用的是 GGUF 张量参数量（a02 的 fixture），不是文件名里的 `4B`/`E2B` 标签；真正活下来的 `Qwen3.5-4B | gemma-4-E2B-it-qat` 一对，实测参数量差 9.1%，`Qwen3.8-27B | gemma-4-26B-A4B` 差 7.6%。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" | sed -n '/10% size criterion/p'`（实跑输出：`10% size criterion rejects: 17842 candidate(s) over 323 family pair(s); largest:` 后跟逐对计数）
- 已记录的限制：`family_of` 保留尺寸 token，所以「同一条产品线的不同尺寸」在这里是两个**家族**（`Qwen3.5-2B` 与 `Qwen3.5-4B`），它们的差异是尺寸轴（a02）而不是家族轴；尺寸闸门正是把它们挡住的那道门，不是家族定义的一部分。

## 家族效应（只在 `bpw_matched` 上读）

### res4 :: 家族差只在「两侧实测位宽差 ≤ 0.25 bpw」的格上读：152 格来自 6 个家族对、12 个基准，其中 151 格有 95% Wilson 区间（1 格 `n_items` 为空，只能记「题数未测」），69 格两侧区间不相交；27 个有格的家族对里只有 6 个能读出家族差，另外 21 个一格都不可读

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res2
- origin: `analysis/effects.py`（读 `analysis/pairs.json`，写 `analysis/effects.json`）
- evidence: 6 个可读家族对与它们的可分辨格数：`LFM2.5-8B-A1B | Qwen3.5-9B` 38 格可读 / 24 可分辨（Δ 从 −2.3 到 +68.3 pp）、`GLM-4.7-Flash | Qwen3.8-27B` 32/12（−1.0…+24.2）、`Qwen3.8-27B | gemma-4-26B-A4B` 30/5（−89.4…+10.0）、`Qwen3.5-4B | gemma-4-E2B-it-qat` 18/11（−50.0…+2.7）、`Llama-3.2-3B | granite-4.1-3b` 18/7（−33.5…+15.0）、`Phi-4-mini | Qwen3.5-4B` 16/10（−2.0…+60.0）。方向最稳的几条（Δ = b − a，单位 pp，括号里是 `n_items`）：`LFM2.5-8B-A1B → Qwen3.5-9B` 在 4.49 bpw（两侧位宽差 0.031）是 +68.29（humaneval，164）、+64.02（humaneval-plus，164）、+56.35（mbpp，378）、+49.56（mmlu，912）；`Phi-4-mini → Qwen3.5-4B` 在 3.58–3.59 bpw 是 +51.00/+60.00（ifeval，100）、+44.96（mmlu，912）；`Qwen3.5-4B → gemma-4-E2B-it-qat` 在 3.72 bpw 是 −50.00（humaneval，164）、−48.78（humaneval-plus，164）、−28.18（mmlu，912）；`Qwen3.8-27B → gemma-4-26B-A4B` 在 3.97 bpw 是 −78.26（humaneval-cpp，161）、−68.94（humaneval-py，161）、−19.96（mmlu，912）；`GLM-4.7-Flash → Qwen3.8-27B` 在 3.76 bpw 是 +24.22（humaneval-py，161）、+22.36（humaneval-cpp，161）、+11.07（mmlu，912）。`Llama-3.2-3B → granite-4.1-3b` 在 3.30 bpw 上六列全负（−19.25…−33.54），到 4.12 bpw 变成 +14.02（humaneval）与 −25.47（humaneval-py）——方向随基准与档位分裂，见 `result.res5`。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" --key-cells`（实跑输出：152 行家族层可读格，带 `ci_a` / `ci_b` 与 `RES yes/no` 列）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '1,10p'`（实跑输出：`label_matched cells (tier 1): 1454`、`family cells, bpw_matched: 152 → resolvable 69`、`family pairs with cells: 27 (readable: 6, …)`）
- 已记录的限制：① 区间是**单跑的二项区间**，只覆盖抽样误差，不覆盖重测误差；② 这些格不独立（283 个 (家族对, 基准) 组，逐组格数见 (g) 段），69 不是 69 次独立重复；③ 家族 = 架构 + 训练配方 + tokenizer 的整包，上面任何一条 Δ 都不能拆成其中一份（`result.res6`）。

## 家族 × 量化档交互

### res5 :: 在固定规模对、固定两侧 arm id（同一份配方、同一条位宽阶梯）、且**两档都是 `bpw_matched`** 的 117 个交互组里（26 组有 ≥2 个档），相邻档之间家族差的符号翻转共 8 次：`Llama-3.2-3B | granite-4.1-3b` 一个对子在 6 个基准上同时翻（Q2_K 负、Q3_K_M 正），另有 `Phi-4-mini | Qwen3.5-4B`（arc_challenge）与 `Qwen3.5-4B | gemma-4-E2B-it-qat`（truthfulqa_mc2）各一次

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res4
- origin: `analysis/effects.py` 的 `interaction` 段
- evidence: 8 处翻转逐条点名（档的平均 bpw 与翻转前后 Δ）：`humaneval` 上 `Llama-3.2-3B → granite-4.1-3b` 从 −33.54 pp（3.30 bpw，164 题）到 +14.02 pp（4.12 bpw）；`humaneval-cpp` 上 −19.25 → +13.04；`humaneval-plus` 上 −29.88 → +13.41；`mbpp` 上 −30.42 → +2.91；`mbpp-plus` 上 −26.19 → +7.14；`truthfulqa_mc2` 上 −3.10 → +3.26；`arc_challenge` 上 `Phi-4-mini → Qwen3.5-4B` 从 +14.50（3.59 bpw）到 −2.00（4.51 bpw）；`truthfulqa_mc2` 上 `Qwen3.5-4B → gemma-4-E2B-it-qat` 从 −0.51（3.71 bpw）到 +2.72（4.56 bpw）。前六处的两档位宽差都被钉在 0.13–0.16 bpw（同一条量化阶梯的 Q2_K/Q3_K_M），所以翻转不能由比特预算漂移解释。家族排序按基准给出 13 个「基准 × 上下文」组，其中 2 组在 ≥2 个档上家族集合相同、可比：`humaneval-cpp` 的一组**翻转**（Q2_K 上 Llama > granite，Q3_K_M 上 granite > Llama），`humaneval-py` 上同一对两档都保持 Llama > granite。家族差与同组量化差放在同一个 pp 单位下比较：`Llama-3.2-3B | granite-4.1-3b` 在 arc_challenge 上 Δfam 从 +15.00 到 +4.00，而同组 granite 自己从 Q2 到 Q3 只动 −3.00 pp、Llama 动 +8.00 pp。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(b) sign of/,/^(c) family/p'`（实跑输出：`117 groups (26 with >= 2 levels); sign flips: 8` 与逐组符号串、逐条翻转详情；每行括号里还印出两侧 arm id）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(c) family/,/^(d) family/p'`（实跑输出：逐组的 `Δfam@low` / `Δfam@high` / `quantΔa` / `quantΔb` / `bpw span`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(d) family ordering/,$p'`（实跑输出：`13 bench×context groups, 2 comparable …, 1 change order` 与逐组排序）
- 已记录的限制：翻转只在「同一对规模 + 同一批其余身份栏 + 两侧 arm 不变 + 相邻两个档」上算；家族在同一个基准上往往挂着多个尺寸的文件，所以按家族排名的组大多因「同一家族在同一档上有多个模型」被跳过（脚本逐条打印被跳过的档与家族名），可比组只有 2 组；`Llama-3.2-3B | granite-4.1-3b` 是唯一在多基准上复现的翻转，其余两个各只有 1 个基准。

## 边界

### res6 :: 这份读法是对**已经测过的格**做事后匹配，不是新测量；可读的家族对只有 6 个（另有 21 个有格但一格都不可读），每一格是单跑、无逐题产物，且**同一份权重在同比特预算下换配方就能挪动 58 pp**（`Qwen3.5-4B` 的 `IQ3_XXS` 对 `Q2_K_XL`，gsm8k 100 题），所以任何一个 Δ 只能读成「家族包效应」，不能读成「架构效应」

- author: measurement
- scope: general
- status: current
- kind: analysis
- from: result.res4, result.res8
- origin: `analysis/effects.py` 的 `counts.family_pairs_*` 与 (e)/(f) 两段
- evidence: 27 个家族对有受控格，其中 6 个至少有一格两侧位宽差 ≤ 半档，另外 21 个**读不出家族差**，因为它们的每一格两侧位宽都差得超过半档——名单由 `effects.py` 的第一段整行打印。位宽闸门是本节唯一的人为选择，写成具名常量：档宽 `level_width_bpw = 0.5`，容差 `bpw_match_tol = 0.25`（半档）；不加闸门的计数照样给：`label_matched` 1454 格、其中 550 格区间不相交，而加了闸门只剩 152 格、69 格可分辨。三处必须与结论同时读的混杂：① 同一份权重、同一比特预算、换量化配方或换比特分配就能挪动分数——最大的三处是 `Qwen3.5-4B-UD-IQ3_XXS` 对 `Qwen3.5-4B-UD-Q2_K_XL` 在 gsm8k 上 +58.00 pp（3.69/3.67 bpw，100 题，区间不相交）、`LFM2.5-8B-A1B-a04-uni45` 对 `LFM2.5-8B-A1B-m55-exq4` 在 humaneval 上 −48.17 pp（4.52/4.47 bpw，164 题）、`Qwen3.5-2B-UD-IQ3_XXS` 对 `Qwen3.5-2B-UD-Q2_K_XL` 在 gsm8k-strict 上 +35.00 pp（3.91/4.06 bpw，100 题）；同一批里也有接近 0 的（`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` 对 `Qwen3.8-27B` 的 10 个格 |Δ| ≤ 5.3 pp、一格都不可分辨），所以「配方」既不是恒为零、也不是恒定大小；② 单跑、无逐题产物：区间只覆盖抽样误差，不能拆到题目层，也不能拆成架构/训练/tokenizer 三份；③ 家族标签由文件名给出（`mktables.family_of` + 同参数量后缀合并），它保留尺寸 token，所以同一条产品线的不同尺寸在这里是两个家族、由尺寸闸门分开（`result.res3`）。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/family pairs with cells/,+1p'`（实跑输出：`family pairs with cells: 27 (readable: 6, not readable: [...21 个点名...])`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | grep "bpw gate"`（实跑输出：`bpw gate: |bpw_a − bpw_b| <= 0.25 bpw (half a 0.5 bpw quant level, measured tensor bpw)`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(f) recipe controls/,/(g) independence/p'`（实跑输出：76 行配方对照逐格表，`Δpp` 从 `-48.17` 到 `+58.00`）
- 未测（不是 0）：任何「同权重、不同架构」的受控对（a02 已证本库与盘上都不存在）；跨三个以上量化档的家族排序（可读的档位基本只有相邻两档）；agentic 基准上的家族差（无 GPU，`docs/plan/subprojects.md` 的 `agentic` 节）。

### res7 :: 这份清单的家族效应是**事后匹配**的读法：它只重排已经落在 `experiments.sqlite` 里的格，没有为任何一对新起一次测量，所以「家族差」的取值只在这批被测过的文件、基准、协议与位上成立

- author: measurement
- scope: general
- status: current
- kind: analysis
- from: result.res1, result.res6
- origin: `analysis/run_all.py`（只以 `mode=ro` 打开库；负控断言真库与真 fixture 前后字节相同）
- evidence: 负控里有一条断言：真库与真 fixture 在整条链跑完后 sha256 不变；脚本没有任何写库路径（连接串是 `file:…?mode=ro`），也没有起模型、没有 `report.html` 重建。清单的候选集由库里的行与 `mktables.family_of` + 规范家族决定的，脚本不含任何文件名白名单或手挑的家族对。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs_negative_control.py" | grep -E 'byte-identical'`（实跑输出：`ok the real database is byte-identical before and after` 与 `ok the real truth fixture is byte-identical before and after`）

## 同权重对照：臂与配方，不进家族计数

### res8 :: 把「同一份权重」的配对单独拿出来看：规范家族合并已经把「家族名 + 尾巴、张量形状相同」的臂并回本家族（所以它们不再是候选），剩下 76 格是同一规范家族、同一份权重（实测参数量相同）、两侧位宽差 ≤ 半档的配方对照；它们的 Δ 从 −48.17 到 +58.00 pp，其中 13 格区间不相交，说明「配方/臂」这一段本身就能把分数搬动，家族差必须带着这条读

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res2
- origin: `analysis/pairs.py` 的 `recipe_controls`（同规范家族 + 同实测参数量 + |Δbpw| ≤ 0.25）+ `analysis/effects.py` 的 (f) 段
- evidence: 76 格配方对照、13 格可分辨；最大的几处是 `Qwen3.5-4B-UD-IQ3_XXS` 对 `Qwen3.5-4B-UD-Q2_K_XL`（3.69/3.67 bpw）+58.00 pp（gsm8k 与 gsm8k-strict，100 题）、`LFM2.5-8B-A1B-a04-uni45` 对 `LFM2.5-8B-A1B-m55-exq4`（4.52/4.47 bpw）−48.17/−46.95/−43.39 pp（humaneval、humaneval-plus、mbpp，164/164/378 题；与 a04 记录的「exq4 在 4.48 bpw 上 HE 0.14」一致）、`Qwen3.5-2B-UD-IQ3_XXS` 对 `Qwen3.5-2B-UD-Q2_K_XL`（3.91/4.06）+35.00 pp（gsm8k-strict，100 题）。接近 0 的那一侧也有：`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` 对 `Qwen3.8-27B` 的 10 个格 |Δ| ≤ 5.3 pp、一格都不可分辨。另一类「规范家族不同、但张量形状相同」的格（39 个标签格、**0 个**位宽格）单列在 (e) 段——它们在位宽层已经不剩一格，因为同参数量的对子要么被合并回本家族（(f) 段），要么被 `same_n_params` 挡在家族计数之外；两条路都**不进**家族计数，理由写在清单里：同参数量意味同一套张量形状（同一架构脚手架），差异是权重/配方而不是架构。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" | grep "recipe controls"`（实跑输出：`recipe controls (same weights, bpw-matched): 76 cells`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(e) same-scaffold/,/(f) recipe controls/p'`（实跑输出：`(e) … — 0 bpw_matched, NOT in family counts`，表体为空）
- 已记录的限制：规范家族合并只吃「同参数量 + 名字加尾巴」的臂；`gemma-4-12B-it-qat`（大写 B）与 `gemma-4-12b` 名字前缀不匹配（大小写不同），因此仍是两个标签，但它们的格同参数量 → 落在 (e) 段、不进家族计数，所以不漏算也不重算。

## 记录：本层被抓到并已修掉的错

四处都不是「文档措辞」，都会改变清单或结论本身，记在这里是因为它们是这份清单可信度的一部分：

1. **用 `experiments.__model` 当家族**（第一版）：它是 `exp.py` 从文件名解析的标签，会把同一份权重拆成两个「家族」（`Qwen3.6-35B-A3B` / `Qwen_Qwen3.6-35B-A3B`，实测参数量都是 35505251456）。现在家族取 `mktables.family_of`。
2. **按行取 `__model` 会把跨家族候选全静默丢掉**：字典推导后写覆盖前写，库里有 65 个文件的 `__model` 同时有值和 NULL，取到 NULL 之后这些文件与所有文件都「同族」，候选只剩 0 条而脚本仍 exit 0。现在家族由 `family_of` 算，候选为空时脚本 exit 2。
3. **「同一量化档」只靠 `__quant` 栏**（第一版把 1112 个格都叫「受控」）：`__quant` 为 NULL 时这一栏什么都没钉住，于是两侧位宽差最大 3.9 bpw 的格也进了「同档」。现在 `label_matched`（标签，只作清单）与 `bpw_matched`（实测 bpw 差 ≤ 半档，所有家族结论只在这一层上算）两层分列。
4. **`family_of` 不剥「家族名 + 供应商/配方尾巴」**：`Qwen3.8-27B` / `-GSQ-RCO-IQ3_S-mtp` / `-IQ3_XXS-mtp` 与 `LFM2.5-8B-A1B` / `-a04-uni45` 被当成不同家族，于是同一个家族对比被数了 3 次（`GLM` vs `Qwen3.8`）与 2 次（`LFM2.5` vs `Qwen3.5`），「10 个可读家族对」是虚高。现在按「同参数量 + 名字加尾巴」合并到不动点（54 个规范家族 / 58 个原始标签），可读家族对因此从 10 掉到 6。合并顺带暴露了第二个错：合并后同一家族的臂落进同一个交互组，`换臂`（a04 的比特分配、a10 的第三方量化、面板配方）被当成「提位宽」，凭空造出 3 个翻转（`Qwen3.8-27B | gemma-4-26B-A4B` 的 mbpp/mbpp-plus、`LFM2.5-8B-A1B | Qwen3.5-9B` 的 truthfulqa_mc2）；现在交互组的分组键里带两侧的 **arm id**（剥掉量化 token 的主干；面板配方与无量化 token 的臂保留整名），翻转回到 8 次，且 8 次都是在「同一份配方、只提位宽」的两档之间。

四处都被 `run_all.py` 的关系式断言与两个负控盯着：候选数 = 排除数 + 有格候选数、每格的 `bpw_matched` 必须等于闸门、清单里不许有同族格、规范家族映射必须闭合、配方对照必须落在同一规范家族内、改身份栏/改尺寸/删真值必掉对并点名、同权重尾巴必须并成一个家族而不同参数量的尾巴必须不并、把一对分数改成相等则 `family_resolvable` 或 `flips` 必变。
