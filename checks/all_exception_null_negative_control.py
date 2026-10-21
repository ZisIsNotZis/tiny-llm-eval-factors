#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：全 Exception 的格在入库时写 NULL，不写 0.0（写侧保证，不是事后修缮）。

背景：`m51`/`m54` 的 summary 给「一个都没被判分」的格写了 `pass=0, score=0.0`，而同一测量的
canonical 孪生行是 `NULL`——同一格在库里存了两份，一份 0.0 一份 NULL。0.0 会被读成「测了，
一个都没通过」，那是把「没有测量」写成「测量结果是 0」（`@absent`）。

判据只认**全 Exception**：全 SyntaxError 是模型写不出能编译的代码，那是一次实测的 0
（`a05` 的加长前缀网格就靠它当楼层），不能一起抹成 NULL。

三例（都在**库副本**上跑，主库一行不动）：
  1. 全 Exception 的行 → 入库后 `_score` 必须是 NULL；
  2. 有通过也有 Exception 的行 → 必须写实测分数（不能被规则误伤）；
  3. summary 根本没记 `score` 的行 → NULL（不是 0）。
外加一条**差分**：把 `summary_score` 换成旧写法（原样写 `row["score"]`）再入库一次，
那三行必须是 `0.0 / 0.8075 / 崩溃或 0`——两条结果不同才说明这条规则在承重，而不是恰好都通过。
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "experiments.sqlite"
sys.path.insert(0, str(REPO))
import migrate_db as M  # noqa: E402

PROBE_MODEL = "Qwen3.5-2B-UD-Q3_K_XL.gguf"
PROBE_TAG = "i02-probe-all-exception"
PROBE_SRC = "i02_probe_summary.jsonl"


def copy_db(src: Path, dst: Path):
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(dst)
    with d:
        s.backup(d)
    d.close()
    s.close()


def main() -> int:
    if not DB.exists():
        print(f"FAIL: 数据库不存在：{DB}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="all-exception-control-"))
    try:
        copy = tmp / "experiments.sqlite"
        copy_db(DB, copy)
        summary = tmp / PROBE_SRC
        rows = [
            # 1) 全 Exception：161 题一条都没判出来
            {"model": "gemma12b-q2", "lang": "js", "n": 161, "pass": 0, "score": 0.0,
             "statuses": {"Exception": 161}, "protocol": "i02-probe-all-exception-js"},
            # 2) 有通过也有 Exception：实测 130/161
            {"model": "gemma12b-q2", "lang": "cpp", "n": 161, "pass": 130,
             "score": 130 / 161, "statuses": {"OK": 130, "Exception": 31},
             "protocol": "i02-probe-all-exception-cpp"},
            # 3) 根本没记分数
            {"model": "gemma12b-q2", "lang": "java", "n": 158, "pass": 0,
             "statuses": {"Exception": 5, "SyntaxError": 153},
             "protocol": "i02-probe-all-exception-java"},
        ]
        summary.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

        con = sqlite3.connect(copy)
        con.row_factory = sqlite3.Row
        M.INGEST_SKIPS.clear()
        n = M.ingest_mpl(con, str(summary), PROBE_TAG, PROBE_SRC,
                         model_map={"gemma12b-q2": PROBE_MODEL})
        con.commit()
        got = {r["language"]: r["_score"] for r in con.execute(
            "SELECT language, _score FROM experiments WHERE run_tag=?", (PROBE_TAG,))}
        con.close()
        print(f"0) 入库 {n} 行：" + ", ".join(f"{k}={v}" for k, v in sorted(got.items())))

        problems = []
        if got.get("js") is not None:
            problems.append(f"全 Exception 的格写成了 {got.get('js')}，应为 NULL")
        if got.get("cpp") is None or abs(got["cpp"] - 130 / 161) > 1e-9:
            problems.append(f"有通过的格写成了 {got.get('cpp')}，应为实测 130/161")
        if "java" not in got or got["java"] is not None:
            problems.append(f"没记分数的格写成了 {got.get('java')}，应为 NULL")
        if len(got) != 3:
            problems.append(f"探针只入 {len(got)} 行（应 3 行）")

        print(f"1) 全 Exception → NULL        : {got.get('js') is None}")
        print(f"2) 有通过 → 实测 0.8075       : {got.get('cpp') is not None and abs(got['cpp'] - 130 / 161) < 1e-9}")
        print(f"3) 没记分数 → NULL            : {'java' in got and got['java'] is None}")
        if problems:
            print("FAIL:")
            for p in problems:
                print("  -", p)
            return 1

        # 差分：同一份 summary 走旧写法（原样写 score）必须写出 0.0——否则这条控制分不出新旧。
        old_copy = tmp / "experiments-naive.sqlite"
        copy_db(DB, old_copy)
        con = sqlite3.connect(old_copy)
        con.row_factory = sqlite3.Row
        saved = M.summary_score
        M.summary_score = lambda row, key: row.get("score")      # 旧行为
        try:
            M.ingest_mpl(con, str(summary), PROBE_TAG + "-naive", PROBE_SRC,
                         model_map={"gemma12b-q2": PROBE_MODEL})
            con.commit()
            naive = {r["language"]: r["_score"] for r in con.execute(
                "SELECT language, _score FROM experiments WHERE run_tag=?",
                (PROBE_TAG + "-naive",))}
        finally:
            M.summary_score = saved
            con.close()
        print(f"4) 旧写法（原样写 score）     : js={naive.get('js')}（要 0.0，说明这条规则在承重）")
        if naive.get("js") != 0.0:
            print("FAIL: 旧写法也没写出 0.0——这条控制区分不出规则有没有生效")
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
