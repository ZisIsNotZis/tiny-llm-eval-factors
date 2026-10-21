#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：m165（厂商推荐采样 R1）的入库按五个采样量区分身份，skip ledger 可见。

三例（库副本 + 临时 summary，不动真库）：
  1. 真文件（7 行）→ 入库 7 格，协议串带 `sampling=`；
  2. 造两份只差 `presence_penalty` 的行 → 必须入库为两格（不与贪心合并、也不互相合并）；
  3. 造一行未知模型名 → 必须进 skip ledger（`reason=unknown_model`），不入库。
"""
from __future__ import annotations
import json, os, shutil, sqlite3, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import migrate_db

BASE_ROW = {"cell": "zz-cpp", "model": "q2", "lang": "cpp", "n": 161, "pass": 1,
            "score": 0.006211180124223602, "temp": 1.0, "top_p": 1.0, "top_k": 20,
            "min_p": 0.0, "presence_penalty": 2.0, "seed": 1234, "ctx": 4096,
            "protocol": "mpl-raw-t1.0-768;ctx=4096;sampling=temp=1.0,top_p=1.00,top_k=20,min_p=0.0,presence_penalty=2.0"}


def run(rows, tmp):
    d = Path(tmp) / ".wrapup" / "mres" / "m165-vendor"
    d.mkdir(parents=True)
    (d / "vendor_r1_summary.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    db = Path(tmp) / "experiments.sqlite"
    shutil.copyfile(REPO / "experiments.sqlite", db)
    old = os.getcwd(); os.chdir(tmp)
    try:
        con = sqlite3.connect(db)
        migrate_db.INGEST_SKIPS.clear()
        n = migrate_db.ingest_m165(con)
        con.commit()
        got = con.execute("SELECT protocol, presence_penalty, seed, ctx_size, n_items "
                          "FROM experiments WHERE run_tag='m165-vendor-r1'").fetchall()
        con.close()
    finally:
        os.chdir(old)
    return n, got, dict(migrate_db.INGEST_SKIPS)


def main():
    ok = True
    real = [json.loads(l) for l in open(REPO / ".wrapup/mres/m165-vendor/vendor_r1_summary.jsonl",
                                        encoding="utf-8") if l.strip()]
    tmp = tempfile.mkdtemp(prefix="m165-c1-")
    try:
        n, got, _ = run(real, tmp)
        print(f"1) real summary           : inserted={n} (expect {len(real)}), "
              f"all protocols carry sampling=: {all('sampling=' in r[0] for r in got)}")
        if n != len(real) or not all("sampling=" in r[0] for r in got):
            print("FAIL: 真 summary 没有按行入库或协议串缺 sampling="); ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    tmp = tempfile.mkdtemp(prefix="m165-c2-")
    try:
        a = dict(BASE_ROW)
        b = dict(BASE_ROW, presence_penalty=0.0,
                 protocol=BASE_ROW["protocol"].replace("presence_penalty=2.0", "presence_penalty=0.0"))
        n, got, _ = run([a, b], tmp)
        pps = sorted({r[1] for r in got})
        print(f"2) only presence_penalty : inserted={n} (expect 2), presence_penalty={pps}")
        if n != 2 or pps != ["0.0", "2.0"]:
            print("FAIL: 只差 presence_penalty 的两行被合并了"); ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    tmp = tempfile.mkdtemp(prefix="m165-c3-")
    try:
        bad = dict(BASE_ROW, model="zz-unknown")
        n, got, skips = run([bad], tmp)
        led = [c for counter in skips.values() for (reason, name), c in counter.items()
               if reason == "unknown_model"]
        print(f"3) unknown model name     : inserted={n} (expect 0), ledger={skips}")
        if n != 0 or not led:
            print("FAIL: 未知模型名没有进 skip ledger"); ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("PASS: 七格按行入库、只差 presence_penalty 的两行各成一格、未知模型进 skip ledger"
          if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
