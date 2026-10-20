# i02 测量基础设施 — 本子项目的规则

本文件只写本子项目给派工对象的窄规则。仓库级规则（数据信任顺序、数据库安全、研究执行）以根 `AGENTS.md` 为准，不在此复述。

## 你在这个子项目里要守的

1. **可复现优先**：任何结论/修复的完成证据是「干净 clone 里跑得通的那条命令 + 它的输出」，不是一段说明。命令没跑过就写「未验证」。
2. **数字只有一个来源**：报告与事实文件里的每个数都由 `experiments.sqlite` 的只读查询或 `checks/` 里的检查产出。不许手抄数字，不许为了过检查改测量值。
3. **缺席不是 0**：没有测量就没有数据。输入缺失时构建必须失败并点名缺失文件，不得渲染成 0 或后退成另一个数。
4. **`report.html` 只生成不手改**：改 `make_report.py` / `.wrapup/mktables.py` 后重新生成并提交，报告差异要能解释到单元格。
5. **数据库变更**：先 `cp` 出下一个未占用的编号备份（`migrate_db.py` 已自动做），再变更，再跑 `PRAGMA integrity_check` 与 `python3 checks/db_check.py`。`migrate_db.py` 是唯一入库路径，幂等性用连跑两次证明。
6. **行键带全部区分列**：表格行的键必须包含所有参与区分的列字段，显示标签才可以省掉不参与区分的部分。同一标签下数值不一致时报错，不静默取一个。

## 事实文件格式

`PLAN.md` / `RESULT.md` 里每条事实的标题是 `## <id> :: <一行事实>`，其下 bullet 给坐标（`kind` / `status` / `from` / `evidence` / `producer`）。
`make_report.py::load_docs` 用这个格式，所以 ` :: ` 是唯一分隔符，事实只写一行；不带 ` :: ` 的 `##` 标题是普通小节，不进报告。

## 检查与它们各自能证明什么

| 命令 | 证明 |
|---|---|
| `./reproduce.sh` | 干净 clone 里一条命令重建报告并逐步核对（依赖、提示集哈希、报告输入、DB、根路径、文档、报告字节） |
| `python3 checks/db_check.py` | 库完整、外键无冲突、强制字段与取值域无违规、无重复身份组 |
| `python3 checks/report_check.py` | 生成的 `report.html` 无重复行标签、无「输入缺失却渲染 0」、非测量登记册在场 |
| `python3 checks/stale_roots.py` | 可执行脚本不含退役绝对根路径（`--fix` 是幂等迁移） |
| `python3 docs/check_docs.py` | 文档集合级不变量；schema 标准缺失时以退出码 2 点名缺失路径 |

## 边界

- 只写本子项目的 `docs/subprojects/i02-测量基础设施/`，以及仓库级的复现设施（`reproduce.sh`、`checks/`、`report_inputs/`、`make_report.py`、`.wrapup/mktables.py`、`migrate_db.py`、`docs/check_docs.py`、`README.md`）。
- 不改其他子项目的目录，不改 `docs/plan/subprojects.md`。
- 本机唯一的 `experiments.sqlite` 不做破坏性操作；需要写库时在副本上先验证。
