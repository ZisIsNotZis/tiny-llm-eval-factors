# a07 投机解码 — 孙 agent 规则

本文件只写本子项目里会让孙 agent 做错事的地方。仓库级与子项目级的通用规则见
`/home/z/vibe/local_lm_research/AGENTS.md` 与 `docs/plan/subprojects.md`，此处不复述。

## 边界

- 可写：`docs/subprojects/a07-投机解码/` 下的全部路径，以及 `.wrapup/mres/m*-spec-*`（测量产物，git 忽略）。
- 不写：其他子项目的目录、`docs/plan/subprojects.md`、`make_report.py`、`.wrapup/mktables.py`、`report.html`、
  `.wrapup/spec_panel.py` 与 `.wrapup/m28_speed.py`（历史测量装置；发现缺陷写进本目录并按工作包上报，不改它）。
- 本轴有**两节**（报告第七、第八），但只有一个自变量（草稿深度）。两节的数字来自同一批行（`mktables.axis_spec`
  一次读 `spec_type IS NOT NULL AND run_tag<>''` 造两节），所以「同一次运行既量速度也量分数」这一点在呈现上成立；
  不要为了「质量」另跑一批没有 tok/s 的格，那样两节就对不上同一批行了。

## 一格的身份里有 spec_type 与深度

- `spec_type`（`none` / `draft-mtp`）与 `spec_draft_n_max` 都是协议身份的一部分，和 `protocol`/`max_tokens`/`ctx` 同等。
  投机格永不与贪心格池化，深度 0 与深度 k 也永不平均（a06 的约束）。
- 已有一处违反：`m28-speed` 的 15 行 `protocol` 串不随深度变（`RESULT.md::identity-m28-protocol`）。只登记，不手改库。
- `model` 列**不区分** MTP 与普通文件：`canonical_model()` 会把 `-MTP` 段丢掉。做跨格比较前先看 `_file_size` 与
  `spec_evidence.py` 的 `[D]` 段，确认两侧是不是同一个文件。

## 「同一」必须点名是哪种

- 两种「同一」：分数同一（逐题判决相同）与字节同一（完成物逐字节相同）。**互不推出**：
  35B 的 n1/n2 有 51 条完成物不同而分数一字不差（`RESULT.md::byte-vs-judgement-decoupled`）。
  写结论没点名，就等于没写。
- 字节同一只能在 humanEval 上判：`gsm8k`/`ifeval` 的历史运行没带 `--log_samples`，没有逐题样本。
  不要用「分数没变」去替代「输出没变」。

## 地板是谁给的

- i01 的确定性地板是 **0 道题**（同一 cell 重跑逐题差异 0、完成物 sha256 相同）。它是在**另一个文件、另一个 harness** 上测的；
  本装置的 n0 重复（`PLAN.md::WP2`）未完成前，`[C]` 的字节差异在归因上要写「依赖 i01 的地板，未在本装置复验」，
  不许直接写成「已证投机改变输出」。

## 时间 claims 的三件套

- 重复次数、逐次值、同卡负载，缺哪件写缺哪件。`m12x` 只有均值（无 CI），`m28` 有逐次值。
- tok/s 一律取 llama-server 自己的 `timings.predicted_per_second`，不用墙钟：墙钟含起服与排队。
  `_wall_time` 列是另一个口径，不允许混用。
- 起服前看 `nvidia-smi --query-gpu=memory.free`；起服后断言 `server.log` 里 `n_slots = 1`（历史五个面板都是 1，
  `--check` 会把这条机器化），不符即作废该次测量。

## 跑 GPU 作业的纪律（踩过三次，别重犯）

- 一律 `setsid nohup bash -c '…' > .wrapup/a07_<tag>.log 2>&1 &`：会话被 30 分钟上限打断时作业要活着。
  pid 落 `<tag>/client.pid`（客户端）与 `.wrapup/a07_ident.pid`（server），并写进 `PLAN.md` 的「在跑的作业」。
- **不要用会匹配到自己命令行的 `pkill -f <脚本名>`**：它会把发起它的那个 shell 一起杀掉，
  并且顺手杀掉同一模式的别的作业（本轴因此丢过一次 0.8B 的跑批）。要停就按 pidfile 里的 pid 停。
- 子进程必须 `prctl(PR_SET_PDEATHSIG, SIGKILL)`：客户端死了 server 要跟着死，否则留下吃显存的孤儿
  （实测过一次：客户端死后 server 空转 52 分钟、零请求）。守则演练：`--vram-only --hold-seconds 90` 起服，
  `kill -9` 客户端，6 秒内 server 必须消失、整卡回到起服前。
- **同名臂不能共用一个 `codegen/<arm>` 目录**：`evalplus.codegen` 会接续既有输出，第二次运行 5 秒跑完、
  复用上一次的完成物，于是得到「164/164 相同」的假地板。同名臂目录加 `-r2` 后缀，且比对要按**目录名**取产物。
- 每臂结束就往 `evidence/spec-runs.jsonl` 追加一行（tag/arm/分数/产物/GPU 分钟/时间）；连续两臂无产物 → 打印原因并 exit 1。
  进度只看这个账本，不看 `ps`，也不看日志尾部。

## 承重证据必须入库、且伪造必须红

- 「字节地板 = 0」这条结论的承重证据是完成物原文：`evidence/bytes/` 的 6 个臂（`BYTE_ARMS`）。
  加/换臂要同时更新 `BYTE_ARMS`、`EXPECTED_FLOOR_PAIRS` 与入库字节，否则 `--check` 会红（故意的）。
- 退出码语义：`0` = 四段跑完且本机完成物与入库字节逐条一致；`2` = 缺输入（含 `[E]` 的臂、
  `ident_control.json`、`m28_speed.jsonl`、地板对数 ≠ 期望）；`1` = **伪造/漂移**（本机完成物与入库字节不一致）。
- 任何承重断言都要有负控，且负控要能点名：`--selftest` 三例（分数层 / 入库字节层 / 本机字节层），
  任何一例不红就返回非 0。改坏一条完成物时，报错必须写出 `tag/arm/task_id`，不能只说「计数不对」。
- 9B 的 19 对没有入库字节：`--check` 会明写「另 19 对无入库字节」，不许把它读成已验证。

## 脚本纪律

- 数字只从 `spec_evidence.py` 出来：`--write` 落 fixture，`--check` 与库/自算逐字对，`--selftest` 证明检查会变红。
  **不许手改 `fixtures/*.tsv`**：手算与 fixture 不一致时 fixture 赢，或者是脚本的选择规则错了，两者都要修一个。
- 加了新臂或新基准，**在现有脚本里加**，不另写一份分析脚本（同一个问题两个家）。
- 脚本只读打开库（`file:experiments.sqlite?mode=ro`），不写库；缺输入时退出 **2**，不许打印 `UNMEASURED` 后退出 0。

## GPU 与库

- 任何 GPU 任务都在 `bash .wrapup/gpu_locked.sh` 下跑；同一张卡还有别的仓库的任务，锁只管本仓库。
- 改库：编号备份 → 只经 `migrate_db.py` → `db_check` → 行数对账。`ingest_spec` 会先
  `DELETE FROM experiments WHERE source_file LIKE 'mres/%-spec-%'` 再重读所有 panel，所以要报「改前/改后的 spec 行数」。
- 不重生成提示集：`.wrapup/prompts` 是唯一来源。

## 交付

- 每条事实写「结论 / `- evidence:`（可重跑的命令或落盘文件）/ `- repro:`」，不写「已确认」「已验证」。
- 未测写「显式未测 + 理由 + 解除条件」。未测 ≠ 0。
- 结束时报：做了什么、改了哪些文件、跑了什么命令得到什么结果、还剩什么风险；没有独立复核就写「未复核」。
