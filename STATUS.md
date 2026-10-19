# STATUS

路由文件：只记「它是什么、现在什么状态、进展落在哪、下一步」。数字与结论见 `FINDINGS.md`；`文件:行` 引用绑定该提交之前的 revision `a2e62fc`。

## 它是什么

一个可复现的**本地语言模型推理因子测量工作台**：量化、模型规模、解码协议与基准行为。数据 SSOT 是 `experiments.sqlite`（记录下来的测量），`docs/plan/plan.yaml` 拥有当前研究问题及其状态，`docs/result/result.yaml` 拥有当前结论及其证据引用，`report.html` 由 `make_report.py` 生成、不得手改。（`README.md:3`、`README.md:7-12`、`AGENTS.md:23`）

## 当前状态

**活跃**，截至 2026-10-19（HEAD `a2e62fc`）。

- 里程碑 **m161 进行中**（owner=worker）：用修好的 harness 重测 6 个 chat/py cell + 1 个端到端控制格，预算 ≤ 2 小时 GPU。（`docs/plan/plan.yaml:94`）
- 后续三个里程碑已排定且未完成：入库（`plan12`，`docs/plan/plan.yaml:103`）、报告重生成（`plan13`，`:112`）、独立复核（`plan14`，`:121`）。
- 当前数据库与报告**仍是低报值**：DB 里 m26 的两条 chat cpp 行还是 `0.2174/0.4845`（正确值 `0.6335/0.8571`，可由磁盘样本重算），`report.html` 因此仍印低报值。（`docs/plan/plan.yaml:76`、`docs/result/result.yaml:243`）
- 文档层有两个**未闭合的阻塞**，不得记为通过：`docs/check_docs.py` 实际执行时因 `/home/z/vibe/AGENTS.docs.schema.yaml` 缺失退出 2（`docs/plan/plan.yaml:58`）；研究证据可恢复性（result 的来源仍指向已退役的 `.scratch/originals`）待修复（同处）。
- 硬阻塞实验（`BLOCKED-on-VRAM` / `GATE-FAIL`）登记在 `docs/plan/plan.yaml:1`。

## 最新进展落在哪个文件

1. 当前问题与里程碑状态：`docs/plan/plan.yaml`（最近三条 m161 计划在同一文件 `plan11`–`plan14`）。
2. 当前结论与证据：`docs/result/result.yaml`（最近的条目是 `res19`–`res22`，都是 MultiPL-E 判分缺陷的追查）。
3. 方法/协议：`docs/method/method.yaml`；产品与需求：`docs/product/product.yaml`、`docs/need/`、`docs/pain/`、`docs/architecture/`。
4. 本地产物（不入库，按 `README.md:12` 的规则）：`.wrapup/`，含 `m161_summary.jsonl`、`prompts/SHA256SUMS`。

## 下一步

仓内已写明的顺序，未新增判断：

1. `plan11` → `plan12` → `plan13` → `plan14` 依次执行：重测 6 个 chat/py cell → 只经 `migrate_db.py` 入库（先备份 `experiments.sqlite.bak39`）→ `make_report.py` 重生成 → fresh-context 独立复核。（`docs/plan/plan.yaml:94`、`:103`、`:112`、`:121`）
2. 未决问题：长上下文的 KV 影响未测、31B 与 26B-A4B 原生档显存不足未测、扩散式解码未测、12B 原生档 MMLU 异常需复测（`docs/plan/plan.yaml:50`）；`.wrapup/` 下 10+ 脚本硬编码已不存在的 `/home/z/hf/research`，按 `migrate_on_touch` 逐个改（`:85`）。
3. 假设池 B1–B3 与 MoE 双变量回归等仍为 `provisional`，未开跑（`docs/plan/plan.yaml:10-49`）。
