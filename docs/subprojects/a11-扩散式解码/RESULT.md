# a11 扩散式解码 — 结果

本文件是 a11 的当前事实。每条事实一个 `## <id> :: <一行话>` 标题，其下的 bullet 是它的坐标：
`kind`、`status`、`from`、`evidence`、`producer`。没有 `producer` 的数字不得引用。
带数字的事实都能用 `analysis/` 里的装置重算；装置的行为由 `run_all.py` 判（见 `res6`）。

## res1 :: 扩散这一轴在本机是「模型在、对照在、缺运行时」：库内 0 行、无产物、两个运行时都在架构查表处非零退出，所以它是 GATE-FAIL（非测量），不是低分。

- kind: citation
- status: current
- evidence: 模型文件 `/home/z/hf/diffusiongemma-26B-A4B-it-Q4_K_M.gguf`（16,806,810,208 B，指向 HF blob `24523b6c833c9ce9f5f34f9b333ab1517d73d6f1e76a103645353114c8028bc5`）；库内该模型 0 行；`.wrapup/mres` 无该模型的任何产物；`llama-server` 与 `llama-diffusion-cli` 都打印 `unknown model architecture: 'diffusion-gemma'` 后退出 1
- producer: `sqlite3 experiments.sqlite "select count(*) from experiments where lower(model) like '%diffusion%'"` → `0`；`python3 docs/subprojects/a11-扩散式解码/analysis/gate.py`
- 对照侧不是空的：同家族自回归 68 行（`res4`），所以缺口只在运行时一侧。

## res2 :: 门槛可复现：两棵 llama.cpp 源码树的架构名表都没有 `diffusion-gemma`（本机二进制所在的 4da6337 有 152 个名字、上游 2026-10-20 的 339f324 有 161 个），而 `gemma4`/`gemma4-assistant` 与四个扩散架构 `dream`/`llada`/`llada-moe`/`rnd1` 都在表里；同一条错话在本机两个运行时上 43 s 内重放出来。

- kind: measured
- status: current
- from: result.res1
- evidence: `analysis/fixtures/arch_tables.json`（两棵树，各带 commit 与 `src/llama-arch.cpp` 的 sha256）；查表失败处的措辞 `unknown model architecture: '` 录在 `src/llama-model.cpp`；`analysis/fixtures/diffusion_gate.json` 里 `verdict = GATE-FAIL`，`llama-diffusion-cli` 与 `llama-server` 两次尝试的 `arch_error` 都是 `diffusion-gemma`、`rc` 都是 1
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/run_all.py --live`（49 条，含 L1 现场重放）
- 这条门槛的含义要读准：**不是**「llama.cpp 不支持扩散解码」（它支持 4 个扩散架构），也**不是**「文件坏了」（`res3`），而是「这一族的键没人实现」。

## res3 :: 失败不是文件坏：该 GGUF 头部可解析（v3、692 张量、30 层、128 专家用 8、非因果注意力、`diffusion.canvas_length = 256`、`tokenizer.ggml.mask_token_id = 4`），参数量 25,250,987,068, 位宽 5.3247 bpw；但**解码回路不在文件里，也不在本机任何运行时里**——它在 `transformers` 的生成代码里（`res12`），读代码可定，我们没读。

- kind: measured
- status: current
- from: result.res1
- evidence: `analysis/fixtures/headers.json` 里该文件的头部，逐张量形状/类型/偏移/字节；`attention.causal = false`、`diffusion.canvas_length = 256` 与词表里的 `mask_token_id = 4` 是「这确实是掩码式块扩散解码器」的三条直接证据
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/gguf_header.py /home/z/hf/diffusiongemma-26B-A4B-it-Q4_K_M.gguf`；夹具由 `python3 …/analysis/record_headers.py` 重取
- 参数量与位宽由张量表独立重算过（`run_all.py` 的 A1/A3 两条），不是从文件名推的；张量集合的差（`res11`）说明这是同一主干加一个解码头。
- 修正（复核指出）：旧写法把「协议未知」当成结论。实际是**读代码可定、我们没读**：`transformers 5.17.0` 的 `generation_diffusion_gemma.py` 里默认 `max_denoising_steps = 48`、块内判据是 `EntropyBoundSampler.accept_canvas`（`res12`）；缺的是权重与许可，不是回路描述。

## res4 :: 对照侧已有一半：同主干自回归双胞胎 `gemma-4-26B-A4B-it-qat-UD-Q4_K_XL` 参数量 25,233,142,046（与 a02 入库真值逐位一致、位宽与 `bpw_map` 一致），与扩散臂只差 +0.0707%；但已入库的 QAT 臂位宽是 4.5176（差 0.807 bpw），位宽最接近的 `UD-Q4_K_XL`（5.3932，差 0.068）正是 nm3 里**未测**的 m145。

- kind: measured
- status: current
- from: result.res3
- evidence: `analysis/fixtures/headers.json` 的双胞胎头部；a02 的 `analysis/fixtures/gguf_truth.json` 里 `n_params = 25233142046`；`.wrapup/bpw_map.json` 里 `4.517565692936376`；nm3（`docs/subprojects/i02-测量基础设施/non_measurements.tsv`）记 m145 为 `BLOCKED-on-VRAM`
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/run_all.py`（C2/C3/C4/C5/C6 四条）
- 结论：即使明天有人实现了这个架构，「位宽匹配的对照」也还差一个未测臂——这是两笔账，不是一笔。

## res5 :: 价格分两个口径：权重 15.638 GiB；KV **上界** 1.875 GiB@4096（不认滑窗，是 bound 不是需求）、KV **真值** 0.273 GiB@4096（按层：25 层滑窗只留 1024 token 且用 `*_swa` 头维、5 层全局留满），上界/真值 = 6.86 倍；按真值算权重+KV = **15.911 GiB**，**当时空闲 21.73 GiB（更早一次记录是 16.42 GiB）→ 当时可容纳**；llama.cpp 的 compute buffer 没算，加它之后是否仍可容纳**未测**。换 transformers 路线要 bf16 47.03 GiB > 整张卡 24.0 GiB，必须 offload。

- kind: measured
- status: current
- from: result.res1
- evidence: `analysis/fixtures/diffusion_gate.json` 的 `price`：`weights_bytes = 16,790,985,619`（= 头部 `data_bytes`）、`kv_bound_bytes_per_token = 491,520`、`kv_true_bytes_at_4096 = 293,601,280`、`bound_over_true = 6.86`、`weights_plus_true_kv_gib = 15.911`、`fits_given_true_kv = true`、`bf16_weights_gib = 47.03`、`gpu = {total 24564, free 22254, compute_apps 1164}` MiB（更早一次记录 `git show f0dd74c:…/diffusion_gate.json` 的空闲是 16819 MiB，同样 ≥ 15.911）
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/run_all.py`（F1–F6）；`python3 …/analysis/gate.py`
- 修正（复核指出）：旧写法把 KV **上界**当成需求，得出「需求 17.5 GiB > 空闲 16.4 GiB ⇒ 就算支持也得独占卡」。那个判决是上界造出来的：真 KV 只有 0.273 GiB（上界是它的 6.9 倍），按真值算那次其实**塞得进去**。「17.5 GiB」这个数不再作为可引用的需求出现，上界只保留为「头部自洽」的参照。
- 仍未测的那一半：llama.cpp 的 compute buffer（与 `n_batch`/`n_ctx`/GPU 层数相关）没算，所以「加它之后是否仍可容纳」没有结论；要判就得在能加载该架构的运行时上实测占用。

## res6 :: 可复现装置：干净 clone 里 `run_all.py` **46 条**全成立（头部 / 名表 / 对照 / 记录 / 价格五组），`--selftest` 的 11 条负控全部按预期翻红；本机（有 venv 那台）`--live` **50 条**全成立、rc=0，而干净 clone 里没有 venv，`--live` 的 L4 是「未验证」并整体退出 **2**。

- kind: measured
- status: current
- from: result.res2
- evidence: `analysis/run_all.py` 的 46 条与 `analysis/run_all.py --live` 的 50 条输出；11 条负控各自翻红的具体检查名（把 `diffusion-gemma` 塞进名表 → `D1` 红；把负控改成没加载起来 → `E4` 红；改一张张量维度 → `A1` 红；把真值 KV 改回上界 → `F2` 红；把「当时可容纳」改成装不下 → `F4` 红；抹掉 `accept_canvas` 标记 → `C7` 红）
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/run_all.py`；`… --selftest`；`… --live`
- 计数口径：`--live` 比 46 多出的 4 条是 L1–L4（现场重放门槛、头部漂移、架构名表漂移、venv 里的 diffusion_gemma 代码漂移），它们要盘上的 gguf / llama.cpp 源码 / venv。干净 clone 里 `.wrapup/bfclenv` 与 `.wrapup/lmenv` 是 gitignore 的，所以 clone 里 `--live` 只有 49 条成立 + L4「未验证」，退出码 2——这是未验证，不是通过，也不是回归。

## res7 :: 记录的三个限制：(a) 门槛的现场重放只能在有 gguf 与 llama.cpp 二进制的机器上做，干净 clone 里它退出 2；(b) 真值 KV 是按层记账的**上界内**口径，`attention.shared_kv_layers = 0` 时才准（本文件就是 0），本机没有实测占用可对；(c) 第三条路（同模型换运行时）是**代码在、权重不在**：`transformers 5.17.0` 的 `diffusion_gemma` 就在本机 venv 里（`res12`），缺的是 bf16 权重（`n_params×2 = 47.03 GiB`）与许可证。

- kind: citation
- status: current
- from: result.res5
- evidence: `run_all.py` 的 `[note]` 行与 `gate.py` 的退出码 2 路径；`analysis/fixtures/headers.json` 里只有 Q4_K_M 一份 GGUF；(c) 的证据是本机 `/home/z/hf` 下该模型只有 GGUF 一个 repo（`models--unsloth--diffusiongemma-26B-A4B-it-GGUF`，16 GB）而 `.wrapup/lmenv` 里 `transformers-5.17.0` 带 `models/diffusion_gemma/`
- producer: `ls /home/z/hf/models--unsloth--diffusiongemma-26B-A4B-it-GGUF/blobs` → 1 个 blob（16,028.2 MiB）；`python3 …/analysis/transformers_code.py`
- 修正（复核指出）：旧写法把 (c) 写成「上游仓库的存在与许可证未知」，把「代码在不在」和「权重在不在」混成一件。代码在，缺的是权重与许可；许可证仍未查（未测，不是已知不可用）。

## res8 :: 登记册里 nm4 的结论（GATE-FAIL）仍然成立，但它的证据指向 `.wrapup/axes_diffusion_gate.log`，那份日志没有入库（`git ls-files .wrapup` 里没有它），所以从 clone 出来的读者打不开它；本子项目的 `res1`–`res6` 给出同一事实的入库版证据。

- kind: citation
- status: current
- from: result.res2
- evidence: `git ls-files .wrapup | grep -c diffusion` → `0`；`docs/subprojects/i02-测量基础设施/non_measurements.tsv` 的 nm4 行
- producer: `git ls-files .wrapup | grep -i diffusion`；`sqlite3 experiments.sqlite "select count(*) from experiments where lower(model) like '%diffusion%'"` → `0`
- 这条是给 i02 的（登记册归它），本子项目不改别的目录。

## res9 :: a11 的 `PLAN.md` 让报告侧的派生索引变陈旧：`report_inputs/open_questions.json` 的 `items` 与 `skipped` 都随 PLAN.md 集合变，重生它必须连 `report.html` 一起重生，而这两个文件归 i02/meta；所以本子项目不改它们，`reproduce.sh` 记 WARN 而不 FAIL。

- kind: citation
- status: current
- from: result.res2
- evidence: 干净 clone（HEAD 919215d）里 `./reproduce.sh` 退出 0、37 条 PASS、1 条 WARN，那一条就是本子项目引起的 `open_questions.json`；`git diff report.html` 的唯一差异是「未解问题」索引的页脚（跳过的子项目少一个）与列表（多了 a11 的四条）
- producer: `python3 report_inputs/build_open_questions.py --check` → `FAIL: … is stale`；`./reproduce.sh` → `WARN open_questions.json 与 PLAN.md 不一致`
- 交回 meta 的一句：下次重生成报告输入与 `report.html` 时带上 a11（它现在有「未解问题」一节），本子项目不越权改那两个文件。

## res10 :: `plan1` 记下的 `GATE-FAIL`（扩散式解码因运行时缺失未测）此前没有产物；本目录的 `res1`–`res6` 就是它的产物，`plan1` 里那半句话现在由可复算的装置支撑，其余三句（长上下文 KV、31B、26B-A4B 原生档）不归本子项目。

- kind: citation
- status: current
- from: result.res2
- evidence: `docs/plan/plan.yaml::plan1` 的 `_text`（该文件已由 meta 迁移删除，原文见 `git show 021e6b8^:docs/plan/plan.yaml`，第 51 行）；本目录 `analysis/` 与 `fixtures/` 是新增的产物
- producer: `git show 021e6b8^:docs/plan/plan.yaml | sed -n 51p`

## res11 :: 可比性的来源不止参数量：扩散文件是双胞胎的**严格父集**，多出来的正好 34 个张量——30 个 `blk.{0..29}.enc_layer_output_scale.weight` 与 4 个 self-conditioning 张量（`self_cond_down/up/gate/pre_norm.weight`），后者是扩散模型独有构件；双胞胎一个也不多。

- kind: measured
- status: current
- from: result.res3
- evidence: `analysis/fixtures/headers.json` 两份张量表的名称集合：`diffusion-only = 34`（30 + 4）、`twin-only = 0`
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/run_all.py`（A2 两条，逐名比对）
- 读法：一对「同一主干 + 一个额外解码头」的模型才配得上「解码器」这个自变量；参数量的差 +0.0707%（`res4`）正是这 34 个张量加上 `embedding_length_per_layer_input` 的效应，不是换了模型。

## res12 :: 第三条路的「代码在」是可核对的：本机 venv 里 `transformers 5.17.0` 带 `models/diffusion_gemma/`，有 `DiffusionGemmaForBlockDiffusion`、生成配置默认 `max_denoising_steps = 48`、块内判据 `EntropyBoundSampler.accept_canvas`，`canvas_length` 的 docstring 原文是「block length in block diffusion」；缺的是权重与许可，不是解码回路。

- kind: measured
- status: current
- from: result.res3
- evidence: `analysis/fixtures/transformers_code.json`（`transformers-5.17.0.dist-info`、三个文件的 sha256、四个标记、`configuration_diffusion_gemma.py:170`）
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/transformers_code.py`（`--record` 落夹具，`--check` 与 live venv 比漂移）
- 这是 `res7(c)` 的依据，也是后续接手人的入口：要提取扩散解码协议，读 `generation_diffusion_gemma.py` 的 `max_denoising_steps` 与 `accept_canvas`，而不是猜；本子项目没有做这一步（未测，不冒充）。
