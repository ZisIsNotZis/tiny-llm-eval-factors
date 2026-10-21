# a04 MoE 各层比特分配 — 本目录规则

本文件只写这个 subproject 自己的窄规则；通用法则在仓库根 `AGENTS.md` 与 `/home/z/vibe/AGENTS.md`，不在此复述。
里程碑、工作包、AC、判据与派工在 `PLAN.md`；已成立的事实与证据在 `RESULT.md`；复算装置在 `analysis/`。

## 这个轴的口径（违反一条，结论就作废）

1. **策略 = 张量类别上的比特向量，不是标签名**。字段唯一：`b_exp` = `ffn-expert` 桶的 bits；`b_layer` = **`attn` / `ffn-dense` / `ffn-shexp`** 三个「层上真正驻留」的桶按参数量加权的平均（代码里的 `LAYER_BUCKETS`，规则与代码必须逐字一致）。`|b_exp − b_layer| ≤ 0.5` 记**均匀**，`b_layer − b_exp > 0.5` 记**非专家优先**，`b_exp − b_layer > 0.5` 记**专家优先**。`embed` 与 `other` **不参与**：`embed` 被 K-quant 模板钉在 4.5–8.5（同一族内实测 3.438–8.500），是另一套机制；`other` 是混杂桶。把 `embed` 也算进去，`b_layer` 从「层上比特」变成「含嵌入的混合均值」：`exq4` 由**专家优先**变成**非专家优先**，「专家优先」这一档在 15 个 MoE 文件里归零、全库只剩两个策略（`--definitions` 逐行打印这次翻转），`strategy-counts` 断言随之失效——所以桶定义只能有一份，就是这三个桶。档位名（`Q3_K_M`、`UD-`、`IQ`、`m55-*`）与上传者名都不是策略（`a03::label-audit`）。
2. **两个距离量不许混**：`Δbpw`（总有效位宽差）与 `L1_pw`（参数加权分配距离，比特/参数，定义在 `analysis/profiles.py`）。只有 `L1_pw ≫ |Δbpw|` 才是「分配对照」；`L1_pw ≈ |Δbpw|` 的对照基本只是总比特变了，读它时必须同时给 a03 的比特尺子并把预算部分扣掉。
3. **钉住判据先写死再比**：三档 `|Δbpw| ≤ 0.05 / 0.15 / 0.45`，每条结论必须写明它落在哪一档；跨档不一致就写「只在某档成立」，不许事后挑档。
4. **分配轮廓只有一个来源**：`docs/subprojects/a03-量化方案与厂商/analysis/fixtures/alloc_map.json`（只读，不改它、不存第二份）。本层自建的配方必须另存 `analysis/fixtures/*.json` 并带 `build/check` 漂移检查，仓库外的东西（`.wrapup/mres/*`、`/home/z/hf/*.gguf`）不能成为断言的唯一来源。本层现有两份入库夹具：`alloc_a04.json`（自建臂的轮廓，源是 gguf，`--check` 在有源时比对）与 `pin_feasibility.json`（逐对可等总比特性，两个输入都在仓库里，`--check` 在任何 clone 都成立）；两份都由 `analysis/build_*.py` 生成，**不手改**。
5. **「能不能等总比特」先查清单再判**：任何以「同一总比特下的分配差」为名的结论，必须先对 `analysis/fixtures/pin_feasibility.json` 确认该对是「可等总比特」；判为「不可等」的对只能当预算比较读。上界用 `(1−s_exp)/s_exp × 层间摆动`，它把全部非专家参数都算成可反向摆动，是**宽松**上界——超界即结论成立，不靠松紧。
5. **分数只从 `experiments.sqlite` 的只读连接读**（`file:...?mode=ro`）；要写库必须先编号备份、跑 `checks/db_check.py`、用 `migrate_db.py` 入库——本层不做这三件事，写库需求交给拥有数据的层。
6. **区间用两比例差的 Newcombe method 10**，`n` 取该格自己的 `n_items`；TruthfulQA 的 `acc` 是概率质量均值（`i01::res26`），本层**不把 TruthfulQA 放进策略判定**；`i01::res31` 记 MBPP+ 有 1/378 个任务能被空体拿满。
7. **temp > 0 的比较不作分配判定**：`i01::res32` 实测 temp 0.3 下同一格逐题 Jaccard 0.53–0.67、分数只摆 6/164，分数摆动系统性低估不稳定。本层的格全是 greedy / temp 0。
8. **不池化**：基准之间、语言之间、协议之间不平均；跨族只数同号族数并打印族数（MoE 只有 5 族，别把族数说成样本数）。
9. **先看 `n_items`**：ifeval / gsm8k / arc_challenge 是 `limit 100` 的子集，mmlu 912，humaneval 164，mbpp 378。缺格写「缺」并写原因，不写 0、不写估计。
10. **未测 ≠ 0**：没有钉住总比特的对照就写「语料里没有这个对照」并给出缺的那一臂与它的实测成本，不写「没有效应」。

## 造新配方（`WP4`）的硬约束

1. **只调运行时参数，不改开源项目代码**：`llama-quantize --tensor-type '<正则>=<类型>'` 是这个仓库已在用的机制（`.wrapup/m55_prebuild.sh` 的 `EXRE='ffn_(gate|up|down)_exps'`），专家张量一个正则覆盖，router (`ffn_gate_inp`) 与 attn/短卷积保持 base 类型。
2. **先搜预算再落地**：用 `llama-quantize --dry-run --tensor-type …` 打印的 `quant size` 选 `(base, expert_type)` 组合，使各臂总位宽互相差 ≤0.05；搜索不落盘、不占 GPU。`.wrapup/m55_prebuild.sh` 的 `dry()`/`best()` 就是这套搜索的先例。
3. **源必须是同一套 base 权重**：`LFM2.5-8B-A1B-BF16.gguf`（符号链接，`stat -Lc%s` 读实测字节数，不用 `ls -l`）。引用 `plan6` 的 ~70 GB 时必须标明那是大模型的量级而不是本层实测值。
4. **每臂入库**：新文件的轮廓（逐类 params/bytes/bits）写进 `analysis/fixtures/`，并让 `build` 能从 gguf 头重建、`--check` 能比对；干净 clone 里 `run_all.py` 必须在没有 `.gguf` 的机器上也退出 0。
5. **量到的不只是分数**：每臂记录构建耗时（`llama-quantize` 自报 `quantize time`）与面板耗时（`.timings`），因为 `WP5` 的资源结论要用它们，不用估算。

## GPU 与并发

1. 一次只跑一个面板：`bash .wrapup/gpu_locked.sh bash <脚本>` 持 `/tmp/llama_gpu.lock`；别的仓库的任务也在同一张卡上，**绑定约束是空闲显存不是锁**：起服前看 `nvidia-smi --query-gpu=memory.free` 与 `--query-compute-apps`，按实测需求判断，不按固定阈值。
2. 起服后断言 server 自报的 `n_slots` 与配置相符，不符即该次测量作废（不重试、不改配置凑数）。
3. 面板走既有脚本：`.wrapup/lmeval_panel.sh`（五基准，`--limit` 生效）、`.wrapup/codepanel.sh`（HumanEval 164 + MBPP 378 全量，`limit` 被忽略）。不要为省时间改 `limit` 或跳基准——`n_items` 一变，与库内既有格就不可比。
4. 本层 GPU 额度 7%（4 周周期 ≈2822 分钟）。`WP4` 三臂 ≈90 GPU 分钟，超出这个量级要先回 meta，不自行扩张。

## 与 a01 / a02 / a03 的分工（别越界）

1. **分配轮廓与分类法借 a03**：`analysis/profiles.py` 直接读 a03 的夹具并用它的桶名；a03 改了分类法本层就跟着变（会报错或数字变），不静默用第二套。
2. **不重做别人的测量**：`a01::m55-exq-inversion` 的分数差是 a01 的事实，`a03::alloc-*` 的轮廓解读是 a03 的事实；本层引用它们的数字时必须写明来源，只在它们之上加「策略判定」这一层。
3. **不重建规模曲线**（`a02`）：MoE 的总参与激活参在本库里不可识别，本层不碰规模轴。
4. **不改别的 subproject 目录、不改 `docs/plan/subprojects.md`、不改 `make_report.py`/`mktables.py`/`report.html`**（i02 拥有）。

## 数字纪律

1. 每个数字后面跟证据路径与一条能被别人重跑的命令，缺一不写；跑不出来写「未测」和原因。
2. `.scratch/originals/*` 已退役，那里的数只能标「不可复现」；`res8` 的旧措辞就是这样撤回的（见 `RESULT.md::migrated-res8`）。
3. 复用 `.wrapup/mres/*` 前先确认它是哪个 `run_tag` 的产物、当时的 `np`/`ctx`/协议串；不确定就当未知。
4. 结论必须指回 `PLAN.md` 的某条 AC；说不清服务哪条的工作不做。
