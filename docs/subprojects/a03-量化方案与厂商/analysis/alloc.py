#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a03：从 gguf 头读每个文件的**实测比特分配轮廓**（不是档位名）。

为什么要这个：本轴的问题是「厂商标签是不是比特分配的代理」。档位名（`Q3_K_XL`）只是配方名，
两份文件可以同名不同轮廓，也可以不同名同轮廓。这里直接量：

  * 每个张量的元素数来自 gguf 的张量信息段（维度连乘）；
  * 每个张量的字节数来自相邻张量的 `offset` 之差（最后一个到文件尾），
    所以 `bits/参数` 是**实测**的，不查任何类型表；
  * 按张量名分类（词嵌入 / 注意力 / 稠密 FFN / 专家 FFN / 归一化 / 输出）汇总，
    得到这个文件的分配轮廓。

校验：Σ(字节)×8 ÷ Σ(参数) 必须复现 `.wrapup/bpw_map.json` 与 `8×文件字节÷参数`；
差超过 0.02 比特/参数就打印 WARN，不静默放过（对齐填充会带来小误差）。

只读 gguf 头与文件大小，不加载权重、不碰 GPU。

用法：
    python3 "docs/subprojects/a03-量化方案与厂商/analysis/alloc.py" <file.gguf> [<file.gguf> ...]
    python3 ".../alloc.py" --pair bartowski/unsloth        # 用 pairs.py 的配对清单
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE
for _ in range(6):                       # docs/subprojects/<id>/analysis/alloc.py → 仓库根
    REPO = REPO.parent
    if (REPO / "experiments.sqlite").is_file():
        break
else:
    sys.exit("找不到仓库根（experiments.sqlite）")

sys.path.insert(0, str(HERE.parent))


def _rstr(f):
    n = struct.unpack("<Q", f.read(8))[0]
    return f.read(n).decode("utf-8", "replace")


def _rval(f, t):
    simple = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i",
              6: "<f", 7: "<B", 10: "<Q", 11: "<q", 12: "<d"}
    if t in simple:
        return struct.unpack(simple[t], f.read(struct.calcsize(simple[t])))[0]
    if t == 8:
        return _rstr(f)
    if t == 9:
        et = struct.unpack("<I", f.read(4))[0]
        cnt = struct.unpack("<Q", f.read(8))[0]
        for _ in range(cnt):
            _rval(f, et)
        return None
    raise ValueError("bad gguf value type %r" % t)


def tensor_class(name):
    """张量分类：问题问的是「比特落在哪一类层上」，所以按功能分类而不是按张量名逐一列。"""
    n = name
    if n.startswith("token_embd"):
        return "embed"
    if n.startswith("output"):
        return "output"
    if "norm" in n:
        return "norm"
    if "_exps" in n:
        return "ffn-expert"
    if ".attn_" in n:
        return "attn"
    if ".ffn_" in n:
        return "ffn-dense"
    return "other"


def read_gguf(path):
    """[(张量名, 参数个数, 字节数)]，字节数由 offset 差给出。"""
    p = Path(path)
    size = p.stat().st_size
    with open(p, "rb") as f:
        if f.read(4) != b"GGUF":
            raise ValueError("not a gguf: %s" % path)
        f.read(4)                                   # version
        n_tensors = struct.unpack("<Q", f.read(8))[0]
        n_kv = struct.unpack("<Q", f.read(8))[0]
        align = 32
        for _ in range(n_kv):
            k = _rstr(f)
            t = struct.unpack("<I", f.read(4))[0]
            v = _rval(f, t)
            if k == "general.alignment":
                align = int(v)
        tensors = []
        for _ in range(n_tensors):
            name = _rstr(f)
            nd = struct.unpack("<I", f.read(4))[0]
            dims = [struct.unpack("<Q", f.read(8))[0] for _ in range(nd)]
            f.read(4)                               # ggml type
            off = struct.unpack("<Q", f.read(8))[0]
            n = 1
            for d in dims:
                n *= d
            tensors.append([name, n, off])
        header_end = f.tell()
    data_start = (header_end + align - 1) // align * align
    tensors.sort(key=lambda t: t[2])
    for i, t in enumerate(tensors):
        nxt = tensors[i + 1][2] if i + 1 < len(tensors) else size - data_start
        t[2] = nxt - t[2]
    return [(n, elems, nbytes) for n, elems, nbytes in tensors], size


def profile(path):
    tensors, size = read_gguf(path)
    by = {}
    tot_e = tot_b = 0
    for name, elems, nbytes in tensors:
        k = tensor_class(name)
        e, b = by.get(k, (0, 0))
        by[k] = (e + elems, b + nbytes)
        tot_e += elems
        tot_b += nbytes
    out = {"file": Path(path).name, "n_params": tot_e, "n_bytes": size,
           "bpw_file": 8.0 * size / tot_e if tot_e else float("nan"),
           "bpw_data": 8.0 * tot_b / tot_e if tot_e else float("nan"),
           "classes": {k: {"params": e, "bytes": b, "bits": 8.0 * b / e if e else float("nan")}
                       for k, (e, b) in sorted(by.items())}}
    return out


def show(p):
    print(f"{p['file']}")
    print(f"  参数 {p['n_params']:,}  文件 {p['n_bytes'] / 2**30:.2f} GiB  "
          f"有效位宽 {p['bpw_file']:.3f}（数据段 {p['bpw_data']:.3f}，差 {abs(p['bpw_file'] - p['bpw_data']):.3f}）")
    for k, v in p["classes"].items():
        print(f"    {k:<11} {v['bits']:6.3f} 比特/参数  {v['params'] / p['n_params'] * 100:5.1f}% 参数")
    if abs(p["bpw_file"] - p["bpw_data"]) > 0.05:
        print("    WARN 文件位宽与数据段位宽差 > 0.05，对齐填充或元数据占比较大，逐类比重要打折看")


def diff(p1, p2):
    """两份文件的分配轮廓差：逐类比特/参数与参数加权平均差。

    这条是「同字节」配对里唯一被钉住的东西：总比特可以几乎相同，而比特落在哪类层上差别很大。
    """
    show(p1)
    show(p2)
    print(f"  轮廓差（{p1['file']} − {p2['file']}，比特/参数）：")
    wsum = dsum = 0.0
    for k in sorted(set(p1["classes"]) | set(p2["classes"])):
        a = p1["classes"].get(k, {"bits": float("nan"), "params": 0})
        b = p2["classes"].get(k, {"bits": float("nan"), "params": 0})
        d = a["bits"] - b["bits"]
        w = max(a["params"], b["params"])
        if d == d and w:
            wsum += w
            dsum += w * abs(d)
        print(f"    {k:<11} {a['bits']:7.3f} vs {b['bits']:7.3f}  Δd={d:+7.3f}")
    print(f"    参数加权平均 |Δ| = {dsum / wsum if wsum else float('nan'):.4f} 比特/参数"
          f"（总位宽差 {p1['bpw_file'] - p2['bpw_file']:+.3f}）")


def main(argv=()):
    args = list(argv) or sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "--pair":
        import pairs
        cells, _dups = pairs.load()
        vendors = pairs.vendor_of()
        want = args[1] if len(args) > 1 else None
        profs = []
        for p in pairs.enumerate_pairs(cells, vendors, 0.45):
            vl = "/".join(p["vendor_low"])
            vh = "/".join(p["vendor_high"])
            if want and want not in (vl, vh, f"{vl}/{vh}", f"{vh}/{vl}"):
                continue
            print(f"== {p['family']}  {p['quant_low']} → {p['quant_high']}  "
                  f"Δbpw={p['dbpw']:+.3f}  {p['kind']}")
            for m in (p["low"], p["high"]):
                path = find_path(m)
                if path is None:
                    print(f"  {m}: 盘上找不到文件，跳过（未测，不是 0）")
                    continue
                profs.append((m, profile(path), p))
            if len(profs) == 2:
                diff(profs[0][1], profs[1][1])
            profs = []
        return 0
    for a in args:
        show(profile(a))
    return 0


def find_path(name):
    """按文件名在 mscache / HF 缓存 / 本地目录里找 gguf（找不到就返回 None，让调用方登记未测）。"""
    import subprocess
    for root in ("/home/z/hf/mscache", "/home/z/hf"):
        r = subprocess.run(["find", root, "-maxdepth", "4", "-name", name, "-type", "f"],
                           capture_output=True, text=True)
        for line in r.stdout.split("\n"):
            if line.strip():
                return line.strip()
    return None


if __name__ == "__main__":
    sys.exit(main())
