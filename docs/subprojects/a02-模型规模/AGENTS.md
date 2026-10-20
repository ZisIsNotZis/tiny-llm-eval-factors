# a02 模型规模 — 孙 agent 的窄规则

本文件只写给在本层干活的 worker / reviewer。全局规则在仓库根的 `AGENTS.md`，本文件不复述也不覆盖它，只补本轴的特别条款。
计划与派工在 `PLAN.md`，结果与证据在 `RESULT.md`，可复算脚本在 `analysis/`。

## 1. 先判 X，再拟合 Y

`experiments.__size` 与 `__activation_size` 不是测量值，是文件名解析结果（`exp.py::double_underscore_fields`），已知有三条互不相同的通道和一处 1000 倍单位错（见 `RESULT.md::size-not-one-thing`）。
任何一行进入回归或曲线之前，先说明它的规模来自哪条通道；说不出通道的行只能进「待判」清单，不能进拟合。判据不是「看起来合理」，是「这一行 `__size` 与 GGUF 张量元素求和一致」或「这一行按 `PLAN.md::WP2` 的规则被归到某条通道」。

## 2. 双变量回归必须先证可识别

`score = f(总参, 激活参)` 只有先给出相关系数、VIF 或设计矩阵结构，才允许报系数。系数符号翻转、或 `total+active` 与 `total+moe` 的调整 R² 差在 0.1 以内，都写成「不可识别」，不写成「激活参有效」。
不可识别时给出的是「缺哪一类受控对」（同总参不同激活，或同激活不同总参）与要补的最小测量，不是一个凑出来的数。

## 3. 不许跨越的语言、协议与判分通道

- 不跨语言池化（`a12`）：MultiPL-E 只在 cpp 与 py 都测过时产出标准列；单语言格子单独写。
- 不跨协议池化（`a12`/`i01`）：`multipl-e-raw-*` 与 `mpl-chat-*` 是不同的 X，不能画进同一条线，也不能互相换算。
- 分母一律用该行自己的 `n_items`；`n_items IS NULL` 的格子不得当分母，只能记「题数未测」。
- 引用某格数字时必须写明它的判分通道状态（`i01` 的 `RESULT.md::res26`–`res28`）：lm-eval 无逐题样本，所以全 timeout 与真 0 在库里不可区分；EvalPlus 不做后处理；gsm8k 用 `flexible-extract`；BFCL 单轮不是官方判分器且 micro 从库算不出。任何结论若依赖这些通道之一，就在同一句里说明。

## 4. 只读库，不写库

本层不改 `experiments.sqlite`。需要修的数写成给 meta 的提案：要动什么、为什么、编号备份序号、改完怎么验证（`PRAGMA integrity_check` + `checks/db_check.py`）。
唯一允许的写操作是本层自己的 `docs/subprojects/a02-模型规模/` 与 `analysis/`，提交时按路径点名，绝不 `git add -A`。

## 5. 本层不做的事

不改 `make_report.py` / `mktables.py` / `report.html`（i02 拥有）；不改别的子项目目录；不改 `docs/plan/subprojects.md`；不启 llama-server、不跑评测（本轴额度是纯分析，任何 GPU 使用都要 meta 批窗口并先看 `nvidia-smi` 的 `memory.free`）。

## 6. reviewer 附加条款

reviewer 必须实跑 `RESULT.md` 里被审事实的 repro 命令并贴输出，只读代码不算证据。
判级看缺陷等级：证据未绑定 revision、负控不成立、证据句为假、AC 条目无人满足，任一即 P1 不接受。
`RESULT.md` 的每个数字必须能由一条命令重算；「报告里的数」不算证据，除非同时给出从库算出它的查询。
