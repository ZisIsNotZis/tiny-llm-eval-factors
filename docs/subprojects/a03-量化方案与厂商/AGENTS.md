# a03 量化方案与厂商 — 本目录规则

本文件只写这个 subproject 自己的窄规则；通用法则在仓库根 `AGENTS.md` 与 `/home/z/vibe/AGENTS.md`，不在此复述。
里程碑、工作包、AC、判据与派工在 `PLAN.md`；已成立的事实与证据在 `RESULT.md`；复算装置在 `analysis/`。

## 这个轴的口径（违反一条，结论就作废）

1. **X 是标签，不是一个数**：方案标签（IQ / K / TQ）、来源标签（厂商 / 上传者）都是**类别变量**；它们的效应只能在「同一套 base 权重、同一字节预算、同一协议」的族内配对里读。不得把标签当连续变量或当质量分。
2. **匹配字节的判据必须写出来**：一律给三档（`|Δbpw| ≤ 0.45 / 0.15 / 0.05`），并说明结论在哪一档成立。`0.45` 是报告第三节的现行口径，不是本层的推荐值——它本身允许约 0.084 的 HumanEval+ 分差（`RESULT.md::slopes`）。
3. **厂商从路径取，不从文件名推**：`mscache/<vendor>/…`、`models--<vendor>--…` 才算来源证据，且要经 `run_tag` 与库内行对上。`UD-` 前缀说明的是**配方**（动态分配），不是来源；`Phi-4-mini-instruct-Q2_K.gguf` 与 `Llama-3.2-3B-Instruct-Q3_K_M.gguf` 就是反例（非 UD 命名、实际来自 unsloth）。
4. **一格一协议，不池化**：`_bench` + `protocol` + `ctx_size` + `parallel_slots` + `temp` + `reasoning` 必须逐列相等；不等判「不可比」并打印。语言、协议、基准之间绝不平均，也不跨族把同字节点当受控比较。
5. **区间用两比例差的 Newcombe method 10**，`n` 取该格自己的 `n_items`；TruthfulQA 的 `acc` 是概率质量均值（`i01::res26`），那一列只报差值。区间是非配对的（逐题结果没落库），所以「跨 0」写「测不出」，不写「相等」。
6. **先看 `n_items`**：`ifeval/gsm8k/arc_challenge/truthfulqa_mc2` 是 `limit 100` 的子集，`mmlu` 912，`humaneval*` 164，`mbpp*` 378。缺格写「缺」，不写 0。
7. **分配轮廓用实测**：`alloc.py` 从 gguf 张量信息段算每个张量的字节与元素数（相邻 offset 之差），不查类型表、不加载权重；校验不过（文件位宽与数据段位宽差 > 0.05）就打 WARN 并给逐类比重要打折。
8. **单次运行**：所有配对只有一次运行，区间不含跨 run 项；小于 0.05 的差只能说「测不出」。`i01::res29` 的量级（±16/161）是引用，不是本层的地板。

## 与 a01 / a04 的分工（别越界）

1. **区间与家族定义借 a01 的**：`analysis/pairs.py` 直接 `import curves` 用 `newcombe_diff` / `wilson` / `family_of`，不复制；a01 改了名字本层就报错，不静默用第二套口径。
2. **不重做 a01 的测量**：`m55-exq2/exq4` 的分数差是 `a01::m55-exq-inversion` 的事实，本层只用自己的分配轮廓解释它「为什么不是厂商效应」，不重新测、不重新下结论。
3. **层比特分配的策略结论归 a04**：本层只把分配轮廓当混杂变量与代理变量读，不说「专家层该压多低」。
4. **不改别的 subproject 目录、不改 `docs/plan/subprojects.md`、不改 `make_report.py`/`mktables.py`/`report.html`**（i02 拥有）。

## 数字纪律

1. 每个数字后面跟证据路径与一条能被别人重跑的命令，缺一不写。跑不出来写「未测」和原因，不写 0、不写「估计」。
2. `.scratch/originals/*` 已退役，那里的数只能标「不可复现」并写明原件已退役（`res7` 的旧措辞就是这样撤回的）。
3. 复用 `.wrapup/mres/*` 的落盘产物前先确认它是哪个 `run_tag` 的产物、当时的 `np`/`ctx`/协议串；不确定就当未知。
4. 结论必须指回 `PLAN.md` 的 AC 之一；说不清服务哪条的工作不做。

## 数据库与脚本

1. `experiments.sqlite` 本层**只读**（`sqlite3` 的 `mode=ro`）。要写库必须先编号备份、跑完整性与清洁检查、重生成 `report.html`——本层不做这三件事，写库需求交给拥有数据的层。
2. 本层脚本只放 `analysis/`，必须能被一条命令重跑并打印可核对的数字；`analysis/run_all.py` 的退出码就是结论。
3. 不加载模型、不占 GPU。要 GPU 的只有复现负控：`bash .wrapup/gpu_locked.sh`、起服前看 `memory.free` 并按实测需求而不是固定阈值判断、起服后断言 server 自报 `n_slots`。
