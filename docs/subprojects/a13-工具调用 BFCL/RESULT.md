# a13 工具调用 BFCL — 结果

每条事实一行一个陈述；数字后面必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回。
**本轴不产出 BFCL 总分**：任何跨协议、跨类别的单一数字都不成立（见 res1、res10）。下文所有数字都带协议串与类别，命令里可见。
下文的 `sqlite3 -readonly` 全部只读，不改库。

## 数据形状

### res1 BFCL 的 123 行是四个测量，不是一列

- 库侧分布：`bfcl` / `bfcl-native-tools-nothink-greedy` = 79 行、11 模型；`bfcl` / `bfcl-prompt-nothink-greedy` = 20 行、4 模型；`bfcl-multiturn` / `bfcl-official-multiturn-temp0` = 22 行、10 模型；`bfcl-multiturn` / `bfcl-official-multiturn-temp0-partial` = 2 行、1 模型。
- 单轮 11 个模型里只有 4 个（Qwen3.5-2B 的 q2/q3、Qwen3.5-4B 的 q2/q3）同时有 native-tools 与 prompt 两个协议；其余 7 个只有 native-tools。
- 证据：`experiments.sqlite`。
- 复现：`sqlite3 -readonly -header -column experiments.sqlite "SELECT bench_family, protocol, count(*) rows, count(n_items) n_notnull, count(DISTINCT model) models FROM experiments WHERE bench_family LIKE 'bfcl%' GROUP BY bench_family, protocol ORDER BY 1,2"`（实跑输出即上表四行）。
- 状态：current。

### res2 `n_items` 的 29 个 NULL 全都是多轮行加上 Bonsai 的单轮行

- 29 = 多轮 24 行（22 + 2 partial，全部 NULL）+ Bonsai 单轮 5 行；其余 94 行有值（i02 回填的派生值，不是测量）。
- 因此「BFCL 这条线缺 n」这句话在多轮上是整列的缺失，不是零散缺格。
- 证据：`experiments.sqlite`。
- 复现：`sqlite3 -readonly experiments.sqlite "SELECT count(*) FROM experiments WHERE bench_family LIKE 'bfcl%' AND n_items IS NULL"`（实跑输出 `29`）；逐行看：`sqlite3 -readonly -header -column experiments.sqlite "SELECT model,_bench,_score,n_items,source_file FROM experiments WHERE bench_family LIKE 'bfcl%' AND (n_items IS NULL OR _bench LIKE '%long_context%') ORDER BY model,_bench"`。
- 状态：current。

## 多轮的题量与聚合

### res3 多轮四个类别各 200 题，所以多轮内部「按类别平均」与「按题加权」是同一个数

- bundled 数据集逐类计数：`multi_turn_base` / `multi_turn_long_context` / `multi_turn_miss_func` / `multi_turn_miss_param` 各 **200** 行；官方运行台账亦记 `total_count = 200`（实测一行 `{"accuracy": 0.7, "correct_count": 140, "total_count": 200}`）。
- 推论（这一步是算术，不是新测量）：当每个类别题量相同，类别等权的 macro 与题量加权的 micro 相等。所以多轮的四类别组合**有唯一值**——但它只对「四个类别都跑过」的模型存在，即 `Qwen3.5-2B-UD-Q2_K_XL` 与 `...Q3_K_XL`（各 4 类）；Bonsai 只有 3 类（base + miss_func + miss_param），Qwen3.5-4B 只有 2 类，9B / 35B-A3B / granite 只有 base。
- 与 i01 `res27`/`res30` 的关系：i01 判「micro 与 macro 差到 0.2028、库算不出 micro」是在**单轮混合面板**上成立的（`live_irrelevance` 884 题等权重极不均）；多轮这一侧题量是齐的，口径差异消失。两句不矛盾，但也不能互相引用。
- 证据：`data/BFCL_v4_multi_turn_*.json`（bundled 数据集）、`score/<handler>/multi_turn/BFCL_v4_<cat>_score.json`（官方运行台账）。
- 复现：`cd .wrapup/bfclenv/lib/python3.11/site-packages/bfcl_eval/data && for c in multi_turn_base multi_turn_long_context multi_turn_miss_func multi_turn_miss_param; do printf "%-28s %s\n" "$c" "$(python3 -c "print(sum(1 for l in open('BFCL_v4_$c.json') if l.strip()))")"; done`（实跑输出四行 `200`）；台账：`cd .wrapup/bfclenv/lib/python3.11/site-packages && python3 -c "import json; rows=[json.loads(l) for l in open('score/Qwen_Qwen3-1.7B-FC/multi_turn/BFCL_v4_multi_turn_base_score.json') if l.strip()]; print(len(rows), rows[0])"`（实跑 `61 {...}`，第一行的 `total_count` 就是 200）。
- 状态：current。

### res4 多轮有官方运行级台账，逐次追记 —— i01「多轮题量推不出自任何运行产物」需要收窄

- `score/<handler>/multi_turn/BFCL_v4_<category>_score.json` 是**追加日志**：每次官方 `bfcl evaluate` 追加一行 `{accuracy, correct_count, total_count}`。实测 `multi_turn_base` 在 `Qwen_Qwen3-1.7B-FC` 下共 **61 行**，即这个 handler 上跑过 61 次该类别。
- 这条台账在同一 handler 被多个模型复用时**不记模型名**，所以它只能证明「某个有 200 题的 run 发生过」，不能把某一行绑定到某个模型。i01 说「面板 summary 只记 `accuracy`、没有 `n`」对 `.wrapup/m*_summary.jsonl` 大体成立（例外：`m32_summary.jsonl` 与 `m36_summary.jsonl` 都带 `"n": 200`），但「推不出自任何运行产物」过强。
- 方向：这让多轮 `n_items` 的缺失变成**可回填**（`WP7`），而不是永久缺失；回填要走 i02 的 `migrate_db.py`。
- 证据：`score/*/multi_turn/*_score.json`、`.wrapup/m32_summary.jsonl`、`.wrapup/m36_summary.jsonl`。
- 复现：`cd .wrapup/bfclenv/lib/python3.11/site-packages && wc -l score/*/multi_turn/*_score.json`；`grep -c '"n": 200' /home/z/vibe/local_lm_research/.wrapup/m32_summary.jsonl /home/z/vibe/local_lm_research/.wrapup/m36_summary.jsonl`。
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

## 未测（不得当成通过）

1. **官方 AST checker 与自研匹配器在单轮上的一致率**：`WP2` 未开跑。res5 已证明输入齐备，所以这是「未测」而不是「不可测」。
2. **多轮的重复地板**：没有任何同配置两次的同格对照（res7 的 `0.095` vs `0.11` 只能算线索）。`WP4` 出数。
3. **多轮判分器的可执行负控**：i01 只做了单轮的；`WP5` 未开跑。
4. **prompt 协议的 4 个模型**：预测文件不存在（res5），协议效应只能从库里的 20 行读，重判不可能。
5. **`multi_turn` 之外的多轮类别**（`web_search`、`memory`）与 `simple_java`/`simple_javascript`：库里 0 行，本轴不覆盖。
