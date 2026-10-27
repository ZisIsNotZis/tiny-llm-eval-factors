# a11 扩散式解码 — 计划

计划层的唯一 home。goal / purpose / AC / 资源 / 依赖由 `docs/plan/subprojects.md` 的 a11 行定义，
本文件不复述；本文件只写里程碑、工作包、状态与派工。
结果与证据在 `RESULT.md`；窄规则在 `AGENTS.md`；可执行的复算装置在 `analysis/`。

## 这个节点为什么这样排工序

登记表给 a11 的 AC 允许两种终点：**测出对照**，或者**证明不可比且门槛可复现**。这一轴在本机
特殊在三个条件只缺一个：模型文件在盘上（`diffusiongemma-26B-A4B-it-Q4_K_M.gguf`，16.81 GB），
对照侧的同主干自回归模型已经在库里（`gemma-4-26B-A4B-it` 一族 68 行），而**运行时认不认这个架构**
是唯一的未知。所以工序不能从「设计一组评测」开始：如果运行时在架构名查表处就拒绝文件，
任何评测设计都是空转，任何「分数」都会是编出来的。

因此顺序是：先把缺口钉到具体那一层（架构名表 / 文件完整性 / 显存 / 构建），再判这个缺口能不能
在 ≤60 GPU 分钟内被绕过，最后把「价格」写成能重算的数（权重字节、KV **上界与真值两个口径**、
当时的卡上占用）。两个口径必须并列：本文件上界是 1.875 GiB@4096 而真值是 0.273 GiB，拿上界
当需求会把「当时塞得进去」误判成「必须独占卡」。
这条路全部在 CPU 侧完成、不持 GPU 锁：a11 的 3% GPU 额度一分没花，因为它换不来这个轴的一格分数。

## 里程碑 M1 :: 研究结束 — 扩散式解码要么可比，要么不可比且门槛可复现

达成条件（每条后面的括号是它现在由哪条事实证明）：

1. 门槛可复现：干净 clone 里 `python3 docs/subprojects/a11-扩散式解码/analysis/run_all.py` 退出 0，
   本机 `… run_all.py --live` 退出 0（`RESULT.md::res6`）；
2. 门槛的机制是**架构名表缺这个键**，不是「文件坏了」、也不是「整个扩散解码都不支持」：
   两棵 llama.cpp 源码树的名表里 `gemma4`/`gemma4-assistant` 与 `dream`/`llada`/`llada-moe`/`rnd1`
   都在，唯独没有 `diffusion-gemma`（`RESULT.md::res2`、`RESULT.md::res3`）；
3. 状态是 `GATE-FAIL` 而不是 0：库内该模型 0 行、`.wrapup/mres` 无产物、两个运行时都在
   架构查表处非零退出（`RESULT.md::res1`）；
4. 价格可复算且口径标明：权重 15.638 GiB；4096 ctx 的 KV **上界** 1.875 GiB / **真值** 0.273 GiB
   （上界/真值 = 6.86）→ 按真值算 15.911 GiB ≤ 当时空闲 21.73 GiB，**当时可容纳**，加 compute buffer
   后是否仍可容纳**未测**；换 transformers 路线是 bf16 47.03 GiB > 整张卡（`RESULT.md::res5`）；
5. 对照侧现状写清：同主干双胞胎与扩散臂参数量差 +0.0707%，但位宽匹配的那个臂（m145）**未测**
   （`RESULT.md::res4`）；
6. 记录的限制逐条写明，不留隐形的「未验证」（`RESULT.md::res7`）。

## AC 状态（登记表里 a11 那一行，逐条对到事实）

| 登记表里的 AC | 状态 | 证明 | 复算命令 |
|---|---|---|---|
| 要么测出对照 | 未达成（不可能在本机达成，理由见 res2/res5） | `RESULT.md::res2`、`RESULT.md::res5` | `python3 …/analysis/run_all.py --live` |
| 要么 GATE-FAIL 且门槛可复现 | **达成** | `RESULT.md::res2`、`RESULT.md::res6` | `python3 …/analysis/run_all.py`；`--selftest`；`--live` |

## 工作包

| 工作包 | owner | AC（可证伪） | 依赖 | 预算 | 状态 |
|---|---|---|---|---|---|
| WP1 文档归位 | 本层编排者 | `PLAN.md`/`RESULT.md`/`AGENTS.md` 三份 Markdown 存在；本目录此前没有 carried 的 `plan.yaml`/`result.yaml`，无迁移可做 | — | 无算力 | 完成 |
| WP2 状态盘点 | 本层编排者 | 模型文件 / 运行时 / 产物 / 失败日志四件事各自有 path 或 0 的实测值，且「失败在哪一层」有一句可判的话 | — | 无算力 | 完成（`res1`） |
| WP3 门槛装置 | 本层编排者 | `gate.py` 用两个运行时重放同一条错话，且**负控**（同一个 llama-server 换一个受支持模型）真的加载出 token；缺任一输入退出 2 | WP2 | CPU 45 s，无 GPU | 完成（`res2`、`res6`） |
| WP4 源级证据 | 本层编排者 | 两棵 llama.cpp 源码树的架构名表进仓库夹具，带 commit 与文件 sha256；`diffusion-gemma` 不在表里，而 gemma4/四个扩散架构在表里 | WP2 | 一次 `git fetch --depth 1` | 完成（`res2`） |
| WP5 价格 | 本层编排者 | 权重字节、KV **上界与真值**、bf16 量、当时的卡上占用都能从夹具重算；上界与真值并列且标明哪个是 bound，结论只许用真值 | WP3 | 无 GPU | 完成（`res5`，复核后已修） |
| WP6 对照侧现状 | 本层编排者 | 同主干双胞胎的参数量与 a02 入库真值、`bpw_map` 两处独立产物一致；张量集合之差逐名可判（扩散独有 34 个）；位宽匹配的臂是否已测有明确答案 | WP2 | 无算力 | 完成（`res4`、`res11`） |
| WP7 独立复核 | meta→reviewer | fresh-context reviewer 在干净 clone 里跑 `run_all.py`（0）、`--selftest`（负控翻红）、并在有 gguf 的机器上跑 `--live`（0），贴命令与输出 | WP1–WP6 | 无 GPU | **待派** |
| WP8 替代对（候选） | 需 meta 决定 | 用 llama.cpp **已支持**的扩散模型（dream / llada / llada-moe / rnd1）对同尺寸自回归做一次受控对照 | — | 未测（准入前要先量下载量与吞吐） | **不批 / 未测**（meta 2026-10-21 裁决）：它把 X 从「解码器」换成「模型身份」，报告要换一节 X，是另一个问题；登记为未测，不占 GPU |

## 当前状态（随每次提交更新）

- 还剩哪些：`WP7`（独立复核，meta 已做一轮 ACCEPT WITH NOTES，本轮修完待复审）；`WP8` 已裁决**不批**（登记未测）。
- 现在在哪个：`WP1`–`WP6` 已完，复核提出的三处（F5 口径、`res7(c)`、`res3`）已修；本层没有待跑的实验，也不需要 GPU。
- 下一个派给谁：**meta → fresh-context reviewer**（`WP7` 复审）。本层没有派孙工具，独立复核必须由 meta 派，
  不得自评通过。

## 未解问题

- **位宽匹配的对照臂 m145 仍未测**：扩散臂 5.3247 bpw 最近的同尺寸自回归是 `gemma-4-26B-A4B-it-UD-Q4_K_XL`（5.3932，差 0.068），而它在 nm3 里是 `BLOCKED-on-VRAM`。即使运行时有了，比较还差这一臂（本层没买，价格按 20 GB 级权重 + 一次面板计）。
- **替代对（`WP8`，已裁决不批）**：用 llama.cpp 已支持的扩散模型（`dream` / `llada` / `llada-moe` / `rnd1`）对同尺寸自回归做受控对照。它把 X 从「解码器」换成「模型身份」，报告要换一节 X，因此**不批**；登记为未测，准入前先量下载量与吞吐。
- **更换运行时后能不能进库**：扩散解码器没有 `llama-server` 路径（本机与上游 `339f324` 的 `tools/` 里都没有扩散采样），只有 `examples/diffusion` 的 CLI；即使架构被实现，评测面也要自己的驱动与自己的协议列，绝不会并进自回归列（未测，价钱未知）。**解码协议本身不必猜**：`transformers 5.17.0` 的 `generation_diffusion_gemma.py` 有默认 `max_denoising_steps = 48` 与 `EntropyBoundSampler.accept_canvas`（`RESULT.md::res12`），要提取就从那里开始。
- **第三条路是「代码在、权重不在」**：`transformers 5.17.0` 的 `diffusion_gemma` 就在本机 venv 里（模型类、生成循环、48 步默认、`accept_canvas`，见 `RESULT.md::res12`），缺的是 bf16 权重（`n_params×2 = 47.03 GiB`，本机只有 Q4_K_M 一份 GGUF）与其许可证（许可证未查，不是已知不可用）。

## 资源

- 已用：0 GPU 分钟（门槛与价格全部在 CPU 侧，`-ngl 0`，不持 `/tmp/llama_gpu.lock`）。
- 若将来有人买到能加载该架构的运行时：按真值算独占需求是 15.911 GiB（权重 15.638 + 真 KV 0.273@4096），
  加上 compute buffer 后是否仍能与非本仓库的任务共卡**未测**；先实测占用再报预算，不预先承诺 GPU 分钟数。

## plan3 :: nm4 复测：上游 PR #24423 的 `llama-diffusion-cli` 能否把这条轴从 GATE-FAIL 变成可测。

- why: `res1` 的 `GATE-FAIL` 依据是旧二进制（2026-09-17）架构表里没有 `diffusion-gemma`；上游把支持放在 `ggml-org/llama.cpp#24423`（`llama-diffusion-cli`）与 `#24427`（架构），据 2026-06-22 公开说明两者都未进 mainline。
- do: 在独立目录 checkout PR 头、`-DGGML_CUDA=ON` 编 `llama-diffusion-cli`；用本机已存的 `diffusiongemma-26B-A4B-it-Q4_K_M.gguf`（16.8 GB）跑最小提示；能出 token 再对齐协议（见 `docs/method/method.yaml`）。
- do not: 不改仓库代码、不因「能加载」就给分数（协议不可对齐时结论只到 `LOADS-ONLY`）。
- ac: 结论三选一且各带一条可重跑命令——`STILL-GATE-FAIL`（不能编/仍不认架构）/ `LOADS-ONLY`（能出 token，协议不可对齐）/ `MEASURABLE`（能按协议跑出与库可比的分数）。日志落 `.wrapup/axis11-diffusion-retest-<日期>/`。
- status: 进行中（2026-10-27）。
