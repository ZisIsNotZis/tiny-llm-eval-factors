kind:    report
from:    local_lm_research (manager, deepseek/deepseek-flash, thinking medium)
spend:   machine_time
id:      none — first report of this advance; the previous run was killed by the runtime at 30 minutes, not by a decision

## 结论

里程碑 `entry` **未达成**，但它的一个工作包结项：`p-entry1`（报告第二节停在旧 `size_claims` 上仍判绿）已落定，报告与仓库里的 `report.html` 从库重建后逐字节相同。剩下 `p-entry2`、`p-entry3` 未做，两者都在 `docs/plan/subprojects.md` 的 `entry` 表里，各有验收命令。

## 一条命令能看到的当前状态

在 `99214a9` 上：

    python3 checks/router_refs.py && python3 docs/check_docs.py && git status --porcelain

exit 0、exit 0、无输出。`./reproduce.sh` 在前一个提交 `e51c86b` 上 exit 0（跑完的输出里以 FAIL/BLOCKED/WARN/SKIP 开头的行数为 0，PASS 行 49 条），末行判「报告可从库重建，且与仓库里的 `report.html` 逐字节相同」；`e51c86b..99214a9` 只改了 `docs/plan/subprojects.md` 的一行散文，所以哪条检查被这次改动失效，我重跑了哪条：`router_refs.py` 与 `docs/check_docs.py` 都在 `99214a9` 上 exit 0，`./reproduce.sh` 未在 `99214a9` 上重跑（它比 `e51c86b` 多出来的只有那一行文档）。

## 这一段推进里发生了什么（按提交）

1. 上一次被杀留下的四处改动，先验后落：`checks/router_refs.py` 与它的负控（十六行→二十一条期望）都真会红，落成两个提交；`p-entry3` 的台账按取证命令重算成 35 个未入库文件 / 9 个 `.log` / 9.3 MB（上一版写的 146 处 / 48 / 14 MB 已按同一命令证伪并删掉）。
2. `p-entry1`：`size_claims.json` 跟着 a02 重生成（3364 行 / 170 组 / 77 文件 / 2101 行），`report.html` 随之重建；`checks/size_claims_negative_control.py` 里写死的 291 与 76 改成从索引读，否则库一长它就变成一条假绿。同时把 a02 `RESULT.md` 里自相矛盾的一处（同一文件另一节已写 170/77/2101）跟到当前产物。
3. `mail/` → `inbox/`：这条目录按规则改了名，文件头从五行收到四行（方向由 `from:` 读出，去掉 `to:`）。

## 需要你决定的事

无。下一步按仓内顺序是 `p-entry2`（把 `reproduce.sh` 里 13 处「输入与来源不一致」的 WARN 判成 FAIL）。它的负控怎么跑还没定：`reproduce.sh` 的路径由自身位置推出、不能在临时树上跑，可走的两条路是给它一个注入输入目录的开关，还是把这 13 条判据抽成能指向任意目录的独立脚本 + 毫秒级负控。这是设计判断不是要批准，下一段推进里我自己定并记录，除非你要另一种。

## 残余风险

- `p-entry3` 的 9 个 `.log` 共 9.3 MB 仍未入库，干净 clone 里那些证据行指不到；处置方式（入库 / 改引用 / store-or-declare 清单）还没选。
- 未结项的 `p-entry2` 意味着下一次输入漂移仍会带着旧值判绿。
