# a06 采样与解码参数 — 结果

本文件是本子项目结果层的唯一 home。每条事实写成一行结论 + `- evidence:` + `- repro:`；
数字的当前值只在这里，报告里的图与表由数据库重新生成，不引用本文件的数值。

数据源：`experiments.sqlite`（只读打开）；产物源：`.wrapup/mres/*/variant_panel.json`、`.wrapup/m27_summary.jsonl`、
`.wrapup/m31_summary.jsonl`、`.wrapup/mres/m{27,31}-*_eval.json`。

复算入口（首行打印被审 revision、脚本 sha256、命令与脏路径，所以捕获绑定到版本而不是绑定到说法）：

- 普查：`python3 "docs/subprojects/a06-采样与解码参数/sampling_census.py"`，退出 0 = 六段全部跑完；
  缺任一输入（库 / `m27_summary.jsonl` / `m31_summary.jsonl` / `variant_panel.json`）时打印 `UNMEASURED` 并退出 **2**。
- 已存捕获：`evidence/census-6fc5b0c.txt`（退出 0，267 行）与
  `evidence/census-negative-control-6fc5b0c.txt`（在空临时树里跑同一脚本，四个输入全缺 → 打印四条 `missing …` 并退出 2）。
  负控证明这条检查会失败，不是空转。
- 逐题判决：`python3 "docs/subprojects/a06-采样与解码参数/peritem_moves.py"`，退出 0 = 36 个 (档位 × 语言 × 设置) 对全部比完；
  缺任一 `_eval.json` 时打印 `UNMEASURED` 并退出 **2**。捕获 `evidence/peritem-2552615.txt`（退出 0）与
  `evidence/peritem-negative-control-2552615.txt`（空临时树 → 6 个产物全缺、退出 2）。

## 一、协议普查

## census-scope :: 库里 3319 行里有 1438 行带协议串（65 个不同的串），另外 1881 行的 `protocol` 与 `run_tag` 同时为 NULL；协议串按基准族与 `max_tokens` 切出来是 96 组，其中与解码有关的只有四类：`multipl-e-raw-greedy-768` 一族（180 格）、`multipl-e-raw-t0.3-768` / `t0.6-768`（各 6 格）、`mpl-raw-t0.3-768;topk-set=…`（30 格）、`variant-sampling-*`（20 格）。

- kind: measured
- evidence: 普查 `[B]` 段逐行打印 `bench_family / max_tokens / cells / models / NULL / protocol`，末行 `distinct protocol strings: 65; rows carrying one: 1438`。
- repro: `python3 "docs/subprojects/a06-采样与解码参数/sampling_census.py"` 的 `[B]` 段。

## census-identity-unreadable :: 490 行（占全库 14.8%）的 `temp`/`top_k` 落在本仓声明过的任何设置之外，这 490 行的 `source_file` 与 `run_tag` **全部**为 NULL，其中 `temp` 有 478 个不同取值、`top_k` 有 385 个、`presence_penalty` 有 477 个（最多重复 13 次）——这是合成填充，不是一个解码设置；按 `@absent` 这些行的采样设置记 UNKNOWN，不读它的列值。

- kind: measured
- evidence: 普查 `[A]` 段：`total rows 3319` / `rows with protocol AND run_tag NULL 1881` / `outside every declared setting 490 (14.8%)` / `of those, rows with no source_file 490` / `distinct temp values 478` / `distinct presence_penalty values 477 (max repeat 13)`。样例行 `DeepSeek-R1-0528-Qwen3-8B-UD-IQ3_XXS.gguf` 的 `_bench='dummybench'`、`temp='0.12345'`。
- repro: `sqlite3 experiments.sqlite "SELECT temp,top_p,top_k,min_p,presence_penalty,_bench,source_file FROM experiments WHERE temp NOT IN ('0.0','0.3','0.6','0.7','1.0') LIMIT 5"`。
- 限制：修这 490 行的列值是 i02 的库整洁范围，a06 不改库；本条只保证 a06 的每一个比较都不依赖这些行。

## fixed-protocol :: 固定协议是贪心解码，`temp=0`、`top_p=0.95`、`top_k=40`、`min_p=0.05`、代码格的 `max_tokens=768`；带 `-768` 协议串的 354 行里 `max_tokens` 与这个值不符的是 **0** 行，而不带 `-768` 的贪心协议串（`max_tokens` 256 / 512 / 1024 与 NULL）是**别的协议**（限速探针、BFCL、lm-eval 的 chat 列），不是反例。

- kind: measured
- evidence: 普查 `[C]` 段：`max_tokens=768 n=570 temp=0.0 top_k=40 top_p=0.95 min_p=0.05`；`declared fixed max_tokens = 768; rows carrying a '-768' protocol: 354; of them disagreeing with that column: 0`；以及 `greedy protocols that are NOT the -768 fixed protocol: max_tokens=None n=8, 256 n=51, 512 n=94, 768 n=294, 1024 n=9`。
- repro: 普查 `[C]` 段。
- 限制：`max_tokens` 是 `text`，逐行 `/` 与 `payload` 已对齐；`seed` 在多数历史格上是 NULL（i01 已登记「未记录输入差可致 ±16/161」），所以固定协议的复现性上限受这一列约束，不由本条解决。

## res-axis-available :: 解码轴真正被测量过的只有三处：`m131`（1 个模型 × 5 个采样设置 × 4 个标准基准列）、`m27`（Qwen3.5-2B 的 Q2/Q3/Q4 × temp 0 / 0.3 / 0.6，只有 Q2 有真正的 temp=0 锚点）、`m31`（同 3 档 × top_k 1/20/40/64/200，温度固定在 0.3）；其余每一条协议都是贪心，没有采样孪生格。

- kind: measured
- evidence: 普查 `[D]` 段按 `run_tag × protocol` 打印每组的 bench / 格数 / 模型数 / 语言 / temp / top_k / max_tokens / n_items 区间；`[E3]` 段打印 `families with a temp>0 twin: 1 ['Qwen3.5-2B']` 与 `greedy models with NO temp>0 twin: 47`（54 个贪心模型里）。
- repro: 普查 `[D]`、`[E3]` 段。

## 二、分数移动

## score-moves-m131 :: 同一模型（Qwen3.5-2B Q3）、同一 ctx=8192、同一批题，从贪心换到 temp>0 时四个标准列的移动是：MMLU **0/456**（五个设置全同 0.6075）、HumanEval **−10/164**（0.5732→0.5122，temp 0.3 与 0.7 相同）、GSM8K **+2/50**（0.60→0.64）与 **+1/50**（temp 0.7）、IFEval **+4/50**（0.62→0.70）与 **+2/50**（temp 0.7）。

- evidence: 普查 `[D]` 段 `m131-sampling` 的 20 行；`.wrapup/mres/m131-sampling/variant_panel.json` 的 `rows`（`mmlu 0.6074561403508771` 在 greedy / temp0.3 / temp0.7 / greedy-topk1 / greedy-topk200 五档逐字相同）。
- repro: `python3 -c "import json;p=json.load(open('.wrapup/mres/m131-sampling/variant_panel.json'));[print(k,{b:v.get(b) for b in ('mmlu','gsm8k','ifeval','humaneval')}) for k,v in p['rows'].items()]"`。
- 限制：`m131` 每个设置只有 **1 个模型、1 次运行**，所以这一条是「移动了多少」，不是「移动的分布」；`mmlu` 的 0/456 结构性成立（走对数似然、不采样），另外三列的移动要配 i01 的噪声地板读。

## topk-inert-at-temp0 :: 温度 0 时 `top_k` 是惰性的，两个独立测量都给出逐字相同的结果：`m131` 的 top_k 1 / 40 / 200 在四个基准列上全同（MMLU 0.6075、GSM8K 0.60、IFEval 0.62、HumanEval 0.5732）；MultiPL-E 上 `m31` 的 `top_k=1`（温度 0.3，但 top-1 截断即 argmax）与 `m27`/`m3` 的贪心格在 6 个 (模型, 语言) 上逐字相同（Q2 cpp 0.1118、Q2 py 0.1366、Q3 cpp 0.2422、Q3 py 0.2671、Q4 cpp 0.2298、Q4 py 0.2733）。

- kind: measured
- evidence: 普查 `[E2]` 段 7 个设置下 6 个 (模型, 语言) 的值；`m131` 的 `greedy-topk1`/`greedy-topk200` 两行与 `greedy` 逐字相同。
- repro: 普查 `[E2]` 段；或 `sqlite3 experiments.sqlite "SELECT model,language,ROUND(_score,4) FROM experiments WHERE run_tag IN ('m27-sampling','m31-topk','m3-quant-ladder') AND protocol LIKE '%greedy-768%' OR (run_tag='m31-topk' AND top_k='1')"`。
- 限制：这里的「温度 0」是 `temp` 列等于 0 或 `top_k=1` 的等价；`m31` 的 K=1 行名义温度是 0.3，所以「top_k=1 与贪心等价」本身是被这 6/6 次全等**证实**的结论，不是一个假设。

## topk-not-inert-at-temp0.3 :: 温度 0.3 时 `top_k` 不是惰性的，而且在**同一档内部**把分数移动了几道题：Qwen3.5-2B Q3 cpp 从 `top_k=1` 的 39/161 掉到 `top_k≥20` 的 28/161（**−11 道**），Q4 py 从 44/161 升到 51/161（**+7 道**），Q2 py 从 22/161 升到 26/161（**+4 道**），Q2 cpp 与 Q3 py 不动；`top_k` 20 / 40 / 64 / 200 四档在每个(模型, 语言)上逐字相同。

- kind: measured
- evidence: 普查 `[E1]`/`[E2]` 段；分母 161 由 `score × 161` 全为整数证明（0.1118→18.0、0.1366→22.0、0.1615→26.0、0.1739→28.0、0.2298→37.0、0.2422→39.0、0.2671→43.0、0.2733→44.0、0.3168→51.0）。
- repro: 普查 `[E2]` 段。
- 限制：`m27` 的 14 行与 `m31` 的 30 行 `n_items` 是 NULL，所以分母是从分值反推的，不是库里读的；反推的口径是「同一语言满格 161 题」（i02 已从产物回填其余格），若某格实际题数不是 161 则本题的题数换算全部失效——但 11 个分值全部落在 161 的整数格上，这个巧合的概率极低。

## 三、逐题判决移动（`m27` / `m31` 的 161 题产物）

## peritem-reshuffle :: 换协议在分数完全不动的时候也会重排逐题判决：36 个 (档位, 语言, 设置) 对里，Q2 cpp 的 6 个设置净移动全是 0 道题，但逐题 6 上 / 6 下、Jaccard 0.50；Q3 py 净 0 而 8 上 / 8 下、Jaccard 0.69；Q4 cpp 净 0 而 9 上 / 9 下、Jaccard 0.61；全部 36 对的 Jaccard 落在 0.40–0.69，所以「分数没变」不等于「判决没变」。

- kind: measured
- evidence: `evidence/peritem-2552615.txt` 的 36 行（`jacc` 列）；最小 0.40 出现在 Q3 cpp temp 0.6，最大 0.69 出现在 Q3 py 的 temp 0.3 与全部 `top_k` 设置。
- repro: `python3 "docs/subprojects/a06-采样与解码参数/peritem_moves.py"`。
- 限制：Jaccard 衡量 pass 集合的重合，不衡量「哪一道题」；同一格里 6 上 6 下可以互相抵消成净 0，所以它必须与 `net` 列一起读。

## peritem-net-hides-flips :: 净分数移动会系统性低估逐题不稳定，最极端的一格是 Qwen3.5-2B Q3 py 在 temp 0.6：净分只动 **+1 道题**（43→44），而逐题 **15 上 / 14 下**、Jaccard 0.50——29 道题换了判决，净移动只报 1。这与 i01 在 temp=0.3 五跑上测到的同一现象同构（净摆动 ≤6/164 而 8–15 上 / 6–12 下）。

- kind: measured
- evidence: `evidence/peritem-2552615.txt` 的 `q3 py temp 0.6` 行：`delta +1 up 15 down 14 net +1 jacc 0.50`。
- repro: 同上。
- 限制：i01 的地板是 EvalPlus 的 164 题格、本表是 MultiPL-E 的 161 题格，两个 harness 的逐题集合与判分器都不同，所以「本表的翻转数与 i01 的翻转数同量级」是指示性对比，**不是受控对比**；把它当受控对比会高估证据强度。

## peritem-separable :: 36 个协议对里只有 **13 个**的净移动超过 i01 的五跑地板（|net| > 6 道题）：Q3 cpp 的 temp 0.3（−11）、temp 0.6（−15）与 `top_k≥20`（−11），Q2 py 的 temp 0.6（−7），Q4 py 的 temp 0.3 / temp 0.6 / `top_k≥20`（各 +7）；其余 23 个的移动（0、+1、+4、−6）与重复噪声不可分。

- kind: measured
- evidence: `evidence/peritem-2552615.txt` 的 `separable` 列：13 行 `yes, |net|>floor`，23 行 `NO, |net|<=floor`。
- repro: 同上；判据写死在脚本的 `FLOOR_NET = 6`，锚点写在 `ANCHORS`（Q2 用真正的 temp=0 行 `m27-q2-t0.0`，Q3/Q4 用 `m31-*-tk1`）。
- 限制：这是单次运行对单次运行的比较，所以「超过地板」只说明移动大于重复噪声的观测上限，**不**说明它可重复；要可重复就得加重复。

## peritem-topk-inert-above-20 :: 温度 0.3 下 `top_k` 20 / 40 / 64 / 200 四个设置在每一个 (档位, 语言) 上给出逐题完全相同的结果（up / down / Jaccard 三列全等），所以 `m31` 名义上测了 5 档 `top_k`，实际只有 2 个不同的测量：`top_k=1` 与 `top_k≥20`。

- kind: measured
- evidence: `evidence/peritem-2552615.txt` 里 `top_k 20 / 40 / 64 / 200 @ temp 0.3` 四行在 6 个 (档位, 语言) 上三列逐字相同（例如 q3 cpp 四行都是 `up 4 down 15 jacc 0.56`）。
- repro: 同上；或 `sqlite3 experiments.sqlite "SELECT model,language,ROUND(_score,4) FROM experiments WHERE run_tag='m31-topk' AND top_k IN ('20','40','64','200') ORDER BY 1,2,3"`。
- 限制：这只证明在这三个模型、161 题、温度 0.3 下 `top_k≥20` 不动；不能推成「`top_k` 普遍惰性」——`top_k=1` 对 Q3 cpp 就移动了 11 道题。

## 四、次序存活

## level-order-py-stable :: 在 python 上，量化档的次序在 6 个已测解码设置下**全部存活**：Q2 < Q3 < Q4 在贪心、temp 0.3（top_k 20/40/64/200）与 temp 0.6 上都不变，C(6,2)=15 个设置对 × 3 个档对 = 45 个非平比较，**0 个反转**；但这个存活是**聚合分层面**的——同一批格里逐题集合只重合 0.41–0.69（见 `peritem-reshuffle`），所以「次序存活」不许读成「判决相同」。

- kind: measured
- evidence: `fixtures/rank_summary.tsv` 的 py 三行都是 `15 0 0 6 survives`；`fixtures/rank_ledger.tsv` 是整个 45 行的逐对账本。普查 `[E2]` 段是同一结论的早期、6 设置版本。
- repro: `python3 "docs/subprojects/a06-采样与解码参数/rank_survival.py" --check`（退出 0 = fixture 与库一致）。

## level-order-cpp-inverts :: 在 cpp 上，Q3 与 Q4 的次序**不存活**：贪心（`top_k=1`）下 Q3 39/161 > Q4 37/161，而 temp 0.3 的 `top_k≥20` 下变成 Q3 28/161 < Q4 37/161，temp 0.6 下也是 Q3 24/161 < Q4 31/161——同 45 个非平比较里 5 个反转，全部落在 Q3-vs-Q4 这一对上（15 个设置对里 10 个一致、5 个反转）；Q2 与 Q3、Q2 与 Q4 这两对在 cpp 上 30 个比较全部一致。

- kind: measured
- evidence: `fixtures/rank_summary.tsv` 的 cpp 行：`Q2>Q3` 与 `Q2>Q4` 都是 `15 0 0 6 survives`，`Q3>Q4` 是 `10 0 5 6 inverts`；逐对明细在 `fixtures/rank_ledger.tsv`（5 行 `discordant` 全部是 Q3>Q4）。普查 `[E2]` 段给出同一结论的早期版本 `cpp level-pair order: concordant=40 discordant=5 over 7 settings`，与逐档值（`('0.3','1') Q2=0.1118 Q3=0.2422 Q4=0.2298` 对 `('0.3','40') Q2=0.1118 Q3=0.1739 Q4=0.2298`）。
- repro: 普查 `[E2]` 段；逐对计数见下面这条命令：`python3 -c "import itertools,collections;s={'k1':(18,39,37),'k20':(18,28,37),'k40':(18,28,37),'k64':(18,28,37),'k200':(18,28,37),'t0.6':(18,24,31)};print(collections.Counter((p,('conc' if (s[a][i]-s[a][j])*(s[b][i]-s[b][j])>0 else 'disc')) for a,b in itertools.combinations(s,2) for (p,(i,j)) in zip(itertools.combinations(('Q2','Q3','Q4'),2),((0,1),(0,2),(1,2)))))"`。
- 限制：`m3` 的贪心锚点 `seed` 是 NULL，`m31` 的 `top_k=1` 行名义温度 0.3 但 top-1 截断等于 argmax 且与 `m3` 逐字相同，所以「贪心」这一侧有两个独立来源互证；「temp 0.6」这一侧只有一次运行，没有重复。−11 道题的净移动超过 i01 的 temp=0.3 五跑净分数摆动上限（6/164），所以它不是重复噪声；temp 0.6 的 −15 道题（Q3 cpp 39→24）同理超出，而 +1/−6/+7 这几档与 6/164 的地板同量级，只有拿到逐题产物才能定（见下一条与 `PLAN.md` 的 `WP2`）。

## size-order-unmeasured :: 规模次序是否在采样下存活，目前**不可判**：54 个有贪心格的模型里只有 1 个（Qwen3.5-2B 一族）有 temp>0 的孪生格，而它的三个档位是同一尺寸的量化档，不是三个尺寸；也就是说已测数据里没有一个「同族 ≥3 个尺寸 × ≥2 个解码设置」的格子组，这条 AC 需要新测量（`PLAN.md` 的 `WP4`，估 ≤40 GPU 分钟）。

- kind: measured
- evidence: 普查 `[E3]` 段：`greedy cells: 54 over 54 models` / `families with a temp>0 twin: 1 ['Qwen3.5-2B']` / `greedy models with NO temp>0 twin: 47`。
- repro: 普查 `[E3]` 段。

## rank-ledger :: 「排序是否存活」已经变成可重算的判据而不是散文：`rank_survival.py --check` 从库里重建 21 个格（3 档 × 2 语言 × [贪心, t0.3-k20/40/64/200, t0.6-k40]）与 90 个 (档对 × 设置对) 比较，再与三份入库 fixture 逐行比对；当前结论是 cpp 的 `Q3>Q4` 为 `inverts`（10 一致 / 5 反序），其余 5 个 (语言, 档对) 全部 `survives`（各 15 一致 / 0 反序）。别人不必重跑任何模型就能复核这两句。

- kind: measured
- evidence: `fixtures/rank_cells.tsv`（21 格）、`fixtures/rank_ledger.tsv`（90 行逐对账本）、`fixtures/rank_summary.tsv`（6 行判定）；捕获 `evidence/rank-954d2c8.txt` 含干净运行 exit 0、篡改一个分值后 exit 1、缺库 exit 2 三段。
- repro: `python3 "docs/subprojects/a06-采样与解码参数/rank_survival.py" --check`（0 = 一致，1 = fixture 与库漂移，2 = 看不到输入）。
- 限制：`rank_cells.tsv` 里的「哪个库行使代表哪一档哪一设置」是**设计声明**（`rank_survival.py` 的 `SELECTION` 表），不是测量；判据能证明「给定这个选择，结论是什么」，不能证明「这个选择是唯一合理的选择」。`t0.3-k1` 作为第二个贪心锚点被排除在账本外（否则贪心那一对比会被数两遍），但它的等价性由同一个脚本检查：`m31` 的 `top_k=1` 必须在 6 个 (档, 语言) 上与 `m3` 的贪心格逐字相同，不同就 exit 2。

## res-vram-and-props :: 厂商臂的显存与生效判据都已实测：Qwen3.5-2B `UD-Q4_K_XL`（1.340 GB 权重）在 `-c 8192 -np 1 -ngl 99` 下让 `memory.free` 从 23088 降到 21198 MiB，占用 1.89 GiB，且 server 自报 `n_slots = 1, n_ctx_slot = 8192`；同时 `/props` 显示这台 server 的**默认**生成参数是 `temperature=0.8, top_k=40, top_p=0.95, min_p=0.05, presence_penalty=0.0`——即固定协议的 `temp=0` 不是服务器的默认值，任何忘记传参的跑会得到 0.8，这个默认值本身就是一条现成的负控。

- kind: measured
- evidence: 探针日志 `/tmp/a06_vram_probe.log` 的 `load_model: initializing, n_slots = 1, n_ctx_slot = 8192`；`nvidia-smi --query-gpu=memory.free` 在起服前后分别是 23088 / 21198 MiB。
- repro: `bash .wrapup/gpu_locked.sh bash -c 'nvidia-smi --query-gpu=memory.free --format=csv,noheader; /home/z/.local/bin/llama-server -m /home/z/hf/models--unsloth--Qwen3.5-2B-GGUF/snapshots/f6d5376be1edb4d416d56da11e5397a961aca8ae/Qwen3.5-2B-UD-Q4_K_XL.gguf --port 8977 -c 8192 -np 1 -ngl 99 --jinja & sleep 20; nvidia-smi --query-gpu=memory.free --format=csv,noheader; curl -s http://127.0.0.1:8977/props | head -c 200; kill %1'`。
- 限制：这是**空载**占用（无 prompt cache、无 batch），满负荷时 prompt cache 每条约 39.4–39.8 MiB（`server.log` 的 `alloc` 行），所以门槛取 2× 实测值而不是 1×。

## vendor-ingest-gap :: i02 的 `vendor-recommended` 臂（`60446d5`）已经落 main，但**没有入库路径**：`migrate_db.py` 里没有任何 `vendor-recommended` 或 `vendor_recommended` 的字符串，所以那一臂的格只会停在 `.wrapup/mres/*/variant_panel.json`，不会进 `experiments` 表；而 `rank_survival.py` 只读库，因此 `WP3` 的最后一步（把 `vendor` 加进 `SELECTION` 并 `--check` 通过）在补上 ingest 之前无法完成。

- kind: measured
- evidence: `grep -c "vendor.recommended" migrate_db.py` → 0；`60446d5` 改了 `migrate_db.py`（6 行）但没有加 ingest 函数；那一臂的行只存在于面板产物。
- repro: `grep -n "vendor" migrate_db.py`（无输出）；`python3 "docs/subprojects/a06-采样与解码参数/rank_survival.py" --check`（当前仍退出 0，因为它还没引用那一臂——这不是通过，是尚未纳入）。
- 后果：`WP3` 的入库这一步归 `migrate_db.py` 的 owner（i02），a06 不改它。没有 ingest 时，`WP3` 的结论只能从产物 json 读，而「可重算判据」这一半就退化回散文——这正是 `rank-ledger` 要避免的。

## vendor-effect-control-open :: i02 的负控（`checks/vendor_arm_negative_control.py`）自己声明了「服务端是否真的按这五个量采样」那一步**未验证**，理由是「本机没有 gguf」；这个前提不成立：`/home/z/hf/models--unsloth--Qwen3.5-2B-GGUF/snapshots/f6d5376…/` 里有 `UD-Q2/Q3/Q4/Q5_K_XL` 四个 `.gguf`，而这一步只要 20 秒 GPU，做法写在 `res-effect-control`：固定 `seed=1234` 连发两次相同请求必须逐字相同，再把 `presence_penalty` 从 2.0 换成 0.0 必须不同。

- kind: measured
- evidence: 本文件 `res-effect-control` 的三次实测输出（greedy 两次同、vendor 两次同、改 presence_penalty 后变）就是那一步的现成读数；gguf 清单来自 `ls -lL /home/z/hf/models--unsloth--Qwen3.5-2B-GGUF/snapshots/*/*.gguf`。
- repro: `python3 "docs/subprojects/a06-采样与解码参数/rank_survival.py" --check` 与本文件 `res-vram-and-props` 的探针命令。
- 后果：那条「未验证」可以关掉，且**不能**用「temp>0 两次输出应不同」去关（固定 seed 下它会假红，见 `res-effect-control`）。

## vendor-param-effect :: 五个厂商采样量**在两条路线上都真的进了采样器**：R1 的服务端启动带 `--temp 1.0 --top-p 1.00 --top-k 20 --min-p 0.0 --presence-penalty 2.0`，`/props` 逐字回显这五个值且 `n_slots = 1`；同一台服务器上 `/completion` 与 `/v1/chat/completions` 两个端点各 2 个 prompt，`top_k=1` 与 `top_p=0.1` 都**逐字重现**贪心输出、`temperature 0` 与 `1.0` 不同、固定 seed 下两者各自可重复——32 项检查里 31 项 PASS，唯一 FAIL 是一处 8-token 清单题上的 `presence_penalty 0 vs 2.0`（同一题上 `5.0 vs 2.0` 为 PASS）。

- kind: measured
- evidence: 捕获 `evidence/vendor-param-effect-<rev>.txt`（含 `/props` 回显与 32 行检查）；`/props` 文件 `evidence/` 之外另有 `.wrapup/mres/m165-vendor/props/{q2,q3,q4,q3-code}.json` 四份。
- repro: `python3 "docs/subprojects/a06-采样与解码参数/vendor_param_effect_probe.py" --port 8141`，前置条件是服务器用那五个 flag 起好。
- 限制：`/props` 只证明**服务端默认值**被接受，不证明请求体没覆盖它；请求体层面由塌缩判据（`top_k=1`/`top_p=0.1` 重现贪心）证明，两者要一起读。也不证明参数被按**正确的量纲**应用（例如 penalty 的缩放），只证明它改变了采样结果且方向与预期一致。

## res-two-routes :: 厂商臂的参数只能分两条路线到达采样器，因为两个客户端里只有一个自由度：`mpl_run.py` 的 raw 请求体只有 `prompt/temperature/n_predict/stop`（`mpl_run.py:146-150`），`evalplus.codegen` 的 CLI 只有 `--temperature`，所以代码列上的 `top_p/top_k/min_p/presence_penalty` 必须**在起服时**传（`run_m31.sh:66-68` 就是这么跑 `top_k` 的：`-c 4096 --top-p 0.95 --top-k $TK --min-p 0.05 --seed 1234`）；而 lm-eval 那条走 `--gen_kwargs`，五个量能逐请求传。

- kind: measured
- evidence: `.wrapup/mpl_run.py` 的 146–150 行与 157–160 行的 payload 字面量；`.wrapup/run_m31.sh` 的 66–68 行；`.wrapup/variant_panel.py` 的 `--gen_kwargs f"{kstr},max_gen_toks=1024"`（kstr 由 `kws` 拼出，厂商臂的五个键都在 `kws` 里）。
- repro: `sed -n '140,170p' .wrapup/mpl_run.py`；`sed -n '60,70p' .wrapup/run_m31.sh`。
- 后果（直接改队列）：① 代码列的厂商档走 `m31` 模式（服务端参数 + `--seed 1234`），这一路线下 `/props` 会显示全部五个量，所以 `/props` **是**生效证明；
  ② lm-eval 路线的逐请求参数**不**会出现在 `/props`（它只反映服务端默认值，实测 `temperature=0.8`），所以那条路线不能拿 `/props` 当证明，只能靠 `--gen_kwargs` 的日志；
  ③ `variant_panel.py` 里 i02 加的 `CODEGEN_UNSUPPORTED = {"vendor-recommended"}` 挡的是**它自己**的 codegen 调用，不覆盖 `m31` 模式，所以在 R1 上 EvalPlus 那一格仍然可测（`--temperature 1.0` + 服务端默认的其余四个量）。
- 限制：`/props` 的这两种行为是一条**实测**结论的一部分（`res-vram-and-props` 里默认 `temperature=0.8`），但「逐请求参数不写进 `/props`」是从「`/props` 显示 0.8 而面板声明 0/0.3/0.7」推出的，没有单独读数；要坐实得在 lm-eval 路线跑一次并同时抓 `/props` 与 `--gen_kwargs` 日志。

## res-effect-control :: 「参数真的生效」必须用结构性判据，不能用「改一个参数看输出变不变」：结构性判据是 `top_k=1` 或 `top_p=0.1` 会把候选集塌成 argmax，所以它的输出必须**逐字等于** `temperature=0` 的输出——一个被忽略的参数做不出这件事；再配「固定 seed 重复全同」当阴性对照。单点 A/B 会两头骗人：它既可能**假红**（我最早那次 `presence_penalty 2.0→0.0` 变了，而 i02 同一个改动没变），也可能**假绿**（下面的探针里 `presence_penalty 0 vs 2.0` 在「Name three colours」这题上完全相同，因为 8 个 token 的清单没有可罚的重复）。

- kind: measured
- evidence: `vendor_param_effect_probe.py` 在 R1 的服务器上跑 4 个 prompt × 8 项检查 = 32 项，**31 项 PASS、1 项 FAIL**，唯一 FAIL 就是上面那处 `presence_penalty 0 vs 2.0`；同一 prompt 上 `presence_penalty 5.0 vs 2.0` 是 PASS，说明这个量确实活着。捕获 `evidence/vendor-param-effect-<rev>.txt`。
- repro: 起服时把五个量当服务端 flag 传好，然后 `python3 "docs/subprojects/a06-采样与解码参数/vendor_param_effect_probe.py" --port 8141`（退出 0 = 全过，1 = 有检查没过，2 = 服务器不可达或 `/props` 没回显这五个量）。
- 后果：① 「temp>0 所以两次输出应该不同」是错的形状（固定 seed 下 temp 1.0 两次也逐字相同）；② i02 观察到的「改 `presence_penalty`/`top_k` 输出没变」与「改 `presence_penalty` 输出变了」都不构成「参数被吞」的证据，它们是同一类单点巧合的两个方向；③ 判「生效」要么用塌缩判据，要么用 `/props`（服务端 flag 路线下它回显全部五个量）。

## vendor-arm-is-not-a-perturbation :: 厂商档不是「温和的采样变化」：Qwen3.5-2B `UD-Q2_K_XL` 的 MultiPL-E cpp 从贪心的 18/161（0.1118）掉到 **1/161（0.0062）**，逐题状态直方图是 `{'SyntaxError': 142, 'Exception': 18, 'OK': 1}`，也就是说 161 个补全里 142 个连语法都不对。同一模型在 temp 0.3/0.6 下的 cpp 分别是 18/161 与 18/161（`topk-not-inert-at-temp0.3`、`m27`），所以这个塌陷不是温度造成的，而只能来自 `top_p=1.0 / min_p=0.0 / presence_penalty=2.0` 这一组（尤其 `presence_penalty=2.0` 会惩罚重复的 token，而 C++ 补全大量复用标识符与标点）。

- kind: measured
- evidence: `.wrapup/mres/m165-vendor/mpl-q2-cpp-vendor_eval.json`（`n=161, pass=1`，details 的状态直方图如上）；三个样例补全里出现 `INF_T_DN_C`、`floor_truce_number`、`if(number > .9987654321)` 这类不存在的构造。
- repro: `python3 -c "import json,collections;d=json.load(open('.wrapup/mres/m165-vendor/mpl-q2-cpp-vendor_eval.json'));print(d['n'],d['pass'],dict(collections.Counter(x['status'] for x in d['details'])))"`。
- 后果（读这一臂前必须知道）：① 若 Q3/Q4 也掉到语法地板，则「厂商档下 Q3-vs-Q4 是否仍反序」**不可估**——地板上的格子之间的差别不是能力差别，这时正确的结论是「在该采样值下 cpp 阶梯不可分辨」，而不是「次序变了」或「次序保住了」；② 这条也解释了为什么不能把厂商档当成「另一个温度点」：它的效应量比温度轴大一个数量级（−17 道题 vs 温度轴的 0 到 −15）；③ 按 a12 的规则，`SyntaxError` 主导的格保留真分数，但必须写成「该采样设置下的 harness floor 或真实通过数」，不得与其它格同权地读成能力差异。

## 五、厂商推荐采样（`plan3`）

## res-vendor-value :: 厂商（unsloth）给 Qwen3.5-2B 的推荐采样参数拿到了：非思考文本任务是 `temperature=1.0, top_p=1.00, top_k=20, min_p=0.0, presence_penalty=2.0, repetition_penalty=1.0`；它落在本研究测过的每一个设置**之外**——温度只有 1.0 一档与已测的 0/0.3/0.6/0.7 都不同，`top_p` 1.00 对已钉住的 0.95，`min_p` 0.0 对 0.05，并且多一个已测协议里恒为 0 的 `presence_penalty=2.0`。

- kind: measured
- evidence: `evidence/vendor-card-excerpt-3b868dc.md`（模型卡原文摘录 + 抓取时间 + 64059 字节 + sha256 `d6507c92…`）；原件 URL `https://hf-mirror.com/unsloth/Qwen3.5-2B-GGUF/raw/main/README.md`。
- repro: `curl -sS -m 15 "https://hf-mirror.com/unsloth/Qwen3.5-2B-GGUF/raw/main/README.md" | grep -A 6 'We recommend using the following set'`。
- 限制：**二手证据**。`huggingface.co` 在本机只解析到 IPv6（`2a03:2880:f12c:183:face:b00c:0:25de`）而到达不了（`curl` 15 秒超时，exit 28），所以读的是公共镜像，没与正库逐字节比对；卡片正文是上传者原文，但镜像的时效性未验证。用途不受影响：本条只用它取参数值，不用它证明别的。
- 模型范围的限制：本条只针对 Qwen3.5-2B。其他模型的卡可能给不同的值；在把结论推到全库前，要么逐模型取卡，要么把结论写成「在 Qwen3.5-2B 上」。

## res-vendor-partial :: 「换成厂商推荐采样会不会颠覆量化结论」现在可以给一个有限答案：厂商值是温度 1.0，而温度那一轴在已测的 0.3 与 0.7 之间给出**同一个** HumanEval 分数（0.5122），所以如果 0.3–1.0 是一个平台，则厂商值的代码分也在 −10/164 附近，与量化档之间 11–15 道题的差距同量级，会让 cpp 上 Q3-vs-Q4 的反转得更不可依赖；但这只是**推断**：温度 1.0 本身**没测**，`top_p` 1.00 / `min_p` 0.0 / `presence_penalty` 2.0 三个维度本研究从未变过，它们同时变时行为未知。

- kind: measured
- evidence: 本节 `res-vendor-value`、`score-moves-m131`、`peritem-separable`；`m131` 的 `temp0.3` 与 `temp0.7` 两行 `humaneval` 逐字相同（0.5121951219512195）。
- repro: `python3 -c "import json;p=json.load(open('.wrapup/mres/m131-sampling/variant_panel.json'));print([(k,v['humaneval']) for k,v in p['rows'].items()])"`。
- 限制：这是一个从已测点外推的**推断**，不是厂商推荐臂的测量；它只说「若温度落在 0.3–1.0 这段且其余维度不变」，而厂商值恰好改了那三个其余维度。因此 `plan3` 保持 provisional，直到 `PLAN.md` 的 `WP3` 真跑一档。

## 六、限制

## limit-per-item :: 逐题判决只在 MultiPL-E 上有产物：`.wrapup/mres/m27-*_eval.json`、`m31-*_eval.json` 存在（可按题号比对），而标准列的 `m131` 只有聚合分（`.wrapup/mres/m131-sampling/codegen/*/humaneval/*_eval_results.json` 只存 `date/hash/eval`，`eval` 里是每题的解，不带每题通过与否；lm-eval 的 `results` 只有 `acc` 与 `stderr`），所以标准列的逐题判决移动在这个库上**不可从产物重算**，只能重跑。

- kind: measured
- evidence: `python3 -c "import json;print(list(json.load(open('.wrapup/mres/m131-sampling/codegen/greedy/humaneval/m131-sampling-greedy_openai_temp_0.0_eval_results.json')).keys()))"` → `['date','hash','eval']`；同目录 `*.jsonl` 每题只有 `task_id`/`solution`；`m131-sampling/sampling_greedy_mmlu_*.json` 的 `results` 每项只有 `{name,alias,sample_len,'acc,none','acc_stderr,none'}`。
- repro: 上面这条命令；`ls .wrapup/mres/m27-*_eval.json .wrapup/mres/m31-*_eval.json | wc -l`（44 个）。
- 后果：`WP2` 的逐题分析已在第三节做完（MultiPL-E 的 161 题，四个 `peritem-*` 事实）；标准列若要逐题，只能重跑（`WP3`/`WP4` 重跑时顺手拿逐题产物）。

## limit-n-items :: `m27` 的 14 行与 `m31` 的 30 行 `n_items` 是 NULL（全库 241 行 NULL 的一部分），所以本子项目的题数换算全部靠「同语言满格 161」这一口径反推，并且用「`score × 161` 全为整数」自证；这一条不进报告，报告仍按 i02 的回填口径印题数。

- kind: measured
- evidence: `sqlite3 experiments.sqlite "SELECT COUNT(*) FROM experiments WHERE n_items IS NULL AND run_tag IN ('m27-sampling','m31-topk')"` → 44；`[E1]` 段每行打印 `n_items=None`。
- repro: 上一条命令。

## res10 :: 采样/解码参数：温度从 0 升到 0.3/0.7 会压低代码通过率；温度 0 时 top_k 无影响；MMLU 对采样完全无反应（走对数似然）。

- author: measurement
- origin: .scratch/originals/L2-结果.md 采样/解码参数
- scope: general
- status: current
- kind: measured
- 迁移后的当前判定：三句都复现，但第二句要加限定。① 代码通过率被压低：HumanEval `m131` −10/164（0.5732→0.5122，temp 0.3 与 0.7 相同），MultiPL-E cpp 上 temp 0.6 把 Q3 从 39/161 压到 24/161（−15 道）；② 「温度 0 时 top_k 无影响」成立且是 6/6 与 12/12 个格逐字相同，但**温度 0.3 时 top_k 影响 11 道题**（见 `topk-not-inert-at-temp0.3`），所以这句必须读成「只在温度 0 时惰性」；③ MMLU 0/456 五档全同，成立。
- evidence: 本节 `score-moves-m131`、`topk-inert-at-temp0`、`topk-not-inert-at-temp0.3`、`level-order-cpp-inverts`、`peritem-separable`。
- 逐题层面的补充：「代码通过率被压低」这一句在逐题上比在分数上剧烈得多——Q3 cpp temp 0.6 是 21 上 / 6 下之后的净 −15，而 Q3 py temp 0.6 净 +1 却翻了 29 道题（`peritem-net-hides-flips`）。
- repro: 普查 `[D]`、`[E1]`、`[E2]` 段。

## 七、报告里 temp>0 的格该怎么读

## report-temp-cells :: `report.html` 第六节（采样 / 解码参数）里的 temp>0 格（`mpl-raw-t0.3-768`、`mpl-raw-t0.6-768`、`mpl-raw-t0.3-768;topk-set=…`、`variant-sampling-temp0.3/0.7-*`）不是固定协议分数的「更宽松版本」，也不能与贪心格同权读：它们是**不同的格**，逐题集合与贪心格不同：MultiPL-E 161 题上净差 11–15 道题、逐题翻转 15–21 道，Jaccard 0.40–0.56，而分数只差 0.04–0.09；所以正确的读法是「该格的协议就是它的身份，跨协议只读方向、不读差值的显著性」，并且方向在 python 上稳、在 cpp 上不稳——一个读者从第六节读到「温度压低代码分」是安全的，读到「Q3 比 Q4 好」是不安全的（贪心下 Q3>Q4，temp>0 下 Q3<Q4）；也不能把「两格分数相同」读成「两格测的是同一个东西」（Q3 py 净 0 而 8 上/8 下）。

- kind: measured
- evidence: `level-order-cpp-inverts`、`peritem-reshuffle`、`peritem-net-hides-flips`、`topk-not-inert-at-temp0.3`、`score-moves-m131`；报告第六节的标签碰撞（`m31` 的 `top_k` 格与 `m27` 的 `t0.3` 格挤成同一个 `raw·temp=0.3` 标签）已由 a12 登记给 i02，a06 只提供上面这三条的数值证据。
- repro: `python3 "docs/subprojects/a06-采样与解码参数/sampling_census.py"` 的 `[E1]`/`[E2]` 段。
- 限制：本节没有改报告，也没有改 `mktables.py`；第六节把 m31 与 m27 的格并成一行的问题属 i02。a06 的贡献是给出「并了之后读者会读错哪一个方向」的具体数（Q3-vs-Q4 在 cpp 上反转）。
