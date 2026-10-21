# a07 投机解码 — 结果

本文件是本子项目结果层的唯一 home（原 `result.yaml::res11` 已迁入并重写）。每条事实写成
一行结论 + `- evidence:` + `- repro:`；数字的当前值只在这里，报告里的图与表由数据库重新生成，不引用本文件的数值。

数据源：`experiments.sqlite`（只读打开）、`.wrapup/mres/m12{5,6,7,8,9}-spec-*/spec_panel.json`（速度 + 四个基准）、
同一目录的 `codegen/n{0,1,2,4}/humaneval/*_eval_results.json`（逐题判决）与 `*_openai_temp_0.0.raw.jsonl`（逐题完成物原文）、
`server.log`（`n_slots` 与草稿接受率）、`.wrapup/m28_speed.jsonl`（第二份速度测量，带逐次值）。

复算入口（首行打印被审 revision、脚本 sha256、面板根，所以捕获绑定到版本而不是绑定到说法）：

- `python3 "docs/subprojects/a07-投机解码/spec_evidence.py"`，退出 0 = 四段全部跑完。
  缺 `.wrapup/mres/*-spec-*/spec_panel.json` 或 `.wrapup/m28_speed.jsonl` 时打印 `UNMEASURED` 并退出 **2**。
- `python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --check`，退出 0 = 6 份 fixture 与库/自算一致：
  每个质量行对上库里的 `_score`（同一 `run_tag` + `spec_draft_n_max` + `_bench`）、每个速度行对上 `_tok_s`、
  每格逐题通过率**复原**该格的 humaneval 分数、每臂 server 自报 `n_slots = 1`、`identical + differing = n`。
  库在仓库里，所以这一条在干净 clone 里也能跑。
- `python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --selftest`，退出 0 = 把 `quality_depth.tsv` 的每一格
  加 0.05 后 `--check` 变红（退出 1）——证明这条检查会失败，不是空转。
- 已存捕获：`evidence/spec-evidence-<revision>.txt`（四段，退出 0）、
  `evidence/spec-evidence-negative-control-<revision>.txt`（空临时树里跑同一脚本：两个输入全缺 → 退出 2）、
  `evidence/check-<revision>.txt`、`evidence/selftest-<revision>.txt`。

## 一、速度：深度换速度，但不是单调、也不是到处成立

## res11 :: 投机解码：草稿深度换速度，但输出与分数都不是「开到最大就好」

- kind: measured
- from: result.speed-depth-panels, result.speed-depth-longctx-negative, result.quality-mmlu-inert, result.byte-identity-fails
- 迁移自 `result.yaml::res11`（`origin: .scratch/originals/L2-结果.md`），四句里两句按实测重写：
  「草稿深度越大速度越快」→ 只在 4B/9B/35B 的代码提示上成立，2B 在 n4 掉头、长上下文在每一个深度都更慢；
  「分数随深度几乎不变，MMLU 在每个深度逐位相同」→ MMLU 逐位相同是**结构事实**（对数似然打分、不生成 token），
  不是质量证据；能生成的三列确实在动，且贪心输出与不开投机**不逐字节相同**。

## speed-depth-panels :: 五个模型（0.8B/2B/4B/9B/35B，Qwen3.5/3.6 UD-Q4_K_XL 与 IQ4_XS）在 ctx=8192、`-np 1`、贪心下，tok/s 随草稿深度 n∈{0,1,2,4} 上升；相对 n0 的增益是 0.8B +36.1%、2B +8.0%、4B +82.9%、9B +91.8%、35B +77.1%

- kind: measured
- evidence: `spec_evidence.py` 的 `[A]` 段逐行（`m125-spec-0.8b` 423.45→460.69→534.88→576.19；`m126-spec-2b`
  319.62→350.15→360.08→345.24；`m127-spec-4b` 184.07→247.77→301.90→336.60；`m128-spec-9b`
  123.37→176.64→212.14→236.62；`m129-spec-35b` 163.47→214.17→262.58→289.44）。
- repro: `python3 "docs/subprojects/a07-投机解码/spec_evidence.py"` 的 `[A]` 段。
- 限制：**每个深度只有一个数**，是 3 次重复请求的均值，逐次值没有落盘 → 没有 CI（`m28` 那份有逐次值，见 `speed-reps-spread`）。
  计时取自 llama-server 自己的 `timings.predicted_per_second`（起服时间已被排除），提示词是单一固定串
  （`def fibonacci(n):` 的函数头，`n_predict=256`），所以这是「同一条提示上的生成速度」，不是提示分布上的平均。
  **同卡上还有什么在跑没有记录**：`server.log` 里只有本进程的日志，`m12x` 五个 panel 都没写 `nvidia-smi` 的占用，
  所以这五个数不能被当成「干净卡上的上限」。

## speed-depth-02b :: 0.8B 上「深度 2 vs 无投机」的 tok/s 对照是 **423.45 → 534.88（+26.3%）**，取自 `m125` 的 `speed_probe`（同文件、同 ctx=8192、同 `-np 1`、3 次重复的均值）；今天为字节负控跑的两臂**没有测 tok/s**，所以不能用 3.80 分钟 vs 3.64 分钟去替代

- kind: measured
- evidence: `[A]` 段 `m125-spec-0.8b` 的 `n0=423.45(+0.0%) n2=534.88(+26.3%)`；`[E]` 段两臂的 `gpu_minutes`（3.8 / 3.64）。
- repro: `[A]` 段。
- 限制：缺的那个数是「今天的 tok/s」——`run_ident_control.py` 不含速度探针（它只为字节与显存而写），
  要补就得在每臂里加 3 次 `n_predict=256` 的固定生成并读 `timings.predicted_per_second`（约 +10 秒/臂）。
  臂的墙钟差（3.8 vs 3.64 分钟）**不是**速度对照：两臂的生成 token 总数不同（分数不同→提前停止的位置不同），
  且今天的卡上一直有别人的进程（起服前整卡 3.2–4.1 GiB），墙钟里含排队。

## speed-depth-nonmonotone :: 2B 上最深一档不再涨：n2=360.08 已经到顶，n4=345.24 比它低（+12.7% → +8.0%）；4B/9B/35B 在 n4 仍在涨，所以「深度越大越快」不能写成普适句

- kind: measured
- evidence: `[A]` 段的 `! 非单调` 行（脚本自动标记）；`m126-spec-2b` 的 319.62→350.15→360.08→345.24。
- repro: `[A]` 段；或 `sqlite3 experiments.sqlite "SELECT spec_draft_n_max,_tok_s FROM experiments WHERE run_tag='m126-spec-2b' AND _bench='speed' ORDER BY 1"`。
- 限制：这里是均值对均值，`m12x` 没存逐次值，所以 n2 与 n4 的 14.8 tok/s 差**不能**判为可分辨；
  能说的是「n4 不高于 n2」。第二份独立测量（`m28`，同一 2B 文件、ctx=16384、有逐次值）在 code 场景上给出同一方向
  （n3 223.11 → n4 217.80，逐次区间 219.1–225.8 与 211.3–223.0 重叠）——方向一致、可分性不足。

## speed-depth-longctx-negative :: 长上下文上投机解码**更慢**：同一 2B 文件、ctx=16384、约 8k token 的提示，n1..n4 每一档都低于 n0（−8.2%、−5.5%、−12.9%、−15.6%），而同一批里的 code 场景 n2 是 +26.2%——收益取决于提示，不取决于深度

- kind: measured
- evidence: `[A2]` 段三行：`longctx` 169.25→155.38→160.00→147.37→142.84，逐次区间在 n4 是 138.8–143.2，
  n0 是 165.8–169.3（**两个区间不重叠**，所以这一格下降比 code 那格的上升更硬）；
  `code` 168.57→177.19→212.80→223.11→217.80；`prose` 171.57→173.58→203.84→198.12→204.61。
- repro: `[A2]` 段；或 `python3 -c "import json;[print(d['mode'],d['draft_n'],d['tok_s'],d['tok_s_reps']) for d in map(json.loads,open('.wrapup/m28_speed.jsonl'))]"`。
- 限制：`m28` 只测速度、**没跑过任何分数**；每格只有 3 次重复、一次会话；它的行在库里 `protocol` 串不随深度变
  （见 `identity-m28-protocol`），所以它是速度证据，不是质量证据，也不能与 `m12x` 的格池化（ctx 不同、题不同、时限不同）。
  机制上这与「草稿接受率随上下文长度下降」一致，但本仓没有按上下文长度拆开记接受率，未验证。

## speed-reps-spread :: 两份速度测量的重复口径不同：`m28` 落盘了逐次值（3 次），`m12x` 只落盘均值；所以只有 `m28` 能给出「重复之间的散布」，`m12x` 的大数字只能当点估计

- kind: measured
- evidence: `.wrapup/m28_speed.jsonl` 每行有 `tok_s_reps`（如 n0 code 的 `[161.75, 168.57, 172.486]`，散度约 ±6%）；
  `m12x` 的 `spec_panel.json` 每档只有一个 `tok_s`（`.wrapup/spec_panel.py::speed_probe` 返回均值）。
- repro: `[A2]` 段括号里的最小–最大值；`m12x` 的缺失由 `[A]` 段无括号值可见。
- 限制：这是记录口径的缺陷，不是测量缺陷；要 CI 就得补落盘逐次值（`WP2` 顺手做，代价 0）。

## 二、质量：分数不是同一个测量

## quality-mmlu-inert :: MMLU 在五个模型、四个深度上逐位相同（0.5241/0.6250/0.7456/0.7939/0.8443），但这是**结构事实**不是质量证据：MMLU 走 lm-eval 的对数似然打分，不生成 token，投机解码的草稿路径结构上碰不到它

- kind: measured
- evidence: `[B]` 段 `mmlu` 五行全同；`migrate_db.py::ingest_spec` 对 mmlu 用的是 loglikelihood shim（`--model gguf` + `EchoShim`），
  另外三列走 `local-chat-completions`（真生成）。
- repro: `[B]` 段；或 `sqlite3 experiments.sqlite "SELECT run_tag,spec_draft_n_max,_score FROM experiments WHERE _bench='mmlu' AND run_tag LIKE 'm12%-spec-%' ORDER BY 1,2"`。
- 限制：它的价值是**正控**（测量链路在四个深度上都对），把它的「逐位相同」读成「投机不伤质量」是原 `res11` 的错误，
  报告第八节现在正是这么写的（见 `report-wording-defect`）。

## quality-moves-items :: 会生成的三列在深度上确实移动，最大单格是 2B 的 humanEval 83→91/164（+8 道题，n4），0.8B 的 IFEval 29→26（−3 道题）；九个模型×基准组合里只有 35B 的四列在 n1/n2 完全不动

- kind: measured
- evidence: `[B]` 段逐行；例如 `m126-spec-2b` humaneval 0.5061→0.5427→0.5305→0.5549（83→89→87→91 题 /164）、
  gsm8k 0.60→0.56→0.54→0.60（30→28→27→30 /50）、ifeval 0.66→0.70→0.72→0.68（33→35→36→34 /50）；
  `m129-spec-35b` 在 n1/n2 四列全同、n4 才动（humaneval 150→149、ifeval 43→42）。
- repro: `[B]` 段；`python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --check` 会把每一格的逐题通过率复原成这里的分数。
- 限制：每个 (模型, 基准, 深度) 只有**一次**运行、每个基准只有 50 或 164 题，所以这些是「移动了多少道题」，
  不是移动的分布；方向在模型之间不一致（0.8B 与 4B 多数向下、2B 多数向上、9B 向上），所以不能写「投机损伤质量」，
  只能写「投机改判了 n 道题」。

## byte-identity-fails :: 贪心输出在投机下**不逐字节同一**：同一提示、同一 server 旗标（只有 `--spec-type`/`--spec-draft-n-max` 不同）、同一 humanEval 164 题，深度 0 与深度 k 的完成物只有 **1489/2460 对（60.5%）逐字节相同**；每个模型的每个深度都有 48–86 条完成物不同

- kind: measured
- evidence: `[C]` 段逐行（`m125-spec-0.8b` n1/n2/n4 同一 90/91/95 条；`m126-spec-2b` 79/91/78；`m127-spec-4b` 112/116/107；
  `m128-spec-9b` 102/100/99；`m129-spec-35b` 113/113/103；合计 1489/2460）。
- repro: `[C]` 段；逐对本体的来源是 `.wrapup/mres/<tag>/codegen/n<k>/humaneval/*_openai_temp_0.0.raw.jsonl`（evalplus 的原始完成物）。
- 限制：归因现在**不再依赖 i01 的地板**——本装置自己的字节地板已实测为 0（`byte-floor-zero`：同一配置两次运行 164/164 相同，
  两次相隔 9 天、不同进程），且投机臂本身也能跨会话逐字节复现（`m125` n2 与今天 `m169` `draft-mtp2` 164/164 相同）。
  差异的**首次分歧位置中位数在 478–624 字符处**（`[C]` 段），远离 0，说明提示词/模板/前几百个 token 完全一致，
  分歧发生在生成中途——这与「提示不同」这一替代解释不相容。
  仍只能在 humanEval 上判：gsm8k/ifeval 的历史运行没有 `--log_samples`，没有逐题样本（i01 已登记同一缺陷）。

## byte-vs-judgement-decoupled :: 字节同一与判决同一互不推出：35B 在 n1/n2 有 **51 条完成物不同**、但逐题判决翻转 **0 道**、四个分数一字不差；反过来 9B 的 n1 也是 3 上 3 下相抵成同一分数

- kind: measured
- evidence: `[C]` 段 `m129-spec-35b` n1/n2「同一 113/164（差异 51）」与 `[B]` 段 humaneval `0.9146(0↑0↓)` 同时成立。
- repro: `[C]` 与 `[B]` 两段并读。
- 限制：这意味着「分数没变」**不能**当成「输出没变」的证据。报告第八节「所有深度分数无差别」即使分数层面成立，
  也不支持「投机不改模型行为」这句话。

## peritem-flips-exceed-floor :: 逐题判决的翻转数超过 i01 的确定性地板（0 道题）：15 个投机格里 14 个有翻转，最大是 2B 的 n4（10 上 / 2 下，净 +8 道题），最小是 35B 的 n1/n2（0 道）；净移动与逐题翻转可以差一个量级（9B n1 净 0 而 3 上 3 下）

- kind: measured
- evidence: `[B]` 段 humaneval 行的括号与 `*` 标记（`*` = 超过地板）；`--check` 用 fixture 的 3280 条逐题记录复原每个分数。
- repro: `[B]` 段。
- 限制：每个格一次运行，所以「超过地板」只说明它不是重复噪声（地板是 0），不说明它可重复；
  方向依赖模型，因此结论只能是「投机格必须各自测量」，不能是「投机更好/更差」。

## 三、草稿的成本（显存）

## draft-is-model-file :: 本仓没有「另起一个草稿模型」这条路：`--spec-type draft-mtp` 用的是**模型自带的 MTP 头**，只存在于 `-MTP-GGUF` 仓库；普通 Qwen3.5 GGUF 起服会报 `model doesn't contain MTP layers`，所以投机轴必须换文件

- kind: measured
- evidence: `migrate_db.py::ingest_spec` 的 docstring 记录了这条失败；`server.log` 里每个 `draft-mtp` 臂都有
  `common_speculative_init_result: creating MTP draft context against the target model '<同一文件>'`（不是第二个 `-m`）。
- repro: `[D]` 段；或 `grep -m1 "creating MTP draft context" .wrapup/mres/m128-spec-9b/server.log`。
- 限制：这条把「草稿模型的内存成本」改写成「MTP 头的内存成本」。真正的独立草稿模型（`-md 0.8B.gguf`）未测，
  所以「用小模型当草稿要多少显存」在本仓没有答案。

## draft-memory-head-bytes :: MTP 头的**权重**开销就是同一 gguf 名在两个仓库里的文件字节差：0.8B +14,212,256 B（+2.54%）、2B +45,149,344 B（+3.37%）、4B +78,554,272 B（+2.70%）；9B 与 35B 的普通仓库不在本机磁盘上，开销 UNKNOWN（不是 0）

- kind: measured
- evidence: `[D]` 段末四行（`-MTP` 文件字节 vs 普通仓库同名文件字节）。
- repro: `[D]` 段；单条 `stat -Lc %s /home/z/hf/models--unsloth--Qwen3.5-0.8B{-MTP,}-GGUF/snapshots/*/Qwen3.5-0.8B-UD-Q4_K_XL.gguf`。
- 限制：这是**磁盘/权重**口径，不是运行期显存；运行期还要多一个草稿上下文（KV + compute buffer），
  它的大小本仓没有记录（`server.log` 不含 buffer size 行），由 `PLAN.md::WP3` 实测。
  另外注意 `/home/z/hf/Qwen3.5-9B-UD-Q4_K_XL.gguf` 这个顶层软链**指向 -MTP 仓库**，所以按路径 stat 会得到 MTP 文件本身。

## identity-model-name-hides-mtp :: 库里的 `model` 列不区分 MTP 与普通文件：两条路都把 `Qwen3.5-9B-UD-Q4_K_XL.gguf` 归一成同一个名字，唯一的身份隔断是 `protocol` 串（`spec-mtp-draft-mtp-nk-*` vs 同名的普通格）；所以「同一模型名」在投机轴上不等于「同一文件」

- kind: measured
- evidence: `migrate_db.py::ingest_spec` 用 `canonical_model()` + `norm_model()` 把 blob 路径归一，`-MTP` 段被丢掉；
  五个 spec panel 的 `_file_size`（0.559/1.340/2.912/6.135/18.209 GB）与 `-MTP` 文件字节一致，而不是与普通仓库文件一致。
- repro: `sqlite3 experiments.sqlite "SELECT DISTINCT model,run_tag,_file_size FROM experiments WHERE run_tag LIKE 'm12%-spec-%'"`。
- 限制：对 9B 没有影响（普通 9B 仓库不在本机，全部 9B 格都在 MTP 文件上跑）；对 0.8B/2B/4B 有影响——
  这三档的顶层软链（`/home/z/hf/<name>.gguf`）指向**普通**仓库，所以研究里其他格子用的是普通文件，跨格比较就是跨文件比较。这条与 `METHOD_CRITIQUE.md` 第 8 条（「速度用 MTP repo 文件、质量用普通文件 → 文件不同」）不同：
  `m12x` 的同一个 panel 在**同一文件**上既量了速度也量了分数（`spec_panel.py` 一个会话里两件事都做），
  所以第 8 条的前半在 `m12x` 上已不成立；它说的多协议并存仍成立（`m28` 与 `spec-mtp-*` 是两套，且 ctx 不同）。

## identity-m28-protocol :: `m28-speed` 的 15 行 `protocol` 串在各深度上相同（`m28-mtp-speed-greedy`），深度只存在于 `spec_draft_n_max` 列；按 a06 的「一格的协议 = 它的身份」，这违反约束，深度必须进协议串

- kind: measured
- evidence: `sqlite3 experiments.sqlite "SELECT DISTINCT protocol FROM experiments WHERE run_tag='m28-speed'"` 只回一行；
  而 `m12x` 的行是 `spec-mtp-draft-mtp-n{k}-greedy-256`。
- repro: 上面那条 SQL；`[A2]` 段的注。
- 限制：报告 G1 表用 `spec_draft_n_max` 当行键，所以呈现上没把两档合并；但任何按 `protocol` 做聚合的查询都会合并。
  修这行属 i02 的库整洁范围，a07 只登记。

## identity-cachetype-asserted :: 库把 100 个 spec 行的 KV 类型写成 `q8_0`，但起服命令里没有 `--cache-type-*`：llama-server build 4399（`4bc272fd72`）的默认是 `f16`，所以这一列是**断言**不是测量；同理 `top_k=40`/`top_p=0.95`/`min_p=0.05` 也是服务端默认值而不是 harness 发的值（只有 `temp=0.0` 是 evalplus 与 lm-eval 真的发过去的，它盖掉了默认的 0.80）

- kind: measured
- evidence: `.wrapup/spec_panel.py::start_server` 的命令是 `-m … -c 8192 -np 1 -ngl 99 --jinja --reasoning off` + spec 旗标，没有 `--cache-type-k/v`；
  `migrate_db.py::ingest_spec` 在 `common` 里硬编码 `cache_type_k/v = q8_0`、`top_k = 40`、`top_p = 0.95`、`min_p = 0.05`。
  默认值由 `llama-server --help` 给出（`-ctk` default: f16；`--temp` default: 0.80；`--top-k` default: 40；`--top-p` default: 0.95；`--min-p` default: 0.05）。
- repro: `sqlite3 experiments.sqlite "SELECT DISTINCT cache_type_k,top_k,top_p,min_p,temp FROM experiments WHERE run_tag LIKE 'm12%-spec-%'"`；
  `/home/z/.local/bin/llama-server --help | grep -A2 -- '-ctk'`。
- 限制：这不推翻任何 a07 的比较——所有比较都在同一 panel 内，两侧的 KV 类型与采样参数逐字相同；但它意味着「投机格是 `kv=q8_0` 的协议」这句话在库里没有证据。
  修这 100 行的列值属 i02 的库整洁范围，a07 只登记。

## identity-protocol-separates :: 投机格与贪心格在库里是两个测量：`spec-mtp-draft-mtp-n{1,2,4}-evalplus|lmeval` vs `spec-mtp-none-n0-*`，`spec_type`/`spec_draft_n_max` 也不同——符合 a06 的约束（投机格永不与贪心格池化）

- kind: measured
- evidence: 五个 panel 的 20 个速度行与 80 个质量行，协议串见 `fixtures/quality_depth.tsv` 与库。
- repro: `python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --check`（对每行的 `_score`/`_tok_s` 逐字对账）。
- 限制：报告第七/八节读的是 (model, ctx, 深度) 三键，不读协议串；而两节共享同一批行（`mktables.axis_spec`），
  所以质量列在呈现上用的是**同一批格**，这一点是对的（同一次运行既量速度也量分数）。

## 四、报告口径

## report-wording-defect :: 报告第八节现在有两句被实测否掉的话：「所有深度分数无差别」（结论表）与「因此投机解码可以放心开：它买速度，不伤质量」——实测是 15 个投机格里 14 个改判了题（最多 +8 道题）、且贪心输出只有 60.5% 的完成物逐字节相同

- kind: measured
- evidence: `make_report.py` 的第八节正文（`八、投机解码（质量）` 段）与结尾结论表 `"投机解码：质量"` 一行的「所有深度分数无差别」；
  实测见 `[B]`（逐题翻转）与 `[C]`（字节同一性）。
- repro: `grep -n "所有深度分数无差别\|不伤质量" make_report.py`；`[B]`、`[C]` 两段。
- 限制：`make_report.py` 与 `report.html` 不是 a07 的写权，a07 只给替代文本，改不改由 i02 与 meta 决定。
  替代文本（建议）：速度那节保留；质量那节改成「MMLU 逐位相同是正控（对数似然，不经草稿）；会生成的三列在深度上改判 0–8 道题，
  且贪心输出与不开投机**不逐字节相同**（humanEval 60.5% 的完成物一致），所以投机格是独立协议，质量列必须各自测量」。

## 六、装置内负控（WP2）与草稿的运行期显存（WP3）

## byte-floor-zero :: 字节地板 = **0**：同一 0.8B -MTP 文件、同一贪心旗标、同一 164 题，`m125`（10-12）、`m169`（10-21 10:24）、`m170` 的两次 `none`（10:43 与 10:46）四个会话两两逐字节相同——**7 对全部 164/164**（差异 0）；`llama-server` 二进制未变（build 4399，2026-09-16）

- kind: measured
- evidence: `[E]` 段「字节地板」七行（`m125/n0` vs `m169/none`、`m125/n0` vs `m170/none`、`m125/n0` vs `m170/none-r2`、
  `m169/none` vs `m170/none`、`m169/none` vs `m170/none-r2`、`m170/none` vs `m170/none-r2`，
  以及投机臂的跨会话对 `m125/n2` vs `m169/draft-mtp2`）；逐对数值在 `fixtures/ident_pairs.tsv`。
- repro: `python3 "docs/subprojects/a07-投机解码/spec_evidence.py"` 的 `[E]` 段；
  `python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --check`（fixture 与库/自算/入库字节逐字对）。
  入库的 6 个臂的完成物原文在 `evidence/bytes/`（每个 164 条、共 988 KB），逐题 sha256 在
  `fixtures/ident_bytes.tsv`，每臂指纹在 `fixtures/ident_arms.tsv`：四个 `none` 臂的指纹都是
  `6cb6c82e601d…`、两个深度 2 臂都是 `e00510e693ad…`——**只读哈希表也能在 clone 里得出「地板 = 0」**
  （见 `byte-evidence-in-repo`）。
- 限制：这是**单模型（0.8B）、单 harness（EvalPlus humanEval 164 题）、单槽（`-np 1`）**上的地板。
  9B/35B 没有跨会话对（`m128`/`m129` 的每个深度只跑过一次），所以地板在更大模型上未复验；
  多槽（`-np>1`）的地板 i01 在 MultiPL-E 上测过（四槽与单槽逐字节相同），但 a07 没有复验。
  另外：`m169` 的第二次 `none` 臂是**同一目录的重复运行**（`evalplus` 接续上次产物），
  它被 `[E]` 段自动标注并排除出「独立会话」，真正的地板由 `m170` 的两个独立目录给出。

## byte-evidence-in-repo :: 承重证据已入库：6 个 0.8B 臂的完成物原文（164 条/臂，988 KB）随仓库走，`--check` 在**没有 `.wrapup` 的 clone 里**逐条核 sha256 + 行数，并从字节重算地板 7 对全同——地板不再是一张没有输入绑定的 fixture 表

- kind: measured
- evidence: `evidence/bytes/MANIFEST.tsv`（6 个文件的 sha256 与行数）、`fixtures/ident_bytes.tsv`（984 条逐题 sha256）、
  `fixtures/ident_arms.tsv`（6 个臂指纹）、`fixtures/sources.txt`（含这 6 个文件与 12 个 `.wrapup` 输入）。
  `--check` 的输出第二行：`入库字节 6 臂：逐条 sha256 + 行数全部对上；从字节重算的地板 7 对全同`。
- repro: 在只有 `docs/` 与 `experiments.sqlite` 的临时树里
  `python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --check` → 退出 0 且打印上面那行；
  `python3 "docs/subprojects/a07-投机解码/spec_evidence.py"`（主命令）在同一棵树里退出 2（[A]–[D] 的 `.wrapup` 输入确实缺）。
  本机再跑 `--check`：`本机重算 34 对与 fixture 逐字相符（含无入库字节的 9B 臂）`。
- 限制：入库的是 **0.8B** 的 6 个臂。9B 的 19 对（`m128` 四深度）没有入库字节，只在有 `.wrapup` 的本机可证；
  这一点由 `--check` 明写（`另 19 对无入库字节`），不算成通过。

## byte-forgery-red :: 伪造负控成立（三次演练）：改任一臂的任一条完成物，主命令与 `--check` 都**变红并点名**——`--selftest` 三例全红

- kind: measured
- evidence: `--selftest` 输出三行：分数层（+0.05 → `--check` 退 1，101 行）、入库字节层（改一条 → 退 1 且点名该臂）、
  本机字节层（`verify_live` 报 1 条且点名该臂）。另做过一次真伪造：往
  `.wrapup/mres/m169-ident-08b-mtp/codegen/none/humaneval/*.raw.jsonl` 追加一条改过的 `HumanEval/0` 后，
  主命令退 **1** 并打印
  `RED m169-ident-08b-mtp/none: 行数 165 ≠ 入库 164` 与
  `RED m169-ident-08b-mtp/none/HumanEval/0: 完成物 sha256 变了 af6abd4583c0… → 6d4d88489db5…`；
  `--check` 同样退 1 并打同两行；地板「其中不同的」从 0 变成 3 对。
- repro: `python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --selftest`（退出 0 = 三例都红）。
- 限制：`verify_live` 只能看见它知道的 6 个臂；9B 的臂没有入库字节，改它们不会被点名（`--check` 的
  「本机重算 ≠ fixture」那一步能抓到，因为 9B 的 19 对也在 fixture 里）。

## byte-identity-spec-effect :: 在地板 = 0 的前提下，开 `draft-mtp n=2` 让 164 题里 **73 条完成物逐字节不同**（91 条相同），分数从 52/164（0.3171）变成 49/164（0.2988）——这是**同一会话内只改草稿深度**的对照

- kind: measured
- evidence: `[E]` 段的「投机效应」对：`m169-ident-08b-mtp` 的 `none` vs `draft-mtp:2` → 同一 91/164、差异 73；
  两臂分数 0.31707317…（52/164）与 0.29878048…（49/164），逐题记录在 `fixtures/ident_peritem.tsv`。
  这两臂各自都能跨会话逐字节复现（`none` 对应 `m125` n0、`draft-mtp2` 对应 `m125` n2，都是 164/164），
  所以「73 条不同」不是抖动，是这条路径的稳定行为。
- repro: `python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --check`（逐题通过率复原两臂分数）；
  `[E]` 段给出 91/164 的逐字节对。
- 限制：一个模型、一个深度（n=2）、一个 harness；方向（49 < 52）不能外推成「投机损伤质量」——
  同一 batch 的历史数据里方向随模型变（`quality-moves-items`）。

## wp3-draft-runtime-vram :: 草稿的运行期显存（与权重字节分开记）：0.8B 上 `none` 的 server 占 1126 MiB、`draft-mtp n=2` 占 1222 MiB（**+96 MiB**）；9B 上 5992 → 6368 MiB（**+376 MiB**）；ctx 都是 8192、KV 都是默认值

- kind: measured
- evidence: `.wrapup/mres/m169-vram-08b-mtp/ident_control.json`（1126/1222，整卡 4530/4626 MiB）与
  `.wrapup/mres/m169-vram-9b/ident_control.json`（5992/6368，整卡 10097/10472 MiB，起服前整卡 4099）；
  每臂 `n_slots=1`、`n_ctx_slot=8192`。
- repro: `[E]` 段的 `m169-vram-*` 行；`python3 -c "import json;print(json.load(open('.wrapup/mres/m169-vram-9b/ident_control.json'))['rows'])"`。
- 限制：这是**运行期**口径（多一个草稿上下文的 KV + compute buffer），与 `draft-memory-head-bytes` 的**权重**字节差
  是两个口径，不能相加成一个「草稿成本」。`server_mib` 取 `nvidia-smi --query-compute-apps` 的该进程占用，
  与整卡差（+96/+375）一致说明旁边没有新任务挤进来；但**同卡上还有别人的进程**（起服前整卡 3.2–4.1 GiB），
  所以绝对值只在本次会话的负载下成立。

## ident-arm-dir-collision :: 记录缺陷（已修）：同名臂共用一个 `codegen/<arm>` 目录时，`evalplus.codegen` 会「接续」上一次的产物——`m169` 的第二次 `none` 只花 0.09 分钟就给出 164/164 相同（假地板）；修法是同名臂目录加 `-r<k>` 后缀，重跑 `m170-ident-08b-floor`

- kind: measured
- evidence: `m169-ident-08b-mtp` 的 ledger 里两个 `none` 臂 `gpu_minutes` 分别是 3.8 与 0.09，产物 164/164 相同；
  `codegen/none/` 只有一个目录（两臂写同一处）。修后 `run_ident_control.py` 的 `dirname` 逻辑见 `seen[k]`。
- repro: `grep -n "dirname = k if" "docs/subprojects/a07-投机解码/run_ident_control.py"`；
  以及 `evidence/spec-runs.jsonl` 的 `m169-ident-08b-mtp` 三行。
- 限制：这条不改变结论，但它是两次踩坑：先是脚本的臂目录命名（同名臂共用一个目录），
  再是 `identity_report()` 里按**臂名**而不是**目录名**取产物（同一处错误的第二次）。两处都已修，
  `m170-ident-08b-floor` 用独立目录 `none` 与 `none-r2` 重跑，两臂 52/164 且逐字节 164/164 相同——
  修法已验证，且这一对现在由 `spec_evidence.py` 的 `byte_pairs()`（按目录名）给出。

## ident-inputs-in-exit2 :: `[E]` 的输入现在也在 exit 2 契约里：移走 `.wrapup/mres/m169-ident-08b-mtp` 后主命令退 **2**、点名 3 个缺输入，并把「地板对 3 / 期望 7」打出来；地板对数不等于 7 也算不可得

- kind: measured
- evidence: 移走该目录后主命令输出：`地板对: 3 对（期望 7）` + `UNMEASURED: 缺输入 3 项`
  （两个臂的 raw 与 `ident_control.json`），退出码 **2**（此前是 0 且只把计数印成 3）。
- repro: `mv .wrapup/mres/m169-ident-08b-mtp /tmp/x && python3 "docs/subprojects/a07-投机解码/spec_evidence.py"; echo $?`（期望 2），之后移回。
- 限制：期望值是写死的常量 `EXPECTED_FLOOR_PAIRS = 7`（4 个深度 0 会话的 C(4,2)=6，加同深度的
  `m125/n2` vs `m169/draft-mtp2`）。加臂就要同时改这个常量，否则会误报不可得——这是故意的，宁严不宽。

## vram-only-null-by-design :: `m169-vram-9b` 的两行 `humaneval: null` 是 `--vram-only` 的设计，不是加载失败：两臂都 `n_slots=1`、`n_ctx_slot=8192`，`gpu_minutes` 0.06/0.07 分钟就是「起服 + 读显存」的耗时（不跑 benchmark）

- kind: measured
- evidence: `.wrapup/mres/m169-vram-9b/ident_control.json` 的两行（`error: null`、`server_mib` 5992/6368）；
  `[E]` 段把 `n_slots`、`n_ctx_slot`、整卡与本进程占用一并打印。
- repro: `[E]` 段；或上面那条 `python3 -c` 命令。
- 限制：9B 的**分数**没有在这次跑里测（要 7.4 分钟/臂 × 2，本次只买显存），它的深度分数仍在
  `quality-moves-items`（`m128` 的四个深度）里，那不是 null 而是已测。

## 五、未测与不可得（不是 0）

## unmeasured-list :: 五类东西现有数据答不了：投机+采样无任何一格（全贪心）；`-np>1` 与投机并用未测；gsm8k/ifeval 无逐题样本；9B/35B 的 MTP 权重开销；各投机格的 tok/s 逐次值与同卡负载

- kind: measured
- evidence: 普查见 `[A]`/`[B]`/`[C]`/`[D]` 四段的空位；`server.log` 每个投机臂都是 `-np 1`；`lmeval_*.log` 无 `--log_samples`。
- repro: `[A]`–`[D]` 段并读；`ls .wrapup/mres/m128-spec-9b/`（无 `samples_*.jsonl`）。
- 限制：解除条件写在 `PLAN.md` 的「未解问题」一节；本条只把「没有」与「0」分开。
