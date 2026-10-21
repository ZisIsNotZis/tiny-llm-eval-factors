# a08 思考开关 — 孙 agent 规则

本文件只写本子项目里会让孙 agent 做错事的地方。仓库级与子项目级的通用规则见
`/home/z/vibe/local_lm_research/AGENTS.md` 与 `docs/plan/subprojects.md`，此处不复述。

## 边界

- 可写：`docs/subprojects/a08-思考开关/` 下的全部路径，以及 `.wrapup/mres/a08-*`（测量产物，git 忽略）。
- 不写：其他子项目的目录、`docs/plan/subprojects.md`、`make_report.py`、`.wrapup/mktables.py`、
  `.wrapup/lmeval_run.py`（i02 的量测基础设施；发现缺陷写进本目录并按 WP 上报，不改它）。

## 一格的身份里有 reasoning

- `reasoning` 是协议身份的一部分，和 `protocol`/`max_tokens`/`ctx` 同等。**on 格永不与 off 格池化、永不平均**：
  一个是「思考关」这个产品协议，另一个是另一个协议。
- 一个对只有在一个变量不同时才能读出效应：`--reasoning` 变了，别的（模型、基准、题量、`max_tokens`、ctx、温度）必须逐字相同。
  `max_tokens` 不同的对被保留但标 `budget_matched=0`，因为差里同时含两个变量。
- 库里 `max_tokens` 为 NULL 的旧格，预算取自它自己的 `lmeval_panel.json`（`profiles[task]` 或顶层 `max_gen_toks`），
  来源写进 fixture 的 `mt_source` 列。**取不到就是 NULL，不填默认值**。

## 数字怎么读

- 分数差先换成题数：`Δscore × n_items`。`n_items` 未知时先证明分母，证不出来不下结论。
- 确定性解码地板是 0 道题（i01），所以同一协议内的逐格差是真实效应；但**跨协议比较不需要地板**，需要的是同一对的其余条件相同。
- a03 的分辨率是 0.10–0.49：落在这一区间的差只能写「与量化标签效应不可分辨」，不能写「没有效应」。
- 延迟只用 panel `timings_s`（harness 包住 lm_eval 的墙钟）。结果 json 里的 `total_evaluation_time_seconds` 是另一个口径
  （同一次 gsm8k：662.6 s 对 1507.7 s），两者不许混用。
- 生成 token 数只从 `server.log` 的逐请求 `eval time = … / N tokens` 求和，先剔除起服后的冒烟请求（`1+1=`，`max_tokens=1`）。
  多任务 panel 的日志不能按格归属 → 记 `shared-log`，不猜。

## on 臂必须先证「开关真的生效」

- 0.00 这个分数有两种来源：模型真的答错，或判分器吃掉了推理流（i01 踩过 `--reasoning off` 忘掉的活故障）。
  所以 `on` 臂的结论必须带端点证据（`fixtures/endpoint_probe/` 的原始响应）说明 `--reasoning` 到底改了什么，
  否则「分数掉了」无法归因。
- `/props` 里的默认参数不证明单次请求生效（a06 已记）。判据是同一提示词在 `off`/`on` 两次真实请求的响应差分。

## 脚本纪律

- 数字只从 `analysis/thinking_pairs.py` 出来：`--write` 落 fixture，`--check` 与 fixture 逐字比。
  **不许手改 `fixtures/*.tsv`**：手算与 fixture 不一致时 fixture 赢，或者是脚本的选择规则错了，两者都要修一个。
- 加了新臂或新类，**在现有脚本里加**，不另写一份分析脚本（同一个问题两个家）。
- 负控：`--selftest` 必须证明「改坏一行 → 检查变红」。一条不会失败的检查等于没有检查。
- 脚本只读打开库（`file:experiments.sqlite?mode=ro`），禁止写库。
- 任何结论在干净 clone 里要能重算或至少能读到（fixture + 来源 sha256 随仓库走）。

## GPU 与库

- 任何 GPU 任务都在 `bash .wrapup/gpu_locked.sh` 下跑；起服后断言 `server.log` 里有 `n_slots = 1`，不符即作废该次测量。
- 起服前看 `nvidia-smi` 的 `memory.free`（同一张卡还有别的仓库的任务，锁只管本仓库）。
- 改库：编号备份（`experiments.sqlite.bakN`）→ 只经 `migrate_db.py` → 改完 `db_check` → **行数对账**。
  `ingest_campaign` 会先 `DELETE FROM experiments WHERE source_file LIKE 'mres/%'` 再重读所有 panel，
  所以每次入库都要报「改前 mres 行数、改后 mres 行数、新增/消失的是哪几格」，消失的行必须先解释。
- 提示集使用 `.wrapup/prompts` 与库内 fixture，不重新生成数据集。

## 交付

- 每条事实写「结论 / `- evidence:`（可重跑的命令或落盘文件）/ `- repro:`」，不写「已确认」「已验证」。
- 失败、阻塞、被取代的旧值都写出来；未测写「显式未测 + 理由 + 解除条件」。未测 ≠ 0。
- 结束时报：做了什么、改了哪些文件、跑了什么命令得到什么结果、还剩什么风险；没有独立复核就写「未复核」。
