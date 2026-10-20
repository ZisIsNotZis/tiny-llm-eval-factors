# BFCL 判分审计（单轮 simple / multiple / parallel / parallel_multiple / irrelevance / live_* + 多轮）

审计对象：**单轮**由本仓库自研判分器 `.wrapup/bfcl_run.py::evaluate`（`call_ok`/`arg_ok`/`parse_prompt_calls`）；**多轮**由 bundled 官方 `multi_turn_checker`（`.wrapup/bfcl_multi_run.py`）。数据集是 bundled `bfcl-eval 2026.3.23`，题目与答案在 `.wrapup/bfclenv/lib/python3.11/site-packages/bfcl_eval/data/`。

复现（无 GPU、无模型、无网络；退出 0 = 每条预期成立）：

    python3 "docs/subprojects/i01-判分与基准有效性/audits/bfcl_audit.py"

## 结论：BFCL 这一列在什么条件下会失真

1. **单轮与多轮不是同一个判分器。** 单轮是自研匹配器，多轮是官方 checker。所以「BFCL 0.6」这类汇总是两个实现、两套口径的混合；单轮分数也不能与公开 BFCL 排行榜对齐比较。方向：不可知（没有任何一次同预测对比），幅度：未测。
2. **`live_relevance` 的判分是「有没有调用」而不是「调得对不对」。** bundled 数据集里没有它的 `possible_answer` 文件（实测 `BFCL_v4_live_relevance.json exists=False`），代码因此写成 `ok = len(calls) > 0`。实测：一个名字根本不存在的函数也会判 PASS。方向：**向上**，幅度：该类别满分（m8 面板里 n=16，占 0.7% 权重）。
3. **聚合口径能把同一个面板变成两个数。** 面板 summary 的 `score` 是**按题加权（micro）**，而库里只有每类别一行的 acc（**按类别平均 macro** 才是那些行的自然聚合）。实测最大差：`m8` 的 gr3b-q2 micro **0.3905** vs macro **0.1877**（差 **0.2028**）；`m4b` 的 2bq3 差 0.0173。原因是最小类别 `live_irrelevance`（884/2251 题，奖励「不调用」）把 micro 抬起来。方向：micro 偏**高**（当大类别是「不做也得分」的类别时）。
4. **库里 123 条 BFCL 行的 `n_items` 全是 NULL**（实测 123/123），所以**从库本身算不出 micro**，只能算 macro；要复现 summary 里的 `score` 必须回到 `.wrapup/m*_summary.jsonl`。这是「同一事实两个家」的现存实例，修法属入库管线（i02）。
5. **匹配器的类型/大小写宽容是单向的**（`arg_ok` 实测）：
   - `arg_ok(10, ["10"]) = True`（数字对上字符串答案）；
   - `arg_ok("10", [10]) = False`（字符串数字对不上数字答案）；
   - `arg_ok(" New York ", ["new york"]) = True`（大小写与首尾空格被折叠）；
   - `arg_ok(True, [1]) = True`（布尔与 1 在 Python 里相等）。
   方向：**向上**且不可忽略——一个把布尔写成 `true`/`1` 混用的模型会在数值型答案上白拿分，一个输出带空格大小写不一致的模型不会被误杀（后者是有意设计）。
6. **多余参数不被检查**：`call_ok` 只遍历标准答案里的键，所以预测里多带一个乱写的参数照样判 PASS（实测）。方向：向上，幅度：对「函数名为对、必需参数全对、但多塞了无意义参数」的完成物整格通过。
7. **多余调用会被判错**（`len(calls) == len(gt)`，实测重复调用判 FAIL），方向向下。`irrelevance` 任何调用都判错（实测），方向正确。

## 四个问题逐条

- **Q1 判分是否后处理**：单轮先把模型输出解析成 `{name, arguments}`（prompt 模式走 `parse_prompt_calls`，会先剥一层 markdown 围栏再取最外层 JSON；tools 模式直接读 `message.tool_calls`），然后只做「函数名相等 + 标准答案里的每个参数取值落在接受列表里」。多轮用官方 checker（最终实例状态 + 执行响应比对）。
- **Q2 逐题状态是否落盘**：`bfcl_run.py eval` 只写 `{n, correct, score, per_category}` 聚合；逐题只有 `*.jsonl` 预测文件（`calls` + `raw` 前 2000 字符）。当前 `.wrapup/bfcl_out/` **是空的**，也没有任何 bfcl 预测文件留存（`find .wrapup -name "*bfcl*"` 只有脚本与目录），所以**历史 BFCL 分数无法重判**——这是本轮最实质的证据缺口。
- **Q3 坏完成物能否被算成通过**：能，两条：`live_relevance` 整类（见上）、多余参数不检查（见上）。另有布尔/数字混用的白拿分。
- **Q4 正确完成物能否被判错**：能——`irrelevance` 之外的类别里，预测比标准答案多一个调用就整格判错；`parallel` 类要求调用数严格相等，模型多调一次即失败。方向向下。

## 未测（不得当成通过）

1. **自研匹配器 vs 官方 AST checker 的一致率**：需要历史预测文件，而它们已被清理。补法：下一次跑 BFCL 时保留预测 jsonl（或用 `--resume` 目录），然后用 `bfcl_eval` 的官方 checker 判同一批预测，给出不一致率。
2. **多轮 checker 的四问**：本轮只覆盖单轮判分器的行为；多轮（`bfcl-multiturn` 22 行）的判定路径（实例状态、执行响应）只从代码读到，未做可执行负控。
3. **`live_relevance` 的白拿满分在历史分数里占多少**：m8 面板该类别 n=16/2251，权重 0.7%；其它面板未逐一统计。
