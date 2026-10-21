# a14 部分给分 — 本目录规则

本文件只写这个 subproject 自己的窄规则；通用法则在仓库根 `AGENTS.md` 与 `/home/z/vibe/AGENTS.md`，不在此复述。
工作包、AC、预算在 `PLAN.md`；已成立的事实与证据在 `RESULT.md`。

## 这个项目的 Y 有两个，别混

1. **二元 pass@1**：一道题要么过要么不过，分数 = 通过题数 / 题数。项目现有报告用的就是这个。
2. **逐测试通过比例**：一道题内部有若干条单元测试，比例 = 通过的测试数 / 该题提供的测试数。有两种聚合，必须分开写、分开引用：`mean_frac`（先按题算比例，再对题取平均）与 `micro_frac`（总通过测试数 / 总测试数）。**二者的差不是噪声，是两个不同的问题**，报告里只许写你实际算的那一个。
3. 「逐题 Jaccard」「通过集一致率」不是第三种 Y，是同一 Y 的可复现性度量，不能当分数报。

## 数字纪律

1. 每个数字跟证据路径与一条能重算它的命令。跑不出来写「未测」并写原因，**不写 0，不写估计**。
2. 分母来自测试源码（`testfrac.py::expected_count`），不是执行到的断言数：程序在第 2 条断言崩溃时，它没跑到的 3 条算没通过，不算「没跑」。引用任何比例前先确认分母口径。
3. `mean_frac` 与 `micro_frac` 不能跨语言池化，也不能与 `a12` 的 161 题格混着比：本题集在 `java` 上是 158 题（`m1-qwen4b-q2-java` 实测 n=158），比 161 少的题不能当 0 分也不能当去掉。
4. 跨协议不比：`temp`、`top_k`、`ctx`、`parallel_slots`、提示集版本、判分器版本任一不同就是两个测量。逐列核对 `experiments` 表后再配对。

## 输入与证据

1. a14 的输入全部是已入库产物：`.wrapup/mres/<tag>_eval.json`（逐题二元）、`.wrapup/testfrac_<tag>.jsonl`（逐题比例）、`experiments.sqlite`。**干净 clone 里必须能算**，所以任何一个查不出来的结论都要先怀疑自己用了 gitignored 的东西（`.wrapup/mres/*.jsonl` 完成物、`/tmp/MultiPL-E/prompts`、三个 venv 全都不随仓库分发）。
2. 用到 gitignored 输入才能得到的结论，必须在 `RESULT.md` 标「clean clone 不可复算」，并给出代价。不许混进「clone 里绿」的那一类。
3. `testfrac` 的逐题文件是上一轮（m38/m41）的产物，复用前先确认它对应的 `<tag>_eval.json` 在场且逐题判定一致；不一致就是发现，不是噪声。

## 判分实现本身是变量

1. `testfrac.py` 靠注入探针计数（cpp 覆盖 `assert` 宏、js 猴补 `node:assert`、py 用 ast 改写 `assert`、java 改写 `assert(`），所以它与 harness 的二元判定一致性**必须实测**，不能假设。实测不一致时，先判是不是探针改变了程序行为，再考虑拒绝该格。
2. 四种语言以外（`rs`/`rb`/`pl`）没有探针实现 → 这些语言的逐测试比例是「不可得」，除非写新探针；写新探针要在 `PLAN.md` 记一次设计变更。

## GPU 与库

1. 本项目默认不占 GPU。要占必须先改 `PLAN.md` 写清「哪个族、为什么 CPU 侧做不到、多少分钟」，然后走 `.wrapup/gpu_locked.sh`。
2. 只读库。任何写库先做编号备份，且写库不属于本项目的任何 AC，所以默认不做。

## 记忆与交付

1. 每条结论指回 `PLAN.md` 里程碑三条之一；说不清服务哪条的工作不要做。
2. 报告给上级只写：结论、证据路径、还差什么、卡在哪。不贴过程。
3. 不改别的 subproject 目录、不改 `docs/plan/subprojects.md`、不改 `make_report.py`/`mktables.py`/`report.html`。
