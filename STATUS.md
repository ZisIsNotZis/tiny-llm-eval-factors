# STATUS

路由文件：只记「它是什么、现在什么状态、下一步落在哪」。数值与结论的当前值在各自的子项目节点里（`docs/plan/subprojects.md` 的单元表指向每个单元的 `RESULT.md`）；本文件不复制它们的值，也不写 `文件:行` 引用（行号随修订漂移）。`::` 后面是节点 id。

## 它是什么

一个可复现的本地语言模型推理因子测量工作台：量化、模型规模、解码协议与基准行为。数据 SSOT 是 `experiments.sqlite`；`report.html` 由 `make_report.py` 从库与入库派生索引生成、不得手改；方法与协议在 `docs/method/method.yaml`。

## 当前状态

**研究里程碑已达成**（`c19c168`：十六个单元全部结项，21 节 / 86 图）。判据是能跑的命令，不是这句话：`./reproduce.sh` 在 `c19c168` 上 exit 0、2 分 07 秒，`report.html`（sha256 `ce4e7cb0…`）从库重建后逐字节相同；逐行结论由该命令当场产生，本文件不复写那份计数。

**里程碑 `entry` 已在结果 revision `3287b76` 上达成**：四轮独立复核，前三轮判「不接受」、第四轮判**接受**（P1 = 0；判词与每轮的修法见 `docs/plan/subprojects.md` 的 `entry` 节末）。工作包与验收写在 `docs/plan/subprojects.md::entry`：研究交付物已经能被一条命令重建，但读者进入仓库的那两道门（本文件与 `FINDINGS.md`）没有跟着那次文档搬迁改建，42 条节点引用里只有 1 条解析得到。它在本次推进里被修掉的部分：

1. 两份根路由不再指向已退役的按层 yaml 文件；`FINDINGS.md` 的每行指到它现在真正住在哪个子项目节点。
2. 这件事不再靠人记得：`python3 checks/router_refs.py` 解析三份根路由里的每条节点引用与每个文档路径，`checks/router_refs_negative_control.py`（二十一条期望）证明它会红，`./reproduce.sh` 把这一对按 `PASS`/`FAIL` 接进来了。
3. 根目录没有未归类路径：运行日志按类忽略，**被点名的**聚合产物与运行日志入库（`.log` 以 `.gz` 入库），`git status --porcelain` 无输出。判据是「被点名」而不是「体积小」或「被某条 ignore 规则命中」：`python3 checks/evidence_logs.py` 逐条判每条被点名的 `.wrapup/…` 路径有没有处置，`checks/evidence_logs_negative_control.py` 证明它会红（真树绿、干净 clone 报 BLOCKED；换字节数、从索引里拿掉、落在未声明的类下、被模式或目录点名却没入库、空扫描各自红），`./reproduce.sh` 把这一对也按 `PASS`/`FAIL` 接进来了。第二轮的教训是「被点名的证据都以能打开的形式随仓库走」这句当时为假：`STATUS.md` 与 `README.md` 现在只断言已被 `checks/evidence_logs.py` 逐条核到的那些，不再声称一份不缺。
4. **输入漂移不再只记 WARN**（`p-entry2` 已结项，`14ea373`）：13 条判断收进 `checks/report_inputs_drift.py`，漂移=FAIL、缺席=SKIP，`python3 checks/report_inputs_drift_negative_control.py` exit 0 证明改坏一个输入会让 `./reproduce.sh` 非零退出并点名它。

仍开放，均不得记为通过：

1. **三类未测不是 0**：`BLOCKED-on-VRAM`（已定价、未买）、`GATE-FAIL`（本环境缺运行时）、「本环境不可测」；入口 `docs/subprojects/i02-测量基础设施/RESULT.md::res72`。
2. **已记录的两条测量限制**（属 i02 的验收边界，不是缺陷待办）：表格行键容纳不下 `top_k`（`docs/subprojects/i02-测量基础设施/RESULT.md::res41`）、审计只能证明值在面板多重集里而非逐格归属。

## 事实落在哪

1. 研究单元的划分、goal / AC / 资源、里程碑与工作包：`docs/plan/subprojects.md`。
2. 每个单元的当前结论、证据与复现命令：`docs/subprojects/<id>-<name>/RESULT.md`；未解问题在同一个目录的 `PLAN.md`。
3. 方法 / 协议：`docs/method/method.yaml`；产品与需求：`docs/product/product.yaml`、`docs/need/`、`docs/pain/`、`docs/architecture/`。
4. 数据：`experiments.sqlite`；报告：`report.html`（生成物，不得手改）；本地产物：`.wrapup/`（入库判据见 `README.md`）。
5. 基础设施检查：`checks/`（`checks/README.md` 逐条说明每个脚本证明什么、谁调它，`checks/*.py` 一个不漏）；一条命令核全部：`./reproduce.sh`。

## 下一步

`entry` 的七个工作包全部结项（`r-entry1`–`r-entry4`、`p-entry1`–`p-entry3`），里程碑复核已在 `3287b76` 上通过（第四轮判接受）。每条 AC 的命令、捕获输出与产物 sha256 由 `docs/plan/subprojects.md` 的 `entry` 节末表格点名到文件；本节不复写那份计数。

**仓库里没有在跑的里程碑。** 剩下的是三类未测（见上「仍开放」）与研究工作本身的下一个方向——决定它需要用户判断，因为那是要买 VRAM 还是换题目的事，不在本文件里替它定。

未测项按 `docs/plan/subprojects.md` 的三类读法对待，不并入本文件的「当前状态」。
