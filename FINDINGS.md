# FINDINGS

路由文件：每条结论只写「它是什么 + 事实落在哪个节点 + 当前状态」。数值、证据、置信区间与复算命令都在被指的节点里，本文件不复制，也不写 `文件:行`（行号随修订漂移）。`::` 后面是节点 id，路径给出唯一 home。

口径纪律：未知 / 阻塞 / 未测必须与 0 或负结果区分；下表「部分」多数就是这一类。

## 一、测量结论（`author: measurement`、`kind: measured`/`citation`）

| 结论 | 事实所在 | 状态 |
| --- | --- | --- |
| 权重量化位宽：同一家族内，从低一档到高一档，各标准基准分数普遍上升 | `docs/result/result.yaml::res1` | 成立 |
| 按基准汇总的位宽步长中位数（该基准对位宽有多敏感） | `docs/result/result.yaml::res2` | 成立 |
| 按位宽归一的基准敏感度：每比特/权重的分数变化中位数及其跨度 | `docs/result/result.yaml::res3` | 成立 |
| 家族内配对差（能力型基准 − 知识型基准）为正，多数家族同向 | `docs/result/result.yaml::res4` | 成立 |
| 小模型多语言代码的有效位宽 → 分数曲线（`scope: specific`） | `docs/result/result.yaml::res5` | 成立 |
| 模型规模：同配方下参数量越大分数越高，小模型之间的差距通常更大 | `docs/result/result.yaml::res6` | 成立 |
| 量化方案比厂商标签重要：字节接近时换方案有可测差异，换厂商标签测不出 | `docs/result/result.yaml::res7` | 成立 |
| KV 缓存精度：短上下文无可测差异，长上下文未覆盖 | `docs/result/result.yaml::res9` | 部分（短上下文为空结果，长上下文未测） |
| 采样/解码：温度抬高压低代码通过率；温度为零时 top_k 无影响；MMLU 对采样无反应 | `docs/result/result.yaml::res10` | 成立 |
| 投机解码：草稿深度越大越快，分数几乎不变 | `docs/result/result.yaml::res11` | 成立 |
| 规模盘点（引用，非测量；随实验推进变化） | `docs/result/result.yaml::res15` | 部分（`kind: citation`） |

## 二、负结果（看起来合理的设计在这里输了 / 测不出差异）

| 结论 | 事实所在 | 状态 |
| --- | --- | --- |
| MoE 逐层比特分配：均匀分配优于把专家层压到极低位，「比特最多」的配置最差 | `docs/result/result.yaml::res8` | 成立（`scope: specific`） |
| QAT 不是量化损失的补救：同标称配方下文件更小，多数低位宽档更差 | `docs/result/result.yaml::res12` | 部分（一个显著项伴随存疑档位） |
| 第三方方案 GSQ-RCO 相对原生阶梯测不出差异 | `docs/result/result.yaml::res13` | 成立（`scope: specific`） |
| 未测不是 0：显存不足与架构无法加载的配置登记为未测 | `docs/result/result.yaml::res14` | 部分（明确登记为未测） |
| MultiPL-E 旧列不可比：不同模型跑了不同语言子集，近零分数是语言覆盖造成的假象 | `docs/result/result.yaml::res16` | 成立 |
| m160 面板的格在生成前失败；同批原始完成物显示模型不写函数体 | `docs/result/result.yaml::res19` | 成立 |
| 生成协议改变 MultiPL-E 分数（同一模型 raw 与 chat 差异大） | `docs/result/result.yaml::res18` | 部分（`status: provisional`） |

## 三、撤回记录

| 被撤回的说法 | 事实所在 | 状态 |
| --- | --- | --- |
| 全 `Exception` 的格曾被归因为整轮运行失败，随后又被归因为旧后处理破坏缩进；两种归因都已撤回，成因改为模型把函数体首行写在第 0 列。「必须记缺失、不得写 0」这一半仍成立 | `docs/result/result.yaml::res17b`、`::res17`、`::res24` | 已撤回（两种归因） |
| 旧 `strip_fences` 只在围栏闭合时剥离，把 Markdown 围栏当语法错误；该批 chat 分数作废，只补正确后处理重算 | `docs/result/result.yaml::res20` | 已撤回（旧分数作废） |
| 旧 `strip_fences` 的 `text.strip()` 抹掉无围栏完成物的首行缩进，并因此造成 gemma-4-26B-A4B py 的 `Exception`：观察成立、因果撤回（同一签名在修正 harness 下依然存在） | `docs/result/result.yaml::res21` | 已撤回（因果从句） |
| m160 的前提「12b 没有任何 cpp/py 数据」不成立：m6b 面板已有 chat cpp 数据；同批 py 格因配置不同（ctx=4096、模板未核对）已被 m161 重测取代，不并入 | `docs/result/result.yaml::res22` | 已撤回（前提作废） |

## 四、推断性判断（`author: agent`、`status: provisional`，不是测量结论）

| 结论 | 事实所在 | 状态 |
| --- | --- | --- |
| 位宽该选多大取决于家族自己的曲线拐点，没有统一档 | `docs/result/result.yaml::an1` | 部分（`provisional`） |
| 判断量化够不够看代码/推理/指令，不要看知识类基准 | `docs/result/result.yaml::an2` | 部分（`provisional`） |
| 小模型做困难多步任务需要更多位宽 | `docs/result/result.yaml::an3` | 部分（`provisional`） |
| 同文件大小下比较「方案/字节」比「厂商标签」更重要 | `docs/result/result.yaml::an4` | 部分（`provisional`） |
| 不要用 PPL 做决策 | `docs/result/result.yaml::an5` | 部分（`provisional`） |
| 不要指望 QAT 挽回量化损失：它更像「同配方下体积更小」的选项 | `docs/result/result.yaml::an6` | 部分（`provisional`） |
| 换生成协议后必须重测：协议本身会改变量化结论的符号 | `docs/result/result.yaml::an7` | 部分（`provisional`） |

## 五、未闭合的问题与阻塞

| 结论 | 事实所在 | 状态 |
| --- | --- | --- |
| 硬阻塞实验不是缺失也不是 0：显存不足记 `BLOCKED-on-VRAM`，架构无法加载记 `GATE-FAIL` | `docs/plan/plan.yaml::plan1` | 部分（阻塞，未测） |
| 研究证据可恢复性待修复：result 的来源仍指向已退役的 `.scratch/originals`，`make_report.py` 依赖 `.wrapup` 与本机路径 | `docs/plan/plan.yaml::evidence_repair` | 部分（未修） |
| 文档检查受阻，不得记为通过：`python3 docs/check_docs.py` 因共享 schema 缺失而退出 | `docs/plan/plan.yaml::evidence_repair` | 部分（阻塞） |
| 陈旧根路径：`.wrapup/` 下多个脚本硬编码已不存在的 `/home/z/hf/research`，重跑会在准备阶段静默失败 | `docs/plan/plan.yaml::plan10` | 部分（未修） |
| m161 已完成入库与报告重生成；独立复核尚未执行 | `docs/result/result.yaml::res24`、`docs/plan/plan.yaml::plan14` | 部分（复核未执行） |
| MultiPL-E chat 同一个 cell 的三次记录值不一致，可复现性未裁决：两个候选原因与裁决命令见节点 | `docs/plan/plan.yaml::plan15` | 部分（未裁决） |
