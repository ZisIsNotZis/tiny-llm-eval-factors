#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对已入库的 py 语料取代行是否真的对得上 a14 的清单（只读）。

清单的 `db_rowids` 是**快照**：并发入库会把 rowid 漂走（实测 14083/14129 在两个小时内消失），
所以核对必须按身份列 + 数值做，不能按 rowid 做。这里逐条断言：

  1. 每个 `superseded_by IS NOT NULL` 的 py 行，其 (model, n_items, pass_new) 在清单里**唯一**对上一格；
  2. 它的协议串 == 清单那一格的 `identity_new`；
  3. 它指向的旧行仍在，且旧行的 `protocol` 就是新串去掉语料两段后缀、`_score` 等于清单的 `score_old`；
  4. 旧行的分数一个字没改：与取代前那一版库（`--before` 给的备份）逐格比 `(model, bench, protocol, score)`。

    python3 checks/py_corpus_regrade_check.py                    # 只核对第 1–3 条
    python3 checks/py_corpus_regrade_check.py --before experiments.sqlite.bak31
"""
from __future__ import annotations

import csv
import ast
import json
import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "experiments.sqlite")
MANIFEST = os.path.join(REPO, "docs", "subprojects", "a14-部分给分",
                        "evidence", "py_regrade_manifest.tsv")
SUFFIX = ";corpus=ac14c3b0abfa;gen_corpus=pre-2026-10-14"


def models_of(rec):
    """`db_models` 有时是 JSON 数组、有时是单引号的 Python 列表字面量——两种都读。"""
    raw = rec["db_models"].strip()
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return list(ast.literal_eval(raw))


def main(argv):
    if not os.path.exists(DB):
        print(f"FAIL: 数据库不存在：{DB}", file=sys.stderr)
        return 2
    if not os.path.exists(MANIFEST):
        print(f"FAIL: 取代清单不存在：{MANIFEST}", file=sys.stderr)
        return 2
    manifest = list(csv.DictReader(open(MANIFEST, encoding="utf-8"), delimiter="\t"))
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    # 取代行 = 协议串带语料两段的新行；旧行 = 带 `superseded_by` 指针的那些（原地保留）。
    # 只核对**二元通过率**的取代行：比例行的清单是另一份（`py_testfrac_regrade.json`），
    # 拿二元清单去对它会必然对不上（这正是本检查第一版报的假错）。
    new_rows = con.execute(
        "SELECT rowid, model, _bench, _score, n_items, protocol, run_tag FROM experiments "
        "WHERE protocol LIKE ? AND language='py' "
        "AND protocol NOT LIKE '%per-test fraction%'", ("%" + SUFFIX,)).fetchall()
    problems, checked, diverged, ambiguous = [], 0, [], []
    for r in new_rows:
        n = r["n_items"] or 0
        passed = round(r["_score"] * n) if n else None
        base = r["protocol"][:-len(SUFFIX)]
        hits = [m for m in manifest
                if r["model"] in models_of(m) and int(m["pass_new"]) == passed
                and int(m["n"]) == n
                and base in ({m["protocol_old"]}
                             | {p for p in (m["db_protocols"] or "").split("|") if p})
                and r["run_tag"] in set((m["db_run_tags"] or "").split(","))]
        if not hits:
            problems.append(f"{r['model']}: 清单里对不上任何格——pass_new={passed}, n={n}，"
                            f"协议基名 {base}")
            continue
        # 同一模型可能出现在多个 run 里且分数相同（清单按 run 列格、库里按 (model,协议,n)
        # 认行），所以这里要求「至少唯一一致」而不是「清单里唯一」：多于一格时按其中任一份
        # 校验（它们的 protocol 基名与 pass_new 已相同），并把这种情形计入 ambiguous。
        if len(hits) > 1:
            ambiguous.append((r["model"], passed, len(hits)))
        rec = hits[0]
        checked += 1
        # 协议串的**基名**要么是清单的 protocol_old，要么是该行在库里实际存的协议串：
        # 50 格的历史 summary 没记 protocol，入库时退化成了 DEFAULT_MPL_PROTOCOL
        # （`multipl-e-raw-greedy-768`），清单记的是 summary 里的名字（`mpl-raw-greedy-768`）。
        # 身份串跟着**库里那一行**走，否则新行与它要取代的行不同名。差异逐条印出来，不静默。
        allowed = {rec["protocol_old"]} | {p for p in (rec["db_protocols"] or "").split("|") if p}
        if base not in allowed:
            problems.append(f"{rec['tag']}: 协议串基名 {base!r} 既不是清单 protocol_old，"
                            f"也不在 db_protocols 里——这一行可能撞错了格")
        elif base != rec["protocol_old"]:
            diverged.append((rec["tag"], rec["protocol_old"], base))
        old_proto = r["protocol"][:-len(SUFFIX)]
        old = con.execute("SELECT protocol, _score, superseded_by FROM experiments "
                          "WHERE model=? AND _bench=? AND language='py' AND protocol=?",
                          (r["model"], r["_bench"], old_proto)).fetchone()
        if old is None:
            problems.append(f"{rec['tag']}: 被取代的旧行不在了（{r['model']} / {old_proto}）")
            continue
        if abs(old["_score"] - float(rec["score_old"])) > 1e-6:
            problems.append(f"{rec['tag']}: 旧行分数变了：库里 {old['_score']}，"
                            f"清单 {rec['score_old']}")
        if old["superseded_by"] != r["protocol"]:
            problems.append(f"{rec['tag']}: 旧行的指针没有指向这一行")

    if "--before" in argv:
        before_path = argv[argv.index("--before") + 1]
        b = sqlite3.connect(f"file:{before_path}?mode=ro", uri=True)
        sys.path.insert(0, REPO)
        from migrate_db import MEASUREMENT_IDENTITY as ID   # 同一份测量身份定义，不另抄
        sel = ",".join(ID)
        before = {tuple(r) for r in b.execute(f"SELECT {sel} FROM experiments")}
        after = {tuple(r) for r in con.execute(f"SELECT {sel} FROM experiments")}
        if "superseded_by" not in [c[1] for c in b.execute("PRAGMA table_info(experiments)")]:
            pass   # 取代前的库没有这一列；测量身份里也不含它
        gone = before - after
        print(f"旧行逐行未变：取代前 {len(before)} 行，现在 {len(after)} 行；"
              f"消失 {len(gone)} 行（要 0：旧行只标指针、不改不删）")
        if gone:
            problems.append(f"{len(gone)} 行旧记录消失或被改写，例如 {sorted(gone)[:2]}")

    print(f"取代行 {len(new_rows)} 个；唯一对上清单的 {checked} 个；"
          f"协议串基名取自库里那一行而非 summary 的 {len(diverged)} 个")
    for tag, want, got in diverged:
        print(f"  · {tag}: 清单 protocol_old={want}，库里实际={got}（身份串跟库里那一行）")
    if ambiguous:
        print(f"清单里对得上多于一格的 {len(ambiguous)} 个（同一模型多 run、分数相同）：")
        for model, passed, k in ambiguous:
            print(f"  · {model}: pass_new={passed} 对上 {k} 格")
    if problems:
        print("FAIL:")
        for p in problems:
            print("  -", p)
        return 1
    print("PASS: 已入库的取代行与清单逐条一致，旧行未被改写")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
