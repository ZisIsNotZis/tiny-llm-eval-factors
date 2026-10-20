# a05 KV 缓存精度 — 结果

每条事实一行一个陈述；数字后面必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
判断类结论（analysis）与技术测量分开，analysis 不覆盖任何数字。
本文件所有数字由一条命令复算：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"`（20 条预期，含长上下文那批的 H 段；**其中 H5 当前是红的**，因为阳性对照格还在等重跑；`A05_SELFTEST=1` 时退出 1；缺 `evidence/needle-retune/` 时退出 1）。

## 短上下文（约 1k tokens）

### kv-short-panel :: KV 精度会改变个别题的判定，但净值双向（m130 标准基准面板）

- 条件：Qwen3.5-2B UD-Q3_K_XL，`ctx 8192`，贪心，同一提示集与后处理；三个 KV 配置 `f16/f16`、`q8_0/q8_0`、`q4_0/q4_0`，每个配置单次运行。列口径：mmlu `--limit 8`/科目（n=456）、gsm8k 与 ifeval `--limit 50`、humaneval 全量 164。
- 逐格分数（`humaneval` 列是 **base** 判分，不是 HumanEval+ 的 plus）：

| KV (K/V) | mmlu | gsm8k | ifeval | humaneval (base) |
|---|---|---|---|---|
| f16/f16 | 0.6096 (278/456) | 0.60 (30/50) | 0.62 (31/50) | 0.5732 (94/164) |
| q8_0/q8_0 | 0.6075 (277/456) | 0.68 (34/50) | 0.64 (32/50) | 0.5488 (90/164) |
| q4_0/q4_0 | 0.6140 (280/456) | 0.60 (30/50) | 0.68 (34/50) | 0.5488 (90/164) |

- **HumanEval 逐题配对（164 题，两套判分各算一遍）**：base 上 `f16→q8_0` 掉 7 题、涨 3 题；`f16→q4_0` 掉 15 题、涨 11 题（净 −4）；`q8_0→q4_0` 掉 12 题、涨 12 题（净 0）。plus 上 `f16→q8_0` 掉 4 涨 4（净 0，两配置都是 86/164，但通过集不同）、`f16→q4_0` 掉 14 涨 11（净 −3）、`q8_0→q4_0` 掉 13 涨 10（净 −3）。
- 读法：KV 精度在这条链路上**改变个别题**（最多 26/164 = 丢 15 + 得 11，口径与 `kv-two-metrics` 一致：报丢/得之和，不是净差），净值小且方向不单调；逐题配对表只报计数，不给 p 值（单次运行、无重复）。
- 状态：current。
- 证据：`.wrapup/mres/m130-kv/variant_panel.json`；`.wrapup/mres/m130-kv/codegen/{f16_f16,q8_0_q8_0,q4_0_q4_0}/humaneval/m130-kv-*_openai_temp_0.0_eval_results.json`；库行 `source_file='mres/m130-kv/variant_panel.json'`、`protocol LIKE 'variant-kv-%'`。
- 复现：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 A 段（打印三行分数与六行 lose/gain）；库侧 `sqlite3 -readonly experiments.sqlite "SELECT protocol,cache_type_k,cache_type_v,bench_family,n_items,_score FROM experiments WHERE protocol LIKE 'variant-kv-%' ORDER BY 1,2"`。

### kv-short-m29 :: fa=on 下 V=q8_0 相对 V=f16 的差在 ±3/161 内且双向（m29 面板）

- 条件：`m29_summary.jsonl`，`mpl-raw-greedy-768;fa=…,kv=…`，n=161，两模型（q2=`Qwen3.5-2B-UD-Q2_K_XL.gguf`、q3=`Qwen3.5-2B-UD-Q3_K_XL.gguf`）× 两语言（cpp/py），每配置两行且两行逐格同值（24 行 / 12 配置）。
- V 从 f16 换到 q8_0（K 固定 q8_0、fa=on）：q2 cpp 18→18（+0）、q2 py 21→22（+1）、q3 cpp 42→39（−3）、q3 py 44→43（−1）。
- fa 从 on 换到 off（V 固定 f16）：q2 cpp 18→17（−1），其余三格相同（21→21、42→42、44→44）。
- 读法：与 `kv-short-panel` 同向——差小、双向、不给区间；这四格是 raw 协议，不能与 m130 的 chat 面板或 161 之外的格比较。
- 状态：current（**未入库**，裁决见 `kv-m29-ingest-decision`）。
- 证据：`.wrapup/m29_summary.jsonl`。
- 复现：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 B 段（打印 12 个配置的 pass/n/protocol 与四行 V 差）。

### kv-two-metrics :: 分数差与逐题翻转是两个口径，分数差完全看不见翻转（m130 与 m29 逐对对照）

条件：同一面板内、同一条协议串的其余部分、贪心、单次运行；m130 = Qwen3.5-2B Q3 / ctx 8192，m29 = raw 协议 / n=161。所有数字由 G 段一条命令打印。

**m130 HumanEval 164 题（逐题产物只有这一列有；base 与 plus 两套判分各算一遍）**

| 配置对 | 分数差 | 丢 | 得 | 翻转合计 | 通过集相同 |
|---|---|---|---|---|---|
| base f16 → q8_0 | −4（94→90） | 7 | 3 | 10 | 否 |
| base f16 → q4_0 | −4（94→90） | 15 | 11 | 26 | 否 |
| base **q8_0 → q4_0** | **0（90→90）** | **12** | **12** | **24** | **否** |
| plus f16 → q8_0 | 0（86→86） | 4 | 4 | 8 | 否 |
| plus f16 → q4_0 | −3（86→83） | 14 | 11 | 25 | 否 |
| plus q8_0 → q4_0 | −3（86→83） | 13 | 10 | 23 | 否 |

**m130 其余三列（lm-eval 未开 `--log_samples`，按 `i01::res26` 没有逐题产物，只能报分数差）**

| 列（n） | f16→q8_0 | f16→q4_0 | q8_0→q4_0 |
|---|---|---|---|
| mmlu（456） | −1（278→277） | +2（278→280） | +3（277→280） |
| gsm8k（50） | +4（30→34） | 0（30→30） | −4（34→30） |
| ifeval（50） | +1（31→32） | +3（31→34） | +2（32→34） |

**m29 全量 161 题（逐题产物齐全）**

| 格 | 配置对 | 分数差 | 丢 | 得 | 翻转合计 |
|---|---|---|---|---|---|
| q2 cpp | fa=on，V f16→q8_0 | 0（18→18） | 1 | 1 | 2 |
| q2 py | fa=on，V f16→q8_0 | +1（21→22） | 0 | 1 | 1 |
| q3 cpp | fa=on，V f16→q8_0 | −3（42→39） | 4 | 1 | 5 |
| q3 py | fa=on，V f16→q8_0 | −1（44→43） | 2 | 1 | 3 |
| q2 cpp | V=f16，fa on→off | −1（18→17） | 1 | 0 | 1 |
| q2 py | V=f16，fa on→off | 0（21→21） | 1 | 1 | 2 |
| q3 cpp | V=f16，fa on→off | 0（42→42） | 2 | 2 | 4 |
| q3 py | V=f16，fa on→off | 0（44→44） | 2 | 2 | 4 |

- **被旧结论判成「无差异」而实际在翻的格（分数差 0、逐题集合不同）共 6 对**：m130 base `q8_0→q4_0`（90→90，12 丢 12 得）、m130 plus `f16→q8_0`（86→86，4 丢 4 得）、m29 q2 cpp（V 变化，1/1）、m29 q2 py（fa 变化，1/1）、m29 q3 cpp（fa 变化，2/2）、m29 q3 py（fa 变化，2/2）。
- 分数差不能预报翻转：14 个有逐题产物的对里，翻转合计最大 26（该对分数差只有 −4），另有 24 翻 / 0 分、25 翻 / −3 分、8 翻 / 0 分；12/14 对同时有丢与得。
- 因此口径写死：**任何 KV 或 FA 的比较必须同时报「分数差」与「逐题丢/得」两栏**；只报分数差的格（m130 的 mmlu/gsm8k/ifeval）必须写明「无逐题产物，翻转未测」，不得据此说「无差异」。
- 状态：current。
- 证据：同 `kv-short-panel` 与 `kv-short-m29` 的逐题产物（`eval_results.json`、`m29-*_eval.json`）。
- 复现：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 G 段（24 行对照表 + 6 对零差翻转 + 三条预期）。

### kv-short-wording :: `res9` 的原文措辞「短上下文无可测差异」撤回，保留方向

- 撤回的是**措辞**，不是方向：`res9` 写「f16 / q8_0 / q4_0 三种 KV 精度在短上下文（约 1–2k tokens）下分数无可测差异」，而 m130 的逐题配对显示 `f16→q4_0` 掉 15 涨 11、`f16→q8_0` 掉 7 涨 3——「无可测差异」与实测不合。
- 死因三条：(1) 原句的来源是 `.scratch/originals/L2-结果.md`，该原件已退役、不可复现；(2) 它**只看了分数**，而同一次面板的逐题产物（`m130-kv/codegen/*/humaneval/*_eval_results.json`）从一开始就在盘上，显示逐题判定在翻（`kv-two-metrics`）；(3) 即便只看分数，「无差异」也不成立：q8_0→q4_0 是 90 vs 90 但 12 丢 12 得，gsm8k 上 q8_0 比 f16 高 4 题。
- 仍然成立的旧结论：**没有一致方向的退化**——q4_0 并不比 f16 单调更差（gsm8k 与 ifeval 上 q4_0 还高 4 与 3 题），所以「省 KV 显存不必担心质量」这一方向的判断保留，但必须按 `kv-short-panel` 的计数说话。
- 状态：current。
- 证据：`.scratch/originals/L2-结果.md` 的原句已不可读（目录退役），本条的替代证据是 `kv-short-panel`。
- 复现：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 A 段。

## 上下文长度

### kv-ctx-null-by-construction :: 旧的 m30 网格是构造性空结果（`-c` 在短提示上不改变任何一道题）

- 2026-10-03 的 m30 网格把 `-c` 设成 8192 / 24576 / 49152，但 MultiPL-E 的 cpp 提示只有 100–300 tokens。同一 KV 配置的三个 ctx 的 eval 文件**逐字节相同**：`f16/f16` 全部 `5fe87737d734`、`q8_0/f16` 全部 `c26f409dd90c`、`f16/q8_0` 全部 `a66bf25c66b6`、`q8_0/q8_0` 全部 `d0b6e76df9bd`（sha256 前 12 位）。
- 读法：这 12 个格只改了**分配的窗口**，输入没变，所以它是构造性空结果，不能当「长上下文无差异」的证据。
- 状态：current。这 12 个落盘文件不在库里（`m30_summary.jsonl` 在修正后的重跑里被重写），所以它们不是库内数据，只是本条的对照证据。
- 证据：`.wrapup/mres/m30-q3-ctx{8192,24576,49152}-kv*-cpp_eval.json`。
- 复现：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 C 段；或 `sha256sum .wrapup/mres/m30-q3-ctx{8192,24576,49152}-kvf16_f16-cpp_eval.json`。

### kv-ctx-padded-floor :: 加长到 16k/49k 的 m30 格测的是「续写填充段」伪像，不是长上下文能力（不可分辨）

- 修正后的 m30 把输入填到 `ctx−1024`（前缀来自其它 HumanEval 题与它们的标准解），60 题 cpp，单模型 Qwen3.5-2B UD-Q3_K_XL。逐格 pass：

| ctx（实测提示 token） | f16/f16 | q8_0/f16 | f16/q8_0 | q8_0/q8_0 |
|---|---|---|---|---|
| 2048（995.8） | 4/60 | 4/60 | 4/60 | 4/60 |
| 16384（15327.6） | 0/60 | 1/60 | 0/60 | 1/60 |
| 49152（48095.7） | 0/60 | 0/60 | 0/60 | 0/60 |

- **为什么这不是长上下文结论**：49k 的四个 KV 配置 eval 文件同哈希（`329ed886ce07`），即逐题状态完全一致，没有分辨力；16k 上只有 K 在起作用（`f16/f16` 与 `f16/q8_0` 同哈希 `f522df5f`，`q8_0/f16` 与 `q8_0/q8_0` 同哈希 `06e15ca6`）。成因可看完成物本身：16k 格 58/60、49k 格 56/60 个完成物以 `// canonical Python solution (reference):` 开头——模型在续写填充前缀，而不是回答末尾那道题。
- 因此 16k/49k 的 8 个格**判「不可分辨」**，只登记，不作长上下文结论，也不参与任何池化。
- 库内这 12 行的 `_score=0` 有 6 个（16k 的 `f16/f16`、`f16/q8_0` 与 49k 的全部四格），就是报告里那 8 个 0.0 格中的 6 个（`a12::8 个 0.0 格` 已把归属登记到本层）。
- 状态：current。
- 证据：`.wrapup/m30_summary.jsonl`、`.wrapup/mres/m30-ctx{2048,16384,49152}-kv*-cpp{.jsonl,_eval.json}`、`.wrapup/m30b.log`。
- 复现：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 D 段（逐格 pass、哈希分组、填充段开头计数）。

### kv-long-ctx-needle :: 32k 上下文上 KV q4_0 没有检索损失：0 丢 1 得（针检索，20 条/格）

条件：Qwen3.5-2B UD-Q3_K_XL，`-fa on`、`-np 1`、贪心、`n_predict 32`；prompt = `ctx − 1024` tokens 的英文散文填充段（`.wrapup/ppl_corpora/nl_english.txt`），一条 `KEY: <5 位数字>` 插在**深度 0.9**（贴着末尾指令），最后一行要求只输出该数字；每格 20 条，同一 (ctx) 的 20 条 prompt 跨 KV 配置**逐字节相同**（sha256 落在证据文件里）；判分 = 完成物里第一个 5 位数字等于针。深度是**分层**而不是混在一格里——第一次跑（`evidence/run-first-void.out`）把 0.1/0.5/0.9 三个深度混成一格，0.5 深度是「lost in the middle」地板（0–1/7），把整格压到 7/20 触发了旧门，那一轮按规则判**不可用**，只作为诊断保留。

| ctx（实测 prompt tokens） | f16/f16 | q4_0/q4_0 | 差值 | 配对丢/得 | 95% CI（Wilson，单格） |
|---|---|---|---|---|---|
| 8192（7169） | 17/20 = 0.85 | 13/20 = 0.65 | −4 | **4 丢 / 0 得** | f16 [0.64,0.95]，q4_0 [0.43,0.82] |
| 16384（15362） | 20/20 = 1.00 | 20/20 = 1.00 | 0 | 0 / 0（逐题完全相同） | 两侧都 [0.84,1.00]（天花板） |
| 32768（31746） | 14/20 = 0.70 | 15/20 = 0.75 | **+1** | **0 丢 / 1 得** | f16 [0.48,0.85]，q4_0 [0.53,0.89] |

- **阳性对照**：旧写法 `hit = (got == needle) and not absent` 是**自证**——`absent=True` 让对照恒为 0，实测的 0/20 只是 20 条回答都输出了占位符 `12345`，它证明不了打分器能看到失败。已删除该判据，改成：**保留针、去掉最后那行指令**，判定与处理组同一条码路（第一个 5 位数字 == 针即命中），所以这条对照**可以非 0**（模型若复述针就记命中）；对照的 `prompt_tokens` 也改成按实际 prompt 用 `/tokenize` 重算（旧值是从处理组复制的 7169）。
- **对照的重跑没跑成，本轮按 void 记**：`needle_grid.py --control-only` 两次排队（1200 s、480 s）都撞在 `a04` 的 `m164-a04-uni45`（`evalplus.codegen mbpp`）持有的 `/tmp/llama_gpu.lock` 上；证据目录里那份对照已改名为 `…-control-absent-VOID.json`，`summary.json` 的 `control` 块写明 `status=void-absent-veto` 与重跑命令。当前可执行的替代负控是 `kv_evidence.py` 的 **H4**：用四个纯函数例子证明打分器「能记命中、能记失败、无数字记失败、占位符 12345 记失败」；**H5 因此是红的**，这正是「对照还没修好」的机器可读状态。
- **动态范围门**：v1 = 8–19/20，首次 13 格（深度混合）跑出 7/20 判不可用；v2 = 地板一侧不变（<8/20 仍不可用）、天花板 20/20 记「单侧」。**v2 与结果同一次提交（`82ae026`），「先写后跑」这件事 git 证明不了**；不受它影响的是：f16 在 32768 上 14/20 同时落在 v1 的 8–19 与 v2 的 ≥8 里，两种门下都通过。
- **结论与方向**：32k 上 q4_0 与 f16 **本次设计未观察到差异**（14 vs 15，配对 0 丢 1 得）；唯一 ≥4 的差在最短的 8k 上（q4_0 4 丢 0 得），16k 两侧都顶到 20/20。可观测下限 **4/20**（n=20 时单侧 α=0.05 的首个分裂是 5/20，所以 4/20 只是「这个量级的差看得出来」，不是显著）；因此可以说「本次设计未观察到长上下文让 KV 量化更贵」，不能说「长上下文不会让 KV 更贵」。
- 限制：只有深度 0.9 这一层、每格 20 条单次运行、`q8_0` 没有重跑（第一次跑的四配置在三个 ctx 上逐格相同，见 `evidence/run-first-void.out`，但那一轮按规则判不可用）；16k 是天花板、只能测出退化。
- 状态：current。
- 证据：`evidence/needle-retune/a05-needle-d0.9-ctx{8192,16384,32768}-kv{f16_f16,q4_0_q4_0}.json`（每条的深度、针值、完成物、是否命中、prompt sha256）与 `evidence/needle-retune/summary.json`；第一次（不可用）的一轮在 `evidence/needle/`。
- 复现：`timeout 780 bash .wrapup/gpu_locked.sh python3 "docs/subprojects/a05-KV 缓存精度/analysis/needle_grid.py" --depths 0.9 --kvs f16:f16,q4_0:q4_0 --outdir "docs/subprojects/a05-KV 缓存精度/evidence/needle-retune"`；重算命中率、配对丢/得与对照（不需要 GPU）：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 H 段（读 `evidence/needle-retune/*.json`，缺文件即退出 1）。

### kv-long-ctx-unmeasured :: 长上下文的 KV 效应已由针检索覆盖到 32k（先前「未测」的状态撤销）

- 本条原为「未测」，现由 `kv-long-ctx-needle` 取代：32k 上 q4_0 与 f16 的检索命中不可分辨（14 vs 15，0 丢 1 得），可见性下限约 4/20。
- 仍未覆盖的部分（不是 0）：**40k 以上没测，理由是成本与时间**，不是模型窗口——GGUF 头 `qwen35.context_length = 262144`（`python3 -c` 读头可验），但 32k 一格已经要 ~64 s（20 条 × 31.7k tokens 提示处理），40k/64k 在 9% GPU 额度下性价比低，且该模型在 32k 上已降到 14/20，再加长只会更快落地板；中间深度（0.5）在该模型上是结构性地板，KV 在那一层测不出——模型行为（lost in the middle），不是 KV 结论；**K 与 V 分开量化未测**：可用的一轮只有 `f16/f16` 与 `q4_0/q4_0`（K、V 同时变），`q8_0/f16` 与 `f16/q8_0` 只在判不可用的第一轮里跑过，所以「长上下文里是 K 还是 V 在起作用」未测。
- 代价已实测：13 格（含 1 个阳性对照）wall 约 11 分钟，其中 32k 格 ~64 s、16k ~32 s、8k ~20 s（`evidence/run-retune.out` 的时间戳）；重跑 7 格约 4 分钟。
- 证据：`evidence/needle-retune/`、`evidence/run-first-void.out`、`evidence/run-retune.out`。
- 复现：见 `kv-long-ctx-needle` 的复现命令；未覆盖档的代价是一次 `--ctxs 8192,16384,32768,49152`（4 个 ctx × 2 KV × 20 条约 8 分钟）。

## 数据库与报告的状态

### kv-db-columns :: m30 的 `cache_type_k/v` 列是默认值，KV 真值只在协议串里

- `run_tag='m30-kv-ctx'` 的 12 行全部写 `cache_type_k='q8_0'`、`cache_type_v='q8_0'`，与行的真实设置（4 个配置）无关。成因：`migrate_db.ingest_m30 → _ingest_mpl_ctx` 只补 `ctx_size`，不解析协议串里的 `kv=`。
- 后果与现状：`mktables.axis_kv` 已经知道这件事（它的注释写明 "those cache_type_k/v columns are unusable for it"），从 `protocol` 里取 KV，所以报告 E 图不受影响；任何按 `cache_type_k/v` 分组的新查询都会把 4 个配置合并成 1 个。
- 状态：current（缺陷已登记；修法要改 `migrate_db.py` 的 m30 入口，不在本层当前工作包内）。
- 证据：`experiments.sqlite` 的 `m30-kv-ctx` 行；`migrate_db.py::_ingest_mpl_ctx`；`.wrapup/mktables.py::axis_kv`。
- 复现：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 E 段；或 `sqlite3 -readonly experiments.sqlite "SELECT DISTINCT cache_type_k,cache_type_v FROM experiments WHERE run_tag='m30-kv-ctx'"`。

### kv-m29-ingest-decision :: m29 不入库（裁决 + 理由 + 前置条件）

- 裁决：**不入库**。`migrate_db.ingest_m29` 保持现状（用默认 model map，因此每次全量 migrate 都会打印 `skipped_rows=24 reason=unknown_model names=q2,q3`），不改成认短名。
- 理由（在库副本上实测，不是读代码推断）：报告的行标签由 `make_report.mpl_protocol_label` 生成，它只保留 `ctx= / kv= / tmpl=` 三段、把 `fa=on` 丢掉。把 12 个格入进副本后，`raw·kv=q8_0/f16` 这一个行标签下面同时出现 fa=on 与 fa=off 两条协议串：**1 个格触发行键冲突提示**（q2 cpp 显示 18/161，另有 17/161），**另 3 个格因为分数相同而静默合并**（q2 py 21/21、q3 cpp 42/42、q3 py 44/44）。也就是说入库会让 `a12` 已经登记过的那类缺陷（同一行标签下有两条协议串、库内无法区分）在本轴上再长一遍，而且只报警 1/4。
- 前置条件（二者满足其一才该重审这条裁决）：
  1. **行标签容纳 fa 维度**：`make_report.mpl_protocol_label` 的保留段从 `ctx= / kv= / tmpl=` 加上 `fa=`（`make_report.py`，i02/meta 拥有）；届时 `ingest_m29` 的 model map 也要加 `q2`/`q3` 两个短名。
  2. **报告改按协议串分行**：MultiPL-E 表的行键从「模型 + 显示标签」换成「模型 + 完整协议串」，两条协议串各占一行、不再是同一行标签下的两个值。
- 两条前置条件都是**消费侧**的改动，不是入库侧的；在此之前 `ingest_m29` 保持现状（默认 model map、每次全量 migrate 明说 `skipped_rows=24 reason=unknown_model names=q2,q3`），m29 的数字只以 `kv-short-m29` 与 `kv-two-metrics` 的形式留在本文件里。
- 两条负控都已在库副本上实跑 PASS：`python3 checks/ingest_protocol_negative_control.py`（逐行尊重协议串、缺字段时明说默认值、重跑不翻倍）、`python3 checks/ingest_skip_negative_control.py`（未知名被明说且不入库、认得的名字全部入库）。所以「入库装置本身已经能按格区分」不是本裁决的理由——理由是**报告消费侧**还分不开。
- 状态：current。
- 证据：`.wrapup/m29_summary.jsonl`；`make_report.py::mpl_protocol_label`；`migrate_db.py::ingest_m29`。
- 复现：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 F 段（在 `.tmp/` 的库副本上跑 ingest + 报告行分组，打印 `入库前 3 → 入库后 4` 与新冲突条目，真库不动）。

## 分析

### kv-analysis :: 在 1k 上下文上 KV 量化是可换的，在长上下文上还答不了

- 短上下文：三个 KV 精度（f16 / q8_0 / q4_0）的**净值**差在 164 与 161 题的规模上都是个位数，方向不单调（`kv-short-panel`、`kv-short-m29`）；但逐题会翻动，最多 26/164（`kv-two-metrics`）。两个口径的差距是可量化的：6 对配置分数差为 0 而逐题集合不同（最强的一对是 90 vs 90、12 丢 12 得），翻转最大的一对是 26 翻 / −4 分。所以「为了省显存把 KV 降到 q8_0 或 q4_0」在 1k 上下文上不必担心分数方向；「同一份权重换 KV 会得到逐题不同的结果」这一点必须承认，跨配置比较单个题目的判定没有意义，报告也不能再写「测不出差别」。
- 长上下文：针检索（`kv-long-ctx-needle`）在 8k/16k/32k 上给出「本次设计未观察到 q4_0 与 f16 的差异」，可观测下限 4/20；8k 上反而有一处 −4（4 丢 0 得），与「越长越贵」的方向相反。所以现在能答的是有界的一档：≤32k、深度 0.9、20 条/格；40k 以上与 K/V 分开量化仍未测（`kv-long-ctx-unmeasured`）。
- 这条 analysis 不覆盖任何数字；数字都在上面的事实里。
