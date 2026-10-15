# 数据质量审计（本轮，工作记录 / 非 SSOT）

本轮针对“12B 附近分数崩溃”“规模越大越差”“0 到底是真 0 还是报错”做了一次对账。
结论已写入 docs/result/result.yaml（res16–res18）与 docs/plan/plan.yaml（plan8），报告“数据质量、可比性与待分析”节逐条呈现。

## 已确诊并已修

1. **MultiPL-E 旧列不可比**：每个模型只跑了不同语言子集（Qwen3.5-2B-IQ2_XXS 只有 cpp；gemma-4-12b 只有 java/js/rb/rs）。
   `mktables.query_cells_by` 现在只在 **cpp 与 py 都在**时产出 MultiPL-E 单元，否则缺失（NaN，不画）。within-model 轴（KV/sampling）保留“跑了什么平均什么”，因为语言集恒定。
2. **基础设施失败 = 0 的缺陷**：9 个 `mres/*_eval.json` 每道题都是 Exception 却记 0；对应 10 行 `_score` 已置 NULL（备份 `experiments.sqlite.bak37`，integrity_check ok）。
   典型：gemma-4-26B-A4B py（chat 协议 161/161 Exception），同模型 cpp=0.832。
3. **raw vs chat 协议**：gemma-4-26B-A4B cpp，raw≈0.043 vs chat 0.832。raw 对 gemma 系列是 harness floor，不是模型能力。
4. **家族曲线不再混供应商**：A 轴按 `family + scheme_class(UD 动态 / 原生 K / QAT)` 拆系列；Qwen3.6-35B-A3B 的 UD-Q3_K_XL(3.88) 与 bartowski 原生 Q3_K_M(3.86) 已分开，后者单点被规则剔除，对比移到轴 C。

## 修复的根因（防止复发）

- `migrate_db.ingest_mpl` 只写 score、不写状态直方图 → 无法区分异常与真 0。**待办：让 mpl_run/eval 在 summary 里写 `statuses`，ingest 对“全 Exception”写 NULL。**
- MultiPL-E 提示集在 `/tmp` 易失。已用 `nuprl/MultiPL-E` 的 cpp/java/js/rs/rb parquet + `openai/openai_humaneval`（py，取与 cpp 相同的 161 题子集）重建到 `/tmp/MultiPL-E/prompts`。**待办：把重建脚本固化进仓库（如 `.wrapup/build_mpl_prompts.py`），并在启动任一 MultiPL-E 面板前校验存在。**

## 运行中

- `m160`（`.wrapup/run_m160_protocol.sh`）：gemma-4-12b Q2/Q3、gemma-4-26B-A4B Q3、Qwen3.8-27B Q3，cpp+py，raw vs chat。
  - 目的：量化协议效应，并验证重建的提示集（Qwen3.8-27B Q3 的 chat cpp/py 应与 m26 的 0.484/0.814 一致，作为重建正确性的对照）。

## 待分析（本轮新增，尚未跑）

- **协议效应全量**：只测了 4 个模型；需要覆盖 granite/llama/phi/gemma-E 以判断哪些模型的 raw MultiPL-E 不可用。
- **语言子研究**：java/js/rs/rb 面板（m38/m42/m51/m54/m56/m57/m60）尚未进入报告；应作为独立“语言×模型”研究，而不是并进 MultiPL-E 标准列。
- **BFCL 工具调用全量**：m4/m4b/m7/m8（单轮四类）与 m9/m11–m20/m32/m36（多轮）尚未进入报告；BACKLOG B3 要求扩到 granite/gemma/MoE 锚点。
- **重复性 w1/w2**：m1 有重复测量，可算方差；报告误差棒目前只有题目级 SE，没有 run-to-run。
- **厂商推荐采样（B2）**：固定协议是否 confound。
- **长上下文 KV（E 的缺口）**：m30 只到 ctx 但 prompt ~1k；真正的长上下文 KV 影响仍未测。

## 追加（本轮后半）

5. **报告新增两节研究**：
   - 十三、多语言代码（MultiPL-E）：逐语言 × 生成协议。热力图行 = (模型, 协议)，避免把 raw/chat 混成一行；空白 = 未测。
   - 十四、工具调用（BFCL）：协议 × 类别。同一模型下“提示式工具调用 vs 原生 tools”分数差常大于模型间差距。
   - 十五、部分给分（每测试通过比例，m41）。用于区分三元量化“错得更多”还是“错得不一样”。
6. **修复 m41 的模型身份缺陷**：`migrate_db.ingest_m41` 原来把 ternary 全写成 `Ternary-Bonsai-27B`、conventional 全写成 `TODO.gguf`。已加 `_m41_model()`，从样本文件名经各面板 model map 解析真实 gguf；重灌 24 行，`TODO.gguf` 归零，integrity ok（备份 `experiments.sqlite.bak38`）。
7. **新增文档事实**：result.res16–res18、plan.plan8；`docs/check_docs.py` PASS。

## 仍待办
- m160 结果回来后：把协议效应写成定量结论，并决定是否将 MultiPL-E 标准列改为 chat 协议（或双协议并列）。
- fa-probe（m44）只有 3 题，功率过低，暂不进报告；testfrac 的 n=161 可用。
- w1/w2 重复性方差、长上下文 KV、BFCL 多轮扩测仍未做。
