# a12 多语言代码 MultiPL-E — 孙 agent 规则

本文件只写本子项目里会让孙 agent 做错事的地方。仓库级与子项目级的通用规则见 `/home/z/vibe/local_lm_research/AGENTS.md`，此处不复述。

## 边界

- 只有派工单里点名的路径可写；a12 的文档在 `docs/subprojects/a12-多语言代码 MultiPL-E/`，其他子项目的目录、`docs/plan/subprojects.md`、`make_report.py`、`.wrapup/mktables.py` 都不在本子项目的写权限内。
- `report.html` 是生成物：永不手改，改数据后重新生成并核对。
- 报告代码里的问题（例如标准列把 cpp+py 加权成一个格）只登记 + 提供证据，不擅自改；改法要 meta 裁决。

## 单元格纪律

- 不跨语言、不跨协议做池化：一格的 Y 只能来自同一个 model × language × protocol，可比的跨模型比较必须固定语言集。
- 整格全 `Exception`（harness 一次都没能执行完）的格是 NULL，不是 0；这一条是唯一把格变成 NULL 的规则。
- 跑过但没通过的格是真分数，0.0 也是分数：`SyntaxError` 主导的格（例如 gemma-4-12b raw 下的 java 158/158、rs 154/155）保留 0.0，但必须在 `RESULT.md` 写成「该协议下的 harness floor 或真实通过数」，不得与其它格同权地读成能力差异。
- 生成被截断、题数不足满格、或整格只是几十题的探针（例如 m30 的 60 题格）不是分数，不能披着 0.0 进比较：这类格要标出成因并交回给拥有那条轴的子项目。
- 未测 ≠ 0：没跑就登记「显式未测 + 理由」，不填默认值。
- 补测前先确认这一格在 `RESULT.md` 的覆盖表里是空格，并说明它为什么值得花 GPU。

## 数据与入库

- 任何改库前先做编号备份（`experiments.sqlite.bakN`），改完跑完整性与洁净检查（无空必备字段、布尔/范围合法）。
- `migrate_db.py` 是唯一入库路径，必须保持幂等；不进库的数字不算存在。
- 数字只从库或落盘产物来，不抄文档；写完跑 `python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"`，退出非 0 就先修，不得带着失败交付。
- 改了审计或负控，就跑 `bash "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_negative_control.sh"`：它故意篡改报告副本，审计必须拒绝。只跑审计不跑负控，等于没证明检查会失败。
- 交付证据要绑定版本：捕获里要有 `git rev-parse HEAD`、脚本 sha256、运行的命令和完整输出（审计自己打印这四行），存在 `evidence/` 下，文件名带短 revision。

## 测量

- 每个 GPU 任务都必须在 `bash .wrapup/gpu_locked.sh` 下跑，一次一个；不同时起两个模型服务。
- 提示集只用 `.wrapup/prompts`，跑前跑后都不许重生成；要重生成先问。
- 判分前后处理必须是 `mpl_run.strip_fences` 的当前版本，先跑 `python3 .wrapup/test_mpl_postprocess.py`（5/5 通过）再判分。
- 协议串按原样入库：`ctx=`、`kv=`、`tmpl=` 三段是设置本身，不能省略或改名；不同设置的格不许压成同一个行标签。

## 交付

- 每条事实写「结论 / 证据 / 复算命令」，证据必须是能重跑的命令或落盘文件路径，不写「已确认」「已验证」这类无证据的话。
- 采集失败、探针格、被取代的旧值都要写出来，而不是从结果里删掉。
- 结束时报：做了什么、改了哪些文件、跑了什么命令得到什么结果、还剩什么风险；没有独立复核就写「未复核」，不得自评通过。
