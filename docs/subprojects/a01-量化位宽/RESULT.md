# a01 量化位宽 — 结果

每条事实一行一个陈述；有数字就必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
测量（`kind: measured`）与分析（`kind: analysis`）分开写，analysis 不覆盖任何数字。

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

## 二、migrated（从退役原稿搬来，暂无可重算命令）

> 这四条没有可重跑的复算命令：它们的 origin 是已退役的 `.scratch/originals/*`。`@falsifiable` 要求每个数字都有命令，所以在 `WP2` 用 `analysis/curves.py` 重算之前，它们只能标 `provisional`，不得被报告当作已复算的结论引用。

### res1 :: 权重量化位宽：同一模型家族内，从较低比特档到下一档（各家族实际跨度不同，典型约 0.8–1.7 比特/权重），7 个标准基准上的分数普遍上升。
- author: measurement
- scope: general
- status: provisional
- evidence: `report.html` 第一节表 A（由 `make_report.py` 从库生成）；原 origin `.scratch/originals/L2-结果.md` 已退役
- repro: 未就位——`WP2` 的 `analysis/curves.py --adjacent` 重算前无命令
- 说明：`qw2b-panel` 给出一个反例（3.961→4.109 有三列下降），所以「普遍上升」的措辞在 `WP2` 后必须收窄成「多数相邻档对上升，例外逐条列出」。

### res2 :: 按基准汇总的位宽步长中位数（越大 = 该基准对位宽越敏感）：GSM8K +0.460、HumanEval+ +0.409、IFEval +0.250、MBPP+ +0.235、MMLU +0.146、ARC-c +0.100、TruthfulQA +0.005。
- author: measurement
- from: result.res1
- scope: general
- status: provisional
- evidence: 原 origin 已退役，无可重算命令
- repro: 未就位——`WP2` 重算或撤回

### res3 :: 每个基准「每 +1 比特/权重 的分数变化」中位数：GSM8K +0.156、IFEval +0.117、HumanEval+ +0.104、MBPP+ +0.065、MMLU +0.054、ARC-c +0.026、TruthfulQA +0.014（约 11 倍跨度）。
- author: measurement
- from: result.res1
- scope: general
- status: provisional
- evidence: 原 origin 已退役，无可重算命令
- repro: 未就位——`WP2` 重算或撤回

### res4 :: 家族内配对差（能力型：代码+指令+推理）−（知识型：MMLU+ARC+TruthfulQA）= +0.12 / 比特，95% CI [+0.04, +0.20]，多数家族同向。
- author: measurement
- from: result.res2, result.res3
- scope: general
- status: provisional
- evidence: 原 origin 已退役；CI 的算法（区间类型、聚类单位）在原稿里没有写，所以即使重算出同一个数也不等于复现
- repro: 未就位——`WP2` 重算或撤回

### res5 :: Qwen3.5-2B 的多语言代码必须按语言分开读：同一对文件上 3.961→4.109 在 cpp 是 0.1801→0.1118、在 py 是 0.1988→0.1366（协议 `multipl-e-raw-greedy-768`，来自不同面板 m23/m50 与 m3，不是受控比较）。
- author: measurement
- scope: specific
- status: current
- evidence: `experiments.sqlite` 的 `model LIKE 'Qwen3.5-2B%' AND protocol='multipl-e-raw-greedy-768'` 行
- repro: `sqlite3 -header -column experiments.sqlite "SELECT model,language,_score,run_tag FROM experiments WHERE model LIKE 'Qwen3.5-2B%' AND protocol='multipl-e-raw-greedy-768' ORDER BY model,language"`
- retracted: 原 res5 的跨语言池化列（3.27→0.0062、3.66→0.1387、3.96→0.1894、4.11→0.0920、4.93→0.2184、5.70→0.2836、6.24→0.2774）已撤回：一是把不同语言集平均成一个数（`i01::res16` 已判不可比），二是 0.0920 用库内该模型 multi-e 行的等权平均复算不出来（cpp+js+py = 0.1201、cpp+js+py+rb+rs = 0.0862，两者都不是 0.0920），原值来源不明。

## 三、分析（`kind: analysis`，不覆盖任何数字）

### an1 :: 量化位宽该选多大，取决于该家族自己的曲线拐点：多数家族的主要抬升出现在有效位宽约 4–5 比特/权重之间，granite-4.1-3b 更早（3.22→0.048、4.06→0.391）；应选「分数曲线开始走平」的位宽，没有统一的某档结论。
- author: agent
- from: result.res1, result.res5
- scope: general
- status: provisional
- evidence: 原 origin 已退役；`qw2b-panel` 与之相容但只有一个家族
- repro: 未就位——`WP2` 的拐点估计（含「不可估」路径）建好后填入
- 说明：`qw2b-panel` 给这条加了一个反例方向——小模型的 GSM8K 到 6.235 比特仍在上升（0.44→0.73），所以「4–5 比特以上走平」至少对 2B 模型的推理基准不成立。

### an2 :: 判断量化够不够，看代码 / 推理 / 指令，不要看知识类基准：知识（MMLU）与事实性（TruthfulQA）在很宽的位宽范围内几乎不动，用它们判断会低估损失。
- author: agent
- from: result.res2, result.res3
- scope: general
- status: provisional
- evidence: 由 `mmlu-does-move` 与 `tqa-flat` 收窄
- repro: 未就位——`WP2` 重算后按 `WP2` 的输出改写
- 说明：这条现在只剩后半句成立（TruthfulQA 确实不动、且它不动是因为地板，`tqa-flat`），前半句「MMLU 几乎不动」被 `mmlu-does-move` 否证。
