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
- **例外**：`ifeval` 天然是细粒度的——它同时报 `prompt_level_strict_acc`（题级，等价二元 Y）与 `inst_level_strict_acc`（指令级，等价「逐测试比例」）。**106 份 `lmeval_ifeval_*.json` 里 106 份都含 `inst_level_strict_acc`**，所以对 ifeval 来说更细的 Y **已经在库里，零成本**。实测同一格 `m100-qwen38-27b-q3kxl`：题级 0.75、指令级 0.8405。
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
      ev=f'.wrapup/mres/{key}_eval.json'
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
- 实跑输出：`产物：MultiPL-E 322 份 / EvalPlus 4 份 / BFCL 15 份；逐测试比例逐题文件 78 格 12540 道题` / `检查1 二元一致性：配上的格 76，逐题比较 12218 道，不一致 0 项` / `检查2 分母在场：缺 n_tests 的逐题记录 0 条` / `检查3 ifeval 指令级指标：106 份产物中 106 份含 inst_level_strict_acc` / `RESULT PASS`，`EXIT=0`。
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

- 76 个格的 `mean_frac - pass@1`：74 格为正、2 格为 0（那两格是 `m3-g12b-q2-cpp/java`，161/158 道题全不过、比例也是 0），最小非零 **+0.0062**，最大 **+0.2381**（`m1-qwen4b-q2-js`），中位 **+0.1138**。
- 读法：比例高不是「模型更强」，而是「过一部分测试比过全部测试容易」。所以两个 Y **不能互换填进同一张表**，也不能把比例的增量当成质量增量。
- 状态：current。
- 证据/复现：`python3 "docs/subprojects/a14-部分给分/rank_compare.py"` 的「## 1" 表（§ 列 `Δ比例-二元`）。

### res11 排序基本不变：Spearman 0.888–1.000，108 对里 7 对符号反转

- 按语言（不池化）：`cpp` 29 格 **0.9622**、`js` 15 格 **0.8883**、`py` 26 格 **0.9636**、`java` 6 格 **1.0000**（`pass@1` vs `mean_frac`）。
- 配对规则：同语言、同题数、tag 只在**一个**连字号位置不同（即只改了一个命名字段的两个设置），共 **108** 对；其中 **7** 对符号反转。
- 反转不是均匀散布，而是集中在近差对（见 res12）：7 对里有 4 对的题数差 ≤2。
- 状态：current。复现：同上脚本的「## 2」「## 3」两节。

### res12 更细的 Y **没有**把二元 Y 留下的歧义消掉：9 个近差对里只分开 3 对，且其中 2 对与二元结论相反

- 近似并列（题数差 1–2）= **9** 对：比例同向 **5** 对、反向 **4** 对。
- 用逐题配对 bootstrap（2000 次，逐题比例差）看这 9 对：**只有 3 对**的 95% 区间不含 0，其余 6 对分不开。3 对里 2 对是反向的：
  - `m3-e4b-q3-js` vs `m3-gr3b-q3-js`：二元 −1 题（−0.0062），比例 **+0.1075**，95% [+0.0138, +0.2038]，题级 51 正/42 负；
  - `m3-gr3b-q2-py` vs `m3-q08b-q2-py`：二元 +2 题（+0.0124），比例 +0.0576，95% [+0.0038, +0.1093]，47/28；
  - `m3-g12b-q2-cpp` vs `m3-g12b-q3-cpp`：二元 +2 题，比例 +0.0186，95% [+0.0016, +0.0404]，题级 **5 正/0 负**（两格都近乎全错，这一对的「分开」靠 5 道题的部分分）。
- **二元并列（题数完全相同）的配对只有 2 对，且比例在这 2 对上都没有分开（95% 区间含 0）**。所以「二元打平、比例能分」这种情况在本批数据里**未观测到**。
- 比例并列而二元不同的对：**0** 对。
- 状态：current。复现：同上脚本的「## 3」节（`近似并列` 段）。

### res13 同一批题上，比例的估计标准误并不比二元小：比值中位 0.96，最差 1.76

- 逐格比 `SE(mean_frac)`（题间 bootstrap/√n）与 `SE(pass@1)`（二项）：74 个可算格里比值中位 **0.96**，最小 **0.66**，最大 **1.76**；**28 格比值 ≥1**（比例反而更粗），**26 格 <0.9**。
- 读法：比例的精确度收益是**偶然的、按格变化**的，不是系统性的。原因在结构：一道题内部 ~7 条测试并不是 7 个独立信息——一条函数写错通常让该题全部测试一起失败，所以分母变大了但有效样本量没怎么变。
- 这是**题间**不确定性，不是跑间噪声；跑间噪声另计（见「待办事实」）。
- 状态：current。复现：同上脚本的「## 4」节。

### res14 排序对照的负控成立：把比例在同语言内打乱，反转从 7 对升到 50 对、Spearman 掉到 0.06–0.14

- `rank_compare.py --negative-control` 做的是一次**已知错误的副本**：保留 `pass@1`，把 `mean_frac` 在同语言的格之间随机重排（不可以用「在题间打乱 frac」，那个变换保均值，平均比例一点不变，测不到东西——这正是本文第一版的缺陷，已改）。
- 实跑：反转 **7 → 50** 对；Spearman `cpp 0.962→0.099`、`py 0.964→0.144`、`js 0.888→0.059`、`java 1.000→−0.257`。所以 res11/res12 的那些数确实依赖比例的真实取值，不是结构自带的。
- 状态：current。复现：`python3 "docs/subprojects/a14-部分给分/rank_compare.py" --negative-control; echo EXIT=$?`（实跑 `EXIT=0`）。

## 待办事实（本文件还没有的，就是还没测）

- `WP3`：同完成物上二元排序 vs 比例排序的反转清单；逐题配对差的中位数与符号计数。
- `WP4`：判分侧重跑确定性（同一格两次 `testfrac.py` 逐字节相同）；采样侧比例噪声（若无可复用重复测量，写未测 + 代价）。- `WP5`：二元并列 / 差 1–2 题的格对里，比例是否把它们分开。
