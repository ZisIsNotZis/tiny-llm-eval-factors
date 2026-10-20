# a01 量化位宽 — 本目录规则

本文件只写这个 subproject 自己的窄规则；通用法则在仓库根 `AGENTS.md` 与 `/home/z/vibe/AGENTS.md`，不在此复述。
里程碑、工作包、AC、预算、判定规则在 `PLAN.md`；已成立的事实与证据在 `RESULT.md`；复算脚本在 `analysis/`。

## 这个轴的口径（违反一条，结论就作废）

1. **X 只有「有效位宽」一个口径**：`8 × 文件字节数 ÷ 参数量`，参数量取 `.wrapup/bpw_map.json`（由 gguf 元数据算出的精确值），不取库里四舍五入的 `__size`。厂商档位名（`Q3_K_M`、`UD-Q2_K_XL`）只能当标签，不能当 X 值——同名档位在不同模型上实际跨度可达 0.4 比特/权重。
2. **每个曲线点都带它的通道状态**：HumanEval+/MBPP+ 的判分不后处理（`i01::res26`–`res28` 的 EvalPlus 审计）、GSM8K 取最后数字、MMLU/ARC-c 的似然打平静默取下标 0、MultiPL-E 的判分是退出码 0。凡是引用这些列的曲线点，必须在 `RESULT.md` 里写明该通道已被排除、未被排除还是未测。
3. **一条 series 只放同一协议的东西**：`_bench` + `protocol` + `ctx_size` + `parallel_slots` + `temp` + `reasoning` 逐列核对，任一不同就是两个测量，必须拆成两条线或在 `RESULT.md` 里显式标注「跨面板」。绝不把不同语言、不同协议、不同面板的数字平均成一个点。
4. **家族内比较**：X 的变化只能在「同一套 base 权重、只换量化文件」的家族内读；跨家族的同位宽点不是受控比较（那是规模轴的活）。

## 区间与拐点

1. **区间用逐题二项区间**（Clopper–Pearson / Wilson），不用跨家族残差：每一格有它自己的 `n_items`，逐题通过是伯努利。
2. **拐点只在家族内位宽点 ≥4 时估**；点数不足写「不可估」并写点数和原因，不许用两点连线造一个拐点。
3. **每个拐点必须附「什么观测会推翻它」**：例如换一种拐点定义（最大曲率 / 分段线性断点 / 边际斜率降到峰值一半）会不会把它挪出区间。
4. **分析不覆盖数字**：`kind: analysis` 的结论只解释 `kind: measured` 的数，不能反过来代替测量。

## 数字纪律

1. 每个数字后面跟证据路径与一条能被别人重跑的命令，缺一不写。跑不出来写「未测」和原因，不写 0、不写「估计」。
2. 已退役路径（`.scratch/originals/*`、`/tmp/MultiPL-E/*`、`/home/z/hf/research/*`）不能当证据来源；要用其中的数只能标成不可复现并写明原件已退役。
3. 复用 `.wrapup/mres/*` 的落盘完成物前先确认它是哪个 `run_tag` 的产物、以及当时的 `np`/`ctx`；不确定就当未知。

## 数据库与共享脚本

1. `experiments.sqlite` 本层**只读**。要写库必须先 `cp experiments.sqlite experiments.sqlite.bakN`（N = 现有最大值 + 1），跑完 `PRAGMA integrity_check` + 清洁检查，再重生成 `report.html` 并给「报告数 = 库数」的核对命令。
2. 不改 `make_report.py`、`mktables.py`、`report.html`（i02 拥有）；不改别的 subproject 目录；不改 `docs/plan/subprojects.md`。发现它们错了写进 `PLAN.md` 的跨子项目依赖。
3. 本层的脚本只放 `analysis/`，只用 `sqlite3` 只读连接；脚本必须能被一条命令重跑并打印可核对的数字。

## GPU

1. 任何 GPU 任务都必须 `bash .wrapup/gpu_locked.sh <cmd>`，全局一次一个，不得绕过锁直接起 `llama-server`。
2. 起 server 前等 `nvidia-smi --query-gpu=memory.free` ≥ 20000 MiB：`flock` 由 shell 释放，而死亡进程的 `cudaFree` 还没完成，锁一到手就起会死在 `cudaAlloc`（`i01` 踩过三次）。
3. 一次 GPU 作业 ≤30 分钟；超了先拆成两个可独立判定的臂。启动前把「跑什么、判据、失败怎么算、日志在哪」写进 `PLAN.md` 对应包，然后 `setsid nohup ... &` 并轮询，不前台等。

## 报告与交付

1. 每条结论指回 `PLAN.md` 三条 AC 之一；说不清服务哪条的工作不做。
2. 给上级只写：结论、证据路径、还差什么、卡在哪。不贴过程。
