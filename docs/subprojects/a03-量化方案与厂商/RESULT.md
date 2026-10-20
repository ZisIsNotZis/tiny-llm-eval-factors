# a03 量化方案与厂商 — 结果

每条事实一行一个陈述；有数字就必须跟证据路径与一条能重算出它的命令，没有命令的数字不写（`@falsifiable`）。
未测写「未测」并写原因，不写 0。状态：`current` 为当前值，`provisional` 为暂时，`retracted` 为已撤回但保留其死因。
测量（`kind: measured`）与分析（`kind: analysis`）分开写，analysis 不覆盖任何数字。

## 证据绑定（读这一层之前先看这里）

本层的数字只由四个入库产物的内容决定，绑定到它们的 sha256：

| 产物 | sha256 | 作用 |
|---|---|---|
| `experiments.sqlite` | `885383dc86e3eff3ae35e5393618eca33dbc7a46925e0ca42b78406a3cfa7bd8` | 全部分数格 |
| `.wrapup/bpw_map.json` | `4f490813cf5fd45caf608fae91cfd37b9648cddc1c8ef05fc54e5e4b94b2dacf` | 有效位宽 |
| `analysis/fixtures/vendor_map.json` | `2af86ab237b500811c927a006a37d2a0e174e18dde4c82e7f812cb4fd9220662` | 来源（厂商/上传者）证据 |
| `analysis/fixtures/alloc_map.json` | `139209a974c0e9a81a20956c1ecb828883a2f2631d03e83bf2ea23a7f129705e` | 比特分配轮廓 |

代码 revision 用一条能解析的命令读，不在正文里写死（写死的 revision 必然落后）：
`git log -1 --format=%H -- "docs/subprojects/a03-量化方案与厂商"`。
`experiments.sqlite` 由多个子项目并发写入，所以**任何一条事实是否仍然成立，用 `analysis/run_all.py` 判定**：
22 条预期逐条成立时本层的事实全部复核通过。

复算装置：`analysis/pairs.py`（同字节配对 + 区间）、`analysis/attrib.py`（方案/来源归因 + 识别来源与探测下限）、
`analysis/alloc.py`（从 gguf 头读实测比特分配轮廓）、`analysis/build_fixtures.py`（重建/核对两份入库夹具）、
`analysis/run_all.py`（全部检查，退出码即结论）。本层**只读** `experiments.sqlite`，不写库、不改 `report.html`、
不加载权重、不占 GPU。

本层全部配对都是**单次运行**：区间只含逐题二项项（同一格的多行取 `n_items` 最大者，`pairs.py` 会打印 101 处），
**不含跨 run 项**。`i01::res29` 记录未记录的输入差能移动一格 ±16/161（≈0.10），所以本层任何小于 0.05 的差
只能说「测不出」，不能说「相等」；复现负控（同格重跑）**未测**，见 `PLAN.md` 的 GPU 队列。

## 一、配对装置与总体（`kind: measured`）

### population :: 进入本层分析的是 66 个有有效位宽、且有标准面板格的文件，分属 30 个族；来源按面板写入的模型路径分成 unsloth 47 / prism-ml 5 / bartowski 3 / ibm-granite 3 / local 3 / ornith-ai 2 / ISTA-DASLab 2 / Manojb 1（合计 66，每个文件恰好一个有证据的来源，没有不可归因的行），量化族按文件名分成 K 54 / IQ 6 / TQ 1 / 其它 5。
- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `analysis/fixtures/vendor_map.json` 的 `models`（每个文件带 `paths: {run_tag: 模型绝对路径}`，来源由路径按 `mscache/<vendor>/…`、`models--<vendor>--…`、`/home/z/hf/*.gguf → local` 三条规则抽出）；面板元数据本身不入库，夹具是它的冻结版，重建与漂移检查见 `build_fixtures.py`
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --inventory`；`python3 "docs/subprojects/a03-量化方案与厂商/analysis/build_fixtures.py" --check`
- 说明：**IQ 文件只有 6 个、只落在 3 个族里**（Qwen3.5-2B 三个、Qwen3.5-4B 一个、Qwen3.8-27B 一个），这是本轴识别「方案」的全部证据量。

### pair-device :: 在匹配字节的三档判据下，族内配对分别是 |Δbpw| ≤ 0.45 → 10 对、≤ 0.15 → 4 对、≤ 0.05 → 2 对，且≤0.05 的两对正好是本轴的两条 AC 各自的最小样本（Qwen3.5-4B 的方案对 Δ=+0.016、Qwen3.6-35B-A3B 的厂商对 Δ=+0.025）；四对在 ≤0.15 档里逐基准的 `protocol / n_items / ctx_size / parallel_slots / temp / reasoning` 全部相等，没有一格判「不可比」。
- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `analysis/pairs.py --bound {0.45,0.15,0.05}` 的配对清单与逐格协议比对
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --bound 0.05`（以及把 `--bound` 换成 0.15 / 0.45）
- 说明：≤0.45 那 10 对里 4 对只变比特预算、3 对只变方案、1 对只变来源、2 对同时变来源与方案。

### slopes :: 同族内每 +1 比特/权重的分数变化（`score ~ bpw + C(family)` 的 OLS 斜率）是 HE +0.1894 [+0.1135,+0.2654]、HE+ +0.1779 [+0.1053,+0.2505]、MBPP +0.1689 [+0.1001,+0.2378]、MBPP+ +0.1329 [+0.0754,+0.1904]、MMLU +0.1084 [+0.0582,+0.1587]、ARC-c +0.1160 [+0.0878,+0.1441]、TruthfulQA +0.0383 [+0.0025,+0.0740]、GSM8K +0.2000 [+0.1141,+0.2859]、IFEval +0.1522 [+0.0965,+0.2079]（每列 58–65 格）。
- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: `analysis/pairs.py --slopes`
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --slopes`
- 说明：这是本层判「比特预算能买多少分」的尺子。报告的 `MATCH_BPW = 0.45` 等于允许组内先有 0.45×0.1779 ≈ **0.080** 的 HumanEval+ 分差（GSM8K 0.090、MBPP+ 0.060），与本轴要检的方案差同量级；`≤0.05` 那一档的预算上限只有 0.0089（HumanEval+），所以那一档的差不可能由比特解释。这里给的是 `pairs.py --slopes` 的独立斜率；`attrib.py` 里同一个量作为系数是 HE+ +0.1863（多了两个标签哑变量），两者在区间内一致；TruthfulQA 的 `acc` 是概率质量均值（`i01::res26`），它的斜率只作参照、不作判断。

### fixtures :: 本层有两条结论依赖仓库外的东西——来源（面板元数据里的模型路径，`.wrapup/mres/*` 不入库）与比特分配（gguf 头，`*.gguf` 不入库）——所以它们各自被冻结成入库夹具 `analysis/fixtures/vendor_map.json`（66 个有证据的文件，每个带 `paths: {run_tag: 绝对路径}`）与 `analysis/fixtures/alloc_map.json`（51 个文件的实测轮廓：参数数、文件字节、逐类 bits/参数）；干净 clone 里 `run_all.py` 不读任何仓库外文件，因此 22 条断言在那里同样成立。
- author: measurement
- scope: general
- status: current
- kind: measured
- evidence: 两个夹具的 sha256 见本节开头的绑定表；重建与漂移检查 `analysis/build_fixtures.py --check`（本机有源时逐模型比对，输出 `[ok] … 与源一致`）
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/build_fixtures.py" --check`（有源的机器上做漂移检查）；干净 clone 证明：`git clone --depth 1 file://$PWD /tmp/a03clone && cd /tmp/a03clone && python3 "docs/subprojects/a03-量化方案与厂商/analysis/run_all.py"`（退出 0，22 条）；再把仓库外源一并断掉也退出 0：`python3 -c "import sys;sys.path.insert(0,'docs/subprojects/a03-量化方案与厂商/analysis');import alloc;alloc.find_path=lambda n:None;import run_all;sys.exit(run_all.main(()))"`
- 说明：这条是为修一条复核阻塞项而生的——上一版 `run_all.py` 直接扫 `.wrapup/mres/*/*.json`，而 `.gitignore` 把那个目录排除了（只放行 `*_eval.json`），于是干净 clone 里来源全丢、「跨上传者受控对」与两个系数的九列检查全部 FAIL。判据是：**承载断言的证据必须随仓库走**；能重建的（分配轮廓）用生成器 + 漂移检查，不能重建的（面板元数据）用带证据行的冻结夹具。

## 二、方案差（IQ 系列 vs K 系列，同厂商内、同字节）

### scheme-4b :: 字节几乎相同的唯一一对方案对照——Qwen3.5-4B 的 UD-Q2_K_XL（3.692）对 UD-IQ3_XXS（3.707，Δbpw = +0.016）——只有 MMLU 分得开：+0.0592 [+0.0170, +0.1011]（912 题，IQ 一侧更高）；其余七列全部跨 0（HE +0.0000、HE+ +0.0061 [−0.0936,+0.1057]、MBPP −0.0079、MBPP+ +0.0106、ARC-c +0.0500 [−0.0871,+0.1845]、TruthfulQA −0.0034 无区间、IFEval +0.0900 [−0.0338,+0.2102]）；该族在这一协议下没有 GSM8K 格（缺，不是 0）。
- author: measurement
- from: result.pair-device
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/pairs.py --bound 0.05`（该对的九列与各格 `n_items`）；两文件同一来源（unsloth）、同一 base 权重
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --bound 0.05`
- 会推翻它：同一对文件在同样协议下重跑出现与 0.0592 相反的 MMLU 差，或该格 `n_items` 变了。

### scheme-2b :: Qwen3.5-2B 的方案对照（UD-IQ3_XXS 3.961 → UD-Q2_K_XL 4.109，Δbpw = +0.148）在 HumanEval 与 HumanEval+ 上方向相反于比特预算：两列都是 −0.1341（IQ 一侧更高），区间 [−0.2317,−0.0329] 与 [−0.2303,−0.0345]，各 22 题；其余七列跨 0（MBPP +0.0265、MBPP+ −0.0132、MMLU −0.0099 [−0.0554,+0.0357]、ARC-c −0.0100、TruthfulQA −0.0090 无区间、GSM8K −0.0800 [−0.2134,+0.0576]、IFEval −0.1000 [−0.2321,+0.0373]）。
- author: measurement
- from: result.pair-device
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/pairs.py --bound 0.15`；判分通道已由 `a01::t2-channel-excluded` 排除（两格完成物围栏率相同、无 timeout、分数低的那格 sanitize 后更干净）
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --bound 0.15`
- 说明：GSM8K 与 IFEval 的 −0.08 / −0.10 是「测不出」而不是「没有差」：两列各 100 题，要分开 8–10 个百分点大约需要每列 400+ 题。这条与 `a01::b1-heplus-only` 是同一组数，本层不重复其结论，只把它放进方案轴的口径里读。
- 会推翻它：同配置重跑该格得到与 −0.1341 差 0.05 以上的值（复现负控未测，见 `PLAN.md`）。

### scheme-27b :: Qwen3.8-27B 的方案对照（UD-Q3_K_XL 3.850 → UD-IQ4_XS 4.173，Δbpw = +0.324）九列全部跨 0，最大点估计是 HE+ +0.0366 [−0.0407,+0.1138]；这一对的比特预算就已经值 0.324×0.1779 ≈ 0.058（HumanEval+），所以它不是一对「同字节」对照。
- author: measurement
- from: result.pair-device
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/pairs.py --bound 0.45`
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --bound 0.45`
- 说明：把这一对算进「方案差」时必须写明 Δbpw = +0.324；它只能支持「方向上 IQ4_XS 不差于 Q3_K_XL」，不能支持大小。

## 三、来源（厂商 / 上传者）差

### vendor-qwen36 :: 唯一一对跨上传者、同尺寸、同协议的受控对照是 Qwen3.6-35B-A3B：bartowski 的 `Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf`（3.857）对 unsloth 的 `Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf`（3.882，Δbpw = +0.025），九列全部跨 0——HE −0.0061、HE+ −0.0061 [−0.0775,+0.0653]、MBPP −0.0159、MBPP+ −0.0159、MMLU −0.0022 [−0.0355,+0.0311]、ARC-c −0.0500 [−0.1823,+0.0848]、GSM8K +0.0100、IFEval −0.0100、TruthfulQA +0.0241（无区间）。
- author: measurement
- from: result.pair-device
- scope: specific
- status: current
- kind: measured
- evidence: `.wrapup/mres/{m101-qwen36-35b-a3b-q3km,m103-qwen36-35b-a3b-q3kxl}/` 的 `evalplus.json`（同 `protocol` 串：`temperature 0.0, greedy, ctx 8192, np 1, reasoning off`）与 `cmd.txt`（逐条相同：同 shim、`max_length=8192`、`--limit 100`）；两文件同在 `bpw_map.json`、参数量同为 35,505,251,456
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --bound 0.05`
- 说明：这是本轴 AC 里「至少一个跨供应商同尺寸受控对」的那一对。它**同时**换了方案（UD 动态分配 vs 均匀 Q3_K_M），所以它约束的是「上传者 + 分配这一整包改变」的上限，不能单独归因给上传者；把两件事分开需要一对同分配、不同上传者的文件，本库没有（`attrib` 打印的识别族计数就是这件事的机械证据）。
- 会推翻它：同一对文件重跑出现某一列 >0.05 且区间不含 0 的差（复现负控未测）。

### vendor-lfm :: 同族、跨来源的两对（unsloth 的 UD 动态 vs 本仓自建的 m55 配方）里，Δbpw = +0.154 的那一对有三列分得开且方向不一致——MBPP −0.1032 [−0.1716,−0.0334]、MBPP+ −0.0767 [−0.1444,−0.0080]（本仓配方更低），MMLU +0.1140 [+0.0698,+0.1576]（本仓配方更高）；ARC-c +0.0800 [−0.0560,+0.2119] 与其余列跨 0；Δbpw = +0.099 的那一对九列全部跨 0（最大 IFEval +0.1000 [−0.0379,+0.2326]）。
- author: measurement
- from: result.pair-device
- scope: specific
- status: current
- kind: measured
- evidence: `analysis/pairs.py --bound 0.15`；文件路径 `/home/z/hf/LFM2.5-8B-A1B-m55-*.gguf`（本仓自建）与 `/home/z/hf/mscache/unsloth/LFM2.5-8B-A1B-GGUF/*`
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --bound 0.45`（Δ=0.154 那一对超出 0.15 判据，只在 0.45 档打印；Δ=0.099 那一对在 0.15 档也打印）
- 说明：「来源」在这里等于「本仓自己的分配配方」，`alloc-m55` 给出这两份文件的分配差有多大；所以这一对不能读成厂商效应。

### attrib :: 同族 + 同比特预算 + 族固定效应下，三个标签系数在 9 个基准上**全部跨 0，且这个「跨 0」得按各自的半宽读**：IQ 效应逐基准半宽 0.104–0.273、**逐基准最大 0.27**（由 Qwen3.5-2B / Qwen3.5-4B / Qwen3.8-27B 三族、6 个 IQ 文件里的 5 个识别）、本仓 `local` 配方逐基准 0.158–0.366、**最大 0.37**（只由 LFM2.5-8B-A1B 一族识别）、`bartowski` 逐基准 0.212–0.489、**最大 0.49**（只由 Qwen3.6-35B-A3B 一族识别）；唯一九列都不含 0 的是位宽斜率（+0.1152 至 +0.2042，20 个族有族内位宽差）。所以正确说法是**本设计探测不到各自半宽以内的效应**，不是「没有效应」。
- author: measurement
- from: result.slopes
- scope: general
- status: current
- kind: measured
- evidence: `analysis/attrib.py` 的逐基准系数 + 「识别来源与探测下限」汇总块（每个系数打印识别基准数、识别族、95% 半宽范围与点估计方向）；`其他来源` 哑变量因「没有任何族同时含两个取值」被判不可识别并从模型剔除；来源不可归因的行（`ambiguous`/`unknown`）不进回归并在同一块打印
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/attrib.py"`（末尾打印「逐基准最大半宽（探测下限，文档与报告只引这一组）」一行，本段引的就是它）
- 口径：半宽 = 该列自己的 95% 半宽（1.96·se）；**引一个数时引逐基准最大**（IQ 0.27 / local 0.37 / bartowski 0.49），它是探测下限的最小值，**不是** 9 列同时成立的联合区间。改口径要同时改脚本那一行与本段，否则又是同一个事实两个数。
- 说明：`bartowski` 系数**不能当厂商效应读**——它由单对识别、又拿汇总斜率外推，逐基准比符号有 3/9 列与它唯一来源的那一对相反（ARC-c、TQA、GSM8K），属外推假象；厂商结论因此由逐对区间承担（`vendor-qwen36`，那一对逐列半宽 0.019–0.134）。脚本每次运行都打印这个翻转计数，`run_all.py` 把它作为一条断言。
- 会推翻它：出现第二个同族跨来源对后 `bartowski`/`local` 系数的区间不含 0；或 IQ 文件补到能给出更窄区间的族。

### label-audit :: 文件名里的厂商/方案标签不可靠，实测反例是 `Phi-4-mini-instruct-Q2_K.gguf` 与 `Llama-3.2-3B-Instruct-Q3_K_M.gguf`：两者都没有 `UD-` 前缀（`mktables.scheme_class` 会把它们判成「原生 K」），但面板记录的实际来源是 `mscache/unsloth/…`。
- author: measurement
- from: result.population
- scope: general
- status: current
- kind: measured
- evidence: `analysis/pairs.py --inventory` 的 vendor 列；`.wrapup/mres/m115-phi4mini-q2k/evalplus.json` 与 `m107-llama32-3b-q3km/evalplus.json` 的 `model` 字段
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --inventory`
- 说明：所以「厂商」不能从档位名推；`UD-` 前缀说明的是上传者的**配方**（动态分配），不是来源。`mktables.scheme_class` 用它把曲线拆系列是合理的目的（同一个族不混两种分配），但它产出的名字**不是**厂商。

## 四、比特分配：标签到底代理了什么（`kind: measured`）

### alloc-qwen36 :: 那对跨上传者的文件总位宽只差 0.025 比特/参数，分配轮廓却差到参数加权平均 0.381 比特/参数：unsloth 的 UD-Q3_K_XL 把 attn 放到 8.500、embed 8.500、专家 3.542，bartowski 的 Q3_K_M 是 attn 4.936、embed 3.438、专家 3.734。分层看：`attn`（4.936 vs 8.500）与 `embed`（3.438 vs 8.500）是**纯桶**，差是真的；`ffn-shexp`（共享专家，占 0.4% 参数）是 7.053 vs 8.515；`router` 是 31.610 对 31.610（f32，两边完全相同）；`ffn-dense` 这一桶在这两个 MoE 文件里是空的——先前版本写的「稠密 FFN 11.812 vs 10.559」是把共享专家与 router 混进同一桶造成的假象，已随 `tensor_class` 拆桶（`_exps` / `_shexp` / `ffn_gate_inp` / 其余）修正。
- author: measurement
- from: result.vendor-qwen36
- scope: specific
- status: current
- kind: measured
- evidence: `.wrapup/mres/{m101,m103}/…gguf` 实测；逐张量元素数与字节数取自 gguf 张量信息段（字节数 = 相邻张量 offset 之差，末张量到文件尾），校验 `Σ字节×8 ÷ Σ参数` 复现 `bpw_map.json` 的值（3.855 vs 3.857、3.879 vs 3.882）
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/alloc.py" --pair bartowski`
- 说明：这条是「厂商标签是分配的代理」的直接度量——标签不同对应的是**大得多的分配差**（0.025 → 0.381 比特/参数），而九列分数差都落在各自半宽（0.019–0.134）以内。

### alloc-scheme :: 两对方案对照在总位宽几乎相同的情况下也各自带着大分配差：Qwen3.5-4B（Δbpw +0.016）的参数加权平均 |Δ| = 0.337 比特/参数（embed 5.500 vs 6.562、attn 3.039 vs 2.849、稠密 FFN 3.124 vs 3.016），Qwen3.5-2B（Δbpw +0.148）是 0.427（embed 5.500 vs 6.562、attn 3.047 vs 2.808）。
- author: measurement
- from: result.scheme-4b
- scope: specific
- status: current
- kind: measured
- evidence: 两文件同参数量（4,205,751,296 / 1,881,825,088），逐类比特/参数来自 gguf 头测量
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/alloc.py" --pair unsloth/unsloth`
- 说明：所以「IQ vs K」不是一个纯机制开关，它本身也是**一种分配约定**：IQ 侧把比特从 embed 挪到 attn/FFN。这解释为什么它的效应只落在少数几格：换的不是一个开关，而是每类层各挪了 0.19–1.06 比特。至于是不是「没有水平位移」，本层只能说到不可分辨（见 `attrib` 的半宽）。

### alloc-m55 :: 同一套 base 权重的两条自建配方把这件事推到极端：m55-exq4（4.483 比特/权重）是专家 4.500 / attn 3.031 / 稠密 FFN 3.365，m55-exq2（2.918）是专家 2.625 / attn 5.535 / 稠密 FFN 6.275——总比特多 1.565 的那份把非专家层压掉 2–3 比特，而 `a01::m55-exq-inversion` 已测它在四个基准上显著更低。
- author: measurement
- from: result.alloc-scheme
- scope: specific
- status: current
- kind: measured
- evidence: `/home/z/hf/LFM2.5-8B-A1B-m55-exq{2,4}.gguf` 实测轮廓；分数见 `a01` 的 `m55-exq-inversion`（本层不重复该测量）
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/alloc.py" /home/z/hf/LFM2.5-8B-A1B-m55-exq2.gguf /home/z/hf/LFM2.5-8B-A1B-m55-exq4.gguf`
- 说明：这是按指令要「解释而不是重复」的那条线索在本轴上的读法——`exq2`/`exq4` 是**分配标签**，不是方案名或厂商名；总比特不能给质量排序，因为比特放在哪里会改写排序。策略本身的结论归 `a04`。

### multiplicity :: 在 ≤0.15 档打印的 4 对 × 各列共 **35 个格**（Qwen3.5-4B 那一对没有 GSM8K 格），其中 **31 个有区间**（4 个 TruthfulQA 是概率质量均值、不套二项区间），区间不含 0 的只有 **3 个**（Qwen3.5-2B 的 HE 与 HE+、Qwen3.5-4B 的 MMLU），即 **3/31 = 9.7%**——在 95% 名义水平下这个命中率与纯偶然同量级。
- author: measurement
- from: result.scheme-2b, result.scheme-4b
- scope: general
- status: current
- kind: measured
- evidence: `analysis/pairs.py --bound 0.15` 的逐格区间；`analysis/run_all.py` 的 `multiplicity` 一条把这三个数写成断言
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --bound 0.15`
- 说明：这条决定本层怎么说话：匹配字节下能分得开的格是**少数派且逐格独立**，本设计的功效不足以判定是否存在一个跨族一致的水平位移；「同一对内部方向相反」的例子在 Δ=0.154 的 LFM 那一对（`vendor-lfm`），它只在 `--bound 0.45` 下打印。

## 五、本轴的两条总结事实（写入 meta 层的 `res7` / `an4` 位置）

### res7 :: 同字节下换量化方案（IQ 系列 vs K 系列）或换上传者，**在本设计下都不可分辨**（undetermined at this precision）：把家族与比特预算固定住后，三个标签系数的区间在 9 个基准上全部跨 0，而它们的逐基准半宽是 IQ 0.104–0.273（最大 0.27）、本仓 `local` 配方 0.158–0.366（最大 0.37）、`bartowski`（厂商，单族识别）0.212–0.489（最大 0.49）——也就是说这两种标签的效应用这份数据只能排除到「大于上述半宽」，不能排除「不存在」。逐对比较里区间不含 0 的只有 3/31 格（Qwen3.5-2B 的 HE/HE+ −0.1341、Qwen3.5-4B 的 MMLU +0.0592），唯一跨上传者受控对（Qwen3.6-35B-A3B，Δbpw +0.025，逐列半宽 0.019–0.134）九列全部跨 0。
- author: measurement
- from: result.attrib, result.multiplicity, result.scheme-4b, result.vendor-qwen36
- scope: general
- status: current
- kind: measured
- evidence: `analysis/attrib.py`（系数 + 识别族 + 半宽）、`analysis/pairs.py`（逐对区间）
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/attrib.py"`；`python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --bound 0.05`
- retracted: 迁移前 `res7` 的措辞「换方案分数有差，合并约 +0.056（95% CI [+0.008,+0.104]）；换厂商标签测不出差异（约 +0.009，95% CI [−0.058,+0.077]）」撤回——它的 origin `.scratch/originals/L2-结果.md` 已退役、区间类型（是否逐题二项、是否跨族合并）没有记录，用本层装置复算得不到这两个数；且「测不出差异」是无区间的断言，现在改成有半宽的「不可分辨」。
- 说明：旧措辞与本条的差别就是这次复核的要害——「测不出」被读成「不存在」。本条把功效写进结论：要判厂商效应，至少要有第二个同族跨来源对，把 `bartowski` 半宽压到 0.1 以下。
- 会推翻它：补出第二个跨上传者同分配对照后系数区间不含 0；或 IQ 文件补到能给出更窄区间；或复现负控显示单次运行的抖动大于 0.05。

### an4 :: 「换方案 / 换厂商」这两个标签在本库里都不是独立于比特预算的变量，它们代理的是**比特分配**：总位宽几乎相同的配对里，实测分配轮廓相差 0.337–0.427 比特/参数（`alloc-qwen36`、`alloc-scheme`），而分数差在这些配对上测不出（`res7`）；相反，把分配推到极端的自建配方（`alloc-m55`）能改写排序。所以挑量化文件该比的是「字节 + 比特落在哪类层上」，不是档位名、不是厂商名。**但这不是「标签无效」**：本设计只能把标签效应排除到各自半宽（逐基准最大：厂商 0.49、方案 0.27、本仓配方 0.37），要断言「厂商标签没有作用」需要更强设计。
- author: agent
- from: result.res7, result.alloc-qwen36, result.alloc-scheme, result.alloc-m55, result.label-audit
- scope: general
- status: provisional
- kind: analysis
- evidence: 四条 `kind: measured` 事实的机器读数
- repro: 见 `res7` 的复算命令；分配轮廓见 `alloc.py` 与 `analysis/fixtures/alloc_map.json`
- 说明：`provisional` 的理由有两条：跨上传者对照只有一族（Qwen3.6-35B-A3B），且该族的厂商系数符号与逐对差相反；「分配能改写排序」的直接证据来自自建配方（a04 的轴），本层只把它当混杂变量读。「比特分配」这个机制本身归 `a04`。
- 会推翻它：找到一对同分配、不同上传者的文件并测出显著的分数差（那时厂商就是真变量）；或找到一对分配轮廓差 ≥0.3 比特/参数、总位宽相同而分数差稳定出现的配对（那时标签代理的是分配且分配有效，本条的第二步要改写）。

## 六、报告第三节的 § 组口径（`kind: measured`）

### cluster-2b :: 报告第三节用 `MATCH_BPW = 0.45` 的单链聚类分组，Qwen3.5-2B 那一组因此从 3.266 拉到 4.109（跨度 0.843 比特/权重，四个文件：IQ2_XXS 3.266、IQ2_M 3.655、IQ3_XXS 3.961、Q2_K_XL 4.109），同组 HumanEval+ 从 0.0366 升到 0.3720——按本层的位宽尺子（HE+ +0.1779/比特）这 0.843 比特本身就值 0.150 分，占那 0.335 实跳的 45%，即组内排名大半是比特预算的排名，不是方案标签的排名。
- author: measurement
- from: result.slopes, result.scheme-2b
- scope: specific
- status: current
- kind: measured
- evidence: `.wrapup/bpw_map.json` 的四个位宽 + `experiments.sqlite` 对应格的 `humaneval-plus`
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --bound 0.45`（该组内的三对都在清单里：IQ2_XXS→IQ2_M、IQ2_M→IQ3_XXS、IQ3_XXS→Q2_K_XL）与 `python3 "docs/subprojects/a03-量化方案与厂商/analysis/run_all.py"`（`cluster-2b` 那一条断言簇宽 0.80–0.90 且预算部分 >0.10）
- 说明：「IQ2_XXS 在该组明显垫底」这个可观察事实是对的，但把它读成「换方案分数会变」不成立：它同时也是位宽最低的那份。真正在匹配字节上的那一步（IQ3_XXS→Q2_K_XL，Δ0.148）恰好是反方向的那一步（`scheme-2b`）。

## 七、未测与限制（不是 0）

### unmeasured :: 复现负控未测：本层所有配对都是单次运行，同一格在相同协议下重跑是否复现入库值没有测（GPU 排队，见 `PLAN.md`）；跨 run 项的噪声仍是未知量，因此本层不能声明任何 <0.05 的差为「无差」，只能说「测不出」。
- author: agent
- scope: general
- status: current
- kind: analysis
- evidence: 库里每个 (文件, 基准) 的规范协议格只有一次运行（`pairs.py` 末尾打印的 101 处「同格多行」都是别的轴的面板，不是同配置重复）；`i01::res25` 只对 MultiPL-E 的一格证明了贪心逐字节可复现，不覆盖本层的 9 列
- repro: `python3 "docs/subprojects/a03-量化方案与厂商/analysis/pairs.py" --slopes`（该命令同时打印“同格多行”清单）
- 说明：`i01::res29` 给的是「未记录的输入差」量级（±16/161）；本层的配对都来自同一脚本、同一协议串，输入差的风险因此更低，但**没有测过**。

### channel-notes :: 本层引用九列时的通道状态：HumanEval+/MBPP+ 不后处理（`i01::res27` 起的一组审计）、GSM8K 取最后一个数字（`flexible-extract`）、IFEval 有约 9 分地板、MMLU/ARC 的似然打平静默取下标 0、TruthfulQA 的 `acc` 是概率质量均值因而**不套二项区间**（`i01::res26`）。
- author: agent
- from: result.unmeasured
- scope: general
- status: current
- kind: analysis
- evidence: `docs/subprojects/i01-判分与基准有效性/RESULT.md` 的 `res26`–`res28`
- repro: 无（这是引用，不是本层的测量）
