# lm-eval 判分审计（mmlu / arc_challenge / gsm8k / ifeval / truthfulqa_mc2）

审计对象：lm-evaluation-harness **0.4.13**，装在本仓库 `.wrapup/lmenv`（`lm_eval` 包在 `.wrapup/lmenv/lib/python3.12/site-packages/lm_eval`），任务定义在 `.../lm_eval/tasks/{gsm8k,ifeval,truthfulqa,arc,mmlu}/`；入库口径在 `migrate_db.py::PRIMARY_METRIC`。

复现整份审计（退出 0 = 每条预期都成立；2 = 有任务没加载出来，算未测不算通过）：

    HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .wrapup/lmenv/bin/python \
        "docs/subprojects/i01-判分与基准有效性/audits/lmeval_audit.py"

方法：用 harness 自己的 `TaskManager`/`get_task_dict` 载入任务定义（所以指标名、filter 链、`doc_to_target` 都是实测的那一套），把手造的完成物过**真实的** `FilterEnsemble.apply` 与 `task.process_results`，逐条打印结果并断言。不起模型、不占 GPU——审计的是判分，需要 GPU 才能跑的审计没人会重跑。

## 一页结论：每个任务的分数在什么条件下会失真

| 任务 | 入库指标 | 会失真的条件 | 方向 | 幅度（实测） |
|---|---|---|---|---|
| mmlu | `acc` | 对数似然源对「不在 top-N 的 token」返回 0.0 而不报错；或 4 个选项似然打平 | 打平被 argmax 静默解成下标 0（第一个选项），不报错 | 平局格实测 `acc=0`（目标≠0）；四选一的无知识基线 0.25 |
| arc_challenge | `acc_norm` | 同上，且 `acc` 与 `acc_norm` 是两个不同问题（后者按续写长度归一） | 无知识时落向第一个选项；换归一化会改变排序 | 两侧对照 `acc/acc_norm` 同为 1.0 / 0.0；二者在真实数据上的差 **未测**（库里只存 `acc_norm`） |
| gsm8k | `exact_match,flexible-extract` | 完成物末尾另有一个数字；或答案对但没写 `#### N` | 前者**向下**（取最后一个数字），后者**向上**（strict 会判错、flexible 救回） | 单例实测：`#### 正确值, and 7 is my lucky number` → strict 1.0 / flexible **0.0**；`答案对但无 ####` → strict 0.0 / flexible **1.0** |
| ifeval | `prompt_level_strict_acc` | 空答案、通用废话、只满足格式的填充文本 | 空答案 0；通用答案**向上** | 前 100 条 prompt：空答案 strict 0/100、`"The answer to your question is 42."` **9/100**、300 个 `word` **9/100** |
| truthfulqa_mc2 | `acc` | 该指标是**归一化后的真答案概率质量**，不是命中率 | 无知识模型天然拿地板分，不能读成「答对率」 | 817 条文档上「各选项等概率」的地板均值 **0.4484**；首条 4 选 1 真 → 0.2500 |

## Q1 判分是否后处理 —— 每个任务的后处理位置不同，且都是「正则」而非「理解」

- **gsm8k**：两条 filter 链，`strict-match` = `regex("#### (\-?[0-9\.\,]+)")` + `take_first`；`flexible-extract` = `regex("(-?[$0-9.,]{2,})|(-?[0-9]+)", group_select=-1)` + `take_first`。匹配不到就给 `[invalid]`（`lm_eval/filters/extraction.py::RegexFilter`），`[invalid]` 与任何答案都不相等，所以**「没写 ####」和「答错」在 strict 下不可区分**。随后 `exact_match` 还会按 `regexes_to_ignore`（`,`, `$`, `(?s).*#### `, 句末句点）与 `ignore_case` 归一化。
- **ifeval**：无 filter（`filters: ['none']`），但 `process_results` 会跑两套判定（`test_instruction_following_strict` / `_loose`），产出 4 个指标；入库只取 `prompt_level_strict_acc`。
- **truthfulqa_mc2**：`process_results_mc2` 把各选项似然 `exp` 后归一化，取真答案那部分的概率质量作为 `acc`（`truthfulqa/utils.py:10-24`）。
- **mmlu / arc_challenge**：loglikelihood 任务，没有文本后处理，`acc = argmax(ll) == target`；arc 另算 `acc_norm`。
- 判分器本身**不改写完成物内容**（除了 gsm8k 的正则抽取会丢掉抽取点以外的全部文本）——这一点与 EvalPlus 相反：EvalPlus 的后处理在写入侧、判分器不后处理（`audits/evalplus.md`），lm-eval 的后处理在判分侧、写入侧不后处理。

## Q2 逐题状态是否落盘 —— 不落盘，只有聚合

- `results.json` 只存每任务的指标值与 `configs`；逐题记录要靠 `--log_samples`，而本仓库的 `lmeval_run.py` 没有开它，`.wrapup` 下也没有任何 `samples_*.jsonl` 落盘（实数：0 个文件）。
- 后果一：一格「全 timeout / 全空答案」与一格真 0 分在产物里长得一样，只能靠 `lmeval_run.py` 自己写的 `errors` 与 `null` 区分（这是读代码得到的，本次未实测，见下「未测」）。
- 后果二：`prompt_level_strict_acc` 为 0 时，无法知道是「每条指令都失败」还是「每条 prompt 只差一条指令」——`inst_level_*` 与 `*_loose_acc` 被算出来但没有入库。

## Q3 坏完成物能不能被算成通过 —— 三个可测的向上通道

1. **ifeval 的通用答案通道**：9/100 的 prompt 用一句 `"The answer to your question is 42."` 就满足全部指令（多为长度/句式类约束），300 个重复词同样 9/100。方向向上，幅度约 9 个百分点，且与模型能力无关——它是这个基准在这批 prompt 上的地板。
2. **gsm8k 的无标记通道**：答案对但没写 `####`，在 flexible-extract 下判对（实测 1.0）。这条是**有意设计**（灵活抽取救回正确推理），代价是它同时让「末尾多一个数字」判错：`#### 18, and 7 is my lucky number` → flexible 0.0、strict 1.0。所以 gsm8k 的 flexible 分数既不高于也不低于 strict 的某个固定偏移，而是**逐例双向偏移**，只能按样本对账，不能用一个常数修正。
3. **truthfulqa_mc2 的地板**：0.4484。这个数不是「44.84% 答对」，是「平均有 44.84% 的概率质量落在真答案上」。一个对任何问题都保持均匀的模型就能拿到它；因此 0.45–0.55 区间的任何跨模型比较都在噪声与地板之间，不构成知识类结论。

## Q4 正确完成物会不会被判错 —— 会，且有两个已知形状

- gsm8k `strict-match`：答案正确但没有 `#### N` 标记 → 0（实测）。仓库入库用的是 flexible，所以这条只影响 `gsm8k-strict` 这一额外行。
- ifeval：`strict` 判定对格式极敏感（大小写、句首、标点都算），`loose` 放宽；入库取 strict，所以「内容对但格式差一点」在这一列上是 0 分。严格与宽松在样本外的差**未测**（没有逐题落盘）。

## 无知识基线（结构性，不是缺陷，但必须与结论一起读）

- mmlu 四选一 → 0.25；arc_challenge 四选一 → 0.25；truthfulqa_mc2 → 0.4484（实测均值）。
- 也就是说：mmlu/arc 上 0.25 以下等于什么都不会，truthfulqa_mc2 上 0.45 以下等于什么都不会。报告里任何落在这条线以下的结论都必须说明它低于基线，而不是「有一定知识」。

## 这一份审计的负控是否真的能失败

- 两侧都测到了：gsm8k 的 `empty` / `wrong_with_marker` 判 0，`correct_with_marker` 判 1；truthfulqa 的 `all_mass_wrong` → 0.0、`all_mass_true` → 1.0、`uniform` → 0.25；arc/mmlu 的 `correct_highest` → 1、`correct_lowest` → 0。
- 会失败的自检：把任一条 `expected` 反过来，脚本退出码变 1 并打印该条。本次实跑 `exit=0`，18 条预期成立。
- 曾经真的失败过：审计脚本前两轮先是 `_metric_list` 属性名错、再是 `filtered_resps` 形状错（0.4.13 里它按 filter 名存 dict，而 `.resps` 是「这个 instance 的响应列表」而不是「instance 列表」），两次都以 `exit=2` 明确报「未测」，没有被当成通过——这正是 Q2 那条「没有状态就没有防线」在本审计自己身上的应用。

## 未测（不得当成通过）

1. **`lmeval_run.py` 的 echo shim 是否会返回 0.0**：代码写着「不在 top-N 就升级 N 再不行硬报错，从不返回 0.0」，并有 `--selftest`。本次没跑（需要起 llama-server 占 GPU）。待 GPU 空出后跑一次：

       python3 .wrapup/lmeval_run.py --model /home/z/hf/<某 gguf> --selftest

   在此之前，「对数似然源不会静默给 0.0」只是代码声称（code claim），不是实测。这一条是 mmlu / arc / truthfulqa 三列可信度的关键缺口。
2. **`acc` vs `acc_norm` 在真实数据上的差**：库里只存 `acc_norm`，`acc` 没入库，所以「换归一化会改多少分」未测。
3. **ifeval strict vs loose 在真实数据上的差**：同上，只有聚合、没有逐题落盘。
4. **gsm8k flexible vs strict 在真实数据上的差**：`migrate_db.py::EXTRA_ROWS` 定义了 `gsm8k-strict` 行，但库里当前有 **0 行**（查询：`SELECT count(*) FROM experiments WHERE bench_family='gsm8k-strict'`），所以跨变体的幅度只在单例上测过。
