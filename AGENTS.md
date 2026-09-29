# Agent memory for this workspace

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
