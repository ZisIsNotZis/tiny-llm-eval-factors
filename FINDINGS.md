# FINDINGS

已确立的结论，每条一行：结论 + 关键数字 + 出处（`文件:行`）+ 状态（成立 / 部分 / 已撤回）。
行号绑定 revision `a2e62fc`。数字均为仓内文档已记录的值，本文件未重算、未做新实验；数据 SSOT 是 `experiments.sqlite`，本文件只搬 `docs/result/result.yaml` 与 `docs/plan/plan.yaml` 的既有记录。
口径纪律：未知 / 阻塞 / 未测必须与 0 或负结果区分（`README.md:14-15`）；下表"部分"多数就是这一类。

## 一、测量结论（`docs/result/result.yaml`，`author: measurement`、`status: current`）

| 结论 | 关键数字 | 出处 | 状态 |
| --- | --- | --- | --- |
| 权重量化位宽：同一家族内从低一档到高一档（典型约 0.8–1.7 比特/权重），7 个标准基准分数普遍上升 | 7 基准 | `docs/result/result.yaml:1` | 成立 |
| 按基准汇总的位宽步长中位数（越大 = 该基准对位宽越敏感） | GSM8K `+0.460`、HumanEval+ `+0.409`、IFEval `+0.250`、MBPP+ `+0.235`、MMLU `+0.146`、ARC-c `+0.100`、TruthfulQA `+0.005` | `docs/result/result.yaml:10` | 成立 |
| 每 +1 比特/权重的分数变化中位数，基准间约 11 倍跨度 | GSM8K `+0.156`、IFEval `+0.117`、HumanEval+ `+0.104`、MBPP+ `+0.065`、MMLU `+0.054`、ARC-c `+0.026`、TruthfulQA `+0.014` | `docs/result/result.yaml:20` | 成立 |
| 家族内配对差（能力型：代码+指令+推理）−（知识型：MMLU+ARC+TruthfulQA）为正，多数家族同向 | `+0.12 / 比特`，95% CI `[+0.04, +0.20]` | `docs/result/result.yaml:30` | 成立 |
| Qwen3.5-2B 多语言代码的有效位宽 → 分数曲线 | `3.27→0.0062`、`3.66→0.1387`、`3.96→0.1894`、`4.11→0.0920`、`4.93→0.2184`、`5.70→0.2836`、`6.24→0.2774` | `docs/result/result.yaml:39` | 成立（`scope: specific`） |
| 模型规模：同配方下参数量越大分数越高，小模型之间差距通常大于大模型之间 | — | `docs/result/result.yaml:48` | 成立 |
| 量化方案比厂商标签重要：文件字节接近时换方案（IQ vs K）有可测差异，换厂商标签测不出 | 方案 `+0.056`，95% CI `[+0.008, +0.104]`；厂商 `+0.009`，95% CI `[−0.058, +0.077]` | `docs/result/result.yaml:56` | 成立 |
| KV 缓存精度：f16 / q8_0 / q4_0 在短上下文下**无可测差异**；长上下文**未覆盖** | 约 1–2k tokens | `docs/result/result.yaml:72` | 部分（短上下文为空结果，长上下文未测） |
| 采样/解码：温度 0→0.3/0.7 压低代码通过率；温度 0 时 top_k 无影响；MMLU 对采样完全无反应（走对数似然） | — | `docs/result/result.yaml:80` | 成立 |
| 投机解码：草稿深度越大越快，分数几乎不变 | 0.8B 约 `+36%`、9B 约 `+93%`；MMLU 在每个深度逐位相同 | `docs/result/result.yaml:88` | 成立 |
| 规模盘点（引用，非测量） | `experiments.sqlite` 约 `3300` 行（已去重）、`208` 个模型文件、`59` 种协议 | `docs/result/result.yaml:120` | 部分（`kind: citation`，随实验推进变化） |

## 二、负结果（看起来合理的设计在这里输了 / 测不出差异）

| 结论 | 关键数字 | 出处 | 状态 |
| --- | --- | --- | --- |
| MoE 逐层比特分配：均匀分配**优于**"专家层压到极低位"，而"比特最多"的配置**最差** | 均匀 `3.88` 比特 → HumanEval+ `0.335` / MMLU `0.447`；专家层 IQ2/Q2、其余高位 `2.92` → `0.287` / `0.427`；专家层 Q4_K、其余 Q2_K `4.48` → `0.134` / `0.287` | `docs/result/result.yaml:64` | 成立（`scope: specific`） |
| QAT 不是量化损失的补救：同标称配方下文件更小，多数 4-bit 档与原生测不出差异，低位宽档明显更低 | 小 `0.36–0.95` 比特/权重；12B 配对 MMLU `−0.197`，95% CI `[−0.242, −0.153]`（该原生档位本身存疑）；约 2-bit 档 QAT 明显更低 | `docs/result/result.yaml:96` | 部分（一个显著项伴随存疑档位） |
| 第三方方案 GSQ-RCO 相对原生阶梯**测不出差异** | 两个档 `3.058` / `3.549` 比特/权重 vs 原生 `2.878` / `3.850` / `4.173`；所有差值 95% CI 跨 0 | `docs/result/result.yaml:104` | 成立（`scope: specific`） |
| **未测不是 0**：三个配置根本没跑出来 | gemma-4-31B QAT/原生档与 gemma-4-26B-A4B 原生档显存不足未测；扩散式解码 DiffusionGemma 本机加载不了该架构、未测 | `docs/result/result.yaml:112` | 部分（明确登记为未测） |
| MultiPL-E 旧列**不可比**：不同模型跑了不同语言子集，把不同测集平均后近零分数是语言覆盖造成的假象；标准列现在只在 cpp 与 py 都测过时产出，否则记 NaN | 例：Qwen3.5-2B-UD-IQ2_XXS 只有 cpp、gemma-4-12b 只有 java/js/rb/rs | `docs/result/result.yaml:192` | 成立 |
| m160 面板 16 个 cell **全部在生成前失败**（提示集 `/tmp/MultiPL-E/prompts` 已被清理），被脚本记成 `CORRUPT ... empty=999`；同批 raw 完成物 151/161 不含 `return`、27/161 只有注释、18/161 带 `<\|channel>` token | 16 cell、`empty=999`、`151/161`、`27/161`、`18/161` | `docs/result/result.yaml:234` | 成立 |
| 生成协议改变 MultiPL-E 分数（同一模型 cpp：raw 纯补全 vs chat 关思考） | raw 约 `0.043` vs chat `0.832`（`m10_summary.jsonl cpp=0.0559` vs `m26_summary.jsonl cpp=0.8323`） | `docs/result/result.yaml:224` | 部分（`status: provisional`，同文件受控复测当时在跑） |

## 三、撤回记录

| 被撤回的说法 | 原因 | 出处 | 状态 |
| --- | --- | --- | --- |
| `res17` 把一批"每道题都是 `Exception`"的格归因为**基础设施整轮报错** | 该归因**已撤回**：真实原因是 `res21` 的缩进破坏；"必须记 null、不得写成 0"这一半仍成立 | `docs/result/result.yaml:214`（`res17b`） | 已撤回（一半） |
| 旧 `strip_fences` 后处理（把 Markdown 代码围栏当语法错误）产出的 chat 分数 | 只在围栏闭合时才剥离，而数据集停止串 `\n}` 通常把完成物切在闭合围栏之前 ⇒ 整格失败。用同一份磁盘完成物只补正确后处理重算：Qwen3.8-27B cpp chat Q2 `0.2174→0.6335`、Q3 `0.4845→0.8571`（py 仅 `+0.0435`/`+0.0497`） | `docs/result/result.yaml:243`（`res20`） | 已撤回（旧分数作废） |
| 旧 `strip_fences` 开头 `text.strip()` 抹掉无围栏完成物的首行缩进 | gemma-4-26B py chat 有 `90/161`（Q2）与 `103/161`（Q3）完成物缩进受损、全部编译后记 `Exception`；对照组 q38-27b-q3-py 仅 `1/161`。成品已落盘，缩进**无法从样本恢复** | `docs/result/result.yaml:254`（`res21`） | 已撤回（该批 py 格作废） |
| m160 的前提"gemma-4-12b 没有任何 cpp/py 数据" | **不成立**：m6b 面板（2026-09-30，从未入库）已有 chat cpp `Q2 4/161=0.0248`、`Q3 130/161=0.8075`；其 py 完成物同样缩进受损、不可用 | `docs/result/result.yaml:264`（`res22`） | 已撤回（前提作废） |

## 四、推断性判断（`author: agent`，`status: provisional`——不是测量结论）

| 结论 | 关键数字 | 出处 | 状态 |
| --- | --- | --- | --- |
| 位宽该选多大取决于家族自己的曲线拐点，多数家族主要抬升在有效位宽约 4–5 比特/权重之间；没有统一档 | granite-4.1-3b 更早（`3.22→0.048`、`4.06→0.391`） | `docs/result/result.yaml:129` | 部分（`provisional`） |
| 判断量化够不够看代码/推理/指令，不要看知识类基准 | 由 `res2`/`res3` 推 | `docs/result/result.yaml:138` | 部分（`provisional`） |
| 小模型做困难多步任务需要更多位宽 | 2B 在低比特时困难 agentic 任务整体触底 | `docs/result/result.yaml:147` | 部分（`provisional`） |
| 同文件大小下比较"方案/字节"比"厂商标签"更重要 | 由 `res7` 推 | `docs/result/result.yaml:156` | 部分（`provisional`） |
| 不要用 PPL 做决策 | PPL 与任务分约 `30%` 情况方向相反 | `docs/result/result.yaml:165` | 部分（`provisional`） |
| 不要指望 QAT 挽回量化损失：它更像"同配方下体积更小"的选项 | 由 `res12` 推 | `docs/result/result.yaml:174` | 部分（`provisional`） |
| 换生成协议后必须重测：协议本身会改变量化结论的符号 | 由 `method.m23` 推 | `docs/result/result.yaml:183` | 部分（`provisional`） |

## 五、未闭合的问题与阻塞（仓内自述）

| 结论 | 关键数字 | 出处 | 状态 |
| --- | --- | --- | --- |
| 硬阻塞实验不是 null 也不是 0 | gemma-4-31B QAT/原生（m142/m143）与 gemma-4-26B-A4B 原生 Q4（m145）权重 `17.3/18.8/17.0 GB`，另一项目在 `:8834` 占约 `6.5 GB` ⇒ `BLOCKED-on-VRAM`；DiffusionGemma-26B-A4B 记 `GATE-FAIL`；APEX 无产物 | `docs/plan/plan.yaml:1` | 部分（阻塞，未测） |
| 研究证据可恢复性待修复：result 的来源仍指向已退役的 `.scratch/originals`，`make_report.py` 依赖 `.wrapup` 与本机路径，README 无可重放的环境入口 | — | `docs/plan/plan.yaml:58` | 部分（未修） |
| 文档检查**受阻，不得记为通过**：`python3 docs/check_docs.py` 实际执行因 `/home/z/vibe/AGENTS.docs.schema.yaml` 缺失退出 `2` | 退出码 `2` | `docs/plan/plan.yaml:58`（`evidence` 字段） | 部分（阻塞） |
| 数据库与报告仍是低报值：m26 两条 chat cpp 行仍是 `0.2174/0.4845`（正确 `0.6335/0.8571`），`report.html` 因此仍印低报值 | `0.2174`、`0.4845` | `docs/plan/plan.yaml:76` | 部分（未修） |
| 陈旧根路径：`.wrapup/` 下 `10+` 个脚本硬编码已不存在的 `/home/z/hf/research`，重跑会在准备阶段静默失败 | `10+` 个脚本 | `docs/plan/plan.yaml:85` | 部分（未修） |
| MultiPL-E 剩余工作：用修好的 harness 重生成 6 个缩进受损的 chat py cell（gemma-4-12b Q2/Q3、gemma-4-26B-A4B Q2/Q3、Qwen3.8-27B Q2/Q3） | 约 `6 × 13` 分钟 GPU；提示集已落 `.wrapup/prompts/`（`6` 个 jsonl，`1.2 MB`，附 `SHA256SUMS`） | `docs/plan/plan.yaml:67` | 部分（进行中，见 `plan11`） |
| m161 里程碑进行中：重测 6 个 chat/py cell + 1 个端到端控制格（q38-27b-q3 cpp chat 应落回 `0.857±0.03`） | 每格 `n=161`；预算 ≤ `2` 小时 GPU | `docs/plan/plan.yaml:94` | 部分（进行中，无结果） |
