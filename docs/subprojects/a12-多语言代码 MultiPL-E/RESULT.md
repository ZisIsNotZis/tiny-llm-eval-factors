# a12 多语言代码 MultiPL-E — 结果

本文件是本子项目结果层的唯一 home。每条事实写成「结论 / 证据 / 复算」，数字的当前值只在这里；报告里的图与表由数据库重新生成，不引用本文件的数值。
数据源：`experiments.sqlite`（只读打开），产物源：`.wrapup/*_summary.jsonl` 与 `.wrapup/mres/*_eval.json`。

复算入口（输出首行记录被审 revision、脚本 sha256、命令与脏路径，所以捕获绑定到版本而不是绑定到说法）：

- 审计：`python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"`，退出 0 = 谱系、全 Exception、协议设置、提示集哈希、报告行归属五项全绿。
- 负控：`bash "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_negative_control.sh"`，退出 0 = 干净报告通过、两处人为篡改都被拒。
- 已存捕获（文件名带短 revision，首部记 `report.html` 的 sha256 `6d5db1ad0d800954…`）：`evidence/audit-2805050-this-machine.txt`（本机 HEAD，退出 0）、`evidence/audit-2805050-clean-clone.txt`（干净 clone，退出 0、0 个脏路径）、`evidence/negative-control-2805050.txt`（退出 0，四处篡改全被拒）。

## 审计的负控能力：四处篡改都被拒

- 结论：把 `report.html` 与库各复制到临时目录后，①把 gemma-4-12b Q2 的 `0.0248`（它只存在于 `mpl-chat-nothink-greedy-768;ctx=4096;tmpl=unverified` 下）塞进同一模型的 `raw` 行，审计以 `MISMATCH: ('gemma-4-12b-it-UD-Q2_K_XL.gguf', 'raw', 'cpp', 0.0248, "no stored cell under this row's protocol label")` 退出 1；②把该模型 chat 行里印的 `(161)` 改成 `(160)`，审计以 `MISMATCH: (…, 'chat', 'cpp', 0.0186, 'printed n=160, artefact n=[161]')` 退出 1；③往库副本里给一个已存协议串追加 `;ctx=99999`，`[9]` 报 `RELABELLED: summary 'mpl-raw-greedy-768' -> stored 'multipl-e-raw-greedy-768;ctx=99999'` 并退出 1；④往库副本里把 gemma-4-12b Q2 js 这个「161 题全 Exception」的 NULL 格写回 `_score = 0.0`，`[4]` 报 `scored cells whose eval is all-Exception: 1` 并点名该格、退出 1。干净报告退出 0，且脚本另外断言干净跑的 `[1]` 段打印 `via a14 regrade 12`（否则那 12 条 `;corpus=` 行是被静默丢掉而不是被追溯）。所以「一个格必须属于它自己那一行协议」「印出的题量必须等于产物的题量」「协议串不得丢或换设置」「全 Exception 的格不得带分数」这四条不是靠断言，而是能失败的检查。
- 证据：三处篡改都只改临时副本（`mktemp -d`，库用 `sqlite3 .backup` 复制），不动真报告与真库；判据分别是 `[7]` 段把报告行的协议标签映射回库中该 (模型, 语言) 的协议再比对值与题量，与 `[9]` 段的全串比对。捕获 `evidence/negative-control-f60a028.txt`（退出 0）。
- 复算：`bash "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_negative_control.sh"`。

## 谱系：每个已入库的格都追到落盘产物

- 结论：库中 MultiPL-E 共 349 个格，其中 341 个有分数、8 个是 NULL；341 个有分数的格全部追到落盘产物——251 个命中 panel summary 的同语言同分值行，78 个只命中 per-item eval，12 个走 a14 的改分清单（`;corpus=` 行，见「追溯按行的代次分开」），未追溯 0 个。
- 规则（`[1]` 按行的代次选证据源，两条不混，实现见 `mpl_cell_audit.py::cells_with_lineage`）：
  (a) **不带 `;corpus=` 的行** → 该面板 summary 里同语言同分值的一行，或命中 `(语言, 通过数, 题数)` 的逐题产物；
  (b) **带 `;corpus=` 的行**（a14 用钉住语料 `ac14c3b0abfa` 重算出来的代次）→ **只**认 `docs/subprojects/a14-部分给分/evidence/py_regrade_manifest.tsv`，并且必须同时满足两件事：清单条目在这五项上唯一（`corpus` + `language` + `score_new` 到 6 位小数 + `db_models` 含该 gguf + `summary_file` 基名等于库中 `source_file`），以及它取代的那行在库中仍存在、且那一行的 `superseded_by` 等于本行的协议串。缺指针、清单无条目、条目不唯一，任一情况都记 untraced 并打印原因。
  (b) 的配套规则：**不留 summary/eval 回退**——重评分值按定义不在旧 summary 里（旧值算在旧语料上），能匹配上只是数值巧合，而这检查本身是多重集成员检查、分辨不了巧合与证据。
- 证据：两格 eval-only 是 `m26-q38-27b-q2-cpp_fixed_eval.json`（102/161=0.6335，summary 记 35/161）与 `m6b-g12b-q2-cpp_fixed_eval.json`（4/161=0.0248，summary 记 2/161）。题数来自 `n_items`：i02 已从产物回填（`migrate_db.py` 的 backfill，最后 2 格见 `90f3511`），MultiPL-E 里的 8 个 NULL 格就是 4 个全 Exception 的 js/rb 格加上它们在 `third-family-code` 协议串下的 4 份副本（见「四行伪 0」）；满格题数为 cpp/py/js/rb 161、java 158、rs 155。
- 限制：`[1]` 是**多重集成员检查**，不是逐格绑定，确切形状是：以库中该格的 `source_file` 为一张池子，把该面板 summary 的每一行折成 `(语言, 分值)` 放进 `collections.Counter`，库里同文件的每个格消耗其中一份（`mpl_cell_audit.py::cells_with_lineage`）。它证明的是「这个值出现在该面板该语言的产物里」，**不**证明「这一行属于这个模型文件」。直接后果：把同一面板、同一语言的两格在库与报告里**同时互换**，`[1]` 仍 exit 0——两份产物都没变、多重集也没变；负控的三处篡改（协议行、题量、协议串）不覆盖这种情况，所以这不是负控能拒的错，而是这条检查的边界。per-item eval 的配对键 `(语言, 通过数, 题数)` 同样不含模型：341 个格里 141 个只命中一份 eval、189 个命中多份、65 个键对应多份文件（多份时只接受状态直方图一致）。把格绑到模型上的只有 `[7]` 的一行一句（该 (模型, 协议标签, 语言) 下必须存在这个值）与库里的 `run_tag`/`source_file` 两列；把 `[1]` 读成逐格绑定会高估它。审计自己把这条印在 `[1]` 段：`the key is not model-unique, so it proves a file reproduces the cell, not that the file is this model's`。
- 干净 clone（可复现性）：`[1]` 在本机与干净 clone 上都是 341/341、退出 0。3 条 m165 vendor 行曾经在 clone 里记 untraced（338/341、退出 1），因为它们的 `source_file` 是 `.wrapup/mres/m165-vendor/vendor_r1_summary.jsonl`，而 `.gitignore` 只放行 `*_eval.json`、这份来源清单不随仓库分发；`2805050` 显式放行这几份来源清单后转绿。由此定一条规则：**承载断言的行，其来源文件必须随仓库走**——否则「这行从哪来、n 是多少、能不能追溯」在 clone 里根本无从核对，本审计会把它们记成 untraced 而不是假装有证据。
- 复算：审计脚本 `[1]` 段。

## 报告：报告印出的每个格都属于它自己那一行协议，且是库中已存的格

- 前提：本节数字来自 `report.html`（sha256 `6d5db1ad0d800954…`，四行伪 0 修完并重生成后，与 `git show HEAD:report.html` 逐字节相同）。捕获名称与本 revision 一致，首部记着被审 revision、脚本 sha256、命令与脏路径。
- 结论：`report.html` 第十三节（多语言代码）逐语言表现有 83 行（= 模型 × 协议标签）、194 个有值格，全部通过 `[7]` 的行归属检查（值在该行协议标签下存在、题量等于产物题量）；归属不符 0 格；题量比对了 194 格、**0 格因缺 n 而跳过**——伪 0 修完重生成后，逐语言表里既没有 `(题量未知)`，也没有把全 Exception 的格印成 0.0000。
- 结论：库中按 (模型, 协议串, 语言) 有 194 个键，而报告逐语言表只印出 188 个有值格，装不下的就是标签碰撞：m31-topk 的协议串（`mpl-raw-t0.3-768;topk-set=…`）与 m27 的 `multipl-e-raw-t0.3-768` 渲染成同一个标签 `raw·temp=0.3`，于是 3 个模型 × 2 语言各有一行被并掉。其中 3 个键的两条记录值不同（m31 的 `top_k=1` 锚点等于贪心地板值）：第十三节的逐语言表只印其中一条，但第六节「采样 / 解码参数」按 `取值` 分行把两条都印了出来，见「表里被并掉的格」。
- 证据：逐语言表 83 行的有值格按列计为 cpp 81 / py 66 / js 21 / java 12 / rs 8 / rb 6，合计 194，与 `[7]` 打印的 `report cells read: 194` 相等；表头是 `模型文件 | 生成协议 | C++ | Python | JS | Java | Rust | Ruby`。
- 限制（[7] 通过不等于印的是改分后的值）：`[7]` 只要求「该值在该 (模型, 协议标签, 语言) 下存在」，而 8 个协议串都渲染成标签 `raw`，所以同一格里存着多个候选值时它分辨不出取了哪个。实例：`Qwen3.5-4B-UD-Q2_K_XL` 的 py 在库里有 4 行——m1 的旧值 0.354037（已被 `superseded_by` 指向）、m50 的两行同值 0.354037（**没有被取代**）、m1 的语料重评分 0.360248；第十三节印的是 0.3540，即改分前的值。这属「标签不带被采样/被取代那一维」（`WP8`）与 m50 那两行没有取代指针两件事，归 i02，本节点只记录：`[7]` 的绿灯说明归属正确，不说明展示的是当前代次。
- 复算：审计脚本 `[7]` 与 `[10]` 段；逐列计数读同一张表的 `<td>` 即可，判据是每格以数字开头（`—` 与 `(题量未知)` 不计入）；上面那个实例用 `sqlite3 experiments.sqlite "SELECT rowid,run_tag,protocol,round(_score,6),superseded_by FROM experiments WHERE model='Qwen3.5-4B-UD-Q2_K_XL.gguf' AND language='py' AND bench_family='humaneval-multipl-e'"` 复现。

## 追溯按行的代次分开：旧语料行 → summary，`;corpus=` 行 → a14 改分清单

- 结论：`[1]` 按行的代次选证据源，两条路不混：不带 `;corpus=` 的行仍按该面板的 summary / 逐题产物追溯；带 `;corpus=` 的行（a14 用钉住语料 `ac14c3b0abfa` 重评出来的）只按 a14 的改分产物追溯，并且要求被它取代的那行仍存在、`superseded_by` 指向它的协议串。当前 341 个有分数的格里，251 个走 summary、78 个走逐题产物、12 个走 a14 清单（`via a14 regrade 12`）。
- 结论：为什么不能统一——重评分值在定义上不可能出现在旧 summary 里（旧值算在旧语料上），所以「能在旧 summary 里找到」对这类行只可能是**数值巧合**；而 `[1]` 的检查本身就是 `(语言, 分值)` 的多重集成员检查（见「谱系」的限制），它分辨不出巧合与证据。把两条路合成一条，等于让这类行靠巧合变绿。
- 结论：键与被接受的证据——查 `evidence/py_regrade_manifest.tsv`，须在 `corpus` + `language` + `score_new`（6 位小数）+ `db_models` 含该 gguf + `summary_file` 基名等于库中 `source_file` 这五项上**唯一**命中一个 `tag`；命中多于一条或一条都没有，都记 untraced 并打印原因，不猜。a14 的另一个产物 `py_testfrac_regrade.json` 不在这里用：它backing 的是 `bench_family='testfrac'` 的 11 行逐测试比例格，本审计只看 `humaneval-multipl-e`，库中 `;corpus=` 行按 `bench_family` 恰好分成这两半（12 + 11）。
- 结论：`superseded_by` 的指针是这条追溯的另一半，缺它就断：审计把该行记 untraced，并打印「清单点名了 tag，但没有旧行的 `superseded_by` 指过来」。
- 证据：改判据前有 8 条 `;corpus=` 行被记 untraced（`NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL`、`Ornith-1.5-9B-Q4_K_M`、`Ornith-1.5-9B-Q5_K_M`、`Qwen3.5-4B-UD-Q2_K_XL`、`Ternary-Bonsai-27B-Q2_g64`、`Qwen3.5-9B-UD-Q2_K_XL`、`Qwen3.5-9B-UD-Q3_K_XL`、`Qwen3.5-2B-UD-Q3_K_XL` 的 py 格），改后 0 条；另 4 条 `;corpus=` 行原来靠 summary 巧合变绿，现在也改走清单。库中共 23 条 `;corpus=` 行，全部落在上两个家族里，且每条的旧行指针都成立。
- 限制：manifest 的 `identity_new` 写作 `mpl-raw-greedy-768;corpus=…`，而 i02 入库时把基础协议串规范成 `multipl-e-raw-greedy-768`，所以配对不能拿 `identity_new` 与库串直接比对，要按上面那五个字段；这份清单也不含模型名以外的身份（`tag` 是面板短名），跨面板同名格靠 `summary_file` 消歧。
- 复算：审计 `[1]` 段（`via a14 regrade N` 与逐行 `regrade trace:` 两处）；`bash "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_negative_control.sh"` 的「normal regrade rows」一节断言这 12 条仍 traced。

## 覆盖：canonical 协议下的语言矩阵与缺口登记

- 结论：`protocol='multipl-e-raw-greedy-768'` 下共 53 个模型，318 个 model×language 槽位里 148 个有分数、4 个是 NULL、166 个在库中没有格。这 166 个里 **165 个是未测**，**1 个是已测但按规则排除入库**，所以「都从未测过」是假登记。逐语言（库视角）：cpp 有分数 51 / NULL 0 / 库中无 2；py 50 / 0 / 3；js 21 / 2 / 30；java 12 / 0 / 41；rs 8 / 0 / 45；rb 6 / 2 / 45。
- 结论：cpp 的 2 个「库中无」都落在 gemma-4-12b 上：**Q2 的 raw cpp 跑过**，`0/161`，直方图 `{'Exception': 74, 'SyntaxError': 84, 'Timeout': 3}`，`migrate_db.py` 的 `M6_MODELS` 明确把它排除（注释：raw 模式下 12b 输出 `<|channel>thought` 思考通道，破坏代码生成，那个 0 不是量化测量），所以它没有库行——这是「已测但排除入库」，不是未测；**Q3 的 raw cpp 没有产物**，才是未测。两格的 chat 协议对见「chat cpp 两格」，本节点只讲 raw 矩阵。
- 结论：有 cpp+py 对的 50 个模型；没有对的 3 个是 `Qwen3.5-2B-UD-IQ2_XXS`（只有 cpp）与 `gemma-4-12b-it-UD-Q2_K_XL`、`gemma-4-12b-it-UD-Q3_K_XL`（raw 下 cpp 一格被排除入库、一格未测）。六种语言全测的 4 个是 `Qwen3.5-2B-UD-Q2_K_XL`、`Qwen3.5-2B-UD-Q3_K_XL`、`Qwen3.5-4B-UD-Q2_K_XL`、`Qwen3.5-4B-UD-Q3_K_XL`。
- 未测的理由（165 个空格）：都是「该模型所在的那些面板没有跑这个语言」，没有产物也没有失败记录，按规则记为显式未测而不是 0。java/rs/rb 的 131 个空格全部落在这个类里：跑过这些语言的面板只有 m1（六语言）、java 的 m6/m38/m51/m56/m57、js 的 m2/m3/m5/m6/m38/m51/m56/m57、rs 与 rb 的 m42/m54/m60；其余面板按设计只跑 cpp+py。
- 结论：4 个 NULL 空格不是未测而是被测过且整格全 `Exception`（见「4 个 NULL 格」）；「已测但被规则排除入库」与「已测但整批未入库」是另外两类，见「覆盖：库中没有的格分三类」。
- 证据：语言集因模型而异的旧列不可比，是 i01 的判分审计节点登记的事实（i01 的 `res16`，其 home 随 i01 迁移到它自己的结果文档）；本节点只提供当前矩阵，不重复那条结论。
- 复算：审计脚本 `[2]` 段打印逐语言的 scored/NULL/absent 三元组与完整的 53 行矩阵（空格 = 未测，`NULL` = 整格全 Exception 记为缺失，数字 = 通过率）；语言→面板清单 `sqlite3 experiments.sqlite "SELECT DISTINCT language,run_tag FROM experiments WHERE bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768' AND language NOT IN ('cpp','py') ORDER BY language"`。

## 覆盖：库中没有的格分三类，只有一类是「未测」

- 结论：一个 model×language 槽位在库中没有格，可能是三种状态之一，本册分开登记：(a) **未测**——没有产物也没有失败记录（raw 的 169 个空格、chat 的 24 个空格）；(b) **已测但按规则排除入库**——有产物与直方图，入库脚本按面板设计跳过（1 个：gemma-4-12b Q2 raw cpp）；(c) **已测但整批未入库**——产物在 `.wrapup/*_summary.jsonl` 里，但那个面板没有可用的入库映射甚至没有入库函数（m29 的 FA × KV 轴、m160 的 12b raw 面板）。把 (a) 与 (b)(c) 混成一句「面板没跑这个语言」，就是本册此前的那处假登记。
- 结论（b）：gemma-4-12b Q2 raw cpp `0/161`，直方图 `{'Exception': 74, 'SyntaxError': 84, 'Timeout': 3}`；产物 `.wrapup/mres/m160-g12b-q2-cpp-raw_eval.json`，`.wrapup/m6_summary.jsonl` 与 `.wrapup/m160_summary.jsonl` 各有一行 `pass 0 n 161 protocol mpl-raw-greedy-768`；库中 0 行，因为没有 `ingest_m160`，且 `M6_MODELS` 明确排除 12b（raw 下 `<|channel>thought` 通道破坏代码生成，这个 0 不是量化测量，与「8 个 0.0 格」里 java 158 / rs 155 的成因同类）。
- 结论（c1）：`.wrapup/m29_summary.jsonl` 24 行、每行都满 161 题，但只有 **12 个配置**——3 个 cell（`faon_f16` / `faoff_f16` / `faon_q8`）× 2 个模型（`Qwen3.5-2B-UD-Q2_K_XL`、`Qwen3.5-2B-UD-Q3_K_XL`）× 2 语言（cpp/py），每个配置写了两遍且两行 pass/score 逐字相同（无法区分是重复追加还是两次完全相同的贪心复跑）。pass 17–44（score 0.1056–0.2733），协议串带 `;fa=on|off,kv=q8_0/f16|q8_0/q8_0`。库中 0 行、`run_tag='m29-flash-attn'` 也为 0：`ingest_m29` 调 `ingest_mpl` 时没传 model_map，走默认 `MPL_MODELS`，而 m29 的 `model` 是短名 `q2`/`q3`，`MPL_MODELS` 没有这两个键，`ingest_mpl` 因此静默 `continue`。
- 结论（c2）：m160 的 12b raw 面板同样没有 `ingest_m160`，所以它唯一的格（Q2 cpp）只有 summary 与 eval、没有库行——(b) 与 (c2) 是同一次面板设计的结果。
- 限制：这两批属 flash-attention × KV 轴与 12b raw 面板的语义范围（`a05` 的 KV 缓存精度、面板的排除规则），a12 只登记状态与来源，不改库、不改报告、不补录。
- 复算：`wc -l < .wrapup/m29_summary.jsonl`（24）与 `python3 -c "import json;rows=[json.loads(l) for l in open('.wrapup/m29_summary.jsonl')];print(len({(r['model'],r['lang'],r['cell']) for r in rows}))"`（12）；`grep -n "M6_MODELS" -A 6 migrate_db.py`；`grep -c "ingest_m160" migrate_db.py`（0）；`python3 -c "import json,collections;d=json.load(open('.wrapup/mres/m160-g12b-q2-cpp-raw_eval.json'));print(d['n'],d['pass'],dict(collections.Counter(x['status'] for x in d['details'])))"`。

## 覆盖：chat 协议只覆盖 cpp 与 py，24 个槽位显式未测

- 结论：chat 生成协议下有 14 个格，覆盖 6 个模型 × cpp/py 两种语言；这 6 个模型的 36 个 model×language 槽位里，js / java / rs / rb 的 24 个从未测过，理由与 `PLAN.md` 非目标一致：非 cpp/py 语言的判分有效性还没有 i01 的审计，24 格也超出 9% 的 GPU 份额。gemma-4-12b 的 cpp 槽位已由 m163 补测（见「chat cpp 两格」），所以 chat 协议下 12b 的 cpp 与 py 两语言都有格。
- 证据：chat 协议串共两种：`mpl-chat-nothink-greedy-768`（12 格，含 m163 的 2 格）与 `mpl-chat-nothink-greedy-768;ctx=4096;tmpl=unverified`（2 格）。
- 复算：审计脚本 `[3]` 段，含 `chat cells: 14 over 6 models` 与 `unmeasured under chat: 24 of 36` 两行。

## chat 面板的逐格值（m161）

- 结论：里程碑 m161 的 7 个 chat 格（`mpl-chat-nothink-greedy-768`，n=161）为：Qwen3.8-27B Q3 cpp 140/161=0.8696（端到端控制格）、Qwen3.8-27B Q2 py 121/161=0.7516、Qwen3.8-27B Q3 py 145/161=0.9006、gemma-4-12b Q2 py 77/161=0.4783、gemma-4-12b Q3 py 93/161=0.5776、gemma-4-26B-A4B Q2 py 2/161=0.0124、gemma-4-26B-A4B Q3 py 1/161=0.0062。
- 证据：gemma-4-26B 的两个 py 格由 `Exception` 主导（159/161、160/161），成因是模型把函数体首行写在第 0 列，而 harness 不重排缩进（`strip_fences` 只剥行首围栏、保留缩进），拼接后必然是 IndentationError；每格「首行在第 0 列的完成物条数」与该格 Exception 条数逐格相等（159=159、160=160），同为 py 的 Qwen3.8-27B Q3 格只有 2/161 首行列 0、得分 0.9006，所以是模型行为而不是 harness 剥离。
- 复算：`for c in m161-g26b-q2-py-chat m161-g26b-q3-py-chat m161-q38-27b-q3-py-chat; do printf "%s firstcol0=%s\n" "$c" "$(jq -r '.completion|split("\n")[0]' .wrapup/mres/$c.jsonl | grep -c '^[^[:space:]]')"; done`；`jq -r '.details[]|select(.status=="Exception")|.name' .wrapup/mres/m161-g26b-q2-py-chat_eval.json | wc -l`。

## chat cpp 两格：m163 补测让 12b 在 canonical chat 协议下有了 cpp+py 对

- 结论：`run_tag='m163-chat-cpp-gemma12b'` 的 2 个 cpp 格按协议串 `mpl-chat-nothink-greedy-768` 原样入库（无 `;ctx=`/`;tmpl=` 后缀；`ctx_size=2048`、`parallel_slots=4`、`max_tokens=768`、`n_items=161`）：gemma-4-12b Q2 cpp `3/161=0.0186`、Q3 cpp `117/161=0.7267`。状态直方图分别是 `{'SyntaxError': 158, 'OK': 3}` 与 `{'OK': 117, 'Exception': 17, 'SyntaxError': 27}`；两格都不是整格 `Exception`，所以是实测值而不是 NULL。
- 结论：于是 12b 在同一个协议串下有四格并排：Q2 `cpp 0.0186 / py 0.4783`（77/161）、Q3 `cpp 0.7267 / py 0.5776`（93/161）。py 两格来自 m161（`run_tag='m161-chat-postprocess-fixed'`，协议串逐字相同），cpp 两格来自 m163，所以「12b 没有同协议 cpp+py 对」这条旧结论到此为止。
- 证据：`.wrapup/mres/m163-g12b-q{2,3}-cpp-chat.jsonl` 与各自 `_eval.json`，汇总 `.wrapup/m163_summary.jsonl`（随入库一起提交）；面板日志 `.wrapup/m163.log` 记着 preflight 的 6 个提示集哈希全匹配、两格 `gen … rc=0`、`panel end 2026-10-20 23:48:03`、`GPU wall=38m30s`，无 `GAVE UP` / `CORRUPT`。py 两格的分子取自 `.wrapup/mres/m161-g12b-q{2,3}-py-chat_eval.json`（各 n=161，pass=77 / 93）。
- 限制：m6b 的 `;ctx=4096;tmpl=unverified` 两格仍是另一套设置，不并入这个对（见「gemma-4-12b 的 m6b cpp 两格」）。
- 复算：审计 `[3]` 段把两组并列印出；`sqlite3 experiments.sqlite "SELECT model,language,_score,n_items,protocol FROM experiments WHERE run_tag='m163-chat-cpp-gemma12b' ORDER BY model"`；直方图 `python3 -c "import json,collections;d=json.load(open('.wrapup/mres/m163-g12b-q2-cpp-chat_eval.json'));print(dict(collections.Counter(x['status'] for x in d['details'])))"`。

## cpp 的补全形状：提示以 `{` 结尾、测试以 `}` 开头，回填空函数体才是对的

- 结论：cpp 提示的最后一行是 `bool has_close_elements(std::vector<float> numbers, float threshold) {`，紧接的 `tests` 以 `}` 开头（`}\nint main() {…`），而 harness 按 `prompt + completion + tests` 拼接。所以 cpp 的正确完成形状是「只回填空函数体、不带签名」，与 py 提示以 `"""` 结尾同理；协议串里没有为 cpp 做过任何偏离设置。
- 结论：因此 Q2 cpp 的 0.0186 不是提示或拼接形状失配的产物：158/161 是编译期 `SyntaxError`，即模型写出的函数体本身过不了 `g++ -std=c++17`；而 m6b 用另一套 ctx 独立跑出的 Q2 cpp 是 `4/161`、Q3 是 `130/161`，与 m163 的 `3/161`、`117/161` 同向同量级。形状若错了，Q3 不会到 0.7267。
- 证据：`.wrapup/prompts/humaneval-cpp.jsonl` 首题的 `prompt` 尾部与 `tests` 头部；`.wrapup/mres/m163-g12b-q2-cpp-chat_eval.json` 的直方图 `{'SyntaxError': 158, 'OK': 3}`；m6b 的 `4/161`、`130/161` 见 `migrate_db.py` 的 m6b 注释与审计 `[1]` 的 eval-only 行。
- 限制：这条只排除「提示/拼接形状导致 cpp 整体判错」这一种解释，不解释 Q2 为什么写不合法；Q2_K_XL 的输出质量本身是候选原因，本节点不裁决。
- 复算：`python3 -c "import json;p=json.loads(open('.wrapup/prompts/humaneval-cpp.jsonl').readline());print(repr(p['prompt'][-100:]));print(repr(p['tests'][:40]))"`。

## gemma-4-12b 的 m6b cpp 两格走另一套协议串（ctx=4096、模板未核对）

- 结论：gemma-4-12b chat cpp（m6b 面板）入库时按协议串原样记录，末尾带 `;ctx=4096;tmpl=unverified`：Q2 `4/161=0.0248`、Q3 `130/161=0.8075`。这两格不并入任何 cpp+py 对：m6b 是 `ctx=4096`、没有 `--jinja`、模板路径未核对的一套配置，与 m161/m163 的 `ctx=2048 --jinja` 不同。12b 的同协议 cpp+py 对由 m163 的 canonical chat 两格给出（见「chat cpp 两格」），m6b 这两格继续单独成行。
- 证据：`.wrapup/m6b.log` 有 `n_ctx_slot = 4096`；`.wrapup/run_m6b.sh` 的 start_server 无 `--jinja`；`.wrapup/run_m161_chat_py.sh` 与 `.wrapup/run_m163_chat_cpp_12b.sh` 都是 `CTX=2048` 加 `--jinja`。m6b 的 summary 留的是旧判分值（Q2 cpp 2/161、Q3 py 5/161），库值取自 `_fixed` 重判，两者的差由旧后处理解释，不由本节点裁决。m161 与 m163 的日志都记下了所用提示集的哈希，与 `.wrapup/prompts/SHA256SUMS` 的 `humaneval-cpp.jsonl` 行一致。
- 限制：这两格的 `n_items` 已由 i02 从产物回填为 161，报告印 `(161)`；它们与 canonical 两格的分栏理由只是协议串不同（`;ctx=4096;tmpl=unverified`），与题量无关。
- 复算：`grep -n "n_ctx_slot" .wrapup/m6b.log | head -1`；`grep -n "jinja\|CTX=" .wrapup/run_m6b.sh .wrapup/run_m161_chat_py.sh .wrapup/run_m163_chat_cpp_12b.sh`；`sqlite3 experiments.sqlite "SELECT protocol,round(_score,4) FROM experiments WHERE run_tag='m6b-chat-gemma12b'"`。

## 8 个 NULL 行（4 个格）：整格全 Exception 记为缺失，证据是逐题状态而不是 summary

- 结论：gemma-4-12b Q2/Q3 的 js 格（`m51-gemma-java-js`）与 rb 格（`m54-gemma-rust-ruby`）是 NULL：这四格的 161 道题逐题状态全部是 `Exception`，harness 一次都没能执行完，按规则记为缺失，不是 0，也不进任何均值。注意 `m51_summary.jsonl` / `m54_summary.jsonl` 把这四格记成 `"score": 0.0`，所以 summary 不是 NULL 的证据；NULL 来自后续修复，证据是 per-item eval。
- 结论：这 4 个格在 `multipl-e-raw-greedy-768` 与 `mpl-raw-greedy-768-third-family-code` 两个协议串下各存了一行，所以库中是 **8 个 NULL 行、4 个格**；`third-family-code` 那 4 行原本存着 0.0，由 `migrations/null_all_exception_cells.py` 按 rowid 置 NULL（见「四行伪 0」），canonical 4 行一直是 NULL。
- 证据：`pan-gemma12b-q2-js_eval.json`、`pan-gemma12b-q3-js_eval.json`、`pan-gemma12b-q2-rb_eval.json`、`pan-gemma12b-q3-rb_eval.json` 各 161 题、`{'Exception': 161}`。
- 复算：审计脚本 `[4]` 段的 NULL 清单给出每格配对的 eval 文件名与状态直方图；或 `for f in .wrapup/mres/pan-gemma12b-q{2,3}-{js,rb}_eval.json; do python3 -c "import json,collections;d=json.load(open('$f'));print('$f',len(d['details']),dict(collections.Counter(x['status'] for x in d['details'])))"; done`。

## 10 个 0.0 行（8 个格）：6 个是长上下文生成失败的探针，2 个是真实计算的 0

- 结论：库里有 10 个行恰好是 0.0，去重后是 8 个格——多出的 2 行是 gemma-4-12b 的 java 与 rs 在 `third-family-code` 协议串下的副本（同一格两份，值都是真实算出的 0）；分两类（库外还有 1 个同成因的 0.0：12b Q2 raw cpp `0/161`，按 `M6_MODELS` 排除入库，见「覆盖：库中没有的格分三类」）。全 Exception 的 4 行原也存 0.0，已按规则置 NULL，不再计入这 10 行（见「四行伪 0」）。第一类 6 个是 `m30-kv-ctx` 的 60 题探针格（Qwen3.5-2B Q3、cpp、ctx=16384 与 ctx=49152）：配对的 eval 显示 59–60/60 道题都是 SyntaxError，即生成在长前缀下被截断，这个 0 是生成失败的产物、不是整格 161 题上的模型分数；它们属于 a05 的 KV 轴，改值会改 a05 的结论，所以只登记不修改（见 `PLAN.md` 非目标）。第二类 2 个是 gemma-4-12b 在 raw 协议下的 java 0/158 与 rs 0/155，都是逐题算出来的真实通过数（java 158 道全是 SyntaxError、rs 154 SyntaxError + 1 Exception），即 raw 协议下 gemma 先输出散文的 harness floor，与 i01 的协议结论同向；它们不是 NULL，因为跑过了、只是没通过。
- 证据：m30 六格分别配对 `m30-ctx16384-kv*-cpp_eval.json`（`{SyntaxError: 59, Exception: 1}`）与 `m30-ctx49152-kv*-cpp_eval.json`（`{SyntaxError: 60}`）；gemma java 配对 `pan-gemma12b-q2-java_eval.json`（`{SyntaxError: 158}`，pass 0），rs 配对 `pan-gemma12b-q3-rs_eval.json`（`{SyntaxError: 154, Exception: 1}`，pass 0）。
- 复算：审计脚本 `[4]` 段的 0.0 清单；或 `for f in .wrapup/mres/m30-ctx*-cpp_eval.json .wrapup/mres/pan-gemma12b-q2-java_eval.json .wrapup/mres/pan-gemma12b-q3-rs_eval.json; do echo "$f $(python3 -c "import json,collections;d=json.load(open('$f'));print(len(d['details']),d.get('pass'),dict(collections.Counter(x['status'] for x in d['details'])))")"; done`。

## 四行伪 0：`third-family-code` 的全 Exception 格置 NULL

- 结论：gemma-4-12b Q2/Q3 的 js/rb 四格在 `mpl-raw-greedy-768-third-family-code` 下曾存 `_score = 0.0`，而它们的逐题产物是 `{'Exception': 161}`——harness 一次都没跑完。按「全 Exception 记 NULL，不是 0」，这四行是同一格两份副本里错的那一份（canonical 孪生行一直就是 NULL）。`migrations/null_all_exception_cells.py` 已把它们置 NULL：rowid `12015 / 12017 / 12029 / 12031`，只按这四个 rowid 精确命中（不用「所有 0.0」，因为 m30 的 60 题探针与 12b 的 java/rs 也是 0.0，但它们是真实算出来的）。
- 结论：迁移前后的库都是 3364 行（行数不变），`PRAGMA integrity_check` = ok，`checks/db_check.py` 退出 0，连跑第二次改动 0 行（幂等）；改动前的备份是 `experiments.sqlite.bak75`（3364 行、integrity ok，`numbered_backup` 用在线备份 API 并自证可用）。
- 结论：报告侧后果：第十三节里 gemma-4-12b 的 `raw` 行不再把 js/rb 印成 `0.0000 (题量未知)`，改成 `—`；`[7]` 的「因缺 n 而跳过」从 4 变 0、比对格数从 188 变 194，`[4]` 的「有分数且全 Exception」从 4 变 0。
- 结论：审计不修这条，`bad = 4` 会让 `mpl_negative_control.sh` 的 clean run 直接红——这也是为什么它被当成数据缺陷而不是审计口径问题；写侧（m51/m54 的入库路径会再造一遍这种行）归 i02 修，a12 只修数据与审计。
- 证据：`python3 migrations/null_all_exception_cells.py --dry-run` 打印四行的判据（rowid、协议串、产物直方图、canonical 孪生行为 NULL）；`--apply` 打印备份名、改动行数与前后行数；负控第四种篡改把这四行之一写回 0.0，审计必须以 `all-Exception: 1` 点名并退出 1。
- 结论（那条查询现在归零）：验收要求的「`_score IS NOT NULL AND n_items IS NULL AND protocol LIKE 'mpl-raw-greedy-768-third-family-code'` 计数为 0」在本次修分后是 **4**，因为另外四条 third-family 行（12b 的 java/rs）是真实算出来的分数、缺的只是 `n_items`；这属回填缺口而不是修分范围，所以当时没有为了让查询归零而放宽迁移的条件，而是把实际值打印出来。i02 已按产物分母回填这四行（`db58584`：java 158 / rs 155），该查询现在是 **0**——两个缺陷各由各自的 owner 修，判据没有因此变软。
- 复算：`python3 migrations/null_all_exception_cells.py --dry-run`；`sqlite3 experiments.sqlite "SELECT rowid,_score FROM experiments WHERE rowid IN (12015,12017,12029,12031)"`；审计 `[4]` 段。

## 两语言分歧：拆列的依据

- 结论：51 个同时有 cpp 与 py 的模型里，py−cpp 的差值最小 −0.2671、中位数 +0.0186、最大 +0.1863，其中 29 个模型的 |差值|>0.05；两语言对 169/1275 对模型（13.3%）给出严格相反的次序，另有 13 对在至少一种语言上打平。这是 meta 裁决「标准列的 MultiPL-E 格拆成 C++ 与 Python 两列」的依据（`PLAN.md`「已裁决」），i02 已落地并提交（见「标准列已拆成 C++ 与 Python 两列」）。
- 撤回：早先报给 meta 的 566/1275 作废。错因是拿两个已排好序的列表按模型名逐个比对，而不是逐对比较差值符号；同一批数据按严格相反得 169/1275、把打平也算进去得 182、按秩反转得 177，三种口径里没有 566。
- 证据：169/1275 是按「两个模型在两语言下的差值符号相反」逐对判定得到的；报告第十三节的逐语言表把同一模型的 raw/chat 分成两行、六种语言各占一列，行键是 (模型, 协议)，没有跨语言或跨协议的合并。
- 复算：审计脚本 `[5]` 段；或直接 `python3 -c "import sqlite3,itertools;con=sqlite3.connect('file:experiments.sqlite?mode=ro',uri=True);d={};[d.setdefault(m,{}).__setitem__(l,s) for m,l,s in con.execute(\"SELECT model,language,_score FROM experiments WHERE bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768' AND language IN ('cpp','py') AND _score IS NOT NULL\")];b=[(m,v['cpp'],v['py']) for m,v in d.items() if 'cpp' in v and 'py' in v];sg=lambda x:(x>0)-(x<0);print(len(b),sum(1 for (m1,c1,p1),(m2,c2,p2) in itertools.combinations(b,2) if sg(c1-c2)*sg(p1-p2)<0))"`；行键证据 `grep -n "cells.setdefault((model, proto)" make_report.py`（`table_mpl_langs`）。

## 标准列已拆成 C++ 与 Python 两列（已提交）

- 结论：HEAD（`f60a028`）的 `report.html` 里，8 个标准表各带「多语言代码 C++」与「多语言代码 Python」两列，带池化单列「多语言代码」的标准表为 0 个；两列的格直接来自库中对应语言的格，不再有 cpp+py 的加权均值。改法在 `make_report.py` 的 `LBL`（`multipl_e_cpp`/`multipl_e_py`）与 `.wrapup/mktables.py` 的 `BENCH`/`query_cells_by` 里，两者与 `report.html` 都已提交，所以干净 clone 能用 HEAD 的代码重建同一份报告。
- 证据：审计 `[8]` 段报 0 个池化表、8 个已拆表；`git diff HEAD -- make_report.py .wrapup/mktables.py report.html` 为空；`sha256sum report.html` = `d7b2ed52834ed7a2…`，与 `git show HEAD:report.html | sha256sum` 相同。
- 复算：`python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"` 的 `[8]` 段；`grep -n "multipl_e_cpp" make_report.py`。

## 不混协议：行的身份由协议串决定

- 结论：报告的标准列取 MultiPL-E 时只读 `protocol='multipl-e-raw-greedy-768'`（`mktables.py::load_standard`），逐语言表的行键是 (模型, 协议标签)，所以采样温度、长上下文 KV、chat 三种设置不会进入同一格；取样轴的 (模型, 温度) / (模型, top_k) / (模型, 协议) 三组键在库中没有任何一个跨两个协议（0 个）。
- 结论：`[9]` 段比对 summary 行与库中协议串的**完整**字符串（`;` 后面的 `ctx=`、`kv=`、`tmpl=`、`fa=`、`prefix=`、`topk-set=` 全部参与，头部只在去掉 `-third-family-code` 这类面板名后比较，面板名记在 `run_tag` 里）：246 个格里 0 格无法解释地丢了或换了设置，另有 1 格是登记的例外。
- 例外：gemma-4-12b Q3 的 chat cpp 格，库里是 `mpl-chat-nothink-greedy-768;ctx=4096;tmpl=unverified`，而 summary 里同分值（130/161=0.8075）的那一行只写 `mpl-chat-nothink-greedy-768`。库里的串是对的：`.wrapup/m6b.log` 记着 `n_ctx_slot = 4096`，`.wrapup/run_m6b.sh` 启动时没有 `--jinja`，所以 ctx 与「模板未核对」这两段正是那次运行的设置，summary 少写了它们而不是库多写了。因此该格的值与协议串都不改库，例外在脚本的 `PROTOCOL_NOTE_EXCEPTIONS` 里逐键登记、每次运行都打印出来。
- 证据：`mktables.py::load_standard` 的 where 子句；`table_mpl_langs` 的行键；三组键的跨协议计数为 0；`[9]` 段对含 `;` 的 42 格做全串比对，唯一不一致就是上面的例外。
- 复算：`grep -n "bench_family='humaneval-multipl-e'" .wrapup/mktables.py`；审计脚本 `[2]`/`[9]` 段；负控的第三种污染往库里加一段 `;ctx=99999`，`[9]` 必须报 `RELABELLED` 并退出 1。

## 表里被并掉的格：3 个格的值被同一行标签遮住（open，归 i02）

- 结论：逐语言表的行键只有「模型 + 协议标签」，而 m31-topk 的协议串里被采样的那一维是 `top_k` 列、不在标签里，于是 m31 的 30 个格与 m27 同一模型的 2 个温度格撞成同一个标签 `raw·temp=0.3`：库中按 (模型, 协议串, 语言) 有 194 个键，报告只能印出 188 个格，合并掉的键里有 3 个两条记录的值不同（m31 的 `top_k=1` 锚点等于贪心地板值 0.1366/0.2422/0.2733，而 t0.3 采样是 0.1615/0.1739/0.3168）。第十三节每 (模型, 语言) 只印一条；第六节「采样 / 解码参数」的原始数据表按 `取值`（K=1 与 K=20/40/64/200）分行，把两条都印出来：Qwen3.5-2B @4.11 的 Python 0.1366（K=1）与 0.1615（K≥20）、@4.93 的 C++ 0.2422 与 0.1739、@5.70 的 Python 0.2733 与 0.3168。所以值没有离开报告，丢的是「这两条属于同一 (模型, 语言) 的两个不同 top_k」这一归属：从第十三节读不出另一条的存在。
- 证据：审计 `[10]` 段逐个列出这三组值；29 个键重复同一个值（重复入库，不丢信息），3 个键值不一致。
- 复算：审计脚本 `[10]` 段；修法在报告代码（标签要把被采样的一维带上，或把采样格移出逐语言表），归 i02，见 `PLAN.md` 的 `WP8`。

## 提示集与后处理已钉住

- 结论：提示集是 `.wrapup/prompts` 的 6 个文件，`SHA256SUMS` 6 个哈希全部匹配、0 漂移；后处理修正由 `.wrapup/test_mpl_postprocess.py` 的 5 个用例钉住，当前 5/5 通过。
- 证据：`sha256sum -c` 的等价检查在审计脚本 `[6]` 段；m161 日志记下了所用提示集的哈希，与 `SHA256SUMS` 的 `humaneval-cpp.jsonl` 行一致。
- 复算：`cd .wrapup/prompts && sha256sum -c SHA256SUMS`；`python3 .wrapup/test_mpl_postprocess.py`。

## 迁移到 Markdown 的后果与死引用

- 结论：本目录已改成 Markdown（`PLAN.md`/`RESULT.md`/`AGENTS.md`），迁移后的 `result.yaml` 已删除。报告生成器 `make_report.py::load_docs` 只读 `docs/subprojects/*/{plan,result}.yaml`，所以报告「客观结果（引自研究文档 L2）」列表不再列出 a12 的两条已测事实；这些事实的内容仍在报告的数据质量节正文里，当前值在 `RESULT.md`。要恢复那份列表，得让 `load_docs` 能读 Markdown，这是报告代码的改动（归 i02），不在 a12 目录内。
- 结论：`make_report.py` 的正文有 4 处引用写成 `docs/result/result.yaml::res5/res17b/res22/res24`，`STATUS.md`、`FINDINGS.md` 的引用同样指向 `docs/result/result.yaml` 与 `docs/plan/plan.yaml`；这些文件在 meta 迁移后已不存在。这是报告代码与根文档的死引用，a12 不改，登记给 meta。
- 证据：`grep -n "docs/result/result.yaml" make_report.py`。
- 复算：`grep -rn "docs/result/result.yaml::" make_report.py STATUS.md FINDINGS.md`；`grep -n "for path in sorted(glob.glob" make_report.py`。
