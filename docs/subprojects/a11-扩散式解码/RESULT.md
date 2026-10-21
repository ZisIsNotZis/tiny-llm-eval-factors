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

## res3 :: 失败不是文件坏：该 GGUF 头部可解析（v3、692 张量、30 层、128 专家用 8、非因果注意力、`diffusion.canvas_length = 256`），参数量 25,250,987,068, 位宽 5.3247 bpw。

- kind: measured
- status: current
- from: result.res1
- evidence: `analysis/fixtures/headers.json` 里该文件的头部，逐张量形状/类型/偏移/字节；`attention.causal = false` 与 `diffusion.canvas_length = 256` 是「这确实是块扩散解码器」的两条直接证据
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/gguf_header.py /home/z/hf/diffusiongemma-26B-A4B-it-Q4_K_M.gguf`；夹具由 `python3 …/analysis/record_headers.py` 重取
- 参数量与位宽由张量表独立重算过（`run_all.py` 的 A1/A3 两条），不是从文件名推的。

## res4 :: 对照侧已有一半：同主干自回归双胞胎 `gemma-4-26B-A4B-it-qat-UD-Q4_K_XL` 参数量 25,233,142,046（与 a02 入库真值逐位一致、位宽与 `bpw_map` 一致），与扩散臂只差 +0.0707%；但已入库的 QAT 臂位宽是 4.5176（差 0.807 bpw），位宽最接近的 `UD-Q4_K_XL`（5.3932，差 0.068）正是 nm3 里**未测**的 m145。

- kind: measured
- status: current
- from: result.res3
- evidence: `analysis/fixtures/headers.json` 的双胞胎头部；a02 的 `analysis/fixtures/gguf_truth.json` 里 `n_params = 25233142046`；`.wrapup/bpw_map.json` 里 `4.517565692936376`；nm3（`docs/subprojects/i02-测量基础设施/non_measurements.tsv`）记 m145 为 `BLOCKED-on-VRAM`
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/run_all.py`（C2/C3/C4/C5/C6 四条）
- 结论：即使明天有人实现了这个架构，「位宽匹配的对照」也还差一个未测臂——这是两笔账，不是一笔。

## res5 :: 价格：要实现这个架构才谈得上测；测的话这一轴要独占卡约 17.5 GiB（权重 15.64 GiB + 4096 ctx 的 KV 上界 1.875 GiB），记录时卡上另有 6.7 GB 外部占用、空闲 16.4 GiB；换 transformers 路线则要 bf16 47.03 GiB，超过整张卡 24.0 GiB 必须 offload，而且仓库的评测面是 llama-server HTTP，扩散解码只存在于 llama.cpp 的 CLI 示例里。

- kind: measured
- status: current
- from: result.res1
- evidence: `analysis/fixtures/diffusion_gate.json` 的 `price`：`weights_bytes = 16,790,985,619`（= 头部 `data_bytes`）、`kv_upper_bytes_per_token = 491,520`（30 层 × 8 kv 头 × (512+512) × 2 B）、`bf16_weights_gib = 47.03`（`n_params × 2`）、`gpu = {total 24564, used 7290, free 16819, compute_apps 6704}` MiB
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/run_all.py`（F1–F6）；`python3 …/analysis/gate.py`
- KV 那个数是**上界**：`attention.shared_kv_layers = 0` 但 `attention.sliding_window = 1024`，真值更小；本机没有真值，所以不往下推（`res7`）。

## res6 :: 可复现装置：干净 clone 里 `run_all.py` 46 条全成立（头部 / 名表 / 记录 / 价格四组），`--selftest` 的 8 条负控全部按预期翻红，本机 `--live` 49 条全成立；缺 live 输入时退出 2（未验证），不是通过。

- kind: measured
- status: current
- from: result.res2
- evidence: `analysis/run_all.py` 的 46 条与 `analysis/run_all.py --live` 的 49 条输出；8 条负控各自翻红的具体检查名（如把 `diffusion-gemma` 塞进名表 → `D1` 红；把负控改成没加载起来 → `E4` 红；改一张张量维度 → `A1` 红）
- producer: `python3 docs/subprojects/a11-扩散式解码/analysis/run_all.py`；`… --selftest`；`… --live`
- 干净 clone 里没有 gguf 与二进制，所以现场重放这一段是 exit 2 而不是「绿」：`--live` 是那一半的唯一入口。

## res7 :: 记录的三个限制：(a) 门槛的现场重放只能在有 gguf 与 llama.cpp 二进制的机器上做，干净 clone 里它退出 2；(b) KV 是上界公式，共享 KV 与滑窗会让真值更小，本机没有实测占用可对；(c) 上游 bf16 权重不在本机，47.03 GiB 是 `n_params×2` 的推算，那个仓库的存在与许可证**未知**。

- kind: citation
- status: current
- from: result.res5
- evidence: `run_all.py` 的 `[note]` 行与 `gate.py` 的退出码 2 路径；`analysis/fixtures/headers.json` 里只有 Q4_K_M 一份 GGUF；(c) 的证据是本机 `/home/z/hf` 下该模型只有 GGUF 一个 repo（`models--unsloth--diffusiongemma-26B-A4B-it-GGUF`，16 GB）
- producer: `ls /home/z/hf/models--unsloth--diffusiongemma-26B-A4B-it-GGUF/blobs` → 1 个 blob（16,028.2 MiB）

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
