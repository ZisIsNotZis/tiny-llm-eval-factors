# i01 判分与基准有效性 — 结果

每条事实一行一个陈述；数字后面必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
判断类结论（analysis）与技术测量分开，analysis 不覆盖任何数字。

## 生成可复现性与噪声

### res25 同一 cell 在 `-np 1` 下贪心生成逐字节可复现（plan15 的一半已裁决）

- 条件：plan15 那个 cell（`q38-27b-q3` = `Qwen3.8-27B-UD-Q3_K_XL.gguf`，py，`mpl-chat-nothink-greedy-768`，chat 关思考，贪心，768 tokens，每槽 ctx 2048），提示集 `.wrapup/prompts`（`humaneval-py.jsonl` sha256=ac14c3b0…，跑前过 `sha256sum -c SHA256SUMS`），server 显式 `-np 1`，同一 server 实例内两次独立生成。
- 两次都是 **145/161 = 0.9006**，逐题判定差异 **0 道**，且两份完成物文件 **sha256 完全相同**：单槽贪心生成在这条链路上是逐字节可复现的。
- 与 m161 的关系：现入库值 145/161 正是本次 `-np 1` 复现出的值。所以「m26 用旧判分 131 → 重判 139 → m161 重生成 145」这 6 道题的差，不能说成「贪心生成本身不稳定」；它只能来自两个仍未排除的方向：四槽批处理（`np4`/`np4b` 待测）或提示集（m26 的 `/tmp/MultiPL-E/prompts` 已被删除，不可测）。
- 因此本层仍不得声称 plan15 已完全裁决；已知的是「四槽不是必要条件，单槽就得到 145」。
- 状态：current。
- 证据：`.wrapup/mres/i01-slot-np1-p{1,2}-py-chat.jsonl` 与 `_eval.json`；`.wrapup/mres/i01-slot-np1-meta.json`（含 `n_slots = 1, n_ctx_slot = 2048` 与提示集哈希）。
- 复现：
  1. 逐题通过集：`for f in p1 p2; do jq -r '.details[]|select(.pass)|.name' .wrapup/mres/i01-slot-np1-$f-py-chat_eval.json | sort > /tmp/i01-$f.txt; done; diff /tmp/i01-p1.txt /tmp/i01-p2.txt && echo IDENTICAL`（实跑输出：无差异，即两次通过集相同）。
  2. 完成物逐字节：`sha256sum .wrapup/mres/i01-slot-np1-p{1,2}-py-chat.jsonl`（实跑输出：两行同为 `a2f5eb5dac78a1e4a2387a4fdb943c318dcf71d16edfffeaa9626cbc22457779`）。
  3. 重跑整个 arm：`bash .wrapup/gpu_locked.sh bash "docs/subprojects/i01-判分与基准有效性/audits/slot_repro_arm.sh" np1`。

### res26 lm-eval 五个任务各有可测的失真通道（见 audits/lmeval.md）

- **truthfulqa_mc2 的 `acc` 不是命中率**：它是归一化后的真答案概率质量；817 条文档上「各选项等概率」的地板均值 **0.4484**（首条 4 选 1 真 → 0.2500）。所以该列 0.45–0.55 区间的跨模型差不能读成知识差。
- **gsm8k 入库用 `flexible-extract`，它取完成物里最后一个数字**：答案对但没写 `#### N` → strict 0.0 / flexible 1.0；答案是正确值但末尾另有数字 → strict 1.0 / flexible 0.0。逐例双向偏移，不能用一个常数修正；库里 `gsm8k-strict` 行数为 0，所以真实数据上的变体差未测。
- **ifeval 的入库指标是 `prompt_level_strict_acc`**：空答案 0/100，通用废话 `"The answer to your question is 42."` 与 300 个重复词各 **9/100**——存在约 9 个百分点的、与模型无关的地板。
- **mmlu/arc_challenge 的似然打平不报错**：`argmax` 静默取下标 0，实测平局格 `acc=0`；arc 入库的是 `acc_norm`、`acc` 未入库，两者在真实数据上的差未测。
- **逐题状态不落盘**：`lmeval_run.py` 的命令行不含 `--log_samples`，所以**历史 lm-eval 运行没有逐题样本**；`results.json` 只有聚合，「全 timeout 的格」与「真 0 分的格」只能靠 `lmeval_run.py` 的 `errors/null` 区分。`.wrapup` 下现有的 **4 个 `samples_*.jsonl` 全部是 i01 自己在 2026-10-21 01:01–01:23 用 `--log_samples` 新跑出来的**（`i01-floor/gsm8k-*`），不是历史产物。
- 状态：current。
- 证据：`audits/lmeval.md`；实跑输出见该文档的复现命令。
- 复现：`HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .wrapup/lmenv/bin/python "docs/subprojects/i01-判分与基准有效性/audits/lmeval_audit.py"`（实跑 `exit=0`，18 条预期成立）。

### res27 BFCL 单轮不是官方判分器，且两个合理聚合相差最多 20 个百分点（见 audits/bfcl.md）

- 单轮类别由仓库自研匹配器 `.wrapup/bfcl_run.py::evaluate` 判分，多轮由 bundled 官方 `multi_turn_checker` 判分，所以「BFCL」这个汇总是两套实现的混合。
- `live_relevance` 的判分退化为「有没有调用」：bundled 数据集无该类的 `possible_answer`（实测 `exists=False`），代码因此写 `ok = len(calls) > 0`，一个不存在的函数名也判 PASS。
- 匹配器单向宽容（实测 `arg_ok`）：`arg_ok(10,["10"])=True`、`arg_ok("10",[10])=False`、`arg_ok(True,[1])=True`、大小写与首尾空格折叠；且多余参数不检查（`call_ok` 只遍历标准答案的键）→ 这些方向都**向上**。
- 聚合：summary 的 `score` 是按题加权（micro），库里每类别一行的自然聚合是按类别平均（macro），实测最大差 `m8` gr3b-q2 micro 0.3905 vs macro 0.1877（差 0.2028）；方向是 micro 偏高，因为 `live_irrelevance`（884/2251 题，奖励不调用）权重大。
- 库里 BFCL 行的 `n_items` 正在被 i02 回填（本会话实测 123 行全 NULL → 29 NULL / 94 有值），所以**行级快照要带时间读**。
- **多轮题量是可推导的**：官方 ledger `.wrapup/bfclenv/lib/python3.11/site-packages/score/<handler>/multi_turn/*_score.json` 每次 run 追加 `{accuracy, correct_count, total_count}`，实测四类的 `total_count` 都是 **200**。所以多轮 `n_items` 的缺口属入库侧（i02）可修，不是不可知。
- **多轮列把模型与提示/调用模板混在一起**：每次多轮 run 记在不同官方 handler 下（实测 `Qwen/Qwen3-1.7B-FC`、`Qwen/Qwen3-8B-FC`、`Qwen/Qwen3-4B-Instruct-2507-FC`、`Qwen/Qwen3-30B-A3B-Instruct-2507-FC`；`m22` 的 summary 甚至没有 handler 字段）。**所以多轮那一列不能跨家族或跨尺寸直接比较**，比较前必须先固定 handler。
- **逐题预测是保留的**（我先前「没有留存」那句搜索太窄）：单轮在 `.wrapup/mres/m4-*.jsonl`（**10 份 × 1240 条**）与 `m8-*.jsonl`（**4 份 × 2251 条**），每行含 `calls` 与 `raw`；多轮在官方 ledger 里也有逐条 `{id, test_category, model_result, possible_answer}`。所以「换官方 checker 后哪些单轮数字会变」**只需重打分即可回答，不需要 GPU**——这项从「未测」变成「可测、待做」。
- 状态：current。
- 证据：`audits/bfcl.md`；`audits/bfcl_audit.py`。
- 复现：`python3 "docs/subprojects/i01-判分与基准有效性/audits/bfcl_audit.py"`（实跑 `exit=0`，14 条预期成立）。

### res28 MultiPL-E 的判分是「程序退出码 0」，提前退出即可白拿（历史发生率为 0）（见 audits/multipl-e.md）

- 后处理在**生成**侧（`mpl_run.py gen` 调 `strip_fences`），判分侧 `eval` 不剥任何东西：同一份正确解，带围栏原样 → `Exception` 判 fail；过 `strip_fences` → `OK` 判 pass；未闭合围栏过 `strip_fences` 也 pass；前面带散文的过 `strip_fences` 仍 fail。
- 判据是编译后程序退出码 0，而数据集测试以 `assert` 追加在完成物之后，所以「函数体错误但 `raise SystemExit(0)`」被实测判 pass（对照：`pass` 单独判 fail）。cpp/js/java 的等价构造是 `exit(0);`/`process.exit(0)`/`System.exit(0);`，未逐个实测。
- **该通道在历史语料里 0 发生**：扫描 `.wrapup/mres/*.jsonl` 共 68,584 条落盘完成物（325 个文件），含提前退出构造的 0 条；含 markdown 围栏的 2,096 条（3.06%）。
- 状态直方图逐题记在 `_eval.json`（`OK/SyntaxError/Exception/Timeout`），汇总只在面板日志的 `recorded` 行里，文件本身没有直方图字段。
- 状态：current。
- 证据：`audits/multipl-e.md`、`audits/multipl_e_audit.py`。
- 复现：`python3 "docs/subprojects/i01-判分与基准有效性/audits/multipl_e_audit.py"`（实跑 `exit=0`，9 条预期成立）；语料扫描见该文档第 2、4 条。

### res29 plan15 裁决：批处理被排除，131 不可复现，「6 道题」说法撤回（16 题双向翻转）

- **批处理不是原因**：同一 cell（`q38-27b-q3`、py、`mpl-chat-nothink-greedy-768`、chat 关思考、贪心、768 tokens、每槽 2048 ctx、`.wrapup/prompts` 定版提示集），四个 pass 全部 **145/161 = 0.9006**，且完成物 **sha256 完全相同**（`a2f5eb5d…`）：`np1` 两次（server `-np 1`）+ `npauto` 两次（历史原旗标 `-c 2048` 不带 `-np`，server 自报 `n_slots = 4, n_ctx_slot = 2048`）。逐题比对：三对比较的 Jaccard 均为 1.0，翻转 0 题。**四槽与单槽的输出逐字节相同**，所以「多槽贪心批处理不可复现」这一候选原因被排除。
- **「139→145 的 6 道题只能来自生成侧」撤回**：在存活工件上重算，`m26` 存活的 py 完成物用当前判分得 139/161，今天新生成得 145/161，逐题是 **16 题翻转（11 上 / 5 下，净 +6）**，不是 6 题单向。其中：
  - 11 题上升里有 **7 题**是「同一批 token，只是 m26 那一份丢了缩进」，即 res20/res21 的旧后处理损伤类；
  - 其余 **4 题上升**与 **5 题下降全部**伴随**不同的 token**（不是缩进/围栏差异）。
- **旧文本与今天的生成差异很大**：m26 存活文件与今天的完成物在 **76/161** 题上文本不同，其中 **66 题是 token 不同**、10 题只差缩进/围栏。既然今天的生成在两种槽位下都逐字节可复现，66 题 token 不同只能来自**输入变了**，唯一被记录到不同的候选是提示集（`/tmp/MultiPL-E/prompts` 已删除，无法逐字节比对）。
- **131 这道锚点不可复现**（成立）：拿 m26 存活文本过两种后处理——原样/新版都得 **139/161**，旧版 `.strip()` 后处理得 **5/161**，都得不到 131/161；即算出 131 的那份文本不在盘上。
- **「那份文本被覆盖」只是候选解释之一，不可证**：两条与本条相关的观测是（a）m26 存活文件与 `_fixed` 快照只差 **2/161**（`HumanEval_69_search`、`HumanEval_129_minPath`），所以它非常接近「修复后再落盘」的那一份；（b）`.wrapup/prompts/humaneval-py.jsonl` 的 mtime 是 **2026-10-14 20:51**，而 m26 那次 run 的 panel start 是 **2026-10-02 20:51:40**，即**测试集在这次 run 之后变过**。两条都只是线索：既不能证明旧文本被覆盖，也不能证明它是另一条从未落盘的生成流。按 `PLAN.md` 预注册的口径，这一项写成「**不可证**」，不写成事实。
- **后果（这才是可用的结论）**：跨 run 比较这个 cell 时，未记录的输入差能造成 **±16/161（≈0.10）**量级的翻转，并让 66/161 的完成物 token 不同。所以任何两次 run 只有在**提示集哈希 + 后处理版本**都被钉住并记录时才可比；把 6/161 或 16/161 当噪声地板是错的——它不是噪声，是输入差。
- 状态：current（裁决口径在 `PLAN.md` 的「plan15 的裁决口径」一节里先写死，实跑落在「四槽复现 145」那一支）。
- 证据：`.wrapup/mres/i01-slot-{np1-p1,np1-p2,npauto-p1,npauto-p2}-py-chat{.jsonl,_eval.json}` 与 `i01-slot-{np1,npauto}-meta.json`；`m26-q38-27b-q3-py.jsonl`、`m26-q38-27b-q3-py_fixed_eval.json`。
- 复现：
  1. 四臂逐题比对：`python3 "docs/subprojects/i01-判分与基准有效性/audits/slot_repro_compare.py"`（实跑 `verdict: prompt-set`，三对 `flipped=0 jaccard=1.0000 identical=True`）。
  2. 逐字节：`sha256sum .wrapup/mres/i01-slot-{np1-p1,np1-p2,npauto-p1,npauto-p2}-py-chat.jsonl`（四行同值 `a2f5eb5d…`）。
  3. 131 不可复现：对 `m26-q38-27b-q3-py.jsonl` 原样 / 过旧后处理 / 过新后处理各跑一次 `mpl_run.py eval`，得 139 / 5 / 139。

### res30 BFCL 在报告里没有汇总列，读者能自己算出来的只有 macro（见 audits/bfcl.md）

- 库侧：`experiments` 的 BFCL 行是**每类别一行**（`_bench = bfcl-<category>`），`n_items` **全为 NULL**（实测 123/123），所以库里没有任何字段能把类别重新按题量加权。
- 报告侧：`make_report.py::table_bfcl` 渲染成「一行一个 (模型, 协议)、一列一个类别」，**没有汇总列**——报告本身不声明单一个 BFCL 数字。
- **单轮族**：类别长度不等（simple_python 400、multiple/parallel/parallel_multiple 各 200、irrelevance 240、live_simple 258、live_multiple 1053、live_parallel 16、live_parallel_multiple 24、live_relevance 16、live_irrelevance 884），所以把类别平均得到的 macro ≠ 面板 summary 的 micro，实测最大差 **0.2028**（`m8` gr3b-q2：micro 0.3905 / macro 0.1877），方向是 micro 偏高，因为 `live_irrelevance`（884/2251 题，奖励「不调用」）权重大。
- **多轮族**：四类各 **200** 题（官方 ledger 的 `total_count` 四份一致），所以**多轮 macro == micro**，不存在这个差。
- 因此「micro 与 macro 最大差 0.2028」**只对单轮族成立**，不能推广到多轮；报告里这两族也必须分开讲。
- 推论给读者：看 BFCL 那一节时，**逐类别比较是有意义的，跨模型的「BFCL 总分」没有唯一值**；要复现历史 micro 必须回到 `.wrapup/m*_summary.jsonl`，库里没有。
- 状态：current。
- 证据：`make_report.py::table_bfcl`（第 1040–1057 行）；`experiments.sqlite` 的 bfcl 行；`.wrapup/m8_summary.jsonl`。
- 复现：`sqlite3 -readonly experiments.sqlite "SELECT count(*) FROM experiments WHERE bench_family LIKE 'bfcl%' AND n_items IS NULL"` 与 `python3 "docs/subprojects/i01-判分与基准有效性/audits/bfcl_audit.py"`（聚合段打印两组数）。

### res31 EvalPlus 的判分器不做后处理，且 MBPP+ 有 1/378 个任务能被空体拿满（见 audits/evalplus.md）

- **判分器 `evalplus.evaluate` 完全不后处理**：它把 samples 里的 `solution` 原样 `exec`；后处理只在写入侧 `evalplus/codegen.py:89` 调一次 `sanitize()`（tree-sitter 按语法有效块抽定义节点），并同时落一份 `.raw.jsonl`。判据不是「剥围栏」而是「按语法找最长有效块」，所以围栏没闭合也能救回，但块里混入非 Python 文本就可能抽错块。
- **方向两侧都实测**：正确解带围栏直接判分 → `fail`；同一份先过 `sanitize()` → `pass`；空完成物、错函数体、`def` 首行在第 0 列、多缩进一层 → 全部 `fail`。真实数据上（humaneval `w1-2bq4-r1` 的 8 个任务）去掉后处理有 **5/8** 判定翻转（raw fail → sanitized pass），即这条链路上后处理承担了大部分通过量。
- **MBPP+ 的白拿通道**：3 个任务的 oracle 只检查「输出不是 None」（`Mbpp/737、787、794`）；其中 `Mbpp/787` 的 101 条 plus 期望全为 False，所以一个只 `return None` 的错误函数体 **`plus_status=pass`**（实测）。另有 7 个任务退化为集合相等（顺序不敏感）；源码里 `exact_match or True` 那个 oracle 在本数据集版本中**不存在**（实测空集）。
- **逐题状态**：`*_eval_results.json` 存每任务 `base_status`/`plus_status`（`pass/fail/timeout`），但不存直方图、**也不存 `pass_at_k`**——库里每个 EvalPlus 分数都是事后由状态重算的。一格全 `timeout` 与真 0 分在文件里只能靠直方图分辨。
- 状态：current。
- 证据：`audits/evalplus.md`、`audits/evalplus_audit.py`。
- 复现：`.wrapup/evalpy/bin/python "docs/subprojects/i01-判分与基准有效性/audits/evalplus_audit.py"`（实跑 `exit=0`，45 条 HumanEval+ 与 9 条 MBPP+ 预期成立）。

### res32 chat 单次测量的噪声地板：四族同配置重复都是 0/题（边界：确定性解码）

同配置重复同一 cell 的逐题结果，四族全部**完全相同**（重算：`python3 "docs/subprojects/i01-判分与基准有效性/audits/noise_floor_compare.py"`）。

| 族 | cell 与配置 | n | 相同题数 | 上翻/下翻 | 分数摆动 | Jaccard |
|---|---|---|---|---|---|---|
| MultiPL-E chat | `q38-27b-q3` py，`mpl-chat-nothink-greedy-768`，greedy，同提示集，`-np 1` 两次 | 161 | 161 | 0 / 0 | 0.0000 | 1.0000 |
| MultiPL-E chat | 同上但历史原旗标（server 默认 → 4 槽），两次 | 161 | 161 | 0 / 0 | 0.0000 | 1.0000 |
| EvalPlus chat | `2b q4` humaneval，temp=0，三次 | 164 | 164 | 0 / 0 | 0.0000 | 1.0000 |
| lm-eval gsm8k | `Qwen3.5-2B-UD-Q3_K_XL`，`--reasoning off`，`--limit 100`，两次（生产配置） | 100 | 100 | 0 / 0 | 0.0000 | 1.0000（两次同为 71/100） |
| BFCL 单轮 | `simple_python` native tools，`--limit 40`，两次 | 40 | 40（预测调用 0/40 不同；correct 10 vs 10） | 0 / 0 | 0.0000 | — |

- **总结：在确定性解码 + 同一提示集 + 同一后处理版本下，chat 单次测量的噪声地板是 0 道题**——重复跑不会改变任何一道题的判定。
- **适用边界（不得外推）**：上表全部是 greedy/temp=0 且样本被 `--limit` 截到 40/100/161/164。采样解码下地板**远不是 0**：同一个 cell（`2b q4` humaneval）在 temp=0.3 的 5 次重复里，逐题通过集合的两两 **Jaccard 只有 0.53–0.67**，每对 **上翻 8–15 题、下翻 6–12 题**，而分数只在 37→43（6/164）之间摆动——即**分数摆动会系统性地低估逐题不稳定**，采样协议下必须按逐题比，不能按分数比。
- **与 `plan15` 的 ±16/161 严格区分**：地板 0 说的是「输入相同、重复跑」；±16/161 说的是「输入变了（提示集/后处理版本）」。两者不可相加、不可互相替代。本项目解读小差异的规则因此是：**提示集哈希 + 后处理版本相同 → 任何非零跨 run 差异都不是噪声；任一改变 → 先按 res29 判输入差，再谈显著性。**
- gsm8k 这一行用的是**生产配置重跑**：server 带 `--reasoning off`，01:18:27–01:20:51 与 01:20:51–01:23:43 两次 `rc=0`，两次都是 **71/100**，逐题 100/100 相同，响应非空（首题 `filtered=['26']`）。证据：`.wrapup/i01_noise_floor2.out`、`.wrapup/i01_noise_floor.log` 的 `rep=1/2 rc=0` 行、`.wrapup/mres/i01-floor/gsm8k-r{1,2}/samples_gsm8k_2026-10-21T01-2*.jsonl`。
- 第一次尝试（`gsm8k-noReasoning-flag-r{1,2}`，11/100）是在**漏传 `--reasoning off`** 的 server 上跑的：响应 content 为空、判分多为 `[invalid]`，那不是生产 cell。它留在盘上只作为「这个旗标不能漏」的证据，**不进地板分母、不作为结论数**。
- 状态：current。
- 证据：`.wrapup/mres/i01-slot-{np1,npauto}-p{1,2}-py-chat_eval.json`；`.wrapup/wres/humaneval/w1-2bq4-r{1,2,3}_openai_temp_{0.0,0.3}_eval_results.json`；`.wrapup/mres/i01-floor/{gsm8k-r*,gsm8k-noReasoning-flag-r*,bfcl-r*}`；`.wrapup/i01_noise_floor.log`。
- 复现：`python3 "docs/subprojects/i01-判分与基准有效性/audits/noise_floor_compare.py"`（实跑：四族 `identical==n`、`swing 0.0000`）；采样边界用 `w1-2bq4-r{1..5}_openai_temp_0.3_eval_results.json` 两两比。

### res33 echo shim 的精确性已实测：top-N 内逐位相同，top-N 外不造假（但文档关于「报错」的说法是错的）

- **在 top-N 内，shim 与 llama-server 的数字逐位相同**：argmax token `-0.807629 vs -0.807629`、第 2 名 token `-2.809992 vs -2.809992`，走 HTTP 面同样是 `-2.809992`。这三条是 mmlu / arc_challenge / truthfulqa_mc2 三列可信的前提。
- **top-N 外不造假**：给一个模型几乎不可能预测的续写（`" æßþø中文ZZQQ"`），shim 返回 `-17.451372`，不是 `0.0`；该值的概率 `exp(-17.45)=2.6e-8`，低于 top-2000 dump 的覆盖下限（`1/2000=5e-4`），与「真的去取了该 token 的对数概率」一致。
- **但 `lmeval_run.py` 的文档说错了**：docstring 写「不在 top-N 就升级 N 一次、再不行**硬报错，从不会返回 0.0**」；实测它**没有报错**，而是升级到更宽的 N 并返回了真实值。升级到能看见 token 为止是更好的行为，但**文档与实现不符**，这一条按缺陷登记（改文档即可，不改实现）。
- **仍未测的边界**：那个 tail 值 `-17.451372` 的精确性没有被独立确认（token 在 top-2000 dump 之外），所以「升级后的取值是否与模型逐位相同」只在前 2000 名内验证过。
- 状态：current。
- 证据：`.wrapup/mres/i01-shim-probe/probe-output.txt`（本次跑的输出）、`.wrapup/mres/i01-shim-probe/shim_probe.log`。
- 复现：`python3 "docs/subprojects/i01-判分与基准有效性/audits/lmeval_shim_probe.py"`（实跑 `exit=0`；实测 free VRAM 19,029 MiB、峰值占用 6,805 MiB、`n_slots = 1`、耗时约 1 分钟；与 a06 的 m165 并行，属 registry 的 GPU 并发例外）。

### res34 clone 里 `run_all.py` 的 exit 2 是「不可得」，不是失败

- **语义**：`audits/run_all.py` 的退出码是 `0 = 全部测过且成立`、`2 = 有东西不可得（逐项打印缺哪个文件）`、`1 = 红`。干净 clone 落在 **2**：逻辑组照常跑绿，真实数据审计逐项报缺什么。看到一个 2 不等于失败——它与 README「它不能重建的东西」那段同义（模型权重、评测运行本身、CJK 字体等）。
- **逻辑组在 clone 里为什么能绿**：`audits/scoring_logic_check.py` 只用仓库里已跟踪的文件（`.wrapup/mpl_run.py`、`.wrapup/bfcl_run.py`、gsm8k 的两条抽取正则）与系统编译器（g++ 一例），输入全部内联构造。实测：全树与「空树模拟 clone」两种情况下它都是 `green`。
- **真实数据组在 clone 里为什么是 2（逐项实测的理由）**：`bfcl_audit` / `lmeval_audit` / `evalplus_audit` 要三个 venv（`.wrapup/{bfclenv,lmenv,evalpy}` 不入库，靠 bootstrap 重建）与数据集（bfcl 包内 / HF 缓存）；`multipl_e_audit` 要格子的 `.jsonl` 完成物（`.gitignore` 只放行 `*_eval.json`）；`noise_floor_compare` 的 EvalPlus 一半要 `.wrapup/wres/**/*_eval_results.json`（**0 个被跟踪**），所以即使四个 MultiPL-E 的 `_eval.json` 已随仓库分发（`i01-slot-*-py-chat_eval.json` 均 tracked），它仍会是 2。
- **随仓库分发的 i01 证据**：`.wrapup/mres/i01-slot-{np1,npauto}-p{1,2}-py-chat_eval.json` 与 `i01-recheck-g26b-q2-cpp_eval.json` 共 5 份已入库（其余逐题产物与完成物在 `.gitignore` 内，可重跑重建）。
- **一处需要别人修的矛盾**：README 同时写着「`.wrapup/mres/*_eval.json` … 随仓库分发（337 files）」与「`.wrapup/mres/*_eval.json` 是逐题落盘产物、**不入库**」——同一事实两个家且一真一假（实测 341 个 `*_eval.json` 被跟踪）。README 不属本层，登记待 i02/meta 修。
- 状态：current。
- 证据：`audits/run_all.py`、`audits/scoring_logic_check.py`；`git ls-files .wrapup/mres | grep -c '_eval.json'`。
- 复现：全树 `python3 "docs/subprojects/i01-判分与基准有效性/audits/run_all.py"` → `exit 0`；clone 模拟 `I01_REPO_ROOT=$(mktemp -d) python3 "…/audits/run_all.py"` → `exit 2` 并列出 `interpreter … absent` / `… missing`。

### res35 门的契约：不可得要如实报，而不是算失败（假红已修）

- **契约（判据是「退出码 + 输出标记」的组合，不是退出码本身）**：`exit 0 且有实测行` → 绿；`exit 2 且有 UNMEASURED 行` → **绿**（它正确地说了「拿不到」，这正是干净 clone 的形态）；`exit 0 但无实测行` → 红（假绿）；`exit 2 但无 UNMEASURED 行` → 红（静默放弃）；`exit 1` 或崩溃 → 红；**解释器缺失（venv 不随仓库分发）→ 绿·不可得**，因为那是「没有证据」而不是「结论错」。
- **两个环境都实测 exit 0**：本机 `.wrapup/i01_gate_host.out` 与三份模拟 clone（空树 `i01_gate_clone.out`、只含跟踪脚本与 `.wrapup/mpl_run.py`/`bfcl_run.py` 的假 clone `i01_gate_fakeclone.out`），两次都是 `10 green, 0 red`；本机那次的实测行数分别是 bfcl 19 / noise_floor 5 / multipl_e 9 / lmeval 18 / evalplus 55。
- **门自己也有负控（`--self-test`，实跑 `exit=0`）**：伪造的「exit 0 但什么都没测」→ 判 **红**；伪造的「UNMEASURED + exit 2」→ 判 **绿**。所以这个门既能失败，也不会把不可得误判成失败。
- 假 clone 里 `run_all.py` 仍然是 **exit 2**（`LOGIC green` + `GATE green`，5 条 DATA 逐项报缺什么）——与 `res34` 的语义一致，不受本修影响。
- 状态：current。
- 证据：`.wrapup/i01_gate_selftest.out`、`.wrapup/i01_gate_host.out`、`.wrapup/i01_gate_clone.out`、`.wrapup/i01_gate_fakeclone.out`、`.wrapup/i01_run_all_fakeclone.out`。
- 复现：`python3 "docs/subprojects/i01-判分与基准有效性/audits/unmeasured_gate_check.py" --self-test`；同脚本不带参数跑本机；`I01_REPO_ROOT=$(mktemp -d)` 跑空树模拟。

## 判分缺陷与修复### res16 MultiPL-E 旧列不可比（language 覆盖）

- 各模型只跑了不同的语言子集（Qwen3.5-2B-UD-IQ2_XXS 只有 cpp；gemma-4-12b 只有 java/js/rb/rs），把不同测集平均后，gemma-4-12b/26B 的近零分数是语言覆盖造成的假象。
- 当前规则：标准列只在 cpp 与 py 都测过时产出该单元，否则记缺失（NaN），不画点。
- 状态：current。
- 证据：`experiments.sqlite` 的 humaneval-multipl-e 行；`report.html` 数据质量节。
- 复现：`sqlite3 experiments.sqlite "SELECT model,language FROM experiments WHERE protocol='multipl-e-raw-greedy-768' GROUP BY 1,2 ORDER BY 1,2"`。

### res17 全 Exception 的格曾被写成 score=0

- 扫描 `.wrapup/mres/*_eval.json` 时有多份文件每道题状态都是 `Exception`，却被计为 0；其中含 gemma-4-26B-A4B 的 py（chat 协议），而同模型 cpp 正常。
- 份数不写在这里：报告数据质量第 2 条按构建时扫描给出当前文件数、其中 `_fixed` 重判份数、5 题探针份数与去重后的格数。
- 当前规则：这类格必须记缺失（NULL）、不得写 0；对应行已置 NULL（备份 `experiments.sqlite.bak37`）。
- 状态：current（本条的成因归因已由 res17b 撤回，见下）。
- 证据：`.wrapup/mres/m26-g26b-q2-py_eval.json` 的 statuses 全为 `Exception`（n=161）。
- 复现：`jq -r '[.details[].status]|group_by(.)|map({(.[0]):length})|add' .wrapup/mres/m26-g26b-q2-py_eval.json`。

### res17b 撤回 res17 的两个成因归因

- 撤回一：「那些全 Exception 的格是整轮运行报错」——不成立。
- 撤回二：「旧 `strip_fences` 的 `text.strip()` 破坏首行缩进，所以判失败」——不成立：同一「函数体首行在第 0 列」的签名在修正后的 harness 下依然存在，修 harness 既没有也救不回那些格。
- 当前成因归到模型行为（res21 的签名计数 + res24 的端到端控制格）。
- 「却被写成 0、必须记缺失」这一半仍然成立。
- 状态：current。
- 证据：`.wrapup/mres/m161-g26b-q2-py-chat_eval.json` 与 `.wrapup/mres/m161-g26b-q3-py-chat_eval.json` 的 statuses 中 `Exception` 各 159、160（n=161）；`.wrapup/mres/m161-g26b-q2-py-chat.jsonl` 首条完成物首行为 `for i in range(len(numbers)):`（列 0）。
- 复现：`jq -r '.details[]|select(.status=="Exception")|.name' .wrapup/mres/m161-g26b-q2-py-chat_eval.json | wc -l`。

### res18 生成协议改变 MultiPL-E 分数（跨面板比较，不是受控比较）

- 同一模型 gemma-4-26B-A4B、同一语言 cpp：raw 纯补全 9/161 = 0.0559，chat（关思考）134/161 = 0.8323。
- 方向可信（差 125/161，远超任何已测噪声），但两次来自不同面板（m10 vs m26），不是同一面板内的受控对照；面板内的 raw vs chat 受控复测是 m160 的任务，它没有产出测量（res19），该复测至今未跑。
- 状态：provisional——「协议改变分数」这一方向成立，「差多少由协议单独造成」尚未受控验证；这个受控复测属于 a12 的协议轴，不在本层 AC 内。
- 证据：`.wrapup/mres/m10-g26b-q2-cpp_eval.json` 与 `.wrapup/mres/m26-g26b-q2-cpp_eval.json`。
- 复现：`for f in m10-g26b-q2-cpp m26-g26b-q2-cpp; do jq -c '{n,pass,score}' .wrapup/mres/${f}_eval.json; done`。

### res19 m160 面板没有产出测量（失败形态被记成 CORRUPT）

- 2026-10-14 20:46 启动的 16 个 cell 全部在生成前失败（`/tmp/MultiPL-E/prompts` 已被清理，`FileNotFoundError`），脚本把它记成 `CORRUPT ... empty=999`。
- 其后一次不经脚本的运行留下 `g12b-q2 cpp raw` 的 0/161；其完成物 151/161 不含 `return`、27/161 只有注释、18/161 带 `<|channel>` 通道 token——是原始补全模式下模型不写函数体，不是提示集坏了。
- 状态：current。
- 证据：`.wrapup/m160.log` 行 42–55 `FileNotFoundError: /tmp/MultiPL-E/prompts/humaneval-cpp.jsonl`；`.wrapup/mres/m160-g12b-q2-cpp-raw.jsonl`。
- 复现：`grep -c 'CORRUPT' .wrapup/m160.log` 与 `grep -c 'FileNotFoundError' .wrapup/m160.log`。

### res20 MultiPL-E chat 判分曾把 Markdown 围栏当语法错误

- 旧 `strip_fences` 只在围栏闭合时才剥离，而数据集停止串把完成物切在闭合围栏之前，于是整格失败。
- 用磁盘完成物（同一份生成、只补上正确后处理）重算：Qwen3.8-27B cpp chat Q2 0.2174→0.6335、Q3 0.4845→0.8571；py 仅 +0.0435/+0.0497；gemma-4-26B 的完成物无围栏，其 cpp 0.8323 不变。
- Q3 那一对是**重判值**、不是该格的当前值：q38-27b-q3 cpp chat 现入库值是 0.8696 = 140/161；重判与重跑之差见 PLAN.md 的 WP6。
- 状态：current。
- 证据：`.wrapup/mres/m26-*_fixed.jsonl`（由 m26 原始样本经修正后处理生成）；m26-q38-27b-q3-cpp 有 72/161 带围栏且 72/161 失败，重算 pass 78→138。
- 复现：`python3 .wrapup/mpl_run.py eval --lang cpp --samples .wrapup/mres/m26-q38-27b-q3-cpp_fixed.jsonl`。

### res21 「函数体首行在第 0 列」签名不是后处理造成的，但仍不能救回那些格

- 旧 `strip_fences` 开头 `text.strip()` 确实会抹掉无围栏完成物的首行缩进（m48 已改为只剥行首围栏），但「因此造成 gemma-4-26B-A4B py 那些 Exception」这一因果从句撤回。
- 落盘完成物普遍带「函数体首行在第 0 列」的签名：m26 的 g26b-q2-py 160/161、g26b-q3-py 161/161，对照格 q38-27b-q3-py 13/161；m161 是在修正后的 harness 下落盘的，同一签名仍在（g26b-q2-py 159/161、g26b-q3-py 160/161 首行列 0）。
- 修正后的 `strip_fences` 对无围栏完成物只做 `rstrip`、不动缩进，所以该签名不是后处理造成的证据。
- 仍然为真的另一半：m26 落盘的 py 完成物用修正后处理重判仍是 `pass: 0`，这些格靠重判救不回来。
- 状态：current。
- 证据：m26 落盘 py 完成物用修正后处理重判 `.wrapup/mres/m26-g26b-q2-py_fixed_eval.json` 与 `.wrapup/mres/m26-g26b-q3-py_fixed_eval.json` 的 `pass` 均为 0（n=161）。
- 复现：每格首行列 0 的条数 `jq -r '.completion|split("\n")[0]' <samples.jsonl> | grep -c '^[^[:space:]]'`；重判值 `jq .pass .wrapup/mres/m26-g26b-q2-py_fixed_eval.json`。

## 分析

### an5 不要用 PPL 做决策

- PPL 与任务分约 30% 情况方向相反。
- 状态：provisional。
- 来源：`docs/product/product.yaml::prod3` 派生；原始出处已退役（`.scratch` 按 `@scratch` 停用，原件不再可打开），因此这条只有结论没有可重算的证据。
- 复现：未测——当前没有一条命令能重算那个 30%；在报告里必须按 provisional 呈现，不得当成已复现测量，也不得当成 0。

### an7 换生成协议后必须重测

- 协议本身会改变量化结论的符号，所以换协议等于换一个测量。
- 状态：provisional（但 res18 已给出同向的强证据：同模型 cpp 的 raw 0.04 对 chat 0.83）。
- 来源：`docs/method/method.yaml::m23`；原始出处 `.scratch/originals/L3-分析.md` 7。
- 复现：见 res18 的命令。
