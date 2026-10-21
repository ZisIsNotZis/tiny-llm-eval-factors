# a10 第三方量化方案 — 结果

每条事实一行一个陈述；有数字就必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
测量（`kind: measured`）与分析（`kind: analysis`）分开写，analysis 不覆盖任何数字。

## 证据绑定（读这一层之前先看这里）

本层的数字只由三样东西的内容决定，绑定到它们的 sha256：

| 产物 | sha256 | 作用 |
|---|---|---|
| `analysis/fixtures/a10_map.json` | `238d0228fcf38fba5e710bdaa608e2bcd0e6c567dfe2beb231c941c017007d0e` | 五个面板文件的分数格 + 九个文件的位宽与逐张量分配指纹 |
| `.wrapup/bpw_map.json` | `4f490813cf5fd45caf608fae91cfd37b9648cddc1c8ef05fc54e5e4b94b2dacf` | 有效位宽（`8 × 文件字节 ÷ gguf 精确参数量`） |
| `experiments.sqlite` | 写作时 `ce849960ab5005a58120ccedc4279716dc1aef86c0945772cc4f0493b3c5fb95` | 全部分数格 |

`experiments.sqlite` 由多个子项目并发写入，所以它自身的 sha256 **不是**本层结论的依据；依据是
`run_all.py` 的 `fixture-drift` 一条：45 个分数格与库逐格一致（`n_items` 与 `score` 都比）。
夹具的 sha256 变了就必须同时改上表（改夹具 = 改判据，见 `AGENTS.md` 第 9 条）。

代码 revision 用一条能解析的命令读，不在正文里写死：
`git log -1 --format=%H -- "docs/subprojects/a10-第三方量化方案"`。

复算装置：`analysis/panel.py`（面板、位宽、几何、区间）、`analysis/position.py`（位置与区间）、
`analysis/alloc_a10.py`（gguf 头的逐类/逐张量分配）、`analysis/protocol_identity.py`（五个面板的命令行是否只在模型路径上不同）、
`analysis/build_fixture.py`（重建/漂移检查夹具）、`analysis/run_all.py`（36 条断言，退出码即结论）。
本层**只读** `experiments.sqlite`，不写库、不改 `report.html`、不加载权重、不占 GPU。

## 一、装置与总体（`kind: measured`）

### panel-size :: 本层唯一的第三方方案是 **GSQ-RCO**，库内有两档有分数格；同一族（`Qwen3.8-27B`）的原生阶梯有三个档。五个文件的有效位宽是原生 2.878 / 3.850 / 4.173、第三方 3.058 / 3.549 比特/权重；文件字节分别是 9,828,981,664 / 13,146,393,504 / 14,252,845,984 与 10,442,827,840 / 12,120,016,960。

- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `analysis/fixtures/a10_map.json` 的 `files`（每个文件带 `n_bytes` / `n_params` / `bpw_file`）；位宽与 `.wrapup/bpw_map.json` 逐项一致（`run_all.py` 的 `bpw-map` 五条）
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/alloc_a10.py"`
- 说明：库内有分数格的 71 个模型文件里，只有这两个带第三方案标记（`GSQ`/`RCO` 同时出现）。`GLM-4.7-Flash-UD-TQ1_0.gguf` 虽然档位名少见，但它是 unsloth **自己阶梯**的三元档（`UD-TQ1_0`），那一档归 `a01`，不进本轴。

### tensor-set :: 五个面板文件是同一套权重结构：**866 个张量、张量名集合逐项相同、元素数逐项相同、参数量都是 27,320,697,856**。所以「同一族、只换量化文件」在这份数据里是实测的，不是按文件名猜的。

- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `analysis/fixtures/a10_map.json` 的 `files[*].n_tensors` / `n_params` / `names_sha`（九个文件全部是 `70d78ea595f9…` 同一个张量名指纹）
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/run_all.py"`（`tensor-set` 一条，打印「张量 866 个、参数 27,320,697,856」）
- 说明：这条同时否掉一个可能的混杂——文件名带 `-mtp` 的两份第三方文件**没有**多出张量，也没有少；它们的张量集合与原生档完全一样。

### protocol-identity :: 五个面板的启动命令**只在 `-m` 的模型路径上不同**：`-c 8192 / -np 1 / -ngl 99 / --jinja`、五个 lmeval 任务名（`mmlu arc_challenge truthfulqa_mc2 gsm8k ifeval`）、`--limit 100`、生成参数 `temperature=0,max_gen_toks=1024`，以及 evalplus 的协议块与版本（`evalplus 0.3.1`、`backend openai-chat`、`greedy true`、`max_new_tokens 768`、`ctx 8192`、`np 1`、`ngl 99`、`reasoning off`）五个面板逐条相同。

- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `.wrapup/mres/{m91-qwen38-27b-q2kxl,m100-qwen38-27b-q3kxl,m152-qwen38-27b-iq4xs,m150-qwen38-gsqrco-iq3xxs,m151-qwen38-gsqrco-iq3s}/{cmd.txt,evalplus.json}`
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/protocol_identity.py"`（退出 0 = 只在模型路径上不同）
- 说明：`.wrapup/mres/*` **不入库**（`.gitignore` 只放行 `*_eval.json`），所以这条检查在干净 clone 里**看不到输入**，此时它退出 **2**（不可得），不是 0。它是本层的前提而不是本层 AC 的载体：`run_all.py` 不依赖它，改由库里 `protocol` 串 + `n_items` 的相等性承担（`position.py` 沿用 `a03` 的逐列协议核对）。

### no-spec :: `-mtp` 不是解码阶段的混杂：五个面板的库里行都是 `spec_type = none`、`spec_draft_n_max = 0`，即没有草稿模型参与。

- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `experiments.sqlite` 的这两列；`analysis/run_all.py` 的 `no-spec` 两条
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/run_all.py"`（`no-spec` 打印 `[('none', '0')]`）
- 说明：与 `tensor-set` 合起来，「-mtp 后缀意味着结构性差异」这个假设被两条独立读数否掉：张量集合相同，且解码时没有用投机草稿。

### fixture-binding :: 本层两条证据的一半在仓库外——分数格在 `experiments.sqlite`（入库），但**有效位宽与逐张量分配来自 `*.gguf` 头**（不入库，单个文件 10–14 GB）——所以九个文件的测量结果冻结成入库夹具 `analysis/fixtures/a10_map.json`（`238d0228…`），每个条目自带推导证据（`n_bytes` / `n_params` / `n_tensors` / 逐类 bits / 逐张量比特指纹）。干净 clone 里 `run_all.py` 不读任何仓库外的文件，因此 36 条断言在那里同样成立。

- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: 夹具 sha256 见本节开头的绑定表；`analysis/build_fixture.py --check` 在本机有源时逐项比对（输出「夹具与源一致」）
- repro: 有源：`python3 "docs/subprojects/a10-第三方量化方案/analysis/build_fixture.py" --check`（退出 0）；**把仓库外的搜索面关掉**：`A10_NO_GGUF=1 python3 ".../build_fixture.py" --check`（退出 **2**，逐条打印「盘上找不到该 gguf」）；同一关断下 `A10_NO_GGUF=1 python3 ".../run_all.py"` 仍退出 **0**（36 条，只用夹具）。干净 clone：`git clone --depth 1 file://$PWD /tmp/a10clone && cd /tmp/a10clone && python3 "docs/subprojects/a10-第三方量化方案/analysis/run_all.py"`（退出 0，36 条）；同一 clone 里 `python3 ".../protocol_identity.py"` 退出 **2**（`.wrapup/mres/*` 不入库）
- 说明：这条是为「看不到输入的检查必须失败」而设的——干净 clone 若恰好跑在这台有 `/home/z/hf` 的机器上，`find_gguf` 会「恰好」成功，把「缺输入退出非 0」变成假绿；`A10_NO_GGUF=1` 就是用来打红它的开关。`--selftest` 的第三条（`A10_NO_GGUF` 之外的三份错误副本）证明断言本身会翻红，两者一起才算「检查有效」。

## 二、位置：第三方档相对原生阶梯（`kind: measured`）

### ladder-own-step :: 本族原生阶梯**不单调**：2.878 → 3.850（Δbpw = +0.971）这一步在 9 列里有 **7 列是负的**——HE −0.0549、HE+ −0.0610、MBPP −0.0185、MBPP+ −0.0238、ARC-c −0.0200、GSM8K −0.0200、IFEval −0.0800，只有 MMLU +0.0329 与 TruthfulQA +0.0500 是正的；第二步 3.850 → 4.173（Δbpw = +0.324）在 8 列上是正的、TruthfulQA 恰好 0.0000。没有一列的两步段斜率都是负的，也没有一列的区间不含 0。

- author: measurement
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/position.py` 的「原生阶梯自己的每一步」块；`analysis/run_all.py` 的 `ladder-own-step` 两条（断言「负的列数 = 7」与「第二步 ≤0 的列数 = 1」）
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/position.py" | head -22`
- 说明：这条不是本层的副产品而是本层结论的一部分——**插值的分母就是它**。用一条在 7 列上往下走的阶梯做线性插值，插值出来的「原生在该位宽应有的分」只能是记账值，不能当预测值。真实含义是：这一族在 2.9–3.9 比特之间的分数变化被单次运行的噪声（±0.06–0.10）盖住了，所以阶梯看起来是平的甚至是波动的。

### position-nearest-xxs :: 第三方 `GSQ-RCO IQ3_XXS`（3.058）对最近原生档 `UD-Q2_K_XL`（2.878，Δbpw = **+0.180**）：九列**全部不可分辨**。点估计是 HE −0.0366 [−0.1014,+0.0272]、HE+ −0.0488 [−0.1222,+0.0244]、MBPP −0.0185 [−0.0653,+0.0282]、MBPP+ −0.0079 [−0.0689,+0.0531]、MMLU +0.0066 [−0.0297,+0.0428]、ARC-c +0.0000 [−0.1329,+0.1329]、TruthfulQA +0.0500（概率质量列，无区间）、GSM8K −0.0400 [−0.1064,+0.0195]、IFEval −0.0100 [−0.1160,+0.0962]；而这一档**多花**的 0.180 比特按位宽尺子本身就值 HE +0.0340 / HE+ +0.0320 / MMLU +0.0195，所以六列的点估计方向（更低）与比特预算的方向（应更高）相反。

- author: measurement
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/position.py` 的第一块；`analysis/run_all.py` 的 `position-nearest: IQ3_XXS 对最近原生档 9 列全部不可分辨`
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/position.py" --bench humaneval-plus`（以及把 `--bench` 换成其余八列）
- 会推翻它：同一对文件在同样协议下重跑出现某列区间不含 0（复现负控未测，见 `gaps`）。
- 说明：「方向相反」不等于「第三方更省」：这七列的区间都跨 0，只能说这一档多花的比特没有换成能读出来的分。

### position-nearest-iq3s :: 第三方 `GSQ-RCO IQ3_S`（3.549）对最近原生档 `UD-Q3_K_XL`（3.850，Δbpw = **−0.301**）：**只有 HumanEval 一列分得开**，Δ = **+0.0671** [+0.0031,+0.1329]（n=164），而这一档**少花** 0.301 比特，按尺子应低 −0.0569 —— 差的方向与比特预算相反，所以这个差**不可能**由比特解释。其余八列跨 0：HE+ +0.0610 [−0.0135,+0.1356]、MBPP +0.0238 [−0.0225,+0.0702]、MBPP+ +0.0265 [−0.0352,+0.0878]、MMLU −0.0088 [−0.0431,+0.0256]、ARC-c +0.0100 [−0.1240,+0.1435]、TruthfulQA −0.0200（无区间）、GSM8K +0.0000 [−0.0632,+0.0632]、IFEval +0.1000 [−0.0114,+0.2091]。

- author: measurement
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/position.py` 的第二块；`analysis/run_all.py` 三条（`只有 HumanEval 一列分得开` / `那一列的差值与区间` / `那一列的比特预算与差反向`）
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/position.py" --bench humaneval`
- 会推翻它：HumanEval 那一格重跑得到跨 0 的区间（复现负控未测）；或该格 `n_items` 变了。
- 说明：HumanEval **基础列**不含 0、HumanEval+ **加强列**含 0（+0.0610 [−0.0135,+0.1356]）。两列来自同一次 evalplus 运行的同一批 164 题，不是两条独立证据；正确读法是「代码面板这一处在分辨力边界上」。

### position-interp :: 相对**插值档**（把第三方位宽夹在两个原生档之间做线性插值）的 18 个格（两档 × 九列，其中 TruthfulQA 两格无区间）**全部不可分辨**，最大点估计是 IFEval +0.0752 [−0.1239,+0.2500]；插值区间是两侧 95% 半宽相加的保守合成。

- author: measurement
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/position.py` 每个档的「插值档」块；`analysis/run_all.py` 的 `position-interp`
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/position.py" | sed -n '/插值档/,$p'`
- 说明：插值只用两个点，残差零自由度，所以这里**不给**插值误差项，改用保守合成（比两比例差区间宽）；因此「跨 0」是保守结论——它跨 0，用更紧的方法也不会变成不跨 0。IQ3_S 的插值还落在**负**段斜率上（见 `ladder-own-step`），所以「插值 = 0.8889 而实测 = 0.9390」不能读成「第三方高于线性预期」。

### multiplicity-36 :: 本层的比较一共 **36 个格**（两档 × {最近原生档, 插值档} × 九列），其中 32 个有区间（TruthfulQA 四格不套二项区间），区间不含 0 的只有 **1 个**（IQ3_S 的 HumanEval）；95% 名义水平下 32 个格期望偶然显著 **1.6** 个。

- author: measurement
- from: result.position-nearest-iq3s, result.position-nearest-xxs, result.position-interp
- scope: general
- status: current
- kind: measured
- evidence: `analysis/run_all.py` 的 `multiplicity` 一条（把它写成断言：36 格 / 32 有区间 / 1 显著）
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/run_all.py" | grep multiplicity`
- 说明：这条决定本层怎么说话——**1/32 与纯偶然同量级**，所以那一列是「值得记下的信号」，不是「第三方方案更好」的证据。

## 三、标签能不能在钉住比特之后存活（`kind: measured` + `kind: analysis`）

### recipe-determinate :: 同一个 tier 标签换上传者、换一套 base 权重之后，逐张量比特分配**完全相同**：`GSQ-RCO-IQ3_XXS` 在 ISTA-DASLab / peculiar-ragdoll（`Dirk-…`）/ huihui-ai（`…-abliterated-…`）手里都是 866 个张量、**0 个张量不同**（指纹 `7784a48204af…`），`IQ3_S` 三处都是 `496d18ace0f3…`；四个副本的文件字节只差 544–20,736 字节（元数据），即张量载荷与类型分配一致。

- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `analysis/fixtures/a10_map.json` 的九个文件条目（`tensor_sha` / `n_bytes`）；`analysis/run_all.py` 的 `recipe-determinate` 四条
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/alloc_a10.py" | tail -8`
- 说明：这条是本轴第二个问题的直接答案的一半——**「GSQ-RCO IQ3_S」不是一个松散的名字，它确定了一套逐张量分配配方**，别的上传者能逐张量复现它（含一套不同的 base 权重）。

### alloc-gap :: 但「同字节」不等于「同分配」：IQ3_XXS 对最近原生档的参数加权 `|Δ|` 是 **0.209 比特/参数**（embed 2.562 vs 2.625、attn 3.000 vs 2.897、ffn-dense 2.952 vs 2.716、output 4.250 vs 4.500、other 3.807 vs 3.420），IQ3_S 对最近原生档是 **0.301**（embed 2.562 vs 3.438、attn 3.511 vs 3.895、ffn-dense 3.506 vs 3.690、output 4.500 vs 5.500、other 4.117 vs 4.368）。两个第三方档都把 **embed 钉在 2.562 比特** 不动，而原生阶梯把 embed 从 2.625 抬到 3.438。

- author: measurement
- from: result.recipe-determinate
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/alloc_a10.py` 的「分配差」块；`analysis/run_all.py` 的 `alloc-gap` 两条；逐类比特由 gguf 头实测（字节 = 相邻张量 `offset` 之差，元素数 = 维度连乘），`alloc-recomputes` 五条验证 `Σ字节×8÷Σ参数` 复现 `bpw_map`（差 ≤0.02）
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/alloc_a10.py" | sed -n '/分配差/,/同一个 tier/p'`
- 说明：这就是 `a03::an4` 那条结论在第三方方案上的形态——**档位标签代理的是分配**。而第三方配方的特征是可以直接读出来的：它把 embed 定死在 2.562 比特，把预算全放在 ffn-dense / attn / other 上。

### no-held-arm :: 本库**不存在**「同字节 + 同分配 + 不同方案」的对照：与任一第三方档 `|Δbpw| ≤ 0.05` 的原生档个数是 **0**，与任一第三方档逐张量比特相同的原生档个数也是 **0**。所以「钉住比特与分配之后方案标签还剩多少」这件事**在本库里测不了**。

- author: measurement
- from: result.alloc-gap, result.position-nearest-xxs, result.position-nearest-iq3s
- scope: general
- status: current
- kind: measured
- evidence: `analysis/run_all.py` 的 `no-held-arm` 两条（打印两个空配对清单）
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/run_all.py" | grep no-held-arm`
- 说明：要做出这一对，需要 `Qwen3.8-27B` 的 f16/bf16 源（≈51 GB）＋ imatrix，按第三方的逐张量类型表重量化出一份「原生方案的权重、第三方的分配」，再跑同一面板。按 `m150` 的实测（代码面板 2,665 s，五个 lmeval 面板另计）估 **≥2 GPU 小时 + 51 GB 磁盘**，超出本层 3% 的 GPU 额度，本层不买（`PLAN.md` 的 GPU 队列有价格与判据）。这是「未测」，不是「没有效应」。

### label-verdict :: 把上面三条合起来：在这个族里，**「方案标签」不是独立于比特与分配的变量，它是「一套逐张量分配配方」的名字**；而「同字节」的第三方档与原生档在分配上差 0.209 / 0.301 比特/参数，所以任何「同字节下第三方更好/更差」的说法，其差里必然混着分配差 —— 要么把它算出来（`alloc-gap`），要么承认测不出（`no-held-arm`）。

- author: agent
- from: result.recipe-determinate, result.alloc-gap, result.no-held-arm
- scope: general
- status: provisional
- kind: analysis
- evidence: 三条 `kind: measured` 事实的机器读数
- repro: 见上三条的 `repro`
- 说明：`provisional` 的理由有两条：(1) 只有一族（`Qwen3.8-27B`）有第三方方案，跨族不可推广；(2) 「分配能改写分数排序」的直接证据在 `a04`/`a01` 的轴上，本层只把分配当混杂变量读。
- 会推翻它：出现一份第三方档与某原生档逐张量比特相同而分数差稳定显著（那时标签就是真变量，且分配不是全部）；或出现第二族的第三方档，且它的 `alloc-gap` 与分数差的关系与这一族相反。

### classifier-blind :: 报告自己的分类器看不见这批文件名：`mktables.split_quant("Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf")` 返回 `(stem, None)`（档位为 `None`），`mktables.scheme_class(...)` 返回 **「原生 K」**；后果在 `report.html` 第十一节的文件表里可见——两个 GSQ 文件的「量化方案」列是 `—`。

- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `analysis/run_all.py` 的 `classifier-blind` 两条；`report.html` 第十一节「用到的模型文件与来源」表（GSQ 两行的量化方案列为 `—`）
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/run_all.py" | grep classifier-blind`
- 说明：这条是**事实**，不是本层的修复项：`mktables.py` 归 i02/meta，本层不改。它的含义是：任何依赖 `family_of`/`scheme_class` 的表格或曲线，都会把第三方档当成「原生 K」并拆成两个独立家族——读报告的人因此看不到「这是一次方案更换」。

## 四、没有匹配对时读者该读出什么（`kind: measured` 的门槛 + 规则）

### resolution :: 这一族上「多小的差才可能读出来」有三道门槛，都在 `position.py` 里现算：①**原生段宽**：2.878→3.850 这一步本身就值 0.971 比特/权重，乘位宽尺子得 HE 0.184 / HE+ 0.173 / MBPP 0.164 / MBPP+ 0.129 / MMLU 0.105 / ARC-c 0.113 / GSM8K 0.194 / IFEval 0.148 —— 也就是说，把第三方档插进这段阶梯，位置本身就有这么大一片不确定区；②**逐格二项半宽**：n=164 时 ±0.076、n=378 时 ±0.050、n=912 时 ±0.032、n=100 时 ±0.096（p=0.5 处取最大，实际格按自己的 p 算）；③**原生阶梯自己的波动**：同一段阶梯上相邻两档的差最大到 −0.0800（IFEval）/−0.0610（HE+），而这些差本身都跨 0。

- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `analysis/position.py` 的「分辨率」块（三列数字在同一屏内）；`analysis/run_all.py` 的 `ladder-own-step` 两条
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/position.py" | sed -n '/分辨率/,/^$/p'`
- 说明：这三道门槛都不依赖第三方方案，它们是这份数据的分辨力上限。

### reader-rule :: 在没有同字节对照的情况下，读者可以下、与不可以下的结论（本层的答复）：

1. **可以下**：「在这个位宽上，第三方档与原生阶梯的差落在 X 以内」，X 取该列的区间宽度（本层 32 个有区间的格全部满足这条）。也可以下更弱但更稳的一条：**第三方档的分数落在相邻两个原生档之间**（IQ3_XXS 有 7 列落在两档之间、TruthfulQA 高于两档、GSM8K 低于两档；IQ3_S 有 4 列高于两档、5 列落在两档之间、0 列低于两档，见 `position.py` 的 `高于两档 / 落在两档之间 / 低于两档` 字段）。
2. **不可以下**：「第三方方案在匹配比特上等于原生」（那要求区间落在 ±0 附近且区间窄于门槛；本层的区间宽 0.10–0.25，比任何可讨论的方案效应都宽）——更不能写成「没有方案红利」，那是把「不可分辨」读成「相等」，与 `a03::res7` 撤回旧措辞时同一个错误。
3. **要写明门槛**：任何小于**该列二项半宽**（或小于**原生段宽 × 尺子**，取两者较大者）的方案效应，在这份数据上都不可能被读出来；`0.971 比特/权重` 这一段阶梯上的差距尤其如此，因为连原生档自己对这一段都给出 7/9 列**负**的段斜率。

- author: agent
- from: result.resolution, result.ladder-own-step, result.multiplicity-36
- scope: general
- status: provisional
- kind: analysis
- evidence: `resolution` 与 `ladder-own-step` 的机器读数
- repro: 见上述两条的 `repro`
- 说明：`provisional` 是因为门槛里的一项（原生段宽 × 尺子）用的是 `a03::pairs.slopes` 的跨族斜率，不是本族的族内斜率；本族三档只有两个段，族内斜率与跨族斜率的差在区间内，但两条斜率谁是那里的真值不可判。
- 会推翻它：补出同字节对照臂后，若该臂的差稳定超过这里的门槛，则第 2 条要改成「可以下」。

## 五、未测与限制（不是 0）

### gaps :: 本层有四处「未测」：①**同字节同分配的对照臂未做**（价格见 `no-held-arm`）；②**MultiPL-E 列没有格**——两个第三方档在 `protocol LIKE 'mpl%'` 上的行数是 **0**，而 60 题的探针本来就不可与 161 题的标准格相比，所以这一轴在代码的多语言侧是空的；③**其它上传者的那四份副本没有分数**（`Dirk-…` 与 `Huihui-…` 只量了分配，库内没有它们的格）；④**复现负控未跑**：每一格只有一次运行，`i01` 的贪心地板是 0 道题（同输入重跑不是噪声来源），但换文件就是换输入，`i01::res29` 的「未记录输入差可致 ±16/161」仍是本层的外部约束。

- author: agent
- scope: general
- status: current
- kind: analysis
- evidence: `analysis/run_all.py` 的 `unmeasured-mpl` 两条（0 行）；`.wrapup/res` 与库内没有 `Dirk-…`/`Huihui-…` 的行；`a03::unmeasured`
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/run_all.py" | grep unmeasured-mpl`
- 说明：四处都不写 0。第②③处尤其要写清楚：空的格子不是 0 分，缺的对照不是「无差」。

### limits :: 本层的结论边界：**只有一族、两个第三方档、九列、每格单次运行**；TruthfulQA 的 `acc` 是概率质量均值，不套二项区间；`ifeval/gsm8k/arc_challenge/truthfulqa_mc2` 是 `limit 100` 的子集，`mmlu` 912、`humaneval*` 164、`mbpp*` 378，这四类 n 不能共用同一个门槛；报告的第十一节只画 7 列（不含 HumanEval 与 MBPP 基础列），而本层算 9 列，所以**本层比报告多出的两列里有一列（HumanEval）是唯一分得开的那一列**。

- author: agent
- from: result.position-nearest-iq3s, result.multiplicity-36
- scope: general
- status: current
- kind: analysis
- evidence: `docs/subprojects/i01-判分与基准有效性/RESULT.md` 的 `res26`–`res29`；`report.html` 第十一节的表头
- repro: 无（这是引用与本层表格的口径说明）

### res13 :: 迁移前的 `res13` 措辞是「第三方方案 GSQ-RCO：固定 Qwen3.8-27B，其两个档（3.058 / 3.549 比特/权重）对原生阶梯（2.878 / 3.850 / 4.173），与『最近原生档』或『按位宽插值后的原生』比较，所有差值的 95% CI 都跨 0」——**这条措辞已撤回**：五个位宽数与「两种比法」的框架由本层复算保住（`panel-size`、`position-nearest-*`、`position-interp`），但「所有差值都跨 0」在最近原生档这一侧**不成立**：IQ3_S 的 HumanEval Δ = +0.0671 [+0.0031,+0.1329] 不含 0。

- author: measurement
- scope: general
- status: retracted
- kind: measured
- evidence: `analysis/run_all.py` 的 `position-nearest: IQ3_S 对最近原生档只有 HumanEval 一列分得开` 与 `那一列的差值与区间`
- repro: `python3 "docs/subprojects/a10-第三方量化方案/analysis/position.py" --bench humaneval`
- retracted: 旧措辞的来源是 `.scratch/originals/L2-结果.md`（已退役），它没有记录区间类型（是否逐题二项）、没有记录 `n_items`、也没有记录它用的是 7 列还是 9 列；用本层装置复算得不到「所有差值都跨 0」。取代它的是 `position-nearest-xxs` / `position-nearest-iq3s` / `position-interp` / `multiplicity` 四条，以及 `label-verdict` 与 `reader-rule` 两条判断。

## 六、给 `report.html` 第十一节的建议文本（`kind: analysis`）

现有第十一节「第三方量化方案（GSQ-RCO）」的四句话逐条给裁决。每条都带否证条件，写进报告时保留。本层不改 `make_report.py`。

1. 现文「GSQ-RCO 的两个量化档（星标）落在原生阶梯（折线）上或附近」——**保留，但要补一句**：折线本身在 2.878→3.850 这一段是**往下走**的（9 列里 7 列为负），所以「落在折线上或附近」在这份数据里几乎不可能不成立。建议改为：「两个第三方档的分数落在相邻两个原生档之间；注意原生折线在这一段本身是平的/波动的（相邻档差最大 −0.080，且全部跨 0），所以『落在折线上』不是一条强证据」。
2. 现文「与『最接近的原生档位』比、与『按有效位宽线性插值后的原生』比，两种比法在所有基准上都测不出差异」——**收窄**。在报告自己的 7 列上这句话成立（本层复算：7 列 × 2 档 = 14 个格全部跨 0）；但本层按 9 列算时，最近原生档一侧的 **HumanEval** 一列不含 0（+0.0671 [+0.0031,+0.1329]，n=164，IQ3_S 对 UD-Q3_K_XL，且该档少花 0.301 比特）。建议改为：「9 列里 32 个有区间的格里 1 个分得开（HumanEval，方向与比特预算相反），按 95% 名义水平这是偶然量级；其余全部测不出」。
3. 现文「结论：GSQ-RCO 是一个中性方案，没有方案级红利」——**改写**。「没有红利」是把「不可分辨」读成「相等」，正是 `a03::res7` 撤回旧措辞时那个错误。建议改为：「本设计测不出方案级红利；能测出的上限是该列的二项半宽（n=164 时 ±0.076、n=378 时 ±0.050、n=912 时 ±0.032），而这一族原生阶梯自己的一步就值 0.971 比特/权重（HE+ 0.173 分），所以小于这个量级的红利不可能被这份数据看见。」否证条件：补出同字节同分配的对照臂后，逐列差不跨 0。
4. 现文「看图要点：两个星点本身的误差棒很长，所以『测不出』有一部分是数据分辨力所限」——**保留，并把它升格为口径**：这句话是对的，且应当写进正文而不是「看图要点」，因为它同时解释了第二条为什么不成立。建议补一句：「分辨力所限的具体数字见上：二项半宽 0.032–0.096，原生段宽 0.105–0.194」。

## 七、给 meta 的一句话

**能支持的决定**：本库没有任何证据支持「换第三方方案能带来可读出的分数红利」，也没有证据支持「第三方方案更差」；唯一可读出的信号是 IQ3_S 在 HumanEval 上比多花 0.301 比特的原生档高 +0.0671（1/32 格，偶然量级）。**要判断「值不值得用第三方」，需要一支同字节 + 同分配的对照臂**（≥2 GPU 小时 + 51 GB 磁盘，本层不买，等 meta 决定）。
