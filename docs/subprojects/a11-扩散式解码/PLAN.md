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
在 ≤60 GPU 分钟内被绕过，最后把「价格」写成能重算的数（权重字节、KV 上界、当时的卡上占用）。
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
4. 价格可复算：权重 15.64 GiB + 4096 ctx 的 KV 上界 1.875 GiB 对当时的空闲显存；
   换 transformers 路线是 bf16 47.03 GiB > 整张卡（`RESULT.md::res5`）；
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
| WP5 价格 | 本层编排者 | 权重字节、KV 上界、bf16 量、当时的卡上占用四个数都能从夹具重算，不用二次引用 | WP3 | 无 GPU | 完成（`res5`） |
| WP6 对照侧现状 | 本层编排者 | 同主干双胞胎的参数量与 a02 入库真值、`bpw_map` 两处独立产物一致；位宽匹配的臂是否已测有明确答案 | WP2 | 无算力 | 完成（`res4`） |
| WP7 独立复核 | meta→reviewer | fresh-context reviewer 在干净 clone 里跑 `run_all.py`（0）、`--selftest`（负控翻红）、并在有 gguf 的机器上跑 `--live`（0），贴命令与输出 | WP1–WP6 | 无 GPU | **待派** |
| WP8 替代对（候选，未开始） | 需 meta 决定 | 用 llama.cpp **已支持**的扩散模型（dream / llada / llada-moe / rnd1）对同尺寸自回归做一次受控对照 | — | 未估算（要先量下载量与吞吐） | **未开始**：它把 X 从「解码器」换成「模型身份」，是另一个问题，买不买由 meta 决定 |

## 当前状态（随每次提交更新）

- 还剩哪些：`WP7`（独立复核）、`WP8`（候选，等 meta 决定是否买）。
- 现在在哪个：`WP1`–`WP6` 已完；本层没有待跑的实验，也不需要 GPU。
- 下一个派给谁：**meta → fresh-context reviewer**（`WP7`）。本层没有派孙工具，独立复核必须由 meta 派，
  不得自评通过。若 meta 决定买 `WP8`，先由本层量下载量与吞吐，再决定要不要占 GPU。

## 资源

- 已用：0 GPU 分钟（门槛与价格全部在 CPU 侧，`-ngl 0`，不持 `/tmp/llama_gpu.lock`）。
- 若 `WP8` 被批准：需求是「一张空闲 ≥20 GB 的卡 × 一次加载 + 一次小样本生成」，先实测吞吐再报预算，
  不预先承诺 GPU 分钟数。
