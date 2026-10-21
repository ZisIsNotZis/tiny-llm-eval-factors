# a13 工具调用 BFCL — 本目录规则

本文件只写这个 subproject 自己的窄规则；通用法则在仓库根 `AGENTS.md` 与 `/home/z/vibe/AGENTS.md`，不在此复述。
工作包、AC、预算在 `PLAN.md`；已成立的事实与证据在 `RESULT.md`。

## 这一轴的第一个动作永远是查协议串

1. 任何 BFCL 数字先问它是哪个协议：`bfcl-native-tools-nothink-greedy`（自研匹配器 + OpenAI `tools=`）、`bfcl-prompt-nothink-greedy`（自研匹配器 + 系统消息里塞 schema）、`bfcl-official-multiturn-temp0` / `-partial`（官方 `bfcl` CLI + 官方 checker + 官方 handler）。四个互不可比。
2. 同一协议内还要逐列核对 `ctx_size, parallel_slots, max_tokens, temp, limit_spec, n_items`：多轮的 `ctx_size` 实测在 98304/131072/196608 三档之间跳（`RESULT.md::res7`），不同档就是两个测量。
3. 多轮还多一根轴：官方 `handler` 决定 prompt 模板与响应解析，逐族甚至族内逐尺寸都不同（`RESULT.md::res8`）。所以要跨族比较就必须**固定 handler** 做受控对，不能拿库里两行不同 handler 的数相减。

## 不做什么

1. **不算 BFCL 总分**：不跨协议、不跨类别池化。要一个「多轮的单一数字」时，只有「四个类别都有数的模型」才允许取等权平均，且必须写明这是多轮四类的平均、不是 BFCL 分（`RESULT.md::res3`）。
2. **不把官方 `score/data_overall.csv` 当总分**：它的 `Non-Live` 列是 `N/A`（`RESULT.md::res10`）。
3. **不改生产 harness**：不要修改 `.wrapup/bfcl_run.py`、`.wrapup/bfcl_multi_run.py`、`.wrapup/run_m9_panel.sh`、bundled `bfcl_eval` 包，也不要改 `make_report.py`/`mktables.py`。审计与对照脚本只 import 它们的函数，或把结果写到自己的目录。
4. **不重跑已存的预测**：单轮 15 个 cell 的预测在 `.wrapup/mres/m4-*.jsonl`、`.wrapup/mres/m8-*.jsonl`（`RESULT.md::res5`）。重判同一批预测不需要 GPU，也不要为此重生成——重生成会引入生成侧差异，把判分差和生成差搅在一起。

## 判分器对照的形状（WP2）

1. 两套判分器吃**同一批** `{id, category, calls}` 记录，逐条给 verdict，然后报三种数：(a) 自研准确率、(b) 官方准确率、(c) 双向翻转条数（自研 PASS→官方 FAIL / 反向）。只报 (a)(b) 不报 (c) 等于没说方向。
2. `arg_ok`/`call_ok` 必须**调用** `.wrapup/bfcl_run.py` 里的实现，不重抄一份；官方侧必须用 bundled `bfcl_eval.eval_checker.ast_eval.ast_checker`。两边都不是自己写的判据，才叫同预测对照。
3. 负控两侧都要有：正确调用判 PASS、错函数名/缺必需参数/多一个乱参数/布尔与数字混用各判 FAIL。只测一侧就写「只证明了一半」。
4. `irrelevance`/`live_irrelevance`/`live_relevance` 没有 `possible_answer`，官方侧走存在性判据（与自研同构）→ 写「换判分器动不了」并写原因，不算通过也不算失败（`RESULT.md::res6`、`res11`）。
5. 产物里必须证明「重算的自研分与库里 `_score` 逐位相同」：这条检验同时给出文件↔DB 行的绑定，并证明你的重算还在镜像生产判分器。绑定不唯一就 exit≠0（`audits/official_vs_homegrown.py` 的 exit 3）。

## 官方台账只保留最后一次运行（查数据时最先看这条）

1. `score/<handler>/multi_turn/BFCL_v4_<cat>_score.json` 是**一次运行一个文件**：首行 `{accuracy, correct_count, total_count}`，之后每个判错题一行。同一 handler + 类别的下一次运行会覆盖它，所以同 handler 跨模型复用时早先那次的逐题与汇总都**不在盘上**（`RESULT.md::res4`）。
2. 因此多轮题量只能对「其 run 恰好是该 (handler, 类别) 最后一次」的行溯源到 `total_count`；其余留 NULL 并写明原因，**不要用数据集行数（200）去填**——那是猜，不是溯源。
3. 回填只走 `migrations/backfill_n_items.py --dry-run/--apply --family <族>`，它自己编号备份、幂等、可 `--trace`；改完 `PRAGMA integrity_check` 要 `ok`。

## 入参与退出码

1. 缺 `.wrapup/mres`、缺 bundled 数据集、缺 `bfclenv` 解释器时，脚本必须 **exit 2** 并在 stderr 说明缺什么；打印 `UNMEASURED` 然后 exit 0 等于让「结果不可得」冒充「结论成立」。
2. 每个脚本自己写 `_meta.json`：跑的时刻、每个输入文件的 sha256、条目数、命令串。证据要能绑到 revision。

## GPU 与资源

1. 任何 GPU 任务走 `bash .wrapup/gpu_locked.sh <cmd>`；起服前先 `nvidia-smi --query-gpu=memory.free` 记录空闲显存，起服后断言 server 自报的 `n_slots` 与配置相符，不符即作废该次测量。
2. 反例：`.wrapup/run_m9_panel.sh` 已带 `SMOKE=1`（先要一次真实 completion 再跑长 panel）与陈旧 server 检测，复用它，不要新写一套起服逻辑。
3. 30 分钟硬上限会 SIGTERM 你的进程：长任务 `setsid nohup` 起在后台、日志落盘、轮询，别前台等。

## 数据库

1. `experiments.sqlite` 只读用 `sqlite3 -readonly`；要写先编号备份 `experiments.sqlite.bakN`，且只走 i02 的 `migrate_db.py`（它是唯一入径，跑完看它的 skip ledger）。
2. `n_items` NULL 是声明的缺失：可以给出来源（`RESULT.md::res3`/`res4`），不得在结论里当 0 用。
