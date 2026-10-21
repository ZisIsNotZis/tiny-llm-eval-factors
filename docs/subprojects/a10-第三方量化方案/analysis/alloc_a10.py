#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a10 第三方量化方案：从 gguf 头量「这个档位的比特落在哪里」，以及标签是否确定了一套分配。

为什么需要它：本轴的第二个问题不是「第三方方案分数高不高」，而是**钉住比特之后剩下的标签还能不能
与分配分开**。档位名（`GSQ-RCO-IQ3_S`）可能只是配方名，也可能真的确定了一套逐张量分配；只有实测
能分辨。这里量三件事：

  1. 每个文件的逐类比特轮廓（`attn` / `embed` / `ffn-dense` / `norm` / `output` / `other`）与有效位宽；
  2. 两个第三方档对最近原生档的**参数加权 |Δ|**（同字节下分配差多少比特/参数）；
  3. 同一 tier 标签在别的上传者 / 另一套 base 权重上是否给出**逐张量相同**的分配
     （打印不同的张量计数与总张量数）；以及五个面板文件是否共享同一张量集合。

逐张量比特 = 8 × 该张量字节 ÷ 元素数；字节来自相邻张量 `offset` 之差（最后一个到文件尾），
元素数来自维度连乘，**不查量化类型表**。解析与分桶复用 `a03::alloc`（唯一 home）。

只读 gguf 头、不加载权重、不占 GPU。

用法：
    python3 "docs/subprojects/a10-第三方量化方案/analysis/alloc_a10.py"
    python3 ".../alloc_a10.py" --json            # 给 build_fixture.py / run_all.py 用
    python3 ".../alloc_a10.py" --diff            # 只看分配差
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import panel

sys.path.insert(0, str(panel.A03))
import alloc as a03alloc           # noqa: E402  —— gguf 解析与张量分桶（唯一 home）

# 盘上的候选位置，按 gguf 文件名精确匹配。HF 缓存的 `<vendor>` 目录与 mscache 的布局不同，
# 所以两种都列；找不到就是「不可得」（退出码 2），不是 0。
CANDIDATES = ("/home/z/hf/mscache/*/*/{name}",
              "/home/z/hf/models--{hint}*/snapshots/*/{name}",
              "/home/z/hf/{name}")
# vendor 提示：文件名里没有厂商时用来缩窄 HF 缓存目录的搜索面（只是搜索提示，不是来源证据）。
HINT = {
    "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf": "ISTA-DASLab",
    "Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf": "ISTA-DASLab",
    "Qwen3.8-27B-UD-Q2_K_XL.gguf": "unsloth",
    "Qwen3.8-27B-UD-Q3_K_XL.gguf": "unsloth",
    "Qwen3.8-27B-UD-IQ4_XS.gguf": "unsloth",
    "Dirk-Qwen3.8-27B-GSQ-RCO-IQ3_XXS.gguf": "peculiar-ragdoll",
    "Dirk-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf": "peculiar-ragdoll",
    "Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_XXS-mtp.gguf": "huihui-ai",
    "Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf": "huihui-ai",
}


def find_gguf(name):
    """按文件名在 mscache / HF 缓存 / 本地目录里找；找不到返回 None（调用方登记不可得）。

    `A10_NO_GGUF=1` 把仓库外的整个搜索面关掉。这不是花活：干净 clone 里 gguf **本就不存在**，
    而如果 clone 恰好跑在这台有 /home/z/hf 的机器上，搜索会「恰好」成功，让「看不到输入时退出非 0」
    这条验收变成假绿。关掉搜索面后：`build_fixture.py --check` 必须退 2，`run_all.py` 仍必须退 0
    （它只用夹具）。
    """
    if os.environ.get("A10_NO_GGUF"):
        return None
    hint = HINT.get(name, "*")
    for pat in CANDIDATES:
        for p in sorted(Path("/").glob(pat.format(name=name, hint=hint).lstrip("/"))):
            if p.is_file():
                return str(p)
    return None


def tensor_bits(path):
    """{张量名: 比特/参数}。"""
    ts, _size = a03alloc.read_gguf(path)
    if len({n for n, _e, _b in ts}) != len(ts):
        raise ValueError(f"{path}: 张量名重复，按名比较无意义")
    return {n: (8.0 * b / e if e else float("nan")) for n, e, b in ts}


def measure(name):
    """一个文件的实测记录；盘上没有就返回 {'missing': 原因}，绝不补 0。"""
    path = find_gguf(name)
    if path is None:
        return {"file": name, "missing": "盘上找不到该 gguf（未测，不是 0）"}
    prof = a03alloc.profile(path)
    tb = tensor_bits(path)
    return {"file": name, "path": path, "n_params": prof["n_params"], "n_bytes": prof["n_bytes"],
            "n_tensors": len(tb), "bpw_file": prof["bpw_file"], "bpw_data": prof["bpw_data"],
            "classes": prof["classes"], "tensor_sha": panel.tensor_fingerprint(tb),
            "names_sha": panel.names_fingerprint(tb), "tensor_bits": tb}


def weighted_abs_diff(a, b):
    """两份文件逐类比特差的参数加权平均 |Δ|（比特/参数），与 `a03::alloc.diff` 同一口径。"""
    wsum = dsum = 0.0
    per_class = {}
    for cls in sorted(set(a["classes"]) | set(b["classes"])):
        ca = a["classes"].get(cls, {"bits": float("nan"), "params": 0})
        cb = b["classes"].get(cls, {"bits": float("nan"), "params": 0})
        d = ca["bits"] - cb["bits"]
        w = max(ca["params"], cb["params"])
        per_class[cls] = {"a": ca["bits"], "b": cb["bits"], "delta": d}
        if d == d and w:
            wsum += w
            dsum += w * abs(d)
    return (dsum / wsum if wsum else float("nan")), per_class


def collect(with_siblings=True):
    names = list(panel.THIRD_PARTY) + list(panel.NATIVE)
    if with_siblings:
        names += list(panel.SIBLINGS)
    return {n: measure(n) for n in names}


def report(rec):
    print("== 每个文件：有效位宽与逐类比特（比特/参数）")
    for n in list(panel.NATIVE) + list(panel.THIRD_PARTY):
        r = rec[n]
        if "missing" in r:
            print(f"  {n}: {r['missing']}")
            continue
        warn = "  WARN 文件位宽与数据段位宽差 >0.05" if abs(r["bpw_file"] - r["bpw_data"]) > 0.05 else ""
        print(f"  {n}")
        print(f"    参数 {r['n_params']:,}  张量 {r['n_tensors']}  有效位宽 {r['bpw_file']:.3f}"
              f"（数据段 {r['bpw_data']:.3f}）{warn}")
        for cls, v in r["classes"].items():
            print(f"      {cls:<11} {v['bits']:7.3f}  {v['params'] / r['n_params'] * 100:5.1f}% 参数")

    print("\n== 张量集合：五个面板文件是否逐项相同（同族 = 实测，不是按名字猜）")
    base = rec[panel.NATIVE[0]]
    for n in panel.THIRD_PARTY + panel.NATIVE[1:]:
        r = rec[n]
        same = (r.get("n_tensors") == base.get("n_tensors")
                and r.get("n_params") == base.get("n_params")
                and set(r.get("tensor_bits", {})) == set(base.get("tensor_bits", {})))
        n_diff = sum(1 for k, e in base.get("tensor_bits", {}).items()
                     if r.get("tensor_bits", {}).get(k) != e)
        print(f"  {n:<52} 张量名/元素数相同: {same}  比特不同的张量: {n_diff}")

    print("\n== 分配差：第三方档 vs 最近原生档（参数加权 |Δ|，比特/参数）")
    for tp in panel.THIRD_PARTY:
        if "missing" in rec[tp]:
            print(f"  {tp}: {rec[tp]['missing']}")
            continue
        ties = panel.nearest_native(panel.BPW[tp])
        for bpw_n, nat in ties:
            if "missing" in rec.get(nat, {}):
                print(f"  {tp} vs {nat}: {rec.get(nat, {}).get('missing')}")
                continue
            w, per = weighted_abs_diff(rec[tp], rec[nat])
            print(f"  {tp}\n    vs {nat}  Δbpw={panel.BPW[tp] - bpw_n:.3f}  加权 |Δ|={w:.3f}")
            for cls, v in per.items():
                print(f"      {cls:<11} {v['a']:7.3f} vs {v['b']:7.3f}  Δ={v['delta']:+7.3f}")

    print("\n== 同一个 tier 标签换上传者/换 base 权重后，分配是否逐张量相同")
    for tp, tier in panel.TIER.items():
        ref = rec[tp]
        if "missing" in ref:
            print(f"  {tp}: {ref['missing']}")
            continue
        print(f"  tier {tier}：基准 {tp}（ISTA-DASLab，tensor_sha {ref['tensor_sha'][:12]}…）")
        for sib, (vendor, t) in panel.SIBLINGS.items():
            if t != tier:
                continue
            r = rec[sib]
            if "missing" in r:
                print(f"    {sib}: {r['missing']}")
                continue
            diff = [k for k in ref["tensor_bits"]
                    if r["tensor_bits"].get(k) != ref["tensor_bits"][k]]
            print(f"    {sib:<56} ({vendor})  不同张量 {len(diff)}/{ref['n_tensors']}"
                  f"  sha 相同: {r['tensor_sha'] == ref['tensor_sha']}"
                  f"  字节 {'相同' if r['n_bytes'] == ref['n_bytes'] else '不同'}")


def main(argv=()):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="打印机器可读记录（给 build_fixture.py 用）")
    ap.add_argument("--no-siblings", action="store_true", help="不量别的上传者那四个文件")
    a = ap.parse_args(list(argv) or None)
    rec = collect(with_siblings=not a.no_siblings)
    if a.json:
        out = {n: {k: v for k, v in r.items() if k != "tensor_bits"} for n, r in rec.items()}
        out["_tensor_bits"] = {n: r["tensor_bits"] for n, r in rec.items() if "tensor_bits" in r}
        print(json.dumps(out, ensure_ascii=False))
        return 0
    missing = [n for n, r in rec.items() if "missing" in r]
    report(rec)
    if missing:
        print(f"\n不可得：{len(missing)} 个文件盘上找不到（未测，不是 0）：{missing}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
