# 方法论审计：报告里哪些对比根本不成立

> 本轮只做审计（brainstorm），不研究、不改报告。所有结论附可复核证据。

## A. 数据管道：最致命的是“标准表混了协议”

1. **`mktables.load_standard()` 不按 `protocol` 过滤。**
   where = `(source_file LIKE 'mres/%' AND reasoning<>'on') OR (humaneval-multipl-e AND protocol='multipl-e-raw-greedy-768')`。
   它会把 `variant-kv-*`、`variant-sampling-*`、`spec-mtp-*` 行也纳入；`query_cells_by` 用 dict 存 cell，**后写覆盖先写**，所以同一列不同行可能来自不同协议、不同题量。
   - 证据：`Qwen3.5-2B-UD-Q3_K_XL` 的 gsm8k：canonical `lmeval-0.4.13-chat-reasoning-off` = **0.65 (n=100)**；`variant-kv-*` = 0.60–0.68 **(n=50)**。报告表 A/B 显示的是 0.60 —— 即用了 variant 行。
   - 证据：24 个 (model, bench) 在 `load_standard` 下有 >1 个不同协议。
   - 后果：gsm8k/ifeval 混 n=50 与 n=100；mmlu 混 n=456 与 n=912；humaneval 混 spec 与 canonical。**题量不同的列不可比**，误差棒也失去意义。
   **这是必须先修的 bug，不是“解释”能解决的。**

2. **重复行**：同一 (model, bench, protocol, language) 出现多次——全库 383–501 组，`mres` 内 114 组。ingest 非幂等（DATABASE.md 已记）。均值不变，但计数/覆盖/“最后一写获胜”都会偏。

3. **MultiPL-E 无 n_items**：324 行 n_items 全 NULL，误差棒用假定 161。语言集/协议不可比（已修一半，协议仍 raw/chat 混存在 DB）。

4. **基建失败曾被记 0**（9 个 eval，10 行，已置 NULL）；**m41 模型身份曾丢失**（TODO.gguf，已修）。

## B. 变量混淆：很多“X”其实混了不止一个变量

1. **轴 A（有效位宽）**：x 是 bpw，但同一家族阶梯同时是**方案阶梯**（IQ2_XXS→IQ2_M→IQ3_XXS→Q2_K_XL→…）。bpw 与 scheme 混淆。
   - 反向证据（bpw 升高、分数下降 >0.03）：Qwen3.5-2B 3.96→4.11 在 gsm8k/he+/ifeval/multipl_e 同时反向；Qwen3.8-27B 2.88→3.85 在 he+/ifeval 反向；Qwen3.6-35B-A3B 2.83→3.88 反向。**共 13 处**。
2. **轴 C（方案/厂商）**：`MATCH_BPW=0.45`，但实际“匹配组”跨度最大 **0.84 bpw**（`Qwen3.5-2B @ 3.27–4.11`，含 IQ2_XXS/IQ2_M/IQ3_XXS/Q2_K_XL）。
   - 所以 C 表里 “Q2_K_XL vs IQ3_XXS” **本质就是 bpw 对比**，不是方案对比；res7 的“同大小下方案 +0.056”因此不成立。
   - “厂商标签测不出差异”只有 **1 个模型对**（Qwen3.6 UD-Q3_K_XL vs bartowski Q3_K_M），不足以一般化。
   - 真正的方案对比应是：**同标称档、同 bpw、只换方案**（如 UD-Q3_K_XL vs 原生 Q3_K_M；IQ3_XXS vs Q3_K_XL 在 3.96 vs ~4.0）。
3. **轴 D（MoE 专家量化）**：三条配方总 bpw = **2.92 / 3.88 / 4.48**，全不同 → 与 bpw 混淆；每配方 1 个模型 1 次。结论“保护非专家层”方向合理但**未被受控实验支持**（需要：固定总 bpw，只移动比特分配）。
4. **轴 B（规模）**：把 `gemma-4 E2B / E4B / 12B / 26B-A4B` 当一条 size 阶梯，但它们**架构不同**（E 系列 / dense 12B / MoE A4B）。证据：`gemma-4 @ Q2_K_XL` mmlu：E4B **0.650** > 12b **0.370**；gsm8k E4B 0.84 > 12b 0.65；he+ E4B 0.695 > 12b 0.506。
5. **QAT**：QAT 是 Q4_0 系列，原生是 K 系列 → 与“方案”混淆（报告已注，但结论仍写成 QAT 效应）。
6. **GSQ-RCO**：与“按位宽插值后的原生”比是建模假设，不是实测对照。
7. **轴 H（思考开关）**：on 用 max_tokens=4096，off 用 768/1024 → **预算混淆**，不能归因于“思考”。
8. **轴 G（投机解码）**：速度用 MTP repo 文件，质量用普通文件 → 文件不同；且速度有 `m28-mtp-speed-greedy`、`speed-greedy-256-tps`、`spec-mtp-*` 多协议。
9. **轴 E（KV）**：ctx 编码在 protocol 字符串里；prompt 仅 ~1k token；长上下文未测。
10. **轴 F（采样）**：温度点在不同位宽模型上不齐（4.11 有 0/0.3/0.6；4.93 有 0.3/0.6/0.7），跨模型不可比。

## C. 异常 / 非单调曲线（应单独画，不应混入曲线）

**gemma-4-12B 是系统异常**：在不同配方下，MMLU/TruthfulQA 都明显低于同族更小的 E4B。
- Q2_K_XL mmlu：E2B 0.475 / E4B 0.650 / **12b 0.370** / 26B-A4B 0.643
- Q4_K_XL mmlu：E2B 0.578 / E4B 0.702 / **12b 0.644**
- it-qat Q4 mmlu：E4B 0.715 / **12B 0.446** / 26B-A4B 0.711
→ gemma-4-12B 应**单独成图/单独系列**，并怀疑是 base 版本/模板/harness 问题，而不是“规模效应”。

其它 reversal（>0.03）：
- Qwen3.8-27B he+ 2.88(0.896)→3.85(0.835)；ifeval 2.88(0.83)→3.85(0.75)
- Qwen3.6-35B-A3B(UD) he+ 2.83(0.909)→3.88(0.878)
- gemma-4-E4B gsm8k 4.88(0.86)→5.45(0.82)
- Ternary-Bonsai 4B→8B he+ 0.78→0.732
- Qwen3.5-0.8B truthfulqa 4.44→5.23 反向
- granite-4.1-3b truthfulqa 4.06→4.94 反向

## D. 统计与不确定性

1. 误差棒只有**题目级二项 SE**，假设 i.i.d.；无 run-to-run / seed 方差（w1/w2 有重复但未纳入）。
2. MultiPL-E 跨语言池化时把语言当独立样本，SE 偏小。
3. 多重比较（几十个配对）**无校正**。
4. res7 的“合并 +0.056”是跨不同模型/不同位宽带的简单合并，不是混合效应模型 → 不能当“方案效应”。
5. **选择偏差**：模型是按“手头有哪个文件”选的，不是抽样；不同 family 的基准覆盖不同（有的只有 5/10 列，missing 不是随机）。

## E. 结论与证据不匹配

- “同大小下方案有差（+0.056，IQ>K）”：建立在 C 的宽匹配带 → **不成立**。
- “同大小下换厂商标签测不出”：n=1 模型对。
- “MoE 保护非专家层”：bpw 未控。
- “3–4 比特拐点”：是所选文件的产物（混方案），不是干净阈值。
- “规模越大越好”：被 gemma 架构混淆与 12B 异常破坏。
- “QAT 不伤质量”：格式（Q4_0 vs K）混淆。

## F. 呈现问题

1. 曲线是“家族内多点连线”，但多点跨方案/协议/题量。
2. 热力图/表格未标 cell 的协议、题量 n、run 数。
3. 误差棒未标来源（题目级还是 run 级）。

## G. 该怎么重做（brainstorm，未实施）

1. **先修 `load_standard`**：按白名单 protocol 过滤（canonical 每基准一条），并去重；题量不一致的列要么拆开、要么禁止合并。
2. **轴 A 重绘**：x 仍可用 bpw，但**同一条线只能同方案**；或改 x = 标称档位、颜色 = 方案。异常点（12B 等）单独标注。
3. **轴 C 真正做“方案对比”**：构造 (模型, 档位近似, IQ vs K) 的**同 bpw 配对**，配对差 + 区间；厂商标签只在同模型同日发布时比。
4. **轴 D 真正做“分配对比”**：需要**固定总 bpw** 的配方（如让 exq2/exq4 与 baseline 同 bpw），否则删掉该结论。
5. **轴 B 按架构分层**：dense 一图，MoE 一图，E 系列一图；12B 单独。
6. **每张图/表加协议与 n 标注**；误差棒区分题目级与 run 级。
7. **异常点先解释再绘图**：所有 reversal 要么给出机制，要么单独标记，不连线。
