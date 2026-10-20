#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本层自建配方的分配轮廓夹具：从 gguf 头重建，并与入库的冻结副本比对（漂移检查）。

用法（仓库根执行）：

    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/build_fixture.py" --write
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/build_fixture.py" --check

为什么要有这一条：`analysis/fixtures/alloc_a04.json` 是本层唯一自建的文件，它在仓库里，
而它的源（`*.gguf`）不在仓库里；所以断言必须读夹具（干净 clone 也成立），而夹具必须能被
重建与比对（在有源的机器上跑 `--check`）。这与 `a03::fixtures` 是同一个判据。

分类法不在这里复制：轮廓由 a03 的 `analysis/alloc.py::profile` 算（它负责 gguf 张量信息段的
字节/元素数推导与分桶），本脚本只负责把结果冻结与比对。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE
for _ in range(5):
    REPO = REPO.parent
    if (REPO / "experiments.sqlite").is_file():
        break
else:
    sys.exit("找不到仓库根（experiments.sqlite）")

A03 = REPO / "docs" / "subprojects" / "a03-量化方案与厂商" / "analysis"
sys.path.insert(0, str(A03))

import alloc  # noqa: E402  —— gguf 头解析与张量分桶由 a03 拥有

FIXTURE = HERE / "fixtures" / "alloc_a04.json"

# 本层自建的臂：名字 → 生成方式。`recipe` 是能重跑的命令片段（`llama-quantize` 的四个参数）。
ARMS = {
    "LFM2.5-8B-A1B-a04-uni45.gguf": {
        "role": "均匀控制臂（pinned 到 m55-exq4 的 4.483）",
        "source": "/home/z/hf/LFM2.5-8B-A1B-BF16.gguf",
        "command": "llama-quantize --tensor-type 'token_embd=Q4_K' "
                   "/home/z/hf/LFM2.5-8B-A1B-BF16.gguf "
                   "/home/z/hf/LFM2.5-8B-A1B-a04-uni45.gguf Q4_K_S",
        "dry_run_mib": 4565.94,
    },
}


def build():
    out = {"generated_by": "docs/subprojects/a04-MoE 各层比特分配/analysis/build_fixture.py",
           "note": "轮廓由 a03 的 alloc.profile 从 gguf 头算出；本文件是它的冻结副本。",
           "models": {}}
    for name, meta in ARMS.items():
        path = Path("/home/z/hf") / name
        if not path.exists():
            return None
        p = alloc.profile(str(path))
        p = {k: v for k, v in p.items() if k != "path"}
        row = dict(meta)
        row.update(p)
        out["models"][name] = row
    return out


def norm(doc):
    """只保留可比字段，并把浮点统一到 6 位，避免文本抖动造成假漂移。"""
    models = {}
    for name, row in doc["models"].items():
        m = {"bpw_file": round(row["bpw_file"], 6), "n_params": row["n_params"],
             "n_bytes": row["n_bytes"], "classes": {}}
        for cls, v in row["classes"].items():
            m["classes"][cls] = {"bits": round(v["bits"], 6), "params": v["params"],
                                 "bytes": v["bytes"]}
        models[name] = m
    return models


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.write:
        doc = build()
        if doc is None:
            print("源 gguf 不在盘上，无法重建；不写夹具（absent 不是 0）")
            return 2
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        print("wrote %s（%d 个文件）" % (FIXTURE, len(doc["models"])))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("夹具不存在：%s" % FIXTURE)
            return 1
        frozen = json.loads(FIXTURE.read_text(encoding="utf-8"))
        live = build()
        if live is None:
            print("[skip] 源 gguf 不在盘上，漂移检查未运行（干净 clone 的正常状态）；夹具仍被断言读取")
            return 0
        a, b = norm(frozen), norm(live)
        if a != b:
            for name in sorted(set(a) | set(b)):
                if a.get(name) != b.get(name):
                    print("[DRIFT] %s" % name)
                    print("  frozen", json.dumps(a.get(name), sort_keys=True)[:300])
                    print("  live  ", json.dumps(b.get(name), sort_keys=True)[:300])
            return 1
        print("[ok] %d 个文件的轮廓与源一致" % len(a))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
