kind:    report
from:    local_lm_research (manager, deepseek/deepseek-flash, thinking medium)
spend:   machine_time
id:      p-entry2 + p-entry3 落地 — 无需决定；里程碑只剩独立复核

## 结论

`entry` 的两个未结项工作包都结项了：`p-entry2`（`14ea373`）、`p-entry3`（`9e89f91`）。里程碑的验收命令在 `9e89f91` 上全绿：`./reproduce.sh` exit 0，51 行 PASS、FAIL/WARN/SKIP/BLOCKED 行 0，末行判报告逐字节可重建。剩下的是复核而不是工作包。

## 每个包的声称与它的命令（绑到 revision）

`p-entry2` — 13 条「输入与其来源不一致」的判断收进 `checks/report_inputs_drift.py`，`reproduce.sh` 只把它翻成核对表里的行：漂移=FAIL（整条命令非零退出），看不到来源=SKIP（rc=2，或来源不在场——缺席不是漂移）。判定比对上：只有三个 builder 自报 rc=2，其余十个由脚本先查来源在不在，查不到才 SKIP，查得到再判。

    python3 checks/report_inputs_drift_negative_control.py   # exit 0，7.5 秒
    PASS 漂移→非零退出并点名；缺席→SKIP 仍绿；改动已按原字节写回

三个用例缺一不算证明：未改动时 `./reproduce.sh` exit 0；把 `open_questions.json` 中间一个字节取反后它 exit 1 且输出点名「open_questions.json 与 PLAN.md 不一致」；把 `gsq.json` 移走后仍 exit 0 且那一行是 `SKIP … 不在场`。最后按原字节写回，sha256 复核不变，`git status -- report_inputs` 无输出。

**负控怎么跑：我定的设计（不是要批准）。** `reproduce.sh` 的路径全部由脚本自身位置推出，所以它不能在临时树上跑；整条链路又要两分钟，若把「跑一遍整条链路」当检查的常态步骤，每次复现核对都要多花两分钟。故给它一个 `REPRODUCE_INPUTS_ONLY=1` 的开关，只跑输入一致性这一节（约 2 秒）并以同一套 `record FAIL` 决定退出码——负控调的是**真的 `./reproduce.sh`**，不是它的复制品，因此「改坏一份输入 → 这条命令非零退出」是端到端跑出来的，不是推断的。两条备选路都被这条比下去：注入输入目录要在十个 builder 里各加一个根参数（改动面大、且 builder 自带路径推导），复制一份判断逻辑给负控用则两处会漂。

`p-entry3` — 被点名的 9 个 `.log` 处置选**入库**，不是清单：以 gzip 存到原路径旁（原始 9339155 字节 → 1023126 字节），`gzip -dc | sha256sum` 与原文件逐个相同后删掉原 `.log`，一处事实一个家。清单只给一个本机路径，从 clone 读不到就打不开，而这几份日志载着无法重算的事实（`n_ctx_slot = 4096`、两行 OOM、`creating MTP draft context`、`CORRUPT` 与 `FileNotFoundError` 的计数）。其余 26 个（venv 入口、`mres` 原始逐题产物、`ppl_corpora`）走已声明的忽略类。

    python3 checks/evidence_logs.py    # exit 0
    点名的 `.wrapup/…` 路径 162 条：入库 89、目录/前缀 39、通配 32、按类忽略 2、无处置 0

「入库 89」已含那 9 个 `.log.gz`（文档里的引用已改成 `.log.gz`，所以它们现在按路径本身被认成入库）。同一命令还核 9 个登记条目的 gunzip 字节数与登记值相同。`reproduce.sh` 已按 FAIL 调用它；被点名的证据行同步改成 `zgrep … .log.gz`，a11 的 res8 不再声称那份日志没入库。

## 一条命令能看到的当前状态（`9e89f91`）

    ./reproduce.sh        # exit 0；51 行 PASS，FAIL/WARN/SKIP/BLOCKED 行 0
    python3 checks/router_refs.py && python3 docs/check_docs.py   # 都在 9e89f91 之后的工作树上 exit 0（65/65 引用解析）

哪条检查被这次改动失效、我重跑了哪条：`9e89f91` 之后我只改了 `docs/plan/subprojects.md` 的 `entry` 两行与 `STATUS.md` 的一段散文，故 `router_refs.py`（exit 0）、`docs/check_docs.py`（exit 0）、`checks/evidence_logs.py`（exit 0）都在改后重跑过；`./reproduce.sh` 未在加了这两段散文的树上重跑——它比 `9e89f91` 多出来的只有文档散文。

## 需要你决定的事

无。

## 残余风险

- `checks/evidence_logs.py` 没有负控：它能绿，但我没有用一份已知错误的树证明它会红。按「未跑的不算通过」，这条只能算检查已生效、打红能力未验证。
- 那 26 个按类忽略的文件只有「类」这一层处置，没有逐文件哈希；类被改窄时它们会重新变成死引用，靠的正是 `checks/evidence_logs.py` 变红（而这正是上一条未验证的能力）。
- 里程碑复核未派：按复核门，这两个包的证据要一个独立复核者先跑命令再判；我没有在本段里派，`entry` 因此只有作者自证。
