# FINDINGS

路由文件：每条结论只写「它是什么 + 事实落在哪个节点 + 当前状态」。数值、证据、置信区间与复算命令都在被指的节点里，本文件不复制，也不写 `文件:行`（行号随修订漂移）。`::` 后面是节点 id，路径给出唯一 home；节点 id 的作用域是文件（同一 id 在不同文件里是两条事实），解析器是 `checks/router_refs.py`。

口径纪律：未知 / 阻塞 / 未测必须与 0 或负结果区分；下表「部分」多数就是这一类。状态列写这条结论现在该怎么读，依据是所引节点自己的 `status` / `状态` 行：`current` 写成立，`provisional` 写部分，`retracted` 写已撤回，节点没有状态行的写未核实并点名。节点写 `current` 而正文撤回这条事实的一部分、或只裁决了它的一部分时，单元格按现在的读法写部分 / 已撤回，并在括注里点名承载那次撤回或那一半的节点与字段——这类节点的 status 行不带撤回，所以括注只指到那一格，不复制 status 的值。

## 一、测量结论（`author: measurement`、`kind: measured`/`citation`）

| 结论 | 事实所在 | 状态 |
| --- | --- | --- |
| 权重量化位宽：同一家族内从低一档到高一档，多数情况下分数上升，但每一列都有反例（原措辞「普遍上升」已按节点收窄） | `docs/subprojects/a01-量化位宽/RESULT.md::res1` | 成立 |
| Qwen3.5-2B 的多语言代码必须按语言分开读，原跨语言池化列已撤回 | `docs/subprojects/a01-量化位宽/RESULT.md::res5` | 成立（`scope: specific`） |
| 模型规模：同配方下参数量越大分数越高，小模型之间的差距通常更大；但本层仍没有独立于报告生成器的复算，且已知同配方反例 | `docs/subprojects/a02-模型规模/RESULT.md::res6` | 部分（`provisional`） |
| 同字节下换量化方案或换厂商标签在本设计下都不可分辨，标签是比特分配的代理；旧措辞「换方案有可测差异」已在该节点标为撤回 | `docs/subprojects/a03-量化方案与厂商/RESULT.md::res7` | 成立 |
| KV 缓存精度：短上下文改变个别题的判定，净值双向且方向不单调；长上下文由针检索覆盖到受测上限，未观察到差异 | `docs/subprojects/a05-KV 缓存精度/RESULT.md::kv-short-panel`、`docs/subprojects/a05-KV 缓存精度/RESULT.md::kv-long-ctx-needle` | 成立（旧措辞「短上下文无可测差异」已撤，理由在 `docs/subprojects/a05-KV 缓存精度/RESULT.md::kv-short-wording`） |
| 采样 / 解码：温度抬高压低代码通过率；`top_k` 只在温度为零时惰性；MMLU 对采样完全无反应 | `docs/subprojects/a06-采样与解码参数/RESULT.md::res10` | 成立 |
| 投机解码：草稿深度换速度，但既不是单调、也不是到处成立；输出与不开投机不逐字节相同，MMLU 逐位相同是结构事实而不是质量证据 | `docs/subprojects/a07-投机解码/RESULT.md::res11` | 未核实（`docs/subprojects/a07-投机解码/RESULT.md` 的节点没有 status 行） |
| 规模盘点（引用，非测量；随入库变化） | `docs/subprojects/i02-测量基础设施/RESULT.md::res15` | 成立（`kind: citation`） |

## 二、负结果（看起来合理的设计在这里输了 / 测不出差异）

| 结论 | 事实所在 | 状态 |
| --- | --- | --- |
| MoE 逐层比特分配：钉住总比特后均匀优于专家优先，但那是单个对照且对手是已知病态臂；「比特最多最差」那三点的差不能归因给分配 | `docs/subprojects/a04-MoE 各层比特分配/RESULT.md::strategy-verdict`、`docs/subprojects/a04-MoE 各层比特分配/RESULT.md::migrated-res8` | 部分（三点的分配归因撤回在 `docs/subprojects/a04-MoE 各层比特分配/RESULT.md::migrated-res8` 的 `retracted:` 字段，不在它的 status 行里） |
| QAT 不是量化损失的补救，也不是被否定的补救：它是同标称档下更小比特的选项；低位宽档更低但差不能归给训练 | `docs/subprojects/a09-量化感知训练 QAT/RESULT.md::qat-analysis`、`docs/subprojects/a09-量化感知训练 QAT/RESULT.md::qat-2bit-pairs` | 部分（`provisional` 只标在 `docs/subprojects/a09-量化感知训练 QAT/RESULT.md::qat-2bit-pairs` 的状态行括注里，不在节点 status 上） |
| 第三方方案 GSQ-RCO 相对原生阶梯在本设计的分辨力边界上只有一格露出信号，按多重比较读不成立；旧措辞「所有差值都跨 0」已撤回 | `docs/subprojects/a10-第三方量化方案/RESULT.md::position-nearest-iq3s`、`docs/subprojects/a10-第三方量化方案/RESULT.md::multiplicity-18` | 部分（撤回的措辞落在 `docs/subprojects/a10-第三方量化方案/RESULT.md::res13`，「不是结论」这半句落在 `docs/subprojects/a10-第三方量化方案/RESULT.md::multiplicity-18` 正文，都不在 status 行里） |
| 未测不是 0：显存不足、架构无法加载的格登记为非测量，不是低分 | `docs/subprojects/i02-测量基础设施/RESULT.md::res14` | 成立（登记为未测） |
| MultiPL-E 旧列不可比：不同模型跑了不同的语言子集，近零分数是语言覆盖造成的假象；现行规则是不池化不同语言 | `docs/subprojects/i01-判分与基准有效性/RESULT.md::res16`（覆盖假象）、`docs/subprojects/i02-测量基础设施/RESULT.md::res29`（不池化的列拆分） | 成立 |
| m160 面板没有产出测量：格在生成前失败，脚本把失败形态记成 CORRUPT；同批原始完成物显示是模型不写函数体 | `docs/subprojects/i01-判分与基准有效性/RESULT.md::res19` | 成立 |
| 生成协议改变 MultiPL-E 分数（跨面板比较，不是同一面板内的受控比较） | `docs/subprojects/i01-判分与基准有效性/RESULT.md::res18` | 部分（`provisional`） |

## 三、撤回记录

| 被撤回的说法 | 事实所在 | 状态 |
| --- | --- | --- |
| 全 `Exception` 的格曾被归因为整轮运行失败，随后又被归因为旧后处理破坏缩进；两种归因都已撤回，成因改为模型把函数体首行写在第 0 列。「必须记缺失、不得写 0」这一半仍成立 | `docs/subprojects/i01-判分与基准有效性/RESULT.md::res17`、`docs/subprojects/i01-判分与基准有效性/RESULT.md::res17b`、`docs/subprojects/i01-判分与基准有效性/RESULT.md::res21` | 已撤回（两种归因的撤回落在 `docs/subprojects/i01-判分与基准有效性/RESULT.md::res17b`，`res17` 的 status 行括注点名它，不在 status 上） |
| 旧 `strip_fences` 只在围栏闭合时剥离，把 Markdown 围栏当语法错误；该批 chat 分数作废，只补正确后处理重算 | `docs/subprojects/i01-判分与基准有效性/RESULT.md::res20` | 已撤回（旧分数作废写在 `docs/subprojects/i01-判分与基准有效性/RESULT.md::res20` 正文，它的 status 行不带这句） |
| 旧 `strip_fences` 的 `text.strip()` 抹掉无围栏完成物的首行缩进，并因此造成 gemma-4-26B-A4B py 的 `Exception`：观察成立、因果撤回（同一签名在修正后的 harness 下依然存在） | `docs/subprojects/i01-判分与基准有效性/RESULT.md::res21` | 已撤回（因果从句的撤回写在 `docs/subprojects/i01-判分与基准有效性/RESULT.md::res21` 正文，它的 status 行不带这句） |
| m160 的前提「12b 没有任何 cpp/py 数据」不成立：m6b 面板已有 chat cpp 数据；同批 py 格因配置不同已被 m161 重测取代，不并入 | `docs/subprojects/a12-多语言代码 MultiPL-E/RESULT.md::m6b-two-cells` | 已撤回（前提作废；判定取自该节点的这一节正文，它的 `状态：` 行不带撤回——m6b 两格本身仍单独成行） |
| 按基准汇总的位宽步长中位数、每比特分数变化中位数、能力型减知识型的配对差这三条旧值撤回：聚合口径、区间类型与聚类单位在原稿里都没有记录，无法重算 | `docs/subprojects/a01-量化位宽/RESULT.md::res2`、`docs/subprojects/a01-量化位宽/RESULT.md::res3`、`docs/subprojects/a01-量化位宽/RESULT.md::res4` | 已撤回（不可复核；方向改由 `docs/subprojects/a01-量化位宽/RESULT.md::an2` 承载） |
| 「陈旧脚本根路径未修」这条登记作废：`.wrapup/` 的可执行脚本已改为按自身位置定位，历史记录类文件按原样保留（改写它们等于伪造运行记录） | `docs/subprojects/i02-测量基础设施/RESULT.md::res27` | 已撤回（作废理由在 `docs/subprojects/i02-测量基础设施/RESULT.md::res27` 的当前正文——它记的就是修复后的事实，正文里没有撤回字样） |
| 「MultiPL-E 表仍渲染重复行」这条登记作废：逐语言表的行键已改成「模型 + 显示标签」；行键装不下 `top_k` 是已裁决接受的限制，不是待修缺陷 | `docs/subprojects/i02-测量基础设施/RESULT.md::res28`、`docs/subprojects/i02-测量基础设施/RESULT.md::res41` | 已撤回（作废理由在 `docs/subprojects/i02-测量基础设施/RESULT.md::res28` 记的行键改动与 `docs/subprojects/i02-测量基础设施/RESULT.md::res41` 记的已裁决限制，不在 status 行里） |
| 「研究证据可恢复性待修复」这条登记作废：报告的输入有限且随仓库分发，干净 clone 一条命令逐字节重建报告 | `docs/subprojects/i02-测量基础设施/RESULT.md::res24`、`docs/subprojects/i02-测量基础设施/RESULT.md::res25` | 已撤回（作废理由在 `docs/subprojects/i02-测量基础设施/RESULT.md::res24` 与 `docs/subprojects/i02-测量基础设施/RESULT.md::res25` 的当前正文——干净 clone 一条命令重建报告，不在 status 行里） |
| 「文档检查受阻，不得记为通过」这条登记作废：标准已落进本仓库，`python3 docs/check_docs.py` 退出 0 | `docs/subprojects/i02-测量基础设施/RESULT.md::res32` | 已撤回（作废理由在 `docs/subprojects/i02-测量基础设施/RESULT.md::res32` 的当前正文——标准已落地、`python3 docs/check_docs.py` 退出 0，不在 status 行里） |
| 「`3eea78f` 独立复核判为接受但带注解」这条登记作废：它只在 `STATUS.md` 里出现过，而 `STATUS.md` 在 `bc1eeb0` 被重写、那段随之退役（`git show bc1eeb0 -- STATUS.md`），`docs/` 下也没有节点承载这次复核，所以它不再登记为「未核实」而是没有 home | `STATUS.md`（`grep -n 3eea78f STATUS.md` 无命中）、`docs/`（`grep -rn 3eea78f docs/` 无命中）；m161 面板的逐格值仍在 `docs/subprojects/a12-多语言代码 MultiPL-E/RESULT.md`（「chat 面板的逐格值（m161）」一节，该节没有节点 id——它不是一条可路由的事实，只是一份逐格数值的落点） | 已撤回（登记随 `STATUS.md` 重写退役，`docs/` 无节点） |

## 四、推断性判断（`author: agent`，不是测量结论）

| 结论 | 事实所在 | 状态 |
| --- | --- | --- |
| 位宽该选多大取决于家族自己的曲线拐点，没有统一档；按当前数据只有 Qwen3.5-2B 有带区间的拐点 | `docs/subprojects/a01-量化位宽/RESULT.md::an1` | 部分（`provisional`） |
| 判断量化够不够看代码/推理/指令，不要看知识类基准；原措辞「MMLU 几乎不动」已在节点内收窄为「敏感度约为代码的一半」 | `docs/subprojects/a01-量化位宽/RESULT.md::an2` | 部分（`provisional`） |
| 小模型做困难多步任务需要更多位宽 | `docs/subprojects/a02-模型规模/RESULT.md::an3` | 部分（`provisional`） |
| 同文件大小下比较「方案/字节」比「厂商标签」更重要；标签代理的是比特分配 | `docs/subprojects/a03-量化方案与厂商/RESULT.md::an4` | 部分（`provisional`） |
| 不要用 PPL 做决策 | `docs/subprojects/i01-判分与基准有效性/RESULT.md::an5` | 部分（`provisional`） |
| 不要指望 QAT 挽回量化损失：它更像「同配方下体积更小」的选项 | `docs/subprojects/a09-量化感知训练 QAT/RESULT.md::an6` | 成立（节点已改写为「不是被否定的补救」，替代原来的 `provisional`） |
| 换生成协议后必须重测：协议本身会改变量化结论的符号 | `docs/subprojects/i01-判分与基准有效性/RESULT.md::an7` | 部分（`provisional`） |

## 五、未闭合的问题与阻塞

| 结论 | 事实所在 | 状态 |
| --- | --- | --- |
| 硬阻塞实验不是缺失也不是 0：显存不足、本环境缺运行时、本环境不可测三类分开登记，各有名字与统一入口，不合成一张表 | `docs/subprojects/i02-测量基础设施/RESULT.md::res72`、`docs/subprojects/a11-扩散式解码/RESULT.md::res10` | 成立（三类未测的名称与登记入口；具体格见 `docs/subprojects/i02-测量基础设施/RESULT.md::res14`） |
| MultiPL-E chat 同一个 cell 的跨 run 差异只裁决了一半：四槽批处理被排除、旧判分值不可复现；残留是 m26 用的提示集已被删除，输入差不可再验，所以该列单次值仍按噪声档读 | `docs/subprojects/i01-判分与基准有效性/RESULT.md::res29`、`docs/subprojects/i01-判分与基准有效性/RESULT.md::res25` | 部分（只裁决一半写在 `docs/subprojects/i01-判分与基准有效性/RESULT.md::res25` 的节点名与正文「plan15 的一半已裁决」，不在它的 status 行里） |
