#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「逐题产物全 Exception 却存了 0.0」的四行置 NULL。

a12 的规则是「全 Exception 记 NULL，不是 0」：harness 一次都没跑完，那不是一个 0 分，
是一个没测出来的格。m51/m54 面板把 gemma-4-12b 的 js/rb 写进
`mpl-raw-greedy-768-third-family-code` 时按 `npass/n` 存了 0.0，而同一次测量的 canonical
孪生行（`multipl-e-raw-greedy-768`）已经是 NULL，所以这四行是同一格两份副本里错的那一份。

判据（每条都可证伪，缺一条就中止，不写库）：

  * 行必须命中本文件写死的 rowid，且协议串、模型、语言、分值逐项相符；
  * 该行配对的逐题产物必须是全 `Exception`，且题量与满格一致；
  * canonical 孪生行必须存在且已是 NULL（这是「同一格」的一致性证据）。

    迁移只按 rowid 精确命中，不用「所有 0.0」这种宽条件：m30 探针格与 12b 的 java/rs 也是
    0.0，但它们的逐题产物不是全 Exception（59–60/60 SyntaxError、158/158 SyntaxError、
    154 SyntaxError + 1 Exception），是真实算出来的 0，不能动。

    python3 migrations/null_all_exception_cells.py --dry-run   # 只核对并打印，不写库
    python3 migrations/null_all_exception_cells.py --apply     # 改库：先编号备份，再改

幂等：只更新「仍等于 0.0」的目标行，第二次跑改动 0 行。
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "experiments.sqlite")
sys.path.insert(0, REPO)
import migrate_db  # noqa: E402  编号备份与它的可用性门禁只有这一份实现

THIRD_FAMILY = "mpl-raw-greedy-768-third-family-code"
CANONICAL = "multipl-e-raw-greedy-768"
FULL_CELL_N = 161

# rowid -> (模型文件, 语言, 逐题产物)。写死而不是用谓词选：见模块注释。
TARGETS = {
    12015: ("gemma-4-12b-it-UD-Q2_K_XL.gguf", "js", "pan-gemma12b-q2-js_eval.json"),
    12017: ("gemma-4-12b-it-UD-Q3_K_XL.gguf", "js", "pan-gemma12b-q3-js_eval.json"),
    12029: ("gemma-4-12b-it-UD-Q2_K_XL.gguf", "rb", "pan-gemma12b-q2-rb_eval.json"),
    12031: ("gemma-4-12b-it-UD-Q3_K_XL.gguf", "rb", "pan-gemma12b-q3-rb_eval.json"),
}


def histogram(eval_file):
    """{'Exception': 161} 这样的状态直方图，或 None（产物缺失/读不动）。"""
    path = os.path.join(REPO, ".wrapup", "mres", eval_file)
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return collections.Counter(x.get("status") for x in d.get("details", [])), d.get("n")


def check(con):
    """每一行的判据；返回 [(rowid, 当前状态, 说明)]，任一不满足就返回 errors。"""
    errors, rows = [], []
    for rowid, (model, lang, eval_file) in sorted(TARGETS.items()):
        got = con.execute("SELECT model, language, protocol, _score, n_items FROM experiments "
                          "WHERE rowid = ?", (rowid,)).fetchone()
        if got is None:
            errors.append("rowid %d 不存在" % rowid)
            continue
        g_model, g_lang, g_proto, g_score, g_n = got
        if (g_model, g_lang, g_proto) != (model, lang, THIRD_FAMILY):
            errors.append("rowid %d 是 %r 而不是 (%r, %r, %r)"
                          % (rowid, got[:3], model, lang, THIRD_FAMILY))
            continue
        if g_score is not None and g_score != 0.0:
            errors.append("rowid %d 的分值是 %r，既不是 0.0 也不是 NULL" % (rowid, g_score))
            continue
        hist, n = histogram(eval_file)
        if hist is None:
            errors.append("rowid %d 的逐题产物 %s 缺失" % (rowid, eval_file))
            continue
        if set(hist) != {"Exception"} or n != FULL_CELL_N:
            errors.append("rowid %d 的逐题产物 %s 直方图 %s / n=%s，不是全 Exception 的满格"
                          % (rowid, eval_file, dict(hist), n))
            continue
        twin = con.execute("SELECT _score FROM experiments WHERE model = ? AND language = ? "
                           "AND protocol = ?", (model, lang, CANONICAL)).fetchall()
        if not twin:
            errors.append("rowid %d 的 canonical 孪生行不存在（%s %s %s）"
                          % (rowid, model, lang, CANONICAL))
            continue
        if any(s is not None for (s,) in twin):
            errors.append("rowid %d 的 canonical 孪生行分值不是 NULL：%s"
                          % (rowid, [s for (s,) in twin]))
            continue
        rows.append((rowid, model, lang, g_score, eval_file, dict(hist)))
    return rows, errors


def post_assertions(con):
    """改完之后必须成立的三条；返回 [(说明, 实际值)]。"""
    out = []
    out.append(("目标行全部为 NULL",
                con.execute("SELECT COUNT(*) FROM experiments WHERE rowid IN (%s) "
                            "AND _score IS NOT NULL" % ",".join(str(r) for r in TARGETS)).fetchone()[0]))
    # This is the form the acceptance asked for.  It reaches 0 only when the other
    # third-family rows (12b java/rs) also get n_items backfilled; they are legitimately
    # scored (158 SyntaxError, 154 SyntaxError + 1 Exception) and their missing n_items is
    # the backfill's gap, not a score defect, so this repair leaves the count at 4 and
    # says so instead of widening its own condition.
    out.append(("third-family 里「有分数、n_items 仍 NULL」的行（其中 4 行是本次修掉的，"
                "其余是 n_items 回填缺口）",
                con.execute("SELECT COUNT(*) FROM experiments WHERE protocol = ? "
                            "AND _score IS NOT NULL AND n_items IS NULL",
                            (THIRD_FAMILY,)).fetchone()[0]))
    out.append(("行数", con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="改库：先编号备份再更新")
    ap.add_argument("--dry-run", action="store_true", help="只核对，不写库")
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        ap.error("给 --dry-run 或 --apply")

    con = sqlite3.connect(DB)
    before_rows = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    rows, errors = check(con)
    for rowid, model, lang, score, eval_file, hist in rows:
        print("  rowid %d  %-34s %-2s  _score=%r -> NULL  (%s %s)"
              % (rowid, model, lang, score, eval_file, hist))
    if errors:
        for e in errors:
            print("  GUARD FAILED: %s" % e)
        print("ABORT: 判据不满足，未写库")
        con.close()
        return 1

    todo = [r[0] for r in rows if r[3] is not None]
    print("目标行 %d，本次要改 %d（已是 NULL 的跳过）" % (len(rows), len(todo)))
    if not args.apply:
        print("dry-run: 未写库")
        con.close()
        return 0

    con.close()
    backup, backup_rows = migrate_db.numbered_backup(DB)
    print("备份: %s（%d 行，可用性已由 assert_backup_usable 核对）" % (backup, backup_rows))

    con = sqlite3.connect(DB)
    changed = 0
    for rowid in todo:
        cur = con.execute("UPDATE experiments SET _score = NULL WHERE rowid = ? AND _score = 0.0",
                          (rowid,))
        changed += cur.rowcount
    con.commit()
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    after_rows = con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    print("改为 NULL 的行: %d；integrity_check: %s；行数 %d -> %d"
          % (changed, integrity, before_rows, after_rows))
    for label, value in post_assertions(con):
        print("  %s: %s" % (label, value))
    con.close()

    check_rc = subprocess.call([sys.executable, os.path.join(REPO, "checks", "db_check.py"),
                                "--quiet"])
    print("db_check exit=%d" % check_rc)

    if changed != len(todo) or integrity != "ok" or before_rows != after_rows or check_rc != 0:
        print("FAIL: 迁移没有达到它声明的后果")
        return 1
    print("PASS: 四行已按规则置 NULL，行数不变，库结构完好")
    return 0


if __name__ == "__main__":
    sys.exit(main())
