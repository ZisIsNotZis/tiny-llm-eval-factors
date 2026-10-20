# a01 量化位宽 — 结果

每条事实一行一个陈述；有数字就必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
测量（`kind: measured`）与分析（`kind: analysis`）分开写，analysis 不覆盖任何数字。

## 证据绑定（读这一层之前先看这里）

本层的全部数字在 `experiments.sqlite` 的 sha256 = `8ddc213cd1863149b1ba550e9deba6fc150e1ca986bc084e69e93d0b62433421` 这个工作树状态上算出（同期 `HEAD` 里的库是 `cc1ae790aefeb20b8ed096f3884e5d553f5ebd62f693909abfbdf82792b22c2e`——两个不一致是因为别的子项目正在改库，本层是只读方）。
`experiments.sqlite` 由多个子项目并发写入，所以**任何一条事实是否仍然成立，用 `python3 "docs/subprojects/a01-量化位宽/analysis/run_all.py"` 判定**：38 条预期全成立时上面的事实全部复核通过；某条不成立时先看 `n_items` 有没有变（`n_items` 变了区间就会变），再判是不是真的变了。

复算装置：`analysis/curves.py`（曲线 + 拐点 + 区间）与 `analysis/run_all.py`（全部检查，退出码即结论）。本层只读 `experiments.sqlite`，不写库、不改 `report.html`。

## 一、已成立（本层亲自跑过命令）

### qw2b-panel :: Qwen3.5-2B 的七个量化文件在库里构成一条同协议同配置、七个标准基准齐全的阶梯，是全库唯一能把「有效位宽 → 分数」当受控序列读的家族。
- author: measurement
- scope: specific
- status: current
- evidence: `experiments.sqlite` 的 `run_tag in (m61…m67) × 七个标准基准` 行；面板级元数据在 `.wrapup/mres/m6{1..7}-*/evalplus.json` 的 `protocol` 字段（`temperature 0.0, greedy true, ctx 8192, np 1, reasoning off`）
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --panel qwen3.5-2b`
- 说明：七个面板的协议串、`ctx_size = 8192`、`parallel_slots = 1`、`temp = 0.0`、`reasoning = off` 全部一致；`n_items` 分别是 164 / 378 / 912 / 100 / 100 / 100 / 100（HumanEval+ / MBPP+ / MMLU / ARC-c / TruthfulQA / GSM8K / IFEval），即除 MMLU 外都是 limit 100 的子集。

| 量化文件 | 有效位宽 | 代码 HumanEval+ | 代码 MBPP+ | 知识 MMLU | 科学 ARC-c | 真实 TruthfulQA | 推理 GSM8K | 指令 IFEval |
|---|---|---|---|---|---|---|---|---|
| UD-IQ2_XXS | 3.266 | 0.0366 | 0.0503 | 0.3596 | 0.3400 | 0.4742 | 0.0600 | 0.1400 |
| UD-IQ2_M | 3.655 | 0.2378 | 0.2407 | 0.5022 | 0.4400 | 0.4319 | 0.3800 | 0.3300 |
| UD-IQ3_XXS | 3.961 | 0.3720 | 0.2857 | 0.5603 | 0.4400 | 0.4351 | 0.5200 | 0.5000 |
| UD-Q2_K_XL | 4.109 | 0.2378 | 0.2725 | 0.5504 | 0.4300 | 0.4261 | 0.4400 | 0.4000 |
| UD-Q3_K_XL | 4.928 | 0.5244 | 0.4444 | 0.6173 | 0.4100 | 0.4350 | 0.6500 | 0.5500 |
| UD-Q4_K_XL | 5.696 | 0.5061 | 0.4206 | 0.6228 | 0.4300 | 0.4240 | 0.6600 | 0.5500 |
| UD-Q5_K_XL | 6.235 | 0.5061 | 0.4180 | 0.6239 | 0.4200 | 0.4232 | 0.7300 | 0.6200 |

### qw2b-inversion :: 在这条阶梯上，4.109 比特/权重的 UD-Q2_K_XL 在三个基准上明显低于 3.961 的 UD-IQ3_XXS（HumanEval+ −13.4 pp = 22 题、IFEval −10.0 pp = 10 题、GSM8K −8.0 pp = 8 题），在另外四个基准上两者差 ≤1.3 pp（MBPP+ −1.3 pp = 5 题、MMLU −1.0 pp、ARC-c −1.0 pp、TruthfulQA −0.9 pp）。
- author: measurement
- from: result.qw2b-panel
- scope: specific
- status: current
- evidence: 上表；逐题数由 `n_items × 差值` 换算，落盘完成物在 `.wrapup/mres/m64-qwen-2b-q2kxl/` 与 `m63-qwen-2b-iq3xxs/`
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --pair qwen3.5-2b/IQ3_XXS/Q2_K_XL`
- 说明：这是「异常」的实际形状——不是整条曲线下移，而是**分基准分化**。哪几个差超出二项区间由 `WP3::T1` 判定，本条只报实测值与题数。

### mmlu-does-move :: MMLU 在同一家族的位宽阶梯上并不「几乎不动」：Qwen3.5-2B 从 3.266 到 6.235 比特/权重的全区间是 0.3596 → 0.6239，跨 3.96→4.93 这一档是 0.5603 → 0.6173。
- author: measurement
- from: result.qw2b-panel
- scope: specific
- status: current
- evidence: `qw2b-panel` 表
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --panel qwen3.5-2b --bench mmlu`
- 说明：这条直接收窄 `an2`（「知识类基准几乎不动」）的适用范围——「几乎不动」只在 ≥4 比特/权重 的区间成立（4.109→6.235：0.5504→0.6239）。

### tqa-flat :: TruthfulQA 沿整条位宽阶梯不升反微降（0.4742 @3.266 → 0.4232 @6.235，跨 7 个点、100 题），与 `i01::res26` 的实测地板（各选项等概率时 `acc` 均值 0.4484）同量级，所以这一列不能用来判「量化伤害」。
- author: measurement
- from: result.qw2b-panel
- scope: specific
- status: current
- evidence: `qw2b-panel` 表；地板值见 `docs/subprojects/i01-判分与基准有效性/RESULT.md::res26`
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --panel qwen3.5-2b --bench truthfulqa_mc2`

### heplus-drop-not-plus-only :: HumanEval+ 的差不是「plus 附加测试」这一个通道造成的：UD-IQ3_XXS 的 base 0.3902 / plus 0.3720，UD-Q2_K_XL 的 base 0.2561 / plus 0.2378——base 判分上两者的差（−13.4 pp）与 plus 上一样大。
- author: measurement
- from: result.qw2b-inversion
- scope: specific
- status: current
- evidence: `.wrapup/mres/m63-qwen-2b-iq3xxs/evalplus.json` 与 `.wrapup/mres/m64-qwen-2b-q2kxl/evalplus.json` 的 `benches.humaneval.{base,plus,n}`；`bad_rate` 两者都是 0.0
- repro: `jq -c '.benches.humaneval|{base,plus,n,bad_rate}' .wrapup/mres/m63-qwen-2b-iq3xxs/evalplus.json .wrapup/mres/m64-qwen-2b-q2kxl/evalplus.json`

### mbpp-base-reverses :: 同一个文件对在 MBPP 上方向相反：base 判分 UD-Q2_K_XL 0.3598 高于 UD-IQ3_XXS 0.3333，而 plus 判分 0.2725 低于 0.2857——两个代码基准对同一对文件的结论不一致。
- author: measurement
- from: result.qw2b-inversion
- scope: specific
- status: current
- evidence: 同上两份 `evalplus.json` 的 `benches.mbpp`
- repro: `jq -c '.benches.mbpp|{base,plus,n,bad_rate}' .wrapup/mres/m63-qwen-2b-iq3xxs/evalplus.json .wrapup/mres/m64-qwen-2b-q2kxl/evalplus.json`
- 说明：这条是 `WP3::E3`（单文件对、不可外推）的现有证据之一，也是 `WP3::T2` 要追的通道（base 与 plus 在 5 题上翻转）。

### gemma12b-mmlu-jump :: gemma-4-12B 的 MMLU 在原生 UD-Q4_K_XL 上是 0.6436，而 UD-Q3_K_XL 是 0.4178、QAT 的 UD-Q4_K_XL 是 0.4463（+22.6 pp），同期其余基准几乎不动：HumanEval+ 0.9146→0.9146、MBPP+ 0.7302→0.7407、GSM8K 0.93→0.93、IFEval 0.87→0.90、TruthfulQA 0.4986→0.5039。
- author: measurement
- scope: specific
- status: current
- evidence: `experiments.sqlite` 的 `run_tag in (m105-gemma-12b-q3kxl, m141-native-gemma12b-q4, m140-qat-gemma12b-q4)` 行
- repro: `sqlite3 -header -column experiments.sqlite "SELECT run_tag,_bench,_score,n_items FROM experiments WHERE run_tag IN ('m105-gemma-12b-q3kxl','m141-native-gemma12b-q4','m140-qat-gemma12b-q4') AND _bench IN ('mmlu','humaneval-plus','mbpp-plus','gsm8k','ifeval','truthfulqa_mc2') ORDER BY run_tag,_bench"`
- 说明：这是 `plan7b` 的当前值。MMLU 走 `lmeval-0.4.13-gguf-shim-reasoning-off`（似然打分、912 题），其余六列走 chat 生成；「一个基准跳 22.6 pp、六个不动」本身就指向通道或模板差，`WP5` 要判的就是这个。

## 二、B1 反例的裁决材料（plan2 的 E1/E2/E3）

### b1-heplus-only :: 3.961（UD-IQ3_XXS）与 4.109（UD-Q2_K_XL）的逐基准两比例差里，只有 HumanEval+ 的 95% 区间不含 0（+0.1341，[+0.0345, +0.2303]，22 题）；GSM8K +0.0800 [−0.0576, +0.2134]（8 题）、IFEval +0.1000 [−0.0373, +0.2321]（10 题）、MBPP+ +0.0132 [−0.0506, +0.0769]（5 题）、MMLU +0.0099 [−0.0357, +0.0554]（9 题）、ARC-c +0.0100 [−0.1252, +0.1447]（1 题）全部跨 0。
- author: measurement
- from: result.qw2b-inversion
- scope: specific
- status: current
- kind: measured
- evidence: 该对文件在每个基准上的 `_score, n_items, run_tag`（`m63-qwen-2b-iq3xxs` 与 `m64-qwen-2b-q2kxl`）
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --pair qwen3.5-2b/IQ3_XXS/Q2_K_XL`
- 说明：这是 plan2 的 E1 裁决。报告第一节原来把「HumanEval+ 0.372→0.238、GSM8K 0.52→0.44、MultiPL-E 0.189→0.092」并列成同一个掉点，但只有 HumanEval+ 这一列在二项区间下分得开；另两列是「测不出」而不是「测出为负」。TruthfulQA 那一列不套区间：`acc` 是概率质量均值（`i01::res26`），不是逐题通过数。
- 会推翻它：同一对文件在同样协议下重跑出现与上表不同的题数（T4 的复现负控），或把 n 提到能分开这 8/10 题的量级（GSM8K/IFEval 各 100 题，要分开 8 个百分点大约需要每列 500+ 题）。

### q2kxl-iq3-4b :: 同门的 Qwen3.5-4B 在几乎同字节的一对文件上（UD-IQ3_XXS 3.707 vs UD-Q2_K_XL 3.692，Δbpw = +0.016）方向与 2B 一致——IQ3_XXS 每一列都不低于 Q2_K_XL——但只有 MMLU 分得开（+0.0592，[+0.0170, +0.1011]，54 题）；HumanEval+ +0.0061 [−0.0936, +0.1057]、MBPP+ +0.0106 [−0.0596, +0.0807]、ARC-c +0.0500 [−0.0871, +0.1845]、IFEval +0.0900 [−0.0338, +0.2102] 都跨 0，TruthfulQA −0.0034（非伯努利）。
- author: measurement
- from: result.b1-heplus-only
- scope: specific
- status: current
- kind: measured
- evidence: `m*-qwen-4b-*` 面板行；两个文件的有效位宽在 `.wrapup/bpw_map.json`
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --pair qwen3.5-4B/IQ3_XXS/Q2_K_XL`
- 说明：这是 E3 的裁决材料。报告原来用 4B 这一对当「反向是模型相关、不是普遍规律」的对照，实测并不支持那个措辞：4B 上方向相同（IQ3_XXS ≥ Q2_K_XL），只是 HumanEval+ 的差从 13.4 pp 缩到 0.6 pp，而 MMLU 的差反而显著。也就是说「同字节下 IQ3_XXS 不差于 Q2_K_XL」在两代上一致，**2B 那个 13.4 pp 是幅度上的离群值**。
- 会推翻它：找到一对同字节文件使 Q2_K_XL 明显高于 IQ3_XXS（方向反转）；或 4B 的 MMLU 差在复测中消失。

### t2-channel-excluded :: 已测的 EvalPlus 判分通道不能解释 HumanEval+ 的那 22 题：两格的原始完成物几乎全部带围栏（164/164 与 164/164），sanitize 后残留围栏 3 vs 1、语法错 3 vs 1、无 `def`/`class` 6 vs 2——**分数更低的那一格（Q2_K_XL）sanitize 后反而更干净**；逐题状态只有 pass/fail，两格都没有一次 timeout。
- author: measurement
- from: result.b1-heplus-only
- scope: specific
- status: current
- kind: measured
- evidence: `.wrapup/mres/{m63-qwen-2b-iq3xxs,m64-qwen-2b-q2kxl}/codegen/humaneval/*.raw.jsonl`、`*.jsonl`、`*_eval_results.json`
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/channel_audit.py"`
- 会推翻它：出现一格大比例的 timeout、或 sanitize 把某一格的完成物系统性判坏（例如残留围栏数远大于分差题数），或 raw（未 sanitize）路径下的分数排序与入库值不同。

### knee-estimable :: 21 条「家族 × 供应商方案大类」series 里只有 Qwen3.5-2B（7 个位宽点）能估出拐点：HumanEval+ 4.928 [3.655, 4.928]、MBPP+ 3.655 [3.655, 4.928]、MMLU 3.961 [3.655, 4.109]、ARC-c 3.655 [3.655, 5.696]、GSM8K 3.961 [3.655, 4.928]、IFEval 3.961 [3.655, 4.928]（比特/权重）；TruthfulQA 不可估（非伯努利列）；其余 20 条 series 只有 2–3 个位宽点，拐点不可估。
- author: measurement
- from: result.qw2b-panel
- scope: general
- status: current
- kind: measured
- evidence: `analysis/curves.py` 的 `--all` 输出；series 按 `mktables.scheme_class` 切开，同一条曲线绝不混 UD 动态与原生 K
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --all`
- 说明：轴 AC 的第一条因此只能部分满足——「每家族一条曲线 + 拐点 + 区间」对 Qwen3.5-2B 成立，对其余 series 的正确结论是「不可估，缺 ≥4 个位宽点」。拐点分辨率等于阶梯间距，所以区间宽度普遍只有一两档。
- 会推翻它：给某家族补到 ≥4 个位宽点后拐点落在这个区间之外。

### adjacent-majority :: 相邻位宽档对的分数变化在多数情况下为正，但每一列都有反例：HumanEval+ 22 升 / 9 降 / 2 平、MBPP+ 24/7/1、MMLU 29/4/0、ARC-c 17/8/5、GSM8K 24/5/1、IFEval 26/5/2（共 33 对相邻档）；每 +1 比特/权重的分数变化中位数为 HumanEval+ 0.0987、GSM8K 0.0775、IFEval 0.0749、MBPP+ 0.0543、MMLU 0.0499、ARC-c 0.0273（TruthfulQA 0.0072，非伯努利仅供参考）。
- author: measurement
- from: result.res1
- scope: general
- status: current
- kind: measured
- evidence: `analysis/curves.py --adjacent`（同一条 series 内相邻位宽点，series = 家族 × 供应方案大类）
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --adjacent`
- 会推翻它：用同一口径重算得到相反的多数方向，或某列的反例多到超过升的数目。


## 三、极低位宽与三元（plan2 的另一半，WP4）

### ternary-offcurve :: 家族内可判的那一例是 GLM-4.7-Flash：UD-TQ1_0（2.226 比特/权重）的 HumanEval+ 0.4634、GSM8K 0.49，而同家族 UD-Q2_K_XL（3.176）是 0.7622 / 0.82、UD-Q3_K_XL（3.682）是 0.7500 / 0.84——低比特档比 3.176 档低 29.9 pp（HumanEval+）与 33.0 pp（GSM8K），而 3.176→3.682 这一档只动 −1.2 pp / +2.0 pp。
- author: measurement
- from: result.qw2b-panel
- scope: specific
- status: current
- kind: measured
- evidence: `m88-glm47flash-tq1` 与 `m*-glm47flash-*` 面板行；有效位宽在 `.wrapup/bpw_map.json`
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --panel "GLM-4.7-Flash"`
- 说明：这是「极低位宽离轨」在本库里唯一能**在家族内**判的一例（同 base 权重、同协议）。它落在家族线上方还是下方要看定义：按「3.176→3.682 已走平」外推，2.226 应该还在 0.75 附近，实测 0.4634，即**远低于外推线**。
- 会推翻它：同族补一个 2.2–2.6 比特的非三元文件后差值消失（那说明是比特数而不是三元方案造成的）。

### lowbit-spread :: 在 2.23–2.28 这个窄比特带里，4 个有 HumanEval+ 的文件从 0.4817（Ternary-Bonsai-1.7B-Q2_0_g64）到 0.8902（Ternary-Bonsai-27B-Q2_g64），跨度 40.9 pp——同一比特预算下分数由 base 模型决定，不由比特数决定。
- author: measurement
- from: result.ternary-offcurve
- scope: general
- status: current
- kind: measured
- evidence: `.wrapup/bpw_map.json` 的位宽 + `humaneval-plus` 行
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/run_all.py"`（`lowbit-spread` 那两条）
- 说明：`Bonsai-27B-Q1_0`（1.131 比特）的 HumanEval+ 是 0.8293，比库里任何 3.0–4.0 比特档都高（该区间最高是 gemma-4-26B-A4B 的 0.9390，但那是 26B MoE），这类文件是**按三元原生训练**的，不是从高位宽压下来的，所以它们不能放进「更多比特→更高分」的曲线里；B1 对它们的前提（同一家族的位宽阶梯）不成立，正确结论是**不可判**而不是「离轨」。
- 会推翻它：找到同 base、同训练精度、只有比特分配不同的三元文件对，使比特数与分数同向。

### m55-exq-inversion :: 同一 base 权重、同协议下，LFM2.5-8B-A1B 的 m55-exq4（4.483 比特/权重）在 HumanEval+ 0.1341、MBPP+ 0.2381、MMLU 0.2873、GSM8K 0.53 上全面低于 m55-exq2（2.918）的 0.2866 / 0.3280 / 0.4265 / 0.78，四列的 95% 区间都不含 0——**多 1.56 比特反而低**，幅度比 Qwen3.5-2B 那对更大。
- author: measurement
- from: result.b1-heplus-only
- scope: specific
- status: current
- kind: measured
- evidence: `m92-lfm25-8b-a1b-m55-exq2`、`m133-m55-exq2` 与 m55 的 exq4 面板行；两文件同一 base 权重（`m55` 是本地自建的逐层比特分配配方）
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --pair "LFM2.5-8B"/exq2/exq4`
- 说明：这条把「有效位宽不是质量的充分统计量」从「一个 2B 模型的怪现象」升级为**同一 base 权重上的可重复现象**，而且它不依赖厂商方案的故事——变的是比特**放在哪些层**（a04 的轴）。
- 会推翻它：复测 exq2/exq4 两格得到相反方向，或发现两文件不是同一 base 权重。

## 四、12B 原生档 MMLU（plan7b，WP5 的 CPU 部分）

### gemma12b-mmlu-uniform :: gemma-4-12B 的 MMLU 从 UD-Q3_K_XL（4.046）到原生 UD-Q4_K_XL（4.949）跳 +22.59 pp（0.4178 → 0.6436，912 题），而同期 HumanEval+ 动 0.0000、MBPP+ +0.0106、IFEval +0.0300；这个跳在 61 个科目上是均匀的——51 个科目上升、中位科目差 +0.250、没有全对或全错的科目。
- author: measurement
- from: result.gemma12b-mmlu-jump
- scope: specific
- status: current
- kind: measured
- evidence: `.wrapup/mres/m105-gemma-12b-q3kxl/lmeval_mmlu_*.json` 与 `.wrapup/mres/m141-native-gemma12b-q4/lmeval_mmlu_*.json` 的逐科目 `acc`；两次运行的 `cmd.txt` 逐字相同（同一个 shim、`--tasks mmlu --limit 100`、`max_length=8192`）
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/mmlu_subjects.py"`
- 说明：均匀平移说明不是少数科目坏了，而是整体判分条件变了；且库里这个文件只有**一次**测量，没有重复可比。剩下的两个候选是「原生 Q4 档这个文件真的更好」与「MMLU 这一列的判分条件在两个文件上不同（模板/分词/似然归一）」——后者需要一次同 shim 的复测或一次生成式 MMLU 对照才能判，见 `PLAN.md` 的 GPU 队列。
- 会推翻它：同 shim 复测得到与 0.6436 差 0.05 以上的值。

## 五、migrated 与撤回

### res1 :: 权重量化位宽：同一模型家族内，从较低比特档到下一档，多数情况下分数上升，但每一列都有反例——33 对相邻档里 HumanEval+ 有 9 对、MBPP+ 7 对、MMLU 4 对、ARC-c 8 对、GSM8K 5 对、IFEval 5 对是下降，「普遍上升」的原措辞已按 `adjacent-majority` 收窄。
- author: measurement
- from: result.adjacent-majority
- scope: general
- status: current
- kind: measured
- evidence: `analysis/curves.py --adjacent`
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --adjacent`
- retracted: 原措辞「7 个标准基准上的分数普遍上升」撤回——反例逐列存在，且其中最受关注的一例就是 `qw2b-inversion`。

### res2 :: 已撤回：按基准汇总的位宽步长中位数在原稿里没有记录计算口径（哪些家族、哪些档对、如何聚合都没写），用本层的同一口径重算得到的是另一组数（见 `adjacent-majority`），所以旧值不可复核，不再保留为当前事实。
- author: measurement
- scope: general
- status: retracted
- kind: measured
- evidence: 无（原 origin `.scratch/originals/L2-结果.md` 已退役，且口径未记录）
- repro: 无——已由 `adjacent-majority` 取代

### res3 :: 已撤回：每比特分数变化中位数的旧值同样无可复核的命令，且排序与本层重算不一致（旧值把 IFEval 排在 HumanEval+ 之前，重算为 HumanEval+ 0.0987 > GSM8K 0.0775 > IFEval 0.0749），旧值不再保留为当前事实。
- author: measurement
- scope: general
- status: retracted
- kind: measured
- evidence: 无（口径未记录）
- repro: 无——已由 `adjacent-majority` 取代

### res4 :: 已撤回：「能力型 − 知识型 = +0.12 / 比特，95% CI [+0.04, +0.20]」这一条的区间类型与聚类单位在原稿里没有记录，无法重算，因此这不是一个可以复核的测量结论；它想表达的方向（代码/推理/指令比知识/事实性更吃位宽）在 `adjacent-majority` 里能直接读出，但那里也没有给出该复合量的区间。
- author: measurement
- scope: general
- status: retracted
- kind: measured
- evidence: 无（区间算法未记录）
- repro: 无——方向改由 `adjacent-majority` 与 `an2` 承载

### res5 :: Qwen3.5-2B 的多语言代码必须按语言分开读：同一对文件上 3.961→4.109 在 cpp 是 0.1801→0.1118、在 py 是 0.1988→0.1366（协议 `multipl-e-raw-greedy-768`，来自不同面板 m23/m50 与 m3，不是受控比较）。
- author: measurement
- scope: specific
- status: current
- kind: measured
- evidence: `experiments.sqlite` 的 `model LIKE 'Qwen3.5-2B%' AND protocol='multipl-e-raw-greedy-768'` 行
- repro: `sqlite3 -header -column experiments.sqlite "SELECT model,language,_score,run_tag FROM experiments WHERE model LIKE 'Qwen3.5-2B%' AND protocol='multipl-e-raw-greedy-768' ORDER BY model,language"`
- retracted: 原 res5 的跨语言池化列（…4.11→0.0920…）已撤回：一是把不同语言集平均成一个数（`i01::res16` 已判不可比），二是 0.0920 用库内该模型 multi-e 行的等权平均复算不出来（cpp+js+py = 0.1201、cpp+js+py+rb+rs = 0.0862）。

## 六、分析（`kind: analysis`，不覆盖任何数字）

### an1 :: 量化位宽该选多大，取决于该家族自己的曲线拐点；但按当前数据只有 Qwen3.5-2B 能估出拐点（3.66–4.93 比特/权重，按基准不同），其余 20 条 series 只有 2–3 个位宽点、拐点不可估，所以「多数家族的主要抬升出现在 4–5 比特/权重」这句话目前没有逐家族的拐点估计支撑，它只来自把各家族的位宽点放在一起看的整体印象。
- author: agent
- from: result.knee-estimable, result.qw2b-panel
- scope: general
- status: provisional
- kind: analysis
- evidence: `analysis/curves.py --all`
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --all`
- 会推翻它：补点后某家族的拐点落在 4–5 比特之外；或改一种拐点定义（最大曲率 / 分段线性断点）把 2B 的 3.66–4.93 移出这个范围。

### an2 :: 判断量化够不够，看代码 / 推理 / 指令，不要看知识类基准：每 +1 比特/权重 的分数变化中位数在 HumanEval+/GSM8K/IFEval 是 0.099/0.078/0.075，在 MMLU/ARC-c 是 0.050/0.027；TruthfulQA 全列不动（0.007）且它的 `acc` 有 0.4484 的地板，这一列不能用来判断。
- author: agent
- from: result.adjacent-majority
- scope: general
- status: provisional
- kind: analysis
- evidence: `analysis/curves.py --adjacent`；地板值见 `i01::res26`
- repro: `python3 "docs/subprojects/a01-量化位宽/analysis/curves.py" --adjacent`
- 说明：原措辞「MMLU 几乎不动」撤回——`mmlu-does-move` 实测 MMLU 在全区间是 0.3596→0.6239；准确的说法是 MMLU 的敏感度约为代码/推理的一半，不是零。
