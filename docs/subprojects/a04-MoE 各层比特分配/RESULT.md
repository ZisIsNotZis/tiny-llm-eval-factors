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

### moe-population :: a03 夹具的 51 个文件里有 **14 个是 MoE**（有 `ffn-expert` 桶），分属 5 族：LFM2.5-8B-A1B（5 个）、GLM-4.7-Flash（3）、Qwen3.6-35B-A3B（3）、gemma-4-26B-A4B（2）、Qwen3.5-35B-A3B（1）；专家桶占参数量 90.51%–92.99%，即这些模型的「比特放在哪」几乎完全由「专家层拿多少」与「非专家层拿多少」两个数决定。

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

### strategies :: 按 `AGENTS.md` 第 1 条的机械规则（专家桶 vs 层桶 = attn/稠密 FFN/共享专家的参数加权均值，带宽 0.5 比特/参数）把 14 个 MoE 文件分成 3 个策略：**非专家优先 12 个**、**均匀 1 个**（`m55-Q3_K_M`，专家 3.792 vs 层桶 3.977）、**专家优先 1 个**（`m55-exq4`，专家 4.500 vs 层桶 2.952）；`embed` 不参与方向判定（K-quant 模板把它钉在 4.5–8.5，是另一套机制），但一并打印。
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

### expert-bound :: 钉住总比特时专家桶能挪多少有一个由架构决定的上界 `(1−s_exp)/s_exp × 层桶跨度`：LFM2.5-8B-A1B（专家占 91.54%，层桶占 1.78%，语料内层桶跨度 5.55）→ **上界 0.513 比特/参数**，而该族专家桶实际跨度是 1.897；GLM-4.7-Flash（92.79%/5.08%/0.32）→ 上界 0.025、实际 1.552；Qwen3.6-35B-A3B（92.99%/3.33%/2.91）→ 上界 0.219、实际 0.930；gemma-4-26B-A4B（90.51%/6.52%/2.44）→ 上界 0.256、实际 0.554。
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

### own-arm :: 本层自建的第三臂是 `LFM2.5-8B-A1B-a04-uni45.gguf`：`llama-quantize --tensor-type 'token_embd=Q4_K' <BF16> <out> Q4_K_S`，dry-run 报 4565.94 MiB、实测落盘 4,573,810,000 字节、`quantize time = 206998.52 ms`；轮廓实测 attn 4.567 / embed 4.500 / 稠密 FFN 4.833 / 专家 4.515 / `other` 4.510，有效位宽 4.531，策略判为**均匀**（专家桶 4.515 vs 层桶 4.722，差 0.21 ≤ 0.5）。它与 `m55-exq4`（4.483 / 专家 4.500 / 层桶 2.952）构成 `Δbpw = +0.048`、`L1_pw = 0.176` 的**钉住对照**，而两者专家桶只差 0.015——分配差全在非专家桶上（embed 2.063、`other` 1.873、稠密 FFN 1.937、attn 1.536）。
- author: measurement
- from: result.expert-bound
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/fixtures/alloc_a04.json`（由 `build_fixture.py --write` 从 gguf 头生成，`--check` 漂移检查通过）；构建耗时与 dry-run 尺寸在同一夹具的 `dry_run_mib` / `command` 字段；落盘尺寸 `stat -Lc%s /home/z/hf/LFM2.5-8B-A1B-a04-uni45.gguf`
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/build_fixture.py" --check`；`python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --infeasible | grep a04-uni45`
- 说明：分数**未测**——它在 `WP4` 的 GPU 队列里（见 `PLAN.md` 的排队项），没跑之前不写任何分数。

### unpinnable-pairs :: 把「能不能被钉住」逐对算一遍：在 4 个有 ≥2 份文件的 MoE 族里，**可钉住 3 对、不可能钉住 17 对**（20 对总数的 85% 不可能）。不可能的那些正好是分数差最大的那些（`exq2`–`exq4` 专家桶差 1.875 对 0.513 的上界、`GLM` 三档 1.552 对 0.025 的上界）。
- author: measurement
- from: result.expert-bound
- scope: general
- status: current
- kind: measured
- evidence: 只读两份入库夹具（a03 的 `alloc_map.json` 与本层的 `alloc_a04.json`），不读仓库外文件，所以干净 clone 里同样成立
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --infeasible`
- 说明：这是「现有语料能不能判分配」的机械回答——结论不是「效果不存在」，而是**85% 的同族文件对根本不能被摆到同总比特下**，能摆的只有 3 对，而那 3 对实测全部不可分辨（`pinned-null`）。

## 四、判定（`kind: analysis`）

### strategy-verdict :: 三个策略各自能说到哪一步：**均匀 vs 非专家优先**在钉住档内有 2 对对照（`L1_pw` 均 0.381）→ 结论是**不可分辨**（16/16 格跨 0，最大半宽 0.135）；**均匀 vs 专家优先**在语料里只有一对非钉住的对照（`L1_pw` 0.696、`Δbpw` +0.601）→ 只能给出打包结论「掉 0.16–0.27」；**专家优先的钉住对照语料里不存在**，而 `expert-bound` 说明它在本架构上最多只能挪 0.5 比特，所以「专家层该压多低」的钉住版本必须现造一臂（`WP4`）。
- author: agent
- from: result.pinned-null, result.inversion-contrast, result.expert-bound
- scope: general
- status: provisional
- kind: analysis
- evidence: 三条 `kind: measured` 事实的机器读数
- repro: 见三条各自的复算命令
- 说明：`provisional` 的理由：第三种策略缺钉住对照，`WP4` 会用一臂把 4.5 比特的**均匀**控制补齐（`llama-quantize --dry-run` 实测 `Q4_K_S + token_embd=Q4_K = 4565.94 MiB` 对 `exq4 = 4517.03 MiB`，Δbpw ≈ 0.049，落在钉住档内），那时本条改为 `current`。
- 会推翻它：`WP4` 那一臂与 `exq4` 的钉住对照出现某一列区间不含 0 且有方向的差（那说明分配在钉住档内确实可测）。

### tier1a-verdict :: `plan6` 的 Tier-1A（专家级/逐张量 MoE 量化）判定：**有界**——它要买的不是「固定总比特下更好的类别级分配」（`expert-bound` 已证明那一维在本架构上几乎没有可行域），而是**类别桶内部**的结构（哪几层/哪几个专家的比特不同），这一维在本语料里**完全没有对照**（14 个 MoE 文件里没有一个的桶内结构与另一个同总比特文件构成对照），所以它值不值得做在本轮**未测**。资源结论：源必须是 F16/BF16 全权重（`LFM2.5-8B-A1B-BF16.gguf` 实测 16,947,260,768 字节 = 16.95 GB；`plan6` 写的 ~70 GB 是大模型（26B/35B）的量级，本层未验证那两类）；构建成本实测 `llama-quantize` 63.8–145.5 s/份；评估成本实测 27 分钟/份（五基准 11.8–13.4 分钟 + code 11.5–15.2 分钟），所以一臂端到端 ≈2.5 分钟 CPU + 27 分钟 GPU。
- author: agent
- from: result.expert-bound, result.pinned-null
- scope: general
- status: provisional
- kind: analysis
- evidence: 尺寸 `stat -Lc%s`；构建耗时 `.wrapup/m55_prebuild.log`；评估耗时 `.wrapup/m55_std.log` 与 `.wrapup/mres/m92-lfm25-8b-a1b-m55-exq2/.timings`
- repro: `stat -Lc%s /home/z/hf/LFM2.5-8B-A1B-BF16.gguf`；`grep 'quantize time' .wrapup/m55_prebuild.log`；`cat .wrapup/mres/m92-lfm25-8b-a1b-m55-exq2/.timings`
- 说明：判定的可证伪形式——若造出两臂「同一类别轮廓、不同的桶内结构、总比特钉住」，且某一列区间不含 0，则「Tier-1A 买不到可测的东西」被推翻。
- 会推翻它：同上两臂的钉住对照出现显著差。


## 四、未测与限制（不是 0）

### unmeasured-pivot-extreme :: 语料里**没有**「总比特钉住 + 专家桶被压到 2.6 / 抬到 4.5」的对照，所以「专家层该压多低」这个 AC 的原问法在当前语料下**不可判**：`exq2` 与 `exq4` 与最近邻的 `Δbpw` 分别是 0.963/0.154 与 0.601/1.564，都不在钉住档内。要判它必须现造配方（`PLAN.md` 的 `WP4`，成本：`llama-quantize` 实测 63.8/106.3/145.5 s/份，六基准面板实测 27 分钟/份 = 五基准 11.8–13.4 分钟 + code 11.5–15.2 分钟，见 `.wrapup/m55_prebuild.log`、`.wrapup/m55_std.log`、`.wrapup/mres/m92-lfm25-8b-a1b-m55-exq2/.timings`）。
- author: agent
- scope: general
- status: current
- kind: analysis
- evidence: `profiles.py` 的三档清单里 `exq2`/`exq4` 只出现在 ≤0.45 档之外；`pivots` 的两对配置都不含极端专家桶
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py"`（三档清单里没有 `exq2`/`exq4` 参与的钉住对）
- 说明：这是本层最重要的一条「未测」——不是「没有效应」，是**没有对照**。

### harness-env :: 在本仓库当前路径下跑面板时，`gsm8k`/`ifeval` 两个生成任务曾直接失败：venv 的入口脚本 shebang 写的是仓库搬家前的旧根 `/home/z/hf/research/.wrapup/lmenv/bin/python3.12`，那个路径已不存在，`subprocess` 报 `FileNotFoundError`（实跑：`.wrapup/mres/m164-a04-uni45` 的第一次面板在 mmlu 0.4825 / arc 0.4600 之后、truthfulqa 之后死于这一行）。两个入口脚本的 shebang 已改指当前根，`lm_eval --help` 正常；但 `.wrapup/lmenv/` 被 `.gitignore` 排除，所以**干净 clone 里这一条会重新出现**，需要重装 venv 或同样修 shebang。
- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `.wrapup/m164_lmeval.out` 的 `FileNotFoundError: … .wrapup/lmenv/bin/lm_eval`；修复后 `.wrapup/m164_lmeval2.out` 正常进入 mmlu
- repro: `grep -c FileNotFoundError .wrapup/m164_lmeval.out`；`head -1 .wrapup/lmenv/bin/lm_eval`
- 说明：这是测量基础设施的缺陷，归 `i02`；本层只记录它曾把一次面板弄死，并说明为何 `m164` 的面板重跑了一次。

### unmeasured-items :: 逐题结果不落库（`i01::res26`：lm-eval 未开 `--log_samples`），所以本层所有区间都是非配对的（两比例差的 Newcombe method 10），跨 0 只能写「不可分辨」并附半宽，不能写「相等」；同一格在相同协议下重跑是否复现入库值**未测**（复现负控未跑，GPU 排队）。
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
