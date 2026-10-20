#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回填 `experiments.n_items`：只从产物推导，推不出就留 NULL 并给出原因。

本仓 AGENTS.md 要求「不留 NULL 必填字段」；已评分但没有题量的行会让 item 级 SE 无法从库本身
算出来。这里按族逐条回填，每条规则都有一个**可证伪的判据**，不是默认值：

  * `humaneval-multipl-e`：用 `report_inputs/eval_status.n_for(lang, score, hints)`，其中 hints 来自
    该行自己的协议串（`ctx=`、`kv=`）。产物给不出唯一 n 就留空。
  * `humaneval` / `mbpp`（EvalPlus）：题量是 harness 常量（164 / 378），只有当分数**恰好**等于
    `k/n`（k 为整数）时才认——这就是判据；被 `--limit` 截过的运行会不满足，因此留空。
  * `bfcl` / `bfcl-multiturn`：读该 run 的 `*_summary.jsonl` 的 `per_category[类别]`，类别与 `acc`
    都要对上，取那一条的 `n`。BFCL 只有类别级数据，**micro 需要逐题结果，库里没有**。
  * `testfrac`：读 `m41_summary.jsonl` 的 `(lang, mean_frac)`，与分数逐位相同才取它的 `n`。
  * 其余族：留 NULL，并在输出里按族列出原因。

幂等：只更新 `n_items IS NULL` 的行，第二次跑改动 0 行。

    python3 migrations/backfill_n_items.py --dry-run   # 只算并打印，不写库
    python3 migrations/backfill_n_items.py --apply     # 改库：前后各一次带 WAL 的备份
    python3 migrations/backfill_n_items.py --trace PATH # 逐行溯源表（rowid/family/bench/score/n/来源）
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "experiments.sqlite")
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "report_inputs"))
import eval_status  # noqa: E402
import migrate_db  # noqa: E402

EVALPLUS_N = {"humaneval": 164, "mbpp": 378}


def is_exact_fraction(score, n):
    """分数是否恰好是 k/n —— 是则 n 是这一行的题量，不是我们填的默认值。"""
    return abs(round(score * n) / n - score) < 1e-12


def load_summaries():
    """{basename: [record, ...]}，覆盖 .wrapup/*_summary.jsonl。"""
    out = collections.defaultdict(list)
    for path in glob.glob(os.path.join(REPO, ".wrapup", "*_summary.jsonl")):
        base = os.path.basename(path)
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                out[base].append(json.loads(line))
            except Exception:
                continue
    return out


def bfcl_n(records, bench, score):
    """BFCL 行：类别级 n（`per_category[类别].n`），类别与 acc 都要对上。"""
    cat = bench[len("bfcl-"):] if bench.startswith("bfcl-") else bench
    for rec in records:
        per = rec.get("per_category")
        if not isinstance(per, dict):
            continue
        item = per.get(cat)
        if isinstance(item, dict) and item.get("n") and item.get("acc") is not None \
                and abs(item["acc"] - score) < 5e-4:
            return int(item["n"]), f"per_category[{cat}].n"
    return None, ""


def testfrac_n(records, language, score):
    for rec in records:
        if rec.get("lang") == language and rec.get("mean_frac") is not None \
                and abs(rec["mean_frac"] - score) < 1e-9 and rec.get("n"):
            return int(rec["n"]), "summary.mean_frac"
    return None, ""


def derive(row, summaries):
    """(n, 来源说明) —— n 为 None 时第二项是原因。"""
    _rowid, model, bench, family, score, protocol, language, source = row
    if family == "humaneval-multipl-e":
        n = eval_status.n_for(language, score, eval_status.hints_from_label(protocol or ""))
        return (n, "eval_status.n_for") if n else (None, "产物无法唯一配对")
    if family in EVALPLUS_N:
        n = EVALPLUS_N[family]
        return (n, f"harness 常量且 score==k/{n}") if is_exact_fraction(score, n) \
            else (None, f"score 不是 k/{n}（该行可能被 --limit 截过）")
    if family == "bfcl-multiturn":
        return None, "多轮类别（multi_turn_*）不在任何 *_summary.jsonl 的 per_category 里"
    if family == "bfcl":
        recs = summaries.get(source or "", []) or [
            r for v in summaries.values() for r in v]
        n, how = bfcl_n(recs, bench, score)
        return (n, f"{source or '任意 summary'}:{how}") if n else (None, "类别级产物无法配对")
    if family == "testfrac":
        n, how = testfrac_n(summaries.get(source or "", []), language, score)
        return (n, f"{source}:{how}") if n else (None, "m41 汇总无法配对")
    return None, f"没有该族的题量产物（family={family or '空'}）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写库（前后各一次备份）")
    ap.add_argument("--dry-run", action="store_true", help="只算并打印")
    ap.add_argument("--trace", help="把逐行溯源写成 TSV")
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        ap.error("选择 --apply 或 --dry-run")

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT rowid, model, _bench, bench_family, _score, protocol, language, source_file "
        "FROM experiments WHERE _score IS NOT NULL AND n_items IS NULL").fetchall()
    families = dict(con.execute(
        "SELECT COALESCE(bench_family,'<空>'), COUNT(*) FROM experiments "
        "WHERE _score IS NOT NULL AND n_items IS NULL GROUP BY 1").fetchall())
    con.close()
    print(f"rows with a score but no n_items: {len(rows)}  {families}")

    summaries = load_summaries()
    plan, unsolved, tally = [], collections.Counter(), collections.Counter()
    for row in rows:
        n, why = derive(row, summaries)
        if n:
            plan.append((row[0], n, why))
            tally[(row[3] or "<空>", why, n)] += 1
        else:
            unsolved[(row[3] or "<空>", why)] += 1

    print(f"\nresolvable: {len(plan)}  仍留 NULL: {sum(unsolved.values())}")
    for (fam, how, n), c in sorted(tally.items()):
        print(f"  fill {c:>5}  family={fam:<20} n={n:<5} via {how}")
    if unsolved:
        print(" 仍为 NULL（按族与原因）:")
        for (fam, why), c in sorted(unsolved.items()):
            print(f"  null {c:>5}  family={fam:<20} {why}")
        by_fam = collections.Counter()
        for (fam, _why), c in unsolved.items():
            by_fam[fam] += c
        print(f" 合计留 NULL: {sum(by_fam.values())}  {dict(sorted(by_fam.items()))}")

    if args.trace:
        with open(args.trace, "w", encoding="utf-8") as fh:
            fh.write("rowid\tfamily\tmodel\tbench\tscore\tn\tsource\n")
            for row in rows:
                n, why = derive(row, summaries)
                fh.write("\t".join(str(x) for x in
                                   (row[0], row[3] or "", row[1], row[2], row[4],
                                    n if n else "", why)) + "\n")
        print(f"trace written: {os.path.relpath(args.trace, REPO)}")

    if not args.apply:
        return 0

    print("\n== backup before ==")
    migrate_db.numbered_backup(DB)
    con = sqlite3.connect(DB)
    changed = 0
    for rowid, n, _why in plan:
        changed += con.execute(
            "UPDATE experiments SET n_items=? WHERE rowid=? AND n_items IS NULL",
            (n, rowid)).rowcount
    con.commit()
    left = con.execute("SELECT COUNT(*) FROM experiments WHERE _score IS NOT NULL "
                       "AND n_items IS NULL").fetchone()[0]
    ic = con.execute("PRAGMA integrity_check").fetchone()[0]
    con.close()
    print(f"updated rows: {changed}; still NULL: {left}; integrity={ic}")
    print("== backup after ==")
    migrate_db.numbered_backup(DB)
    print("\nnext: python3 checks/db_check.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
