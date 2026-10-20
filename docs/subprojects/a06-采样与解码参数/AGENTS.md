# a06 采样与解码参数 — 孙 agent 规则

本文件只写本子项目里会让孙 agent 做错事的地方。仓库级与子项目级的通用规则见 `/home/z/vibe/local_lm_research/AGENTS.md`，
此处不复述。

## 边界

- 只有派工单里点名的路径可写；a06 的文档与脚本在 `docs/subprojects/a06-采样与解码参数/`。
  其他子项目的目录、`docs/plan/subprojects.md`、`make_report.py`、`.wrapup/mktables.py` 都不在 a06 的写权限内。
- `report.html` 是生成物：永不手改。
- `.wrapup/variant_panel.py` 是 i02 的量测基础设施，a06 不直接改它的 `AXES`；要加一档就把「加哪一档、参数逐字是什么、出处 URL」写进 `PLAN.md` 的 `WP3`，由 i02 落。
- 报告第六节把 `m31` 的 `top_k` 格与 `m27` 的 `t0.3` 格印成同一行标签，这是 i02 的呈现问题；a06 只提供数值证据，不擅自改报告代码。

## 一格的协议 = 它的身份

- 不跨协议、不跨语言、不跨 harness 池化。比较前逐列核对 `protocol`（含 `;ctx=` `;kv=` `;tmpl=` 段）、`max_tokens`、
  `ctx_size`、`n_items`、`reasoning`。任一不同就是两个测量，打印并跳过，不许平均。
- 贪心协议串有多个（`multipl-e-raw-greedy-768` 是固定协议，另有限速探针 256、BFCL 512、lm-eval chat 1024）。
  它们不是同一个协议，`max_tokens` 不同的贪心格**不能**互相当作复现证据。
- 60 题探针不与 161 题满格比；`m131` 的 GSM8K/IFEval 是 `--limit 50`，只能与同为 50 题的格比。

## 采样列的读法

- `temp`/`top_k`/`top_p`/`min_p`/`presence_penalty` 只在这一行的取值属于本仓声明过的设置时才是采样设置。
  落在声明集合之外的行（当前 490 行，`source_file` 与 `run_tag` 都是 NULL）其采样设置是 **UNKNOWN**：
  不读它的列值，也不把它算进任何一个采样比较。判据见 `sampling_census.py` 的 `[A]` 段。
- `top_k=1` 在名义温度 0.3 下等价于贪心（top-1 截断即 argmax），这一点是被 6/6 个 MultiPL-E 格与贪心格逐字相同**证实**的，
  可以在比较里当贪心锚点用，但引用时必须带上这条证据。
- `top_p` 在所有已测协议里都钉在 0.95，从不是变量。不要把「换个 top_p」当成已测过的采样变化。

## 数字与判据

- 分数移动要换成题数：`Δscore × n_items`。`n_items` 是 NULL 时先证明分母——MultiPL-E cpp/py 满格 161 的判据是
  「`score × 161` 全为整数」，证不出来就不下结论。
- 「噪声」与「效应」的分界用 i01 的地板，不用感觉：确定性解码地板 = 0 道题；temp=0.3 同一格五跑的净分数摆动上限 6/164。
  净移动超过地板但与 6/164 同量级的格，只有拿到逐题产物才能判；没有逐题产物就写「与重复噪声不可分」。
- 次序存活用成对比较数（concordant / discordant / tie）报，不用单个模型的单个差。
- 未测 ≠ 0：没跑就写「显式未测 + 理由 + 解除条件」，不填默认值。厂商推荐采样值取不到时，写「不可得」并给出命令与退出码，
  不许自己造一个「厂商推荐 = temp 0.7」再去测。
- 任何一条结论都要能由 `RESULT.md` 里的一条命令重算。跑 `python3 "docs/subprojects/a06-采样与解码参数/sampling_census.py"`，
  退出非 0（2）就先修输入，不得带着 `UNMEASURED` 交付。
- 改了普查脚本就跑负控：在空目录里跑同一脚本必须打印四条 `missing …` 并退出 2；
  一条不会失败的检查等于没有检查。

## 数据与测量

- 任何改库前先做编号备份（`experiments.sqlite.bakN`，`numbered_backup` 自校验），改完跑完整性与洁净检查。
  `migrate_db.py` 是唯一入库路径，必须保持幂等；不进库的数字不算存在。
- 普查与逐题分析只读打开库（`file:experiments.sqlite?mode=ro`），不要写。
- 任何 GPU 任务必须在 `bash .wrapup/gpu_locked.sh` 下跑，一次一个；起服前看 `nvidia-smi` 的 `memory.free`
  （同一张卡上还有别的仓库的任务，锁只管本仓库），起服后断言 server 自报的 `n_slots` 与 `-np` 相符，不符即作废该次测量。
- 提示集只用 `.wrapup/prompts`，跑前跑后都不许重生成。

## 交付

- 每条事实写「结论 / `- evidence:` / `- repro:`」，evidence 是可以重跑的命令或落盘文件路径，不写「已确认」「已验证」。
- 采集失败、阻塞、被取代的旧值都要写出来，而不是从结果里删掉。
- 结束时报：做了什么、改了哪些文件、跑了什么命令得到什么结果、还剩什么风险；没有独立复核就写「未复核」，不得自评通过。
