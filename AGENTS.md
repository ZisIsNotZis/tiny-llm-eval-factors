# Agent memory for this workspace

## 目标（先读这一节，再挑活）

1. 目标：**benchmark 开源模型**——在**模型的架构 / 版本 / 规模 / 激活规模**、**量化的 provider / 风格（如 UD）/ 配置**、以及**全部运行时参数**之下——对「**真实的 agentic 基准（多种类型、多种难度）**」最终跑分的**端到端影响**（`docs/need/need.yaml::n1`，用户原话，2026-10-27）。
2. 三类 X 都是研究对象：模型本身、量化、运行时参数。控制变量原则（一次只变一个）是**比较的方式**，不是范围的上限——「所有比较都在同一家族内」是旧文档把范围写窄的说法。
3. 价值的单位是「一个 X 上能回答端到端会怎样，且答案能从库复算」；诚实的「本库答不了，缺什么、补要多少成本」也算交付。把格子填满不是目标。
4. 挑活前的第一问：**这件事会改变哪个 X 对哪个 agentic 基准的答案？** 答不上来就先做答得上的；纯粹的可复现性/记账工作排在后面，只因报告必须可复算才重要。
5. 每个 X 当前的答案与缺口在一屏里：`docs/subprojects/i02-测量基础设施/RESULT.md::res72`。收工前对一眼那张表，而不是对一眼工作包表。
6. manager 的活是**朝目标推进并调整路线**，不是机械执行 roadmap；细节归 worker。

## Data trust and ingestion priority
1. Trust non-`_analysis` `json/jsonl` first.
2. Then use non-`_analysis` `txt` (mainly timing/aux logs).
3. Use `_analysis` content only as fallback/context.

## Database safety rules
1. Before any DB mutation, always create numbered backups:
   * `experiments.sqlite.bak1`, `.bak2`, ..., `.bakN`
2. After mutation, run integrity and cleanliness checks.
3. Keep DB clean (no null mandatory fields, valid boolean/range values).

## Research execution rules
1. No blind grid/random search.
2. Always run weakest-point-first targeted experiments.
3. Keep GPU occupied with highest-value run while analysis/design proceeds.
4. Do not stop before clearing all questions/assumptions unless a hard external blocker exists.
5. Do not modify existing open source projects unless absolutely required.
6. Prefer passing sampling parameters directly to llama-server/runtime instead of patching project code.
7. Run evaluations in the background and check progress timely; avoid foreground waits that can stall indefinitely.

Documentation SSOT: `docs/` (data SSOT: `experiments.sqlite`; `report.html` is generated, never hand-edited).
