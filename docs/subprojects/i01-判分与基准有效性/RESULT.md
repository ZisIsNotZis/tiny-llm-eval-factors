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
- **逐题状态不落盘**：`--log_samples` 未开，`.wrapup` 下 0 个 `samples_*.jsonl`；`results.json` 只有聚合，所以「全 timeout 的格」与「真 0 分的格」在产物里只能靠 `lmeval_run.py` 的 `errors/null` 区分。
- 状态：current。
- 证据：`audits/lmeval.md`；实跑输出见该文档的复现命令。
- 复现：`HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .wrapup/lmenv/bin/python "docs/subprojects/i01-判分与基准有效性/audits/lmeval_audit.py"`（实跑 `exit=0`，18 条预期成立）。

### res27 BFCL 单轮不是官方判分器，且两个合理聚合相差最多 20 个百分点（见 audits/bfcl.md）

- 单轮类别由仓库自研匹配器 `.wrapup/bfcl_run.py::evaluate` 判分，多轮由 bundled 官方 `multi_turn_checker` 判分，所以「BFCL」这个汇总是两套实现的混合。
- `live_relevance` 的判分退化为「有没有调用」：bundled 数据集无该类的 `possible_answer`（实测 `exists=False`），代码因此写 `ok = len(calls) > 0`，一个不存在的函数名也判 PASS。
- 匹配器单向宽容（实测 `arg_ok`）：`arg_ok(10,["10"])=True`、`arg_ok("10",[10])=False`、`arg_ok(True,[1])=True`、大小写与首尾空格折叠；且多余参数不检查（`call_ok` 只遍历标准答案的键）→ 这些方向都**向上**。
- 聚合：summary 的 `score` 是按题加权（micro），库里每类别一行的自然聚合是按类别平均（macro），实测最大差 `m8` gr3b-q2 micro 0.3905 vs macro 0.1877（差 0.2028）；方向是 micro 偏高，因为 `live_irrelevance`（884/2251 题，奖励不调用）权重大。
- 库里 123 条 BFCL 行的 `n_items` 全为 NULL，**从库本身算不出 micro**。
- 历史 BFCL 预测文件没有留存（`.wrapup/bfcl_out` 为空），所以自研匹配器与官方 checker 的一致率**未测**，历史分数无法重判。
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
- **131 这道锚点不可复现**：拿 m26 存活文本过两种后处理——原样/新版都得 **139/161**，旧版 `.strip()` 后处理得 **5/161**，都得不到 131/161。所以当初算出 131 的那份文本不在盘上（m26 的 py 样本文件已被修复后的快照覆盖），这是**证据持久性缺陷**，不是判分问题。
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
- 因此读者若把表里的类别列平均起来，得到的是**未加权平均（macro）**；而面板 summary 里那个 `score` 是**按题加权（micro）**。两者实测最大差 **0.2028**（`m8` gr3b-q2：micro 0.3905 / macro 0.1877），方向是 micro 偏高，因为 `live_irrelevance`（884/2251 题，奖励「不调用」）权重大。
- 推论给读者：看 BFCL 那一节时，**逐类别比较是有意义的，跨模型的「BFCL 总分」没有唯一值**；要复现历史 micro 必须回到 `.wrapup/m*_summary.jsonl`，库里没有。
- 状态：current。
- 证据：`make_report.py::table_bfcl`（第 1040–1057 行）；`experiments.sqlite` 的 bfcl 行；`.wrapup/m8_summary.jsonl`。
- 复现：`sqlite3 -readonly experiments.sqlite "SELECT count(*) FROM experiments WHERE bench_family LIKE 'bfcl%' AND n_items IS NULL"` 与 `python3 "docs/subprojects/i01-判分与基准有效性/audits/bfcl_audit.py"`（聚合段打印两组数）。

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
