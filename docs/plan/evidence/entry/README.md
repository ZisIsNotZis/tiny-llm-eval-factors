# entry 里程碑的证据捕获（本次结果 revision）

七份捕获，一个包一份，文件名带短 revision。每份首部记被审 revision、脚本 sha256、命令与 `rc=`，
尾部记该包承重产物的 sha256——门 3 要的四件（revision / 命令 / 输出 / 产物 sha256）都在一个文件里。

当前结果 revision 是 `5e6df26`（`*-5e6df26.txt`，整条链是 `reproduce-5e6df26.txt`）；上一次结果 revision
`00be81d`（`*-00be81d.txt`）与更早的 `*-e338f4b.txt` 作为历史保留：`e338f4b` 那一版在干净 clone 里
`checks/evidence_logs.py` 红 13 条，正是 `00be81d` 修掉的那条复核门；`5e6df26` 又把逐题评测产物从
「可重建缓存」档里摘出来（被点名却没入库的 `*_eval.json` / `*_panel.json` 必须红，负控第 7 例）。

重建方式：在被审 revision 的干净工作树上重跑同一批命令（`docs/plan/subprojects.md` 的 `entry` 节
表格逐行给命令）。这些文件只是把那次运行的输出留下来；任何数字都不在本目录里手写，数字来自命令。
