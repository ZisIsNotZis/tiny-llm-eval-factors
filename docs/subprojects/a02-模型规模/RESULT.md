# a02 模型规模 — 结果

每条事实一行一个陈述；数字后面必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
判断类结论（analysis）与技术测量分开，analysis 不覆盖任何数字。
本层只读 `experiments.sqlite`；所有命令都在仓库根执行。

### acceptance-entry-point :: 本层的唯一验收入口是一条命令 `python3 "docs/subprojects/a02-模型规模/analysis/run_all.py" --selftest`，它跑六个脚本的 79 条断言并附一次负控（篡改一条取数通道后检查必须失败）；`A02_HF_ROOT=/nonexistent` 模拟干净 clone（没有任何 GGUF）时同样全绿。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/run_all.py`
- evidence: 逐脚本断言数 fixture 漂移检查 1、provenance 37、ladder 15、regression 12、curves 10、moe_position 4，合计 79；负控输出 `expected failure was seen`。真值来自入库 fixture `analysis/fixtures/gguf_truth.json`，所以断言不依赖 `/home/z/hf`；GGUF 头解析带 (size, mtime) 缓存（`analysis/gguf_cache.json`），重复运行 3m52s → 0.08s。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/run_all.py" --selftest`（实跑输出：`6/6 checks green` + `[PASS] negative control`）
- repro: `A02_HF_ROOT=/nonexistent python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" --check`（实跑输出：`37 expected true, 0 false`）

## 本轴的 X 本身不是一条通道给的数

### size-not-one-thing :: 「模型规模」这一列（`experiments.__size`）由三条互不相同的通道给出，且其中一条把百万和十亿当成同一个单位：文件名 size token 直接取数（`-4B`→4.0）、同一 token 在 M 量级时不换算（`LFM2.5-230M`→230.0，实际 0.23B，差 1000 倍）、文件名没有 size token 时回退成 `2 × gguf 文件字节数`（量化后字节数是 `_file_size`）。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `exp.py::double_underscore_fields` 的解析规则 + `experiments.sqlite` 当前值
- evidence: 解析规则在 `exp.py:44`（`SIZE_RE = -E?([0-9.]+)[MB]\b`，不区分 M/B 单位）、`exp.py:62`（`size = float(...)`）、`exp.py:76-84`（`size < filesize` 时取 `filesize`；`size` 缺失时取 `filesize / 0.5`）。库内证据：`LFM2.5-230M-UD-Q4_K_XL.gguf` 的 `__size=230.0`、`functiongemma-*` 的 `__size=270.0`（两者都 >100，其余行都 <36）；`GLM-4.7-Flash` 的 8 个非 REAP 量化文件里有 8 个的 `__size/_file_size` 等于 2.0000（第 9 个 `UD-TQ1_0` 不在其中：它是 16.662，走的是另一条）。
- repro: `sqlite3 -header -column experiments.sqlite "SELECT model,__size,__activation_size,count(*) FROM experiments WHERE __size>100 GROUP BY 1,2,3"`（实跑输出：`LFM2.5-230M-UD-Q4_K_XL.gguf|230.0|230.0|53`、`functiongemma-270M-*|270.0|270.0|14`）
- repro: `sqlite3 -header -column experiments.sqlite "SELECT model,__size,_file_size,round(__size/_file_size,4) r FROM experiments WHERE __model='GLM-4.7' AND __size>17 GROUP BY model ORDER BY __size"`（实跑输出：`GLM-4.7-Flash-UD-IQ1_S`/`IQ1_M`/`IQ2_XXS`/`IQ2_M`/`Q2_K_XL`/`IQ3_XXS`/`Q3_K_XL` 七行的 `r` 全为 `2.0`）

### size-tracks-bits :: 对有上述「2 × 文件字节数」回退的那些行，规模列随量化位宽移动而与参数量无关：`GLM-4.7-Flash` 的 8 个非 REAP 量化文件是同一个模型的同一份 29.94B 权重，参数量按构造是常数，却在 `__size` 上跨 18.50–27.56，即「规模」在那里就是「比特数」。

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.size-not-one-thing
- origin: `experiments.sqlite` 中 `__model='GLM-4.7'` 且文件名不含 A token 的行
- evidence: 同一目录下 `GLM-4.7-Flash-REAP-23B-A3B-*` 走 size token 通道得到恒定的 23.0（`__quant_ratio` 随档位变 0.313–0.619），而 `GLM-4.7-Flash-UD-*` 走回退通道得到 18.495967936→27.564008128（`__quant_ratio` 恒为 0.5，因为分子分母都随字节数走）。差别就来自文件名里有没有 size token。
- repro: `sqlite3 -header -column experiments.sqlite "SELECT model,__size,_file_size,__quant,__quant_ratio FROM experiments WHERE __model='GLM-4.7' AND __size>17 GROUP BY model ORDER BY __size"`（实跑输出：REAP 行 `__size=23.0` 且 `__quant_ratio` 逐档不同；非 REAP 行 `__quant_ratio=0.5` 且 `__size` 逐档不同）

### active-param-is-a-filename-label :: 「激活参数量」（`__activation_size`）不是测量，是文件名里的 `-A<n>B` 标签：有该 token 就填它，没有就令激活 = 总参（`exp.py:64,87-90`），所以同一个 MoE 家族里文件名带 A token 的被记为 MoE、不带的被记为稠密。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `exp.py::double_underscore_fields` 的 `ACTIVATION_RE` 规则 + 库内对照
- evidence: `exp.py:45` `ACTIVATION_RE = -A([0-9.]+)[MB]\b`；`exp.py:87-90` `activation_size = activation if activation > 0 else size`。库内：`GLM-4.7-Flash-REAP-23B-A3B-UD-Q4_K_XL.gguf` → 23.0/3.0；`GLM-4.7-Flash-UD-Q4_K_XL.gguf` → 27.56/27.56（同一 GLM-4.7-Flash 权重谱系，激活/总参被写成 1.0）。所以「总参与激活参是否可分」在本库里不能只靠这两列回答，必须先判每行的标签来源（`WP2`）。
- repro: `sqlite3 -header -column experiments.sqlite "SELECT model,__size,__activation_size,count(*) FROM experiments WHERE __activation_size<__size GROUP BY 1,2,3 ORDER BY 2"`（实跑输出：只有 LFM2.5-8B-A1B 系、GLM-4.7-Flash-REAP-23B-A3B 系、gemma-4-26B-A4B 系、NVIDIA-Nemotron-3-30B-A3B 系、Qwen3.6-35B-A3B 系五族出现 `__activation_size<__size`）

### size-channel-inventory :: 把库的 3233 行全部按取数通道归位后，只有 659 行（20%）的「规模」与 GGUF 张量求和的真参数量相差 10% 以内，1061 行根本没有规模（`__size IS NULL`），其余 1513 行分属四条与参数量无关的通道（文件名标签低于张量总数 58、等于文件字节数 190、等于两倍文件字节数 86、至少大 8 倍 67），另有 1112 行因模型文件不在盘上且无 bpw_map 条目而不可判。

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.size-not-one-thing
- origin: `analysis/size_provenance.py`（读 `experiments.sqlite` 的 304 个 `(model, __size, _file_size)` 组 + `/home/z/hf/` 的 GGUF 头）
- evidence: 通道与行数 `size-null` 1061 / `undecidable` 1112 / `token-rounded` 659 / `clamped-to-file-bytes` 190 / `two-times-file-bytes` 86 / `size-too-large-for-file` 67 / `label-below-total` 58，合计 3233，`other` 为 0（真参数量已知却解释不通的行一条也没有）。真参数量来源：169 个 `(model, size)` 组 / 76 个模型文件 / 1970 行由 GGUF 张量元素求和测得（`truth_source=gguf-tensors` 或 `fixture`，两者同源），无一组来自猜测。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" | head -12`（实跑输出：上表七行通道计数）
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" --check`（实跑输出：`32 expected true, 0 false`，退出 0）

### size-null-on-protocol-rows :: 缺规模的 1061 行全部是带 `protocol` 标签的行，但反过来不成立：带协议的行共 1352 行，其中 291 行有规模（`multipl-e-raw-greedy-768` 178、bfcl 系 94、`evalplus-0.3.1-openai-chat` 19）；lm-eval 系协议 563 行则是 563/563 全缺。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `experiments.sqlite` 按 protocol 分组统计 `__size`
- evidence: `protocol IS NOT NULL AND protocol<>''` 1352 行，其中 `__size IS NOT NULL` 291 行、`NULL` 1061 行；1061 个空值全部落在带协议的行上（历史行 1881 个没有一条为空）。按前缀算 `protocol LIKE 'lmeval%'` 是 479 行、全为空；把以 `-lmeval` 结尾的变体协议（`variant-*-lmeval`、`spec-mtp-*-lmeval` 等）一并算上则是 `%lmeval%` 563 行，也全为空——两个数都对，差别只在口径，报告里用前缀那个 479 是同一事实的窄口径；`evalplus%` 313 行里 294 行为空、19 行有值；`bfcl%` 123 行里 29 行为空；`multipl-e%` 194 行里 16 行为空。`_file_size` 一列 3233 行全部非空，所以这不是缺文件元数据，是插入时没算 `__size`。
- repro: `sqlite3 -header -column experiments.sqlite "SELECT count(*) n, sum(__size IS NOT NULL) with_size FROM experiments WHERE protocol IS NOT NULL AND protocol<>''"`（实跑输出：`1352|291`）
- repro: `sqlite3 -header -column experiments.sqlite "SELECT sum(protocol LIKE '%lmeval%') n, sum(protocol LIKE '%lmeval%' AND __size IS NULL) nulls, sum(protocol LIKE 'multipl-e%' AND __size IS NOT NULL) mpl_with, sum(protocol LIKE 'bfcl%' AND __size IS NOT NULL) bfcl_with, sum(protocol LIKE 'evalplus%' AND __size IS NOT NULL) ep_with FROM experiments"`（实跑输出：`563|563|178|94|19`）
- repro: `sqlite3 -header -column experiments.sqlite "SELECT count(*) null_rows, sum(protocol IS NOT NULL AND protocol<>'') null_with_protocol FROM experiments WHERE __size IS NULL"`（实跑输出：`1061|1061`）

### gguf-truth-coverage :: 真参数量覆盖 169 个 `(model, size)` 组 / **76 个不同的模型文件**（库里的 211 个模型文件中只有这 76 个的 GGUF 在盘上）/ 1970 行；另 135 个组（1263 行）的模型文件已从 `/home/z/hf` 消失且不在 `bpw_map` 里，只能记未测。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/size_provenance.json` 的 `missing` / `truth_source` 字段 + `analysis/fixtures/gguf_truth.json`
- evidence: `/home/z/hf` 只剩 134 个 `.gguf` 直链；`deepseek-r1-0528-qwen3-8b`、`dolphin3.0`、`glm-4.7-flash-reap-23b-a3b`、`north-mini-code-1.0`、`qwen3.6-27b` 等族全部落在这一档。76 个文件之所以覆盖 169 个组，是因为同一个模型文件在库里按 `(model, __size, _file_size)` 出现多个组。真值已做成入库 fixture，所以干净 clone 里这条检查不依赖 `/home/z/hf`（见 `fixture-gguf-truth`）。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));g=[r for r in d['rows'] if r['truth_source']];print(len(g), len({r['model'] for r in g}), sum(r['rows'] for r in g))"`（实跑输出：`169 76 1970`）
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));print(len(d['missing']), sum(m['rows'] for m in d['missing']))"`（实跑输出：`135 1263`）

### fixture-gguf-truth :: 实测参数量与逐类比特已做成入库 fixture `analysis/fixtures/gguf_truth.json`（76 个模型文件，含总/专家池/共享参数量、激活参数量、专家数与激活专家数、每文件字节数、按 ggml 类型折算的逐类比特），`build_fixtures.py --check` 负责与现场 GGUF 比对漂移。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/build_fixtures.py` 的 `read_gguf()`（张量形状 + 类型表）与 `--check`
- evidence: 76 条记录，未知 ggml 类型 0；类型表的自检是「按类型折算的张量字节数」对「文件真实大小」，`bpw_tensors` 与 `bpw_file` 的差中位 0.29%、最大 2.95%（差即元数据与对齐开销）。新增的 `Q1_0`(41)=128/18 与 `Q2_0`(42)=64/18 两块大小不是查表得来，而是由「文件字节 ÷ 元素数」反解并用同一条自检验过。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/build_fixtures.py" --check`（实跑输出：`76 个现场 GGUF 在场，0 处与 fixture 不符`）
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json'))['models'];print(len(d), sum(1 for r in d.values() if r['unknown_ggml_types']))"`（实跑输出：`76 0`）

### label-honest-families :: 文件名标签在三个家族里就是参数量（误差 ≤10%）：Qwen3.5 的 0.8/2/4/9 实测 0.752/1.882/4.206/8.954，Ternary-Bonsai 的 1.7/4/8 实测 1.72/4.02/8.19，gemma-4-12B 的 12 实测 11.907。

- author: measurement
- scope: specific
- status: current
- kind: measured
- from: result.size-channel-inventory
- origin: GGUF 张量求和 vs 文件名标签（`size_provenance.json` 的 `token-rounded` 通道）
- evidence: 三族共 76 个组的标签都落在真参数量的 ±10% 内，且同一模型的不同量化档给出**同一个**标签（Qwen3.5-2B 的 Q2/Q3/Q4/IQ2/IQ3 全部 `__size=2.0`、真参 1.882），所以在这三族里「同族内按标签比大小」是可用的。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));[print(r['model'],r['db_size'],round(r['truth_params'],3)) for r in d['rows'] if r['channel']=='token-rounded' and r['model'].startswith(('Qwen3.5','Ternary-Bonsai'))]"`

### label-dishonest-cases :: 三个家族的标签不是参数量：gemma-4 的 `E2B`/`E4B` 是厂商的「有效参数量」（张量总和 4.65B / 7.52B），`LFM2.5-230M` 被写成 230（单位错，隐含比特数 8×0.15÷230≈0.005，物理上不可能），`GLM-4.7-Flash` 的 8 个非 REAP 量化文件是同一份 29.94B 权重，却给出 18.50–27.56 这 8 个不同的「规模」。

- author: measurement
- scope: specific
- status: current
- kind: measured
- from: result.size-channel-inventory
- origin: `size_provenance.json` 的 `label-below-total` / `size-too-large-for-file` / `two-times-file-bytes` 三条通道
- evidence: gemma-4-E2B-it-UD-Q4_K_XL 真参 4.6475B 而 `__size=3.1845`（恰好等于该文件字节数）；E2B 的八个量化档在 `__size` 上是 2.186/2.291/2.373/2.404/2.620/2.924/3.184/4.294，同一个模型八个「规模」；E4B 真参 7.5181B 而标签 4；`LFM2.5-230M-UD-Q4_K_XL` 的 `_file_size` 使 `8×字节÷230` 远小于 1；GLM-4.7-Flash 的 8 个非 REAP 文件里，`__size/_file_size` 等于 2.0 的有 8 个（`UD-TQ1_0` 的 16.662 走的是 token 通道）。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));[print(r['model'],r['db_size'],r['truth_params'] and round(r['truth_params'],4),r['channel']) for r in d['rows'] if r['channel'] in ('label-below-total','size-too-large-for-file')]"`

### moe-active-params-measured :: MoE 的激活参数量现在有实测值（专家池张量按 `expert_used/expert_count` 折算）：GLM-4.7-Flash 29.94B/3.90B（4/64 专家）、LFM2.5-8B-A1B 8.47B/1.69B（4/32）、Qwen3.6-35B-A3B 35.51B/3.52B（8/256）、gemma-4-26B-A4B 25.23B/3.82B（8/128）；而库里对应的标签是 8/1、35/3、26/4，GLM-4.7-Flash 更是被记成 27.56/27.56（稠密）。

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.active-param-is-a-filename-label
- origin: 40 个 MoE 模型组的 GGUF 头（`expert_count` / `expert_used_count` + 张量名里 `_exps` 与 `_shexp` 的区分）
- evidence: `LFM2.5-8B-A1B` 记作 A1B，实测激活 1.69B（差 69%）；`GLM-4.7-Flash-REAP-23B-A3B` 记作 23/3，其非 REAP 同族文件实测 29.94/3.90 却被记成 27.56/27.56。所以 `plan5` 不能拿库里的 `__activation_size` 当激活轴，必须用实测列。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));[print(r['model'],round(r['gguf']['n_params']/1e9,2),round(r['gguf']['active_params']/1e9,2),str(r['gguf']['expert_used'])+'/'+str(r['gguf']['expert_count']),r['db_size'],r['db_active']) for r in d['rows'] if r['gguf_says_moe'] and r['gguf']]" | sort -u`

### size-axis-verdict :: 三个候选 X 的可用性逐族判定：实测参数量（GGUF）在 gemma-4、Qwen3.5、Ternary-Bonsai、GLM-4.7-Flash、LFM2.5 上都能当族内单调量用；文件名标签只在 Qwen3.5、Ternary-Bonsai、LFM2.5 等标签诚实的族里可用，在 gemma-4（8 个文件的标签不是参数量）、GLM-4.7-Flash（8 个全是 2×字节数）、granite-4.1、MiniCPM5 上不可用；`experiments.__size` 在报告用的面板里一行都没有值，不能当分析用的 X。

- author: agent
- scope: general
- status: current
- kind: analysis
- from: result.size-channel-inventory, result.label-honest-families, result.label-dishonest-cases, result.size-null-on-protocol-rows
- origin: `analysis/size_ladder.py`（对 `size_provenance.json` 逐族折叠 + 报告 §2 那一列 `_bench=humaneval` / `evalplus-0.3.1-openai-chat-greedy-base` 的 n=164 逐格）
- evidence: `size_ladder.json` 的逐族 `x_truth` / `x_label` / `x_db_size`：Qwen3.5 = yes/yes/yes（20/24 文件有实测值，标签 20 个全对，`__size` 覆盖率 49%）、Ternary-Bonsai = yes/yes/yes（4/4、3/3 对、7%）、gemma-4 = yes/**no**/no（11/27 有实测值，5 个标签对、8 个标签不是参数量）、GLM-4.7-Flash = yes/**no**/no（3/8 有实测值，8 个文件全是 2×字节数）、granite-4.1 与 MiniCPM5 的标签也全是 `label-below-total`。§2 面板（evalplus base，n=164）里 `__size` 非空的行数为 0。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_ladder.py" | head -16`（实跑输出：上表 15 行按族计数）
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_ladder.py" --check`（实跑输出：`15 expected true, 0 false`，退出 0）
- 结论的边界：本条判的是「族内能否比大小」，不是「跨族可比」——不同族的 tokenizer、训练数据与评测协议都不同，跨族只有 `plan5` 那种多变量设计才能谈。

### gemma4-q2kxl-inversion :: gemma-4 的 Q2_K_XL 档里 12B 比 4B 低 20.1 个百分点（54.3% [46.6, 61.7] vs 74.4% [67.2, 80.5]，n=164，区间不重叠），而同一个 12B 在 Q3_K_XL 档是 93.9% —— 这个反例是配方格的损伤，不是规模效应，报告 §2 把它叙述成「13B 附近的回折」是没有依据的。

- author: measurement
- scope: specific
- status: current
- kind: measured
- from: result.size-axis-verdict
- origin: `size_ladder.py` 的 `gemma-4` → `detail.Q2_K_XL`（Wilson 区间，`n_items=164`）
- evidence: Q2_K_XL 档按实测参数量排序的四格：4.647B→53.0%、7.518B→74.4%、11.907B→54.3%、25.233B→95.7%；Q3_K_XL 档同一 12B 是 93.9%。同一模型两档相差 39.6 pp，远超二项噪声（n=164 时 1.96σ≈7.3 pp），所以「12B 在 Q2_K_XL 上的位置」不能读成规模效应。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_ladder.json'));print(json.dumps(d['gemma-4']['detail']['Q2_K_XL'],ensure_ascii=False,indent=1))"`

### size-curve-shape :: 「越大越高」在 Qwen3.5 的 Q3_K_XL 档成立且增量递减（0.752→23.8%、1.882→57.3%、4.206→81.7%、8.954→82.3%，即 +33.5 / +24.4 / +0.6 pp），但在 Q2_K_XL 档不成立（9.1% → 25.6% → 72.0% → 79.9%，最大的一步是 1.882→4.206 的 +46.4 pp）；Ternary-Bonsai 的 4.022→8.189 是 −3.0 pp 且区间重叠（76.4–87.9 vs 73.1–85.3），判「测不出」。

- author: measurement
- scope: specific
- status: current
- kind: measured
- from: result.size-axis-verdict
- origin: `size_ladder.py` 的 `detail` 字段（Qwen3.5 / Ternary-Bonsai 两族）
- evidence: 六条同配方曲线里 5 条在实测参数量下单调，唯一的两处反向是 Ternary-Bonsai 的 −3.0 pp（区间重叠，属噪声）与 gemma-4 Q2_K_XL 的 −20.1 pp（`gemma4-q2kxl-inversion`）。所以「小模型之间差距更大」这句话在 Q3_K_XL 档成立、在 Q2_K_XL 档不成立，不能作为通例。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_ladder.json'));[print(lin,rec,v['rungs'],v['inversions']) for lin in ('Qwen3.5','Ternary-Bonsai') for rec,v in d[lin]['detail'].items()]"`

### report-size-claims-audit :: 报告里拿规模当 X 的说法共六处，逐条判：§2 的 X 定义「模型参数量（单位 B）」不成立（标签是有效参数量/字节数/单位错的混合）；「同一配方下参数量越大分数越高」在 Q3_K_XL 等档成立、在 gemma-4 Q2_K_XL 被 20.1pp 的反例推翻；「小模型之间差距更大」只在 Q3_K_XL 档成立、在 Q2_K_XL 档最大的一步反而是 1.882→4.206；「gemma-4 在 13B 附近回折」不成立，那是 Q2_K_XL 那一格的损伤；「剩下同家族同方案同协议的单调趋势是真实的规模效应」需要先换数源才成立（标签通道不诚实的族里它是比特效应）；「规模影响低比特表现」属 an3，WP4 未做，记未测。

- author: agent
- scope: specific
- status: current
- kind: analysis
- from: result.size-axis-verdict, result.gemma4-q2kxl-inversion, result.size-curve-shape, result.label-dishonest-cases
- origin: `report.html` 全文按「参数量 / 规模」正则扫描（`make_report.py:1674-1675` 是 §2 两句的来源）
- evidence: 逐条判定与它依赖的本层事实：X 定义→`label-dishonest-cases`（不可用，需换数源）；「越大越高」→`size-curve-shape`（有条件）；「小模型差距更大」→`size-curve-shape`（只在 Q3_K_XL 成立）；「13B 回折」→`gemma4-q2kxl-inversion`（撤回）；「真实的规模效应」→`size-axis-verdict`（换数源后才成立）；「低比特触底」→ 未测（`WP4`）。
- repro: `python3 -c "import re;h=open('report.html',encoding='utf-8').read();t=re.sub(r'<[^>]+>',' ',h);[print(m.group(0).strip()[:150]) for m in re.finditer(r'[^。\n]{0,60}(参数量|规模)[^。\n]{0,100}。',t)]" | sort -u`
- 给 i02 的建议文本（不由本层改 `make_report.py`）：「X = 实测参数量（GGUF 张量求和）」；把 E2B/E4B 两档的行从 §2 面板剔除或在表头注明其标签是有效参数量；删掉「13B 回折」那句，改为「gemma-4 的 Q2_K_XL 档里 12B 这一格低于同档 4B（54.3% vs 74.4%，n=164），与同模型 Q3_K_XL 档的 93.9% 相差 39.6pp，属该配方格的问题」。

### size-curve-inventory :: 用实测参数量当 X、每个基准钉死一个协议、每格用自己的 `n_items` 做分母，库内能画出 63 条「同族 + 同配方 + 同基准 + 同语言」的规模曲线（至少 2 个 rung）；其中 40 条完全单调，23 条有反向步；反向步里只有 4 处既超出二项噪声又不能由已知 harness 缺陷解释，全部是 gemma-4 的 Q2_K_XL 档在 7.518B→11.907B 上（gsm8k −19.0pp、Humaneval+ −18.9pp、Humaneval −20.1pp、MBPP −10.3pp）。

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.size-axis-verdict, result.gemma4-q2kxl-inversion
- origin: `analysis/size_curves.py`（`PROTOCOL_OF` 把每个基准钉到一个协议；Wilson 区间 n = 该格 `n_items`）
- evidence: 分组口径：带配方的 `(lineage, recipe, bench, language)` 组共 328 个 = 63 条曲线（≥2 rung）+ **265 个只有一个 rung 的组**（记 `thin_curves`，每个带原因，不丢弃）+ 12 个无配方后缀而被跳过的格。「无曲线」的 265 个是结论而不是缺口：那些族在那个基准上只有一个尺寸有实测参数量。曲线数 63、单调 40、有反向 23、超出噪声 4；其余 19 处反向里 16 处的区间与前一档重叠（判「测不出」，最大是 Ternary-Bonsai 的 −6.2pp），3 处是已知 harness 失败（见 `gemma4-mpl-harness`）。被跳过的格子只有 12 个「无配方名」的，没有一例是因为缺 `n_items`。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_curves.py" | head -8`
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_curves.py" --check`（实跑输出：`7 expected true, 0 false`）

### gemma4-mpl-harness :: gemma-4 在 MultiPL-E raw 补全协议上的两处大幅反向（Q2_K_XL 档 26B-A4B 比 4B 低 41.6pp、Q3_K_XL 档低 71.4pp）是已记录的 harness 失败，不是规模效应——同一批文件在探针里 0/40，完成物是 markdown 推理散文而非代码。

- author: measurement
- scope: specific
- status: current
- kind: measured
- from: result.size-curve-inventory
- origin: `.wrapup/moe_structure_analysis.py::HARNESS_INVALID`（该表由 40 题探针与完成物形状判定）+ 本轮 `size_curves.py` 的 `harness_suspect` 标记
- evidence: `size_curves.json` 里 `gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf` 与 `..._Q3_K_XL.gguf` 在 `humaneval-cpp`/`humaneval-py` 两条线上的反向被标 `harness_explained: true`，故不计入「超出噪声」。i01 的 `res18`/`res19` 记录同一现象（raw 补全下 gemma-4 写散文，0/161）。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_curves.json'));[print(r['lineage'],r['recipe'],r['bench'],i) for r in d['curves'] for i in r['inversions'] if i['harness_explained']]"`

## plan5：双变量回归的可识别性

### moe-vif-unresolved :: 既往那份 `log(总参) + log(激活参)` 联合回归（`.wrapup/moe_structure_analysis.py` 及其输出 `.wrapup/moe_structure.json`）给出 VIF=1.93、`total_only` 调整 R²=0.668、`total+active`=0.750、`total+moe`=0.765，但它既不足以证明可识别、也不足以判不可识别：它只覆盖 `multipl-e-raw-greedy-768` 一个协议、把每格题数硬编码为 322、且成文于 `n_items` 回填之前，所以结论仍是未定，由 `WP3` 在 WP2 判定的行集上重算。

- author: measurement
- scope: specific
- status: provisional
- kind: analysis
- from: result.size-not-one-thing, result.active-param-is-a-filename-label
- origin: `.wrapup/moe_structure_analysis.py` 的一次运行（输出 `.wrapup/moe_structure.json`，mtime 2026-10-02，早于 `n_items` 回填与后续入库修复）
- evidence: json 里 `n_points_all=33`、`n_points_valid=31`、`vif_total_active=1.9342`；`fits` 数组里 `total+active` 的调整 R² 0.7496 只比 `total_only` 的 0.6680 高 0.082，而 `total+moe`（把「是否 MoE」当哑变量）到 0.7647；`total+active+moe+experts` 里总参系数变成 −0.127（t=−1.41）。这是「两个变量几乎在做同一件事」的形态，不是「两者都可估」的形态。
- 每格题数硬编码的证据就在脚本里：`moe_structure_analysis.py` 的 `n = 322` 与 `passes = round((lang["cpp"] + lang["py"]) / 2 * 161) * 2`。
- repro: `python3 -c "import json;d=json.load(open('.wrapup/moe_structure.json'));print(d['vif_total_active'],d['n_points_valid']);[print(f['name'],round(f['adj_r2'],4),[round(b,4) for b in f['beta']]) for f in d['fits']]"`
- 推翻条件：在 `WP2` 判为「`__size` 是真参数量」的行集上，用每行自己的 `n_items` 重算后若 VIF（或条件数）降到可接受区且两个系数都带同号区间，则本条改写为「可识别」，反之写成「不可识别 + 缺哪类受控对」。

### res6 :: 模型规模：同一量化配方下，参数量越大分数越高；小模型之间的差距通常大于大模型之间。

- author: measurement
- scope: general
- status: provisional
- kind: measured
- origin: `.scratch/originals/L2-结果.md` 模型规模（原稿；`.scratch` 已退役）
- evidence: 报告 §2 面板（30 格，`evalplus` 系 HumanEval 164 题）逐格值见 `report.html` §2 的原始数据表；本层尚未给它一条独立于报告生成器的复算命令，也尚未逐家族检验单调性，因此降为 provisional。已知至少 gemma-4 的 12B 格在这条口径下低于同配方的 4B 格，与「越大越高」不一致（`WP4` 负责定性）。
- repro: 未就位——`WP4` 的 `analysis/size_curves.py` 建好后填入

### an3 :: 小模型做困难、多步任务需要更多位宽：2B 在低比特时困难 agentic 任务整体触底。

- author: agent
- scope: general
- status: provisional
- kind: analysis
- from: result.res1
- origin: `.scratch/originals/L3-分析.md` 3（原稿；`.scratch` 已退役）
- evidence: 该条由 a01 的位宽事实 `result.res1` 推出，本层只能判它在规模轴上是否复现（`WP4`），判不了位宽轴本身；本次归位未新增测量，状态保持 provisional。
- repro: 未就位——`WP4` 建好后填入；位宽轴那侧的可复算入口是 `python3 "docs/subprojects/a01-量化位宽/analysis/run_all.py"`

### moe-design-not-identified :: plan5 的双变量回归在本库的模型集里**不可识别**：稠密模型的激活参等于总参（稠密子集内 log 总参与 log 激活的 r = 1.0000，去掉 MoE 点后设计矩阵秩亏），MoE 子集内两个变量也锁在一起（r = 0.962、VIF = 13.3 > 10），加上「是否 MoE」指示变量后两个系数翻号（总参 +0.1624→+0.4535、激活 +0.0926→−0.2056），说明合并拟合的两个「显著」系数是两团点云的假象。

- author: measurement
- scope: general
- status: current
- kind: analysis
- from: result.moe-active-params-measured, result.size-axis-verdict
- origin: `analysis/size_regression.py`（X = 实测总参/激活参，Y = `_bench='humaneval'` + `evalplus-0.3.1-openai-chat-greedy-base` 每模型一格，权重 = 1/二项方差）
- evidence: 65 个可用模型点（稠密 50、MoE 15）。**全样本**的数值共线性并不高（r=0.628、VIF=1.65、中心化条件数 2.09），所以只看全样本 VIF 会误判为可识别；两条子集判据才是阻塞：稠密子集 r=1.0000（秩亏），MoE 子集 r=0.962、VIF=13.3。合并拟合 总参 +0.1624±0.0268、激活 +0.0926±0.0311（两个都「显著」），但加入 MoE 指示变量后变成 +0.4535±0.1720 与 −0.2056±0.1767；只看 MoE 点时总参系数 +0.1222±0.1405（t=0.87，与 0 不可分）。留一族检验（17 族逐一删除）里两个系数都不翻号，说明合并拟合不是被某一族顶住的——这与「不可识别」不矛盾：不可识别是设计层面的，不是样本量层面的。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_regression.py"`（实跑输出：`dense-only r = 1.0000（激活≡总参，秩亏）   MoE-only r = 0.962  VIF_moe = 13.3` 与 `total+active+moe_dummy … ln_size=+0.4535 ln_active=-0.2056`）
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_regression.py" --check`（实跑输出：`12 expected true, 0 false`）
- 要让它可识别的最小补测：至少两对「同总参、不同激活」的受控点（同一 MoE 权重换 `expert_used`，或同总参的稠密/MoE 对）。本轮没有这类格，记未测。

### size-total-slope :: 在稠密模型上被识别的只有一个合并斜率：实测总参每涨 e 倍，HumanEval 分数涨 0.210±0.023（`total_only` 加权拟合，n=65，adjR²=0.754）；单独用激活参拟合更弱（0.205±0.031，adjR²=0.658）。

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.moe-design-not-identified
- origin: `analysis/size_regression.py` 的 `fits`
- evidence: 报告只能说「规模大分数高」的**方向**与这个量级，不能说「总参与激活参各自贡献多少」；`total+active` 的 adjR² 0.782 只比 `total_only` 的 0.754 高 0.028，而这 0.028 完全由 15 个 MoE 点提供。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_regression.json'));[print(m['name'],round(m['adj_r2'],4),[round(b,4) for b in m['beta']],[round(x,4) for x in m['se']]) for m in d['fits']]"`

### moe-sits-above-same-active-dense :: 同样激活参数量下，三个大 MoE 家族站在稠密曲线的高处而不是旁边：gemma-4-26B-A4B（3.82B 激活）的等效稠密规模 18.4–22.1B、Qwen3.6-35B-A3B（3.52B 激活）18.9–20.4B、GLM-4.7-Flash（3.90B 激活）11.3–11.6B，分别是自身激活参数的 4.8–5.8×、5.4–5.8×、2.9–3.0×；LFM2.5-8B-A1B（1.69B 激活）则是 1.3–1.9B，约等于自身激活参数。

- author: measurement
- scope: general
- status: provisional
- kind: analysis
- from: result.moe-active-params-measured, result.size-total-slope
- origin: `analysis/size_moe_position.py`（只在 50 个稠密点上拟 `score = 0.2223 + 0.2375·ln(参数量)`，adjR²=0.716，再对每个 MoE 反解等效稠密规模）
- evidence: 稠密拟合与 15 个 MoE 锚点逐条见 `moe_position.json`。GLM-4.7-Flash 的 `TQ1_0` 档（2.2 比特）等效 2.90B，是量化效应不是架构效应，所以上面引用的是它的 Q2/Q3 档。15 个锚点里 11 个的等效稠密规模大于自身激活参数。
- 边界：这是**跨家族**比较（tokenizer、训练数据、代数都不同），只能读成「MoE 锚点落在稠密曲线的哪一侧、差多少」，不能读成「架构增益」；库内没有同家族同权重的稠密/MoE 对（这正是 `moe-design-not-identified` 的成因）。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_moe_position.py"`（实跑输出：稠密拟合 + 15 行锚点表）
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_moe_position.py" --check`（实跑输出：`4 expected true, 0 false`）

## 报告 §2 现在说的两句话

### report-s2-claims :: 报告第二节的两条结论不是从库里算出来的，是 `make_report.py` 里的硬编码文本，本轴的 `WP6` 要逐句判它们成立与否。

- author: third-party
- scope: specific
- status: current
- kind: citation
- origin: `report.html` §2「分析」框与生成它的源码
- evidence: 两句为「同一配方下，参数量越大分数越高」和「小模型之间（0.8B→2B→4B）的差距通常比大模型之间更大——大模型已接近各自的分数上限，规模带来的边际收益变小」；源码位置 `make_report.py:1674-1675`。§2 的面板是 30 格（家族 @ 配方 × 规模），来自 `mktables.py` 的表，规模列用的是 `__size` 派生出的标签（`E2B`/`12b`/`26B-A4B` 等），因此 §2 的两个数字结论同时依赖 `size-not-one-thing` 判定的那条通道。
- repro: `grep -n "同一配方下，参数量越大分数越高\|小模型之间（0.8B→2B→4B）" make_report.py`（实跑输出：`1674`、`1675` 两行）
- repro: `python3 -c "import re;h=open('report.html',encoding='utf-8').read();i=h.find('<h2>二、模型规模');print(len(re.findall(r'<tr>',h[i:h.find('<h2>',i+10)])))"`（实跑输出：`62`，即 §2 的两张表各 2 行表头，30 格原始数据 + 30 行模型文件清单）
