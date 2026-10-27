# a02 模型规模 — 结果

每条事实一行一个陈述；数字后面必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
判断类结论（analysis）与技术测量分开，analysis 不覆盖任何数字。
本层只读 `experiments.sqlite`；所有命令都在仓库根执行。

### acceptance-entry-point :: 本层的唯一验收入口是一条命令 `python3 "docs/subprojects/a02-模型规模/analysis/run_all.py" --selftest`，它跑六个脚本的 77 条断言并附一次负控（篡改一条取数通道后检查必须失败）；`A02_HF_ROOT=/nonexistent` 模拟干净 clone（没有任何 GGUF）时同样全绿。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/run_all.py`
- evidence: 逐脚本断言数 fixture 漂移检查 1、provenance 36、ladder 15、regression 12、curves 10、moe_position 4，合计 78（另有一次负控）；负控输出 `expected failure was seen`。真值来自入库 fixture `analysis/fixtures/gguf_truth.json`，所以断言不依赖 `/home/z/hf`；GGUF 头解析带 (size, mtime) 缓存（`analysis/gguf_cache.json`），重复运行 3m52s → 0.08s。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/run_all.py" --selftest`（实跑输出：`6/6 checks green` + `[PASS] negative control`）
- repro: `A02_HF_ROOT=/nonexistent python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" --check`（实跑输出：`36 expected true, 0 false`）

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

### size-channel-inventory :: 把库的全部行按取数通道归位后（当前 3364 行），只有 659 行（19.6%）的「规模」与 GGUF 张量求和的真参数量相差 10% 以内，1192 行根本没有规模（`__size IS NULL`），其余 1513 行分属四条与参数量无关的通道（文件名标签低于张量总数 58、等于文件字节数 190、等于两倍文件字节数 86、至少大 8 倍 67），另有 1112 行因模型文件不在盘上且无 bpw_map 条目而不可判。行数随入库增长，口径不变；断言只说「归位行数 = 库总行数」，不写死数字。

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.size-not-one-thing
- origin: `analysis/size_provenance.py`（读 `experiments.sqlite` 的 305 个 `(model, __size, _file_size)` 组 + `/home/z/hf/` 的 GGUF 头）
- evidence: 通道与行数 `size-null` 1192 / `undecidable` 1112 / `token-rounded` 659 / `clamped-to-file-bytes` 190 / `two-times-file-bytes` 86 / `size-too-large-for-file` 67 / `label-below-total` 58，合计 3364（= 库当前行数），`other` 为 0（真参数量已知却解释不通的行一条也没有）。真参数量来源：170 个 `(model, size)` 组 / 77 个模型文件 / 2101 行由 GGUF 张量元素求和测得（`truth_source=gguf-tensors` 或 `fixture`，两者同源），无一组来自猜测。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" | head -12`（实跑输出：上表七行通道计数）
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" --check`（实跑输出：`36 expected true, 0 false`，退出 0）

### size-null-on-protocol-rows :: 缺规模的行（当前 1192 行，随入库增长）全部是带 `protocol` 标签的行，但反过来不成立：带协议的行有相当一部分带规模（`multipl-e-raw-greedy-768`、bfcl 系、`evalplus-0.3.1-openai-chat`），而 lm-eval 系协议则 563/563 全缺。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `experiments.sqlite` 按 protocol 分组统计 `__size`
- evidence: `protocol IS NOT NULL AND protocol<>''` 1352 行，其中 `__size IS NOT NULL` 291 行、`NULL` 1061 行；1061 个空值全部落在带协议的行上（历史行 1881 个没有一条为空）。按前缀算 `protocol LIKE 'lmeval%'` 是 479 行、全为空；把以 `-lmeval` 结尾的变体协议（`variant-*-lmeval`、`spec-mtp-*-lmeval` 等）一并算上则是 `%lmeval%` 563 行，也全为空——两个数都对，差别只在口径，报告里用前缀那个 479 是同一事实的窄口径；`evalplus%` 313 行里 294 行为空、19 行有值；`bfcl%` 123 行里 29 行为空；`multipl-e%` 194 行里 16 行为空。`_file_size` 一列 3233 行全部非空，所以这不是缺文件元数据，是插入时没算 `__size`。
- repro: `sqlite3 -header -column experiments.sqlite "SELECT count(*) n, sum(__size IS NOT NULL) with_size FROM experiments WHERE protocol IS NOT NULL AND protocol<>''"`（实跑输出：`1352|291`）
- repro: `sqlite3 -header -column experiments.sqlite "SELECT sum(protocol LIKE '%lmeval%') n, sum(protocol LIKE '%lmeval%' AND __size IS NULL) nulls, sum(protocol LIKE 'multipl-e%' AND __size IS NOT NULL) mpl_with, sum(protocol LIKE 'bfcl%' AND __size IS NOT NULL) bfcl_with, sum(protocol LIKE 'evalplus%' AND __size IS NOT NULL) ep_with FROM experiments"`（实跑输出：`563|563|178|94|19`）
- repro: `sqlite3 -header -column experiments.sqlite "SELECT count(*) null_rows, sum(protocol IS NOT NULL AND protocol<>'') null_with_protocol FROM experiments WHERE __size IS NULL"`（实跑输出：`1061|1061`）

### gguf-truth-coverage :: 真参数量覆盖 170 个 `(model, size)` 组 / **77 个不同的模型文件**（库里只有这些文件的 GGUF 在盘上）/ 2101 行；另 135 个组（1263 行）的模型文件已从 `/home/z/hf` 消失且不在 `bpw_map` 里，只能记未测。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/size_provenance.json` 的 `missing` / `truth_source` 字段 + `analysis/fixtures/gguf_truth.json`
- evidence: `/home/z/hf` 只剩 134 个 `.gguf` 直链；`deepseek-r1-0528-qwen3-8b`、`dolphin3.0`、`glm-4.7-flash-reap-23b-a3b`、`north-mini-code-1.0`、`qwen3.6-27b` 等族全部落在这一档。76 个文件之所以覆盖 169 个组，是因为同一个模型文件在库里按 `(model, __size, _file_size)` 出现多个组。真值已做成入库 fixture，所以干净 clone 里这条检查不依赖 `/home/z/hf`（见 `fixture-gguf-truth`）。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));g=[r for r in d['rows'] if r['truth_source']];print(len(g), len({r['model'] for r in g}), sum(r['rows'] for r in g))"`（实跑输出：`170 77 2101`）
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));print(len(d['missing']), sum(m['rows'] for m in d['missing']))"`（实跑输出：`135 1263`）

### fixture-gguf-truth :: 实测参数量与逐类比特已做成入库 fixture `analysis/fixtures/gguf_truth.json`（全部在盘上的模型文件，当前 77 个；含总/专家池/共享参数量、激活参数量、专家数与激活专家数、每文件字节数、按 ggml 类型折算的逐类比特），`build_fixtures.py --check` 负责与现场 GGUF 比对漂移。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/build_fixtures.py` 的 `read_gguf()`（张量形状 + 类型表）与 `--check`
- evidence: 77 条记录（每入库一个新量化文件就重生成一次），未知 ggml 类型 0；类型表的自检是「按类型折算的张量字节数」对「文件真实大小」，`bpw_tensors` 与 `bpw_file` 的差中位 0.29%、最大 2.95%（差即元数据与对齐开销）。新增的 `Q1_0`(41)=128/18 与 `Q2_0`(42)=64/18 两块大小不是查表得来，而是由「文件字节 ÷ 元素数」反解并用同一条自检验过。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/build_fixtures.py" --check`（实跑输出：`77 个现场 GGUF 在场，0 处与 fixture 不符`）
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json'))['models'];print(len(d), sum(1 for r in d.values() if r['unknown_ggml_types']))"`（实跑输出：`77 0`）

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
- evidence: 分组口径：带配方的 `(lineage, recipe, bench, language)` 组共 326 个 = 63 条曲线（≥2 rung）+ **263 个只有一个 rung 的组**（记 `thin_curves`，每个带原因，不丢弃）+ 18 个无配方后缀而被跳过的格；这组数字随入库变，断言只要求「曲线 + 无曲线 = 组数」。「无曲线」的 265 个是结论而不是缺口：那些族在那个基准上只有一个尺寸有实测参数量。曲线数 63、单调 40、有反向 23、超出噪声 4；其余 19 处反向里 16 处的区间与前一档重叠（判「测不出」，最大是 Ternary-Bonsai 的 −6.2pp），3 处是已知 harness 失败（见 `gemma4-mpl-harness`）。被跳过的格子只有 12 个「无配方名」的，没有一例是因为缺 `n_items`。
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

## 版本/代际轴：库里四对候选、没有一对是受控对

### version-axis :: 「模型版本/代际」这条 X 在本库里没有可用的受控对：库内 3 对名字级版本对（27B UD 的 Q2_K_XL 与 Q3_K_XL 两档、Ornith 9B 的 Q4_K_M）旧侧都没有规范协议行，而唯一把 8 项身份栏对上 6 项的 Qwen3.5→3.6（35B-A3B）同时把位宽从 1.995 抬到 3.857 bit（+1.862），所以它那 12 个基准的差是「换代 + 位宽」的合成，判不了纯代际效应。

- author: measurement
- scope: general
- status: current
- kind: measured
- from: result.size-not-one-thing, result.fixture-gguf-truth, result.size-channel-inventory
- origin: 全库名字级版本对扫描（同 stem、只有版本号不同）+ `experiments.sqlite` 身份栏逐项对照 + `analysis/fixtures/gguf_truth.json`（GGUF 张量求和）与 `.wrapup/bpw_map.json`（有效位宽）
- evidence: 4 对候选与逐项身份栏（P0/P0' 的 11 行对照表、P1 的 8 组对照）；`fixtures/gguf_truth.json` 的 27.321B / 34.661B / 35.505B 与 `bpw_map` 的 2.878 / 3.850 / 1.995 / 3.857；P1 的 12 格差表（其中 5 格区间分开）；同代位宽阶梯 12 格（全重叠）；盘上 77 个 GGUF / 21 个同总参组 / 0 个混合组
- producer: 本文末「可复算命令」里的两条 SQL + 一段 python（均逐字实跑过）；P1 差表的 SQL 输出里 `temp`/`reasoning`/`kv`/`ctx`/`maxtok`/`spec`/`rep` 七列左右两侧相同，就是这 6 组身份栏对齐的证据
- 方法：把「只换代」拆成 8 个可查的身份栏（①参数量 ②位宽 ③provider ④`protocol` ⑤`n_ctx` ⑥`temp`+`max_tokens` ⑦`spec_type`+`rep` ⑧`reasoning`+KV 精度），任何一栏不一致就不叫受控对。分母一律用该行自己的 `n_items`；判「差得动没」用本层现行判据（逐题 Wilson 区间，`analysis/size_curves.py::verdict`，`n = n_items`），不另造。
- 库内一共 **3 对名字级版本对** + **1 对协议全对齐但名字里档位不同的对**，逐对判定在下表。这三对的问题不是「格子里没有数」，而是「旧侧那批行成文于 `protocol` 列存在之前」：全库 3364 行里有 1881 行的 `protocol` 是 NULL，而且旧侧那几行连 `source_file`/`run_tag`/`completed_at` 都是空的，盘上找不到任何产物。

| # | 对（旧 → 新） | 尺寸/档位 | 旧侧 GGUF 在盘? | 旧侧规范协议行 | 结论 |
|---|---|---|---|---|---|
| P0 | Qwen3.6-27B-UD-**Q2_K_XL** → Qwen3.8-27B-UD-Q2_K_XL | 27B / UD / Q2_K_XL | 否（也不在 fixture、不在 bpw_map） | 0（humaneval 3 行 + mbpp 2 行，全为 `protocol=NULL`） | **不可比** |
| P0' | Qwen3.6-27B-UD-**Q3_K_XL** → Qwen3.8-27B-UD-Q3_K_XL | 27B / UD / Q3_K_XL | 否 | 0（同上，5 行） | **不可比** |
| P1 | Qwen_Qwen3.5-35B-A3B-IQ1_M → Qwen_Qwen3.6-35B-A3B-Q3_K_M | 35B-A3B / 官方 IQ_M→Q_M | 是 | 12（12 个基准；新侧 humaneval-cpp/py 各 2 行） | 可算，但**代际 × 位宽**混杂 |
| P2 | ornith-1.0-9b-Q4_K_M → Ornith-1.5-9B-Q4_K_M | 9B / Q4_K_M | 否 | 0（旧侧 4 行全是 `protocol=NULL`、`temp=0.3`） | **不可比** |

#### P0/P0' 的受控性核对（27B UD，Q2_K_XL 与 Q3_K_XL 两档逐项同结论）

| 项 | 旧侧 3.6 | 新侧 3.8 | 受控? |
|---|---|---|---|
| 参数量（GGUF 张量求和，非标签） | **未测**：`Qwen3.6-27B-UD-Q2_K_XL.gguf` 不在 `/home/z/hf`、不在 `fixtures/gguf_truth.json`、不在 `bpw_map.json` | 27.321B（Q2/Q3 同文件族，dense，`expert_count=0`） | ✗ 无法核 |
| 量化位宽 | 未测；Q2 文件 12.041 GB、Q3 文件 14.788 GB | Q2 = 2.878 bit、Q3 = 3.850 bit | ✗ |
| provider | `__quant=UD-Q2_K_XL` | `UD-Q2_K_XL` | ✓ |
| `protocol` | NULL（Q2/Q3 各 5 行全空） | `evalplus-0.3.1-openai-chat-greedy-base`/`-plus`、`lmeval-0.4.13-{chat,gguf-shim}-reasoning-off`、`multipl-e-raw-greedy-768` | ✗ |
| `n_ctx` | NULL | 8192（MultiPL-E 4096） | ✗ |
| `temp` | 0.0 / 0.3 / 0.3（三行三个值） | 0.0 | ✗ |
| `max_tokens` | NULL | 768 / 1024 | ✗ |
| `spec_type` | none | none | ✓ |
| `rep` | NULL | 1 | ✗ |
| `reasoning` + KV 精度 | (auto, fp16/fp16) / (off, q8_0/q8_0) / (off, q8_0/q5_1) | (off, q8_0/q8_0) | ✗ |
| 产物出处 | `source_file`/`run_tag`/`completed_at` 全空，盘上没有任何 mres 目录 | `mres/m91-qwen38-27b-q2kxl/evalplus.json`（带 base/plus 通过题数 152/164、336/378）、`lmeval_panel.json` | ✗ |

按上面那 8 组身份栏数：**只有 provider 一组一致，其余 7 组不一致**（其中 `spec_type` 一致但同组的 `rep` 不一致，故该组记不一致），所以 P0/P0' 不是受控对——要求是 8 组全一致。前两组不一致是**在库内就能证伪的算术矛盾**，不依赖「文件丢了」这件事：
- Q2_K_XL 档：两个文件字节比 3.6/3.8 = **1.2250**。若两侧参数量相同（27.321B），旧侧位宽 = **3.526 bit**，比新侧 2.878 高 0.648 bit——「同档位」不成立；若两侧位宽相同（2.878 bit），旧侧参数量必须是 **33.468B**——「同 27B」不成立。**两者不可兼得。**
- Q3_K_XL 档：字节比 1.1249；同参数则旧侧 4.330 vs 新侧 3.850 bit，同位宽则旧侧需 30.732B。同样不可兼得。
- 旁证：家族内 UD-Q2_K_XL 的位宽带是 2.83–2.88 bit（`Qwen3.6-35B-A3B-UD-Q2_K_XL` 2.831、`Qwen3.8-27B-UD-Q2_K_XL` 2.878），3.526 落在 Q2 与 Q3（3.85）之间，不属于任何一档。
- 有人会拿「3.6 那 3 行里有一行是 `temp=0.0`，和新侧一样」来主张可比。它同时是 `reasoning=auto` + `fp16/fp16` KV，而新侧是 `reasoning=off` + `q8_0/q8_0`——**新侧占住 (0.0, off, q8_0/q8_0) 这一格，旧侧三个点分别落在 (0.0, auto, fp16/fp16)、(0.3, off, q8_0/q8_0)、(0.3, off, q8_0/q5_1)，没有点落在新侧的格上**。另外 `reasoning='auto'` 在代码类基准上不可解释：`a08::res1` 已判「`auto` 的 619 个 EvalPlus 格不能说成开或关，它们的 `protocol` 是 NULL，reasoning 设置不可知」——这 3 行正是那一类。

#### 每基准代际差：P0 / P0'（两档都必须写「不可比，缺什么」）

12 个基准逐格：**10 个基准旧侧一行都没有；humaneval/mbpp 旧侧有行但身份不齐**。因此不存在「差」这一列——写成差就是把变量移动当效应。

| 基准 | 新侧 3.8（Q2_K_XL）值 / n / 协议 | 旧侧 Q2_K_XL | 旧侧 Q3_K_XL | 判定 |
|---|---|---|---|---|
| arc_challenge | 0.6100 / 100 / lmeval-shim | 0 行 | 0 行 | 不可比：缺旧侧该基准测量 |
| gsm8k | 0.9800 / 100 / lmeval-chat | 0 行 | 0 行 | 同上 |
| gsm8k-strict | 0.9800 / 100 / lmeval-chat | 0 行 | 0 行 | 同上 |
| mmlu | 0.8037 / 912 / lmeval-shim | 0 行 | 0 行 | 同上 |
| truthfulqa_mc2 | 0.5210 / 100 / lmeval-shim | 0 行 | 0 行 | 同上 |
| ifeval | 0.8300 / 100 / lmeval-chat | 0 行 | 0 行 | 同上 |
| humaneval | 0.9268 (Q3: 0.8720) / 164 / evalplus-base | 3 行，`protocol=NULL` | 3 行，`protocol=NULL` | 不可比：protocol/temp/reasoning/KV 无一对齐 |
| humaneval-plus | 0.8963 (Q3: 0.8354) / 164 / evalplus-plus | 0 行 | 0 行 | 不可比：缺旧侧 |
| mbpp | 0.8889 (Q3: 0.8704) / 378 / evalplus-base | 2 行，`protocol=NULL`、`temp=0.3`（旧侧无 temp=0 的 mbpp 行） | 2 行，同 | 不可比 |
| mbpp-plus | 0.7619 (Q3: 0.7381) / 378 / evalplus-plus | 0 行 | 0 行 | 不可比：缺旧侧 |
| humaneval-cpp / -py（MultiPL-E） | 新侧有（m10/m26/m161 三条协议串） | 0 行 | 0 行 | 不可比：缺旧侧 |

- 「两档方向是否一致」在 P0 上**无从判**：两档在 12 个基准上都只有一侧的数，任何「Q2 涨、Q3 跌」的说法都只能来自把旧侧那 3 行硬配上新侧——那 3 行的身份不齐（见上表），配出来的数不是代际差。为了让复核者知道这个陷阱长什么样：硬配会给出 **Q2 humaneval +3.66…+4.88pp（新侧更高）、Q3 humaneval −3.66…−5.49pp（新侧更低）**，方向相反、且四个数里三个区间重叠。这是「变量移动」的指纹，不是「代际差随位宽变」的证据。

#### 每基准代际差：P1（唯一可算的一对，但只能读成合成差）

P1 的 8 组身份栏里**只有 2 组不一致**：①参数量 +2.44%（34.661B → 35.505B）与②位宽 +1.862 bit（1.9950 → 3.8570）。其余 6 组全对齐：③provider 两侧都是官方 `Q_*` 档（`Qwen_` 前缀，`IQ1_M`/`Q3_K_M`，不是 UD 重打包）；④`protocol` 串逐字相同；⑤`n_ctx` 8192（MultiPL-E 4096）；⑥`temp=0.0`、`max_tokens` 768/1024；⑦`spec_type=none`、`rep=1`；⑧`reasoning=off`、KV 都是 q8_0/q8_0。另外 GGUF 头的 arch tag 两侧都是 `qwen35moe`，专家数都是 8/256。

| 基准 | 旧 3.5 | 新 3.6 | Δ | n | 是否超过地板（i01::res32 地板=0 题） | 二项区间 |
|---|---|---|---|---|---|---|
| humaneval | 0.8476 | 0.9268 | **+7.93pp** | 164 | 超过 | 重叠（测不出） |
| humaneval-plus | 0.8110 | 0.8841 | +7.32pp | 164 | 超过 | 重叠（测不出） |
| mbpp | 0.7910 | 0.9153 | **+12.43pp** | 378 | 超过 | 分开 |
| mbpp-plus | 0.6614 | 0.7778 | **+11.64pp** | 378 | 超过 | 分开 |
| mmlu | 0.7675 | 0.8454 | **+7.79pp** | 912 | 超过 | 分开 |
| arc_challenge | 0.5500 | 0.6200 | +7.00pp | 100 | 超过 | 重叠（测不出） |
| gsm8k | 0.8900 | 0.9700 | +8.00pp | 100 | 超过 | 重叠（测不出） |
| gsm8k-strict | 0.8800 | 0.9700 | +9.00pp | 100 | 超过 | 重叠（测不出） |
| ifeval | 0.8200 | 0.8300 | +1.00pp | 100 | 超过 | 重叠（测不出） |
| truthfulqa_mc2 | 0.5109 | 0.5032 | −0.77pp | 100 | 超过 | 重叠（测不出） |
| humaneval-cpp | 0.4907 | 0.7578 | **+26.71pp** | 161 | 超过 | 分开 |
| humaneval-py | 0.5652 | 0.7391 | **+17.39pp** | 161 | 超过 | 分开 |

- **两个「超地板」要分开读**：`i01::res32` 的地板是「同配置重复跑 = 0 道题」，所以这 12 格**全部**超过地板（差不是重复噪声）；但要问「这个差能不能分辨」，本层用的是逐题 Wilson 区间——**只有 5 格（mbpp、mbpp-plus、mmlu、humaneval-cpp、humaneval-py）区间分开**，其余 7 格按库内现行口径记「测不出」。
- 半宽参照（p=0.5）：n=100 → ±9.62pp、161 → ±7.63pp、164 → ±7.56pp、378 → ±5.02pp、912 → ±3.24pp。新侧 `m91/m100/m101` 面板的 arc/gsm8k/ifeval/truthfulqa 四格带 `limit_spec='100'`，本来就只够分辨 ≥10pp 的差。
- **这 12 个差不能读成代际效应**（推断，`status: provisional`）：位宽项扣不掉，理由是本库自己量过的那一段——`a01::ternary-offcurve`：GLM-4.7-Flash 从 2.226 bit 抬到 3.176 bit，HumanEval+ 抬 **29.9pp**、GSM8K 抬 33.0pp。P1 在 HumanEval+ 上的合成差只有 +7.3pp，**完全落在「位宽一项就能造出」的量级内**。唯一能用来「扣」的同代阶梯是 3.6-35B-A3B 的 UD-Q2_K_XL(2.831)→UD-Q3_K_XL(3.879)，+1.048 bit，12 个基准上**全部区间重叠、|Δ|≤6.21pp**；但这一段根本不覆盖 P1 旧侧所在的亚 2 bit 区（1.995 bit，`run_tag=m35-sub2bit`），所以它既不能支持也不能否证「位宽解释了这些差」。按本层规矩（`AGENTS.md` §2：「不可识别时给缺哪类受控对，不给凑出来的数」），这里给的是**不可识别 + 缺哪一对**，不是一个扣除后的代际差。
- 顺带一条可用的：同一代内部的位宽阶梯（上一条那 12 格）在 2.83→3.88 bit 之间测不出任何基准的移动，这本身是 `a01` 位宽轴的复现（中等位宽区平坦），与代际无关。
- **最小补测（两个都开价，不排队）**：①把 `Qwen3.5-35B-A3B` 量化到 3.85±0.05 bit 再跑同一 panel（现有的是 1.995 bit 的官方 IQ1_M，同族没有第二个点）——这一条直接把位宽项做成 0，是唯一能把「代际」从这个混合里分出来的做法；②把 `Qwen3.6-35B-A3B-UD-IQ1_M` 的同一 panel 跑出来（库里有它 5 行、全是 `protocol=NULL` 的 humaneval/mbpp），但该文件不在盘上、且它自己是 2.56 bit 而不是 1.99 bit，所以就算跑通也只能把位宽差缩到 0.57 bit，不能归零。①比②值钱。

#### 架构（dense vs MoE）这一类 X：同样没有受控对

- 盘上 77 个 GGUF 里 17 个 `expert_count>0`；**21 个「实测总参相同」的组里，组内 `expert_count` 混合的组 = 0**——即库与本机都没有「同一份权重、分别以 dense 与 MoE 两种形态存在」的一对文件。
- 名字层面最像的两组都不是受控对：`GLM-4.7-Flash`（实测 **MoE 4/64**，29.94B/激活 3.90B）与 `GLM-4.7-Flash-REAP-23B-A3B`（标签 23/3）之间是 **REAP 剪枝**，权重与总参都变了；Qwen3.6 的 27B（dense，27.32B）与 35B-A3B（MoE 8/256，35.51B）同代不同权重、总参差 30%。
- 缺什么：同一份权重导出 dense/MoE 两形态，或同一 MoE 换 `expert_used`（这就是 `moe-design-not-identified` 里登记的同一条最小补测，本节点不新增结论）。旁证：`qwen35`/`qwen35moe` 两个 arch tag 在库里都存在，但跨 tag 的每一对同时换了尺寸。

#### 复核者会反对的地方（逐条先认）

1. **「你只是没找到」**：名字级扫描只有 3 对，P1 是我按 (size token, provider, 专家数) 另外找出来的，因为它的档位在名字里不同（`IQ1_M` vs `Q3_K_M`）。反向也查过：全库没有任何一对模型文件名只差版本号且有规范协议行（名字级 3 对里 2 对是 27B UD，1 对是 Ornith，全部旧侧无协议）。
2. **「P1 的 +26.71pp 那么大，位宽不可能解释」**：可能，也可能不是——`a01::ternary-offcurve` 在 2.226→3.176 bit 这一段量到 29.9pp。我不拿「大到不像位宽」当论据，这正是它不可识别的理由。
3. **参数量差 2.44% 算不算「同规模」**：这是我自己判的，标准是「同一标签、同一专家结构、差 <3%」。若复核者要求完全同参，则 P1 连「同规模」也不成立，四条候选对全部作废——结论只会更强（一条受控对都没有），不会更弱。
4. **`humaneval-cpp/py` 新侧 rep=2**：两条同协议同分不同 `run_tag`（`m25-vendor`/`m37-vendor-matched-size`）。按 `size_curves.py::cells()` 的库内口径取均值（分数相同，均值不改变值）与 `min(n_items)`，所以不影响数字；但它说明这两格有重复入库，引用时要知道。
5. **本层没有逐题行，`humaneval`/`mbpp` 的聚合口径不是我定的**：库内 `humaneval` 的 `n_items` 恒为 164、`mbpp` 恒 378，**没有逐题行**，每行本身就是「分子/`n_items`」；同一格多行时的库内口径是 `size_curves.py::cells()` 的「分数取均值、分母取最小 `n_items`、`replicates` 记行数」。我没有另造口径，也没有把身份不同的旧侧三行平均成「一个 3.6 的值」。
6. **判分通道的已知缺陷**（引 `i01`，`size_curves.py::CAVEAT`）：EvalPlus 不做后处理（围栏不过即判错）；gsm8k 用 `flexible-extract`；mmlu/arc 似然打平静默取下标 0 且无逐题样本；`truthfulqa_mc2` 的 acc 是归一化后的概率质量（地板 0.4484），所以表中 `truthfulqa_mc2` 的 −0.77pp 连方向都不该读。
7. **「差是否超过地板」有两种答案**：按 `i01::res32` 的重复地板（0 题）全部超过；按二项区间只有 5 格分开。我在表里两列都给了，没有选一个更好看的。
8. **P2 才是最便宜的那一对，但它的旧侧不是同一口径**：Ornith 这一对的字节比是 0.9739（若同参 9.197B，位宽 4.896 vs 5.028，只差 0.13 bit），所以规模/位宽这一层比 P0/P1 都干净；但旧侧 4 行是 `protocol=NULL`、`temp=0.3`（采样），新侧是 `temp=0.0` 规范协议——差不是「小」，是**不可比**。修它比修 P0 便宜（一次重跑，但 `ornith-1.0-9b-Q4_K_M.gguf` 不在盘上，需先重新取权重）。

#### 可复算命令

一条 SQL 出 P1 的差表与全部身份栏（P1 是唯一能出数的对；`min()` 列左右两边相同即表示该身份栏一致）：

```
sqlite3 -header -column experiments.sqlite <<'SQL'
WITH canon(b,proto) AS (VALUES
 ('humaneval','evalplus-0.3.1-openai-chat-greedy-base'),
 ('humaneval-plus','evalplus-0.3.1-openai-chat-greedy-plus'),
 ('mbpp','evalplus-0.3.1-openai-chat-greedy-base'),
 ('mbpp-plus','evalplus-0.3.1-openai-chat-greedy-plus'),
 ('mmlu','lmeval-0.4.13-gguf-shim-reasoning-off'),
 ('arc_challenge','lmeval-0.4.13-gguf-shim-reasoning-off'),
 ('truthfulqa_mc2','lmeval-0.4.13-gguf-shim-reasoning-off'),
 ('gsm8k','lmeval-0.4.13-chat-reasoning-off'),
 ('gsm8k-strict','lmeval-0.4.13-chat-reasoning-off'),
 ('ifeval','lmeval-0.4.13-chat-reasoning-off'),
 ('humaneval-cpp','multipl-e-raw-greedy-768'),
 ('humaneval-py','multipl-e-raw-greedy-768'))
SELECT c.b bench, o.n_items n, round(avg(o._score),4) old, round(avg(n._score),4) new,
       round(100*(avg(n._score)-avg(o._score)),2) delta_pp, count(*) pairs,
       min(o.temp||'/'||n.temp) temp, min(o.reasoning||'/'||n.reasoning) reasoning,
       min(o.cache_type_k||o.cache_type_v||'/'||n.cache_type_k||n.cache_type_v) kv,
       min(ifnull(o.ctx_size,'-')||'/'||n.ctx_size) ctx,
       min(ifnull(o.max_tokens,'-')||'/'||n.max_tokens) maxtok,
       min(o.spec_type||'/'||n.spec_type) spec, min(o.rep||'/'||n.rep) rep
FROM experiments o JOIN experiments n
  ON n._bench=o._bench AND n.protocol=o.protocol AND n.n_items=o.n_items
JOIN canon c ON c.b=o._bench AND c.proto=o.protocol
WHERE o.model='Qwen_Qwen3.5-35B-A3B-IQ1_M.gguf' AND n.model='Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf'
GROUP BY c.b, o.n_items ORDER BY o.n_items, c.b;
SQL
```

一条 SQL 出 P0/P0' 的「不可比」证据（旧侧 5 行全 `NULL` 协议，新侧每基准 1 行）：

```
sqlite3 -header -column experiments.sqlite "SELECT _bench,model,protocol,temp,reasoning||'/'||cache_type_k||'/'||cache_type_v idents,n_items,round(_score,4) s FROM experiments WHERE model GLOB 'Qwen3.[68]-27B-UD-Q[23]_K_XL.gguf' ORDER BY _bench,model,_score"
```

一段 python 重打本节点所有派生数（参数量/位宽反解、区间、半宽、同代阶梯、架构轴；只读库与入库 fixture）：

```
python3 - <<'PY'
import json,math,sqlite3
con=sqlite3.connect("file:experiments.sqlite?mode=ro",uri=True);con.row_factory=sqlite3.Row
R=[dict(r) for r in con.execute("select * from experiments")]
F=json.load(open("docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json"))["models"]
B=json.load(open(".wrapup/bpw_map.json"))
C={"humaneval":"evalplus-0.3.1-openai-chat-greedy-base","humaneval-plus":"evalplus-0.3.1-openai-chat-greedy-plus",
   "mbpp":"evalplus-0.3.1-openai-chat-greedy-base","mbpp-plus":"evalplus-0.3.1-openai-chat-greedy-plus",
   "mmlu":"lmeval-0.4.13-gguf-shim-reasoning-off","arc_challenge":"lmeval-0.4.13-gguf-shim-reasoning-off",
   "truthfulqa_mc2":"lmeval-0.4.13-gguf-shim-reasoning-off","gsm8k":"lmeval-0.4.13-chat-reasoning-off",
   "gsm8k-strict":"lmeval-0.4.13-chat-reasoning-off","ifeval":"lmeval-0.4.13-chat-reasoning-off",
   "humaneval-cpp":"multipl-e-raw-greedy-768","humaneval-py":"multipl-e-raw-greedy-768"}
def w(p,n,z=1.96):
    d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return max(0,c-h),min(1,c+h)
def cell(m,b):                       # 库内口径 = analysis/size_curves.py::cells()
    h=[r for r in R if r["model"]==m and r["_bench"]==b and r["protocol"]==C[b]]
    return (sum(r["_score"] for r in h)/len(h),min(r["n_items"] for r in h),len(h)) if h else None
A="Qwen3.6-27B-UD-%s.gguf";Bz="Qwen3.8-27B-UD-%s.gguf"
for q in ("Q2_K_XL","Q3_K_XL"):
    a=[r["_file_size"] for r in R if r["model"]==A%q][0];b=[r["_file_size"] for r in R if r["model"]==Bz%q][0]
    p=F[Bz%q]["n_params"]
    print(f"27B {q}: 字节比 {a/b:.4f} | 同参数({p/1e9:.3f}B)→旧侧 bpw={8*a*1e9/p:.3f} vs 新侧 {8*b*1e9/p:.3f}"
          f" | 同位宽→旧侧需 {8*a*1e9/(8*b*1e9/p)/1e9:.3f}B")
for name,o,n in (("P0 Q2",A%"Q2_K_XL",Bz%"Q2_K_XL"),("P0 Q3",A%"Q3_K_XL",Bz%"Q3_K_XL"),
                 ("P1 35B-A3B","Qwen_Qwen3.5-35B-A3B-IQ1_M.gguf","Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf")):
    print("---",name)
    for b in C:
        x,y=cell(n,b),cell(o,b)
        if x and y:
            l1,h1=w(y[0],y[1]);l2,h2=w(x[0],x[1])
            print(f"  {b:15s} {y[0]:.4f}->{x[0]:.4f} Δ={100*(x[0]-y[0]):+.2f}pp n={y[1]} "
                  f"{'区间分开' if (h1<l2 or h2<l1) else '区间重叠'}")
        else:
            print(f"  {b:15s} 不可比（旧侧规范协议行 {len([r for r in R if r['model']==o and r['_bench']==b])} 行，"
                  f"新侧 {len([r for r in R if r['model']==n and r['_bench']==b])} 行）")
print("--- 同代位宽阶梯 3.6-35B-A3B UD-Q2_K_XL->UD-Q3_K_XL (+1.048bit)")
for b in C:
    x,y=cell("Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf",b),cell("Qwen3.6-35B-A3B-UD-Q2_K_XL.gguf",b)
    if x and y:
        l1,h1=w(y[0],y[1]);l2,h2=w(x[0],x[1])
        print(f"  {b:15s} {y[0]:.4f}->{x[0]:.4f} Δ={100*(x[0]-y[0]):+.2f}pp {'分开' if (h1<l2 or h2<l1) else '重叠'}")
print("半宽(p=0.5):",{n:round(100*(w(.5,n)[1]-w(.5,n)[0])/2,2) for n in (100,161,164,378,912)})
print("协议 NULL 行:",sum(1 for r in R if not r["protocol"]),"/",len(R))
g={}
for v in F.values(): g.setdefault(v["n_params"],[]).append(v["expert_count"])
print("盘上 GGUF",len(F),"MoE",sum(1 for v in F.values() if v["expert_count"]>0),
      "同总参组",sum(1 for v in g.values() if len(v)>1),"混合组",sum(1 for v in g.values() if len(set(v))>1))
PY
```
