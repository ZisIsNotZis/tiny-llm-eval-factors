# a02 模型规模 — 结果

每条事实一行一个陈述；数字后面必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
判断类结论（analysis）与技术测量分开，analysis 不覆盖任何数字。
本层只读 `experiments.sqlite`；所有命令都在仓库根执行。

## 本轴的 X 本身不是一条通道给的数

### size-not-one-thing :: 「模型规模」这一列（`experiments.__size`）由三条互不相同的通道给出，且其中一条把百万和十亿当成同一个单位：文件名 size token 直接取数（`-4B`→4.0）、同一 token 在 M 量级时不换算（`LFM2.5-230M`→230.0，实际 0.23B，差 1000 倍）、文件名没有 size token 时回退成 `2 × gguf 文件字节数`（量化后字节数是 `_file_size`）。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `exp.py::double_underscore_fields` 的解析规则 + `experiments.sqlite` 当前值
- evidence: 解析规则在 `exp.py:44`（`SIZE_RE = -E?([0-9.]+)[MB]\b`，不区分 M/B 单位）、`exp.py:62`（`size = float(...)`）、`exp.py:76-84`（`size < filesize` 时取 `filesize`；`size` 缺失时取 `filesize / 0.5`）。库内证据：`LFM2.5-230M-UD-Q4_K_XL.gguf` 的 `__size=230.0`、`functiongemma-*` 的 `__size=270.0`（两者都 >100，其余行都 <36）；`GLM-4.7-Flash` 六档的 `__size/_file_size` 全为 2.0000。
- repro: `sqlite3 -header -column experiments.sqlite "SELECT model,__size,__activation_size,count(*) FROM experiments WHERE __size>100 GROUP BY 1,2,3"`（实跑输出：`LFM2.5-230M-UD-Q4_K_XL.gguf|230.0|230.0|53`、`functiongemma-270M-*|270.0|270.0|14`）
- repro: `sqlite3 -header -column experiments.sqlite "SELECT model,__size,_file_size,round(__size/_file_size,4) r FROM experiments WHERE __model='GLM-4.7' AND __size>17 GROUP BY model ORDER BY __size"`（实跑输出：`GLM-4.7-Flash-UD-IQ1_S`/`IQ1_M`/`IQ2_XXS`/`IQ2_M`/`Q2_K_XL`/`IQ3_XXS`/`Q3_K_XL` 七行的 `r` 全为 `2.0`）

### size-tracks-bits :: 对有上述「2 × 文件字节数」回退的那些行，规模列随量化位宽移动而与参数量无关：`GLM-4.7-Flash` 的七个量化档是同一个模型的同一份权重，参数量按构造是常数，却在 `__size` 上跨 18.50–27.56，即「规模」在那里就是「比特数」。

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
- evidence: 通道与行数 `size-null` 1061 / `undecidable` 1112 / `token-rounded` 659 / `clamped-to-file-bytes` 190 / `two-times-file-bytes` 86 / `size-too-large-for-file` 67 / `label-below-total` 58，合计 3233，`other` 为 0（真参数量已知却解释不通的行一条也没有）。真参数量来源：169 组 / 1970 行由 GGUF 张量元素求和测得（`truth_source=gguf-tensors`），无一组来自猜测。
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" | head -12`（实跑输出：上表七行通道计数）
- repro: `python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" --check`（实跑输出：`32 expected true, 0 false`，退出 0）

### size-null-on-protocol-rows :: 缺规模的那 1061 行不是随机的：`__size` 为 NULL 的行恰好就是所有带 `protocol` 标签的新面板行（lm-eval 两个协议 453 行、EvalPlus 两个协议 294 行、多语言 30 行等），所以任何用 `experiments.__size` 当 X 的查询会静默丢掉整张 lm-eval / EvalPlus 面板，而报告 §2 的规模列走的不是这一列，是 `mktables.py::lineage_and_size` 从文件名取的数字标签。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `experiments.sqlite` 按 protocol 分组统计 `__size IS NULL`
- evidence: 按协议：`''`（历史行）1881 行中 0 行为 NULL；`lmeval-0.4.13-gguf-shim-reasoning-off` 227/227、`lmeval-0.4.13-chat-reasoning-off` 226/226、`evalplus-…-base` 147/147、`evalplus-…-plus` 147/147 全为 NULL；`_file_size` 一列 3233 行全部非空，所以这不是缺文件元数据，是插入时没算 `__size`。
- repro: `sqlite3 -header -column experiments.sqlite "SELECT protocol, count(*) n, sum(__size IS NULL) size_null FROM experiments GROUP BY 1 ORDER BY n DESC LIMIT 6"`
- repro: `sqlite3 -header -column experiments.sqlite "SELECT sum(__size IS NULL) size_null, sum(_file_size IS NULL) file_null FROM experiments"`（实跑输出：`1061|0`）

### gguf-truth-coverage :: 真参数量只覆盖 169 个模型文件（1970 行）；另 135 个文件（1263 行）在 `/home/z/hf/` 已不存在且不在 `.wrapup/bpw_map.json` 里，所以它们的「规模」在本轮不可判，只能按「未测」处理，不能假设等于标签。

- author: measurement
- scope: general
- status: current
- kind: measured
- origin: `analysis/size_provenance.json` 的 `missing` 与 `truth_source` 字段
- evidence: `/home/z/hf/` 只剩 134 个 `.gguf` 直链（其余模型文件已被清理）；`deepseek-r1-0528-qwen3-8b`、`dolphin3.0`、`glm-4.7-flash-reap-23b-a3b`、`north-mini-code-1.0`、`qwen3.6-27b` 等族全部落在这一档。这与 a01 的位宽轴无关：那轴同样只有 69 个文件的 bpw。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));print(len(d['missing']), sum(m['rows'] for m in d['missing']))"`（实跑输出：`135 1263`）

### label-honest-families :: 文件名标签在三个家族里就是参数量（误差 ≤10%）：Qwen3.5 的 0.8/2/4/9 实测 0.752/1.882/4.206/8.954，Ternary-Bonsai 的 1.7/4/8 实测 1.72/4.02/8.19，gemma-4-12B 的 12 实测 11.907。

- author: measurement
- scope: specific
- status: current
- kind: measured
- from: result.size-channel-inventory
- origin: GGUF 张量求和 vs 文件名标签（`size_provenance.json` 的 `token-rounded` 通道）
- evidence: 三族共 76 个组的标签都落在真参数量的 ±10% 内，且同一模型的不同量化档给出**同一个**标签（Qwen3.5-2B 的 Q2/Q3/Q4/IQ2/IQ3 全部 `__size=2.0`、真参 1.882），所以在这三族里「同族内按标签比大小」是可用的。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));[print(r['model'],r['db_size'],round(r['truth_params'],3)) for r in d['rows'] if r['channel']=='token-rounded' and r['model'].startswith(('Qwen3.5','Ternary-Bonsai'))]"`

### label-dishonest-cases :: 三个家族的标签不是参数量：gemma-4 的 `E2B`/`E4B` 是厂商的「有效参数量」（张量总和 4.65B / 7.52B），`LFM2.5-230M` 被写成 230（单位错，隐含比特数 8×0.15÷230≈0.005，物理上不可能），`GLM-4.7-Flash` 的七个量化档是同一份 29.94B 权重却给出 18.50–27.56 七个「规模」。

- author: measurement
- scope: specific
- status: current
- kind: measured
- from: result.size-channel-inventory
- origin: `size_provenance.json` 的 `label-below-total` / `size-too-large-for-file` / `two-times-file-bytes` 三条通道
- evidence: gemma-4-E2B-it-UD-Q4_K_XL 真参 4.6475B 而 `__size=3.1845`（恰好等于该文件字节数）；E2B 的八个量化档在 `__size` 上是 2.186/2.291/2.373/2.404/2.620/2.924/3.184/4.294，同一个模型八个「规模」；E4B 真参 7.5181B 而标签 4；`LFM2.5-230M-UD-Q4_K_XL` 的 `_file_size` 使 `8×字节÷230` 远小于 1；GLM-4.7-Flash 七个档 `__size/_file_size` 全为 2.0。
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

### size-axis-verdict :: 规模这个 X 只在「同族 + 同配方 + 标签通道诚实」三者同时成立时才是单调量：Qwen3.5 与 Ternary-Bonsai 的整条阶梯可用，gemma-4 只有 12B/26B-A4B 两档可与 12.0/25.23 的真值对齐，E2B/E4B 两档不可用（标签是有效参数量、`__size` 又随量化档在 2.19–4.29 之间漂移），GLM-4.7-Flash 与 LFM2.5-230M 整族不可用；报告 §2 那张表把「文件字节数」与「文件名标签」两种量混在同一个 X 轴上。

- author: agent
- scope: general
- status: provisional
- kind: analysis
- from: result.size-channel-inventory, result.label-honest-families, result.label-dishonest-cases, result.size-null-on-protocol-rows
- origin: 本层对 `report.html` §2 的 30 格逐格追溯（家族 @ 配方 × 规模）
- evidence: §2 的四个 lineage 中，Qwen3.5（0.752/1.882/4.206/8.954）与 Ternary-Bonsai（1.72/4.02/8.19）可用；gemma-4 的 E2B 的八个量化档在库里的 `__size` 是 2.186/2.291/2.373/2.404/2.620/2.924/3.184/4.294（同一个模型八个「规模」），E4B 的四档是 4.0/4.0/4.2157/4.5884，而它们是 4.65B 与 7.52B 的模型；GLM-4.7-Flash 不在 §2 面板里，但同一条通道会污染任何按它画的曲线。
- repro: `python3 -c "import json;d=json.load(open('docs/subprojects/a02-模型规模/analysis/size_provenance.json'));[print(r['model'],r['db_size'],r['channel']) for r in d['rows'] if r['model'].startswith('gemma-4-E')]" | sort -u`
- 推翻条件：若 §2 的规模列改用 GGUF 真参数量重算后，E2B/E4B 两档仍落在同一单调序列上且与 12B/26B 同量纲，本条改写为「可用，仅需换数源」。

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
