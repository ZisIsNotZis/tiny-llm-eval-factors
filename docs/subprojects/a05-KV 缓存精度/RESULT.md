# a05 KV 缓存精度 — 结果

每条事实一行一个陈述；数字后面必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
判断类结论（analysis）与技术测量分开，analysis 不覆盖任何数字。
本文件所有数字由一条命令复算：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"`（12 条预期；`A05_SELFTEST=1` 时退出 1）。

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
- 读法：KV 精度在这条链路上**改变个别题**（最多 15/164），净值小且方向不单调；逐题配对表只报计数，不给 p 值（单次运行、无重复）。
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

### kv-short-wording :: `res9` 的原文措辞「短上下文无可测差异」撤回，保留方向

- 撤回的是**措辞**，不是方向：`res9` 写「f16 / q8_0 / q4_0 三种 KV 精度在短上下文（约 1–2k tokens）下分数无可测差异」，而 m130 的逐题配对显示 `f16→q4_0` 掉 15 涨 11、`f16→q8_0` 掉 7 涨 3——「无可测差异」与实测不合。
- 死因两条：(1) 原句的来源是 `.scratch/originals/L2-结果.md`，该原件已退役、不可复现；(2) 即便是同一条面板，逐题层面也不是「相同」，只是「净值小且双向」。
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

### kv-long-ctx-unmeasured :: 长上下文的 KV 效应未测（不是 0），代价与判据见 `PLAN.md::WP4`

- 未测的原因：上面 8 个不可分辨格是现有唯一的长 ctx KV 数据；要判定需要换测量方式（`llama-passkey` 一类有动态范围的指标，或连续 NLL），而不是再调一次 `-c`。
- 代价（按实测算，不拍脑袋）：`.wrapup/m30b.log` 里 480 条 >4000 token 的 `prompt eval time` 行，中位 23 800 tok/s、最小 20 795 tok/s（同模型同卡），所以 32k 提示的提示处理约 1.4 s/格；12 格含模型加载 ≤30 GPU 分钟。
- 状态：**未测**（`plan7` 的正文迁入本条；它的其余部分早已拆到 `a01` 的 12B MMLU 复测、`i02` 的显存阻塞登记、`a11` 的扩散解码）。
- 证据：`.wrapup/m30b.log`。
- 复现：`grep "prompt eval time" .wrapup/m30b.log | grep -o "([ 0-9.]* tokens per second)" | sort -t'(' -k2 -n | sed -n '1p;$p'`。

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
- 前置条件：让 `mpl_protocol_label` 的保留段加上 `fa=`（`make_report.py`，i02/meta 拥有）之后，这条裁决才该被重新审；届时 `ingest_m29` 的 model map 也要加 `q2`/`q3` 两个短名。
- 两条负控都已在库副本上实跑 PASS：`python3 checks/ingest_protocol_negative_control.py`（逐行尊重协议串、缺字段时明说默认值、重跑不翻倍）、`python3 checks/ingest_skip_negative_control.py`（未知名被明说且不入库、认得的名字全部入库）。所以「入库装置本身已经能按格区分」不是本裁决的理由——理由是**报告消费侧**还分不开。
- 状态：current。
- 证据：`.wrapup/m29_summary.jsonl`；`make_report.py::mpl_protocol_label`；`migrate_db.py::ingest_m29`。
- 复现：`python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"` 的 F 段（在 `.tmp/` 的库副本上跑 ingest + 报告行分组，打印 `入库前 3 → 入库后 4` 与新冲突条目，真库不动）。

## 分析

### kv-analysis :: 在 1k 上下文上 KV 量化是可换的，在长上下文上还答不了

- 短上下文：三个 KV 精度（f16 / q8_0 / q4_0）的**净值**差在 164 与 161 题的规模上都是个位数，方向不单调（`kv-short-panel`、`kv-short-m29`）；但逐题会翻动，最多 15/164。所以「为了省显存把 KV 降到 q8_0 或 q4_0」在 1k 上下文上不必担心分数方向；「同一份权重换 KV 会得到逐题不同的结果」这一点必须承认，跨配置比较单个题目的判定没有意义。
- 长上下文：现有唯一的长 ctx 数据被判不可分辨（`kv-ctx-padded-floor`），所以「KV 能不能省显存」这个问题在长上下文上仍未答；答它需要 `PLAN.md::WP4` 的有动态范围测量，预算 ≤30 GPU 分钟。
- 这条 analysis 不覆盖任何数字；数字都在上面的事实里。
