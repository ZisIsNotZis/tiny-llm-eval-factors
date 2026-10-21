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
- 在办：`WP3`（厂商推荐臂）**已从「外网阻塞」转为「等 GPU + 等 i02 加一档」**：厂商推荐值已取到并存成 `RESULT.md` 的 `res-vendor-value`，
  但那个值落在已测的每一个设置之外（温度 1.0、`top_p` 1.00、`min_p` 0.0、`presence_penalty` 2.0），所以不能用已有的格代理它，必须真跑。
- 下一步派给谁：`WP3` 需要两步：(a) i02 在 `.wrapup/variant_panel.py` 的 `AXES['sampling']` 里加一档，参数逐字取 `res-vendor-value`；
  (b) 一个 GPU worker 在 `bash .wrapup/gpu_locked.sh` 下跑两个面板（标准列 + MultiPL-E cpp/py 三档），估 30–50 GPU 分钟。
  `WP4`（规模次序）同样等 GPU 槽；`WP5`（独立复核）由 meta 派 fresh-context reviewer，可先针对 `WP1`/`WP2` 的产物做。
- 真正未做的只剩两件：`WP3` 的厂商档测量 + `WP4` 的规模次序。
  AC 的「温度/top-k 结论可复算」那一半已经完成；「厂商推荐采样 vs 固定协议受控检查完成」那一半的**输入**已就位、**测量**未跑。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 + 协议普查 | a06 编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；`plan.yaml` 与 `result.yaml` 已删除且 `plan3`/`res10` 以 `## <id> :: <text>` 事实存活；`sampling_census.py` 退出 0，缺任一输入（库 / `m27_summary.jsonl` / `m31_summary.jsonl` / `variant_panel.json`）时退出 2；`python3 docs/check_docs.py` 退出 0 | — | 1 会话 | 完成 |
| WP2 逐题判决在协议改变时移动多少 | a06 worker（CPU 槽） | 对 `.wrapup/mres/m27-*_eval.json` 与 `m31-*_eval.json` 逐题比 greedy 锚点与每个 temp>0 / top_k 设置，给出每 (模型, 语言, 设置) 的 up/down 翻转数与 Jaccard，并回答「净分数移动 vs 逐题翻转」是否与 i01 的 temp=0.3 五跑地板同量级；缺产物时 exit 2 | WP1 | 0.2 CPU 时 | 完成：`peritem_moves.py` 比完 36 对（3 档 × 2 语言 × 6 设置）退出 0；Jaccard 0.40–0.69，23/36 对净移动 ≤ 6 道题（与 i01 五跑地板不可分），最极端一格净 +1 而 15 上/14 下；负控在空临时树里 exit 2 |
| WP3 厂商推荐采样臂（`plan3` 的受控检查） | i02 加档 + GPU worker 跑 | `.wrapup/mres/*/variant_panel.json` 的 sampling 轴里多一档 `vendor`，参数**逐字**为 `temperature=1.0, top_p=1.00, top_k=20, min_p=0.0, presence_penalty=2.0, repetition_penalty=1.0`（来源 `RESULT.md::res-vendor-value`），与 `greedy` 同模型同 bench 同 `n_items` 对照；另在 MultiPL-E 上对 Q2/Q3/Q4 × cpp/py 跑同一档，以回答「厂商档下 Q3-vs-Q4 在 cpp 上的反转是否仍在」 | 厂商值已就位（`res-vendor-value`）；需一个 GPU 槽 | 标准列 1 档 ≈ 9–10 分钟（m131 实测）+ MultiPL-E 6 格 | 待派（值已就位，等 GPU 与 i02 加档） |
| WP4 规模次序在采样下是否存活 | GPU worker | 同族 ≥3 个规模（例如 Qwen3.5-0.8B/2B/4B）在同一 bench、同一 ctx 下各有 greedy 与一档 temp>0 的格；给出规模对的 win/loss 与次序反转数，且与 WP1 的量化档结论分开报告 | 一个 GPU 槽 + `variant_panel.py` 的 sampling 轴（已在盘上） | ≤40 GPU 分钟（2 个模型 × 2 档 × 4 基准，按 m131 的 9–10 分钟/档估） | 待派（等显存） |
| WP5 独立复核 | fresh-context reviewer（meta 派） | 对本目录三份文档与 `sampling_census.py` 的输出给裁决，指出证据缺口；reviewer 的结论取代本人的自评 | WP1–WP4 | 一次复核 | 待派 |

## plan3 :: 假设 B2（厂商推荐采样）：unsloth 给每个模型发布推荐运行/采样参数，而我们固定协议；做一次受控检查，看厂商推荐采样会不会改变任何量化结论（即我们的协议是否是 confound）。

- author: agent
- scope: general
- status: provisional
- domain: kind: hypothesis
- 当前判定：**输入已就位，测量未跑**。厂商推荐值已逐字取得并存成 `RESULT.md::res-vendor-value`：
  非思考文本任务 `temperature=1.0, top_p=1.00, top_k=20, min_p=0.0, presence_penalty=2.0, repetition_penalty=1.0`。
  它落在本研究测过的**每一个**设置之外（温度 1.0 不在 0/0.3/0.6/0.7 里；`top_p` 1.00 对钉住的 0.95；`min_p` 0.0 对 0.05；`presence_penalty=2.0` 对恒为 0），
  所以已有的五档采样格**代理不了**它——这正是本假设必须真跑一档的理由。
- 取值过程与限制：`huggingface.co` 在本机只解析到 IPv6 且到达不了（`curl` 15 秒超时，exit 28），值是从公共镜像 `hf-mirror.com` 读的，
  原件摘录、字节数与 sha256 存在 `evidence/vendor-card-excerpt-*.md`；因此这是二手证据，只用它取参数值，不拿它证明别的。
- 预期方向（推断，不是结论）：若温度 0.3–1.0 在代码列是一个平台（已测 0.3 与 0.7 在 HumanEval 上给出同一分数 0.5122），
  则厂商档的代码分也在 −10/164 附近；但同一档还改了 `top_p`/`min_p`/`presence_penalty` 三个从未变过的维度，所以这个外推未经验证。

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
