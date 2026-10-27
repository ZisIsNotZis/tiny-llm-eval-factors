# a15 模型家族（架构代理）— 结果

每条事实一行一个陈述；数字后面跟一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
本层只读 `experiments.sqlite`（以 `mode=ro` 打开），真参数量取 a02 入库的 GGUF fixture；所有命令在仓库根执行。
口径与实现说明在 `analysis/` 的脚本头部；计划与派工在 `PLAN.md`；本层的窄规则在 `AGENTS.md`。

## 本层的三件东西

### res1 :: 本层的唯一验收入口是一条命令 `python3 "docs/subprojects/a15-模型家族/analysis/run_all.py" --selftest`，它当场跑受控对清单、效应与交互、以及两个负控，十八条自检全绿，整条链在本机 10 秒内跑完（多次实跑落在 4.9–7.9 s，秒数随机器负载浮动，验收只认 rc 与 18/18）

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/run_all.py`
- evidence: 输出末尾一行 `OK 18/18 checks green | candidates=24428 controlled=1112 excluded=23316 cells_with_intervals=1080 resolvable=469 resolvable_bpw_matched=56 bpw_matched=134 flips=44 flips_constant_gap=7 orderings_unstable=1`（行尾还有一个秒数，随负载浮动）；两个负控各自打印自己的结论行（清单侧 18/18、效应侧 10/10 绿）。自检里有三条是关系式而不是快照常量：候选数 = 被排除候选数 + 产出受控格的候选数、每一格的尺寸差 ≤ 容差、每一格的两个文件都在 `families` 表里；另有两条确定性断言：两个负控把同样的输入重跑到临时目录，得到的 JSON 与入库的那两份**逐字节相同**。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/run_all.py" --selftest`（实跑输出：`OK 18/18 checks green | candidates=24428 controlled=1112 excluded=23316 … orderings_unstable=1 | <秒>s`，rc=0）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs_negative_control.py"`（实跑输出：`18/18 checks green` + `NEGATIVE CONTROL OK: the inventory loses the mutated pair and names the reason; the unmodified run is green`，rc=0；四处改动分别是改 `temp`、把尺寸差改成 11%、删掉真值、以及真库字节不变）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects_negative_control.py"`（实跑输出：`10/10 checks green`，其中 `resolvable 497 → 496` 与 `flips 44 → 43` 两处改动都被点名）
- 边界：本层**不启任何模型**、不重建 `report.html`、不跑 `./reproduce.sh`；它只读一个已经在盘上的 `experiments.sqlite`，所以「结论成立」这句话的范围是这些已测的格，不是新测量（见 `result.res6`）。

## 受控对清单

### res2 :: 从库里的 3379 行枚举出 24428 个跨家族候选（同基准 + 同量化档 + 两个不同 `__model`），其中 1112 个通过全部十六条身份栏、`protocol IS NOT NULL`、`_score IS NOT NULL` 与「实测参数量相差 ≤10%」的判据成为受控格，23316 个被逐条登记原因排除，没有人工白名单

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res1
- origin: `analysis/pairs.py`（读库 + a02 的 GGUF fixture，写 `analysis/pairs.json`）
- evidence: 候选漏斗在脚本的一次运行里全部打印：同一个基准上跨家族的模型文件对共 59961 个，其中 20527 个还共享一个量化档（成为候选的一部分），39434 个从不共享量化档（它们是交互轴的原料，不是受控对照，理由写在脚本头部）；另有 3901 个候选有一侧文件**所有**行的 `__model` 都为 NULL（跨不跨家族不可判），登记为 `family_unknown`。排除原因逐条计数（同一候选只记第一条成立的原因）：`size_gt_10pct=13278`、`family_unknown=3901`、`protocol_null=2770`、`identity_mismatch:*` 合计 3309（其中点名最多的是 `max_tokens=899`、`protocol=558`、`protocol,n_items=487`、`reasoning,max_tokens=456`）、`score_null=44`、`score_ambiguous=14`。37 个家族对有受控格，格子最多的三对是 `Qwen3.5 | gemma-4` 127 格、`Qwen3.5 | Ternary-Bonsai-Q2_0_g64` 92 格、`Qwen3.8 | gemma-4` 62 格。清单是确定性的：格按 (基准, 两个文件名, 身份键) 排序后发 `famNNNN` 号，同样输入第二次跑出逐字节相同的 JSON。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py"`（实跑输出：`candidates (bench+quant+filepair): 24428`、`controlled cells: 1112`、`excluded candidates: 23316`、`SELFCHECK candidates == excluded + candidates_with_cells: 24428 == 23316 + 1112 ok`、`COUNT candidates=24428 controlled=1112 excluded=23316`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" | sed -n '/excluded by reason/p'`（实跑输出即上面那串逐原因计数）
- repro: `python3 -c "import sqlite3; c=sqlite3.connect('file:experiments.sqlite?mode=ro',uri=True); r=c.execute('select model, count(distinct case when __model is not null then __model end) v, sum(__model is null) n from experiments group by 1').fetchall(); print('files:', len(r), 'value+NULL:', sum(1 for m,v,n in r if v and n>0), 'only NULL:', sum(1 for m,v,n in r if not v))"`（实跑输出：`files: 212 value+NULL: 65 only NULL: 6`）
- 已记录的限制：`__model` 是 `exp.py` 从文件名解析出来的家族标签，不是模型元数据；同一个文件的某些行 `__model` 为空（212 个文件里 65 个既有值又有 NULL 行、6 个全为 NULL），所以家族按文件取唯一非空值，全 NULL 的文件登记 `family_unknown` 而不是当同族处理——按行取最后一个值会把 `{None,'Qwen3.5'}` 读成 NULL，从而把所有候选静默判成「同族」（这个错在本次实现里真出过一次，见 `result.res5` 末段）。

### res3 :: 「实测参数量相差 ≤10%」这一条单独拒掉了 13278 个候选、覆盖 171 个家族对，主要不是因为它太严，而是因为同一个家族标签下挂着多个不同尺寸的文件（`gemma-4` 在库里有 E2B/E4B/12B/26B 四档），所以「同家族、不同尺寸」的配对先被尺寸判据挡在门外

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res2
- origin: `analysis/pairs.py` 的 `counts.family_pairs_rejected_by_size`
- evidence: 被尺寸判据拒掉的家族对按候选数排序，前几名是 `Qwen3.5 | gemma-4` 1655、`Ternary-Bonsai-Q2_0_g64 | gemma-4` 410、`Qwen3.5 | granite-4.1` 362、`gemma-4 | granite-4.1` 322、`NVIDIA-Nemotron-3 | gemma-4` 318、`GLM-4.7 | gemma-4` 312；而真正活下来的 `Qwen3.5 | gemma-4` 格只用 `gemma-4-E2B-it`（实测参数量与 `Qwen3.5-4B` 差 9.5%）与 `gemma-4-26B-A4B` 对 `Qwen3.8-27B`（差 7.6%）这类同尺寸配对。判据用的是 GGUF 张量参数量（a02 的 fixture），不是文件名里的 `4B`/`E2B` 标签。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" | sed -n '/10% size criterion/p'`（实跑输出：`10% size criterion rejects: 13278 candidate(s) over 171 family pair(s); largest:` 后跟逐对计数）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" | grep -E 'identity_mismatch|size_gt_10pct'`（实跑输出：逐原因计数那一行）

## 家族效应

### res4 :: 在 1112 个受控格里，1080 个能按各自的 `n_items` 给出 95% Wilson 区间（32 个格 `n_items` 为空，只能写「题数未测」，不写 0），全集的 469 格两侧区间不相交；但把「两侧位宽差 ≤ 半档（0.25 bpw）」这条可读性闸门加上去之后只剩 134 格可读、其中 56 格可分辨——家族差的量级远超噪声，可读的格却只占一成

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res2
- origin: `analysis/effects.py`（读 `analysis/pairs.json`，写 `analysis/effects.json`）
- evidence: 位宽是测出来的（GGUF 张量 bpw），不是标签：全集的位宽差从 0.025 跨到 3.937 bpw，把「同基准同 `__quant`」当受控对只是名字上的同档，真正钉住比特预算的是 bpw。可读子集里方向最稳的是 Qwen3.5 与 gemma-4：在 3.71 bpw 附近 gemma-4 减 Qwen3.5 是 −50.00（humaneval）、−48.78（humaneval-plus）、−35.00（ifeval）、−28.18（mmlu）、−22.26（mmlu 另一格），到 4.56 bpw 附近收窄到 −6.71/−7.32/−9.00/−15.24/−13.76；同一批格里 `Llama-3.2-Instruct — granite-4.1` 是 −33.54（humaneval，3.30 bpw）到 +14.02（4.12 bpw），`LFM2.5-m55-exq4 — Qwen3.5` 是 +68.29（humaneval）、+44.00（gsm8k-strict）、+49.56（mmlu）。反向的 sanity 对照也在同一张表里：`Qwen3.6 — Qwen_Qwen3.6` 是同一份基座权重（实测参数量都是 35505251456）换了两套量化配方与两个家族标签，在 3.87 bpw 附近 12 格上的家族差是 −2.41…+5.00 pp、**没有一格可分辨**。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" --key-cells`（实跑输出：134 行可读格逐格表，带 `ci_a` / `ci_b` 与 `RES yes/no` 列）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '1,8p'`（实跑输出：`controlled cells: 1112`、`cells with Wilson intervals: 1080 (n_items missing: 32)`、`resolvable (all cells): 469`、`bpw_matched cells (<= 0.25 bpw) : 134 → resolvable 56`）
- 已记录的限制：单跑，没有重复测量的噪声地板可用（i01 在确定性解码下测到逐题地板为 0 道题，但那是对特定 harness 的结论）；因此这里的「可分辨」只说明两个二项区间不相交，不说明单次运行的重测稳定。

## 家族 × 量化档交互

### res5 :: 在固定规模对、固定其余身份栏的 437 个交互组里（294 组有 ≥2 个量化档），相邻量化档之间家族差的符号翻转共 44 次；把「两档的位宽 handicap 相差 ≤ 半档」也钉住之后只剩 7 次，其中两档位宽完全相等的只有 1 次——翻转大多能由位宽漂移解释，剩下 7 处是真正的交互

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.res4
- origin: `analysis/effects.py` 的 `interaction` 段
- evidence: 7 处常数 handicap 的翻转逐条在输出里点名：`bfcl-irrelevance` 上 Qwen3.5—gemma-4 从 −16.2 pp（3.89 bpw）翻到 +3.8 pp（4.81 bpw）；`bfcl-multiple` 上 +1.5 → −3.0；`bfcl-parallel_multiple` 上 +18.0 → −3.0；`humaneval-cpp` 上 Llama-3.2-Instruct—granite-4.1 从 −19.3 pp（Q2_K，3.30 bpw）翻到 +13.0 pp（Q3_K_M，4.12 bpw，这一处的两档位宽 handicap 都在 0.25 bpw 之内，是全库唯一一处「两档都位宽相等」的翻转）；`humaneval-cpp` 上 Qwen3.5—gemma-4 从 −4.3 到 +8.1；`ifeval` 上 GLM-4.7—Qwen3.8 从 +6.5 到 −1.5；`truthfulqa_mc2` 上 Llama-3.2-Instruct—granite-4.1 从 +4.0 到 −0.3。家族排序按基准给出 15 个「基准 × 上下文」组，其中 3 组在 ≥2 个量化档上家族集合相同、可比：`humaneval-cpp` 的一组排序**翻转**（Q2_K 上 Llama > granite，Q3_K_M 上 granite > Llama），`humaneval-py` 上同一对两档都保持 Llama > granite。同一组里家族差与同族跨档的量化差放在同一个 pp 单位下比较：`bfcl-multiple` 的家族差 +1.50/−3.00 pp，而 Qwen3.5 自己从 Q2 到 Q3 涨了 +7.00 pp、gemma-4 涨了 +2.50 pp。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(b) sign of/,/^(c) family/p'`（实跑输出：`sign flips: 44 (constant bit-width handicap: 7; both levels bpw_matched: 1)` 与逐组符号串、逐条翻转详情）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(c) family/,/^(d) family/p'`（实跑输出：逐组的 `Δfam@low` / `Δfam@high` / `quantΔa` / `quantΔb` / `bpw span`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/^(d) family/,$p'`（实跑输出：`15 bench×context groups, 3 comparable …, 1 change order` 与逐组排序）
- 已记录的限制：翻转只在「同一对规模 + 同一批其余身份栏 + 相邻两个量化档」上算；库里绝大多数 `__model` 家族在同一个基准上都挂着多个尺寸的文件，所以按家族排名的组大多因为「同一家族在同一档上有多个模型」被跳过（脚本逐条打印被跳过的档与家族名），家族排序这一项的可比组只有 3 组。

## 边界

### res6 :: 这份读法是对**已经测过的格**做事后匹配，不是新测量：家族标签是「架构 + 训练配方 + tokenizer」的整包，单跑、无逐题产物，所以任何一个 Δ 只能读成「家族包效应」，不能读成「架构效应」；可读的家族对只有 11 个，另有 26 个家族对有格但一格都不可读

- author: measurement
- scope: general
- status: current
- kind: analysis
- from: result.res4, result.res5
- origin: `analysis/effects.py` 的 `counts.family_pairs_*` 与 `analysis/pairs.py` 的口径
- evidence: 37 个家族对有受控格，其中 11 个至少有一格两侧位宽差 ≤ 半档（`GLM-4.7 | Qwen3.8`、`LFM2.5 | LFM2.5-m55`、`LFM2.5 | LFM2.5-m55-exq2`、`LFM2.5 | Qwen3.5`、`LFM2.5-m55 | Qwen3.5`、`LFM2.5-m55-exq4 | Qwen3.5`、`Llama-3.2-Instruct | granite-4.1`、`Phi-4-instruct | Qwen3.5`、`Qwen3.5 | gemma-4`、`Qwen3.6 | Qwen_Qwen3.6`、`Qwen3.8 | gemma-4`），另外 26 个（`Bonsai-Q1_0 | Qwen3.8`、`Bonsai-Q1_0 | gemma-4`、`GLM-4.7 | GLM-4.7-UD-TQ1_0`、`GLM-4.7-UD-TQ1_0 | Qwen3.8`、`LFM2.5 | LFM2.5-m55-exq4`、`LFM2.5 | Ornith-1.5`、`LFM2.5 | Ternary-Bonsai-Q2_0_g64`、`LFM2.5-m55 | LFM2.5-m55-exq2`、`LFM2.5-m55 | LFM2.5-m55-exq4`、`LFM2.5-m55 | Ornith-1.5`、`LFM2.5-m55 | Ternary-Bonsai-Q2_0_g64`、`LFM2.5-m55-exq2 | LFM2.5-m55-exq4`、`LFM2.5-m55-exq2 | Ornith-1.5`、`LFM2.5-m55-exq2 | Qwen3.5`、`LFM2.5-m55-exq2 | Ternary-Bonsai-Q2_0_g64`、`LFM2.5-m55-exq4 | Ornith-1.5`、`LFM2.5-m55-exq4 | Ternary-Bonsai-Q2_0_g64`、`NVIDIA-Nemotron-3 | Phi-4-instruct`、`NVIDIA-Nemotron-3 | Qwen3.5`、`NVIDIA-Nemotron-3 | Ternary-Bonsai-Q2_0_g64`、`Ornith-1.5 | Qwen3.5`、`Phi-4-instruct | Ternary-Bonsai-Q2_0_g64`、`Qwen3.5 | Ternary-Bonsai-Q2_0_g64`、`Qwen3.6 | Qwen_Qwen3.5`、`Qwen_Qwen3.5 | Qwen_Qwen3.6`、`Ternary-Bonsai-Q2_0_g64 | gemma-4`）**读不出家族差**，因为它们的每一格两侧位宽都差得超过半档。三处必须与结论同时读的混杂：① 11 个可读家族对里有三个不是「换家族」——`Qwen3.6 | Qwen_Qwen3.6` 是同一份基座权重（实测参数量都是 35505251456）被两个 `__model` 标签拆开，`LFM2.5 | LFM2.5-m55` 与 `LFM2.5 | LFM2.5-m55-exq2` 是同一份 8467856832 参数权重换专家层比特分配（a04 的那两条臂），它们的可读格给出 −10.32…+20.00 pp 的差（`LFM2.5 | LFM2.5-m55-exq2` 在 gsm8k-strict 上 +20.00 pp 且区间不相交，`LFM2.5 | LFM2.5-m55` 最大只有 +3.00 pp），这说明「配方」这一段本身就能搬动分数；② 位宽闸门自身有一个每次运行都算的自检：档宽 0.5 bpw、容差 0.25 bpw 必须小于测到的最小档间距，实测最小档间距 0.2873 bpw，故闸门成立（`warnings=0`）；③ 每一格是一条（或若干条同分）run，没有逐题产物，所以「家族差」不能拆到题目层，也不能拆成架构/训练/tokenizer 三份。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | sed -n '/family pairs with cells/,+1p'`（实跑输出：`family pairs with cells: 37 (readable: 11, not readable: [...26 个点名...])`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" | grep "smallest level step"`（实跑输出：`smallest level step seen    : 0.2873 bpw (level width 0.5 bpw, tolerance 0.25 bpw)`）
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/effects.py" --key-cells | grep "Qwen3.6 — Qwen_Qwen3.6"`（实跑输出：12 行，`Δpp` 从 `-2.41` 到 `+5.00`，`RES` 列全为 `no`）
- 未测（不是 0）：任何「同权重、不同架构」的受控对（a02 已证本库与盘上都不存在），以及跨量化档更多档位上的家族排序——可读的档位基本只有相邻两档（Q2、Q3），再往上一档的格子两侧位宽差就超闸门。

### res7 :: 这份清单的家族效应是**事后匹配**的读法：它只重排已经落在 `experiments.sqlite` 里的格，没有为任何一对新起一次测量，所以「家族差」的取值只在被测过的文件、基准、协议与位上成立，换协议或换新家族都需要新测量

- author: measurement
- scope: general
- status: current
- kind: analysis
- from: result.res1, result.res6
- origin: `analysis/run_all.py`（只以 `mode=ro` 打开库；负控断言真库与真 fixture 前后字节相同）
- evidence: 负控里有一条断言：真库与真 fixture 在整条链跑完后 sha256 不变；脚本没有任何写库路径（连接串是 `file:…?mode=ro`），也没有起模型、没有 `report.html` 重建。清单的候选集完全由库里的行决定，脚本不含任何文件名白名单或手挑的家族对。
- repro: `python3 "docs/subprojects/a15-模型家族/analysis/pairs_negative_control.py" | grep -E 'byte-identical|sha'`（实跑输出：`ok the real database is byte-identical before and after` 与 `ok the real truth fixture is byte-identical before and after`）

## 记录：本次实现里被抓到并已修掉的错

两个错都不是「文档措辞」而会改变清单本身，记在这里是因为它们是这份清单可信度的一部分：

1. **按行取 `__model` 会把跨家族候选全静默丢掉。** 初版用 `{row.model: row.__model}`（字典推导，后写覆盖前写）建家族表；库里有 65 个文件的 `__model` 同时有值和 NULL，取到 NULL 之后这些文件与所有文件都「同族」，于是候选只剩 0 条、`controlled` 为 0 而**脚本仍然 exit 0**。现在按文件取唯一非空值，一个文件出现两个不同非空家族值直接抛错；候选为空或受控为空时脚本 exit 2。
2. **候选的量化档没有钉在候选上。** 初版枚举候选时不区分量化档，只要求「两行的 `__quant` 相等」，于是同一格可以被两个不同 `quant` 的候选各报一次（受控格从 1112 虚增到 1150）。现在候选就是 (基准, `__quant`, 文件对)，配对只取同 `__quant` 的行，同一格只属于一个候选，账才平。

两处都被 `run_all.py` 的关系式断言与负控盯着：候选数 = 排除数 + 有格候选数、每格尺寸差 ≤ 容差、改身份栏/改尺寸必掉对并点名、把一对分数改成相等则 `resolvable` 或 `flips` 必变。
