# EvalPlus 判分审计（humaneval / humaneval-plus / mbpp / mbpp-plus）

审计对象：`.wrapup/evalpy` 里的 evalplus 0.3.1（`evalplus.codegen` 写完成物、`evalplus.evaluate` 判分）。
复现整份审计（退出 0 = 每条预期都成立）：

    .wrapup/evalpy/bin/python "docs/subprojects/i01-判分与基准有效性/audits/evalplus_audit.py"

方法：构造判定已知的完成物，过真实判分路径，逐条断言。它不是一个「读代码觉得没问题」的结论：
审计里每一条都是实际输出，且负控两侧都测（错的要判错、对的要判对）。

## Q1 剥不剥 markdown —— 判分器不剥，后处理在写完成物那一侧

- 判分器 `evalplus.evaluate` **完全不后处理**：它把 samples 文件里的 `solution` 原样 `exec`（`evalplus/eval/__init__.py::unsafe_execute`）。后处理只存在于写入侧 `evalplus/codegen.py:89`，写入前对每条完成物调一次 `evalplus.sanitize.sanitize()`，并同时落一份 `.raw.jsonl` 原始完成物。
- 因此「围栏会不会被剥」取决于这条 rollout 走没走 `evalplus.codegen`，而不是取决于判分器。实测：把一份**正确**的 fenced 完成物直接交给判分器 → `plus_status=fail`；同一份先过 `sanitize()` 再判 → `plus_status=pass`。
- `sanitize()` 不是「剥围栏」，它做的是「按语法有效的最长行跨度取块（`code_extract`）+ tree-sitter 只保留 import / 函数定义 / 赋值节点（`extract_target_code_or_empty`）」。围栏与散文因为不是合法 Python 而被隐式丢弃，代价是**只要块内有非 Python 文本，抽取就可能取到错误的块**。
- 这不是理论风险，实际发生：拿库里一个真实 cell 的 8 个任务比 `.raw.jsonl` 与 sanitized `.jsonl` 的判定，**5/8 变了**（`HumanEval/0、2、3、4、7`：raw=fail → sanitized=pass）。也就是说这条链路上后处理承担了 62% 的通过量；任何绕过 `codegen` 写入的 rollout（例如本仓库 MultiPL-E 用的 `mpl_run.py` 自研后处理、或手工 ingesting 原始完成物）都会在这些格上少算分。`RESULT.md::res20` 的围栏缺陷就是同一类问题的另一个实现。

## Q2 保不保缩进 —— 保留，且不修复模型写出的错缩进

- `sanitize()` 按 AST 节点的原始字节范围拼接，最后只对整个块做一次 `.strip()`，所以**函数体内的缩进原样保留**；`code_extract` 也是整行拼接，行首缩进不丢。
- 实测：把正确函数体的每一行缩进削到第 0 列（MultiPL-E 的失败签名，`RESULT.md::res21`），直接判分与先过 `sanitize()` 两条路都是 `plus_status=fail`；整体多缩进一层同样是 `fail`。结论：判分路径不重排缩进、也不吃缩进，错缩进的完成物会被判错——这既是「保留缩进」的证明，也是「判分器不会替模型把函数体摆正」的证明（后者正是 res21 撤回那条因果时需要的半个证据）。

## Q3 记不记状态直方图 —— 记逐题状态，但不记直方图、也不存 pass@k

- `*_eval_results.json` 的顶层只有 `date / hash / eval`；`pass_at_k` 只打印到日志、**不保存**（`.wrapup/collect_scores.py` 的注释与本次实测一致），所以库里每个 EvalPlus 分数都是事后由状态重算的。
- 逐题状态是可靠的：每个任务存 `base_status` / `plus_status`，取值 `pass / fail / timeout`（没有 MultiPL-E 那种 `Exception / SyntaxError` 分桶）。直方图要现算：

      jq -r '[.eval[][]|.plus_status]|group_by(.)|map({(.[0]):length})|add' <cell>_eval_results.json

- 也就是说 Q3 的回答是「记逐题状态，但不记汇总，且没有『这一格到底跑成了没有』的独立字段」——一格全 `timeout` 与一格真 0 分在文件里长得一样，只能靠直方图分辨（`RESULT.md::res17` 在 MultiPL-E 上踩的就是这个坑）。

## Q4 坏完成物能不能被打成可信的数字 —— 在 1/378 个任务上可以，而且是上游有意为之

- 负控两侧都在同一批里测到了：`wrong_body`（`return None`）、`empty`、fenced、散文包裹，在 HumanEval+ 的 5 个任务上全部 `fail`；`canonical` 与过 `sanitize()` 的 fenced 正确解全部 `pass`。所以判分器对正常任务是有鉴别力的。
- **例外**：MBPP+ 给 3 个任务的 oracle 只检查「输出不是 None」（`evalplus/eval/_special_oracle.py::MBPP_OUTPUT_NOT_NONE_TASKS` = `Mbpp/737、787、794`），实现是 `exp == (out is not None)`。这让「什么都不做、只 `return None` 的函数体」在 plus 测试的期望全为 False 的任务上**整格判过**：实测 `Mbpp/787` 的 101 条 plus 测试期望全为 False，`return None` 的坏体拿到 `plus_status=pass`（同一批里 `Mbpp/737 / 794` 的期望含 True，所以坏体仍判 fail；两条预期的判定由基准真值推导，不是手写）。
- 另外 7 个任务的 oracle 退化为集合相等（`MBPP_OUTPUT_SET_EQ_TASKS`：`Mbpp/2、7、111、140、232、249→非本版、579、769`），顺序不敏感；`are_equivalent` 的 `exact_match or True` 在本数据集版本里**不存在**（实测为空集），所以「恒真 oracle」这一条不成立，不能沿用旧说法。
- 结论：MBPP+ 的分数在 378 个任务里有 1 个能被「永不做事的函数」拿满，另有 3 个只看 None-ness、7 个只看集合相等。这个量级不足以推翻 MBPP+ 作为聚合指标，但任何单格结论（尤其低分格的差）都必须避开这 11 个任务，或者显式说明它们被算进来了。

## 这一份审计的负控是否真的能失败

- 正控：`canonical` 5/5 `pass`——证明「判对」这一侧在跑。
- 负控：`wrong_body / empty / fenced_direct / prose_direct / body_at_column_0 / body_over_indented` 共 30 条全部 `fail`——证明「判错」这一侧在跑。
- 反向控（假阴性方向，res20 的教训）：fenced 正确解直接判分 → `fail`，过 `sanitize()` → `pass`——证明审计能看见「合法完成物被判错」。
- 会失败的自检：把任何一条预期的 `expected` 反过来，脚本退出码就变成 1 并打印那条；`SUMMARY: 0 expectation(s) diverged` 是可失败的结论，不是恒真断言。本次实跑：`exit=0`，45 条 HumanEval+ 预期 + 9 条 MBPP+ 预期全部成立。
