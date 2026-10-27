# plan4 :: 扩散轴的生成协议 vs 库内对照臂 m144 —— 协议差表与判词

- 日期: 2026-10-27
- 范围: 只读 + 小实验。没有改仓库文件，没有写 `experiments.sqlite`；GPU 只在
  `flock -w 7200 /tmp/llama_gpu.lock` 内用，11 次生成共 ≈2 min 25 s（模型页缓存已热，单次 9–40 s）。
- 二进制: `/home/z/llama-diffusion-pr/build/bin/llama-diffusion-cli`，sha256
  `f47ce12bcf6b1b50a03aa07289870d7354d2ad4742083db3f02e11f6b3ce9b8f`（PR #24423 头 `dd7f73b`）。
- 模型: `/home/z/hf/diffusiongemma-26B-A4B-it-Q4_K_M.gguf` → 符号链接到
  `…/blobs/24523b6c833c9ce9f5f34f9b333ab1517d73d6f1e76a103645353114c8028bc5`，16,806,810,208 B。
  （早期日志行里的 `(147 B)` 是链接本身；已在那几份日志尾部追加更正，第二批日志直接写 `stat -L`。）

## 判词（一句话）

**不同系列；扩散轴的任何分数只能当 reference 数字，不进同 series，也不与 `m144` 逐列相减。**
两条独立理由，任一一条就足以判：
1. **采样器不可对齐**：`m144` 是贪心（`temp 0.0` + `--greedy True` / lm_eval `temperature=0`），扩散臂的原生解码器
   entropy-bound **没有 temperature/top_k 这一套**（`--temp`/`--top-k` 只喂非 EB 路径），它靠固定的
   temperature 调度 `t=[0.4,0.8]`＋随机初始化/renoise 的 canvas 采样；把它改成"逐位置贪心"是存在的
   （`--diffusion-eb off --diffusion-algorithm 4 --temp 0 --top-k 1`），但实测**输出退化成 `"<|channel>thought\n<channel|>️ Correction"`、单块 30.4 s**（EB 是 1.8 s／18 步），不可用于评测。
2. **对照臂本身不匹配位宽**：`m144` 是 QAT 4.5176 bpw，扩散文件是 5.3247 bpw（Δ +0.807 bpw）；位宽最近的是
   `m145`（5.3932，Δ 0.068）而它**从未测过**（`RESULT.md::res4`、`i02/non_measurements.tsv::nm3`）。
   即使明天采样器能对齐，"扩散 vs m144"这一列也是「解码器 + 0.8 bpw」的合流，不是受控对照。

## 一、协议差表（每一项带出处）

对照臂 = `run_tag = m144-qat-gemma26b-a4b-q4`，模型 `gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf`
（8 行：mmlu / gsm8k / gsm8k-strict / ifeval / humaneval / humaneval-plus / mbpp / mbpp-plus）。
库列取值来自 `select … from experiments where run_tag='m144-qat-gemma26b-a4b-q4'`；跑法来自
`.wrapup/lmeval_run.py`、`.wrapup/lmeval_panel.sh`、`.wrapup/codepanel.sh`；判分器来自
`.wrapup/mres/m144-…/lmeval_*.json` 与 `evalplus.json`。

| # | 项 | m144（自回归对照臂） | 扩散臂（llama-diffusion-cli） | 可对齐? | 对"系列"的影响 |
|---|---|---|---|---|---|
| 1 | 运行时/接口 | `llama-server` build 4399 + OpenAI 端点；生成任务走 `/v1/chat/completions`（`.wrapup/lmeval_run.py:436-440`），代码走 evalplus 的 openai 后端（`.wrapup/codepanel.sh:114-116`） | 只有 CLI 进程，无 server（`--help` 无宿主/端口项；`RESULT.md::res13`） | **可对齐**（自写逐题 driver，把 CLI 的输出喂给同一判分器） | 仍可比（只是采集层） |
| 2 | 模型/位宽 | QAT `UD-Q4_K_XL`，4.5176 bpw（`.wrapup/bpw_map.json`；`RESULT.md::res4`） | `Q4_K_M`，5.3247 bpw（`analysis/fixtures/headers.json::bpw_file`） | **不可对齐**（文件不同；位宽最接近的 m145 未测） | **不同系列**（差 0.807 bpw，不是受控变量） |
| 3 | 提示模板 · gsm8k | lm_eval 0.4.13 `gsm8k`，**5-shot**、`fewshot_as_multiturn=true`、`doc_to_text="Question: {{question}}\nAnswer:"`、`--apply_chat_template`（`lmeval_gsm8k_*.json::n-shot=5`、`fewshot_as_multiturn`、`configs`；`lmeval_run.py:436-440`） | CLI 只能表达**一条 user 消息**（+可选 `-sys`）：`apply_template()` 只塞 system/user（`diffusion-cli.cpp:488-497`），无消息数组、无 `--in-prefix`（该组开关只挂在 completion 示例，`common/arg.cpp:1941-1967`） | **不可对齐** | 不同系列（5-shot 与 0-shot 在 gsm8k 上不是同一个测量） |
| 4 | 提示模板 · ifeval | 0-shot、`doc_to_text="prompt"`、`--apply_chat_template`（`lmeval_ifeval_*.json::n-shot=0`） | 0-shot 单 user 消息，模板同一份 GGUF jinja | **可对齐** | 仍可比 |
| 5 | 提示模板 · humaneval/mbpp | evalplus 0.3.1 `OpenAIChatDecoder`：system=`"You are a helpful assistant good at coding."`，user=`instruction_prefix + "\n\`\`\`python\n" + prompt.strip() + "\n\`\`\`"`，`instruction_prefix="Please provide a self-contained Python script that solves the following problem in a markdown code block:"`（`…/evalplus/provider/openai.py:24-31`、`gen/util/openai_request.py:20-33`、`codegen.py:176`） | `-sys` + `-p` 可以逐字节复现同样两条消息；模板同一份 jinja（`diffusion-cli.cpp:242,492-497`） | **可对齐** | 仍可比 |
| 6 | 采样器 | 贪心：`temp 0.0` / evalplus `--greedy True`；lm_eval `--gen_kwargs temperature=0`（`codepanel.sh:116`、`lmeval_run.py:438-439`；DB 列 `temp=0.0`） | entropy-bound：`max_steps=48`、`t=[0.400,0.800]`、`entropy_bound=0.1`、`stability=1`、`confidence=0.005`（`diffusion-cli.cpp:320-331`，实测日志 `protocol-*.log::diffusion_eb:`）；输出 canvas 是**每步 argmax**，但初始 canvas 随机、未接受位置 renoise（`diffusion.cpp:465,644-660`）。`--temp/--top-k/--top-p` 只进非 EB 路径（`diffusion.cpp:139-150`），EB 路径根本读不到 | **不可对齐** | **不同系列**（这是判词的第一根支柱） |
| 7 | 种子 | DB `seed` 列为空；llama-server 默认种子 | `-s/--seed`，默认 `-1`；这里 `-1` 不是"随机"：`std::mt19937 rng(params.seed)` 直接吃 `0xFFFFFFFF`（`diffusion.cpp:465`） → 固定种子 | **可对齐**（两侧都可固定） | 仍可比 |
| 8 | 生成长度上限 | gsm8k/ifeval `max_tokens=1024`；humaneval/mbpp `max_new_tokens=768`（DB 列 `max_tokens`；`evalplus/provider/base.py:13`） | 每块固定 `canvas_length=256`，块数由 `-n` 决定：`blocks = ceil(n/256)`，`n_ctx = blocks*256 + 2048`（`diffusion-cli.cpp:203-215` 实测日志 `diffusion: -n …`）。默认 `--diffusion-blocks 1` → 默认上限 256 | **可对齐**（`-n 1024` → 4 块；`-c 8192` 可显式给） | 仍可比 |
| 9 | 早停/裁剪 | 遇 EOS 停；AR 流没有块边界 | 每块先 `trim_canvas`：首个 EOG **或** 重复循环（stride 1–2、连续 ≥6 次）截断；未截断则整块 256 提交进 prefix，再 denoise 下一块（`diffusion-cli.cpp:386-410,474-479`） | 不可对齐（这是解码器的一部分） | 仍可比（属自变量，但必须在 `protocol` 里写明：它会把代码截在中途，直接影响 pass@1） |
| 10 | thinking 通道 | server 级 `--reasoning off`（`codepanel.sh:82`、`lmeval_run.py:339-340`、DB `reasoning=off`），内容里不留思考（m144 的 humaneval 产出里 thought 块是空的：`<|channel>thought\n<channel|>```python…`，`codegen/humaneval/*.raw.jsonl`） | **没有** `--reasoning/--reasoning-format` 开关（`--help` 全文无此项）；模板不做剥离，思考文本原样进返回串。实测 `1+1=` 返回 `"<|channel>thought\nThe user is asking for the sum of "1+1"…2"`，真 prompt 上 256 token 全被思考吃光、一个代码字符都没出（`protocol-eb-he0.log`） | **不可对齐** | gsm8k/ifeval **不同系列**（库内自测 UD-Q2_K_XL：thinking off→on 把 gsm8k strict 从 0.38 打到 0.06，`lmeval_run.py:66-72`）；humaneval 仍可比（evalplus 用围栏提代码） |
| 11 | ctx / 并行槽 / KV 精度 | `ctx_size=8192`、`parallel_slots=1`、`cache_type_k/v=q8_0`（DB 列） | `-c` 可显式 8192（否则由 `-n` 推出 ≥2304）；`-np` 默认 1；`-ctk/-ctv` 支持 `q8_0`，默认 f16 | **可对齐**（`-c 8192 -np 1 -ctk q8_0 -ctv q8_0`） | 仍可比 |
| 12 | 判分器 | gsm8k：lm_eval `exact_match,flexible-extract`（strict 存独立列 `gsm8k-strict`；`lmeval_gsm8k_*.json::results`）；humaneval/mbpp：evalplus 0.3.1 `pass@1`，base 与 plus 分列（`evalplus.json::benches`） | 无内置判分；但判分器吃的是文本，可完全复用 | **可对齐** | 仍可比 |
| 13 | 题集/题数 | gsm8k 100（前 100/1319）、ifeval 100、humaneval 164（全量，`--limit` 对代码无效）、mbpp 378、mmlu 912 | driver 自选，可指定同题数同子集 | **可对齐** | 仍可比 |
| 14 | 对数似然类基准（mmlu/arc/truthfulqa） | `lm_eval --model gguf` + 精确回显 shim，逐 token logprob（`lmeval_run.py:8-16`） | CLI 不吐 logprob，只吐 canvas token | **不可对齐** | 这类基准在本运行时上**测不了**（不是"不同系列"而是"无格"） |

## 二、确定性（同一提示、同一命令跑 3 次）

命令（三份独立进程，日志 `protocol-det{1,2,3}.log`）：

```
llama-diffusion-cli -m …/diffusiongemma-26B-A4B-it-Q4_K_M.gguf -ngl 99 -no-cnv -p '1+1=' -n 64
```

- 返回串逐字节相同：`<|channel>thought\nThe user is asking for the sum of "1+1".\nThis is a basic arithmetic problem.\n1 plus 1 equals 2.<channel|>2`
  → sha256 前缀 `cb72997455df749d`（124 B）× 3。
- 块内步数也相同：6 steps/1 block（`diffusion_eb:` 行三次一致）；wall time 有抖动（687 / 733 / 699 ms），**文本没有任何抖动**。
- 种子开关存在且是活的：`-s 1234` → 文本变成 `…the sum of $1+1$…`（sha256 `9cd258e6a98c44e9`，`protocol-seed1234.log`）；
  `-s -1` 与不传 `-s` 逐字节相同（`protocol-seed-1.log` = `det1`）。所以默认 `-1` 是**固定种子 0xFFFFFFFF**，不是随机。
- 结论：这条轴在固定命令下是**逐字节确定**的；随机性只由 `-s` 控制，`-1` 只是那个固定值。

## 三、`-n` 对 canvas / 输出长度 / 耗时 / 显存的影响（实测）

| 命令后缀 | 日志算出的块数/ctx | 实际输出 | 步数×块 | 步时 | 峰值显存 | 进程总时长 |
|---|---|---|---|---|---|---|
| `-n 64`  | 1 block, `n_ubatch=n_batch=n_ctx=2304` | 256 token（canvas）×1（早停在 EOG `2`） | 6 steps / 1 block | 113.4 ms | 21,474 MiB | 9.23 s（含 ~8.5 s 加载，页缓存热） |
| `-n 256` | 1 block, 2304 | 同上，逐字节相同（sha `cb7299…`） | 6 / 1 | 122.3 ms | 21,474 MiB | 9.81 s |
| `-n 512` | 2 blocks, 2560 | 同上（第 1 块就早停，第 2 块没跑） | 6 / 1 | 117.5 ms | 21,752 MiB | 9.79 s |

- **`-n` 不是输出长度**：`-n < 256` 依然给一整块 256 token 的 canvas（`-n 64` 与 `-n 256` 完全等价）；
  只有跨过 256 的整数倍才多一块（`-n 512` → 2 块），且多出来的块只有在上一块没早停时才会跑。
- 每多一块，ctx/ubatch 各 +256 token、峰值显存 +278 MiB（21,474 → 21,752）。
- 冷启动（页缓存冷）时加载约 47 s，端到端 57 s（`RESULT.md::res13`）；本次 7 次跑全热，9–17 s。
- 真实 HumanEval/0 提示下单块成本：EB 18 步 × 98.7 ms ≈ **1.78 s/块**（`protocol-eb-he0.log`）；
  非 EB 的"贪心"路径 128 步 × 237.7 ms ≈ **30.4 s/块**，且输出退化（`protocol-greedy-he0-128.log`）。

## 四、逐项判决汇总

- **不可对齐且把两个数变成不同系列**：采样器（#6）、位宽（#2）、gsm8k/ifeval 的 thinking（#10）。
- **不可对齐、但那类基准直接没有格**：#14（mmlu/arc/truthfulqa 需要 logprob）。
- **不可对齐但只影响采集层**：#1（自写 driver 即可）。
- **可对齐**：#4/#5 的 0-shot 提示、#7 种子、#8 长度上限、#11 ctx/KV/槽、#12 判分器、#13 题集。
- 属于自变量（不算协议差，但必须写进 `protocol` 串）：#9 的块提交与循环裁剪、EB 的 48 步/熵界。

## 五、最小可行格（**只作 reference，不进同 series**）

若 meta 只想要一个"扩散臂在这一格上大约什么水平"的参考数，最小、最省、最容易对齐的是：

- 基准：**HumanEval（base）**，`_bench=humaneval`，`n_items=164`（全量；evalplus 对代码不支持子集，`.wrapup/codepanel.sh:5-15`）。
- 理由：0-shot、提示可逐字节复现（`-sys` + `-p` 拼 evalplus 的那两条消息）、判分器可原样复用（evalplus 0.3.1）、
  且不受 thinking 通道伤害（围栏提取）。
- 生成协议（写进 `protocol` 列的建议串，一个新名字，绝不与既有协议串混用）：
  `evalplus-0.3.1-openai-chat-diffusion-eb48-canvas256-blocks4-1024`
  参数：`-ngl 99 -no-cnv -c 8192 -np 1 -ctk q8_0 -ctv q8_0 -s -1 -n 1024`
  （= 4 块 × 256；EB 默认 `max_steps=48 t=[0.4,0.8] entropy_bound=0.1 stability=1 confidence=0.005`），
  `-sys "You are a helpful assistant good at coding."`，
  `-p "<instruction_prefix>\n\`\`\`python\n<prompt.strip()>\n\`\`\`"`。
- 判分：evalplus 0.3.1 的 `base_status`/`plus_status` → `pass@1`，与 `m144` 的 `humaneval` 行同一判分器。
- 预计 GPU：单题 = 预填 ~0.5 s + 1–4 块 × 1.8 s（最坏 48 步 = 4.7 s/块）→ 8–19 s/题；
  **164 题 ≈ 22–52 分钟**（对照：`m144` 同格 codegen 实测 852 s = 14.2 min；扩散侧慢 1.5–3.5 倍）。
  实现成本在 CPU 侧：一个把 CLI 逐题调用写成 evalplus jsonl 的小 driver（无需 GPU）。
- 这一格的结果**只能与 `m145`（5.3932 bpw，未测）或另一个扩散运行时比**；与 `m144` 的 0.9573 相减是
  「解码器 + 0.8 bpw + thinking」三差合流，没有解释力。绝不能把这一格写进按 `protocol` 聚合的标准表。

## 六、证据文件（本目录）

| 文件 | 内容 |
|---|---|
| `protocol_runs.sh` / `protocol_runs2.sh` / `protocol_runs3.sh` | 三批实测脚本（全部在 `flock -w 7200 /tmp/llama_gpu.lock` 内跑） |
| `protocol_runs.status` / `protocol_runs.out` | 每跑的 rc / 峰值 / 时长 |
| `protocol-det{1,2,3}.log` | 同命令 3 次，逐字节相同的返回串 |
| `protocol-det{1,2,3}.mem` | 0.5 s 采样的显存序列 |
| `protocol-n64.log` / `protocol-n256.log` / `protocol-n512.log` | `-n` 实验（1/1/2 块，21,474/21,474/21,752 MiB） |
| `protocol-seed1234.log` / `protocol-seed-1.log` | 种子开关是活的；`-1` = 固定种子 |
| `protocol-eb-he0.log` | 真 HumanEval/0 提示上的原生 EB 输出（256 token 全思考、无代码） |
| `protocol-greedy-he0.log` / `protocol-greedy-he0-128.log` | "逐位置贪心"配置的退化输出与 30.4 s/块 |

## 七、复算

```bash
# 1) 协议来源（对照臂）
cd /home/z/vibe/local_lm_research
sqlite3 -header experiments.sqlite "select _bench,protocol,temp,top_p,top_k,min_p,max_tokens,ctx_size,parallel_slots,reasoning,cache_type_k,n_items,_score from experiments where run_tag='m144-qat-gemma26b-a4b-q4'"
sed -n '79,90p;330,345p;430,445p' .wrapup/lmeval_run.py          # 生成任务协议 / server 启动 / lm_eval 命令行
sed -n '1,20p;70,120p' .wrapup/codepanel.sh                       # 代码面板协议
grep -n 'instruction_prefix\|max_tokens\|top_p' .wrapup/evalpy/lib/python3.11/site-packages/evalplus/{codegen.py,provider/base.py,provider/openai.py,gen/util/openai_request.py}

# 2) 协议来源（扩散臂）
/home/z/llama-diffusion-pr/build/bin/llama-diffusion-cli --help | sed -n '/----- example-specific params -----/,$p'
sed -n '200,215p;240,245p;300,335p;386,410p;455,480p;488,500p' /home/z/llama-diffusion-pr/examples/diffusion/diffusion-cli.cpp
sed -n '130,165p;440,470p;640,670p' /home/z/llama-diffusion-pr/examples/diffusion/diffusion.cpp

# 3) 实测重放
cd .wrapup/axis11-diffusion-retest-2026-10-27
flock -w 7200 /tmp/llama_gpu.lock -c 'bash protocol_runs.sh'
flock -w 7200 /tmp/llama_gpu.lock -c 'bash protocol_runs2.sh'
flock -w 7200 /tmp/llama_gpu.lock -c 'bash protocol_runs3.sh'
```
