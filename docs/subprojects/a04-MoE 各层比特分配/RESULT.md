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

## 三、判定（`kind: analysis`，由 `WP3`/`WP5` 写）

### strategy-verdict :: 待 `WP3` 写：三种策略（均匀 / 非专家优先 / 专家优先）在钉住总比特的对照下各自的判定与区间。

- author: agent
- from: result.pivots
- scope: general
- status: provisional
- kind: analysis
- evidence: `WP3` 未完成，本条是占位还是事实以 `PLAN.md` 的工作包状态为准——**本条不是结论**，`run_all.py` 不把它当断言。
- repro: 无

### tier1a-verdict :: 待 `WP5` 写：`plan6` 的 Tier-1A（专家级/逐张量 MoE 量化，F16 源 ~70 GB）判定与资源结论。

- author: agent
- scope: general
- status: provisional
- kind: analysis
- evidence: `WP4`/`WP5` 未完成；`plan6` 的原文只说「需要 F16 源（~70 GB）」，那个数**未在本层验证**（`LFM2.5-8B-A1B-BF16.gguf` 实测 16.9 GB，见 `PLAN.md` 的 `WP4`），所以 70 GB 只能当作大模型的量级而不是实测值。
- repro: `stat -Lc%s /home/z/hf/LFM2.5-8B-A1B-BF16.gguf`

## 四、未测与限制（不是 0）

### unmeasured-pivot-extreme :: 语料里**没有**「总比特钉住 + 专家桶被压到 2.6 / 抬到 4.5」的对照，所以「专家层该压多低」这个 AC 的原问法在当前语料下**不可判**：`exq2` 与 `exq4` 与最近邻的 `Δbpw` 分别是 0.963/0.154 与 0.601/1.564，都不在钉住档内。要判它必须现造配方（`PLAN.md` 的 `WP4`，成本：`llama-quantize` 实测 63.8/106.3/145.5 s/份，六基准面板实测 27 分钟/份 = 五基准 11.8–13.4 分钟 + code 11.5–15.2 分钟，见 `.wrapup/m55_prebuild.log`、`.wrapup/m55_std.log`、`.wrapup/mres/m92-lfm25-8b-a1b-m55-exq2/.timings`）。
- author: agent
- scope: general
- status: current
- kind: analysis
- evidence: `profiles.py` 的三档清单里 `exq2`/`exq4` 只出现在 ≤0.45 档之外；`pivots` 的两对配置都不含极端专家桶
- repro: `python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py"`（三档清单里没有 `exq2`/`exq4` 参与的钉住对）
- 说明：这是本层最重要的一条「未测」——不是「没有效应」，是**没有对照**。

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
