#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：入库时被跳过的行必须被报出来，不能静默丢掉。

来由：`.wrapup/m29_summary.jsonl` 有 24 行、`run_tag='m29-flash-attn'`，用的是短名 `q2`/`q3`，
而 `ingest_m29` 走默认 `MPL_MODELS`，于是 `ingest_mpl` 静默跳过——数据在、结论不在，还没人知道。

这个负控在库副本上把一个真实的 summary 喂给 `ingest_mpl`，分三种情形：

  1. 模型名不在 `model_map` 里 → 必须打印 `skipped_rows=N reason=unknown_model names=…`，且一行都不入库；
  2. 同一个文件配上认识它的 `model_map` → 必须全部入库、且没有 unknown_model 的跳过；
  3. 一个只含已知模型名的文件 → 必须跳过计数为 0（负控的另一半：不是永远都在报）。

    python3 checks/ingest_skip_negative_control.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import migrate_db  # noqa: E402

M29 = REPO / ".wrapup" / "m29_summary.jsonl"
KNOWN = REPO / ".wrapup" / "m9_bfcl_placeholder"


def run_ingest(path, run_tag, model_map):
    """在库副本上跑一次 ingest_mpl，返回 (inserted, stdout)。"""
    tmp = Path(tempfile.mkdtemp(prefix="ingest-skip-negative-control-"))
    try:
        db = tmp / "experiments.sqlite"
        shutil.copyfile(REPO / "experiments.sqlite", db)
        con = sqlite3.connect(db)
        migrate_db.INGEST_SKIPS.clear()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            n = migrate_db.ingest_mpl(con, str(path), run_tag, os.path.basename(path),
                                      model_map=model_map)
            migrate_db.print_ingest_skips()
        con.close()
        return n, buf.getvalue()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    rows = [json.loads(l) for l in open(M29, encoding="utf-8") if l.strip()]
    names = sorted({r["model"] for r in rows})
    print(f"fixture: {os.path.basename(M29)}, {len(rows)} rows, model names {names}")

    ok = True
    n, out = run_ingest(M29, "m29-skip-probe", migrate_db.MPL_MODELS)
    unknown = [l for l in out.split("\n") if "reason=unknown_model" in l]
    print(f"  1) default model map   : inserted={n}, reported: {unknown[:2]}")
    if n != 0 or not unknown or f"skipped_rows={len(rows)}" not in unknown[0]:
        print("FAIL: 不认识的模型名没有被明确报出（或竟然入了库）")
        print(out)
        ok = False

    # 这一条只验证「可见性」：配上认得的映射后，不该再有 unknown_model 的跳过。
    # 至于这些格该不该入库、以什么协议入库，是 a05 的判断——`ingest_mpl` 现在把协议写死成
    # 规范化那一条，m29 的 fa/kv 面因此不能被它原样收下（见 RESULT::res44）。
    known_map = {"q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf", "q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf"}
    n2, out2 = run_ingest(M29, "m29-skip-probe", known_map)
    reported2 = [l for l in out2.split("\n") if "reason=unknown_model" in l]
    present2 = [l for l in out2.split("\n") if "already present" in l]
    print(f"  2) map that knows them : inserted={n2}, unknown reports: {len(reported2)}, "
          f"already-present: {present2[0].strip() if present2 else 'none'}")
    if reported2:
        print("FAIL: 配上认识的映射后仍然报未知名跳过")
        print(out2)
        ok = False

    tmp_summary = Path(tempfile.mkdtemp(prefix="ingest-skip-known-")) / "known_summary.jsonl"
    with open(tmp_summary, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"model": "qwen4b-q2", "lang": "cpp", "n": 161, "pass": 55,
                             "score": 0.3416149068322981,
                             "protocol": "mpl-raw-greedy-768"}) + "\n")
    n3, out3 = run_ingest(tmp_summary, "known-probe", migrate_db.MPL_MODELS)
    reported3 = [l for l in out3.split("\n") if "reason=unknown_model" in l]
    print(f"  3) all-known summary   : inserted={n3}, unknown reports: {len(reported3)}, "
          f"ledger: {[l.strip() for l in out3.split(chr(10)) if 'ingest skips' in l]}")
    if reported3 or "ingest skips == none" not in out3:
        print("FAIL: 全部认识的输入也报了跳过（说明报告不是按事实给的）")
        print(out3)
        ok = False
    shutil.rmtree(tmp_summary.parent, ignore_errors=True)

    if ok:
        print("PASS: 未知名被明确报出且不入库；认得的名字全部入库、跳过计数为 0")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
