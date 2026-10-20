# a12 多语言代码 MultiPL-E — 结果

本文件是本子项目结果层的唯一 home。每条事实写成「结论 / 证据 / 复算」，数字的当前值只在这里；报告里的图与表由数据库重新生成，不引用本文件的数值。
数据源：`experiments.sqlite`（只读打开），产物源：`.wrapup/*_summary.jsonl` 与 `.wrapup/mres/*_eval.json`。
一次跑完全部检查：`python3 "docs/subprojects/a12-多语言代码 MultiPL-E/mpl_cell_audit.py"`（退出 0 = 谱系、全 Exception、提示集哈希、报告格入库四项全绿）。

## 谱系：每个已入库的格都追到落盘产物

- 结论：库中 MultiPL-E 共 248 个格，其中 244 个有分数、4 个是 NULL；244 个有分数的格全部追到落盘产物——242 个命中 panel summary 的同语言同分值行，2 个只命中 per-item eval（它们的库值是修正后处理重判后的值，summary 里留的是旧判分），未追溯 0 个。
- 证据：两格 eval-only 是 `m26-q38-27b-q2-cpp_fixed_eval.json`（102/161=0.6335，summary 记 35/161）与 `m6b-g12b-q2-cpp_fixed_eval.json`（4/161=0.0248，summary 记 2/161）。MultiPL-E 行不带 `n_items`，题数只能从 summary 取，满格题数为 cpp/py/js/rb 161、java 158、rs 155。
- 限制：summary 命中是按「同一个文件 + 同语言 + 同分值」核对的；summary 行的 `model` 是面板短名，它与库中 gguf 文件名的映射在 `migrate_db.py` 的 `MPL_MODELS`/各面板 model_map 里，本审计不重做这层映射，所以它证明「该格的值确实在这份产物里」，不单独证明「这行属于这个模型文件」。
- 复算：审计脚本 `[1]` 段。

## 报告：报告印出的每个格都是库中已存的格

- 结论：`report.html` 第十三节（多语言代码）逐语言表共 83 行（= 模型 × 生成协议）、192 个有值格；这 192 个 (模型, 语言, 分数) 全部能在库中找到，没有一个数字是报告独有的。
- 证据：报告覆盖行自报 cpp 79 / py 66 / js 21 / java 12 / rs 8 / rb 6，合计 192；报告 mtime 晚于数据库 mtime。
- 复算：审计脚本 `[7]` 段；或 `python3 -c "import re;h=open('report.html',encoding='utf-8').read();i=h.find('<th>模型文件</th><th>生成协议</th>');print(h[i:i+400])"`。

## 覆盖：canonical 协议下的语言矩阵与缺口登记

- 结论：`protocol='multipl-e-raw-greedy-768'` 下共 54 个模型，324 个 model×language 槽位里 150 个有分数、4 个是 NULL、170 个从未测过。逐语言：cpp 已测 52 / NULL 0 / 未测 2；py 51 / 0 / 3；js 21 / 2 / 31；java 12 / 0 / 42；rs 8 / 0 / 46；rb 6 / 2 / 46。
- 结论：有 cpp+py 对的 51 个模型；没有对的 3 个是 `Qwen3.5-2B-UD-IQ2_XXS`（只有 cpp）、`gemma-4-12b-it-UD-Q2_K_XL` 与 `gemma-4-12b-it-UD-Q3_K_XL`（raw 协议下只有 java/js/rs/rb，cpp 只在 m6b 的 chat 协议下跑过）。六种语言全测的 4 个是 `Qwen3.5-2B-UD-Q2_K_XL`、`Qwen3.5-2B-UD-Q3_K_XL`、`Qwen3.5-4B-UD-Q2_K_XL`、`Qwen3.5-4B-UD-Q3_K_XL`。
- 未测的理由（170 个空格）：都是「该模型所在的那些面板没有跑这个语言」，没有产物也没有失败记录，按规则记为显式未测而不是 0；其中 java/rs/rb 的 134 个空格全部落在这个类里，因为绝大多数面板只跑 cpp+py 两种语言，语言扩展面板只有 m1/m2/m3/m5/m6/m10（cpp/py/js/java）与 m38/m42/m51/m54/m56/m57/m60（成对的语言）。
- 结论：4 个 NULL 空格不是未测而是被测过且整格全 `Exception`（见「4 个 NULL 格」）。
- 证据：语言集因模型而异的旧列不可比，是 i01 的判分审计节点登记的事实（i01 的 `res16`，其 home 随 i01 迁移到它自己的结果文档）；本节点只提供当前矩阵，不重复那条结论。
- 复算：审计脚本 `[2]` 段打印逐语言的 scored/NULL/absent 三元组与完整的 54 行矩阵（空格 = 未测，`NULL` = 整格全 Exception 记为缺失，数字 = 通过率）。

## 覆盖：chat 协议只覆盖 cpp 与 py，24 个槽位显式未测

- 结论：chat 生成协议下只有 12 个格，覆盖 6 个模型 × cpp/py 两种语言；这 6 个模型的 36 个 model×language 槽位里，js / java / rs / rb 的 24 个从未测过，理由与 `PLAN.md` 非目标一致：非 cpp/py 语言的判分有效性还没有 i01 的审计，24 格也超出 9% 的 GPU 份额。gemma-4-12b 的 cpp 槽位已在补测计划里（`PLAN.md` 的 `WP5`）。
- 证据：chat 协议串共两种：`mpl-chat-nothink-greedy-768`（10 格）与 `mpl-chat-nothink-greedy-768;ctx=4096;tmpl=unverified`（2 格）。
- 复算：审计脚本 `[3]` 段，含 `unmeasured under chat: 24 of 36` 一行。

## chat 面板的逐格值（m161）

- 结论：里程碑 m161 的 7 个 chat 格（`mpl-chat-nothink-greedy-768`，n=161）为：Qwen3.8-27B Q3 cpp 140/161=0.8696（端到端控制格）、Qwen3.8-27B Q2 py 121/161=0.7516、Qwen3.8-27B Q3 py 145/161=0.9006、gemma-4-12b Q2 py 77/161=0.4783、gemma-4-12b Q3 py 93/161=0.5776、gemma-4-26B-A4B Q2 py 2/161=0.0124、gemma-4-26B-A4B Q3 py 1/161=0.0062。
- 证据：gemma-4-26B 的两个 py 格由 `Exception` 主导（159/161、160/161），成因是模型把函数体首行写在第 0 列，而 harness 不重排缩进（`strip_fences` 只剥行首围栏、保留缩进），拼接后必然是 IndentationError；每格「首行在第 0 列的完成物条数」与该格 Exception 条数逐格相等（159=159、160=160），同为 py 的 Qwen3.8-27B Q3 格只有 2/161 首行列 0、得分 0.9006，所以是模型行为而不是 harness 剥离。
- 复算：`for c in m161-g26b-q2-py-chat m161-g26b-q3-py-chat m161-q38-27b-q3-py-chat; do printf "%s firstcol0=%s\n" "$c" "$(jq -r '.completion|split("\n")[0]' .wrapup/mres/$c.jsonl | grep -c '^[^[:space:]]')"; done`；`jq -r '.details[]|select(.status=="Exception")|.name' .wrapup/mres/m161-g26b-q2-py-chat_eval.json | wc -l`。

## gemma-4-12b 的 cpp 格走另一套协议串（ctx=4096、模板未核对）

- 结论：gemma-4-12b chat cpp（m6b 面板）入库时按协议串原样记录，末尾带 `;ctx=4096;tmpl=unverified`：Q2 `4/161=0.0248`、Q3 `130/161=0.8075`。同批 py 格不并入任何 cpp/py 对：m6b 是 `ctx=4096` 且没有 `--jinja`、模板路径未核对的一套配置，而 m161 用 `ctx=2048 --jinja` 把 12b 的 py 重测成 Q2 0.4783、Q3 0.5776，所以 12b 在任何单一协议下都没有 cpp+py 对，它的标准列格是缺失而不是低分。
- 证据：`.wrapup/m6b.log` 有 `n_ctx_slot = 4096`；`.wrapup/run_m6b.sh` 的 start_server 无 `--jinja`；`.wrapup/run_m161_chat_py.sh` 是 `CTX=${CTX:-2048}` 加 `--jinja`。m6b 的 summary 留的是旧判分值（Q2 cpp 2/161、Q3 py 5/161），库值取自 `_fixed` 重判，两者的差由旧后处理解释，不由本节点裁决。m161 日志记下了所用提示集的哈希，与 `.wrapup/prompts/SHA256SUMS` 的 `humaneval-cpp.jsonl` 行一致。
- 复算：`grep -n "n_ctx_slot" .wrapup/m6b.log | head -1`；`grep -n "jinja\|CTX=" .wrapup/run_m6b.sh .wrapup/run_m161_chat_py.sh`；`sqlite3 experiments.sqlite "SELECT protocol,round(_score,4) FROM experiments WHERE run_tag='m6b-chat-gemma12b'"`。

## 4 个 NULL 格：整格全 Exception 记为缺失

- 结论：gemma-4-12b Q2/Q3 的 js 格（`m51-gemma-java-js`）与 rb 格（`m54-gemma-rust-ruby`）是 NULL——整格每道题都抛异常，按规则记为缺失，不是 0，也不进任何均值。
- 证据：`.wrapup/m51_summary.jsonl`、`.wrapup/m54_summary.jsonl` 对应行的 score 为空；库中这 4 行 `_score IS NULL`。
- 复算：审计脚本 `[4]` 段；`sqlite3 experiments.sqlite "SELECT model,language,run_tag FROM experiments WHERE bench_family='humaneval-multipl-e' AND _score IS NULL"`。

## 8 个 0.0 格：6 个是长上下文生成失败，2 个是 raw 协议下的计算值

- 结论：库里有 8 个格恰好是 0.0，分两类。第一类 6 个是 `m30-kv-ctx` 的 60 题探针格（Qwen3.5-2B Q3、cpp、ctx=16384 与 ctx=49152）：配对的 eval 显示 59–60/60 道题都是 SyntaxError，即生成在长前缀下被截断，这个 0 是生成失败的产物而不是模型分数；它们属于 a05 的 KV 轴，改值会改 a05 的结论，所以只登记不修改（见 `PLAN.md` 非目标）。第二类 2 个是 gemma-4-12b 在 raw 协议下的 java 0/158 与 rs 0/155，是真实的通过数计算值，表现为 raw 协议下 gemma 先输出散文的 harness floor，与 i01 的协议结论同向。
- 证据：配对 eval 分别是 `m30-ctx16384-kv*-cpp_eval.json`（`{SyntaxError: 59, Exception: 1}`）与 `m30-ctx49152-kv*-cpp_eval.json`（`{SyntaxError: 60}`）；gemma 的 rs 格配对到 `pan-gemma12b-q3-rs_eval.json`（`{SyntaxError: 154, Exception: 1}`），java 格没有对应的 per-item eval，值取自 summary。
- 复算：审计脚本 `[4]` 段；`for f in .wrapup/mres/m30-ctx*-cpp_eval.json; do echo "$f $(python3 -c "import json,sys,collections;d=json.load(open('$f'));print(len(d['details']),d.get('pass'),dict(collections.Counter(x['status'] for x in d['details'])))")"; done`。

## 两语言分歧：cpp+py 的均值会掩盖语言层面的排序

- 结论：51 个同时有 cpp 与 py 的模型里，py−cpp 的差值最小 −0.2671、中位数 +0.0186、最大 +0.1863，其中 29 个模型的 |差值|>0.05；两语言对 169/1275 对模型（13.3%）给出严格相反的次序，另有 13 对在至少一种语言上打平。因此把两者加权成一个「多语言代码」格会掩盖语言层面的次序反转，标准列按 meta 的裁决拆成 C++ 与 Python 两列（`PLAN.md`「已裁决」）。
- 证据：169/1275 是按「两个模型在两语言下的差值符号相反」逐对判定得到的；报告第十三节的逐语言表把同一模型的 raw/chat 分成两行、六种语言各占一列，行键是 (模型, 协议)，没有跨语言或跨协议的合并，所以逐语言的当前值在报告里本就可读。
- 复算：审计脚本 `[5]` 段；或直接 `python3 -c "import sqlite3,itertools;con=sqlite3.connect('file:experiments.sqlite?mode=ro',uri=True);d={};[d.setdefault(m,{}).__setitem__(l,s) for m,l,s in con.execute(\"SELECT model,language,_score FROM experiments WHERE bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768' AND language IN ('cpp','py') AND _score IS NOT NULL\")];b=[(m,v['cpp'],v['py']) for m,v in d.items() if 'cpp' in v and 'py' in v];sg=lambda x:(x>0)-(x<0);print(len(b),sum(1 for (m1,c1,p1),(m2,c2,p2) in itertools.combinations(b,2) if sg(c1-c2)*sg(p1-p2)<0))"`；行键证据 `grep -n "cells.setdefault((model, proto)" make_report.py`（`table_mpl_langs`）。

## 不混协议：标准列只取 canonical raw-greedy 协议

- 结论：报告的标准列取 MultiPL-E 时只读 `protocol='multipl-e-raw-greedy-768'`（`mktables.py::load_standard`），所以采样温度、长上下文 KV、chat 三种设置都不会进入同一格；轴的取样表也按 (模型, 温度) / (模型, top_k) / (模型, 协议) 建键，库中这三组没有任何一个键跨两个协议（0 个）。标准列的「多语言代码」格仍是 cpp+py 的加权均值，这一项与 AC 字面冲突，已交 meta 裁决（`PLAN.md`「待裁决」）。
- 证据：`mktables.py::load_standard` 的 where 子句；`table_mpl_langs` 的行键；三组 (模型, 参数) 键的跨协议计数为 0。
- 复算：`grep -n "bench_family='humaneval-multipl-e'" .wrapup/mktables.py`；审计脚本 `[5]` 段给语言池化的量化后果。

## 提示集与后处理已钉住

- 结论：提示集是 `.wrapup/prompts` 的 6 个文件，`SHA256SUMS` 6 个哈希全部匹配、0 漂移；后处理修正由 `.wrapup/test_mpl_postprocess.py` 的 5 个用例钉住，当前 5/5 通过。
- 证据：`sha256sum -c` 的等价检查在审计脚本 `[6]` 段；m161 日志首行记录了实际使用的提示集哈希，与 `SHA256SUMS` 的 `humaneval-cpp.jsonl` 行一致。
- 复算：`cd .wrapup/prompts && sha256sum -c SHA256SUMS`；`python3 .wrapup/test_mpl_postprocess.py`。

## 迁移到 Markdown 的后果与死引用

- 结论：本目录已改成 Markdown（`PLAN.md`/`RESULT.md`/`AGENTS.md`），迁移后的 `result.yaml` 已删除。报告生成器 `make_report.py::load_docs` 只读 `docs/subprojects/*/{plan,result}.yaml`，所以报告「客观结果（引自研究文档 L2）」列表不再列出 a12 的两条已测事实；这些事实的内容仍在报告的数据质量节正文里，当前值在 `RESULT.md`。要恢复那份列表，得让 `load_docs` 能读 Markdown，这是报告代码的改动（归 i02），不在 a12 目录内。
- 结论：`make_report.py` 的正文有 4 处引用写成 `docs/result/result.yaml::res5/res17b/res22/res24`，`STATUS.md`、`FINDINGS.md` 的引用同样指向 `docs/result/result.yaml` 与 `docs/plan/plan.yaml`；这些文件在 meta 迁移后已不存在。这是报告代码与根文档的死引用，a12 不改，登记给 meta。
- 证据：`grep -n "docs/result/result.yaml" make_report.py`；`git log --oneline -1` 指向 meta 的迁移提交。
- 复算：`grep -rn "docs/result/result.yaml::" make_report.py STATUS.md FINDINGS.md`；`grep -n "for path in sorted(glob.glob" make_report.py`。
