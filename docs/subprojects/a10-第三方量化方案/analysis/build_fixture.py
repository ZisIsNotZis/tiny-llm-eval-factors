#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a10 第三方量化方案：重建 / 核对入库夹具 `analysis/fixtures/a10_map.json`。

为什么需要夹具：本层两条证据的一半在仓库外——分数格在 `experiments.sqlite`（入库），但
**有效位宽与逐类/逐张量分配来自 `*.gguf` 头**（不入库，几十 GB）。干净 clone 里没有 gguf，
断言的证据就会断。所以把 gguf 的测量结果冻结成夹具，每个条目自带推导证据（文件字节数、
参数量、张量数、逐类 bits、逐张量比特指纹），并由本文件的 `--check` 用本机源做漂移检查。

判定（退出码就是结论）：
    0  夹具与源一致（或刚写入）
    1  漂移（源变了 / 夹具与源不一致）—— 打印是哪一项
    2  **看不到输入**（gguf 不在盘上、DB 缺格）—— 这不是「一致」，必须非 0

用法：
    python3 "docs/subprojects/a10-第三方量化方案/analysis/build_fixture.py"            # 写入
    python3 ".../build_fixture.py" --check                                            # 漂移检查
"""
from __future__ import annotations

import argparse
import json
import sys

import panel
import alloc_a10


def collect():
    """从源收集夹具内容：分数格（库）+ 位宽与分配（gguf）。"""
    cells, dups = panel.cells()
    rec = alloc_a10.collect(with_siblings=True)
    missing = {n: r["missing"] for n, r in rec.items() if "missing" in r}
    doc = {
        "generated_by": "docs/subprojects/a10-第三方量化方案/analysis/build_fixture.py",
        "why": "gguf 头（有效位宽与逐张量比特分配）不入库；干净 clone 里没有 gguf，"
               "所以本层的位宽与分配证据冻结在这里，并由 --check 用本机源做漂移检查。",
        "third_party": panel.THIRD_PARTY,
        "native": panel.NATIVE,
        "siblings": {k: {"vendor": v[0], "tier": v[1]} for k, v in panel.SIBLINGS.items()},
        "tier": panel.TIER,
        "bench_order": panel.BENCH,
        "cells": {},
        "files": {},
        "missing_on_disk": missing,
        "duplicate_cells": [list(d) for d in dups],
    }
    for m in panel.THIRD_PARTY + panel.NATIVE:
        doc["cells"][m] = {
            b: {"score": c["score"], "n_items": c["n_items"], "run_tag": c["run_tag"],
                "protocol": c["protocol"], "ctx_size": c["ctx_size"],
                "parallel_slots": c["parallel_slots"], "temp": c["temp"],
                "reasoning": c["reasoning"]}
            for b, c in cells[m].items()}
    for m, r in rec.items():
        if "missing" in r:
            doc["files"][m] = {"missing": r["missing"]}
            continue
        doc["files"][m] = {"path": r["path"], "n_params": r["n_params"], "n_bytes": r["n_bytes"],
                           "n_tensors": r["n_tensors"], "bpw_file": r["bpw_file"],
                           "bpw_data": r["bpw_data"], "classes": r["classes"],
                           "tensor_sha": r["tensor_sha"], "names_sha": r["names_sha"]}
    return doc


def main(argv=()):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="只核对，不写入")
    a = ap.parse_args(list(argv) or None)
    doc = collect()
    if doc["missing_on_disk"]:
        print("看不到输入（这是「不可得」，不是「一致」）：", file=sys.stderr)
        for n, why in doc["missing_on_disk"].items():
            print(f"  {n}: {why}", file=sys.stderr)
        return 2
    if not a.check:
        panel.FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        panel.FIXTURE.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                                 encoding="utf-8")
        print(f"已写入 {panel.FIXTURE.relative_to(panel.REPO)}："
              f"{len(doc['cells'])} 个文件的分数格、{len(doc['files'])} 个文件的分配记录")
        return 0
    if not panel.FIXTURE.is_file():
        print(f"还没生成夹具 {panel.FIXTURE.relative_to(panel.REPO)}：先不带 --check 跑一次",
              file=sys.stderr)
        return 2
    old = json.loads(panel.FIXTURE.read_text(encoding="utf-8"))
    bad = []
    for key in ("cells", "files", "third_party", "native", "tier", "bench_order"):
        if old.get(key) != doc.get(key):
            bad.append(key)
    if bad:
        print(f"漂移：夹具与源不一致的键 {bad}")
        for key in bad:
            o, n = old.get(key), doc.get(key)
            if isinstance(o, dict) and isinstance(n, dict):
                for k in sorted(set(o) | set(n)):
                    if o.get(k) != n.get(k):
                        print(f"  {key}.{k}: 夹具 {json.dumps(o.get(k), ensure_ascii=False)[:160]}")
                        print(f"  {key}.{k}: 源   {json.dumps(n.get(k), ensure_ascii=False)[:160]}")
        return 1
    print(f"夹具与源一致：{panel.FIXTURE.relative_to(panel.REPO)}"
          f"（{len(doc['cells'])} 个文件 × 分数格、{len(doc['files'])} 个文件的逐张量指纹）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
