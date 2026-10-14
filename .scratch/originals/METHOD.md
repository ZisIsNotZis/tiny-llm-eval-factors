# 研究方法（唯一规范；与本文冲突时，先改本文再执行）

> 层级：**L1 客观规范/事实**（研究方法与测量协议）。

## 1. 要回答的问题

**量化如何映射到"实测任务分数"**——跨模型规模、模型类型（dense/MoE）、架构、任务类型与解码方式，
在受控协议下。非目标：排行榜、产品推荐、自我训练、以 PPL 为目标（PPL 只作参考）。

## 2. 什么算一个结果

- 结果是一个**带不确定性的差异**，不是点估计。
- **显著性按题目级**：一道题是一次伯努利试验，`SE = √(p(1−p)/n + p'(1−p')/n')`。
  按语言/类别算的 CI（n=2–5）会窄约 10 倍，已因此产生过两个假结论。
- 每个数字必须带 `run_tag`。无来源的数字作废。
- 同时报告**地板**：同一配置跑两次即该轴的噪声（agentic ≈ ±0.015；贪心代码 = 0）。低于地板的差异是噪声。
- **负结果与 null 是一等结果**；CI 很窄的 null 就是发现。

### 2b. 数据契约：只记录发生了什么，不做解释

| 发生了什么 | 写什么 |
|---|---|
| harness 产出了分数 | **原样写分数**（0.0 是一个值，不是错误） |
| harness 没产出分数（崩溃/OOM/超时/无结果文件） | **`无结果`**，别的什么都不写 |

**禁止**（这些是 agent 发明的，不属于本研究）：字节相同即判失败、输出格式检查、类别互相矛盾即判失败、
截断启发式。pass 就是 pass，fail 就是 fail，按 harness 的判定。

## 3. 基准：只用标准套件，且多于一种任务类型

**规则（operator）：任何结论不能只建立在一类任务上。每条存活的结论必须在至少两个基准家族上测过
——代码 _和_ 知识/推理 _和_ 指令遵循。** 只在代码上成立的量化结果是代码 harness 的发现，不是量化发现。

| 家族 | 基准 | 题数 | 工具 |
|---|---|---|---|
| 代码 | HumanEval / HumanEval+ | 164 | EvalPlus 0.3.1 |
| 代码 | MBPP / MBPP+ | 378 | EvalPlus 0.3.1 |
| 代码 | MultiPL-E（cpp/py/java/js/rs/rb） | 每语言 ~160 | MultiPL-E |
| 知识/推理 | MMLU（57 科） | 14042 | lm-evaluation-harness |
| 推理 | GSM8K | 1319 | lm-evaluation-harness |
| 指令 | IFEval | 541 | lm-evaluation-harness |
| 知识 | ARC-Challenge | 1172 | lm-evaluation-harness |
| 事实性 | TruthfulQA（mc2） | 817 | lm-evaluation-harness |

已退役、仅作历史保留：BFCL 单轮/多轮（含 `miss_func`/`miss_param`，它们是 BFCL 子类别不是独立基准）、
`testfrac`、`fa-probe`。

## 4. 测量协议（每一行都是用一次测量换来的）

| 设置 | 取值 | 为什么 |
|---|---|---|
| 运行时 | `llama-server` build 4399（commit 4bc272fd72） | 我们所有 gguf 都能加载的唯一运行时；同一基准内混运行时会把量化效应和反量化 kernel 混在一起 |
| 上下文 | `-c 8192 -np 1` | 够 5-shot GSM8K + 完整生成长度 |
| 生成解码 | 贪心，`max_gen_toks=1024`，聊天模板，5-shot，`fewshot_as_multiturn=True` | 只让权重变化。GSM8K 对协议极敏感，此默认是测过替代方案后选定的 |
| gsm8k 指标 | `exact_match,flexible-extract` | `strict-match` 要求字面 `#### N`，量的是"格式对不对"而非"算术对不对"（同一次运行：IQ3_XXS strict 0.01 / flexible 0.52）。strict 存为独立列 `gsm8k-strict` |
| 思考 | 一律 OFF | 开思考时 IFEval 跌到 0.00（指令检查器看到推理流），且每项 27s vs 5s。开思考的 gsm8k 只作诊断轴（`reasoning='on'`），永不并入主列 |
| 对数似然传输 | 精确回显 shim（`.wrapup/lmeval_run.py`） | 该构建静默忽略 `echo`，只返回新构造的 `logprobs.content[*]`；shim 从 `top_logprobs` 读真 logprob，**拒绝猜测** |
| 网络 | `HF_HUB_OFFLINE=1` 等 | 一次 DNS 抖动曾让 mmlu 返回 null（缓存完好） |
| 代码 | EvalPlus 0.3.1 全 164/378 题 | 公布口径是全量；pass@1 从 `eval` 字典算并记录分子 |
| 限制 | `--limit 100`；`--limit 16`（MMLU 每科） | MMLU 的 limit 是**每科**（57 科），共享 limit 会饿死其它任务或把 MMLU 放大 57 倍 |

## 5. 协议纪律（每条都因真实 bug 而立）

1. **每条结论必须写明生成协议**：原始补全 vs 聊天 vs 原生工具；强制 JSON vs 原生调用。协议本身已两次翻转量化结论的符号。
2. **绝不混协议**。
3. **判分方言必须匹配模型的工具调用方言**。`0.00` 先怀疑 harness（每槽上下文、是否用 FC handler、是否在重算陈旧结果）。
4. **每槽上下文**：BFCL 多轮提示可达 ~100k tokens；`-c N -np K` 每槽只有 `N/K`。按观测到的提示长度设，不要猜。
5. **除非采样就是变量，否则用贪心**；始终记录 temp/top_p/top_k/min_p/penalty。
6. **同一时刻只有一个 GPU 任务**，用 `flock /tmp/llama_gpu.lock`（`.wrapup/gpu_locked.sh`）串行。面板不得遗留自己的 server。
7. **绝不改上游项目**（llama.cpp、BFCL、EvalPlus）；需要新特性就另建目录。

## 6. 如何选下一个实验（最大信息增益，不暴力搜索）

```
价值 = (对存活问题不确定性的降低) × (触达的待解问题数) / (GPU 秒 × 新风险)
```

优先级：① 解决一个矛盾或可疑数字；② 跨一个没跨过的边界（新模型类型/方案/任务类型）；
③ 缩小头条结论的 CI（加题目/语言，而不是重复同一跑）；④ 补来源洞（无法再推导的数字）。
明确降级：为加一行而在新尺寸重复已有轴；handler 方言未验证的面板；价值未证就要新工具链的事。

## 7. 委派与防空转（曾因 GPU 空转 9.5 小时）

- 一个 GPU 任务串行，并行只在"worker 启动 detached 后立即返回"时有用。
- worker **绝不阻塞在 GPU 锁上**：写好脚本、排在当前持有者之后、`setsid nohup … &` 启动、短暂轮询、写状态行、结束本轮。
- 每个面板结束时测试其后继是否完成，未完成则自行启动它（`chainN.sh` 模式）；队列状态落在 `QUEUE` 文件，不落在 session。
- 结束一批前确认：`ps` 有活的锁持有者 **或** 下一个队列项已 armed。
- **绝不用文本存活门**（`pgrep -f "<脚本名>"`）：它会匹配任何命令行里提到该名字的进程，也会匹配别的项目的进程，
  已造成三次误判。存活只由 `flock -n /tmp/llama_gpu.lock` 或日志中的完成横幅判定。
