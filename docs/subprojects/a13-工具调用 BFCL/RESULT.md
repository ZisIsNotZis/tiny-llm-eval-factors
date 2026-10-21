# a13 工具调用 BFCL — 结果

每条事实一行一个陈述；数字后面必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回。
**本轴不产出 BFCL 总分**：任何跨协议、跨类别的单一数字都不成立（见 res1、res10）。下文所有数字都带协议串与类别，命令里可见。
下文的 `sqlite3 -readonly` 全部只读，不改库。

## 结论层（读者只需要这三句；细节与证据在下面的 res 条目里）

**一、单轮（native-tools 与 prompt 两个协议分别说，不池化）。** 换成官方 AST checker 后 11 个单轮类别里 8 个整体上移、2 个翻转 0（`irrelevance` / `live_irrelevance`）、1 个只差 1 题且方向向下（`live_relevance`，−0.0625），中位幅度 `multiple` +0.325、`simple_python` +0.278、`live_multiple` +0.148、`parallel_multiple` +0.145、`parallel` +0.105、`live_simple` +0.105，各列极差 +0.004 到 +0.351；22,644 题里 2,788 题由判错改判对、35 题反向。**所以：模型之间的排序大体保留（11 个模型 5 个 non-live 类别合并只有 4/55 对逆序），但任何绝对分数与任何 0.05 以内的邻近间距都不可沿用**——旧数字是自研匹配器的缺陷产物，`RESULT.md::res13` 已按撤回处理。（`RESULT.md::res11`、`res13`）

**二、多轮（`bfcl-official-multiturn-temp0`）。** 库内 24 行多轮只支持**组内**比较，因为 handler 决定 prompt 模板与响应解析，而每个族、甚至每个 Qwen 尺寸都跑在不同 handler 下：只有 4 组组内可比（`Qwen3-1.7B-FC`：2B-q2/q3 + Bonsai；`Qwen3-4B-Instruct-2507-FC`：4B-q2/q3；`Qwen3-8B-FC`：9B-q2/q3；`Qwen3-30B-A3B-Instruct-2507-FC`：35B-A3B-q2/q3），granite-4.1-3b 用 `granite-4.0-350m` 的模板单独一组、**没有任何对照**；gemma 族多轮 0 行，补它**只能补覆盖、补不了可比**。跨族多轮结论（「谁的函数调用更强」）目前**没有证据**；要拿到证据必须做 2 模型 × 2 handler 的受控对，**已定价、未测：4 臂 × 200 题 ≈ 50 GPU 分钟**（`RESULT.md::res12`、`PLAN.md` 的 WP4）。

**三、这次换判分器具体改变了哪些判断（读者层面，不只是数字）。**
- **5 个 non-live 类别合并的第一名换人**：旧 Bonsai-q2g64 0.7053 vs gemma-4-E4B-Q3 0.7028（差 0.0025）；新 gemma-4-E4B-Q3 0.8908 vs Bonsai 0.8808（差 0.0100，反向）。所以「三值 Bonsai 是这批里最好的工具调用模型」这句话**不再成立**，改成「gemma-4-E4B-Q3 略高，与 Bonsai 差距 0.01，在判分器更换的噪声范围内不可分」。
- **`parallel_multiple` 的第一名同样翻转**：Bonsai → gemma-4-E4B-Q3（旧 Δ +0.035 给 Bonsai，新 Δ −0.010 给 gemma）。
- **`simple_python` 上「大模型更好」被推翻**：旧 Qwen3.5-4B-Q3 0.66 > gemma-4-E2B-Q3 0.5975、Qwen4B-Q3 0.66 > gemma-4-E4B-Q3 0.62；新 gemma-E2B-Q3 0.9125 > Qwen4B-Q3 0.89、gemma-E4B-Q3 0.915 > 0.89。**2B 级的 gemma 在这个类别上反超 4B 级的 Qwen**，差 0.022–0.11。
- **不变的两条**（可以继续引用）：granite-4.1-3b 的 Q3 远远好于 Q2（旧 0.5798 vs 0.2024，新 0.7710 vs 0.2065）；`irrelevance` 上 granite-Q2 的异常高分 0.9875 判分器无关（0 翻转），所以它不是判分产物。
- **§14 的聚合口径结论不受影响**：同一格 m8-gr3b-q2 的 micro/macro 差旧 0.2028（0.3905 vs 0.1877）、新 0.2059（0.3954 vs 0.1894）——换判分器几乎不动这个差，所以「BFCL 没有唯一总分」这条继续成立。
- **给报告文本的两条输入**（`make_report.py` 不归我改，只报事实）：(a) §14 现在写的「micro 不可从库复算」**已过时**——`n_items` 回填后 micro 可从库算，实测 gemma-4-E4B-Q3 的 5 类 micro=0.8944（`SELECT _score,n_items ... WHERE protocol LIKE '%official-ast-checker'` 加权）；(b) §14 表里现在的数值已经是官方 checker 的值，行标签带 `...-official-ast-checker`，prompt 协议那 4 个模型仍是 `...-homegrown-matcher`，两者不可混算。

## 数据形状

### res1 BFCL 的 123 行是四个测量，不是一列

- 库侧分布：`bfcl` / `bfcl-native-tools-nothink-greedy` = 79 行、11 模型；`bfcl` / `bfcl-prompt-nothink-greedy` = 20 行、4 模型；`bfcl-multiturn` / `bfcl-official-multiturn-temp0` = 22 行、10 模型；`bfcl-multiturn` / `bfcl-official-multiturn-temp0-partial` = 2 行、1 模型。
- 单轮 11 个模型里只有 4 个（Qwen3.5-2B 的 q2/q3、Qwen3.5-4B 的 q2/q3）同时有 native-tools 与 prompt 两个协议；其余 7 个只有 native-tools。
- 证据：`experiments.sqlite`。
- 复现：`sqlite3 -readonly -header -column experiments.sqlite "SELECT bench_family, protocol, count(*) rows, count(n_items) n_notnull, count(DISTINCT model) models FROM experiments WHERE bench_family LIKE 'bfcl%' GROUP BY bench_family, protocol ORDER BY 1,2"`（实跑输出即上表四行）。
- 状态：current。

### res2 `n_items` 的 15 个 NULL 全是多轮行（已回填 14 行：单轮 5 + 多轮 9）

- 回填前：`bfcl%` 共 29 个 NULL = 多轮 24 行 + Bonsai 单轮 5 行。回填后：**15 个，全部是多轮行**；单轮 NULL = 0。
- 多轮那 9 行之所以能回填，是因为它们的 run 恰好是所在 (handler, 类别) 的**最后一次**（见 res4）；其余 15 行留 NULL 的原因写在 res4 里，不是「忘了填」。
- 每次入库前都做了编号备份（`experiments.sqlite.bak41` 我手动、`bak20/21/22/23` 由 `migrations/backfill_n_items.py` 自建），跑完 `PRAGMA integrity_check` = `ok`，第二次 `--dry-run` 可解析 0 行（幂等）。
- 证据：`experiments.sqlite`。
- 复现：`python3 migrations/backfill_n_items.py --dry-run --family bfcl-multiturn`（实跑：`resolvable: 0  仍留 NULL: 15`）；`sqlite3 -readonly experiments.sqlite "SELECT bench_family, count(*) FROM experiments WHERE bench_family LIKE 'bfcl%' AND n_items IS NULL GROUP BY 1"`（实跑：`bfcl-multiturn|15`）。
- 状态：current。

## 多轮的题量与聚合

### res3 多轮四个类别各 200 题，所以多轮内部「按类别平均」与「按题加权」是同一个数

- bundled 数据集逐类计数：`multi_turn_base` / `multi_turn_long_context` / `multi_turn_miss_func` / `multi_turn_miss_param` 各 **200** 行；官方运行台账亦记 `total_count = 200`（实测一行 `{"accuracy": 0.7, "correct_count": 140, "total_count": 200}`）。
- 推论（这一步是算术，不是新测量）：当每个类别题量相同，类别等权的 macro 与题量加权的 micro 相等。所以多轮的四类别组合**有唯一值**——但它只对「四个类别都跑过」的模型存在，即 `Qwen3.5-2B-UD-Q2_K_XL` 与 `...Q3_K_XL`（各 4 类）；Bonsai 只有 3 类（base + miss_func + miss_param），Qwen3.5-4B 只有 2 类，9B / 35B-A3B / granite 只有 base。
- 与 i01 `res27`/`res30` 的关系：i01 判「micro 与 macro 差到 0.2028、库算不出 micro」是在**单轮混合面板**上成立的（`live_irrelevance` 884 题等权重极不均）；多轮这一侧题量是齐的，口径差异消失。两句不矛盾，但也不能互相引用。
- 证据：`data/BFCL_v4_multi_turn_*.json`（bundled 数据集）、`score/<handler>/multi_turn/BFCL_v4_<cat>_score.json`（官方运行台账）。
- 复现：`cd .wrapup/bfclenv/lib/python3.11/site-packages/bfcl_eval/data && for c in multi_turn_base multi_turn_long_context multi_turn_miss_func multi_turn_miss_param; do printf "%-28s %s\n" "$c" "$(python3 -c "print(sum(1 for l in open('BFCL_v4_$c.json') if l.strip()))")"; done`（实跑输出四行 `200`）；台账：`cd .wrapup/bfclenv/lib/python3.11/site-packages && python3 -c "import json; rows=[json.loads(l) for l in open('score/Qwen_Qwen3-1.7B-FC/multi_turn/BFCL_v4_multi_turn_base_score.json') if l.strip()]; print(len(rows), rows[0])"`（实跑 `61 {...}`，第一行的 `total_count` 就是 200）。
- 状态：current。

### res4 多轮台账只保留每个 (handler, 类别) 的最后一次运行 —— 题量只能对最后一次溯源

- `score/<handler>/multi_turn/BFCL_v4_<category>_score.json` 的结构是**一次运行一个文件**：首行 `{accuracy, correct_count, total_count}`，之后**每个判错题一行**逐题记录（`{id, model_name, test_category, valid, error, prompt, model_result, inference_log, possible_answer}`）。实测 `Qwen_Qwen3-1.7B-FC` 的 `multi_turn_base` 文件共 **61 行 = 1 行汇总 + 60 行判错题**，而该次 `accuracy=0.7, correct_count=140, total_count=200`，`200-140=60` 正好对上。
- 所以同一 handler + 类别的下一次运行会**覆盖**上一次：这个目录不是追加日志，是「最后一次运行」的快照。同 handler 跨模型复用（2B 与 Bonsai 都用 `Qwen/Qwen3-1.7B-FC`）时，早先那次多轮的逐题与汇总都不在盘上了。
- 后果（可回填的边界）：`n_items` 能溯源到 `total_count` 的只有「其 run 恰好是该 (handler, 类别) 最后一次」的行，实测 **9 行**（6 行靠台账、3 行靠 `m32`/`m36` 汇总自带的 `n`）；其余 **15 行**留 NULL，原因写定并逐行可查：台账里没有匹配该 (handler, 类别, accuracy) 的行。
- 对 i01 的关系：i01 「多轮题量推不出自任何运行产物」对那 15 行仍然成立；但「推不出」的范围是**被覆盖过的 run**，不是所有多轮 run。
- 证据：`score/*/multi_turn/*_score.json`、`.wrapup/m32_summary.jsonl`、`.wrapup/m36_summary.jsonl`、`migrations/backfill_n_items.py` 的 `multiturn_ledger_n()`。
- 复现：`python3 -c "import json; rows=[json.loads(l) for l in open('.wrapup/bfclenv/lib/python3.11/site-packages/score/Qwen_Qwen3-1.7B-FC/multi_turn/BFCL_v4_multi_turn_base_score.json') if l.strip()]; print(len(rows), rows[0], sum(1 for r in rows if 'id' in r))"`（实跑 `61 {'accuracy': 0.7, ...} 60`）；溯源表：`python3 migrations/backfill_n_items.py --dry-run --family bfcl-multiturn --trace /tmp/n.tsv`。
- 状态：current。

## 判分器：单轮预测文件其实还在（i01 的缺口可以补）

### res5 单轮 15 个 cell 的预测文件存活，因此「自研 vs 官方一致率」是可测的

- `.wrapup/mres/m4-*.jsonl` 11 个文件（`2bq2 2bq3 e2b-q2 e2b-q3 e4b-q2 e4b-q3 gr3b-q2 gr3b-q3 q2 q3` + `m22-bonsai`），每个 **1240** 条，覆盖 `simple_python:400 multiple:200 parallel:200 parallel_multiple:200 irrelevance:240`。
- `.wrapup/mres/m8-*.jsonl` 4 个文件（`qwen2b-q2 qwen2b-q3 gr3b-q2 gr3b-q3`），每个 **2251** 条，覆盖 `live_simple:258 live_multiple:1053 live_parallel:16 live_parallel_multiple:24 live_irrelevance:884 live_relevance:16`。
- 每条记录形如 `{"id","category","calls","raw"}`，正是 `bfcl_run.py eval` 的输入，所以**每个 cell 的自研分数都能原样重算**，也能喂给官方 AST checker 重判。
- 对 i01 `res27`/`Q3` 的修正：i01 写「`.wrapup/bfcl_out` 为空、没有任何 bfcl 预测文件留存、历史分数无法重判」，其检索式是 `find .wrapup -name "*bfcl*"`，只匹配到脚本与目录；预测文件按 panel 命名为 `m4-*`/`m8-*`，被漏检。**一致率未测的原因是检索式太窄，不是文件不存在。** 本条不修改 i01 的目录。
- prompt 协议（20 行）没有对应的预测文件，那 4 个模型的 prompt 侧仍无法重判。
- 证据：`.wrapup/mres/m4-*.jsonl`、`.wrapup/mres/m8-*.jsonl`。
- 复现：`cd /home/z/vibe/local_lm_research/.wrapup/mres && for f in *.jsonl; do head -1 "$f" | grep -q '"calls"' && echo "$f $(wc -l < "$f")"; done`（实跑输出 15 行，行数为 1240 或 2251）。
- 状态：current。

### res6 单轮的 irrlevance / live_relevance 两类在任何判分器下都不可重判

- `irrelevance` 与 `live_irrelevance`、`live_relevance` 三类在 bundled `possible_answer/` 里**没有**文件，所以官方 AST checker 没有可用的标准答案；`bfcl_run.py` 因此把 `live_relevance` 判成 `len(calls) > 0`（i01 `res27` 已实测一个不存在的函数名也 PASS）。这三类只能用各自的内建规则判，两套判分器在此不可对照。
- 证据：`possible_answer/` 目录清单、`.wrapup/bfcl_run.py::evaluate`。
- 复现：`ls .wrapup/bfclenv/lib/python3.11/site-packages/bfcl_eval/data/possible_answer/ | grep -E "irrelevance|relevance"`（实跑输出：无匹配）。
- 状态：current。

## 协议：多轮那一列的混杂比「两套判分器」更多

### res7 多轮的 `ctx_size` 逐 panel 不同，所以同一 (模型, 类别) 的多行是不同测量

- 多轮行的 `ctx_size` 在 98304 / 131072 / 196608 三档之间分布（m9/m11/m32/m36 = 98304，m14/m17/m18/m20/m22 = 131072，m15/m19 = 196608）。
- `Qwen3.5-2B-UD-Q3_K_XL` 的 `multi_turn_long_context` 有 4 行：m12 `0.135`（ctx 98304）、m13 `0.105`（131072）、m15 `0.095`（196608）、m19 `0.11`（196608）。前三行之间差值是**改了 ctx**；m15 与 m19 同为 196608 却差 `0.015`（= 3/200 题），这一个差**未解释**，可能是同配置重复的抖动，也可能是另一处未记录的输入差——`WP4` 要把它测掉。
- 推论：把 4 行当「同一格的 4 次重复」算方差是错的，其中 3 行不是重复。
- 证据：`experiments.sqlite`（`ctx_size` 列）、`.wrapup/m{12,13,15,19}_summary.jsonl`。
- 复现：`sqlite3 -readonly -header -column experiments.sqlite "SELECT model,_bench,_score,ctx_size,run_tag FROM experiments WHERE bench_family LIKE 'bfcl%' AND (n_items IS NULL OR _bench LIKE '%long_context%') ORDER BY model,_bench"`。
- 状态：current。

### res8 多轮的 handler 逐族、甚至族内逐尺寸都不同 —— 跨模型多轮比较混着「模型」与「模板」

- 官方 handler（决定多轮 prompt 的格式化与响应解析）：`Qwen3.5-2B` → `Qwen/Qwen3-1.7B-FC`；`Qwen3.5-4B` → `Qwen/Qwen3-4B-Instruct-2507-FC`；`Qwen3.5-9B` → `Qwen/Qwen3-8B-FC`；`Qwen3.6-35B-A3B` → `Qwen/Qwen3-30B-A3B-Instruct-2507-FC`；`granite-4.1-3b` → `ibm-granite/granite-4.0-350m`（用 350M 的模板跑 3B 模型）；`Ternary-Bonsai-27B` → 借 `Qwen/Qwen3-1.7B-FC`。
- 生成侧的 tokenizer 路径对所有族都是 `/home/z/hf/qwen_tok`（`run_m9_panel.sh:10` 的 `TOK=`）。
- 后果：`bfcl-official-multiturn-temp0` 这一列里，「跨族差」与「模板差」在同一个自变量位置上，**族间排序不能读成能力差**；同 handler 内的比较（例如 2B-q2 vs 2B-q3、Bonsai vs Qwen2B）才是受控的。
- 证据：`run_m9_panel.sh`（第 10 行与 `--model "$handler"`）、`.wrapup/m{9,11,14,17,18,20,22,36}_summary.jsonl` 的 `handler` 字段。
- 复现：`grep -h '"handler"' .wrapup/m{9,11,14,17,18,20,22,36}_summary.jsonl | python3 -c "import sys,json; [print(json.loads(l)['model'], json.loads(l)['handler']) for l in sys.stdin]"`；`sed -n '10p;105,108p' .wrapup/run_m9_panel.sh`。
- 状态：current。

### res9 `plan4` 的真实缺口是 gemma 族，不是「多轮只跑过一个锚点」

- 多轮已有 10 个模型：Qwen3.5-2B(q2,q3)、4B(q2,q3)、9B(q2,q3)、Qwen3.6-35B-A3B(q2,q3)、Ternary-Bonsai-27B、granite-4.1-3b——即 5 个族里 4 个有数。
- **gemma-4 族多轮 0 行**，而单轮 20 行齐全（E2B/E4B × q2/q3 × 5 类）。
- 类别覆盖：`multi_turn_base` = 9 个模型；`multi_turn_long_context` = 3 个（2B q2/q3、4B q2/q3 计 4 个模型名）；`miss_func` / `miss_param` = 各 3 个（2B q2/q3、Bonsai）。没有任何模型同时有 4 类以外的完整覆盖。
- 所以 `plan4` 可以不做「扩到 granite/MoE」（已有），只剩 gemma 一族；但 res8 说跨族比较已经被模板混杂，必须用**同 handler 的受控对**而不是再添一个不同 handler 的行。
- 证据：`experiments.sqlite` 的多轮行清单。
- 复现：`sqlite3 -readonly experiments.sqlite "SELECT model, count(*), group_concat(_bench,'|') FROM experiments WHERE bench_family LIKE 'bfcl-multiturn%' GROUP BY model"`（实跑输出 10 个模型，无 gemma）。
- 状态：current。

### res10 官方 `data_overall.csv` 是官方口径的部分聚合，不能当「BFCL 总分」用

- 官方写出的 `score/data_overall.csv` 里 `Overall Acc` 一列有值（实跑快照 `Qwen3-1.7B (FC) = 13.20%`），但同一行的 `Non-Live AST Acc` 全是 `N/A`——因为我们跑的是官方 CLI 的多轮类别，非官方 CLI 的单轮类别没跑过。`data_multi_turn.csv` 里的 `Multi Turn Overall Acc` 同样把 `N/A` 的类别按已跑类别平均（`Qwen3-1.7B (FC) = 44.00%` 是 base/miss_func/miss_param/long_context 四类的等权平均）。
- 所以这个 CSV **既不是我们的单轮列，也不是完整 BFCL**；它在报告里只能作为「官方口径的部分聚合」引用，不能替换 `report.html` 的 BFCL 表，也不能与本轴任何单轮数字相减。
- 证据：`.wrapup/bfclenv/lib/python3.11/site-packages/score/data_overall.csv`、`data_multi_turn.csv`。
- 复现：`cat .wrapup/bfclenv/lib/python3.11/site-packages/score/data_multi_turn.csv`。
- 状态：current。

## 单轮换官方 checker：60 个可比格全部上行，排序基本不变但距离全变

### res11 单轮 8 个类别的已报数字全部是**偏低**的，中位差 +0.10 到 +0.33

- 同一批预测（15 个 cell、22,644 条）分别判两次：自研 `.wrapup/bfcl_run.py` 的 `call_ok`/`arg_ok`（生产函数，import 不重写）与 bundled 官方 `ast_checker`；`irrelevance` 三类走 `eval_runner.py::_evaluate_single_relevance_entry` 的存在性判据（不需要 `possible_answer`），所以 **79 个 (文件, 类别) 格全部可判**。
- 逐条翻转 **35 上行**（自研 PASS→官方 FAIL）对 **2788 下行**（自研 FAIL→官方 PASS）。上行 35 条的构成：`type_error:nested` 25、`parallel_function_checker_no_order:cannot_find_match` 5、`simple_function_checker:unexpected_param` 4、存在性判据 1 —— 这就是 i01 说的「多余参数不检查」通道的真实体量：**4 条**。
- 按类别（11 或 4 个 cell 的极差 / 中位）：

| 类别 | cell 数 | 中位差 | 最大差 |
|---|---|---|---|
| simple_python | 11 | +0.2775 | +0.3150 |
| multiple | 11 | +0.3250 | +0.3500 |
| parallel | 11 | +0.1050 | +0.1400 |
| parallel_multiple | 11 | +0.1450 | +0.1900 |
| live_simple | 4 | +0.1434 | +0.2752 |
| live_multiple | 4 | +0.2251 | +0.3514 |
| live_parallel | 4 | +0.0625 | +0.2500 |
| live_parallel_multiple | 4 | +0.0417 | +0.2500 |

- **机制（这才是要改的东西）**：2788 条下行里 **2534 条是 `missing_optional`**——`possible_answer` 把可选参数的接受列表写成 `["units", ""]`（`""` = 可省略，官方 checker 因此只检查 `required`），而自研 `call_ok` 对 gt 里**每个**键都要求预测里存在（`if k not in pargs: return False`），于是「正确但省略可选参数」被判错。剩下 **254 条是 `value_or_type`**（官方按函数声明做类型检查、自研用 `norm()` 做松比较）。**call_count 与 wrong_name 的贡献为 0**。
- **方向修正 i01 的叙述**：i01 `res27` 实测的宽容通道（`arg_ok(10,["10"])`、`arg_ok(True,[1])`、多余参数不检查）真实存在，但它们的总量是 **34 条**；同一个匹配器的「可选参数必须出现」这条**严格**通道是 **2534 条**。所以净效应是自研**系统性低估**，不是高估。
- **对排序的影响**：11 个单轮模型的 5 个 non-live 类别合并分（micro，22,644 题里非 live 的 13,640 题），自研→官方共 **4/55 对逆序**：gemma-E2B-Q3 跨过 Qwen3.5-4B-Q3、gemma-E4B-Q2 跨过 Qwen3.5-4B-Q3、gemma-E4B-Q3 跨过 Bonsai、granite-4.1-3b-Q3 跨过 Qwen3.5-4B-Q2。其余 51 对保序。结论：**排序大体可用，分数与邻近间距不可用**。复算命令见 res13。
- **三个存在性类别是实测出来的 0，不是推断的 0**：`irrelevance`（11 格 / 2,640 题）与 `live_irrelevance`（4 格 / 3,536 题）新旧完全一致、翻转 0；`live_relevance`（4 格 / 64 题）差 1 题（`-0.0625`）——自研把 `arguments` 不是 dict 的调用也算「有调用」，官方解码失败即不算。这条差 1 题同时说明了「同构」的边界。
- **prompt 协议 20 行不可重判**：那 4 个模型的 prompt 预测文件不存在（res5），所以「换成官方 checker」对它只能写未测。
- 负控两侧都观测到（`correct_call` 两判对，`wrong_name` / `empty_calls` / `missing_required` 两判错），脚本 `exit=0`；每条测试文件绑定到一个 DB (model, protocol) 行靠的是「重算的自研分与库里 `_score` 逐位相同」这个检验（4 个文件不确定就会 exit 3，实跑 15/15 全部绑定成功）。
- 证据：`audits/official_vs_homegrown.py`、`audits/official_vs_homegrown.json`（逐格明细 + 每个输入文件的 sha256 + 15 个绑定）。
- 复现：`.wrapup/bfclenv/bin/python "docs/subprojects/a13-工具调用 BFCL/audits/official_vs_homegrown.py"`（实跑 `EXIT=0`，打 60 行逐格表、负控四行 `ok`、15 行绑定）。
- 状态：current。

## 入库：单轮 BFCL 的分数量级是错的，已按官方判分器替换（撤回旧值）

### res13 撤回：以前的单轮 BFCL 数字系统性偏低，绝对值不可沿用；排序大体保留

- **撤回什么**：`experiments.sqlite` 里 79 个单轮 native-tools 格的旧 `_score`（自研匹配器的值）不再是当前事实。它们偏低，每一列都偏低，其中位幅度见下表；旧值仍可从 git 历史、`.wrapup/m*_summary.jsonl` 与 `audits/official_vs_homegrown.json` 的 `home_acc` 取回，但**不得再当当前值引用**。
- **为什么**：`possible_answer` 用 `["units", ""]` 表示「该参数可省略」，官方 checker 只校验函数声明里的 `required`；自研 `call_ok` 要求标准答案里**每个**键都出现在预测里。2,788 条「自研判错、官方判对」里 **2,534 条**是这个原因，254 条是类型/取值宽容度（官方按声明做类型检查）。
- **替换后的入库形状**：79 格 `_score` ← 官方值，`protocol` ← `bfcl-native-tools-nothink-greedy-official-ast-checker`；prompt 协议 20 行没有预测文件可重判，值不动，`protocol` ← `bfcl-prompt-nothink-greedy-homegrown-matcher`（身份写明是自研匹配器）。**两条身份不合并**：任何一行存的分数，其 `protocol` 都说明了是哪套判分器给的。
- **逐列旧 → 新**（每列 11 或 4 个 cell 的中位数；`d_min/d_max` 是该列各 cell 的极差）：

| 报告列 | cell | 题数 | 旧中位 | 新中位 | 中位 Δ | Δ 最小 | Δ 最大 | 上行 | 下行 |
|---|---|---|---|---|---|---|---|---|---|
| simple_python | 11 | 4,400 | 0.5975 | 0.8900 | +0.2775 | +0.0050 | +0.3150 | 24 | 943 |
| multiple | 11 | 2,200 | 0.5800 | 0.9150 | +0.3250 | +0.0050 | +0.3500 | 0 | 572 |
| parallel | 11 | 2,200 | 0.7000 | 0.7900 | +0.1050 | 0.0000 | +0.1400 | 0 | 171 |
| parallel_multiple | 11 | 2,200 | 0.6350 | 0.7800 | +0.1450 | +0.0100 | +0.1900 | 5 | 267 |
| irrelevance | 11 | 2,640 | 0.8458 | 0.8458 | 0 | 0 | 0 | 0 | 0 |
| live_simple | 4 | 1,032 | 0.3023 | 0.4070 | +0.1047 | 0.0000 | +0.2752 | 1 | 126 |
| live_multiple | 4 | 4,212 | 0.2707 | 0.4492 | +0.1481 | +0.0104 | +0.3514 | 4 | 697 |
| live_parallel | 4 | 64 | 0.2812 | 0.3125 | +0.0312 | 0.0000 | +0.2500 | 0 | 5 |
| live_parallel_multiple | 4 | 96 | 0.2083 | 0.2917 | +0.0208 | 0.0000 | +0.2500 | 0 | 7 |
| live_irrelevance | 4 | 3,536 | 0.8756 | 0.8756 | 0 | 0 | 0 | 0 | 0 |
| live_relevance | 4 | 64 | 0.3438 | 0.3125 | 0 | −0.0625 | 0 | 1 | 0 |
| **合计** | **79** | **22,644** | — | — | — | — | — | **35** | **2,788** |

- **排序结论保留、绝对值不保留**：11 个模型按 5 个 non-live 类别合并（13,640 题）的新旧两套排序只有 **4/55 对逆序**（题名见 res11），但同一个模型的分数普遍上移 +0.004 到 +0.204，`multiple` 一列整体上移 0.325 —— 所以「谁比谁强」大体还站得住，「分数是多少、差距多大」全部作废。跨模型的相邻差距（例如 gemma-E2B-Q3 与 Qwen3.5-4B-Q3 相差 0.0146）小于这次替换的幅度，单独引用没有意义。
- **入库的三条硬保证**：编号备份（`bak28`/`bak29`，另有 `migrations/backfill_n_items.py` 自建 `bak25`/`bak27`）；`PRAGMA integrity_check=ok`、`checks/db_check.py` PASS（3323 行、0 重复格、0 外键问题）；重跑幂等（第二次 `ingest_bfcl_official_rescore` 改动 **0** 行）。**并且在库副本上实测过收敛**：REFRESH 类 ingest（`ingest_m22`）会把 Bonsai 的 5 行按历史协议串重插，随后 `ingest_bfcl_official_rescore` 把这 5 行改回官方身份，`integrity=ok`。
- **skip ledger**：这次入库只在两类情况下跳过并记账——重打分产物缺失（致命，打印 MISSING 且不动任何行）与库里没有该格；`n_items` 回填那一侧跳过 15 行多轮，原因见 res4。`migrate_db.py` 的 `print_ingest_skips()` 会把它们逐条打出。
- **一次差点造成数据丢失的错误（已修，记录以防复发）**：第一版清理逻辑按 `(model, _bench)` 找重复行，把 prompt 协议的 20 行当成重复删掉了（那是**另一个测量**，不是重复）。库从 `bak28` 恢复后，清理条件收紧到「同一对协议串内」，并把「改前后行数必须一致」写进检查。这一类错误的名字是「身份去重时把另一个测量当重复」。
- 证据：`experiments.sqlite`、`audits/official_vs_homegrown.json`、`migrate_db.py::ingest_bfcl_official_rescore`。
- 复现：
  1. 重打分与逐格表：`.wrapup/bfclenv/bin/python "docs/subprojects/a13-工具调用 BFCL/audits/official_vs_homegrown.py"`（实跑 `EXIT=0`，末尾打印 11 行排序表与 `pairwise inversions homegrown -> official: 4/55`）。
  2. 入库值对照：`sqlite3 -readonly -header -column experiments.sqlite "SELECT protocol,count(*),round(avg(_score),4) FROM experiments WHERE bench_family LIKE 'bfcl%' GROUP BY 1"`（实跑：官方 79 行均值 0.62、prompt 自研 20 行 0.5732、多轮 22 + 2）。
  3. 幂等：`python3 -c "import sqlite3,migrate_db as m; con=sqlite3.connect(m.DB); print(m.ingest_bfcl_official_rescore(con))"`（实跑 `rescored 0`）。
- 状态：current（旧值状态：retracted，死因是 `missing_optional` 等判据差异）。

## 多轮 handler 分组：这一列的「跨模型比较」实际比的是模型+模板

### res12 可比性由 handler 分组决定，跨组比较需要 2×2 重跑

| handler | 用它的模型（多轮） | 类别 | 组内可比？ |
|---|---|---|---|
| `Qwen/Qwen3-1.7B-FC` | Qwen3.5-2B(q2,q3)、Ternary-Bonsai-27B | base, long_context, miss_func, miss_param | **可比**（同模板）：2B-q2/q3 与 Bonsai 可两两比；这是库内唯一有「跨族同模板」对的组 |
| `Qwen/Qwen3-4B-Instruct-2507-FC` | Qwen3.5-4B(q2,q3) | base, long_context | 组内可比（同族同尺寸，只差量化档） |
| `Qwen/Qwen3-8B-FC` | Qwen3.5-9B(q2,q3) | base | 组内可比 |
| `Qwen/Qwen3-30B-A3B-Instruct-2507-FC` | Qwen3.6-35B-A3B(q2,q3) | base | 组内可比 |
| `ibm-granite/granite-4.0-350m` | granite-4.1-3b-Q3_K_M | base | 单独一组；与任何行都不可比（模板既非自家版本也不同尺寸） |

- 因此：**跨 handler 的多轮分数差 = 族/尺寸差 + 模板差**，两者没有分开。库内可读的是上表四个组**组内**的比较；「Qwen 家族比 granite 强」「MoE 比稠密好」这类跨组结论目前**没有证据**。
- 要分开它们需要一个 **2 模型 × 2 handler 的受控对**（同一对模型各跑两个模板），实测成本：每个 arm 200 题，参 m12 的 granite-8B 实测 `11:40` 生成 + ~10 s 判分，E2B/2B 量级 ≤ 12 分钟/arm；四臂加上模型加载 ≈ **50 GPU 分钟**。这是 `PLAN.md` 里 WP4 的设计，也是本轴唯一的未测大项。
- 已有一个族全缺：**gemma-4 多轮 0 行**（单轮 20 行齐）。补 gemma 只能补「覆盖」，补不了「可比」，因为它的 handler 也只能是借来的。
- 证据：`.wrapup/m{9,11,14,17,18,20,22,36}_summary.jsonl` 的 `handler` 字段；`run_m9_panel.sh`。
- 复现：`grep -h '"handler"' .wrapup/m{9,11,14,17,18,20,22,36}_summary.jsonl | python3 -c "import sys,json; [print(json.loads(l)['model'], json.loads(l)['handler']) for l in sys.stdin]"`。
- 状态：current。

## 多轮判分器的负控：它真的会失败（i01 留下的那个缺口关掉了）

### res14 官方 `multi_turn_checker` 四条控制：正确回放判 PASS，三条坏预测全判 FAIL

- 对象是 bundled 的 `bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker.multi_turn_checker`，调用方式与 `.wrapup/bfcl_multi_run.py` 完全相同（同一函数、同一参数序），没有重写判据。用的真实题目是 `multi_turn_base_0`（4 轮、10 条标准调用）。
- 四条控制与实测结果：

| 控制 | 构造 | 要求 | 实测 | `error_type` |
|---|---|---|---|---|
| P 正控 | 把标准答案原样回放成模型答案 | PASS | **PASS** | — |
| A 答案错但格式对 | 某条调用的字符串参数改掉：`cd(folder='document')` → `cd(folder='document_x')` | FAIL | **FAIL** | `multi_turn:execution_response_mismatch` |
| B 意图对但格式坏 | 同一条调用去掉右括号：`cd(folder='document'` | FAIL | **FAIL** | `multi_turn:execution_response_mismatch` |
| C 什么都不做 | 每一轮都不发调用 | FAIL | **FAIL** | `multi_turn:empty_turn_model_response` |

- **正控是这套控制的关键**：没有 P 就只能证明「它会失败」，不能证明「它判得对」。P 成立说明它不是恒假。
- **一个要写进结论的判断**：A 与 B 的 `error_type` 是**同一个** `multi_turn:execution_response_mismatch`，也就是说判分器在错误类型上**不区分「答案错」与「格式坏」**，两者都落到「执行响应不一致」。所以拿历史多轮失败原因做归因（是模型不会调，还是格式没吐对）**不能靠 `error_type`**，只能逐题看 `inference_log` 里 handler 的 decode 记录。
- 边界：只测了 `multi_turn_base` 一条真实题目；`long_context` / `miss_func` / `miss_param` 的判分路径相同（同一个 checker，差别只在数据集内容与 handler 的补全逻辑），但**未逐类构造控制**，写在这里当已知边界。
- 证据：`audits/multiturn_checker_negative_control.py`。
- 复现：`.wrapup/bfclenv/bin/python "docs/subprojects/a13-工具调用 BFCL/audits/multiturn_checker_negative_control.py"`（实跑 `EXIT=0`，四行控制表即上表）。
- 状态：current。

## 判定入口与快照边界

- **判据是脚本，不是本文件里的数**：`python3 "docs/subprojects/a13-工具调用 BFCL/audits/run_all.py"` 一条命令跑完三项——单轮换判分器的对照（必须 exit 0）、多轮判分器的四条负控（必须 exit 0）、以及**库与证据一致**（每个可比格的 `_score` 必须逐位等于 `audits/official_vs_homegrown.json` 的 `official_acc` 且 `protocol` 是官方身份；prompt 20 行必须是自研身份；不许出现未知协议串；`n_items` 为 NULL 的行必须全是多轮）。实跑 `EXIT=0`，末行 `PASS: 判分器对照、多轮负控、库与证据一致`。
- **行数与哈希是快照**：`experiments.sqlite` 仍被 `a06`/`i02` 写，所以任何具体行数（123 行 bfcl、79/20/24、15 行缺题量）都只在指定 revision 上成立。`run_all.py` 因此**不把行数当判据**，只打印快照（含 `artifact sha256[:16]`），判据是上面那些**关系**：别的子项目加行不会把它弄红，本轴自己的值一旦漂移就会红。本文件里引用的库数字均取自 `b8cc7c1` 之后的库状态，重算以 `run_all.py` 的输出为准。
- 这条脚本本身**能红**（实测过两次）：第一次因 `official_vs_homegrown.py` 的绑定把库里的官方值当不匹配而红（`exit 3`），第二次因断言只按 `(model, _bench)` 取行、取到了 prompt 行而红（`exit 1`）——两次都是它自己发现的真不一致，修完才绿。

## 未测（不得当成通过）

1. ~~官方 AST checker 与自研匹配器在单轮上的一致率~~ **已测（res11）**：60 格、34 上行 / 2788 下行。残留：prompt 协议 20 行仍不可重判（无预测文件）。
2. **多轮的重复地板**：没有任何同配置两次的同格对照（res7 的 `0.095` vs `0.11` 只能算线索）。`WP4` 出数。
3. **多轮判分器的可执行负控**：i01 只做了单轮的；`WP5` 未开跑。
4. **prompt 协议的 4 个模型**：预测文件不存在（res5），协议效应只能从库里的 20 行读，重判不可能。
5. **`multi_turn` 之外的多轮类别**（`web_search`、`memory`）与 `simple_java`/`simple_javascript`：库里 0 行，本轴不覆盖。
6. **跨 handler 的族间比较**：未测且不可由库内数据补救，需要 res12 的 2×2 重跑（≈50 GPU 分钟）。
