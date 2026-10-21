# a04 MoE 各层比特分配 — 结果

每条事实一行一个陈述；有数字就必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
测量（`kind: measured`）与分析（`kind: analysis`）分开写，analysis 不覆盖任何数字。

## 证据绑定（读这一层之前先看这里）

本层的**分配轮廓只有一个来源**：a03 的入库夹具 `docs/subprojects/a03-量化方案与厂商/analysis/fixtures/alloc_map.json`
（51 个文件的逐张量类别 params / bytes / bits，由 gguf 张量信息段实测；sha256 与重建见 `a03::fixtures`）。本层只读它、不改它、不存第二份。
本层的**分数只有一个来源**：`experiments.sqlite`（只读连接），任何一条是否仍成立用 `analysis/run_all.py` 判定。
读数装置：`analysis/profiles.py`（轮廓表 / 同参数对 / 分配距离 `L1_pw` / 分数表）、`analysis/alloc_pairs.py`（逐对区间）、
`analysis/run_all.py`（全部检查，退出码即结论）。

两个量必须分清，混了就会把总比特说成分配：

    Δbpw  = bpw_file(A) - bpw_file(B)                 总有效位宽差（整个文件）
    L1_pw = Σ_c |b_c(A) - b_c(B)| · p_c / p_total     参数加权分配距离（比特/参数）

`L1_pw ≈ |Δbpw|` 说明这一对基本只是总比特变了；`L1_pw ≫ |Δbpw|` 才是总比特钉住、比特挪了位置。**只有后者能当作分配的对照。**

## 一、语料里有什么（`kind: measured`）

### moe-population :: a03 夹具的 51 个文件里有 **14 个是 MoE**（有 `ffn-expert` 桶），加上本层自建的 1 个共 **15 个**，分属 5 族：LFM2.5-8B-A1B（6 个，含自建臂）、GLM-4.7-Flash（3）、Qwen3.6-35B-A3B（3）、gemma-4-26B-A4B（2）、Qwen3.5-35B-A3B（1）；专家桶占参数量 90.51%–92.99%，即这些模型的「比特放在哪」几乎完全由「专家层拿多少」与「非专家层拿多少」两个数决定。

- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `docs/subprojects/a03-量化方案与厂商/analysis/fixtures/alloc_map.json` 的 `models.<file>.classes` 里有没有 `ffn-expert` 桶；占比 = `classes['ffn-expert'].params / n_params`
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py" | head -3`（配上 `--family` 看单族轮廓表）
- 说明：这是本轴的可行域——能做的分配对照只可能出自这 5 族。

### profile-lfm :: LFM2.5-8B-A1B 是唯一有 **5 份同一套 base 权重（参数数同为 8,467,856,832）** 且都在标准六基准上跑过的族，五份的分配向量差别极大：`UD-Q2_K_XL`（2.764，attn 5.713 / embed 5.500 / 稠密 FFN 5.854 / 专家 2.603）、`exq2`（2.918，5.535 / 6.563 / 5.854 / 2.625）、`UD-Q3_K_XL`（3.782，8.500 / 8.500 / 8.500 / 3.529）、`m55-Q3_K_M`（3.881，4.002 / 6.563 / 3.958 / 3.792）、`exq4`（4.483，3.031 / 6.563 / 2.896 / 4.500）；专家桶占 91.535% 参数，attn 0.743%、embed 3.096%、稠密 FFN 1.040%、`other` 3.568%。
- author: measurement
- scope: specific
- status: current
- kind: measured
- evidence: `alloc_map.json` 的五个条目（逐类 `bits`）与 `n_params`；专家/非专家的分类法见 `a03::alloc-qwen36` 的拆桶说明（`_exps` / `_shexp` / `ffn_gate_inp` / 其余）
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py" --family LFM2.5-8B-A1B`
- 说明：五份里两份是本仓自建（`.wrapup/m55_prebuild.sh` 用 `llama-quantize --tensor-type 'ffn_(gate|up|down)_exps=<T>'` 造的 `m55-*`），所以「换分配」在本族是同源、同工具链的改动，不是换上传者。

### pivots :: 全语料里「参数数相同（同一套 base 权重）且 |Δbpw| ≤ 0.15」的文件对只有 **4 对**，其中 **2 对是 MoE**，两对的分配距离都是 `L1_pw = 0.381` 比特/参数、而总位宽差只有 +0.025 与 −0.099——这两对是全语料里唯一「总比特钉住、比特大幅挪位」的 MoE 对照，方向也正好相反：Qwen3.6-35B-A3B 那一对是 attn 8.500→4.936、embed 8.500→3.438、专家 3.542→3.734；LFM2.5-8B-A1B 那一对是 attn 8.500→4.002、embed 8.500→6.563、稠密 FFN 8.500→3.958、专家 3.529→3.792。
- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `alloc_map.json` 逐类 `bits` 与 `params`；`profiles.py` 的 `L1_pw` 定义
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py"`
- 说明：另外 2 对（Qwen3.5-4B `L1_pw` 0.337、Qwen3.5-2B 0.427）是稠密模型，没有 `ffn-expert` 桶，只作分配装置的旁证，不进本轴的策略判定。
- 说明：两对 MoE 的分配差都集中在**占比很小的桶**上（attn/embed/稠密 FFN 合计 4%–6% 参数），所以 0.381 比特/参数的位移是靠把这两个桶抬到 8.5、同时把专家桶压低 0.19–0.26 换来的；这两对**都不含**「专家桶被压到 2.6」或「专家桶抬到 4.5」的配置。

## 二、三个已知策略的实测分数（`kind: measured`）

### three-arm-scores :: LFM2.5-8B-A1B 的五份文件在标准六基准上（HumanEval+ 164 题 / MBPP+ 378 / MMLU 912 / ARC-c 100 / GSM8K 100 / IFEval 100，全部 greedy、temp 0）分数是：`UD-Q2_K_XL` 0.3110 / 0.4048 / 0.3125 / 0.3800 / 0.7400 / 缺；`exq2` 0.2866 / 0.3280 / 0.4265 / 0.4600 / 0.7800 / 0.3900；`UD-Q3_K_XL` 0.3598 / 0.4630 / 0.4803 / 0.4300 / 0.7800 / 0.4700；`m55-Q3_K_M` 0.3354 / 0.4815 / 0.4474 / 0.4600 / 0.7500 / 0.5700；`exq4` 0.1341 / 0.2381 / 0.2873 / 0.3700 / 0.5300 / 0.3900。
- author: measurement
- scope: specific
- status: current
- kind: measured
- evidence: `experiments.sqlite` 的 `model LIKE 'LFM2.5-8B-A1B-%'` 行（`_bench` ∈ 六列，取该格 `n_items` 最大的那一行），协议 `evalplus-0.3.1-openai-chat-greedy-plus` 与 `lmeval-0.4.13-{gguf-shim,chat}-reasoning-off`
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py" --scores LFM2.5-8B-A1B`
- 说明：`UD-Q2_K_XL` 的 IFEval 是**缺**（该文件没有这一格），不是 0。这条只报实测值，判定归 `strategy-verdict`。

### migrated-res8 :: 迁移前的 `result.yaml::res8` 那组三点（均匀 3.88 → HumanEval+ 0.335 / MMLU 0.447；专家压到 IQ2/Q2、其余高位 2.92 → 0.287 / 0.427；专家 Q4_K、其余 Q2_K 4.48 → 0.134 / 0.287）与 `three-arm-scores` 的三个对应格逐位一致（0.3354 / 0.4474、0.2866 / 0.4265、0.1341 / 0.2873），三个文件就是 `m55-Q3_K_M`、`m55-exq2`、`m55-exq4`。
- author: measurement
- from: result.three-arm-scores
- scope: specific
- status: current
- kind: measured
- retracted: 原 `res8` 的措辞把这三点的差别读成「专家层比特分配」的效应，撤回——三个文件的总位宽分别是 3.881 / 2.918 / 4.483，`Δbpw` 达 0.963 与 1.564，远大于本层「钉住」档（≤0.05）与最宽档（≤0.45），所以这三点的分数差**不能**归因给分配；能归因给分配的是 `pivots` 那两对。
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py" --scores LFM2.5-8B-A1B`
- 会推翻它：找到第三条能让这三点在同总位宽下复现的配方（那就是 `WP4` 要做的事，见 `PLAN.md`）。

### budget-ruler :: 把 `Δbpw` 折成分数的尺子借用 a03 的同族斜率（每 +1 比特/参数：HumanEval+ +0.1779、MBPP+ +0.1329、MMLU +0.1084、GSM8K +0.2000、IFEval +0.1522），于是 `exq2`→`exq4` 的 +1.564 比特**本该**值 HumanEval+ +0.278 / MMLU +0.170，实测却是 −0.153 / −0.139，即符号相反；而 `pivots` 那两对的 `|Δbpw|` 只值 HumanEval+ 0.0029–0.0176，与其上任何观测差都不是同一个量级。
- author: measurement
- from: result.pivots, result.three-arm-scores
- scope: general
- status: current
- kind: measured
- evidence: 斜率来自 `a03::slopes`（本层只引用，不重测）；分数差来自 `three-arm-scores`；`Δbpw` 来自 `alloc_map.json`
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py" --family LFM2.5-8B-A1B`（`Δbpw`）与 `--scores LFM2.5-8B-A1B`（分数）；斜率本身用 `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --slopes`
- 说明：这条是「多给比特反而更低」这个现象的形状化：不是「比特没用」，是**这 1.564 比特被放在了错误的地方**（专家 2.625→4.500，同时非专家被砍 2.5–2.9 比特）。它把问题变成分配问题而不是预算问题，但还不能单独当分配的判定，因为总位宽也一起变了。

## 三、三个策略与受控对照（`kind: measured`）

### strategies :: 按 `AGENTS.md` 第 1 条的机械规则（专家桶 vs 层桶 = **attn / 稠密 FFN / 共享专家**的参数加权均值，带宽 0.5 比特/参数）把 **15 个** MoE 文件分成 3 个策略：**非专家优先 12 个**、**均匀 2 个**（`m55-Q3_K_M` 专家 3.792 vs 层桶 3.977；自建臂 4.515 vs 4.722）、**专家优先 1 个**（`m55-exq4`，专家 4.500 vs 层桶 2.952）；`embed` 与 `other` **不参与方向判定**（K-quant 模板把 `embed` 钉在 4.5–8.5、`other` 是混杂桶，两者都不是「层」），但一并打印。规则文字与代码逐字一致（`LAYER_BUCKETS = (attn, ffn-dense, ffn-shexp)`）；另一个候选口径的后果是机械可查的：把 `embed` 也算进 `b_layer`，`exq4` 从**专家优先**翻成**非专家优先**、「专家优先」在 15 个文件里归零（14 非专家优先 / 1 均匀 / 0 专家优先），`strategy-counts` 断言随之失效——所以桶定义只能有一份，就是这三个桶。
- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `alloc_map.json` 逐类 `bits` 与 `params`；分类规则在 `AGENTS.md`
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py"`
- 说明：12/1/1 这个分布本身就是结果——本库的每条「非专家优先」配方（unsloth UD-XL 系列、本仓 exq2、GLM/gemma 的 UD 档）都把注意力/稠密层抬到远高于专家层，而**均匀**与**专家优先**各只有一个文件，所以后两者在语料里几乎没有对照可用。

### pinned-null :: 总比特钉住的 MoE 对照只有 2 对，两对的分配距离都是 `L1_pw = 0.381` 比特/参数；两对合计 **16 个有区间的格，区间不含 0 的 0 个**，最大半宽 0.135（≤0.05 档：1 对、8 格、0 个不含 0、最大半宽 0.134）。也就是说：把 0.381 比特/参数从专家层挪到非专家层（或反向），在本设计下六基准上**全部不可分辨**。
- author: measurement
- from: result.pivots
- scope: general
- status: current
- kind: measured
- evidence: `alloc_pairs.py --summary` 的逐档统计；逐格差值与区间用 `--pinned`；区间是两比例差的 Newcombe method 10，`n` 取该格 `n_items`，TruthfulQA 不套区间
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --summary`
- 说明：这两对的 `|Δbpw|` 分别只值 HumanEval+ 0.0044 与 0.0177，所以「预算部分」也解释不了任何观测差；观测差最大的是 LFM 那对的 IFEval +0.100 [−0.038,+0.233]（100 题，跨 0）。
- 会推翻它：同两对文件同配置重跑出现某一列区间不含 0 且方向稳定的差（复现负控未测，见 `unmeasured-items`）。

### expert-bound :: 钉住总比特时专家桶能挪多少有一个由架构决定的上界 `(1−s_exp)/s_exp × 层桶跨度`：LFM2.5-8B-A1B（专家占 91.54%，层桶占 1.78%，语料内层桶跨度 5.55）→ **上界 0.513 比特/参数**，而该族专家桶实际跨度是 1.912；GLM-4.7-Flash（92.79%/5.08%/0.32）→ 上界 0.025、实际 1.552；Qwen3.6-35B-A3B（92.99%/3.33%/3.33）→ 上界 0.251、实际 1.122；gemma-4-26B-A4B（90.51%/6.52%/2.44）→ 上界 0.256、实际 0.554。
- author: measurement
- from: result.strategies
- scope: general
- status: current
- kind: measured
- evidence: `alloc_map.json` 的桶参数占比与比特数；推导是恒等式（钉住：`Σ_c Δb_c p_c = 0`），不是拟合
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --bounds`
- 说明：这是本轴最重要的一条结构事实——**在 90%–93% 参数都是专家的架构上，「固定总比特、只改专家层比特」几乎不存在可行域**：专家桶最多挪 0.03–0.51 比特，而语料里实际看到的 0.55–1.90 比特跨度**全部**超出上界，所以它们必然同时改了总比特。`exq2`（2.918）与 `exq4`（4.483）专家桶差 1.875 > 上界 0.513，就是这件事的具体例证。

### inversion-contrast :: 语料里唯一一对「均匀 → 专家优先」是 `m55-Q3_K_M`（3.881，专家 3.792 / 层桶 3.977）对 `m55-exq4`（4.483，专家 4.500 / 层桶 2.952）：`Δbpw = +0.601`、`L1_pw = 0.696`，8 个有区间的格里 **6 个区间不含 0 且全为负**（HumanEval+ −0.201、MBPP+ −0.243、MMLU −0.160、GSM8K −0.220、IFEval −0.180、HumanEval −0.213、MBPP −0.270），而比特尺子对 `Δbpw = +0.601` 的预测是 **+0.107**（HumanEval+）——符号相反，残差 −0.31，远大于任何半宽。
- author: measurement
- from: result.strategies, result.budget-ruler
- scope: specific
- status: current
- kind: measured
- evidence: `alloc_pairs.py --pairs --family LFM2.5-8B`；斜率来自 `a03::slopes`
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --pairs --family LFM2.5-8B`
- 说明：这一对**不是**受控分配对照（`L1_pw = 0.696` 远超 `|Δbpw| = 0.601`，且总位宽也变了），所以它只能支持「往专家优先方向走 0.6 比特、同时把层桶砍 1 比特，分数会掉 0.16–0.27」这个**打包**结论；要把「掉分」归给分配本身，必须在总比特钉住下重做（`PLAN.md` 的 `WP4`）。

### inseparability :: 第三对（≤0.45 档）`UD-Q2_K_XL`（2.764）对 `exq2`（2.918）的 `L1_pw = 0.157` 与 `|Δbpw| = 0.154` **同量级**，因此这一对分不开「总比特」与「分配」：它的 7 个有区间的格里有 3 个不含 0（MBPP −0.103、MBPP+ −0.077、MMLU +0.114），方向还不一致（代码降、知识升）。
- author: measurement
- from: result.pivots
- scope: specific
- status: current
- kind: measured
- evidence: `alloc_pairs.py --pairs --family LFM2.5-8B`
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --pairs --family LFM2.5-8B`
- 说明：这一条是「本语料不能把所有配对都判成分配对照」的机械反例：`L1_pw ≈ |Δbpw|` 的对必须排除在分配判定之外（`AGENTS.md` 第 2 条）。

### own-arm :: 本层自建的第三臂是 `LFM2.5-8B-A1B-a04-uni45.gguf`：`llama-quantize --tensor-type 'token_embd=Q4_K' <BF16> <out> Q4_K_S`，dry-run 报 4565.94 MiB、实测 `quantize time = 206998.52 ms`；轮廓实测 attn 4.567 / embed 4.500 / 稠密 FFN 4.833 / 专家 4.515 / `other` 4.510，有效位宽 4.531，策略判为**均匀**（专家桶 4.515 vs 层桶 4.722，差 0.21 ≤ 0.5）。它与 `m55-exq4`（4.483 / 专家 4.500 / 层桶 2.952）构成 `Δbpw = −0.048`、`L1_pw = 0.176` 的**钉住对照**，而两者专家桶只差 0.015——分配差全在非专家桶上（embed 2.063、`other` 1.873、稠密 FFN 1.937、attn 1.536）。
- author: measurement
- from: result.expert-bound
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/fixtures/alloc_a04.json`（`build_fixture.py --write` 从 gguf 头生成，`--check` 通过）；构建耗时与 dry-run 尺寸在同一夹具的 `dry_run_mib` / `command` 字段
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/build_fixture.py" --check`；`python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --infeasible | grep a04-uni45`
- 说明：分数见 `third-arm-pinned`（六基准齐、`bad_rate` 0、同协议）。

### third-arm-pinned :: 钉住档（`Δbpw = −0.048`、`L1_pw = 0.176`）上，**均匀**（本层自建臂，4.531）对**专家优先**（`m55-exq4`，4.483）的逐基准差值是 HumanEval +0.4817 [+0.3838,+0.5654]、HumanEval+ +0.4695 [+0.3720,+0.5535]、MBPP +0.4339 [+0.3669,+0.4947]、MBPP+ +0.3439 [+0.2761,+0.4070]、MMLU +0.1952 [+0.1510,+0.2383]、GSM8K +0.2400 [+0.1081,+0.3606]（六列区间都不含 0），ARC-c +0.0900 [−0.0459,+0.2213] 与 IFEval +0.0900 [−0.0467,+0.2221] 跨 0，TruthfulQA −0.1153 不套区间；而比特预算对这些差的贡献按 `a03::slopes` 的同族固定效应斜率 **+0.1779 ± 0.0726（n=65 格，95% [0.036,+0.320]）** 折算只有 **+0.0017…+0.0155**。
- author: measurement
- from: result.own-arm
- scope: specific
- status: current
- kind: measured
- evidence: 自建臂的六列分数在 `experiments.sqlite`（`model='LFM2.5-8B-A1B-a04-uni45.gguf'`，协议 `evalplus-0.3.1-openai-chat-greedy-{base,plus}` 与 `lmeval-0.4.13-{gguf-shim,chat}-reasoning-off`，`n_items` 164/164/378/378/912/100/100/100/100）；落盘面板在 `.wrapup/mres/m164-a04-uni45/`（`lmeval_panel.json`、`evalplus.json`、`codegen/*/`），入库走 `migrate_db.py`（备份 `experiments.sqlite.bak19`），`checks/db_check.py` PASS
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --pairs --family LFM2.5-8B`（打印该对九列差值 + 非配对区间 + 比特预算项）；配对检验见 `paired-he-plus` / `paired-mbpp-plus`
- 三档归类：HumanEval / HumanEval+ / MBPP / MBPP+ / MMLU / GSM8K 六列**可分辨**（方向：均匀更高）；ARC-c 与 IFEval **不可分辨**（可见性下限 = 半宽 0.134，即这两个 100 题列只能探测 ≥0.13 的差）；TruthfulQA 属**通道不可用**（概率质量均值，`i01::res26`，不作判定）。无任何一格是「本次不可用」——该臂的两个面板都跑成、无 `errors`、`bad_rate` = 0。
- 说明：两侧同一套 base 权重（8,467,856,832 参数）、同一协议串、同 `n_items`、同 `ctx`/`np`/`temp`/`reasoning`，所以「同一总比特、比特放不同层」是唯一变化量；`Δbpw` 只值 HumanEval+ 0.0086，**预算解释不了 0.34–0.47 的差**。
- 说明：这条是本层唯一一个把「分配」从「预算」分离出来并测出可分辨差的对照，也是 `expert-first` 策略的判定依据——但它是 **n=1**，且对手是一条已知病态的臂：`exq4` 在 4.483 比特/权重上 HumanEval 只有 0.1402，**低于本族 2.764 比特那一档的 0.3110**，即它的分数不是「比特少」也不是「分配不同」能单独解释的低，所以正确的读法是「exq4 这条配方形状（专家 4.5 + 非专家压到 ~2.95）被否定」，不是「专家优先这一类策略被一般性否定」。
- 会推翻它：同两文件同配置重跑出现六列中任一列区间含 0（复现负控未测，见 `unmeasured-items`）。

### paired-he-plus :: 用两臂的**逐题**判定做配对检验：HumanEval+ 上 99/164 对 22/164，discordant **77 : 0**（A 只过 77、B 只过 0），McNemar 精确双侧 p = **1.32e-23**，差值 **+0.4695**，95% 区间 Wald 配对 **[+0.3931,+0.5459]**、条件精确 **[+0.4256,+0.4695]**（`c=0` 时条件精确的上端退化到点估计，这是它的正常行为）。
- author: measurement
- from: result.third-arm-pinned
- scope: specific
- status: current
- kind: measured
- evidence: 逐题产物入库为 `.wrapup/mres/a04-arm-uni45-humaneval-evalplus_eval.json`（sha256 `66bd15bd5bcd2217cee3962f860e8f587f6c8a71dda5f5b75f32e71dfc5df7bb`，源 `.wrapup/mres/m164-a04-uni45/codegen/humaneval/…_eval_results.json`）与 `.wrapup/mres/a04-arm-exq4-humaneval-evalplus_eval.json`（sha256 `0d8880262e960597a9177dc7559c0d445dcb2855bb0de5fa0d90493d6c1ddda9`，源 `.wrapup/mres/m109-lfm25-8b-a1b-m55-exq4/codegen/humaneval/…_eval_results.json`）；`.gitignore` 的 `!.wrapup/mres/*_eval.json` 让它们随仓库走
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/paired.py" --bench humaneval`
- 说明：配对检验比非配对区间强得多（同一道题上比较），所以「区间不含 0」在这里不是靠样本量硬撑；两臂的 `n_items` 都是 164 且题号集合完全相同（`paired.py` 会打印 `tasks_unmatched` 为空）。

### paired-mbpp-plus :: MBPP+ 上 220/378 对 90/378，discordant **136 : 6**，McNemar 精确双侧 p = **3.84e-33**，差值 **+0.3439**，95% 区间 Wald 配对 **[+0.2928,+0.3951]**、条件精确 **[+0.3083,+0.3639]**；base 判分（不带 plus）是 263/378 对 99/378、discordant 167 : 3、p = 1.09e-45。
- author: measurement
- from: result.third-arm-pinned
- scope: specific
- status: current
- kind: measured
- evidence: `.wrapup/mres/a04-arm-uni45-mbpp-evalplus_eval.json`（sha256 `10f13a11dec7114e552479868ab8160d6a154d8227e579c3c7a5bbd3f5f43088`）与 `.wrapup/mres/a04-arm-exq4-mbpp-evalplus_eval.json`（sha256 `4cebdd98db4c9893ec147fd51394834f69b864bd5ed3db0682a81d1974a13c34`）
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/paired.py" --bench mbpp`
- 说明：这一列不是「6 题翻转导致」——discordant 的不对称度 136:6 就是这个结论的全部内容；`i01::res31` 记的 MBPP+ 1/378 空体缺陷对差值的影响上限约 0.003，不影响判定。

### mixed-pair-uni45-q3km :: 同一族、同为**均匀**轮廓的另一对（本层自建臂 4.531 对 `m55-Q3_K_M` 3.881）在代码四列上可分辨：HumanEval +0.2683 [+0.1608,+0.3671]、HumanEval+ +0.2683 [+0.1610,+0.3669]、MBPP +0.1640 [+0.0948,+0.2310]、MBPP+ +0.1005 [+0.0294,+0.1702]；五列 lm-eval 全跨 0（MMLU +0.0351 [−0.0107,+0.0806]、ARC-c 0.0000、GSM8K +0.0200、IFEval −0.0900）。
- author: measurement
- from: result.three-arm-scores, result.own-arm
- scope: specific
- status: current
- kind: measured
- evidence: `experiments.sqlite` 的两行模型（协议同上）；轮廓见两份入库夹具
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --pairs --family LFM2.5-8B`
- retracted: 上一版把这一对叫「只差总比特」并据此算出本族代码列每比特斜率 ≈0.41，撤回——它的 `L1_pw = 0.777` **大于** `|Δbpw| = 0.650`，按本层自己的规则 2 它不是预算对，而是预算与分配同时变了的混合对；两点估计出来的斜率既无区间又是 13.5 倍外推（`Δbpw` 0.048 vs 0.650），不得使用。本族的预算项统一用 `a03::slopes` 的固定效应斜率 +0.1779 ± 0.0726（n=65）。
- 说明：这一对仍然有用，但只能当**混合对照**读：同为均匀轮廓、多 0.65 比特、代码四列更高而 lm-eval 五列测不出——它同时说明 lm-eval 那几列（mmlu 除外）在 100 题上探测不到这个量级的差。

### unpinnable-pairs :: 把「能不能被钉住」逐对算一遍：在 4 个有 ≥2 份文件的 MoE 族里，**可钉住 4 对、不可能钉住 18 对**（22 对总数的 82% 不可能）。不可能的那些正好是分数差最大的那些（`exq2`–`exq4` 专家桶差 1.875 对 0.513 的上界、`GLM` 三档 1.552 对 0.025 的上界）。
- author: measurement
- from: result.expert-bound
- scope: general
- status: current
- kind: measured
- evidence: 逐对冻结在 `analysis/fixtures/pin_feasibility.json`（22 对，每对带 `expert_span` / `expert_span_bound` / `verdict` / `l1_pw` / `dbpw` / 两侧策略）；它的两个输入（a03 的 `alloc_map.json` 与本层的 `alloc_a04.json`）都在仓库里，所以干净 clone 里 `--check` 同样成立，不需要 gguf、不读数据库、不占 GPU
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/build_pin_fixture.py" --check`（实跑输出：`[ok] 22 对一致（可等总比特 4 / 不可等 18），4 个有配对的 MoE 族`）；逐对清单见 `analysis/alloc_pairs.py --infeasible`
- 说明：上界的算法 `(1−s_exp)/s_exp × 层间摆动` 把**全部非专家参数**（含 embed 与 `other`）都算成可反向摆动的额度，而实测只观测到层桶摆动过 5.55 比特，所以这个上界是**宽松的**；即便如此仍有 18 对超界，结论因此不依赖上界的松紧。
- 说明：判据本身不是测量而是恒等式（钉住总比特 ⇒ `Σ_c Δb_c·p_c = 0`），所以这份夹具复核的是「数对不对、分族对不对」，不是「效应存不存在」。
- 说明：这是「现有语料能不能判分配」的机械回答——结论不是「效果不存在」，而是**85% 的同族文件对根本不能被摆到同总比特下**，能摆的只有 4 对，而那 3 对实测全部不可分辨（`pinned-null`）。

## 四、判定（`kind: analysis`）

### strategy-verdict :: 三个策略各自的判定（钉住档内）：**均匀 > 专家优先**——在 `Δbpw = −0.048` 的钉住对照上，均匀在六个可分辨列上全面更高（代码 +0.34…+0.48、MMLU +0.195、GSM8K +0.240），预算项按 `a03::slopes`（+0.1779 ± 0.0726，95% [0.036,+0.320]）只值 0.0017–0.0155；配对检验 HE+ 77:0、p=1.3e-23，MBPP+ 136:6、p=3.8e-33；**均匀 vs 非专家优先 不可分辨**——两对 `L1_pw = 0.381` 的对照 16 格全跨 0、可见性下限 0.135，所以在 3.8–3.9 比特这一带把非专家层从 4.0 抬到 8.5 测不出好处。**专家优先在本架构上不可推广**：`expert-bound` 给出它最多只能挪 0.03–0.51 比特，18/22 对根本不能被摆到同总比特，唯一可钉住的那一对（本条第一句）显著更差。
- author: agent
- from: result.third-arm-pinned, result.pinned-null, result.expert-bound
- scope: general
- status: current
- kind: analysis
- evidence: 三条 `kind: measured` 事实的机器读数
- repro: 见三条各自的复算命令
- 说明：这条是本层对 AC「≥3 种分配策略受控结论」的回答——三个策略都有钉住档内的对照，两个有方向（均匀 ≥ 专家优先、均匀 vs 非专家优先不可分辨），第三个方向的可行域由上界钉死。
- 说明（适用范围，别外推）：`均匀 > 专家优先` 这一条是 **n=1 对**，对手是 `exq4`——一条**已知病态**的臂（4.483 比特/权重上 HumanEval 0.1402，低于本族 2.764 比特档的 0.3110）。所以能被这条证据否定的说法是「把非专家层砍到 ~2.95 去喂专家仍然安全」，**不是**「专家优先这一类策略一般性地更差」；要后者需要在别的族或别的专家桶高度上重复。
- 会推翻它：另一族（GLM / gemma / Qwen3.6）出现同方向的钉住对照反例，或 `third-arm-pinned` 重跑不再显著。

### tier1a-verdict :: `plan6` 的 Tier-1A（专家级/逐张量 MoE 量化）判定：**类别级分配这一维已判完，Tier-1A 要买的东西在这一维上没有价值，它的价值只能在「专家桶内部」**。依据：`expert-bound` 证明在 91.5%–93% 专家占比下、固定总比特时专家桶只能挪 0.03–0.51 比特；`third-arm-pinned` 证明把非专家层压到 ~2.95 去喂专家（正是 exq4 这类「专家优先」配方的形状）在钉住总比特下可分辨地更差（代码 −0.34…−0.48）。剩下唯一没测的一维是**桶内结构**（哪几层 / 哪几个专家的比特不同），本语料 15 个 MoE 文件里没有任何一对构成那一维的对照，所以它本轮**未测**。资源结论（全部实测）：源必须是全精度权重——`LFM2.5-8B-A1B-BF16.gguf` = 16,947,260,768 字节（16.95 GB，`stat -Lc%s`），`plan6` 写的 ~70 GB 是 26B/35B 的量级、本层未验证；单臂构建 207.0 s（本臂）/ 63.8–145.5 s（`m55` 三臂）；单臂六基准面板 **2,692.3 s ≈ 44.9 分钟 GPU** = lm-eval **1,330.3 s**（mmlu 149.5 + arc 158.4 + tqa 181.7 + gsm8k 306.4 + ifeval 534.3，取 `lmeval_panel.json` 的 `timings_s` 合计）+ EvalPlus code **1,362 s**（humaneval 484 + mbpp 878，取 `evalplus.json` 的 `timings_s.total`）；即**一臂端到端 ≈3.5 分钟 CPU + 44.9 分钟 GPU**。
- author: agent
- from: result.expert-bound, result.third-arm-pinned, result.own-arm
- scope: general
- status: current
- kind: analysis
- evidence: 尺寸 `stat -Lc%s`；构建耗时 `llama-quantize` 自报（`quantize time = 206998.52 ms`）；面板耗时 = `lmeval_panel.json` 的 `timings_s` 合计 1,330.3 s + `evalplus.json` 的 `timings_s.total` 1,362 s
- repro: `stat -Lc%s /home/z/hf/LFM2.5-8B-A1B-BF16.gguf`；`python3 -c "import json;d=json.load(open('.wrapup/mres/m164-a04-uni45/lmeval_panel.json'));print(sum(d['timings_s'].values()))"`；`python3 -c "import json;print(json.load(open('.wrapup/mres/m164-a04-uni45/evalplus.json'))['timings_s'])"`
- 说明：可证伪形式——造出两臂「同一类别轮廓、不同的桶内结构、总比特钉住」，若六列出现可分辨差，则「Tier-1A 在类别级没价值、只在桶内」这一判定要被改写成「桶内也有价值」；成本已实测，所以这一步的报价是 **2 臂 × 44.9 ≈ 89.7 GPU 分钟（≈1.5 小时）+ 7 分钟 CPU**。（上一版写「两臂 ≈47 分钟」是把 code 段 1,362 s 误记成 519 s 得出的，低估约 1.9 倍；本版按产物合计。）

### harness-env :: 在本仓库当前路径下跑面板时，`gsm8k`/`ifeval` 与整个 EvalPlus code 阶段曾直接失败：五个 venv（`lmenv` / `evalpy` / `mplenv` / `msenv` / `bfclenv`）里**187 个** Python 入口脚本的第一行 shebang 写的是仓库搬家前的旧根 `/home/z/hf/research/.wrapup/<venv>/bin/python…`，那个路径已不存在，`subprocess` 报 `FileNotFoundError`、`timeout` 报 rc=127（实跑：`.wrapup/mres/m164-a04-uni45` 的第一次面板死于 `gsm8k`，第一次 code 面板死于 `evalplus.codegen`）。187 个入口点已全部改指当前根，另 24 个 `activate*` 脚本里的 `VIRTUAL_ENV=` 也一并改掉，现在 `*/bin/` 下 0 个旧根 shebang、0 个旧根引用（唯一残留是一个编译缓存 `__pycache__/jp.cpython-312.pyc` 里的字符串，无影响）。
- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `.wrapup/m164_lmeval.out` 的 `FileNotFoundError: … .wrapup/lmenv/bin/lm_eval`、`.wrapup/m164_code.out` 的 `codegen rc=127`；修复后 `.wrapup/m164_lmeval2.out` 与 `.wrapup/m164_code2.out` 正常
- repro: `for f in $(find .wrapup -maxdepth 3 -path "*/bin/*" -type f); do head -1 "$f" | grep -q '^#!.*python' && echo x; done | wc -l`（实跑 187）；`for f in $(find .wrapup -maxdepth 3 -path "*/bin/*" -type f); do head -1 "$f" | grep -q '^#!/home/z/hf/research/' && echo x; done | wc -l`（实跑 0）
- 说明：计数口径写在这里，因为「修了几个」只有在口径下才是一个事实——**入口点 = `*/bin/` 下第一行是 `#!…python` 的普通文件**；按这个口径是 187（上一版写 185，是两次 sweep 用了不同 glob 漏掉 2 个）。`.wrapup/` 被 `.gitignore` 排除，所以**干净 clone 里这一条会重现**，需要重装 venv 或同样修 shebang。

### unmeasured-items :: `experiments.sqlite` 只存聚合分（`i01::res26`：lm-eval 未开 `--log_samples`），所以表驱动的区间都是**非配对**的（两比例差的 Newcombe method 10），跨 0 只能写「不可分辨」并附半宽；**例外**是 EvalPlus 的两个代码基准：两臂的逐题判定已在盘上，已作为 `_eval.json` 入库，配对检验见 `paired-he-plus` / `paired-mbpp-plus`（lm-eval 那五列仍然只有聚合分，不能配对）。同一格在相同协议下重跑是否复现入库值**未测**（复现负控未跑）。
- author: agent
- scope: general
- status: current
- kind: analysis
- evidence: `experiments.sqlite` 每个 (文件, 基准) 的规范协议格只有一次运行；`.wrapup/mres/*/samples_*.jsonl` 不存在
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py" --scores LFM2.5-8B-A1B`（每个格只有一行）

### noise-bound :: 本层的比较全部在 greedy / temp 0 下进行，`i01::res32` 实测该条件的逐题重复地板是 0 题，所以本层的分数差不是采样噪声；但那条地板的前提是「同一提示集 + 同一后处理版本」，任一改变就先按 `i01::res29` 的 ±16/161 判输入差。**temp > 0 的比较在本层一律不作分配判定**（`i01::res32`：temp 0.3 下逐题 Jaccard 0.53–0.67 而分数只摆 6/164）。
- author: agent
- from: result.unmeasured-items
- scope: general
- status: current
- kind: analysis
- evidence: `docs/subprojects/i01-判分与基准有效性/RESULT.md::res32` 与 `::res29`
- repro: `python3 "docs/subprojects/i01-判分与基准有效性/audits/noise_floor_compare.py"`（引用，不是本层的测量）

### channels-cited :: 本层引用六列时的通道状态：HumanEval+/MBPP+ 不后处理且 MBPP+ 有 1/378 个任务能被空体拿满（`i01::res31`）；GSM8K 取最后一个数字（`flexible-extract`）；IFEval 有约 9 分地板；MMLU/ARC 的似然打平静默取下标 0；TruthfulQA 的 `acc` 是概率质量均值（`i01::res26`）——本层因此不把 TruthfulQA 放进策略判定。
- author: agent
- scope: general
- status: current
- kind: analysis
- evidence: `docs/subprojects/i01-判分与基准有效性/RESULT.md` 的 `res26`–`res31`
- repro: 无（这是引用，不是本层的测量）
