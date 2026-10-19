# STATUS

路由文件：只记「它是什么、现在什么状态、下一步落在哪」。数值与结论的当前值在 `docs/result/result.yaml`，研究问题与里程碑状态在 `docs/plan/plan.yaml`；本文件不复制它们的值，也不写 `文件:行` 引用（行号随修订漂移）。`::` 后面是节点 id。

## 它是什么

一个可复现的本地语言模型推理因子测量工作台：量化、模型规模、解码协议与基准行为。数据 SSOT 是 `experiments.sqlite`；`report.html` 由 `make_report.py` 从库与评测文件生成、不得手改；方法与协议在 `docs/method/method.yaml`。

## 当前状态

**活跃。** 里程碑 m161 已完成，并在 `3eea78f` 经独立复核判为**接受但带注解**（accept with notes）：复核在 fresh context 中按 `proof.review` 审视结果层与整个 m161 改动集，阻塞的因果归因自相矛盾、无法由命令重现的数字、引用了不存在的测试三项已逐条关闭并各留一条命令，测量层可重现，其余注解为文字性问题、不另立工作项。m161 交付的内容：

- 测量与入库：`docs/result/result.yaml::res24`（重测的 chat 格与端到端控制格）、`::res23`（重复行去重与 `ingest_mpl` 幂等修复）。当前库行数、去重前后的集合差与备份名都在 `res23` 的证据里。
- 报告已由 `make_report.py` 重生成；数据质量节现在从库与 `.wrapup/mres/*_eval.json` 现算（`make_report.py::data_quality_html`），不再带手写数字。

仍开放，均不得记为通过：

1. **MultiPL-E 表渲染重复行未修**：`docs/plan/plan.yaml::plan16`——同一模型的两条协议串渲染成同一个行标签，表格里出现两行同名同值的行；成因是表格行键，不是标签。
2. **MultiPL-E chat 单次值的可复现风险未裁决**：`docs/plan/plan.yaml::plan15`——同一个 cell 的多次记录值、两个候选原因和裁决命令都在该节点。
3. **陈旧脚本根路径未修**：`docs/plan/plan.yaml::plan10`。
4. **硬阻塞实验**（显存不足、架构无法加载）不是缺失也不是 0：`docs/plan/plan.yaml::plan1`。
5. **文档层阻塞（先于 m161 存在，未修）**：证据可恢复性与文档检查受阻都登记在 `docs/plan/plan.yaml::evidence_repair`；`python3 docs/check_docs.py` 目前因共享 schema 缺失而退出，不得记为通过。

## 事实落在哪

1. 当前问题、里程碑与未决项：`docs/plan/plan.yaml`。
2. 当前结论与证据：`docs/result/result.yaml`。
3. 方法/协议：`docs/method/method.yaml`；产品与需求：`docs/product/product.yaml`、`docs/need/`、`docs/pain/`、`docs/architecture/`。
4. 数据：`experiments.sqlite`；报告：`report.html`（生成物，不得手改）；本地产物：`.wrapup/`（不入库，规则见 `README.md` 与 `AGENTS.md`）。

## 下一步

按仓内已写明的顺序：`plan16` 的表格行键修复 → `plan15` 的可复现性裁决 → `plan10` 的脚本根路径修复；`evidence_repair` 的文档检查与证据可恢复性在获得授权后单独处理。
