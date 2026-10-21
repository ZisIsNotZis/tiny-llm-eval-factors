#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：两份只差 `presence_penalty` 的 variant 面板必须入库为两格，不与 greedy 合并。

做法：临时目录里放一个 `variant_panel.json`（同一模型、同标签、只差 presence_penalty 2.0 vs 0.0），
在库副本上跑 `migrate_db.ingest_variant`，然后按测量身份列数一遍：
  * 两行 → 两格（presence_penalty 不同、协议串不同）；
  * 再跑一次 → 行数不变（ingest 用 DELETE+重建，必须幂等）。
"""
from __future__ import annotations
import json, os, shutil, sqlite3, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import migrate_db

SPEC_A = "sampling=temperature=1.0,top_p=1.0,top_k=20,min_p=0.0,presence_penalty=2.0"
SPEC_B = "sampling=temperature=1.0,top_p=1.0,top_k=20,min_p=0.0,presence_penalty=0.0"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="variant-ingest-negative-control-"))
    try:
        panel_dir = tmp / ".wrapup" / "mres" / "zz-probe"
        panel_dir.mkdir(parents=True)
        panel = {"tag": "zz-probe", "model": "LFM2.5-8B-A1B-a04-uni45.gguf", "axis": "sampling",
                 "rows": {
                     "vendor-recommended": {"label": "vendor-recommended", "llama_args": [],
                                            "sampling": {"temperature": 1.0, "top_p": 1.0,
                                                         "top_k": 20, "min_p": 0.0,
                                                         "presence_penalty": 2.0},
                                            "sampling_spec": SPEC_A, "mmlu": 0.5, "gsm8k": 0.4},
                     "vendor-recommended-pp0": {"label": "vendor-recommended-pp0", "llama_args": [],
                                                "sampling": {"temperature": 1.0, "top_p": 1.0,
                                                             "top_k": 20, "min_p": 0.0,
                                                             "presence_penalty": 0.0},
                                                "sampling_spec": SPEC_B, "mmlu": 0.5, "gsm8k": 0.4},
                 }}
        (panel_dir / "variant_panel.json").write_text(json.dumps(panel) + "\n")
        db = tmp / "experiments.sqlite"
        shutil.copyfile(REPO / "experiments.sqlite", db)
        old = os.getcwd()
        os.chdir(tmp)
        try:
            con = sqlite3.connect(db)
            migrate_db.ingest_variant(con)
            con.commit()
            rows = con.execute(
                "SELECT protocol, presence_penalty, _bench FROM experiments "
                "WHERE run_tag='zz-probe' ORDER BY protocol, _bench").fetchall()
            n1 = len(rows)
            migrate_db.ingest_variant(con)
            con.commit()
            n2 = con.execute("SELECT count(*) FROM experiments WHERE run_tag='zz-probe'").fetchone()[0]
            con.close()
        finally:
            os.chdir(old)
        protos = sorted({r[0] for r in rows})
        pps = sorted({r[1] for r in rows})
        print(f"rows={n1} after re-run={n2}; distinct protocols={len(protos)}; presence_penalty={pps}")
        for p in protos:
            print("  ", p)
        ok = (n1 == 4 and n2 == 4 and len(protos) == 2 and pps == ["0.0", "2.0"])
        print("PASS: 只差 presence_penalty 的两份面板入库为两格，且重跑行数不变" if ok else
              "FAIL: 两份面板被合并，或重跑行数变了")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
