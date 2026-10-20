#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `/home/z/hf` 里 GGUF 头的解析结果做成入库的 fixture。

为什么要有这一份：本轴的 X 是「实测参数量」，只能从 GGUF 头算出来，而 GGUF 体积大、不入 git
（`.gitignore` 里 `*.gguf`）。没有这份 fixture 时，`/home/z/hf` 一旦缺失，整条规模轴的检查在
干净 clone 里就退化成「未测」。所以真值在这里落一份，`--check` 负责与现场文件比对漂移。

每条记录只放**可从头部确定**的量：张量元素个数（总/专家池/共享）、专家数与激活专家数、架构名、
每个 ggml 类型的字节数与据此算出的逐类比特。不改 GGUF 里任何精度信息缺失的推断。

    python3 "docs/subprojects/a02-模型规模/analysis/build_fixtures.py"           # 重建
    python3 "docs/subprojects/a02-模型规模/analysis/build_fixtures.py" --check   # 与现文件比对漂移
"""
from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HF = Path("/home/z/hf")
OUT = HERE / "fixtures" / "gguf_truth.json"

sys.path.insert(0, str(REPO / ".wrapup"))
import gguf_params  # noqa: E402  唯一的 GGUF 值解码实现

_rstr, _rval = gguf_params._rstr, gguf_params._rval

# ggml 类型 → (每块元素数, 每块字节数)。用来把「张量个数 × 类型」折成字节，再与文件大小对照——
# 这一步就是这张表的自检：折出来的字节和文件大小差 2% 以上，就说明表里缺/错了类型。
TYPE_SIZE = {
    0: (1, 4), 1: (1, 2), 2: (32, 18), 3: (32, 20), 6: (32, 22), 7: (32, 24),
    8: (32, 34), 9: (32, 36), 10: (256, 84), 11: (256, 110), 12: (256, 144),
    13: (256, 176), 14: (256, 210), 15: (256, 292), 16: (256, 66), 17: (256, 74),
    18: (256, 98), 19: (256, 50), 20: (32, 18), 21: (256, 110), 22: (256, 82),
    23: (256, 136), 24: (1, 1), 25: (1, 2), 26: (1, 4), 27: (1, 8), 28: (1, 8),
    29: (256, 56), 30: (1, 2), 34: (256, 54), 35: (256, 66),
    # 41/42 是新版 ggml 的 Q1_0 / Q2_0：块大小不是查表得来的，而是用「文件字节数 ÷ 元素数」
    # 反解出来的（Q1_0 → 0.1406 字节/元素 = 18/128，Q2_0 → 0.28125 字节/元素 = 18/64），
    # 两者与实测文件大小的差都 <0.6%，就是本文件末尾那条自检。
    41: (128, 18), 42: (64, 18),
}


def read_gguf(path: Path) -> dict:
    """头部 → 参数量、逐类参数量与字节数、架构。张量名区分专家池（`_exps`）与共享（`_shexp`）。"""
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            raise ValueError(f"not a gguf: {path}")
        f.read(4)
        n_tensors = struct.unpack("<Q", f.read(8))[0]
        n_kv = struct.unpack("<Q", f.read(8))[0]
        meta = {}
        for _ in range(n_kv):
            k = _rstr(f)
            t = struct.unpack("<I", f.read(4))[0]
            meta[k] = _rval(f, t)
        total = expert = 0
        bytes_total = bytes_expert = 0
        unknown_types = set()
        for _ in range(n_tensors):
            name = _rstr(f)
            nd = struct.unpack("<I", f.read(4))[0]
            dims = [struct.unpack("<Q", f.read(8))[0] for _ in range(nd)]
            gtype = struct.unpack("<I", f.read(4))[0]
            f.read(8)
            n = 1
            for d in dims:
                n *= d
            blk, nbytes = TYPE_SIZE.get(gtype, (None, None))
            if blk is None:
                unknown_types.add(gtype)
                b = 0
            else:
                b = (n // blk) * nbytes
            is_expert = "_exps" in name and "_shexp" not in name
            total += n
            bytes_total += b
            if is_expert:
                expert += n
                bytes_expert += b

    def one(suffix):
        for k, v in meta.items():
            if k.endswith(suffix):
                return v
        return None

    used, count = int(one(".expert_used_count") or 0), int(one(".expert_count") or 0)
    shared = total - expert
    return {
        "n_params": total,
        "expert_params": expert,
        "shared_params": shared,
        "expert_count": count,
        "expert_used": used,
        "active_params": total if count == 0 else shared + round(expert * used / count),
        "arch": str(meta.get("general.architecture", "")),
        "tensor_bytes": bytes_total,
        "expert_tensor_bytes": bytes_expert,
        "shared_tensor_bytes": bytes_total - bytes_expert,
        "expert_bpw": round(8.0 * bytes_expert / expert, 4) if expert else None,
        "shared_bpw": round(8.0 * (bytes_total - bytes_expert) / shared, 4) if shared else None,
        "unknown_ggml_types": sorted(unknown_types),
    }


def build(models):
    out = {}
    for m in models:
        p = HF / m
        if not p.is_file():
            continue
        rec = read_gguf(p)
        rec["file_bytes"] = p.stat().st_size
        rec["bpw_file"] = round(8.0 * rec["file_bytes"] / rec["n_params"], 4)
        rec["bpw_tensors"] = round(8.0 * rec["tensor_bytes"] / rec["n_params"], 4) if rec["n_params"] else None
        rec["file_size_gb"] = round(rec["file_bytes"] / 1e9, 9)
        out[m] = rec
    doc = {
        "what": "每个模型文件的实测参数量、逐类参数量与字节数；来源是 GGUF 头（张量形状 + KV），"
                "GGUF 本身不入 git，所以真值落在这里",
        "built_from": f"{HF}/<name>.gguf 的头部（不含权重）",
        "type_table": "ggml 类型 → (块内元素数, 块字节数)；bpw_tensors 与 bpw_file 的差就是这张表的自检",
        "models": dict(sorted(out.items())),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return doc


def db_models() -> list[str]:
    import sqlite3
    con = sqlite3.connect(f"file:{REPO / 'experiments.sqlite'}?mode=ro", uri=True)
    return [r[0] for r in con.execute("select distinct model from experiments order by 1")]


def main(argv):
    models = db_models()
    if "--check" in argv:
        if not OUT.is_file():
            print(f"FAIL: fixture 不存在（{OUT.relative_to(REPO)}）；先跑不带 --check 的那次")
            return 1
        cur = json.loads(OUT.read_text(encoding="utf-8"))["models"]
        bad = drift = 0
        present = 0
        for m in models:
            p = HF / m
            if not p.is_file():
                continue
            present += 1
            rec = read_gguf(p)
            rec["file_bytes"] = p.stat().st_size
            currec = cur.get(m)
            if currec is None:
                print(f"  FAIL  {m}: 现场有 GGUF 但 fixture 里没有")
                bad += 1
                continue
            for k in ("n_params", "expert_params", "shared_params", "active_params",
                      "expert_count", "expert_used", "arch", "tensor_bytes", "file_bytes"):
                if rec[k] != currec.get(k):
                    print(f"  FAIL  {m}: {k} 现场 {rec[k]} vs fixture {currec.get(k)}")
                    bad += 1
            if rec["unknown_ggml_types"]:
                print(f"  WARN  {m}: 未知 ggml 类型 {rec['unknown_ggml_types']}（字节折算会偏低）")
        print(f"  {present} 个现场 GGUF 在场，{bad} 处与 fixture 不符；"
              f"fixture 共 {len(cur)} 条（另外 {len(cur) - present} 条来自已删除的文件，无法现场复验）")
        return 0 if bad == 0 else 1

    doc = build(models)
    m = doc["models"]
    print(f"wrote {OUT.relative_to(REPO)}: {len(m)} 个模型文件")
    print(f"{'model':46s} {'params B':>9s} {'active B':>9s} {'bpw_file':>9s} {'bpw_tensors':>12s} {'diff%':>7s}")
    for name, r in list(m.items())[:8]:
        d = 100 * (r["bpw_tensors"] - r["bpw_file"]) / r["bpw_file"]
        print(f"{name[:46]:46s} {r['n_params']/1e9:9.3f} {r['active_params']/1e9:9.3f} "
              f"{r['bpw_file']:9.4f} {r['bpw_tensors']:12.4f} {d:+7.2f}")
    diffs = [abs(100 * (r["bpw_tensors"] - r["bpw_file"]) / r["bpw_file"]) for r in m.values()]
    print(f"\n自检：|bpw_tensors - bpw_file| 的中位 {sorted(diffs)[len(diffs)//2]:.2f}%、最大 {max(diffs):.2f}%")
    unk = {t for r in m.values() for t in r["unknown_ggml_types"]}
    if unk:
        print(f"未知 ggml 类型：{sorted(unk)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
