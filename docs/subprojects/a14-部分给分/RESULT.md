# a14 部分给分 — 结果

每条事实一行一个陈述；数字后面必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。

## 口径（先定义，后面所有数字按这个读）

- **二元 Y**：一道题通过对面的全部单元测试才算过。分数 = 通过题数 / 题数。
- **逐测试比例**：一道题内部通过的测试数 / 该题提供的测试数，分母取测试源码里的断言数（`testfrac.py::expected_count`），不是执行到的断言数。
- **`mean_frac`** = 先按题算比例再对题取平均；**`micro_frac`** = 全部通过测试数 / 全部测试数。两者是不同的统计量，不互相替代。

## 可得性（WP2）

### res1 逐题二元产物在仓库里，但它不带测试数，所以二元 Y 已入库、比例不能从它直接算

- 已入库的逐题 artefacts 共 **341** 个（`git ls-files .wrapup/mres`），按结构分三种：
  - **322** 个 MultiPL-E 结构（顶层 `details`，每道题一条 `{name, pass, status}`），共 **47872** 条逐题记录；
  - **15** 个 BFCL 结构（只有 `{n, correct, score, per_category}`，无逐题）；
  - **4** 个 EvalPlus 结构（顶层 `eval`，每题一条含 `base_status`/`plus_status`/`base_fail_tests`/`plus_fail_tests`）。
- **MultiPL-E 的逐题记录只有 `pass` 与 `status`，没有「这道题有几条测试」**，所以从 `_eval.json` 只能得到二元 Y，得不到逐测试比例。
- 状态：current。
- 证据：`.wrapup/mres/m1-qwen4b-q2-py_eval.json`（`details[0]` 的键集就是 `['name','pass','status']`）、`.wrapup/mres/m22-bonsai_eval.json`（BFCL 结构）、`.wrapup/mres/a04-arm-uni45-humaneval-evalplus_eval.json`（EvalPlus 结构）。
- 复现：
  ```
  python3 -c "
  import json,subprocess,collections
  tr=subprocess.run(['git','ls-files','.wrapup/mres'],capture_output=True,text=True).stdout.split()
  s=collections.Counter(); items=0
  for f in tr:
      d=json.load(open(f))
      if 'details' in d: s['details']+=1; items+=len(d['details'])
      elif 'eval' in d: s['evalplus']+=1
      elif 'per_category' in d: s['bfcl']+=1
  print(dict(s),'records',items)"
  ```
  实跑输出：`{'evalplus': 4, 'details': 322, 'bfcl': 15} records 47872`。

### res2 逐测试比例对 78 个 MultiPL-E 格已经算好并在仓库里，覆盖 4 种语言

- `.wrapup/testfrac_<tag>-<lang>.jsonl` 共 **78** 个逐题文件 + **79** 个汇总文件，全部已跟踪（`git ls-files .wrapup | grep 'testfrac_.*jsonl'` = 157）。
- 逐题字段：`{name, n_tests, n_pass, frac, binary_pass, status}`；每格题数 `n` 与该格测试总数都在文件里，所以比例**不需要重跑模型**就能用。
- 语言覆盖：`cpp` 29 格、`py` 27 格、`js` 16 格、`java` 6 格。`rs`/`rb`/`pl` **没有探针实现**，比例不可得（见 res6）。
- 平均每题测试数（`cpp`，`m1-qwen4b-q2`）**7.019**，`java` 6.975，`js` 7.019 —— 一道题内部就有 ~7 条测试，这是二元 Y 扔掉的粒度。
- 状态：current。
- 证据：`.wrapup/testfrac_m1-qwen4b-q2-py.jsonl`、`.wrapup/testfrac_summary.jsonl`（60 行，字段 `n, pass, pass_at_1, mean_frac, micro_frac, mean_tests_per_item`）。
- 复现：
  ```
  python3 -c "
  import glob,os,collections
  its=[f for f in sorted(glob.glob('.wrapup/testfrac_*.jsonl')) if not f.endswith('_summary.jsonl')]
  print(len(its), collections.Counter(f[:-len('.jsonl')].rsplit('-',1)[-1] for f in its))"
  ```
  实跑输出：`78 Counter({'cpp': 29, 'py': 27, 'js': 16, 'java': 6})`。

### res3 生成物不随仓库分发，所以「比例」的可复算性来自这些已入库的逐题文件，不来自重跑

- `.wrapup/mres/*.jsonl`（模型完成物）**339 个在盘上、0 个跟踪**（`.gitignore` 的规则是「只发 `*_eval.json`，完成物可重建」）。
- 后果：干净 clone 里能算的比例只限 res2 那 78 格；其余格要算比例必须重新生成完成物（GPU）。这条是 `WP6` 代价清单的依据，不是缺陷。
- 状态：current。
- 复现：`ls .wrapup/mres/*.jsonl | wc -l` → `339`；`git ls-files .wrapup/mres | grep -c 'jsonl$'` → `0`。

### res4 EvalPlus 的逐题状态在，但缺分母；补分母只要数据集、不要 GPU

- 已跟踪的 4 个 EvalPlus `_eval.json` 每题都有 `base_fail_tests` / `plus_fail_tests`（失败测试名清单），但**没有该题测试总数**。
- 所以「每题通过了几条测试」不能从 artefact 算；分母在 EvalPlus 数据集的测试集里（`HumanEvalPlus`/`MBPPPlus` 每题固定输入数）。代价是 CPU：数据集已在 `.wrapup/evalpy` venv 里（gitignored），只需要读出每个 task 的测试数，**不需要 GPU、不需要重跑模型**（`base_fail_tests` 已经在 artefact 里）。
- 限制：`fail_tests` 只给名字，不给「跑了没跑」，所以分母仍须与数据集对齐后才能算比例；对齐前不得声称比例可得。
- 状态：current（EvalPlus 比例**未测**，仅判定「分母在数据集侧」）。`testfrac_audit.py --matrix` 的这一行给出同一句话与代价。

### res5 lm-eval 五任务的逐题样本没有落盘，因此 gsm8k/mmlu/arc 的比例不可得；但 ifeval 的细粒度指标本来就记在 artefact 里

- 587 份 `lmeval_*.json` 里 **0** 份含 `samples`（`lmeval_run.py` 从不传 `--log_samples`，`i01::res26` 已记录），所以 gsm8k/mmlu/arc_challenge 的逐题对错没有产物，任何「每题部分分」都不可得。
- **例外**：`ifeval` 天然是细粒度的——它同时报 `prompt_level_strict_acc`（题级，等价二元 Y）与 `inst_level_strict_acc`（指令级，等价「逐测试比例」）。**不变量：`lmeval_ifeval_*.json` 里的每一份都含 `inst_level_strict_acc`**（检查写成 `with_inst == len(files)`，不写死份数）。份数随产物增长，所以只报「写这条时的值」：2026-10-21 复核时是 **108/108**（初写时 106/106，中间又落了 2 份）。所以对 ifeval 来说更细的 Y **已经在库里，零成本**。实测同一格 `m100-qwen38-27b-q3kxl`：题级 0.75、指令级 0.8405。
- 代价（若要 gsm8k/mmlu/arc 的逐题）：必须用 `--log_samples` 重跑该格（GPU，`m100` 的 gsm8k 单格实测 11 分钟量级），且只能拿到逐题对错，拿不到「题内部分分」——选择题与短答在定义上就是二元的。所以这一族**没有「逐测试比例」这种东西**，只有「逐题是否对」的噪声结构。
- 状态：current（ifeval 细粒度指标已有值；gsm8k/mmlu/arc 的比例在本定义下**不可得**，原因是题目内部没有测试）。

### res6 BFCL 的逐题产物不存在，比例不可得；它的二元 Y 本身已经是「按题」

- 已跟踪的 15 个 BFCL `_eval.json` 只有 `{n, correct, score, per_category}`；`.wrapup/bfcl_out` 目录**空**（0 个文件）。所以「一条用例内几个参数/几轮对」没有落盘。
- BFCL 的一条用例本来就是一条测试，题内没有更细的官方粒度；官方多轮 ledger 只记 `{accuracy, correct_count, total_count}`（`i01::res27`），`total_count=200` 是题数不是测试数。因此把「逐测试比例」搬到 BFCL 只能自造「每轮/每参数通过率」，那是新指标而不是现有 Y 的细化，本项目**不做**。
- 状态：current。

## 有效性（WP2 顺带得到的强证据）

### res7 逐测试探针的二元判定与 harness 的二元判定在 76 个格上逐题一致

- 78 个 testfrac 逐题文件里，**76** 个有同名 `<tag>_eval.json`，共逐题比较 **12218** 道题（78 格共 12540 道）：`binary_pass` 与 harness 的 `pass` **0 个不一致**，且这 76 格两边题集完全相同。
- 这条同时证明两件事：(1) `testfrac.py` 的探针（宏/猴补/ast 改写）没有把程序行为改成另一个判定；(2) `n_tests` 分母口径没有把「本来通过」的题算成不通过。**没有这条，后面所有比例都不成立**。
- 缺的两个格是 `m3-g12b-q2-js` 与 `m3-g12b-q3-py`（同名 `_eval.json` 未跟踪），它们不进任何配对统计。
- 状态：current。
- 复现：
  ```
  python3 -c "
  import json,glob,os
  its=[f for f in sorted(glob.glob('.wrapup/testfrac_*.jsonl')) if not f.endswith('_summary.jsonl')]
  dis=[]
  for f in its:
      key=os.path.basename(f)[len('testfrac_'):-len('.jsonl')]
      ev='.wrapup/mres/' + key + '_eval.json'
      if not os.path.exists(ev): continue
      d=json.load(open(ev)); evp={x['name']:x['pass'] for x in d['details']}
      tf={json.loads(l)['name']:json.loads(l) for l in open(f)}
      bad=[n for n in set(evp)&set(tf) if bool(evp[n])!=bool(tf[n]['binary_pass'])]
      if bad or len(set(evp)&set(tf))!=len(d['details']) or len(set(evp)&set(tf))!=len(tf): dis.append((key,bad[:3]))
  print('disagreements',len(dis))"
  ```
  实跑输出：`disagreements 0`。

### res8 `testfrac.py` 的语言覆盖是 4 种，`rs`/`rb`/`pl` 没有探针

- `testfrac.py::RUNNERS` 只有 `cpp/js/py/java`；对 `rs`/`rb`/`pl` 跑会直接 `choices` 报错，不是「比例 0」。所以这三种语言的格在比例口径下**未测**，代价是写新探针（每种语言一套断言计数注入 + 一次二元一致性复核，即重复 res7 的检查）。
- 状态：current。复现：`grep -n 'RUNNERS = ' .wrapup/testfrac.py`。

### res9 一条命令给出可得性矩阵，且缺输入就 `exit 2`、篡改就 `exit 1`

- 入口：`python3 "docs/subprojects/a14-部分给分/testfrac_audit.py"`。三条检查（二元一致性 / 分母在场 / ifeval 指令级指标在场）全过才 `exit 0`；缺输入 `exit 2` 并打印 `UNMEASURED + 缺哪个文件`；结构不认识的产物也算不可得而不是跳过。
- 实跑输出：`产物：MultiPL-E 322 份 / EvalPlus 4 份 / BFCL 15 份；逐测试比例逐题文件 78 格 12540 道题` / `检查1 二元一致性：配上的格 76，逐题比较 12218 道，不一致 0 项` / `检查2 分母在场：缺 n_tests 的逐题记录 0 条` / `检查3 ifeval 指令级指标：<N> 份产物中 <N> 份含 inst_level_strict_acc`（N 随产物增长，初写 106、复核 108） / `RESULT PASS`，`EXIT=0`。
- **负控成立**：`--negative-control` 在临时副本上把 `testfrac_m1-qwen4b-q2-cpp.jsonl::HumanEval_0_has_close_elements` 从通过改成不通过，检查报出 `m1-qwen4b-q2-cpp: 1 道题二元判定不一致，例如 ['HumanEval_0_has_close_elements']`，`EXIT=0`（负控自己通过）；不篡改时同一检查报 0 项。两侧都观测到了，不是只证一半。
- 输入全部已入库（`.wrapup/mres/*_eval.json`、`.wrapup/testfrac_*.jsonl`），所以这条在干净 clone 里应当同样 `exit 0`；`experiments.sqlite` 不参与，因此不依赖库的状态。
- 状态：current。
- 复现：
  ```
  python3 "docs/subprojects/a14-部分给分/testfrac_audit.py"; echo "EXIT=$?"
  python3 "docs/subprojects/a14-部分给分/testfrac_audit.py" --negative-control; echo "EXIT=$?"
  python3 "docs/subprojects/a14-部分给分/testfrac_audit.py" --matrix
  ```

## 双 Y 对照（WP3 / WP5）

### res10 同一批完成物上，比例恒 ≥ 二元，且两者不是同一把尺：中位位移 +0.114

- 76 个格的 `mean_frac - pass@1`：74 格为正、2 格为 0（那两格是 `m3-g12b-q2-cpp/java`，161/158 道题全不过、比例也是 0），最小非零 **+0.0062**，最大 **+0.2381**（`m1-qwen4b-q2-js`），中位 **+0.1115**（这是**全部 76 格**的中位；若只取 74 个非零格则是 **+0.1138**——两个数都对，但分母不同不能混着引）。
- 读法：比例高不是「模型更强」，而是「过一部分测试比过全部测试容易」。所以两个 Y **不能互换填进同一张表**，也不能把比例的增量当成质量增量。
- 状态：current。
- 证据/复现：`python3 "docs/subprojects/a14-部分给分/rank_compare.py"` 的「## 1" 表（§ 列 `Δ比例-二元`）。

### res11 排序基本不变：Spearman 0.888–1.000，108 对里 7 对符号反转

- 按语言（不池化）：`cpp` 29 格 **0.9622**、`js` 15 格 **0.8883**、`py` 26 格 **0.9636**、`java` 6 格 **1.0000**（`pass@1` vs `mean_frac`）。
- 配对规则：同语言、同题数、tag 只在**一个**连字号位置不同（即只改了一个命名字段的两个设置），共 **108** 对；其中 **7** 对符号反转。
- 反转不是均匀散布，而是集中在近差对（见 res12）：7 对里有 4 对的题数差 ≤2。
- 状态：current。复现：同上脚本的「## 2」「## 3」两节。

### res12 更细的 Y **没有**把二元 Y 留下的歧义消掉：9 个近差对里只分开 3 对，且其中 **1** 对与二元结论相反

- 近似并列（题数差 1–2）= **9** 对：比例同向 **5** 对、反向 **4** 对。
- 用逐题配对 bootstrap（2000 次，逐题比例差）看这 9 对：**只有 3 对**的 95% 区间不含 0，其余 6 对分不开。**3 对里只有 1 对是反向的**，另两对与二元同号：
  - `m3-e4b-q3-js` vs `m3-gr3b-q3-js`：二元 −1 题（−0.0062），比例 **+0.1075**，95% [+0.0138, +0.2038]，题级 51 正/42 负；
  - `m3-gr3b-q2-py` vs `m3-q08b-q2-py`：二元 +2 题（+0.0124），比例 +0.0576，95% [+0.0038, +0.1093]，47/28；
  - `m3-g12b-q2-cpp` vs `m3-g12b-q3-cpp`：二元 +2 题，比例 +0.0186，95% [+0.0016, +0.0404]，题级 **5 正/0 负**（两格都近乎全错，这一对的「分开」靠 5 道题的部分分）。
- **二元并列（题数完全相同）的配对只有 2 对，且比例在这 2 对上都没有分开（95% 区间含 0）**。所以「二元打平、比例能分」这种情况在本批数据里**未观测到**。
- 比例并列而二元不同的对：**0** 对。
- 区间**端点**对 bootstrap 种子与重采样顺序敏感（独立复核用另一实现得 `[+0.0048,+0.1104]`，本脚本得 `[+0.0027,+0.1077]`），所以承重的判据只有一个：**区间是否含 0**。两种实现给出同一个「分开/不分」判定，这才是本节要的结论。
- 状态：current。复现：同上脚本的「## 3」节（`近似并列` 段）。

### res13 同一批题上，比例的估计标准误并不比二元小：比值中位 0.96，最差 1.76

- 逐格比 `SE(mean_frac)`（题间 bootstrap/√n）与 `SE(pass@1)`（二项）：74 个可算格里比值中位 **0.9572**，最小 **0.66**，最大 **1.76**；按**精确**比值 **26 格 ≥1**（比例反而更粗）、**27 格 <0.9**。注意：脚本打印列取两位小数，按打印值数会得到 28 ≥1 / 26 <0.9——差在 `m3-e2b-q3-js`（0.9982）、`pan-glm47flash-tq1-cpp`（0.9956）、`m1-qwen4b-q3-py`（0.8978）这三个贴边格的四舍五入。**结论不变**：比例的精度收益是偶然的。
- 读法：比例的精确度收益是**偶然的、按格变化**的，不是系统性的。原因在结构：一道题内部 ~7 条测试并不是 7 个独立信息——一条函数写错通常让该题全部测试一起失败，所以分母变大了但有效样本量没怎么变。
- 这是**题间**不确定性，不是跑间噪声；跑间噪声另计（见「待办事实」）。
- 状态：current。复现：同上脚本的「## 4」节。

### res14 排序对照的负控成立：把比例在同语言内打乱，反转从 7 对升到 48 对、Spearman 掉到 −0.254–0.429

- `rank_compare.py --negative-control` 做的是一次**已知错误的副本**：保留 `pass@1`，把 `mean_frac` 在同语言的格之间随机重排（不可以用「在题间打乱 frac」，那个变换保均值，平均比例一点不变，测不到东西——这正是本文第一版的缺陷，已改）。
- 实跑（打乱种子固定，连跑两次逐字相同）：反转 **7 → 48** 对；Spearman `cpp 0.962→−0.254`、`py 0.964→0.151`、`js 0.888→0.021`、`java 1.000→0.429`。所以 res11/res12 的那些数确实依赖比例的真实取值，不是结构自带的。
- 状态：current。复现：`python3 "docs/subprojects/a14-部分给分/rank_compare.py" --negative-control; echo EXIT=$?`（实跑 `EXIT=0`）。

### res15 判分侧重跑逐字节相同；一个 161 题的 py 格重算只要 ~12 s CPU、0 GPU

- 同一个完成物文件（`.wrapup/mres/m1-qwen4b-q2-py.jsonl`）跑两次 `testfrac.py --lang py --workers 5`：两份输出 `sha256` 同为 **498b6060…76ed01**，汇总行逐字相同（`n 161, pass 58, mean_frac 0.569358, micro_frac 0.533956, mean_tests_per_item 7.317`），耗时 11.6 s / 11.9 s。
- 所以「判分侧重跑噪声」= **0**（在同一输入快照下）；但这只能当**确定性**用，不能当「已入库的数可重算」（见 res16）。
- 代价：每格一次重算 ~12 s CPU / 5 并发，**0 GPU、不重新生成完成物**。
- 状态：current。注意这条用了两个 gitignored 输入（完成物 `.wrapup/mres/*.jsonl`、`/tmp/MultiPL-E/prompts`），所以**干净 clone 不可复算**。
- 复现：
  ```
  cd .wrapup && python3 testfrac.py --lang py --samples mres/m1-qwen4b-q2-py.jsonl --out /tmp/r1.jsonl --workers 5 \
    && python3 testfrac.py --lang py --samples mres/m1-qwen4b-q2-py.jsonl --out /tmp/r2.jsonl --workers 5 \
    && sha256sum /tmp/r1.jsonl /tmp/r2.jsonl
  ```
  实跑输出：两行同为 `498b6060d3efce406eb59825fb4cb23c5d32a1c766010f4c1ec0f3d84276ed01`。

### res16 今天重算同一格得到 58/161，已入库的是 57/161 —— 不是判分不稳定，是 py 测试语料被重建过（见 res19 的判别实验）

- 今天的 `/tmp/MultiPL-E/prompts/humaneval-py.jsonl` 与仓库的 `.wrapup/prompts/humaneval-py.jsonl` **逐字节相同**（两者 sha256 都是 `ac14c3b0abfa218c8442807b729acdce30a165d9e2f79b9dfa7bf78e6aa26edb`）；但两份都**不是** 2026-09-30 产出入库产物时用的那份：`.wrapup/prompts/humaneval-py.jsonl` 的 mtime 是 `2026-10-14 20:51`，在 b57a71f（2026-10-19）才被钉进仓库，而入库的 py 产物与 `_eval.json` 都是 `2026-09-30 08:06–20:31` —— 用的是当时 `/tmp` 里的旧副本。
- 用今天的语料重算，与已入库的 `testfrac_m1-qwen4b-q2-py.jsonl` 不一致：**40/161** 道题的分母 `n_tests` 不同（均值 **7.317** vs **7.019**），格级 **pass 58 vs 57**、`mean_frac` **0.569358 vs 0.543334**、`micro_frac` **0.533956 vs 0.508850**。
- 分母的 40 条里，**37 条**是因为当时的计数口径排除常量真断言（`assert True`）而今天的不排除：用「排除 `assert True`」这条规则在今天的文本上重算，161 道题里 **157 道**与入库值一致（今天代码的口径只对得上 121 道）。剩下 **4 道在任何口径下都推不出来**，所以**文本真的变了**：

  | 题目 | 入库 n_tests | 今天文本 A（全部断言） | 今天文本 B（排除 assert True） |
  |---|---|---|---|
  | `HumanEval_33_sort_third` | 4 | 7 | 7 |
  | `HumanEval_44_change_base` | 12 | 7 | 7 |
  | `HumanEval_53_add` | 5 | 6 | 6 |
  | `HumanEval_78_hex_key` | 6 | 7 | 7 |

- 结论：已入库的逐题比例是**证据物**，内部自洽且与 harness 二元判定逐题一致（res7）；但它**不是**「拿仓库里任何东西就能重算出同一组数」的**复现**——产出它的语料文本已不在盘上，且新旧文本在断言内容上也不同（见 res19 的 47 个判定翻转）。这与 `plan15` 的「提示集不是被钉住的输入」同一个类（该说法在 `i01/PLAN.md:40` 与 `i01::res25` 的叙述里，措辞要改见 res21 的注）。
- 对 a14 结论的影响：无。res11–res13 的对照全部用**同一批已入库文件**做成对比较，且 res7 用 12218 道题证明这批文件的二元判定与 harness 一致。
- 状态：current（机制在 res19 判别完毕）。
- 证据：`.wrapup/testfrac_m1-qwen4b-q2-py_summary.jsonl`（pass 57 / mean_frac 0.543334 / mean_tests_per_item 7.019）vs res15 的实跑汇总行；`.wrapup/prompts/humaneval-py.jsonl` 的 mtime 与 b57a71f 的日期。
- 复现：
  ```
  sha256sum /tmp/MultiPL-E/prompts/humaneval-py.jsonl .wrapup/prompts/humaneval-py.jsonl
  ls -l --time-style=long-iso .wrapup/prompts/humaneval-py.jsonl .wrapup/mres/m1-qwen4b-q2-py.jsonl .wrapup/mres/m1-qwen4b-q2-py_eval.json
  python3 "docs/subprojects/a14-部分给分/corpus_version_check.py"   # 四道不可达题 + 逐格摘要一起校
  ```
  实跑输出：两行同为 `ac14c3b0…26edb`；mtime 分别为 `2026-10-14 20:51` / `2026-09-30 08:06` / `2026-09-30 08:06`。

### res19 判别实验：不是判分侧不稳定，是 py 测试语料被重建过 —— 47/10608 个判定翻转**全部**落在 py，cpp+java+js 0/6422

问的是：`58 vs 57` 这 1 道题到底是「评分侧不稳定」还是「入库时用的是旧测试」？两者后果不同，所以先做能区分的实验。

1. **同一批完成物、同一份语料、连跑两次判分**：`mpl_run.py eval` 两次都 `pass=58`，两份输出 `sha256` 同为 **fe71bad6…a35bc**（`testfrac.py` 另一条路径也是两次逐字节相同，见 res15）。不稳定假设在第一步就不成立。
2. **定位那一题**：`HumanEval_79_decimal_to_binary`。
   - 入库 `_eval.json`：`pass=False`、`status=Exception`；入库 `testfrac`：`n_tests=4, n_pass=0, frac=0.0, binary_pass=False, status=NoOutput`。
   - 今天：harness `pass=True status=OK`；`testfrac` `n_tests=5, n_pass=5, frac=1.0, binary_pass=True, status=OK`。
   - 完成物是纯整数进制转换（`decimal % 2`、字符串前插），**无任何不确定性源**：完成物与测试里 `random`/`hash`/`time`/`set(`/`dict(`/`shuffle`/`datetime`/`glob` 的出现次数**全部为 0**；`PYTHONHASHSEED` 取 `0/1/42/12345` 各跑 3 次，**12/12 返回码都是 0**（Python 3.12.3，numpy 2.5.4 在场）。
   - 关键细节（**是推断，不是 diff**）：该题入库 `n_tests=4` **等于**今天文本在「排除 `assert True`」口径下的值 4（按今天的口径则是 5），所以**分母看上去没变**。但**旧文本在盘上不存在**——`find / -name humaneval-py.jsonl` 只找到 `ac14c3b0…` 这一代（`/tmp`、`.wrapup` 与各处 clone 全同）与 git 里的 `b57a71f`，所以「哪条断言变了、是 prompt 还是 tests 变了」**无法 diff**。能说的只有：同一份完成物、同一份判分代码、判分变了 ⟹ 旧格用的文本 ≠ 这一代。把它写成「期望值变了」是由分母相等推出来的**推断**，标注为推断。
3. **环境差异逐个排除**：`eval_one`（写 `prompt + completion + "\n" + tests`、跑 `python3`、超时 10 s）在**加入这批产物的那个提交 7cd7f61 与 HEAD 之间逐字节相同**；`run_eval` 唯一的改动是提示路径从写死的 `/tmp/...` 改成 `prompt_path(...)`（即改成读钉住语料）。完成物本身也没重生成过：`.wrapup/mres/m1-qwen4b-q2-py.jsonl` 的 mtime 是 `2026-09-30 08:06:24`，其 `_eval.json` 是 `08:06:51`（相差 27 秒）。
4. **能区分的实验**：用今天的钉住语料 + harness 自己的判分路径，把**已落盘完成物**全量重算（66 个格：cpp 19 / java 6 / js 15 / py 26，共 **10608** 道题）：

   | 语言 | 格 | 题 | 判定翻转 |
   |---|---|---|---|
   | py | 26 | 4186 | **47（1.123%），分布在 17 个格** |
   | cpp | 19 | 3059 | **0** |
   | js | 15 | 2415 | **0** |
   | java | 6 | 948 | **0** |

   判分侧不稳定不会挑语言：超时、浮点、`hash` 随机化、进程环境都会随机落在任何语言上。翻转**全部**在 py，而不是 py 的 6422 道 cpp/java/js 一题也不动——这只能来自「py 的 `tests` 文本换了」。
5. **幅度**：17 个 py 格改变分数，最大 **+5 道题**（`m21-bonsai-q2g64-py` 123→128、`pan-glm47flash-q3-py` 79→84，即 **+3.1 个百分点**），最小 −2（`pan-glm47flash-tq1-py` 19→17）；17 格净 +17 道题，方向是新语料对 py 略宽松。

**结论**：这是「入库时用的是旧测试」，不是「评分侧 1 题不稳定」。已入库的 py 产物是 2026-09-30 用当时的 `/tmp` 副本算的；今天的语料在 2026-10-14 重建、2026-10-19 才钉进仓库。

**对 `i01::res32`（确定性解码地板 = 0）意味着什么**：**地板 0 仍成立**，因为它是用**同一份语料**内的重复测量定的（`np1`×2 与 `npauto`×2 完成物逐字节相同），本实验不动它。但它把 plan15 的「(a) 提示集」从「不可测」变成**有实测机制和量级**：一次语料重建就能让 py 格移动 **0–5 道题**，正好是 6/161 的量级；可以升级为「已测的语料版本差」，但不得说成已证就是那一次的原因（那个语料副本已不在）。

  **指针更正（复核 D6）**：那句「131→139 由判分缺陷解释」在 **`docs/subprojects/i01-判分与基准有效性/PLAN.md:40`**，不在 `i01::res25`；而 `i01::res29` 已经改口（拿 m26 存活文本过原样/新版后处理都得 **139/161**，**131 不可复现**）。所以这不是「i01 仍主张后处理解释」，而是**它有一处 PLAN 遗留措辞与 res25 的叙述没跟着 res29 改**。要 i01 修的是 `PLAN.md:40` 与 `res25` 里 131→139 的措辞，把成因补成「语料代次（本文件 res20/res27 实测）」。a14 不改它的目录。

- 状态：current。
- 证据：`docs/subprojects/a14-部分给分/evidence/corpus_rescore.json`（66 格逐格的旧/新通过数与翻转题名，含四个语料文件的 sha256）。
- 复现：
  ```
  python3 "docs/subprojects/a14-部分给分/corpus_version_check.py"                 # 静态四条证据 + 逐格摘要对账，实跑 PASS
  python3 "docs/subprojects/a14-部分给分/corpus_version_check.py" --negative-control
  # 重算某一格（需要 gitignored 完成物）：
  # cd .wrapup && python3 mpl_run.py eval --lang py --samples mres/m1-qwen4b-q2-py.jsonl --out /tmp/h1.json
  ```
  实跑负控输出：`给 HumanEval_79_decimal_to_binary 追加一条必失败断言后，判分给出 pass=False status=Exception` —— 与入库那条历史记录的形状一致，证明「语料变了 → 判定翻」这条链两端都观测到了。

### res27 翻转的来源清单：最大来源是 `HumanEval_95`（32 格，OK→Exception），机制是**输入类型变了**，不是「期望值变了」

- 151 个翻转只涉及 **20 道题**，但极不平均（`evidence/py_regrade.json` 的 `flipped` 列按题名计数）：

  | 题 | 涉及格数 | 方向 |
  |---|---|---|
  | `HumanEval_95_check_dict_case` | **32** | OK → Exception |
  | `HumanEval_79_decimal_to_binary` | 26 | Exception → OK |
  | `HumanEval_65_circular_shift` | 18 | 双向 |
  | `HumanEval_103_rounded_avg` | 16 | 双向 |
  | `HumanEval_158_find_max` | 14 | 双向 |
  | 其余 15 题 | ≤9 各 | 双向 |

- **`HumanEval_95` 的机制可直接观测，是「输入类型变了」**：钉住语料的第三条断言是
  `assert candidate({"p":"pineapple", 5:"banana", "a":"apple"}) == False` —— 字典里带 **int 键 `5`**。
  于是把 `for k in d: if k.islower()` 这类解法直接打成 `AttributeError: 'int' object has no attribute 'islower'`。
  实测（`m1-qwen4b-q3-py` 的完成物 + 钉住测试，`PYTHONHASHSEED` 取 `0/1/42/12345` 各 4 次）：**16/16 返回码都是 1，stderr 尾行都是这条 AttributeError**——确定性复现，不是超时/浮点/hash。
  所以这一类翻转的成因是**测试喂进来的输入类型**（旧格那一代没有这条 int 键断言，或其断言不同），不是期望值写错。
- **`HumanEval_79` 的成因只能推断**（见 res19 第 2 步的注）：旧文本不在盘上，无法 diff 是哪条断言、也无法区分是 prompt 还是 tests 变了；只能由「同一完成物 + 同一判分代码 + 判定翻转」推出「旧文本 ≠ 这一代」。
- **所以机制那句话的正确写法**：语料重建改变了**判分输入**（断言集合/期望值/输入数据三者之一或多项），其中可证的一支是 `HumanEval_95` 的 **int 键输入类型**；`HumanEval_79` 那一支只能写成「文本变了，细节不可观测」。**不得**写成「期望值变了」当结论。
- 状态：current。
- 证据：`docs/subprojects/a14-部分给分/evidence/py_regrade.json`（每格的 `flipped` 题名）。
- 复现：
  ```
  python3 -c "
  import json,collections
  d=json.load(open('docs/subprojects/a14-部分给分/evidence/py_regrade.json'))
  c=collections.Counter(n for cell in d['cells'] for n in cell['flipped'])
  print(c.most_common(6))"
  ```
  实跑输出：`[('HumanEval_95_check_dict_case', 32), ('HumanEval_79_decimal_to_binary', 26), ('HumanEval_65_circular_shift', 18), ('HumanEval_103_rounded_avg', 16), ('HumanEval_158_find_max', 14), ('HumanEval_161_solve', 9)]`。

### res20 全部 98 个历史 py 格用钉住语料重评：50 格改分、151/15516 题翻转；**且 `plan15` 那格的 131→139 由语料代次单独复现**

- **范围**：库里 `bench_family='humaneval-multipl-e' AND language='py'` 写这条时 **117 行**、复核时已涨到 **136 行**（库是活的，别人在并发入库）；其中 **98 个格**至今还有落盘完成物（`git ls-files` 不含它们），这 98 格共 **15516** 道题被重评。**未被重评的是「没有完成物」的那些行**：按 117 行算 19 行、按 136 行算 38 行——这个数要按当时的库重算，不能当常数（要重评得重跑模型，GPU）。
- **语料代次**：`.wrapup/prompts`（`sha256sum -c SHA256SUMS` 6/6 OK），`humaneval-py.jsonl` 的 sha256 = **ac14c3b0abfa218c8442807b729acdce30a165d9e2f79b9dfa7bf78e6aa26edb**，于 `b57a71f`（2026-10-19）钉入仓库，文件 mtime 是 2026-10-14 20:51。判分身份串写成 `mpl-raw-greedy-768;corpus=ac14c3b0abfa`（**库里还没有这个串**）。
- **结果**：**50/98 个格改变分数，151/15516 道题翻转（0.973%）**。逐格 Δ 分布：0 有 48 格，|Δ|≤2 有 40 格，|Δ|≥3 有 **10 格**。

  | 格 | 旧 → 新 | Δ题 | 翻转 |
  |---|---|---|---|
  | `m26-q38-27b-q3-py` | 131 → **139** | +8 | 8 |
  | `m26-q38-27b-q2-py` | 105 → 112 | +7 | 9 |
  | `m21-bonsai-q2g64-py` | 123 → 128 | +5 | 5 |
  | `pan-glm47flash-q3-py` | 79 → 84 | +5 | 5 |
  | `m10-q38-27b-q3-py` | 118 → 122 | +4 | 6 |
  | `pan-llama32-3b-q2-py` | 48 → **45** | −3 | 3 |
  | `pan-llama32-3b-q3-py` / `pan-glm47flash-tq1-py` | 80 → 78 / 19 → 17 | −2 | 2 |

- **`plan15` 的那个数被复制出来了（这是本项目最该被 meta 看到的一条）**：`m26-q38-27b-q3-py` 在钉住语料下的重评结果是 **139/161**，而 `i01::res25` 记录的是「按旧后处理判分 131，用**修正后后处理重判同一批落盘完成物** 139」。`mpl_run.py eval` 的 `eval_one` **完全不施加后处理**（直接写 `prompt + completion + "\n" + tests`），所以「换语料代次」单独就能把 131 变成 139。**i01 把 131→139 归因于后处理修正，这个归因与语料代次混淆了**；139→145 仍然是生成侧（m161 是重新生成的完成物）。这条不属 a14 的 AC，交 `i01` 复核措辞。
- **被语料代次改掉的排序边界（7 对，全部落在 1–2 题的近差区）**：同语言、tag 只差一个字段、同题数：
  - `m10-q38-27b-q2` vs `m10-q38-27b-q3`：旧 **−2 题** → 新 **0 题**（Q2 与 Q3 的差消失）；
  - `m3-q4` vs `m3-q5`：旧 +1 → 新 0；
  - `m27-q4-t0.3` vs `m27-q4-t0.6`：旧 0 → 新 +1（一个打平变成有差）；
  - `m31-q3-tk1` vs `m31-q3-tk20/tk40/tk64/tk200`：旧 0 → 新 +1（**四对本来打平的 top-k 档变成有差**，影响 `a06` 的 top-k 结论口径）。
- **旧格无法反推它当年用的是哪一代**：任何入库产物都没记录语料哈希；2026-10-14 前的 `/tmp` 副本已不在盘上。能留下的唯一指纹是分母样式：用「排除 `assert True`」这条规则在**今天**的文本上重算，161 道题里 **157** 道与入库值吻合（今天代码的口径只吻合 121 道），**4** 道在任何口径下都推不出来（res16 的表）。所以只能说「旧格 = 不是这一代」，**说不出**它是哪一代。
- 状态：current。
- 证据：`docs/subprojects/a14-部分给分/evidence/py_regrade.json`（98 格逐格旧值/新值/翻转题名 + 语料 sha256 + 判分身份串）。
- 复现：
  ```
  python3 "docs/subprojects/a14-部分给分/py_regrade.py"            # 核对语料代次与旧值，打印逐格旧→新与 §13 影响面，实跑 PASS
  python3 "docs/subprojects/a14-部分给分/py_regrade.py" --rescore  # 重打分并重写摘要（需 gitignored 完成物）
  ```
  实跑输出首行：`语料代次：sha256=ac14c3b0…26edb（SHA256SUMS 全过），判分身份串 mpl-raw-greedy-768;corpus=ac14c3b0abfa`；汇总行：`格 98（15516 道题）：50 格改变分数，151 题翻转 (0.973%)`。

### res21 替代建议：py 用钉住语料的值取代旧值（旧值留作 superseded），代价与影响面都是有限的

- **建议：取代，不是并存。** 理由按 `a13` 的先例（官方判分器取代自研匹配器）：语料是判分器的输入，可复现的那一代应当是真值；两个同名列并存只会招来挑数。**但取代的是「同一批完成物 × 钉住语料」这个测量**，不是重新生成完成物——后者 98 格 × ~8 GPU 分钟 ≈ 13 小时，而重评是纯 CPU 且确定性（res15/res19）。
- **这个身份是混合的，必须写明**：完成物是在**旧**语料的 prompt 上生成的，判定用**新**语料的 tests。因为只有 151/15516 道题翻转（0.973%），prompt 侧没有实质变化；但「旧生成 × 新真值」这句话必须进协议串，不能只说 `corpus=…`。建议串：`mpl-raw-greedy-768;corpus=ac14c3b0abfa;gen_corpus=pre-2026-10-14`。
- **§13（逐语言表）会动的数字**：受影响 50 格里 18 格在库里唯一配对、30 格多重配对（同一分数落在多行上，不能猜，必须按 `source_file` 逐条对）、2 格不在 §13（`m26` 那两行）。唯一配对的 18 格：

  | 格 | 模型 | 旧 → 新 | 旧 → 新（比例） |
  |---|---|---|---|
  | `m1-qwen4b-q2-py` | Qwen3.5-4B-UD-Q2_K_XL | 57 → 58 | 0.3540 → 0.3602 |
  | `m1-qwen4b-q3-py` | Qwen3.5-4B-UD-Q3_K_XL | 81 → 80 | 0.5031 → 0.4969 |
  | `m10-nem4b-q2-py` | Nemotron-3-Nano-4B-Q2 | 104 → 105 | 0.6460 → 0.6522 |
  | `m10-nem4b-q3-py` | Nemotron-3-Nano-4B-Q3 | 106 → 107 | 0.6584 → 0.6646 |
  | `m10-orn9b-q4-py` | Ornith-1.5-9B-Q4_K_M | 68 → 71 | 0.4224 → 0.4410 |
  | `m10-orn9b-q5-py` | Ornith-1.5-9B-Q5_K_M | 76 → 78 | 0.4720 → 0.4845 |
  | `m10-q38-27b-q2-py` | Qwen3.8-27B-Q2_K_XL | 120 → 122 | 0.7453 → 0.7578 |
  | `m10-q38-27b-q3-py` | Qwen3.8-27B-Q3_K_XL | 118 → 122 | 0.7329 → 0.7578 |
  | `m2-qwen9b-q2-py` | Qwen3.5-9B-Q2_K_XL | 56 → 58 | 0.3478 → 0.3602 |
  | `m2-qwen9b-q3-py` | Qwen3.5-9B-Q3_K_XL | 84 → 87 | 0.5217 → 0.5404 |
  | `m21-bonsai-q2g64-py` | Ternary-Bonsai-27B-Q2_g64 | 123 → 128 | 0.7640 → 0.7950 |
  | `m27-q3-t0.6-py` | Qwen3.5-2B-Q3_K_XL (t0.6) | 44 → 45 | 0.2733 → 0.2795 |
  | `m3-e2b-q2-py` | gemma-4-E2B-Q2_K_XL | 30 → 29 | 0.1863 → 0.1801 |
  | `m3-e4b-q3-py` | gemma-4-E4B-Q3_K_XL | 103 → 102 | 0.6398 → 0.6335 |
  | `m3-gr3b-q4-py` | granite-4.1-3b-Q4_K_M | 49 → 50 | 0.3043 → 0.3106 |
  | `m3-q3-py` | Qwen3.5-2B-Q3_K_XL | 43 → 42 | 0.2671 → 0.2609 |
  | `m3-q36-35b-q2-py` | Qwen3.6-35B-A3B-Q2_K_XL | 112 → 113 | 0.6957 → 0.7019 |
  | `m3-q5-py` | Qwen3.5-2B-Q5_K_XL | 45 → 44 | 0.2795 → 0.2733 |

- **一处会被看见的结论形状变化**：`m10-q38-27b` 的 Q2 与 Q3 在取代后**都等于 122/161 = 0.7578**（旧值 120 vs 118，即 Q2 高 2 题）。也就是报告里「Q3 比 Q2 略低」这个 1–2 题的形状会变成**打平**。这类 1–2 题的形状在本项目里不止一处（res20 的 7 对），都要跟着改口径。
- **代价**（全部 CPU，不需要 GPU）：
  1. `i02` 入库：98 格（或只入 50 格改动的）新行 + 旧行标 superseded；先做编号备份、跑 `db_check`、核对 skip ledger 为空、行数对账。**这是改库 + 改报告，属需要授权的动作**。
  2. 重生成 `report.html`，§13 的 py 列随之变化（18 唯一 + 30 待按 `source_file` 对）。
  3. `a14` 自己的 27 个 py `testfrac` 文件要按同一代次重算（~12 s/格，≈6 CPU 分钟）并在同一次提交里换掉，否则二元列与比例列会是两代（见 res22）。
- 状态：provisional（**建议**，未执行；执行需要 meta 授权，且入库属 i02）。本节 18/30/2 的配对同样是**库快照**下的结果（见 res24 的 D8 段）：库一涨，「唯一配对」的格数会变，所以 i02 落库时按 `(model, bench, language, protocol_old, n_items)` 重定位并**要求唯一**，不用这组计数当断言。
- 复现：`python3 "docs/subprojects/a14-部分给分/py_regrade.py"` 的最后三行给出 18/30/2 的配对结果。

### res22 `testfrac` 的同一问题：它的分母也来自语料，所以旧比例值带两代

- `testfrac.py::expected_count` 从**语料里的 `tests` 文本**数断言得到分母，所以旧 `testfrac_*.jsonl` 同时带两个代次：(a) **语料代次**（`tests` 文本变了，res16 的 4 道不可达题）；(b) **口径代次**（旧版排除 `assert True`，今天的不排除；res16 的 37 道）。
- 后果：res10–res13 的所有比例数字都是「旧语料 + 旧口径」这一代，内部自洽（二元与比例同代），但**不能与钉住语料下的值混用**；若 py 二元值被取代，这一批比例必须一并重算。
- 重算单价：~12 s CPU/格、0 GPU（res15）；27 个 py 格 ≈ 6 CPU 分钟。
- 状态：current。

### res23 若按 res21 取代：a14 的裁决**不变**，只有绝对水平抬高（中位 +0.027）

- 把 27 个 py 格按「钉住语料 + 今天口径」重算逐测试比例（27 × ~12 s CPU、0 GPU）：**18/27 格二元分数改变**（−2…+5 题），`mean_frac` 改变 **+0.0007…+0.0505，中位 +0.0271**，**27 格里 25 格**的改动 >0.01（同一节里 18/27 用的也是 27 格分母；早先写的 +0.0268 与「26 格里 24 格」是把分母混了）。
- **res10 的「两把不同的尺」不变、还更强**：`mean_frac − pass@1` 的中位从 **+0.1098** 变成 **+0.1324**（新语料对 py 略宽松，比例与二元的距离拉大）。
- **res12/res18 的近差消歧裁决不变**：py 里旧二元差 1–2 题的 4 对，在新代次下「比例能否分开」的判定**逐对一格不改**（1 对分开、3 对不分）；变的只是二元侧的形状：
  - `m3-q3-py` vs `m3-q4-py`：旧 +1 题 → 新 +2 题（比例仍不分，Δ −0.0304 95%[−0.0912,+0.0331]）；
  - `m3-q4-py` vs `m3-q5-py`：旧 +1 题 → 新 **0 题**（多出一对二元打平）；
  - `m3-gr3b-q2-py` vs `m3-q08b-q2-py`：旧 +2 → 新 +2，比例仍**分开**（Δ +0.0716 95%[+0.0158,+0.1217]）。
- 所以取代的代价是**绝对数换一遍**，不是结论换一遍：报告若改写，§13 与 §15 的数字都要动，但 a14 的答案（部分给分不消解二元歧义）不需要重写。
- 状态：current。
- 证据：`docs/subprojects/a14-部分给分/evidence/py_testfrac_regrade.json`（27 格旧/新 pass 与 mean_frac + 语料 sha256）。
- 复现：重算命令 `cd .wrapup && python3 testfrac.py --lang py --samples mres/<tag>.jsonl --out /tmp/tf/<tag>.jsonl`（每格 ~12 s）；对照组读 `.wrapup/testfrac_<tag>.jsonl`。

## 取代执行包（meta 已授权；i02 照 res24 的清单入库）

### res24 入库清单：`evidence/py_regrade_manifest.tsv`，98 格全列（改分 50 + 未改 48，151 题翻转）

- 路径：`docs/subprojects/a14-部分给分/evidence/py_regrade_manifest.tsv`（TSV，一行一格，UTF-8，无时间戳，同样输入永远同样字节）。
- **25 列**（复核 D7 更正两次：早先写 23，实为 24；补上 D8 的 `db_sha256` 后是 25）：`tag, run, bench, language, model, protocol_old, protocol_source, identity_new, n, pass_old, pass_new, score_old, score_new, delta, flips, corpus, gen_corpus, db_rowids, db_match, db_models, db_source_files, db_protocols, db_run_tags, db_sha256, summary_file`。核对：`head -1 …tsv | awk -F'\t' '{print NF}'` → `25`。
- 关键列怎么读：
  - `flips` = JSON 数组，每题一条 `{name, old_status, new_status, old_pass, new_pass}`（例：`HumanEval_103_rounded_avg` 由 `Exception` → `OK`）。**这是 i02 唯一需要照抄的判定差异**，其余列只是给对账用。
  - `identity_new` = `<该格旧协议>;corpus=ac14c3b0abfa;gen_corpus=pre-2026-10-14`。**59/98 行**填上了旧协议（`protocol_source=summary` 50 行、`db` 9 行）；余下 39 行只写两段（缺协议前缀），因为既没有该 run 的汇总文件、同分候选行又跨多个协议——**不猜**。
  - `db_rowids`/`db_match`：库里 (language=py, `_score` == 旧分) 的所有候选行，`unique` 19 / `multi` 73 / `none` 6。库里**没有 artefact 文件名列**，所以这组候选无法再收窄；配对键与 `make_report.py::_eval_status_index` 同口径。`none` 的 6 格**不在库里**（没有可取代的行，例：`m26-q38-27b-q3-py`，这正是 `plan15` 那格，它从未入库）。
  - `bench`：唯一配对时取库里的 `_bench`（如 `humaneval-py`），否则退成 `humaneval-multipl-e`。
- **取代的是什么，写在清单里**：同一批落盘完成物 × 钉住语料的重评，**不是重新生成**。所以身份串两段缺一不可：`corpus=` 说明判定用的真值，`gen_corpus=` 说明完成物是在旧语料上生成的。
- **`db_rowids` 是快照，库是输入之一（复核 D8）**：清单里的 rowid 只在一个库状态（`db_sha256=007bf15c…0d01`，3355 行、其中 16 行协议串已带 `corpus=`）下有效；采样期间库被并发入库改写（py 的 MultiPL-E 行从 117 涨到 136），我先前引用的 rowid 已不存在，同一脚本对活库重算得到 **unique=18 / multi=75 / none=5**（而不是当时写在文档里的 19/73/6）。所以：**「同样输入永远同样字节」里的「输入」必须包含库**，清单里因此带 `db_sha256` 列。结论：**rowid 只能当线索，不能当键**；`i02` 已据此把入库改为按 `(model, bench, language, protocol_old, n_items)` 重定位并要求唯一，不许按 rowid 或分数匹配——本清单的 `model / bench / language / protocol_old / n` 五列就是为这个键准备的（`model` 只在唯一配对时填，空就是空，不猜）。
- 状态：current（`db_rowids` 为 2026-10-21 快照）。
- 复现：`python3 "docs/subprojects/a14-部分给分/py_regrade.py" --manifest`（实跑输出：`写入 …py_regrade_manifest.tsv：98 行（改分 50，未改 48，翻转 151 题）` / `db_match: unique=18, multi=75, none=5` / `db_sha256=007bf15c…0d01（rowid 只在该快照下有效）`）。
- **i02 入库时请注意三条**：① 别按 `score_old` 去改行——那会把同分的别的格一起改掉（73 格是 multi）；用 `source_file`/`db_protocols` 与 ingest ledger 定行。② 旧行不删、标 superseded，新行协议串用 `identity_new`。③ 同一提交里换掉 27 个 py `testfrac` 文件（res22/res23），否则二元列与比例列会是两代。

### res25 7 对跨过结论边界的格子（报告 §13 与 `a06` 的输入）

语料代次改掉的符号，全部落在 1–2 题的近差区：

| 格对（同语言、tag 只差一个字段、同题数） | 旧 | 新 | 形状变化 |
|---|---|---|---|
| `m10-q38-27b-q2-py` vs `m10-q38-27b-q3-py` | −2 题（120 vs 118） | **0 题（122 vs 122）** | Q3 比 Q2 略低 → **打平** |
| `m3-q4-py` vs `m3-q5-py` | +1 题 | **0 题** | 有差 → 打平 |
| `m27-q4-t0.3-py` vs `m27-q4-t0.6-py` | 0 题 | **+1 题** | 打平 → 有差 |
| `m31-q3-tk1-py` vs `m31-q3-tk20/40/64/200-py`（四对） | 0 题 | **+1 题** | 贪心地板与各 top-k 档由打平变有差 |

- **对报告的影响（§13 逐语言表的 py 列）**：`m10-q38-27b` 那对会让「Q3 比 Q2 略低」这类 1–2 题形状变成打平；报告若仍按旧值画排序/写「略低」，就是错的。其余 6 对同理，都属于「1–2 题的形状不成立」这一类，不是分数大幅移动。
- **给 `a06` 的输入**：`m31-q3-tk1` 是 top-k 扫描里的贪心地板（K=1），它与 K=20/40/64/200 的四个「打平」在补入语料代次后**变成每个档都高 1 题**。也就是说 a06 若曾用「K≥20 与贪心无差」这类 0 题差做结论，这条需要在钉住语料下重述；a14 不改 a06 的目录，这条作为输入交过去。
- 状态：current。复现：`python3 "docs/subprojects/a14-部分给分/py_regrade.py"` 输出「语料代次改掉符号的 py 格对：7 对」。

### res26 语料代次（钉住的那一代，以及为什么旧格反推不出代次）

- 校验：`cd .wrapup/prompts && sha256sum -c SHA256SUMS` → **6/6 OK**。
- `humaneval-py.jsonl` 的 sha256 = **`ac14c3b0abfa218c8442807b729acdce30a165d9e2f79b9dfa7bf78e6aa26edb`**；该文件 mtime `2026-10-14 20:51`，于 **`b57a71f`（2026-10-19）** 被钉进仓库（提交信息就叫 "pin the prompt set"）。
- **该代次下 `HumanEval_79_decimal_to_binary` 的期望值**：`candidate(0) == "db0db"`、`candidate(32) == "db100000db"`、`candidate(103) == "db1100111db"`、`candidate(15) == "db1111db"`，外加一条 `assert True`（调试用填充）。那批完成物 4 条取值断言全过，所以今天判 pass（旧记录是 `Exception`）。
- **旧格无法反推它当年用的是哪一代**：任何入库产物都没有语料哈希列；2026-10-14 之前的 `/tmp` 副本已不在盘上。唯一残留指纹是分母样式——用「排除 `assert True`」这条口径在**今天**的文本上重算，161 题里 **157** 题与入库分母吻合（今天的口径只吻合 121 题），**4** 题在任何口径下都推不出来（res16 表格）。所以只能说 **旧格 ≠ 这一代**，说不出它是哪一代。
- 状态：current。复现：`sha256sum -c` 那行 + `python3 "docs/subprojects/a14-部分给分/py_regrade.py"` 的首行（打印语料 sha 与身份串）。

## 不可得清单与代价（WP6）

### res17 只能靠一条命令查：`testfrac_audit.py --matrix` 逐族给出「能不能推 / 缺什么 / 代价 / 拿到后怎么验」

- 七行：MultiPL-E 四语（可得，代价 0）、MultiPL-E `rs/rb/pl`（不可得，每门语言 ≤60 CPU 分钟、0 GPU）、EvalPlus（部分，≤30 CPU 分钟、0 GPU）、lm-eval ifeval（可得且已得，0）、lm-eval gsm8k/mmlu/arc（不可得，GPU ≥11 分钟/格）、BFCL（不可得且不做）、以及「新增一个 MultiPL-E 格的比例」的单价。
- **单价（实测）：~12 s CPU / 格、0 GPU**（res15），前提是完成物已落盘且测试语料被钉住。所以 a14 的轴不需要 GPU 预算；本会话 GPU 用量 **0 分钟**。
- 状态：current。复现：`python3 "docs/subprojects/a14-部分给分/testfrac_audit.py" --matrix`。

## 裁决（服务里程碑第 3 条）

### res18 更细的 Y 成立，但它**不**自动把二元 Y 留下的歧义消掉；它换了一种歧义，而没有消除

逐问作答（只限上述可得范围）：

1. **哪些基准能从既有产物推出逐测试比例**：MultiPL-E `cpp/js/py/java` 四语 —— 78 格、12540 道题已经算好并在仓库里；`ifeval` 的 `inst_level_strict_acc` 本来就是指令级比例（每份都有的不变量，份数随产物增长：初写 106、复核 108）；EvalPlus 在 dataset 分母到手后可算（≤30 CPU 分钟，0 GPU）；`rs/rb/pl`、`gsm8k/mmlu/arc_challenge`、`BFCL` 不可得（原因与代价见 res17）。
2. **排序变了多少**：基本不变。按语言 Spearman **0.888–1.000**；108 个「只差一个字段」的配对里 **7** 对符号反转（6.5%）。但两个 Y **不在同一把尺**上：比例恒相等或更大，中位位移 **+0.114**（最大 +0.238）。所以「更细」带来的是均匀抬高，不是重新排序；把一个表里的数换成另一个而不改解读，就是错的。
3. **歧义是否减少**：**没有稳定减少**。二元只差 1–2 道题的 9 对里，比例在 95% 配对区间下只分开了 **3** 对，其中 **1** 对与二元结论**相反**；而二元完全并列的 2 对，比例**一对也没分开**。同时，在同一批题上比例的题间 SE 与二元比中位 **0.96**、**28/74 格 ≥1** —— 「每道题 ~7 条测试」带来的不是 7 倍信息，而是一条函数写错就整道题全错，所以分母变大而有效样本量没怎么变。
4. **更细的 Y 在哪里反而更差**：采样。`i01::res30` 已实测 temp=0.3 下逐题通过集 Jaccard **0.53–0.67** 而分数只摆 **6/164**；逐测试比例比二元更依赖**同一批完成物**，所以它在 temp>0 下的跑间噪声只会更大（本项目的跑间噪声**未测**，代价见 res17）。判分侧则相反：重跑逐字节相同（res15）。

一句话：**二元 Y 丢的是「差多少」这个量，而不是「谁更好」这个排序；换成逐测试比例能得到一个 0–1 的连续量、能让阈值型比较（例如「距离目标分数还差多少」）稳定，但当两个设置真的挤在 1–2 道题上时，比例并不比二元更会分辩它们，而它自己的采样噪声更大。**

服务哪条 AC：`docs/plan/subprojects.md` a14 的「与二元判分的对照结论及其噪声」。噪声部分：判分侧已实测为 0，采样侧**未测**并给了代价，不算成立。

- 状态：current。

## 待办事实（本文件还没有的，就是还没测）

- `WP4` 的采样侧：比例在 temp>0 下的**跑间**噪声——**未测**。盘上没有任何一个格的重复生成带逐测试比例（重复测量只有二元，`i01-slot-np1-p{1,2}`、`npauto`×2）；代价是每格至少 2 次生成（`m1` 级模型 ~8 GPU 分钟/次，与 `i01` 的实测同量级）。
- 修「测试语料没被钉住」（res16）不属于 a14 的 AC：需要把产出每一批逐题比例的语料哈希记在文件旁边并在检查里校。仓库已有 `.wrapup/prompts/SHA256SUMS`，但没有任何东西记录「哪一批文件用了哪个哈希」。这条交给 meta/i02。
