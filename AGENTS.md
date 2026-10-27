# Agent memory for this workspace

## 目标（先读这一节，再挑活）

1. 目标：**必须能知道——给本地部署的大模型换一个设置之后，它在本机基准上的实际跑分会怎么变**（`docs/need/need.yaml::n1`，用户原话）。其余一切都从它派生。
2. 研究对象是**各种设置 / 超参数**，不是「量化研究」；每项设置单列一项研究（X = 设置，Y = 基准分数，其余固定量构成 series）（`docs/product/product.yaml::prod1`、`::prod2`）。
3. 价值的单位是「一个设置上能回答换它会怎样，且答案能从库复算」，不是「格子填满」；诚实的「本库答不了，缺什么、补要多少成本」也算交付。
4. 挑活前的第一问：**这件事会改变哪个设置的答案？** 答不上来就先做答得上的；纯粹的可复现性/记账工作排在后面，只因报告必须可复算才重要。
5. 每个设置当前的答案与缺口在一屏里：`docs/subprojects/i02-测量基础设施/RESULT.md::res72`（十六轴总账）。收工前对一眼这张表，而不是对一眼工作包表。

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
