# i02 测量基础设施 — 计划

本文件是 i02 的当前计划：一个里程碑，其下每个工作包给出所有者、验收、依赖、预算和状态。
owner 列写「i02 主控」表示由本子项目自己执行（本子项目在本轮没有可用的运行时递归工具，见工作包 wp11）；
写「meta→reviewer」表示需要 meta 派独立复核者。

## 里程碑 M1 :: 研究结束 — 测量基础设施可被外人独立复现与审计

达成条件（全部为真才算达成；每条后面的括号是它现在由哪条事实证明）：

1. ✅ 干净 clone 后一条命令 `./reproduce.sh` 从库与仓库内输入重建 `report.html`，与已提交的 `report.html` 逐字节相同（`RESULT.md::res24`）；
2. ✅ `migrate_db.py` 连跑两次插入 0 行，`PRAGMA integrity_check` ok，`checks/db_check.py` 绿（`RESULT.md::res31`、`RESULT.md::res23`）；
3. ✅ 提示集与其 SHA256 可在干净 clone 内一条命令核对（`RESULT.md::res26`）；
4. ✅ 非测量（`BLOCKED-on-VRAM` / `GATE-FAIL`）在报告里与 0 分开可见，且每条有证据（`RESULT.md::res14`）；
5. ✅ MultiPL-E 表无同名同值的重复行，行键与显示标签一一对应（`RESULT.md::res28`）；
6. ✅ `.wrapup/` 里可执行脚本不再硬编码已退役的绝对根路径（`RESULT.md::res27`）；
7. ✅ 文档检查不再是阻断：`docs@1` 标准有了仓库内的家，`docs/check_docs.py` 以 0 通过并有负控（`RESULT.md::res32`）。

## AC 状态（子项目登记表里那一行，逐条对到事实）

| # | 登记表里的 AC | 状态 | 证明 | 复算命令 |
|---|---|---|---|---|
| 1 | 干净 clone 一条命令复现报告与数据 | 完成 | `RESULT.md::res24` | `git clone <repo> x && cd x && ./reproduce.sh` |
| 2 | DB 幂等，完整性检查绿 | 完成 | `RESULT.md::res31`、`RESULT.md::res23` | `python3 migrate_db.py` 连跑两次；`python3 checks/db_check.py` |
| 3 | 提示集 / 哈希可查 | 完成 | `RESULT.md::res26` | `cd .wrapup/prompts && sha256sum -c SHA256SUMS` |
| 4 | 表格行键与陈旧根路径修完 | 完成 | `RESULT.md::res28`（行键）、`RESULT.md::res27`（根路径） | `python3 checks/report_check.py`；`python3 checks/stale_roots.py` |
| 5 | docs 检查：解决或显式阻塞 | 完成（已解决，不是阻塞） | `RESULT.md::res32` | `python3 docs/check_docs.py`；`python3 checks/docs_schema_negative_control.py` |

另有两项由本子项目负责、也已落地，但不在登记表那一行里：报告的「未测 ≠ 0」与两列不池化（`RESULT.md::res29`、`RESULT.md::res30`）、未解问题派生索引（`RESULT.md::res33`）。

## 工作包

### wp1 :: 文档层 SSOT（PLAN / RESULT / AGENTS，yaml 迁移后删除）

- owner: i02 主控
- AC: 三份 Markdown 存在；`plan.yaml`、`result.yaml` 已删除且其节点在新文件里；`make_report.py::load_docs` 读 Markdown 后报告可构建，未决问题段非空。
- deps: 无
- budget: 1 次提交，无外部算力
- 状态: 完成

### wp2 :: 干净 clone 一条命令复现报告

- owner: i02 主控
- AC: 在 `git clone` 出的空树里执行 `./reproduce.sh` 退出 0，且 `report.html` 与已提交版本逐字节相同；任何输入缺失时报错并点名缺失文件，不降级为 0。
- deps: wp4（非测量登记册）、wp6（提示集哈希）
- budget: CPU 1 核 ×2 分钟量级（报告构建实测 33 s），本机内存
- 状态: 完成

### wp3 :: 数据库迁移幂等与检查

- owner: i02 主控
- AC: `python3 migrate_db.py` 连跑两次第二次 `rows N -> N` 且插入 0；`checks/db_check.py` 报 ok；每次变更前自动产生 `experiments.sqlite.bakN`。
- deps: 无
- budget: 每条验证在库副本上进行，不占 GPU
- 状态: 完成

### wp4 :: 非测量登记册

- owner: i02 主控
- AC: `non_measurements.tsv` 列出每个未测格与状态、原因、证据、对应事实；报告把它渲染成独立登记表，并与「未测 ≠ 0」的说明相邻；登记册缺失时报告构建失败而不是渲染 0。
- deps: 无
- budget: 无外部算力
- 状态: 完成

### wp5 :: 提示集与哈希可查

- owner: i02 主控
- AC: 干净 clone 内 `sha256sum -c .wrapup/prompts/SHA256SUMS` 通过，且该核对已接进 `reproduce.sh`；RESULT 记下提示集清单与来源。
- deps: wp2
- budget: 无
- 状态: 完成

### wp6 :: 陈旧根路径

- owner: i02 主控
- AC: `python3 checks/stale_roots.py` 绿；每个被改脚本 `bash -n` / `python3 -m py_compile` 通过；历史记录类文件（`*.log`、`*.txt`、`*.json`）不改写并在检查里声明豁免。
- deps: 无
- budget: 无
- 状态: 完成

### wp7 :: MultiPL-E 表行键

- owner: i02 主控
- AC: 同一模型的行标签唯一；同标签多协议在数值完全一致时合并为一行、不一致时报错；逐语言计数不变；报告重新生成。
- deps: wp1
- budget: 无
- 状态: 完成

### wp8 :: 文档检查的阻断状态

- owner: i02 主控
- AC: `python3 docs/check_docs.py` 在新目录布局（`docs/subprojects/*/`）下运行，集合级不变量真跑并通过；缺失的 `docs@1` 标准以退出码 2 点名确切的缺失路径；该阻断写入 RESULT 并说明需要谁的授权。
- deps: wp1
- budget: 无
- 状态: 完成

### wp9 :: 证据可恢复性（origin 与 README 环境入口）

- owner: i02 主控
- AC: 本子项目的事实不再以已退役的 `.scratch/originals` 作为来源；README 给出一条可重放的命令、其实测耗时和它不能重建的东西。
- deps: wp2
- budget: 无
- 状态: 完成

### wp10 :: 规模数字复核

- owner: i02 主控
- AC: RESULT 里的库规模数字由一条只读查询当场重算，与记录的数值一致。
- deps: 无
- budget: 无
- 状态: 完成

### wp12 :: 多语言代码列拆成 C++ / Python（禁止跨语言池化）

- owner: i02 主控（语义由 a12 定，代码与报告一致性归本条）
- AC: `.wrapup/mktables.py::BENCH` / `query_cells_by` 产出两个独立列，`make_report.py` 的标签同步，标准表多一列、轴 A/B/C 图各多一条 series；任何一列的值等于其语言子集自身的聚合，cpp 与 py 不被加权成任何单一数值；分协议规则不变（仍只取 canonical 协议，不混协议）；单语言只有格的模型另一列为空且渲染 `-`。
- 证据: 重新生成 `report.html`，逐格核对 192 个 MultiPL-E 格与新列一一对应；复算命令 `python3 checks/report_check.py`。
- deps: wp7（同一段代码，行键一并修）
- budget: 无外部算力，报告重建一次
- 状态: 完成

### wp13 :: 报告的「未解问题」改由派生索引提供（替代原来的「统一 Markdown 事实形状」）

- owner: i02 主控（决定由 meta 作出：报告不解析子项目 Markdown）
- AC: `report_inputs/build_open_questions.py` 扫 `docs/subprojects/*/PLAN.md` 的「未解问题」一节生成 `report_inputs/open_questions.json`，每条带子项目 id 与来源路径，没有这一节的文件被跳过并计数，连跑两次字节相同；报告据它渲染「未解问题」节；`make_report.py` 不再解析任何子项目 Markdown 事实。
- deps: 无
- budget: 无外部算力，报告重建一次
- 状态: 完成

### wp11 :: 独立复核与落地

- owner: meta→reviewer
- AC: 一个全新上下文的 reviewer 对 M1 的七条达成条件逐条给出 verdict；本条完成前 M1 不得宣称达成。
- deps: wp1–wp13
- budget: 一轮复核
- 状态: 待派（阻断项：本子项目运行时没有可用的递归派工工具，无法自行派出 reviewer）

## 未解问题

- 独立复核未派：i02 侧没有待做的工作包了，`wp11` 的 reviewer 由 meta 派出（owner: meta）；在它的增量结论回来之前 i02 不再开新工作。
- `m31` 的 `top_k` 扫描把 K=1（贪心地板）与 K=200（不截断）写进同一条协议串，库内没有列区分（owner: 入库侧，非 i02 工作包）——报告已把两个值都印出并写明取用规则。
- 长上下文的 KV 精度结论只覆盖短上下文（owner: a05，非 i02 工作包）；i02 只保证「未测 ≠ 0」在报告里可见。

## 当前在做什么 / 下一步（接手先读这一节）

- 已完成（最近提交 `0b68086`）：kv 那条假 WARN 已清（不可得 ≠ 过期，带负控）；`open_questions` 跟上 a11；
  a14 的 py 语料取代入库（**11 行** `corpus=` + 11 个 `superseded_by` 指针，按活库身份认行，
  `checks/py_corpus_regrade_check.py` 逐行核对 PASS、旧记录 0 行丢失）；`mres/%` 宽前缀删除收窄
  （`checks/mres_prefix_delete_negative_control.py`：探针行跑两次仍在、924 行一条不丢）；
  `superseded_by` 列 + 悬空指针断言 + 两条负控（指针、报告过滤）；报告 §13 有语料代次表注。
- **未做，按优先级**：
  1. **第二个 P1（比 mres 那条更隐蔽）**：refresh 会改写别人修正过的行——14 行 BFCL 多轮格的
     `n_items` 被抹回 NULL（a13 从官方 ledger 回填的）、32 行 `variant-*` 协议串被追加
     `;sampling=default`（把「没记录采样」写成「采样=默认」，属编造）。改前状态在
     `experiments.sqlite.bak30`。要做的：每个 ingester 只改 `(run_tag, source_file)` 自身前缀内的行；
     `n_items`/`protocol` 只能「读现值，为空才补写」并记 ledger；回填那 14 + 32 行；负控造三行分属
     三个 ingester 的行，跑两次 refresh 断言逐字未变。
  2. **py 取代的收尾**：38 条 skip ledger 逐格原因已给出，但 §13 只按总数给了语料代次表注，
     未逐格标注；`a14` 的 27 个 py `testfrac` 值尚未随二元列换到同一代（`evidence/py_testfrac_regrade.json`），
     这是「两列各说一代」的口子；§15 的绝对水平中位 +0.027 与 7 对近差翻转的文字也未改。
  3. `a07`（spec-decode 是否逐字节同贪心）/`a08`（thinking 开关是另一协议）/`a11`（扩散：`未测` + 门槛 + 价格，不写 0）落地时接报告。
- 阻塞/风险：报告只依赖库 + `report_inputs/*` 派生索引；索引落后于子项目产物时 `reproduce.sh` 报 WARN，
  必须显式重建。工作树里的 `experiments.sqlite` 常有别的子项目未提交的写入，所以 `report.html`
  一律在 HEAD 的干净 clone 里重建再拷回，避免把未提交的库改动烤进报告。
  当下 `reproduce.sh` 在本机工作树里还有 2 条 WARN（size_claims / open_questions，都因别的子项目正在改它们的事实源）。

## 读法：还剩哪些、当前在哪、下一个派给谁

- 还剩：只有 `wp11`（独立复核，owner: meta）。
- 当前：`wp1`–`wp10`、`wp12`、`wp13` 全部完成；M1 七条达成条件都已为真；`AC 状态` 一节逐条对到事实。
- 下一个派给：meta 派 reviewer 对 `9a80742` 之后的增量做结论；i02 在这之前不开新工作包。
- 明确没做到、也不由 i02 做的（照实记）：其他子项目 89 条事实的来源仍是已退役的 `.scratch/originals`（`RESULT.md::res35` 有清点命令），报告层面已停止把它们当来源引用，迁移归各自持有层。
