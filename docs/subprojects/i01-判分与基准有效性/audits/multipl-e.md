# MultiPL-E 判分审计（cpp / py / js / java / rs / rb × raw / chat）

审计对象：仓库自研 runner `.wrapup/mpl_run.py`（`gen` 生成并后处理、`eval` 编译执行判分），提示集 `.wrapup/prompts/humaneval-<lang>.jsonl`（带 `SHA256SUMS`）。这补齐 `RESULT.md::res20`（围栏缺陷）、`res21`（缩进签名）先前只在真实数据上测过的部分，并把「坏完成物能否被算成通过」这条方向第一次做成可执行负控。

复现（无 GPU、无模型）：

    python3 "docs/subprojects/i01-判分与基准有效性/audits/multipl_e_audit.py"

方法：从已落盘的 `i01-slot-np1-p1-py-chat` 里取一条**真实判为 OK** 的完成物（`HumanEval_0_has_close_elements`），据此造 9 个判定已知的变体，逐个过真实 `eval` 路径。这样「正确」不是我说的，是这条 cell 自己判过的。

## 结论：MultiPL-E 这一列在什么条件下会失真

| 条件 | 方向 | 实测 |
|---|---|---|
| 完成物带 markdown 围栏，且没有过 `strip_fences` | **向下**（把正确解判成语法错） | 原样围栏 → `status=Exception` 判 fail；过 `strip_fences` 后 → `status=OK` 判 pass；未闭合围栏过 `strip_fences` 也 pass |
| 完成物前面有散文（`Here is the code:` 之类） | **向下** | 过 `strip_fences` 后仍 `Exception`（该函数只剥行首围栏，不剥散文） |
| 函数体首行缩进被抹平（模型行为，见 res21） | **向下** | 去缩进变体 `Exception`；判分器**不会**替模型重排缩进 |
| 空完成物 | 向下 | `Exception` |
| **函数体错误但程序提前退出 0** | **向上** | `pass` + `raise SystemExit(0)` → `status=OK` **判 pass**；对照 `pass` 单独 → `Exception` |
| 整格全是 `Exception` | — | 与「真 0 分」在 `_eval.json` 里只差状态，不差分数；必须记 NULL（res17） |

## 关键结构事实

1. **后处理在生成侧，不在判分侧。** `strip_fences` 只在 `mpl_run.py gen` 里调用；`eval` 读多少个字符就编译多少字符。所以：历史格子的分数取决于**当时那版 `strip_fences`**（res20 的 131→139 就是这么来的），而用今天的 `eval` 重判旧样本并不会补上后处理（这也解释了 res21 里「重判仍是 pass: 0」）。
2. **判分判据是「整个程序退出码 0」。** 数据集测试以 `assert` 形式追加在完成物后面，所以任何让进程提前以 0 退出的完成物都算通过：python `raise SystemExit(0)` / `sys.exit(0)`、js `process.exit(0)`、cpp `exit(0);`、java `System.exit(0);`。本次只对 py 做了实测，其余由同一条判据推出（写在脚本的 `EARLY_EXIT` 里，未逐个实测）。
   - **但它在历史语料里从未发生**：扫描 `.wrapup/mres/*.jsonl` 全部 **68,584** 条落盘完成物（325 个文件），含提前退出构造的条数是 **0**。所以这是**存在但零发生**的通道：现在没有任何已入库分数由它造成，而它一旦发生就是满分白拿。
3. **状态直方图**：`_eval.json` 逐题有 `status ∈ {OK, SyntaxError, Exception, Timeout, HarnessError:...}`；汇总只出现在面板日志的 `recorded <tag> <lang> ... {'OK': n, 'Exception': m}` 行里，`_eval.json` 本身没有直方图字段。所以「这一格到底跑成了没有」只能靠日志或现算。
4. **围栏的实际规模**：68,584 条落盘完成物中 **2,096 条（3.06%）** 含围栏；res20 量到 cpp chat 那一格 72/161 带围栏且 72/161 失败。所以这条缺陷的实际影响集中在 chat 协议的 cpp/qwen 那批格子，而不是全表。

## 四个问题逐条

- **Q1 剥不剥 markdown**：生成侧剥（只剥行首、闭合与否都剥），判分侧不剥。方向与位置都在上表与第 1 条里给出。
- **Q2 保不保缩进**：`strip_fences` 对无围栏完成物只 `rstrip`，不动行内缩进；判分器按 `prompt + completion + tests` 原样编译。所以缩进被保住，也意味着模型写错缩进不会被救回（res21 的结论在这条负控里成立）。
- **Q3 记不记状态直方图**：逐题记、汇总不记（见第 3 条）。
- **Q4 坏完成物能否算成通过**：能，唯一已证通道是提前退出（本次实测 1/1 例），历史发生率为 0（68,584 条里 0 条）。

## 未测（不得当成通过）

1. **cpp / js / java / rs / rb 的提前退出通道未逐个实测**：只测了 py；其余由「退出码 0」这条判据推出。
2. **`SyntaxError` 与 `Exception` 的区分是否可靠**：编译失败记 `SyntaxError`、运行非 0 记 `Exception`，但 `SyntaxError` 也可能是运行时 `SyntaxError`（例如 `eval` 里的语法错），本次未构造该边界。
3. **rs / rb / js / java 的判分器是否存在与 py 不同的失真**（例如 js 里未捕获的 async 异常不改变退出码、rb 的 `at_exit`）：未测。
