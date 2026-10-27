# a15 模型家族（架构代理）— 结果

每条事实一行一个陈述；数字后面跟一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
本层只读 `experiments.sqlite`（以 `mode=ro` 打开），真参数量与逐张量位宽取 a02 入库的 GGUF fixture；
**家族用报告那一套定义** `.wrapup/mktables.py::family_of`（随仓库分发，剥掉量化/配方后缀并归一化 `Qwen_`）。
口径与实现说明在 `analysis/` 的脚本头部；计划与派工在 `PLAN.md`；本层的窄规则在 `AGENTS.md`。

## 本层的三件东西

### res1 :: 本层的唯一验收入口是一条命令 `python3 "docs/subprojects/a15-模型家族/analysis/run_all.py" --selftest`，它当场跑受控对清单、效应与交互、以及两个负控，二十六条自检全绿，整条链在本机 10 秒内跑完

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/run_all.py`
- evidence: 输出末尾一行 `OK 26/26 checks green | candidates=26470 label_matched=1588 bpw_matched=172 family_bpw_matched=152 family_resolvable=69 readable_pairs=10/43 flips=8 quant_label_missing=1542 same_scaffold=20 recipe_controls=56 excluded=24882`（行尾还有一个秒数，随负载浮动，本轮多次实跑落在 4.6–5.4 s）。两个负控各自打印自己的结论行（清单侧 20/20、效应侧 13/13 绿）。自检里有六条是**关系式或定义**而不是快照常量：候选数 = 被排除候选数 + 产出受控格的候选数、每一格的 `bpw_matched` 必须等于 `bpw_gap ≤ 容差`、每个配方对照必须同权重且位宽匹配、清单里不许有同族格、效应侧的家族格数必须等于 `bpw_matched − same_n_params`、两侧的 `quant_label_missing` 必须相等；另有两项确定性断言：两个负控把同样的输入重跑到临时目录，得到的 JSON 与入库的那两份**逐字节相同**。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/run_all.py" --selftest`（实跑输出：`OK 26/26 checks green | candidates=26470 label_matched=1588 bpw_matched=172 … excluded=24882`，rc=0）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs_negative_control.py"`（实跑输出：`20/20 checks green` + `NEGATIVE CONTROL OK: the inventory loses the mutated pair and names the reason; the unmodified run is green`，rc=0；四处改动是改 `temp`、把尺寸差改成 11%、删掉真值、以及真库字节不变）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects_negative_control.py"`（实跑输出：`13/13 checks green`，其中 `family_resolvable 69 → 68` 与 `flips 8 → 7` 两处改动都被点名）
- 边界：本层**不启任何模型**、不重建 `report.html`、不跑 `./reproduce.sh`；它只读一个已经在盘上的 `experiments.sqlite`，所以「结论成立」这句话的范围是这些已测的格，不是新测量（见 `result.res7`）。

## 受控对清单：两层口径

### res2 :: 从库里的 3379 行（212 个文件 / 58 个家族）枚举出 26470 个跨家族候选（同基准 + 同量化档标签 + 两个不同家族），其中 1588 个通过十六条身份栏与 `protocol`/`_score` 非空成为 `label_matched` 格，24882 个被逐条登记原因排除；`label_matched` 只是**标签**相同——其中 1542 个格的量化档标签是 NULL，所以「同一比特预算」必须另立一层，按实测 bpw 加闸门后只剩 172 格 `bpw_matched`，再去掉 20 个同权重（同张量形状）的格，家族层是 152 格

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res1
- origin: `analysis/pairs.py`（读库 + a02 的 GGUF fixture + `.wrapup/mktables.py`，写 `analysis/pairs.json`）
- evidence: 漏斗一次运行全部打印：同一基准上跨家族的文件对 63681 个，其中 37211 个从不共享量化档（它们是交互轴的原料，不是受控对照），剩下的 26470 个成为候选。排除原因逐条计数（同一候选只记第一条成立的）：`size_gt_10pct=17842`、`protocol_null=3030`、`identity_mismatch:*` 合计 3941（点名最多的是 `max_tokens=1102`、`protocol=595`、`protocol,n_items=560`、`reasoning,max_tokens=540`）、`score_null=56`、`score_ambiguous=13`。三层口径的计数分别是：`label_matched=1588`（其中量化标签缺失 1542）、`bpw_matched=172`（量化标签缺失 164）、家族层 152（= 172 − 20 个同权重格）。清单确定性：格按 (基准, 两个文件名, 身份键) 排序后发 `famNNNN` 号，同样输入第二次跑出逐字节相同的 JSON。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py"`（实跑输出：`candidates …: 26470`、`label_matched cells: 1588`、`bpw_matched cells (<= 0.25 bpw): 172`、`quant label missing: 1542 label_matched, 164 of them bpw_matched`、`same true n_params (same scaffold): 173 cells, 20 of them bpw_matched`、`COUNT candidates=26470 label_matched=1588 bpw_matched=172 recipe_controls=56 excluded=24882`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" | sed -n '/excluded by reason/p'`（实跑输出即上面那串逐原因计数）
- 已记录的限制：**这些格不是独立样本**。1588 个标签格落在 429 个 (家族对, 基准) 组里，最大的组是 `LFM2.5-8B-A1B | Qwen3.5-9B` 在 humaneval 等基准上的 10 格；家族层的 152 格来自 10 个家族对 × 12 个基准，逐组格数由 `effects.py` 的 (g) 段打印。所以「152 格、69 格可分辨」是**格的计数，不是 n**，不能当独立重复次数做二项检验。

### res3 :: 「实测参数量相差 ≤10%」这一条单独拒掉了 17842 个候选、覆盖 416 个家族对；被拒的主力是同一条产品线只差尺寸的配对（`Qwen3.5-2B` 对 `Qwen3.5-4B`、`LFM2.5-8B-A1B` 对 `Qwen3.5-2B` 之类），也就是尺寸轴本身，而不是「判据太严」

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res2
- origin: `analysis/pairs.py` 的 `counts.family_pairs_rejected_by_size`
- evidence: 被尺寸判据拒掉的家族对按候选数排序，前几名为 `LFM2.5-8B-A1B | Qwen3.5-2B` 261、`Qwen3.5-2B | Qwen3.5-4B` 232、`Qwen3.5-2B | granite-4.1-3b` 189、`GLM-4.7-Flash | LFM2.5-8B-A1B` 167、`Qwen3.5-2B | gemma-4-E2B` 163。判据用的是 GGUF 张量参数量（a02 的 fixture），不是文件名里的 `4B`/`E2B` 标签；真正活下来的 `Qwen3.5-4B | gemma-4-E2B-it-qat` 一对，实测参数量差 9.1%，`Qwen3.8-27B | gemma-4-26B-A4B` 差 7.6%。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" | sed -n '/10% size criterion/p'`（实跑输出：`10% size criterion rejects: 17842 candidate(s) over 416 family pair(s); largest:` 后跟逐对计数）
- 已记录的限制：`family_of` 保留尺寸 token，所以「同一条产品线的不同尺寸」在这里是两个**家族**（`Qwen3.5-2B` 与 `Qwen3.5-4B`），它们的差异是尺寸轴（a02）而不是家族轴；尺寸闸门正是把它们挡住的那道门，不是家族定义的一部分。

## 家族效应（只在 `bpw_matched` 上读）

### res4 :: 家族差只在「两侧实测位宽差 ≤ 0.25 bpw」的格上读：152 格来自 10 个家族对、12 个基准，其中 151 格有 95% Wilson 区间（1 格 `n_items` 为空，只能记「题数未测」），69 格两侧区间不相交；43 个有格的家族对里只有 10 个能读出家族差，另外 33 个一格都不可读

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res2
- origin: `analysis/effects.py`（读 `analysis/pairs.json`，写 `analysis/effects.json`）
- evidence: 可读家族对（`effects.py` 头部打印）：`GLM-4.7-Flash | Qwen3.8-27B`、`GLM-4.7-Flash | Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`、`GLM-4.7-Flash | Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp`、`LFM2.5-8B-A1B | Qwen3.5-9B`、`LFM2.5-8B-A1B-a04-uni45 | Qwen3.5-9B`、`Llama-3.2-3B | granite-4.1-3b`、`Phi-4-mini | Qwen3.5-4B`、`Qwen3.5-4B | gemma-4-E2B-it-qat`、`Qwen3.8-27B | gemma-4-26B-A4B`、`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp | gemma-4-26B-A4B`。方向最稳的几条（Δ = b − a，单位 pp，括号里是两侧 `n_items`）：`LFM2.5-8B-A1B → Qwen3.5-9B` 是 +42.07/+44.51/+68.29（humaneval，164 题）、+40.24/+42.68/+64.02（humaneval-plus，164）、+41.00（gsm8k）与 +44.00（gsm8k-strict），各 100 题、+25.66/+28.95/+49.56（mmlu，912）、+11.38…+56.35（mbpp/mbpp-plus，378）；`Phi-4-mini → Qwen3.5-4B` 是 +39.04/+44.96/+11.62（mmlu，912）、+51.00/+60.00/+26.00（ifeval，100）；`Qwen3.5-4B → gemma-4-E2B-it-qat` 是 −50.00/−48.78/−35.00/−28.18/−22.26（humaneval、humaneval-plus、ifeval、mmlu 两格，164/164/100/912/912 题）；`Qwen3.8-27B → gemma-4-26B-A4B` 是 −78.26（humaneval-cpp，161）、−68.94（humaneval-py，161）、−19.96/−21.27（mmlu，912）；`GLM-4.7-Flash → Qwen3.8-27B` 是 +22.36（humaneval-cpp，161）、+24.22（humaneval-py，161）、+11.07（mmlu，912）、+12.00（gsm8k，100）。`Llama-3.2-3B → granite-4.1-3b` 在 3.30 bpw 上六列全负（−19.25…−33.54），到 4.12 bpw 变成 +13.0（humaneval-cpp）与 −25.47（humaneval-py）——方向随基准与档位分裂，见 `result.res5`。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" --key-cells`（实跑输出：152 行家族层可读格，带 `ci_a` / `ci_b` 与 `RES yes/no` 列）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '1,10p'`（实跑输出：`label_matched cells (tier 1): 1588`、`family cells, bpw_matched: 152 → resolvable 69`、`family pairs with cells: 43 (readable: 10, …)`）
- 已记录的限制：① 区间是**单跑的二项区间**，只覆盖抽样误差，不覆盖重测误差；② 这些格不独立（429 个 (家族对, 基准) 组，逐组格数见 (g) 段），69 不是 69 次独立重复；③ 家族 = 架构 + 训练配方 + tokenizer 的整包，上面任何一条 Δ 都不能拆成其中一份（`result.res6`）。

## 家族 × 量化档交互

### res5 :: 在固定规模对、固定其余身份栏、且**两档都是 `bpw_matched`** 的 99 个交互组里（35 组有 ≥2 个档），相邻档之间家族差的符号翻转共 8 次，集中在 8 个组：`Llama-3.2-3B | granite-4.1-3b` 一个对子在 6 个基准上同时翻（Q2_K 负、Q3_K_M 正），另有 `Phi-4-mini | Qwen3.5-4B`（arc_challenge）与 `Qwen3.5-4B | gemma-4-E2B-it-qat`（truthfulqa_mc2）各一次

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res4
- origin: `analysis/effects.py` 的 `interaction` 段
- evidence: 8 处翻转逐条点名：`humaneval` 上 `Llama-3.2-3B → granite-4.1-3b` 从 −33.54 pp（3.30 bpw，164 题）到 +14.02 pp（4.12 bpw）；`humaneval-cpp` 上 −19.25 → +13.04；`humaneval-plus` 上 −29.88 → +13.41；`mbpp` 上 −30.42 → +2.91；`mbpp-plus` 上 −26.19 → +7.14；`truthfulqa_mc2` 上 −3.10 → +3.26；`arc_challenge` 上 `Phi-4-mini → Qwen3.5-4B` 从 +14.5 pp（3.59 bpw）到 −2.0 pp（4.51 bpw）；`truthfulqa_mc2` 上 `Qwen3.5-4B → gemma-4-E2B-it-qat` 从 −0.5 到 +2.7。前六处的两档位宽差都被钉在 0.13–0.16 bpw（同一条量化阶梯的 Q2_K/Q3_K_M），所以翻转不能由比特预算漂移解释。家族排序按基准给出 13 个「基准 × 上下文」组，其中 2 组在 ≥2 个档上家族集合相同、可比：`humaneval-cpp` 的一组**翻转**（Q2_K 上 Llama > granite，Q3_K_M 上 granite > Llama），`humaneval-py` 上同一对两档都保持 Llama > granite。家族差与同组量化差放在同一个 pp 单位下比较：`Llama-3.2-3B | granite-4.1-3b` 在 arc_challenge 上 Δfam 从 +15.00 到 +4.00，而同组 granite 自己从 Q2 到 Q3 只动 −3.00 pp、Llama 动 +8.00 pp。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(b) sign of/,/^(c) family/p'`（实跑输出：`99 groups (35 with >= 2 levels); sign flips: 8` 与逐组符号串、逐条翻转详情）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(c) family/,/^(d) family/p'`（实跑输出：逐组的 `Δfam@low` / `Δfam@high` / `quantΔa` / `quantΔb` / `bpw span`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(d) family ordering/,$p'`（实跑输出：`13 bench×context groups, 2 comparable …, 1 change order` 与逐组排序）
- 已记录的限制：翻转只在「同一对规模 + 同一批其余身份栏 + 相邻两个档」上算；`__model`/`family_of` 的家族在同一个基准上往往挂着多个尺寸的文件，所以按家族排名的组大多因「同一家族在同一档上有多个模型」被跳过（脚本逐条打印被跳过的档与家族名），可比组只有 2 组。

## 边界

### res6 :: 这份读法是对**已经测过的格**做事后匹配，不是新测量；可读的家族对只有 10 个（另有 33 个有格但一格都不可读），每一格是单跑、无逐题产物，且**同一份权重在同比特预算下换配方就能挪动 58 pp**（`Qwen3.5-4B` 的 `IQ3_XXS` 对 `Q2_K_XL`，gsm8k 100 题），所以任何一个 Δ 只能读成「家族包效应」，不能读成「架构效应」

- author: measurement
- scope: general
- status: current
- kind: analysis
- from: result.res4, result.res8
- origin: `analysis/effects.py` 的 `counts.family_pairs_*` 与 (e)/(f) 两段
- evidence: 43 个家族对有受控格，其中 10 个至少有一格两侧位宽差 ≤ 半档，另外 33 个（`Bonsai-27B | Qwen3.8-27B` 等）**读不出家族差**，因为它们的每一格两侧位宽都差得超过半档——名单由 `effects.py` 的第一段整行打印。位宽闸门是本节唯一的人为选择，写成具名常量：档宽 `level_width_bpw = 0.5`，容差 `bpw_match_tol = 0.25`（半档）；不加闸门的计数照样给：`label_matched` 1588 格、其中 550 格区间不相交，而加了闸门只剩 172 格、家族层 152 格、69 格可分辨。三处必须与结论同时读的混杂：① 同一份权重、同一比特预算、换量化配方就能挪动分数——最大的三处是 `Qwen3.5-4B-UD-IQ3_XXS` 对 `Qwen3.5-4B-UD-Q2_K_XL` 在 gsm8k 上 +58.0 pp（3.69/3.67 bpw，100 题，区间不相交）、`LFM2.5-8B-A1B-a04-uni45` 对 `-m55-exq4` 在 humaneval 上 −48.2 pp（4.52/4.47 bpw，164 题）、`LFM2.5-8B-A1B-UD-Q2_K_XL` 对 `-m55-exq2` 在 gsm8k-strict 上 +20.0 pp（2.76/2.91 bpw，100 题）；同一批里也有接近 0 的（`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` 对 `Qwen3.8-27B` 的 10 个格 |Δ| ≤ 5.3 pp、一格都不可分辨），所以「配方」既不是恒为零、也不是恒定大小；② 单跑、无逐题产物：区间只覆盖抽样误差，不能拆到题目层，也不能拆成架构/训练/tokenizer 三份；③ 库里的家族标签由文件名给出（`mktables.family_of`），它保留尺寸 token，所以同一条产品线的不同尺寸在这里是两个家族、由尺寸闸门分开（`result.res3`）。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/family pairs with cells/,+1p'`（实跑输出：`family pairs with cells: 43 (readable: 10, not readable: [...33 个点名...])`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | grep "bpw gate"`（实跑输出：`bpw gate: |bpw_a − bpw_b| <= 0.25 bpw (half a 0.5 bpw quant level, measured tensor bpw)`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(f) recipe controls/,/(g) independence/p'`（实跑输出：56 行配方对照逐格表，`Δpp` 从 `-13.41` 到 `+58.00`）
- 未测（不是 0）：任何「同权重、不同架构」的受控对（a02 已证本库与盘上都不存在）；跨三个以上量化档的家族排序（可读的档位基本只有相邻两档）；agentic 基准上的家族差（无 GPU，`docs/plan/subprojects.md` 的 `agentic` 节）。

### res7 :: 这份清单的家族效应是**事后匹配**的读法：它只重排已经落在 `experiments.sqlite` 里的格，没有为任何一对新起一次测量，所以「家族差」的取值只在这批被测过的文件、基准、协议与位上成立

- author: measurement
- scope: general
- status: current
- kind: analysis
- from: result.res1, result.res6
- origin: `analysis/run_all.py`（只以 `mode=ro` 打开库；负控断言真库与真 fixture 前后字节相同）
- evidence: 负控里有一条断言：真库与真 fixture 在整条链跑完后 sha256 不变；脚本没有任何写库路径（连接串是 `file:…?mode=ro`），也没有起模型、没有 `report.html` 重建。清单的候选集完全由库里的行与 `mktables.family_of` 决定，脚本不含任何文件名白名单或手挑的家族对。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs_negative_control.py" | grep -E 'byte-identical'`（实跑输出：`ok the real database is byte-identical before and after` 与 `ok the real truth fixture is byte-identical before and after`）

## 同权重对照：标签拆分与配方变体（不进家族计数）

### res8 :: 把「同一份权重」的配对单独拿出来看，它们是这份数据里唯一的「已知同权重」读数：`family_of` 已经把 `Qwen3.6-35B-A3B` / `Qwen_Qwen3.6-35B-A3B` 与 `LFM2.5-8B-A1B` / `-m55-exq2` / `-m55-exq4` 归成同族（所以它们不再是候选），剩下 56 格是同一家族、同一份权重（实测参数量相同）、两侧位宽差 ≤ 半档的配方对照；它们的 Δ 从 −13.41 到 +58.00 pp，其中 6 格区间不相交，说明「配方」这一段本身就能把分数搬动，家族差必须带着这条读

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res2
- origin: `analysis/pairs.py` 的 `recipe_controls`（同族 + 同实测参数量 + |Δbpw| ≤ 0.25）+ `analysis/effects.py` 的 (f) 段
- evidence: 56 格配方对照，6 格可分辨；最大的几处是 `Qwen3.5-4B-UD-IQ3_XXS` 对 `Qwen3.5-4B-UD-Q2_K_XL`（3.69/3.67 bpw）+58.0 pp（gsm8k 与 gsm8k-strict，100 题，`lmeval-…-reasoning-on`）、`Qwen3.5-2B-UD-IQ3_XXS` 对 `Qwen3.5-2B-UD-Q2_K_XL`（3.91/4.06）+35.0 pp（gsm8k-strict，100 题）、`LFM2.5-8B-A1B-UD-Q2_K_XL` 对 `LFM2.5-8B-A1B-m55-exq2`（2.76/2.91）+20.0 pp（gsm8k-strict）与 +11.4 pp（mmlu，912 题）、−10.3 pp（mbpp，378 题）。另一类「家族名不同、但张量形状相同」的格（173 个标签格 / 20 个位宽格）单列在 (e) 段，它们是 a04 的比特分配臂与 a10 的第三方量化臂：`LFM2.5-8B-A1B-a04-uni45` 对 `LFM2.5-8B-A1B` 在 humaneval 上 −48.2 pp（4.52/4.47 bpw，164 题，与 a04 记录的「exq4 在 4.48 bpw 上 HE 0.14」一致），而 `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` 对 `Qwen3.8-27B` 的 10 个格 |Δ| ≤ 5.3 pp、一格都不可分辨。这两类都**不进**家族计数，理由写在清单里：同参数量意味同一套张量形状（同一架构脚手架），差异是权重/配方而不是架构。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" | grep "recipe controls"`（实跑输出：`recipe controls (same weights, bpw-matched): 56 cells`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(e) same-scaffold/,/(f) recipe controls/p'`（实跑输出：20 行同脚手架格，`Δpp` 从 `-48.17` 到 `+11.53`）
- 已记录的限制：`family_of` 不剥 `-a04-uni45`、`-GSQ-RCO-…-mtp` 这类后缀，所以这些文件在标签上是「不同家族」；把它们从家族计数里移走靠的**不是**标签而是实测参数量相等这一条，判据与例子都打印在上面，读者可以逐条核。

## 记录：本层被抓到并已修掉的错

三处都不是「文档措辞」，都会改变清单或结论本身，记在这里是因为它们是这份清单可信度的一部分：

1. **用 `experiments.__model` 当家族**（第一版）：它是 `exp.py` 从文件名解析的标签，会把同一份权重拆成两个「家族」（`Qwen3.6-35B-A3B` / `Qwen_Qwen3.6-35B-A3B`，实测参数量都是 35505251456；`LFM2.5-8B-A1B` / `-m55-exq2` / `-m55-exq4`，都是 8467856832），于是配方对被当成跨家族对写进了家族计数。现在家族取 `mktables.family_of`（报告那一套），同权重格单独成表（`result.res8`）。
2. **按行取 `__model` 会把跨家族候选全静默丢掉**：字典推导后写覆盖前写，库里有 65 个文件的 `__model` 同时有值和 NULL，取到 NULL 之后这些文件与所有文件都「同族」，候选只剩 0 条而脚本仍 exit 0。现在家族由 `family_of` 算，候选为空时脚本 exit 2。
3. **「同一量化档」只靠 `__quant` 栏**（第一版把 1112 个格都叫「受控」）：`__quant` 为 NULL 时这一栏什么都没钉住（库里 1542 个格的标签是 NULL），于是两侧位宽差最大 3.9 bpw 的格也进了「同档」。现在一层叫 `label_matched`（标签，只作清单）、一层叫 `bpw_matched`（实测 bpw 差 ≤ 半档，所有家族结论只在这一层上算），两层的计数、闸门常量与「不加闸门时是多少」都在 `result.res2`/`result.res6` 里。

三处都被 `run_all.py` 的关系式断言与两个负控盯着：候选数 = 排除数 + 有格候选数、每格的 `bpw_matched` 必须等于闸门、清单里不许有同族格、改身份栏/改尺寸/删真值必掉对并点名、把一对分数改成相等则 `family_resolvable` 或 `flips` 必变。
