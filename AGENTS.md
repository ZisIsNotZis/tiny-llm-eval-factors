# Agent memory for this workspace

## 目标（先读这一节，再挑活）

1. **目标与覆盖各自只有一处，别处一律引用、不复述**：目标 = `docs/need/need.yaml::n1`（用户原话）；
   每个 X 的答案与面对目标的覆盖缺口 = `docs/subprojects/i02-测量基础设施/RESULT.md::res72` 末段。
2. 挑活前的第一问：**这件事会改变哪个 X 对哪个基准的答案？** 答不上来就先做答得上的；
   纯可复现性/记账工作排在后面，只因报告必须可复算才重要。
3. manager 的活是**朝目标推进并调整路线**，不是机械执行 roadmap；细节归 worker。

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
