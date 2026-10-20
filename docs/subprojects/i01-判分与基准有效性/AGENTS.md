# i01 判分与基准有效性 — 本目录规则

本文件只写这个 subproject 自己的窄规则；通用法则在仓库根 `AGENTS.md` 与 `/home/z/vibe/AGENTS.md`，不在此复述。
工作包、AC、预算在 `PLAN.md`；已成立的事实与证据在 `RESULT.md`。

## 判分审计的形状（每族一份，缺一项就不算完成）

1. 四问逐问给裁决，不许合并成一句「判分正常」：剥不剥 markdown、保不保缩进、记不记状态直方图、坏完成物能否被打成可信数字。
2. 每个裁决带证据：文件名 + 函数名或行、以及一条能被别人重跑的命令。`@falsifiable`：说「会剥围栏」时必须给出「围栏样例进去、什么出来」的实际输出。
3. 负控必须能失败：先证明「错的完成物会被判错」和「对的会被判对」两侧都观测到；只测一侧的写「只证明了一半」。
4. 审计脚本写成 `docs/subprojects/i01-判分与基准有效性/audits/<harness>_audit.py`，只 import / 调用生产判分路径，不改生产 harness（`mpl_run.py`、`lmeval_run.py`、`bfcl_run.py`、evalplus 包）。要改就必须先在 `PLAN.md` 记一次设计变更，否则视为越界。
5. 审计文档放 `docs/subprojects/i01-判分与基准有效性/audits/<harness>.md`，一个 harness 一份；不要写进 `RESULT.md`，`RESULT.md` 只放收口后的结论。

## 数字纪律

1. 每个数字后面跟证据路径和复现命令，缺一不写。**跑不出来就写「未测」并写原因，不写 0，不写「估计」。**
2. 已退役路径（`.scratch/originals/*`、`/tmp/MultiPL-E/*`、`/home/z/hf/research/*`）不能作为证据来源。要用其中的数，只能标成不可复现，并说明原件已退役。
3. 复用别人留下的 `.wrapup/mres/*` 文件前先确认它是哪一次运行的产物；不确定就当未知，不猜。
4. 「同协议串」不等于「同配置」：ctx_size、parallel_slots、模板、提示集版本、判分器版本任一不同，就是两个测量。比较前逐列核对 `experiments` 表的 `protocol, ctx_size, parallel_slots, max_tokens, seed, temp, n_items`。

## GPU 与资源

1. 任何 GPU 任务都必须 `bash .wrapup/gpu_locked.sh <cmd>`，全局一次一个；不得绕过锁直接起 `llama-server`。
2. 一个 GPU 任务开始前把「跑什么、判据、失败怎么算、日志在哪」写进 `PLAN.md` 对应包，然后 `setsid nohup ... &` 启动并轮询，不前台等。
3. 单次 GPU 作业 ≤90 分钟为默认上限，超了先拆。CPU 重活并发 ≤2。
4. 起 server 前先记录配置（`-np`、`-c`、模板、max_tokens），落进日志首行，因为 plan15 的教训正是「槽位数没被当成输入」。

## 数据库

1. 任何写库前先做编号备份：`cp experiments.sqlite experiments.sqlite.bakN`（N 取现有最大值 +1），跑完 `PRAGMA integrity_check` 与清洁检查（无 NULL 必填项、布尔/范围合法）。
2. 未测的格记 NULL，不写 0。
3. 改库后必须重生成 `report.html`，并给出一条「报告的数 = 库查询的数」的核对命令；没改库就写明没改。

## 记忆与交付

1. 每条结论都指回它服务的 AC（`PLAN.md` 三条之一）。说不清服务哪条的工作，不要做。
2. 报告给上级只写：结论、证据路径、还差什么、卡在哪。不要贴过程。
3. 不要修改别的 subproject 目录，不要改 `docs/plan/subprojects.md`，不要改 `make_report.py`（发现它坏了就写进 `PLAN.md` 的跨子项目依赖）。
