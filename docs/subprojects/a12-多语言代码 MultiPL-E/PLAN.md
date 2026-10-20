# a12 多语言代码 MultiPL-E — 计划

计划层的唯一 home。目标 / 用途 / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a12 行定义，本文件不复述；本文件只写里程碑、工作包、状态与派工。

## 里程碑：研究结束

- 终点状态：a12 的 AC 全部有可复算证据，未测的格都带着理由登记，报告里的每个 model×language 格都能追到落盘产物。
- done 判据：`python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"` 退出 0（谱系、全 Exception 检查、提示集哈希、报告格入库检查四项全绿），且 RESULT.md 的覆盖表把每个空格归入「已测」或「显式未测 + 理由」。
- 只有这一个里程碑：它是用户同步点，之前不再切分。

## 当前状态

- 已完成：`WP1`、`WP2`、`WP3`、`WP4`（`WP4` 的语言池化一项待裁决，见「待裁决」）。
- 在办：无。本子项目当前不持有 GPU，也不持有任何后台任务。
- 下一个派给谁：`WP5`（补测两格）需要一个持 GPU 的 worker，由 meta 派；`WP6`（独立复核）需要一个 fresh-context reviewer，由 meta 派。

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | a12 编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 存在；迁移后的 `result.yaml` 已删除；每条事实带证据与复算命令；提交在 main | — | 1 会话 | 完成 |
| WP2 单元格谱系审计 | a12 编排者 | `mpl_cell_audit.py` 对库中 248 个格给出「已评分 244 全部追溯、0 未追溯、无全 Exception 格带分数」，退出 0 | WP1 | 0.5 CPU 时 | 完成 |
| WP3 覆盖缺口登记 | a12 编排者 | 54 个模型 × 6 语言的矩阵、4 个 NULL 格、未测格的理由全部写进 `RESULT.md` | WP2 | 0.5 CPU 时 | 完成 |
| WP4 协议 / 语言受控审计 | a12 编排者（语言池化的改法落在报告代码，需 meta 裁决） | 报告的逐语言表行键 =(模型, 协议) 有代码与数据证据；标准列只取 canonical raw-greedy 协议；cpp+py 均值与两语言各自排序的不一致率有具体数 | WP2 | 0.5 CPU 时 | 完成，一项待裁决 |
| WP5 补测 gemma-4-12b 的 chat cpp 两格 | GPU worker（meta 派） | Q2/Q3 两格以 `mpl-chat-nothink-greedy-768`（`ctx=2048`、`--jinja`）入库并留下 `_eval.json`；审计仍退出 0；12b 首次有同协议 cpp+py 对 | 一个 GPU 槽（`bash .wrapup/gpu_locked.sh`）；提示集用 `.wrapup/prompts` 不许重生成 | ≤15 GPU 分钟（m161 实测 7 格 39 分钟） | 待派 |
| WP6 独立复核 | fresh-context reviewer（meta 派） | 对本目录三份文档与审计输出给裁决，指出证据缺口；reviewer 的结论取代本人的自评 | WP1–WP4 | 一次复核 | 待派（本会话没有派孙工具） |

## 待裁决（meta）

**标准列的「多语言代码」格是 cpp+py 的加权均值，这是跨语言池化，与 a12 AC「标准列不跨语言或协议池化」字面冲突。**
证据与选项：

- 现状：`mktables.py::load_standard` 只取 `protocol='multipl-e-raw-greedy-768'`，所以不混协议；随后 `query_cells_by` 用 `CANON_MPL=("cpp","py")` 按题量加权求均值，得到一个「多语言代码」格，喂给轴 A/B/C 的标准表（当前 41 行有值）。
- 危害已测：51 个同时有 cpp+py 的模型里，两语言各自的排序在 566/1275 对模型上不一致；py−cpp 差值从 −0.2671 到 +0.1863，中位数 +0.0186（`RESULT.md`「两语言分歧」）。
- 选项 A（推荐）：把标准列的「多语言代码」拆成 C++ / Python 两列，报告轴 A/B/C 各多一列、各多一条曲线；代价是表变宽、图多一条 series，好处是无池化且不丢数据。
- 选项 B：标准列只留 Python 一列，语言结论回到逐语言表；代价是丢掉 cpp 这一维。
- 选项 C：保留均值，在表头与图注标明「固定语言对均值，语言结论只取第十三节」；代价是仍与 AC 字面冲突，只是把冲突写清楚。

改法落在 `make_report.py` / `.wrapup/mktables.py`（i02 的报告代码），不在 a12 目录内，所以我不擅自改；meta 裁决后由 i02 或 meta 派的工作包执行，a12 只提供证据与复核。

## 非目标

- 不为 js / java / rs / rb 补 chat 协议格：那是 4 语言 × 6 模型的 24 格，超出 9% GPU 份额，且这几个语言的判分有效性还没有 i01 的审计。
- 不改 m30-kv-ctx 的 6 个 0.0 格：它们属于 a05 的 KV 轴，改值会改 a05 的结论；a12 只登记缺陷（`RESULT.md`「8 个 0.0 格」）。
- 不改其他子项目目录、不改 `docs/plan/subprojects.md`、不重跑历史面板的旧后处理分数。
- 不重生成提示集：`.wrapup/prompts` 与 `SHA256SUMS` 是唯一来源。

## 已记录的判断（本会话自行决定）

- 补测先做 gemma-4-12b 的 chat cpp 两格，而不是先补语言维度：它把 12b 从「任何协议下都没有 cpp+py 对」变成「同一协议下有对」，是覆盖表里唯一能用一个协议内的两格填补的模型。
- 谱系审计的判据写成「panel summary 命中，或按 (语言, 通过数, 题数) 命中的 per-item eval 文件」，因为有两格的库值是修正后处理重判出来的（summary 里留的是旧判分值），把 eval 文件当第二等证据而不是降级。
- 报告里的 4 处引用（`docs/result/result.yaml::res5/res17b/res22/res24`）指向 meta 迁移后已不存在的路径，属报告代码的死引用；a12 不改报告代码，登记给 meta（见 `RESULT.md`「迁移到 Markdown 的后果与死引用」）。

## 派工与资源

- GPU：占 4 周周期的 9%，全局串行，任何 GPU 任务必须在 `bash .wrapup/gpu_locked.sh` 下跑，一次一个。
- CPU：5%；本目录的审计脚本只读数据库，秒级。
- 任何入库走 `migrate_db.py`，改库前做编号备份，改完跑完整性与洁净检查（见 `AGENTS.md`）。
