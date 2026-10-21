# a11 扩散式解码 — 节点文档与孙 agent 规则

## 这个节点是什么

a11 存在，是因为「扩散式解码」在报告里占一节，而这一节的答案可能合法地是「在本机测不了」。
登记表给它的 AC 允许两种终点：测出对照，或证明不可比**且门槛可复现**。本节点的工就是把后者做成
别人能重跑的东西：说明缺口在运行时的哪一层、这一层能不能在六十 GPU 分钟内被绕过、绕不过去的价格是多少。

工序顺序的理由在 `PLAN.md` 的开头一段：模型在、对照在、只缺运行时，所以先钉缺口，再谈价格，
最后才谈「替代对」。本节点至今没花任何 GPU 分钟，因为花它换不来这个轴的一格分数。

## roadmap

- 里程碑 `M1 :: 研究结束` 的达成条件与现状见 `PLAN.md`。
- 工作包 `WP1`–`WP6` 已完成，`WP7`（独立复核）待 meta 派，`WP8`（替代对）是候选、等 meta 决定。
- 下一个动作永远写在 `PLAN.md::当前状态` 一节，不写在这里。

## 当前事实（一句话版，细节在 `RESULT.md`）

- 状态是 `GATE-FAIL`：两个运行时都在架构名查表处拒绝该文件，库内 0 行、无产物（`res1`）。
- 门槛的机制是名表缺 `diffusion-gemma` 这个键；`gemma4` 与四个扩散架构都在表里（`res2`）。
- 文件没坏：非因果、`canvas_length = 256`、25,250,987,068 参数、5.3247 bpw（`res3`）。
- 对照侧只有一半：同主干双胞胎在库，位宽匹配的臂 m145 未测（`res4`）。
- 价格：独占卡约 17.5 GiB；换 transformers 路线 bf16 47.03 GiB > 整张卡（`res5`）。
- 装置：`run_all.py` 46 条 + `--selftest` 8 条负控 + `--live` 49 条（`res6`），限制见 `res7`。

## 证据在哪

- 装置：`docs/subprojects/a11-扩散式解码/analysis/{gate.py,gguf_header.py,arch_table.py,record_headers.py,run_all.py}`
- 夹具（入库，干净 clone 可读）：`analysis/fixtures/{headers.json,arch_tables.json,diffusion_gate.json}`
- 重跑：`python3 …/analysis/run_all.py`（clone 可跑）／`--selftest`（负控）／`--live`（要盘上的 gguf 与二进制）

## 孙 agent 容易做错的六件事

1. **把「加载不了」写成 0 分或「差」**。它是 `GATE-FAIL`，是非测量。分数不存在，偏差更不存在。
2. **把门槛说成「llama.cpp 不支持扩散解码」**。它支持 `dream`/`llada`/`llada-moe`/`rnd1`；
   缺的是 `diffusion-gemma` 这一个键。写错这一句，整条结论就从「缺实现」滑成「技术不可行」。
3. **用文件名或标签代替实测**。参数量、位宽一律从 GGUF 头部重算（`gguf_header.py`），
   并与 a02 的入库真值、`.wrapup/bpw_map.json` 两处独立产物对；对不上先怀疑自己的解析。
4. **自己起一个 llama-server 去试**。测这个架构不需要 GPU：全程 `-ngl 0`、不持 `/tmp/llama_gpu.lock`、
   不碰别的进程正在用的那 6–7 GB。要占卡的任务先看 `nvidia-smi` 的 `memory.free`，再按实测数报价。
5. **把扩散格与自回归格池化**。扩散解码器是它自己的协议；即使将来测出分数，也不与贪心/采样格平均、
   不并进同一列。`protocol` 与 `spec_type`/`max_tokens`/`ctx` 一样是测量身份的一部分。
6. **改别人的目录**。`non_measurements.tsv` 归 i02，`docs/plan/subprojects.md`、`make_report.py`、
   `mktables.py`、`report.html` 不归本子项目。发现那边有缺陷（例如 `res8` 里 nm4 的证据没入库）写进
   本目录并上报，不改它。

## 脚本纪律

- 数字只从 `analysis/` 的装置出来。夹具与脚本不一致时，二者必有一个错，都要修一个，**不许手改夹具**。
- 新事实先写进 `RESULT.md`，再把它的断言加进 `run_all.py`：文档里没有装置判过的数字不许引用。
- 缺输入时退出 **2**（未验证），不许打印 `UNMEASURED` 后退出 0；负控必须在 `--selftest` 里翻红。
- 只读打开 `experiments.sqlite`（`mode=ro`）；本子项目当前不需要写库。真要写就按仓库规矩：
  编号备份 → `migrate_db.py` → `db_check` → 行数对账。
- 提交按路径点名，`git commit -m … -- docs/subprojects/a11-扩散式解码/`，不 `git push`。
