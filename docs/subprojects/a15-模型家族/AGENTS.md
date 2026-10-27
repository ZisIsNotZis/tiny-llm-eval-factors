# a15 模型家族（架构代理）— 孙 agent 的窄规则

本文件只写给在本层干活的 worker / reviewer。全局规则在仓库根的 `AGENTS.md`，本文件不复述也不覆盖它，
只补本轴的特别条款。计划与派工在 `PLAN.md`，结果与证据在 `RESULT.md`，可复算脚本在 `analysis/`。

## 1. 「家族」是标签，不是元数据

`experiments.__model` 是 `exp.py` 从文件名解析出来的家族标签，不是模型元数据；同一个文件的某些行它是 NULL。
所以（a）家族按**文件**取唯一非空值，全 NULL 的文件登记 `family_unknown`、不当同族处理；
（b）一个文件上出现两个不同的非空家族值就是数据缺陷，脚本抛错而不是挑一个。
同一份权重在库里可能被拆成两个「家族」（`Qwen3.6` / `Qwen_Qwen3.6`）或几个配方变体（`LFM2.5` / `LFM2.5-m55*`），
引用任何一个家族差之前先看 `analysis/pairs.json` 的 `families` 表与实测参数量。

## 2. 参数量真值从 fixture 读，位宽用测出来的 bpw

实测参数量与逐张量 bpw 在 `docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json`；
不要用文件名里的 `4B`/`E2B` 标签判尺寸，也不要假设 `/home/z/hf` 存在。
「同一量化档」的判据是 `__quant` 栏相等**加上**两侧实测 bpw 相差 ≤ 半档（0.25 bpw）；
只有 `__quant` 相等不算同档（`UD-Q2_K_XL` 在不同家族上可以差 1.4 bpw，`UNKNOWN` 是个标签而不是档位）。

## 3. 候选与排除都要留痕

清单里每个候选恰好出现在一处：要么至少产出一个受控格，要么在 `excluded` 里带一条点名原因
（`analysis/run_all.py` 用「候选数 = 排除数 + 有格候选数」这条关系式盯着）。
**不要**为了少几条排除而加白名单、改判据顺序或跳过 `family_unknown`——排除本身就是结论的一部分。
断言只许写关系式与定义（尺寸差 ≤ 容差、每格两个文件都有家族），不许写快照常量（24428 / 1112 这类数字只进打印与 `RESULT.md`）：
库每入库一次这些数就变，快照常量会让检查周期性变红，而红的那一次并不代表分析错了。

## 4. 「测不出」就是测不出

`n_items` 为空的格不算分母、不给区间，写「题数未测」；两区间相交写「不可分辨」，不写 0；
两侧位宽差超过半档的格即使 Δ 很大也不许读成家族效应（它混了比特预算）。
每个结论都要能被 `analysis/effects.py` 的某一节重新打印出来，`RESULT.md` 里不许有手抄的数字。

## 5. 只读库，不写库

本层以 `file:…?mode=ro` 打开库，没有任何写库路径；`pairs_negative_control.py` 里改身份栏、改尺寸差都在
**副本**上做，并断言真库与真 fixture 的 sha256 前后不变。要修库里的数写成给 meta 的提案，不在本层动手。

## 6. 本层不做的事

不启 llama-server、不跑评测、不重建 `report.html`、不改 `make_report.py` / `report_inputs/`、不跑 `./reproduce.sh`、
不改别的子项目目录。本层额度是纯分析。

## 7. reviewer 附加条款

reviewer 必须实跑 `RESULT.md` 里被审事实的 repro 命令并贴输出，只读代码不算证据。
判级看缺陷等级：证据未绑定 revision、负控不成立、证据句为假、AC 条目无人满足，任一即 P1 不接受。
特别要看两条：负控是否真的**在副本上**改（而不是改真库或改真 fixture），以及 `RESULT.md` 的每个数字是否
能在 `analysis/pairs.py` / `analysis/effects.py` 的输出里找到同一行。
