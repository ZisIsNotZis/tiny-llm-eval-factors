#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：`ingest_mpl` 必须逐行尊重 summary 的协议串，缺字段时才退回默认值并明说。

来由：这个函数曾把 `protocol` 写死成 `multipl-e-raw-greedy-768`，于是 `m29_summary.jsonl` 里
`mpl-raw-greedy-768;fa=on,kv=q8_0/f16` 与 `…;fa=off,kv=q8_0/f16` 会按同一个测量身份合并成一行，
`fa` 这个因子在库里就消失了——数据在、格没了。

三种情形，都在库副本上跑：

  1. 两行只有 `fa=on`/`fa=off` 不同 → 必须入库 **2 行**，且两条协议串各自原样保留；
  2. 协议字段缺失 → 必须打印「用了默认协议」，且入库行的协议就是那个默认值；
  3. 同一份两行文件重跑一次 → 0 行新增（测量身份包含协议，重复入库不会翻倍）。

    python3 checks/ingest_protocol_negative_control.py
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import migrate_db  # noqa: E402

MODEL_MAP = {"q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf"}
PROTO_ON = "mpl-raw-greedy-768;fa=on,kv=q8_0/f16"
PROTO_OFF = "mpl-raw-greedy-768;fa=off,kv=q8_0/f16"
RUN_TAG = "proto-probe"


def ingest_in_fresh_db(rows, tmp):
    """在库副本上跑一次 ingest_mpl；返回 (inserted, stdout, db 路径, 临时目录)。"""
    summary = Path(tmp) / "probe_summary.jsonl"
    with open(summary, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    db = Path(tmp) / "experiments.sqlite"
    shutil.copyfile(REPO / "experiments.sqlite", db)
    con = sqlite3.connect(db)
    migrate_db.INGEST_SKIPS.clear()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            inserted = migrate_db.ingest_mpl(con, str(summary), RUN_TAG, summary.name,
                                             model_map=MODEL_MAP)
    finally:
        con.commit()          # ingest_* 只 execute，提交由调用方负责（migrate_db.main 也是这么做的）
        con.close()
    return inserted, buf.getvalue(), db, summary


def protocols_of(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [r[0] for r in con.execute(
            "SELECT protocol FROM experiments WHERE run_tag=? ORDER BY protocol", (RUN_TAG,))]
    finally:
        con.close()


def main():
    ok = True
    base = {"model": "q2", "lang": "cpp", "n": 161, "pass": 55, "score": 0.3416149068322981}

    # 1) 两行只有 fa 不同 → 两个格；3) 重跑不翻倍
    tmp = tempfile.mkdtemp(prefix="proto-c1-")
    try:
        inserted, out, db, summary = ingest_in_fresh_db(
            [dict(base, protocol=PROTO_ON), dict(base, protocol=PROTO_OFF)], tmp)
        protos = protocols_of(db)
        print(f"1) two rows differing only in fa : inserted={inserted}")
        print(f"   protocols stored              : {protos}")
        if inserted != 2 or protos != sorted([PROTO_OFF, PROTO_ON]):
            print("FAIL: 只有 fa 不同的两行没有被各自保留成一个格")
            print(out)
            ok = False

        con = sqlite3.connect(db)
        migrate_db.INGEST_SKIPS.clear()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                again = migrate_db.ingest_mpl(con, str(summary), RUN_TAG, summary.name,
                                              model_map=MODEL_MAP)
        finally:
            con.commit()
            con.close()
        print(f"3) same file re-ingested         : inserted={again} (expect 0), "
              f"rows still {len(protocols_of(db))}")
        if again != 0 or len(protocols_of(db)) != 2:
            print("FAIL: 重跑同一份文件又插入了行（测量身份没有覆盖协议）")
            ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 2) 协议字段缺失 → 明说用了默认协议，且入库行就是那个默认协议
    tmp2 = tempfile.mkdtemp(prefix="proto-c2-")
    try:
        inserted2, out2, db2, _ = ingest_in_fresh_db([dict(base, language="cpp")], tmp2)
        protos2 = protocols_of(db2)
        says_default = "用了默认协议" in out2
        print(f"2) protocol field missing        : inserted={inserted2}, stored={protos2}, "
              f"says default: {says_default}")
        print(f"   message                       : "
              f"{[l.strip() for l in out2.split(chr(10)) if '用了默认协议' in l]}")
        if inserted2 != 1 or protos2 != [migrate_db.DEFAULT_MPL_PROTOCOL] or not says_default:
            print("FAIL: 缺协议字段时没有明说用了默认协议")
            print(out2)
            ok = False
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)

    if ok:
        print("PASS: 带因子的两行各成一格、协议串原样保留；缺协议时明说用了默认值；重跑不翻倍")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
