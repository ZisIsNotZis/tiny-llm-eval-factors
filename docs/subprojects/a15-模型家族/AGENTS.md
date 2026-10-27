# a15 模型家族（架构代理）— 孙 agent 的窄规则

本文件只写给在本层干活的 worker / reviewer。全局规则在仓库根的 `AGENTS.md`，本文件不复述也不覆盖它，
只补本轴的特别条款。计划与派工在 `PLAN.md`，结果与证据在 `RESULT.md`，可复算脚本在 `analysis/`。

## 1. 家族只有一个定义：`mktables.family_of`

家族 = `.wrapup/mktables.py::family_of(model)`，也就是报告里用的那一套：剥掉量化/配方后缀、归一化 `Qwen_`
前缀、保留尺寸 token。**不要**用 `experiments.__model`——它是 `exp.py` 从文件名解析的标签，会把同一份权重
拆成两个「家族」（`Qwen3.6-35B-A3B` / `Qwen_Qwen3.6-35B-A3B`，实测参数量都是 35505251456；
`LFM2.5-8B-A1B` / `-m55-exq2` / `-m55-exq4`，都是 8467856832），于是配方对被当成跨家族对。
拿不到 `mktables.py` 就 exit 2，不要自己再写一套解析。

## 2. 三层口径，名字不许串用

- `label_matched`：16 个身份栏相等（`__quant` 可以是 NULL，NULL==NULL 也算相等）。**只作清单**：
  `__quant` 为 NULL 时这一栏什么都没钉住，库里这样的格有一千五百多个。
- `bpw_matched`：`|bpw_a − bpw_b| ≤ bpw_match_tol`（0.25 bpw = 半个档宽 `level_width_bpw` = 0.5 bpw）。
  位宽是 GGUF 张量实测值（a02 的 fixture），不是标签。**家族差、可分辨数、可读家族对、翻转计数只在这一层算。**
- 家族层：`bpw_matched` 且**两侧实测参数量不同**。同参数量 = 同一套张量形状（同一架构脚手架），那样的对子
  （a04 的比特分配臂、a10 的第三方量化臂、同权重换标签）进 `same_scaffold` / `recipe_controls` 表，
  数值照给，但**不进家族计数**。

两个常量只有一处：`analysis/pairs.py` 的 `LEVEL_W` / `BPW_MATCH_TOL`，写进 `pairs.json` 的
`level_width_bpw` / `bpw_match_tol`；`effects.py` 从清单里读，不另设一份。

## 3. 参数量真值从 fixture 读

实测参数量与逐张量 bpw 在 `docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json`；
不要用文件名里的 `4B`/`E2B` 标签判尺寸，也不要假设 `/home/z/hf` 存在。

## 4. 候选与排除都要留痕

清单里每个候选恰好出现在一处：要么至少产出一个受控格，要么在 `excluded` 里带一条点名原因
（`analysis/run_all.py` 用「候选数 = 排除数 + 有格候选数」这条关系式盯着）。
**不要**为了少几条排除而加白名单、改判据顺序或跳过某条原因——排除本身就是结论的一部分。
断言只许写关系式与定义（`bpw_matched` 必须等于闸门、每格两个家族都在 `families` 表里、每个配方对照必须
同权重且位宽匹配），不许写快照常量（26470 / 1588 / 152 这类数字只进打印与 `RESULT.md`）：
库每入库一次这些数就变，快照常量会让检查周期性变红，而红的那一次并不代表分析错了。

## 5. 「测不出」就是测不出，格数不是 n

`n_items` 为空的格不算分母、不给区间，写「题数未测」；两区间相交写「不可分辨」，不写 0；
两侧位宽差超过半档的格即使 Δ 很大也不许读成家族效应（它混了比特预算）。
**152 格 / 69 格可分辨是格的计数，不是独立样本数**：它们来自 10 个家族对 × 12 个基准、落在 429 个
(家族对, 基准) 组里，逐组格数由 `effects.py` 的 (g) 段打印。任何「显著/不显著」的说法都必须说明这一点。

## 6. 只读库，不写库

本层以 `file:…?mode=ro` 打开库，没有任何写库路径；两个负控里改身份栏、改尺寸差、删真值都在**副本**上做，
并断言真库与真 fixture 的 sha256 前后不变。要修库里的数写成给 meta 的提案，不在本层动手。

## 7. 本层不做的事

不启 llama-server、不跑评测、不重建 `report.html`、不改 `make_report.py` / `report_inputs/`、不跑 `./reproduce.sh`、
不改别的子项目目录、不改 `.wrapup/mktables.py`（它是报告的家族定义，改它等于改另一层的结论——若确需改，
写成给 meta 与报告拥有者 i02 的提案）。本层额度是纯分析。

## 8. reviewer 附加条款

reviewer 必须实跑 `RESULT.md` 里被审事实的 repro 命令并贴输出，只读代码不算证据。
判级看缺陷等级：证据未绑定 revision、负控不成立、证据句为假、AC 条目无人满足，任一即 P1 不接受。
特别要看三条：负控是否真的**在副本上**改（而不是改真库或真 fixture）；`RESULT.md` 的每个数字是否能在
`analysis/pairs.py` / `analysis/effects.py` 的同一次输出的同一行找到；以及有没有把 `label_matched` 的数
（1588 格）当成「同比特预算」的数来写。
