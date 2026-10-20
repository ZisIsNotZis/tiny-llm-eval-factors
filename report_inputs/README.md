# report_inputs — 报告在数据库之外的输入

这个目录归 i02（测量基础设施），装着 `make_report.py` 除 `experiments.sqlite` 之外要读的东西，
以及把其中派生那一份重新生成出来的脚本。它们必须随仓库分发，因为干净 clone 用不上本机的运行产物。

| 文件 | 是什么 | 来源 |
|---|---|---|
| `eval_status.json` | 每份逐题评测（`.wrapup/mres/*_eval.json`）的文件名、语言、题数、通过数与状态直方图 | 由 `build_eval_status.py` 抽取；源文件体积大可重生成，不入 git |
| `build_eval_status.py` | 上面那份的生成器；`--check` 与现有落盘产物比对，不一致就报错 | — |
| `eval_status.py` | 唯一的读取口：`records()` 与 `n_for(lang, score, hints)`；题量取不到时返回 `None` | — |

规矩：

1. 输入缺失时报告构建必须失败并点名缺失文件，不得渲染成 0，也不得退回默认值。
2. 题量（格子里括号中的数）只能来自该格自己的产物；`n_for` 用产物文件名里的 facet（`ctx…`、`kv…`）
   消歧，定不下来就打印「题量未知」。
3. 重新生成后必须重建报告并提交两者，否则报告与输入会脱节（`./reproduce.sh` 会 warn）。
