# a06 采样与解码参数 — 计划

计划层的唯一 home。goal / purpose / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a06 行定义，本文件不复述；
本文件只写里程碑、工作包、状态、派工与判据。数字的当前值在 `RESULT.md`，这里只写判据和状态。

## 里程碑：研究结束

- 终点状态：a06 的 AC 全部有可复算证据——「厂商推荐采样 vs 固定协议」的受控检查有结论（或显式登记为不可得并说明代价），
  温度 / top_k 的每条结论都能由 `RESULT.md` 里的一条命令重算出来。
- done 判据（四条同时成立）：
  1. `python3 "docs/subprojects/a06-采样与解码参数/sampling_census.py"` 退出 0，并打印协议普查、固定协议的参数、可用比较清单；
  2. `RESULT.md` 的每条事实都带 `- evidence:` 与 `- repro:`，且 `repro` 是一条命令；
  3. 三条轴的结论都在 `RESULT.md` 里有数：分数移动、逐题判决移动、量化档/规模次序是否存活；
  4. `plan3` 有终态：要么「厂商推荐臂已测且结论如下」，要么「厂商推荐值不可得（原因）+ 已有温度臂给出什么」，
     不许停在「待跑」。
- 只有这一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`（文档归位 + 协议普查）与 `WP2`（逐题判决移动）。
  两个只读脚本都退出 0，捕获在 `evidence/`：`census-6fc5b0c.txt`（267 行）、`peritem-2552615.txt`（36 对），
  各自带一份负控（空临时树里跑同一脚本 → 输入全缺、exit 2）。
- 在办：`WP3`（厂商推荐臂）**外部阻塞**：本机无外网，模型卡也不在本地缓存，见 `RESULT.md` 的 `res-vendor-gap`。
- 下一步派给谁：`WP4`（规模次序）需要一个 GPU 槽，先看 `nvidia-smi` 的 `memory.free` 再决定能否起服；
  `WP5`（独立复核）由 meta 派 fresh-context reviewer——复核可先针对 `WP1`/`WP2` 的产物做，不必等 `WP3`/`WP4`。
- 真正未做的只剩两件：`WP3` 的厂商推荐值（等外网）+ `WP4` 的规模次序（等显存）。
  AC 的「温度/top-k 结论可复算」那一半已经完成；「厂商推荐采样 vs 固定协议受控检查完成」那一半在两个轴上都不成立于当前环境。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 + 协议普查 | a06 编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`plan.yaml` 与 `result.yaml` 已删除且 `plan3`/`res10` 以 `## <id> :: <text>` 事实存活；`sampling_census.py` 退出 0，缺任一输入（库 / `m27_summary.jsonl` / `m31_summary.jsonl` / `variant_panel.json`）时退出 2；`python3 docs/check_docs.py` 退出 0 | — | 1 会话 | 完成 |
| WP2 逐题判决在协议改变时移动多少 | a06 worker（CPU 槽） | 对 `.wrapup/mres/m27-*_eval.json` 与 `m31-*_eval.json` 逐题比 greedy 锚点与每个 temp>0 / top_k 设置，给出每 (模型, 语言, 设置) 的 up/down 翻转数与 Jaccard，并回答「净分数移动 vs 逐题翻转」是否与 i01 的 temp=0.3 五跑地板同量级；缺产物时 exit 2 | WP1 | 0.2 CPU 时 | 完成：`peritem_moves.py` 比完 36 对（3 档 × 2 语言 × 6 设置）退出 0；Jaccard 0.40–0.69，23/36 对净移动 ≤ 6 道题（与 i01 五跑地板不可分），最极端一格净 +1 而 15 上/14 下；负控在空临时树里 exit 2 |
| WP3 厂商推荐采样臂（`plan3` 的受控检查） | a06 编排者（需要外网取值）+ GPU worker | 在 `.wrapup/mres/*/variant_panel.json` 的 sampling 轴里加入名为 `vendor` 的一档，其采样参数逐字取自模型卡（记录 URL + 抓取日期到 `RESULT.md`），与 `greedy` 同模型同 bench 同 n_items 对照；若模型卡不可达，则本条 AC 记为「不可得 + 原因 + 已有什么」，不得用猜的值填 | 模型卡可达（本机当前无外网，见下） | 约 10 GPU 分钟/模型/档（m131 实测 5 档 4 个基准共约 45 分钟） | 阻塞（外网） |
| WP4 规模次序在采样下是否存活 | GPU worker | 同族 ≥3 个规模（例如 Qwen3.5-0.8B/2B/4B）在同一 bench、同一 ctx 下各有 greedy 与一档 temp>0 的格；给出规模对的 win/loss 与次序反转数，且与 WP1 的量化档结论分开报告 | 一个 GPU 槽 + `variant_panel.py` 的 sampling 轴（已在盘上） | ≤40 GPU 分钟（2 个模型 × 2 档 × 4 基准，按 m131 的 9–10 分钟/档估） | 待派（等显存） |
| WP5 独立复核 | fresh-context reviewer（meta 派） | 对本目录三份文档与 `sampling_census.py` 的输出给裁决，指出证据缺口；reviewer 的结论取代本人的自评 | WP1–WP4 | 一次复核 | 待派 |

## plan3 :: 假设 B2（厂商推荐采样）：unsloth 给每个模型发布推荐运行/采样参数，而我们固定协议；做一次受控检查，看厂商推荐采样会不会改变任何量化结论（即我们的协议是否是 confound）。

- author: agent
- scope: general
- status: provisional
- domain: kind: hypothesis
- 当前判定：**未测**。厂商推荐值是一个外部事实，必须逐字取自模型卡；本机实测 `curl` 到 `huggingface.co` 12 秒超时（`curl: (28) Connection timed out`），
  且 `/home/z/hf/models--unsloth--Qwen3.5-2B-GGUF/snapshots/…/` 里只有 `.gguf` 软链、没有 `README.md`，所以本机拿不到这个输入。
  按 `@absent`，缺的值记「不可得」，不填默认值——填一个「厂商推荐 = temp 0.7 / top_p 0.8」就是把推断冒充成事实。
- 已有部分答案：厂商推荐值与本研究实测过的温度臂同类，所以 `RESULT.md` 的温度/top_k 结论已经把「采样能不能改变量化结论」这一半回答了；
  剩余的不确定性只有「厂商那一档的具体取值是否落在已测取值之外」，见 `RESULT.md` 的 `res-vendor-gap`。
- 解除条件：任一可用的外网出口，或把模型卡的推荐段落落盘进仓库。解除后 `WP3` 直接可跑，不需要重新设计。

## 判据（写死，避免事后挑解释）

1. **一格的协议 = 它的身份**：`protocol` 串（含 `;ctx=` `;kv=` `;tmpl=` 段）、`max_tokens`、`ctx_size`、`n_items` 任一不同就是两个测量。
   不跨协议池化，不跨语言池化，60 题探针不与 161 题满格比。
2. **可以读的列与不可以读的列**：`temp`/`top_k` 只在取值属于本仓声明过的设置时才当作采样设置读（普查 `[A]` 段）。
   落在声明集合之外的行，其采样设置是 UNKNOWN，不读它的列值。
3. **分数的移动要按题数读**：`Δscore × n_items` 才是移动了几道题；n_items 缺失时先证明分母（MultiPL-E 的 cpp/py 满格 161，
   可由 `score × 161` 全是整数验证），证不出来就不读。
4. **「噪声」与「效应」的分界**由 i01 的地板决定：确定性解码地板 = 0 道题；temp=0.3 同一格五跑的净分数摆动上限 6/164。
   净移动超过地板、且靠近或超过 6/164 的，只有拿到逐题产物才能下结论（`WP2`）。
5. **次序存活**用成对比较数（concordant / discordant / tie），不用单个模型的一个数。一个格的方向不算次序。

## 非目标

- 不重测固定协议：`multipl-e-raw-greedy-768` 的 180 格与 `evalplus-*` 的 148 格是既有资产，普查只读。
- 不补 `top_p` 轴：`top_p` 在每一条已测协议里都钉在 0.95，从不是变量；把它变成变量是一条新轴，超出 7% GPU 份额。
- 不改 `make_report.py` / `.wrapup/mktables.py`：报告第六节的呈现问题（`top_k` 撞标签）属 i02，a06 只提供证据。
- 不改其他子项目目录、不改 `docs/plan/subprojects.md`。
- 不重生成提示集：`.wrapup/prompts` 是唯一来源。
- 不修那 490 行采样列不可信的历史行的库值：修法是 i02 的库整洁范围，a06 只登记「这些行的采样设置 UNKNOWN」并保证自己的比较不依赖它们。

## 派工与资源

- GPU：占 4 周周期的 7%，全局串行，任何 GPU 任务必须在 `bash .wrapup/gpu_locked.sh` 下跑，一次一个；
  起服前看 `nvidia-smi` 的 `memory.free`（同一张卡上还有别的仓库的任务，`/tmp/llama_gpu.lock` 只管本仓库），
  起服后断言 server 自报的 `n_slots` 与 `-np` 相符，不符即作废该次测量。
- CPU：5%，两个并发以内；普查与逐题分析都是秒级只读脚本。
- 改库前做编号备份（`experiments.sqlite.bakN`），入库只走 `migrate_db.py`（见 `AGENTS.md`）。
