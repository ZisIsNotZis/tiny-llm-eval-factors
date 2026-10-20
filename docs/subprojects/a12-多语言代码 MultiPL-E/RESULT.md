# a12 多语言代码 MultiPL-E — 结果

本文件是本子项目结果层的唯一 home。每条事实写成「结论 / 证据 / 复算」，数字的当前值只在这里；报告里的图与表由数据库重新生成，不引用本文件的数值。
数据源：`experiments.sqlite`（只读打开），产物源：`.wrapup/*_summary.jsonl` 与 `.wrapup/mres/*_eval.json`。

复算入口（输出首行记录被审 revision、脚本 sha256、命令与脏路径，所以捕获绑定到版本而不是绑定到说法）：

- 审计：`python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"`，退出 0 = 谱系、全 Exception、协议设置、提示集哈希、报告行归属五项全绿。
- 负控：`bash "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_negative_control.sh"`，退出 0 = 干净报告通过、两处人为篡改都被拒。
- 已存捕获（文件名带短 revision，绑定到被审 revision `f60a028` 与 `report.html` 的 sha256 `e97af396da4d26bb…`）：`evidence/audit-f60a028-head-report.txt`（HEAD 报告，退出 0）、`evidence/negative-control-f60a028.txt`（退出 0，三处篡改全被拒）。

## 审计的负控能力：三处篡改都被拒

- 结论：把 `report.html` 与库各复制到临时目录后，①把 gemma-4-12b Q2 的 `0.0248`（它只存在于 `mpl-chat-nothink-greedy-768;ctx=4096;tmpl=unverified` 下）塞进同一模型的 `raw` 行，审计以 `MISMATCH: ('gemma-4-12b-it-UD-Q2_K_XL.gguf', 'raw', 'cpp', 0.0248, "no stored cell under this row's protocol label")` 退出 1；②把该模型 chat 行里印的 `(161)` 改成 `(160)`，审计以 `MISMATCH: (…, 'chat', 'cpp', 0.0186, 'printed n=160, artefact n=[161]')` 退出 1；③往库副本里给一个已存协议串追加 `;ctx=99999`，`[9]` 报 `RELABELLED: summary 'mpl-raw-greedy-768' -> stored 'multipl-e-raw-greedy-768;ctx=99999'` 并退出 1。干净报告退出 0。所以「一个格必须属于它自己那一行协议」「印出的题量必须等于产物的题量」「协议串不得丢或换设置」这三条不是靠断言，而是能失败的检查。
- 证据：三处篡改都只改临时副本（`mktemp -d`，库用 `sqlite3 .backup` 复制），不动真报告与真库；判据分别是 `[7]` 段把报告行的协议标签映射回库中该 (模型, 语言) 的协议再比对值与题量，与 `[9]` 段的全串比对。捕获 `evidence/negative-control-f60a028.txt`（退出 0）。
- 复算：`bash "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_negative_control.sh"`。

## 谱系：每个已入库的格都追到落盘产物

- 结论：库中 MultiPL-E 共 250 个格，其中 246 个有分数、4 个是 NULL；246 个有分数的格全部追到落盘产物——244 个命中 panel summary 的同语言同分值行，2 个只命中 per-item eval（它们的库值是修正后处理重判后的值，summary 里留的是旧判分），未追溯 0 个。
- 证据：两格 eval-only 是 `m26-q38-27b-q2-cpp_fixed_eval.json`（102/161=0.6335，summary 记 35/161）与 `m6b-g12b-q2-cpp_fixed_eval.json`（4/161=0.0248，summary 记 2/161）。题数来自 `n_items`：i02 已从产物回填（`migrate_db.py` 的 backfill），MultiPL-E 里仍有 6 格是 NULL——4 个 NULL 分的 js/rb 格与 m6b 的 2 个 chat cpp 格；满格题数为 cpp/py/js/rb 161、java 158、rs 155。
- 限制：summary 命中是按「同一个文件 + 同语言 + 同分值」核对的；summary 行的 `model` 是面板短名，它与库中 gguf 文件名的映射在 `migrate_db.py` 的 `MPL_MODELS`/各面板 model_map 里，本审计不重做这层映射。per-item eval 的配对键 `(语言, 通过数, 题数)` 同样不是模型唯一的：246 个格里 101 个只命中一份 eval、145 个命中多份（多份时报告只在状态直方图一致时才接受）。所以这两条都证明「该格的值确实在这份产物里」，不单独证明「这行属于这个模型文件」。
- 复算：审计脚本 `[1]` 段。

## 报告：报告印出的每个格都属于它自己那一行协议，且是库中已存的格

- 前提：本节数字来自 HEAD 里的 `report.html`（revision `f60a028`、sha256 `e97af396da4d26bb…`，与 `git show HEAD:report.html` 逐字节相同）。捕获 `evidence/audit-f60a028-head-report.txt` 的首部记着被审 revision、脚本 sha256、命令与脏路径，其中「审计读的那些路径」无未提交改动。
- 结论：`report.html` 第十三节（多语言代码）逐语言表现有 80 行（= 模型 × 协议标签）、188 个有值格，全部通过 `[7]` 的行归属检查（值在该行协议标签下存在、题量等于产物题量）；归属不符 0 格；题量比对了 186 格，另外 2 格因为报告不印 n 而跳过——正是 m6b 的 chat cpp 两格，它们在报告里印成 `(题量未知)`，即显式缺失而不是编出来的数字。
- 结论：库中按 (模型, 协议串, 语言) 有 194 个键，而报告逐语言表只印出 188 个有值格，装不下的就是标签碰撞：m31-topk 的协议串（`mpl-raw-t0.3-768;topk-set=…`）与 m27 的 `multipl-e-raw-t0.3-768` 渲染成同一个标签 `raw·temp=0.3`，于是 3 个模型 × 2 语言各有一行被并掉。其中 3 个键的两条记录值不同（m31 的 `top_k=1` 锚点等于贪心地板值），被并掉的那条值不再出现在报告里，见「表里被并掉的格」。
- 证据：逐语言表 80 行的有值格按列计为 cpp 78 / py 63 / js 21 / java 12 / rs 8 / rb 6，合计 188，与 `[7]` 打印的 `report cells read: 188` 相等；表头是 `模型文件 | 生成协议 | C++ | Python | JS | Java | Rust | Ruby`。
- 复算：审计脚本 `[7]` 与 `[10]` 段；逐列计数读同一张表的 `<td>` 即可，判据是每格以数字开头（`—` 与 `(题量未知)` 不计入）。

## 覆盖：canonical 协议下的语言矩阵与缺口登记

- 结论：`protocol='multipl-e-raw-greedy-768'` 下共 54 个模型，324 个 model×language 槽位里 150 个有分数、4 个是 NULL、170 个从未测过。逐语言：cpp 已测 52 / NULL 0 / 未测 2；py 51 / 0 / 3；js 21 / 2 / 31；java 12 / 0 / 42；rs 8 / 0 / 46；rb 6 / 2 / 46。
- 结论：有 cpp+py 对的 51 个模型；没有对的 3 个是 `Qwen3.5-2B-UD-IQ2_XXS`（只有 cpp）、`gemma-4-12b-it-UD-Q2_K_XL` 与 `gemma-4-12b-it-UD-Q3_K_XL`（raw 协议下只有 java/js/rs/rb，cpp 只在 chat 协议下跑过；这两格对应的 chat 对见「chat cpp 两格」，本节点只讲 raw 矩阵）。六种语言全测的 4 个是 `Qwen3.5-2B-UD-Q2_K_XL`、`Qwen3.5-2B-UD-Q3_K_XL`、`Qwen3.5-4B-UD-Q2_K_XL`、`Qwen3.5-4B-UD-Q3_K_XL`。
- 未测的理由（170 个空格）：都是「该模型所在的那些面板没有跑这个语言」，没有产物也没有失败记录，按规则记为显式未测而不是 0。java/rs/rb 的 134 个空格全部落在这个类里：跑过这些语言的面板只有 m1（六语言）、java 的 m6/m38/m51/m56/m57、js 的 m2/m3/m5/m6/m38/m51/m56/m57、rs 与 rb 的 m42/m54/m60；其余面板按设计只跑 cpp+py。
- 结论：4 个 NULL 空格不是未测而是被测过且整格全 `Exception`（见「4 个 NULL 格」）。
- 证据：语言集因模型而异的旧列不可比，是 i01 的判分审计节点登记的事实（i01 的 `res16`，其 home 随 i01 迁移到它自己的结果文档）；本节点只提供当前矩阵，不重复那条结论。
- 复算：审计脚本 `[2]` 段打印逐语言的 scored/NULL/absent 三元组与完整的 54 行矩阵（空格 = 未测，`NULL` = 整格全 Exception 记为缺失，数字 = 通过率）；语言→面板清单 `sqlite3 experiments.sqlite "SELECT DISTINCT language,run_tag FROM experiments WHERE bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768' AND language NOT IN ('cpp','py') ORDER BY language"`。

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
- 限制：这两格是 `[7]` 里唯一印 `(题量未知)` 的格（库中 `n_items` 为 NULL，回填没能从产物里对上），所以它们的题量在报告里缺席而不是猜成 161。
- 复算：`grep -n "n_ctx_slot" .wrapup/m6b.log | head -1`；`grep -n "jinja\|CTX=" .wrapup/run_m6b.sh .wrapup/run_m161_chat_py.sh .wrapup/run_m163_chat_cpp_12b.sh`；`sqlite3 experiments.sqlite "SELECT protocol,round(_score,4) FROM experiments WHERE run_tag='m6b-chat-gemma12b'"`。

## 4 个 NULL 格：整格全 Exception 记为缺失，证据是逐题状态而不是 summary

- 结论：gemma-4-12b Q2/Q3 的 js 格（`m51-gemma-java-js`）与 rb 格（`m54-gemma-rust-ruby`）是 NULL：这四格的 161 道题逐题状态全部是 `Exception`，harness 一次都没能执行完，按规则记为缺失，不是 0，也不进任何均值。注意 `m51_summary.jsonl` / `m54_summary.jsonl` 把这四格记成 `"score": 0.0`，所以 summary 不是 NULL 的证据；NULL 来自后续修复，证据是 per-item eval。
- 证据：`pan-gemma12b-q2-js_eval.json`、`pan-gemma12b-q3-js_eval.json`、`pan-gemma12b-q2-rb_eval.json`、`pan-gemma12b-q3-rb_eval.json` 各 161 题、`{'Exception': 161}`。
- 复算：审计脚本 `[4]` 段的 NULL 清单给出每格配对的 eval 文件名与状态直方图；或 `for f in .wrapup/mres/pan-gemma12b-q{2,3}-{js,rb}_eval.json; do python3 -c "import json,collections;d=json.load(open('$f'));print('$f',len(d['details']),dict(collections.Counter(x['status'] for x in d['details'])))"; done`。

## 8 个 0.0 格：6 个是长上下文生成失败的探针，2 个是真实计算的 0

- 结论：库里有 8 个格恰好是 0.0，分两类。第一类 6 个是 `m30-kv-ctx` 的 60 题探针格（Qwen3.5-2B Q3、cpp、ctx=16384 与 ctx=49152）：配对的 eval 显示 59–60/60 道题都是 SyntaxError，即生成在长前缀下被截断，这个 0 是生成失败的产物、不是整格 161 题上的模型分数；它们属于 a05 的 KV 轴，改值会改 a05 的结论，所以只登记不修改（见 `PLAN.md` 非目标）。第二类 2 个是 gemma-4-12b 在 raw 协议下的 java 0/158 与 rs 0/155，都是逐题算出来的真实通过数（java 158 道全是 SyntaxError、rs 154 SyntaxError + 1 Exception），即 raw 协议下 gemma 先输出散文的 harness floor，与 i01 的协议结论同向；它们不是 NULL，因为跑过了、只是没通过。
- 证据：m30 六格分别配对 `m30-ctx16384-kv*-cpp_eval.json`（`{SyntaxError: 59, Exception: 1}`）与 `m30-ctx49152-kv*-cpp_eval.json`（`{SyntaxError: 60}`）；gemma java 配对 `pan-gemma12b-q2-java_eval.json`（`{SyntaxError: 158}`，pass 0），rs 配对 `pan-gemma12b-q3-rs_eval.json`（`{SyntaxError: 154, Exception: 1}`，pass 0）。
- 复算：审计脚本 `[4]` 段的 0.0 清单；或 `for f in .wrapup/mres/m30-ctx*-cpp_eval.json .wrapup/mres/pan-gemma12b-q2-java_eval.json .wrapup/mres/pan-gemma12b-q3-rs_eval.json; do echo "$f $(python3 -c "import json,collections;d=json.load(open('$f'));print(len(d['details']),d.get('pass'),dict(collections.Counter(x['status'] for x in d['details'])))")"; done`。

## 两语言分歧：拆列的依据

- 结论：51 个同时有 cpp 与 py 的模型里，py−cpp 的差值最小 −0.2671、中位数 +0.0186、最大 +0.1863，其中 29 个模型的 |差值|>0.05；两语言对 169/1275 对模型（13.3%）给出严格相反的次序，另有 13 对在至少一种语言上打平。这是 meta 裁决「标准列的 MultiPL-E 格拆成 C++ 与 Python 两列」的依据（`PLAN.md`「已裁决」），i02 已落地并提交（见「标准列已拆成 C++ 与 Python 两列」）。
- 撤回：早先报给 meta 的 566/1275 作废。错因是拿两个已排好序的列表按模型名逐个比对，而不是逐对比较差值符号；同一批数据按严格相反得 169/1275、把打平也算进去得 182、按秩反转得 177，三种口径里没有 566。
- 证据：169/1275 是按「两个模型在两语言下的差值符号相反」逐对判定得到的；报告第十三节的逐语言表把同一模型的 raw/chat 分成两行、六种语言各占一列，行键是 (模型, 协议)，没有跨语言或跨协议的合并。
- 复算：审计脚本 `[5]` 段；或直接 `python3 -c "import sqlite3,itertools;con=sqlite3.connect('file:experiments.sqlite?mode=ro',uri=True);d={};[d.setdefault(m,{}).__setitem__(l,s) for m,l,s in con.execute(\"SELECT model,language,_score FROM experiments WHERE bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768' AND language IN ('cpp','py') AND _score IS NOT NULL\")];b=[(m,v['cpp'],v['py']) for m,v in d.items() if 'cpp' in v and 'py' in v];sg=lambda x:(x>0)-(x<0);print(len(b),sum(1 for (m1,c1,p1),(m2,c2,p2) in itertools.combinations(b,2) if sg(c1-c2)*sg(p1-p2)<0))"`；行键证据 `grep -n "cells.setdefault((model, proto)" make_report.py`（`table_mpl_langs`）。

## 标准列已拆成 C++ 与 Python 两列（已提交）

- 结论：HEAD（`f60a028`）的 `report.html` 里，8 个标准表各带「多语言代码 C++」与「多语言代码 Python」两列，带池化单列「多语言代码」的标准表为 0 个；两列的格直接来自库中对应语言的格，不再有 cpp+py 的加权均值。改法在 `make_report.py` 的 `LBL`（`multipl_e_cpp`/`multipl_e_py`）与 `.wrapup/mktables.py` 的 `BENCH`/`query_cells_by` 里，两者与 `report.html` 都已提交，所以干净 clone 能用 HEAD 的代码重建同一份报告。
- 证据：审计 `[8]` 段报 0 个池化表、8 个已拆表；`git diff HEAD -- make_report.py .wrapup/mktables.py report.html` 为空；`sha256sum report.html` = `e97af396da4d26bb…`，与 `git show HEAD:report.html | sha256sum` 相同。
- 复算：`python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"` 的 `[8]` 段；`grep -n "multipl_e_cpp" make_report.py`。

## 不混协议：行的身份由协议串决定

- 结论：报告的标准列取 MultiPL-E 时只读 `protocol='multipl-e-raw-greedy-768'`（`mktables.py::load_standard`），逐语言表的行键是 (模型, 协议标签)，所以采样温度、长上下文 KV、chat 三种设置不会进入同一格；取样轴的 (模型, 温度) / (模型, top_k) / (模型, 协议) 三组键在库中没有任何一个跨两个协议（0 个）。
- 结论：`[9]` 段比对 summary 行与库中协议串的**完整**字符串（`;` 后面的 `ctx=`、`kv=`、`tmpl=`、`fa=`、`prefix=`、`topk-set=` 全部参与，头部只在去掉 `-third-family-code` 这类面板名后比较，面板名记在 `run_tag` 里）：246 个格里 0 格无法解释地丢了或换了设置，另有 1 格是登记的例外。
- 例外：gemma-4-12b Q3 的 chat cpp 格，库里是 `mpl-chat-nothink-greedy-768;ctx=4096;tmpl=unverified`，而 summary 里同分值（130/161=0.8075）的那一行只写 `mpl-chat-nothink-greedy-768`。库里的串是对的：`.wrapup/m6b.log` 记着 `n_ctx_slot = 4096`，`.wrapup/run_m6b.sh` 启动时没有 `--jinja`，所以 ctx 与「模板未核对」这两段正是那次运行的设置，summary 少写了它们而不是库多写了。因此该格的值与协议串都不改库，例外在脚本的 `PROTOCOL_NOTE_EXCEPTIONS` 里逐键登记、每次运行都打印出来。
- 证据：`mktables.py::load_standard` 的 where 子句；`table_mpl_langs` 的行键；三组键的跨协议计数为 0；`[9]` 段对含 `;` 的 42 格做全串比对，唯一不一致就是上面的例外。
- 复算：`grep -n "bench_family='humaneval-multipl-e'" .wrapup/mktables.py`；审计脚本 `[2]`/`[9]` 段；负控的第三种污染往库里加一段 `;ctx=99999`，`[9]` 必须报 `RELABELLED` 并退出 1。

## 表里被并掉的格：3 个格的值被同一行标签遮住（open，归 i02）

- 结论：逐语言表的行键只有「模型 + 协议标签」，而 m31-topk 的协议串里被采样的那一维是 `top_k` 列、不在标签里，于是 m31 的 30 个格与 m27 同一模型的 2 个温度格撞成同一个标签 `raw·temp=0.3`：库中按 (模型, 协议串, 语言) 有 194 个键，报告只能印出 188 个格，合并掉的键里有 3 个两条记录的值不同（m31 的 `top_k=1` 锚点等于贪心地板值 0.1366/0.2422/0.2733，而 t0.3 采样是 0.1615/0.1739/0.3168），报告只能印出其中一条。
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
