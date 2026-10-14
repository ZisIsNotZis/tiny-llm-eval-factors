# 名字与约定

> 层级：**L1 客观规范/事实**（名字、术语、禁用词、协议、run_tag）。

## 有效位宽（effective bpw）—— 量化唯一的横轴

```
有效位宽 = 8 × GGUF 文件字节数 ÷ 参数量
```

来源文件：`.wrapup/bpw_map.json`（键 = GGUF 文件名），由 `.wrapup/gguf_params.py` 生成。

**绝不用标称标签当横轴**：`Q2`/`Q3` 之类的标签在不同模型上实际是 2.76–5.04 bpw，
用它们当横轴会让不同家族不可比。凡是横轴是量化的地方，一律用有效位宽，保留两位小数。

## 模型文件命名与家族

- 模型文件 = `家族-版本[-类型]-<量化后缀>.gguf`。
- **家族（family）** = 去掉量化后缀后的名字。同一个家族 = 同一套 base 权重，这是"家族内对照"的基础。
- **量化后缀** 例：`UD-Q2_K_XL`（unsloth dynamic K 系列）、`UD-IQ3_XXS`（imatrix/IQ 系列）、
  `UD-TQ1_0`（三元）、`Q2_0_g64`（Bonsai 三元）、`Q1_0`。
- **MoE 模型**：家族名里带 `A<激活参数>`，如 `Qwen3.6-35B-A3B`（35B 总参、3B 激活）。

## 基准列（列序固定，永不删列）

| 列键（DB `_bench`） | 报告列名 | 任务类型 | 工具 |
|---|---|---|---|
| `humaneval` / `humaneval-plus` | HumanEval / HumanEval+ | 代码 | EvalPlus 0.3.1（全 164 题） |
| `mbpp` / `mbpp-plus` | MBPP / MBPP+ | 代码 | EvalPlus 0.3.1（全 378 题） |
| `humaneval-<lang>`（cpp/py/java/js/rs/rb） | 多语言代码（MultiPL-E） | 代码 | MultiPL-E，原始补全，每语言 155–164 题 |
| `mmlu` | MMLU | 知识（选择题） | lm-evaluation-harness，对数似然打分 |
| `arc_challenge` | ARC-Challenge | 科学常识（选择题） | 同上 |
| `truthfulqa_mc2` | TruthfulQA | 事实性（选择题） | 同上 |
| `gsm8k` | GSM8K | 算术推理 | lm-eval，贪心生成 |
| `ifeval` | IFEval | 指令遵循 | lm-eval，贪心生成 |

## 协议名（`protocol` 列）—— 每一条都必须能唯一定位一次测量

| 协议 | 含义 |
|---|---|
| `multipl-e-raw-greedy-768` | MultiPL-E，原始补全，贪心，max 768 tokens（规范列） |
| `mpl-chat-nothink-greedy-768` | MultiPL-E，聊天模板，关思考，贪心 |
| `evalplus-0.3.1-openai-chat-greedy-plus` | EvalPlus，聊天，贪心，`+` 严格变体 |
| `lmeval-0.4.13-gguf-shim-reasoning-off` | lm-eval，对数似然，走回显 shim，关思考 |
| `lmeval-0.4.13-chat-reasoning-off` | lm-eval，聊天生成，关思考 |
| `bfcl-native-tools-nothink-greedy` | BFCL，原生 `tools=` 工具调用 |
| `bfcl-prompt-nothink-greedy` | BFCL，提示式（已被上面取代，历史保留） |
| `mpl-raw-t<temp>-768` / `mpl-raw-greedy-768;topk-...` | 采样/KV 等变量面板 |

**同一张表里绝不能混协议**（协议本身会让量化结论翻号，见 `L2-结果.md` F8）。

## run_tag（来源键）

每次测量必须带 `run_tag`（形如 `m<编号>-<描述>`，如 `m140-qat-gemma12b-q4`）。没有 `run_tag` 的数字视为无效。

## 特殊状态词

- `无结果` / `NO RESULT`：harness 没产出分数（崩溃/OOM/超时/无结果文件）。**绝不是 0 分**。
- `BLOCKED-on-VRAM`：显存不足没跑成（如 31B），非测量、非 0。
- `GATE-FAIL`：模型在本机运行时加载不了（如 `diffusion-gemma` 架构），非测量。
