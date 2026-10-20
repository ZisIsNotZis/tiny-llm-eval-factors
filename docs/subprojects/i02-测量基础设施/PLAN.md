# i02 测量基础设施 — 计划

本文件是 i02 的当前计划：一个里程碑，其下每个工作包给出所有者、验收、依赖、预算和状态。
owner 列写「i02 主控」表示由本子项目自己执行（本子项目在本轮没有可用的运行时递归工具，见工作包 wp11）；
写「meta→reviewer」表示需要 meta 派独立复核者。

## 里程碑 M1 :: 研究结束 — 测量基础设施可被外人独立复现与审计

达成条件（全部为真才算达成）：

1. 干净 clone 后一条命令 `./reproduce.sh` 从库与仓库内输入重建 `report.html`，与已提交的 `report.html` 逐字节相同；
2. `migrate_db.py` 连跑两次插入 0 行，`PRAGMA integrity_check` ok，`checks/db_check.py` 绿；
3. 提示集与其 SHA256 可在干净 clone 内一条命令核对；
4. 非测量（`BLOCKED-on-VRAM` / `GATE-FAIL` / `NOT-RUN`）在报告里与 0 分开可见，且每条有证据；
5. MultiPL-E 表无同名同值的重复行，行键与显示标签一一对应；
6. `.wrapup/` 里可执行脚本不再硬编码已退役的绝对根路径；
7. 文档检查的阻断状态被记录或解除，并点名缺失的确切文件。

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

- 独立复核未派：本子项目运行时没有递归派工工具，`wp11` 的 reviewer 要由 meta 派出；在此之前 M1 不得宣称达成。
- `m31` 的 `top_k` 扫描把 K=1（贪心地板）与 K=200（不截断）写进同一条协议串，库内没有列区分——报告已把两个值都印出，但处置归入库侧（协议串应带上实际 top_k）。
- 长上下文的 KV 精度结论只覆盖短上下文，长上下文仍属未测；它由 a05 拥有，本子项目只保证「未测 ≠ 0」在报告里可见。

## 读法：还剩哪些、当前在哪、下一个派给谁

- 还剩：wp13（格式裁决，meta 所有）、wp11（独立复核）。
- 当前：wp1–wp10、wp12 已完成；等 wp13 的裁决与 wp11 的独立复核。
- 下一个派给：meta 派 reviewer 复核 wp1–wp10、wp12 与 M1 七条；wp13 由 meta 裁决。
