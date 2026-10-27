[English](README.md) | **简体中文**

<img src="assets/logo.svg" alt="tiny-llm-eval-factors" width="200">

# tiny-llm-eval-factors

*一个可复现的测量台：量清楚到底是哪个因子在动本地语言模型的基准分。*

**量化位宽、模型规模、解码协议、判分口径：一次只动一个因子，全部落进同一个 SQLite 库，报告由干净 clone 逐字节重建。**

6-bit 掉到 4-bit，模型到底丢不丢代码能力？厂商推荐的采样档是帮忙还是把一轮评测跑塌？KV 缓存精度在 32k 上下文上要不要付代价？这类问题在本仓库里由受控面板、逐题产物和一份生成式报告来回答——印在报告里的每个数字都是从 `experiments.sqlite` 当场算出来的，不是手抄进散文的。它是研究证据，不是模型发布，也不声称所有计划中的对照都已做完：未知、阻塞、未测始终与 0 和负结果分开记。

## 快速开始

从干净 clone 到重建出报告：

```bash
sudo apt-get install -y fonts-noto-cjk       # 图表字体是被复现条件的一部分
python3 -m pip install -r requirements.txt   # 本机实测约 1 分钟（含 matplotlib 依赖）
./reproduce.sh                               # 核对输入并从库重建报告，约 40 秒
```

`./reproduce.sh` 按顺序走完整条链，任何一步失败都以非零退出：运行时依赖 → 提示集 SHA256（`.wrapup/prompts/SHA256SUMS`）→ 报告输入 → 数据库完整性与清洁度 → 是否还有可执行脚本引用已退役的绝对根路径 → 文档检查 → 从 `experiments.sqlite` 重建 `report.html` 并与仓库里那份**逐字节**对比 → 用 `checks/report_check.py` 核对报告与产物一致。最后一行 `OK：报告可从库重建…` 是完成信号。`SKIP` / `BLOCKED` 行表示该项**未**验证（例如干净 clone 里没有本机的 `.wrapup/mres/` 落盘产物），不能当成绿。

本机实测（8 线程 / 4 核 CPU、无 GPU、与其他进程共用）：报告构建 2m31s；一次完整 `./reproduce.sh` 2m44s。依赖实测于 Python 3.14.8（见 `requirements.txt`）；这些数比专用工作站慢，但与 GPU 无关。

需要跑 `lm-eval` 时，按锁定的依赖重建 venv，不要把 venv 入库：

```bash
./bootstrap_venv.sh .wrapup/lmenv requirements.txt
```

**CJK 字体是复现条件，不是装饰**：它的路径与期望 sha256 只有一个家——`make_report.py` 的 `CJK_FONT` / `CJK_FONT_SHA256`。构建末行打印的 `cjk font: <路径> sha256=<哈希>` 就是本次实际用的那一份，`./reproduce.sh` 也把这一条当单独一步核对。缺它或版本不对时构建**直接失败**并说明装什么，不静默换字体——换字体后 86 张图的字形与度量都变，报告就不再逐字节相同。

干净 clone 重建不了的东西：模型权重（`.gguf` 不在仓库内，原始权重文件已不在本机；本仓库没有 `artifacts.tsv`，也不打算为它们建一份——那些字节已丢失）、`/tmp/MultiPL-E` 提示缓存、CJK 字体（系统包，按上面的命令装）、以及评测运行本身（需要 GPU 与模型文件）。

## 现在能做什么

十六个研究单元全部结项，第一版交付物是 21 节 / 86 图的报告（`report.html`，一条命令重建）。已测的因子：

- **量化位宽**——每个家族一条可复算的分数曲线，带拐点与区间；记录在库的数据里只有 Qwen3.5-2B 有非退化的拐点。三元与极低位宽变体各有「支持 / 否定 / 有界」的明确结论；12B MMLU 异常由一次逐位重复归位为文件与协议的性质。
- **模型规模**——旧的「规模」列逐行审计后只有一部分可信；规模这一因子改用入库 fixture 的 GGUF 张量参数量，登记了 63 条同族同配方曲线，并将双变量回归判为不可识别。
- **量化方案与厂商标签**——同字节下两者在本设计的分辨力内不可分辨；标签被证明是比特分配的代理。
- **MoE 各层比特分配**——钉住总比特后均匀优于专家优先，预算项与分配项可分离；但那是 *n=1* 且对手是已知病态臂，这一点也照样写在结论里。
- **KV 缓存精度**——短上下文会改变个别题的判定且方向双向，而聚合分看起来没动；长上下文用针检索覆盖到 32k，未观察到差异，并给出可观测下限。
- **采样与解码**——厂商推荐档让 MultiPL-E 与 EvalPlus 塌陷；单变量探针把成因归到 `temperature=1.0`，而不是惩罚项或 `top_p`/`min_p`。
- **投机解码**——速度与质量一起测；字节同一性地板为 164/164（跨会话），投机臂 164 题里 73 题与基线不同，且差异在两侧都可复现。
- **思考开关、QAT、第三方方案（GSQ-RCO）、扩散式解码、逐语言 MultiPL-E、BFCL 工具调用、部分给分**——每一项都有已闭合的判定、部分支持的判定，或明确的「门槛 / 未测」登记。
- **判分与基准有效性**——每个 harness 一份审计，确定性解码的噪声地板为 0 题，单次噪声有数；已退役的分数（围栏剥离、跨语言池化）按撤回处理，而不是悄悄修好。

每条判定的证据与复算命令住在拥有它的子项目 `RESULT.md` 里；`FINDINGS.md` 是路由表，说明哪条结论住在哪个节点、现在该怎么读（`current` / `provisional` / `retracted`）。

## 架构

两个存储加一份生成物：测量进 `experiments.sqlite`，派生索引进 `report_inputs/`，`make_report.py` 从这两处渲染 `report.html`。数据库下游的任何东西都不手改。

```
tiny-llm-eval-factors/
├── experiments.sqlite     # 数据 SSOT：一次测量一行，派生列以 `__` 开头
├── make_report.py         # 从库与 report_inputs/ 渲染 report.html 与图（以只读方式打开库）
├── migrate_db.py          # schema 升级与运行产物入库
├── exp.py                 # 实验脚本共用的库助手
├── report.html            # 生成物：21 节 / 86 图，不得手改
├── report_inputs/         # 报告除库之外要读的派生索引，以及它们的生成器
├── checks/                # 39 个基础设施检查，每个都配一条负控
├── docs/                  # pain / need / product / architecture / method / plan / subprojects
├── .wrapup/               # 运行产物、提示集、面板脚本（入库判据见下）
├── migrations/            # 一次性数据迁移
├── inbox/                 # 与上一层交换的消息
├── reproduce.sh           # 一条命令核对并重建整条链
├── bootstrap_venv.sh      # 一次性 venv 构建（venv 不入库）
├── requirements.txt
├── STATUS.md              # 它是什么、现在什么状态、下一步落在哪
├── FINDINGS.md            # 结论 → 事实所在节点，带读法状态
├── AGENTS.md              # 数据信任、实验与数据库安全规则
└── LICENSE                # MIT
```

各部件怎么接起来：评测运行写出逐题产物（`.wrapup/mres/*_eval.json`）与面板摘要 → `migrate_db.py` 先做编号备份（`.bak1`、`.bak2`…）再入库，认不出的名字逐条报出而不是猜 → `report_inputs/build_*.py` 派生报告需要的索引（题量、未解问题、配对差、规模说法……）→ `make_report.py` 渲染报告与图 → `checks/report_check.py` 重读产物：行标签重复、印出的题量与产物矛盾、或把「两个值分不开」的格藏起来，都判失败。`./reproduce.sh` 把这一切串成 `PASS` / `SKIP` / `FAIL` 行。

### 事实落在哪

- `experiments.sqlite` 是已记录测量的数据 SSOT。
- `docs/plan/subprojects.md` 拥有研究划分：哪个单元拥有哪一节、它的 goal 与 AC。
- `docs/subprojects/<id>-<name>/PLAN.md` 拥有该单元的里程碑与工作包；`RESULT.md` 拥有它当前的结论，每条带证据与复现命令。
- 不按单元切分的层住在 `docs/pain/`、`docs/need/`、`docs/product/`、`docs/architecture/` 与 `docs/method/`（方法 / 协议在 `method.yaml`）。
- `AGENTS.md` 规定数据信任、实验与数据库安全规则。
- `docs/check_docs.py` 按 `docs/docs.schema.yaml` 校验文档，今天退出 0。
- `checks/` 是基础设施检查：数据库完整性与清洁度、报告与产物一致、退役绝对路径，以及路由表本身。
- 入口是 `STATUS.md`（它是什么、当前状态、下一步）；`FINDINGS.md` 是结论索引。

### `.wrapup/` 里什么入库

`.wrapup/` 收运行产物、下载的语料与其他可再生成的实验产物。一条判据（`@regeneration_cost`）决定什么入库：**产物带着断言、且不能从已入库的东西重算出来，就入库；是可重建的分发件，就留在外面。**

- **入库（证据）**：`.wrapup/prompts/`（提示集加 `SHA256SUMS`）、`.wrapup/mres/*_eval.json`（逐题评测产物——「没有一格全 `Exception` 还带分数」以及每个印出来的题量，靠它在干净 clone 里可查；用 `git ls-files '.wrapup/mres/*_eval.json' | wc -l` 当场数）、面板脚本与它们产出的 `*_summary.jsonl`、`bpw_map.json`、`report_inputs/` 下的一切，以及**被子项目 `RESULT.md` 以 `evidence:`/`repro:` 点名的聚合产物与日志**（`evalplus.json`、`lmeval_panel.json`、`ident_control.json`、探针输出；运行日志以原路径旁的 `.log.gz` 入库；面板的 per-task `lmeval_*.json` 邻居一起入库，因为 `migrate_db.py` 从里面取 metric 名与分数，缺了它干净 clone 里的 refresh 会把那几行重写成 `#None`）。判据是「被点名」，不是「体积小」。
- **不入库（可重建缓存）**：`.wrapup/mres/*.jsonl` 逐题样本、venv（`lmenv/`、`msenv/`、`evalpy/`、`bfclenv/`、`mplenv/`）、`jars/`、运行日志与进程戳、`dl_ready/`、`ppl_corpora/`、`figures/`（由 `make_report.py` 重绘，库里一行不差）、DB 备份与旁路文件（`experiments.sqlite.bak*`、`*.sqlite-wal`、`*.sqlite-shm`）、`.tmp/`。

上面第二栏只是摘要：类清单的唯一 home 是 `checks/evidence_logs.py` 的 `REBUILDABLE_CLASSES`，它同时说明哪条 ignore 规则算哪一类、该类允许什么路径形状。要增删一类就改那张表，不另写一份。被点名的证据是否真的入库不由这段文字断言，而由 `python3 checks/evidence_logs.py` 逐条核：盘上有 run 文件的那台机器上它核到文件并 exit 0；干净 clone 里只能按声明 / 索引判，于是报 `BLOCKED`（exit 2）并给出本次有多少条判不了。不可得不是通过——别把干净 clone 当成绿。

## 怎么开发

先装运行时依赖（同快速开始），然后工作中直接跑单个检查：

```bash
./reproduce.sh                                  # 提交前的整条门
REPRODUCE_INPUTS_ONLY=1 ./reproduce.sh           # 只跑报告输入一节（约 2 秒，供它的负控使用）
python3 checks/db_check.py                      # 结构、外键、必填字段、取值域、重复测量身份
python3 docs/check_docs.py                      # 文档 schema（docs@1）
python3 checks/router_refs.py                   # STATUS/FINDINGS/README 里每条节点引用都解析得到
python3 checks/readme_counts.py                 # README 的入库说法与 `git ls-files` 一致
python3 checks/evidence_logs.py                 # 每条被点名的 .wrapup 产物都有处置
python3 checks/<name>_negative_control.py       # 证明某个检查真的会红
```

每个检查都配一条负控，证明它守着的东西坏掉时会失败；这一对才是 `./reproduce.sh` 调用的东西。`checks/README.md` 逐条说明每个脚本证明什么、谁调它。本仓库没有 lint、没有构建步骤、也没有 CI——`./reproduce.sh` 就是那道门，任何一条不成立都以非零退出。

动数据时不可让步的规矩：任何库改动前先做编号备份（`.bak` 系列），保持库清洁（必填字段无 null、分数在取值域内），永不手改 `report.html`，改了 `report_inputs/` 里某份的来源就同时重建那份输入与报告。

## 怎么贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。一句话：会动到数字的改动，必须带上复算它的命令和「它坏掉时会变红」的那个检查；开 PR 之前 `./reproduce.sh` 必须 exit 0。

## 路线图

**已实现**

- 十六个单元结项，覆盖位宽、模型规模、方案 / 厂商、MoE 分配、KV 缓存、采样、投机解码、思考开关、QAT、第三方量化、扩散式解码、逐语言代码、工具调用、部分给分、判分有效性与测量基础设施。
- 第一版报告：21 节 / 86 图，干净 clone 从 `experiments.sqlite` 逐字节重建。
- 里程碑 `entry`：读者进仓库的两道门（`STATUS.md`、`FINDINGS.md`）都只指真实存在的节点，这条性质由 `checks/router_refs.py` 与它的二十一条期望负控守着。结果 revision `3287b76` 上判接受。
- 39 个基础设施检查，每个配一条证明它会红的负控；报告输入做漂移检查，旧索引是硬失败而不是警告。

**计划中**

- 三类**未测**已定价并登记、但未解决：显存不足（已定价、未买）、缺运行时（`GATE-FAIL`）、本环境不可测。它们登记为未测，永不记为低分。
- 扩散式解码（单元 `a11`）：上游门槛已于 2026-10-27 解除，尚无分数——待办是给出受控对照，或把门槛本身复现出来。
- 两条已裁决接受的测量限制，记录而不隐藏：表格行键容纳不下 `top_k`；审计只能证明某个值在面板多重集里，不能逐格归属。
- 下一个研究方向（买更多显存，还是换题目）需要人的判断，本仓库有意不替它定——`STATUS.md` 里就写明了这一点。

远期想法：把同一套纪律——一个因子、一组面板、一份产物、一条从结论到证据的路由——推到那些目前停在资源墙上的因子上。交付物仍然是一份陌生人能重建的报告，因为重建不出来的结论不叫测量。

## 许可

原始代码与文档沿用仓库既有的 MIT 许可，见 [LICENSE](LICENSE)。模型权重、基准数据集与其他第三方材料各自保留自己的许可，不因本声明而重新授权。
