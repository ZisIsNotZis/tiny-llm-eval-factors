#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GGUF 头部读取：把一个 `.gguf` 的**头**（元数据 + 张量表，不含权重）变成可入库的事实。

只回答本子项目要问的四件事：架构名、参数量、文件字节、每张量的形状与类型。
不读权重，所以 16 GB 的文件 0.2 s 读完，也不需要 GPU。

张量字节数不靠 ggml 类型表推，而靠相邻 offset 相减（最后一个用文件尾），
这样未知 ggml 类型不会让字节数变成猜的。

用法：
    python3 gguf_header.py <file.gguf>            # 打印 JSON
    python3 gguf_header.py <file.gguf> --shapes   # 附带每张量形状（夹具用）
"""
from __future__ import annotations

import json
import os
import struct
import sys

GGUF_MAGIC = 0x46554747          # "GGUF"
# gguf_value_type -> (struct code, 定长字节)
_SCALAR = {0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2),
           4: ("<I", 4), 5: ("<i", 4), 6: ("<f", 4), 7: ("<?", 1),
           10: ("<Q", 8), 11: ("<q", 8), 12: ("<d", 8)}
_T_STRING, _T_ARRAY = 8, 9


class Reader:
    def __init__(self, fh):
        self.fh = fh

    def raw(self, n):
        b = self.fh.read(n)
        if len(b) != n:
            raise EOFError(f"头部在 {n} 字节处提前结束")
        return b

    def unpack(self, code):
        code_, size = _SCALAR[code] if isinstance(code, int) else (code, None)
        if size is None:
            return struct.unpack(code_, self.fh.read(struct.calcsize(code_)))[0]
        return struct.unpack(code_, self.raw(size))[0]

    def u32(self):
        return struct.unpack("<I", self.raw(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.raw(8))[0]

    def gstr(self):
        n = self.u64()
        return self.raw(n).decode("utf-8", "replace")


def _value(r, vtype):
    if vtype in _SCALAR:
        return r.unpack(vtype)
    if vtype == _T_STRING:
        return r.gstr()
    if vtype == _T_ARRAY:
        itype, n = r.u32(), r.u64()
        if itype in _SCALAR:
            code, size = _SCALAR[itype]
            return list(struct.unpack("<" + code[1] * n, r.raw(size * n)))
        return [_value(r, itype) for _ in range(n)]
    raise ValueError(f"未知的 kv 值类型 {vtype}")


def read_header(path, shapes=True):
    """返回头部事实。`shapes=False` 时只留张量计数与类型直方图（夹具更小）。"""
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        r = Reader(fh)
        magic = r.u32()
        if magic != GGUF_MAGIC:
            raise ValueError(f"不是 GGUF 文件（magic=0x{magic:08x}）")
        version = r.u32()
        n_tensors, n_kv = r.u64(), r.u64()
        kv = {}
        for _ in range(n_kv):
            key = r.gstr()
            kv[key] = _value(r, r.u32())
        tensors = []
        for _ in range(n_tensors):
            name = r.gstr()
            n_dims = r.u32()
            dims = [r.u64() for _ in range(n_dims)]
            ggml_type = r.u32()
            offset = r.u64()
            tensors.append({"name": name, "dims": dims,
                            "type": ggml_type, "offset": offset})
        data_offset = fh.tell()

    align = int(kv.get("general.alignment", 32))
    data_bytes = size - data_offset
    for i, t in enumerate(tensors):
        nxt = tensors[i + 1]["offset"] if i + 1 < len(tensors) else data_bytes
        t["bytes"] = nxt - t["offset"]

    n_params = sum(_prod(t["dims"]) for t in tensors)
    nested = sum(len(t["dims"]) + 1 for t in tensors) + 1
    if n_tensors > 1 and all(t["bytes"] % align == 0 for t in tensors[:-1]):
        pass  # 对齐差已在 bytes 里；bpw_tensors 的误差 ≤ n_tensors×align
    arch = kv.get("general.architecture")
    # 架构前缀的键（dim/expert/attention…）与解码器专属的 `diffusion.*` 键都留在 meta 里：
    # 后者是「这文件真的是扩散解码器」的那一份证据，不能因为前缀不同就丢。
    meta = {k[len(arch) + 1:]: v for k, v in kv.items()
            if arch and k.startswith(arch + ".")}
    meta.update({k: v for k, v in kv.items() if k.startswith("diffusion.")})
    out = {
        "path": os.path.abspath(path),
        "file_bytes": size,
        "gguf_version": version,
        "n_tensors": n_tensors,
        "n_kv": n_kv,
        "data_offset": data_offset,
        "data_bytes": data_bytes,
        "alignment": align,
        "arch": arch,
        "name": kv.get("general.name"),
        "size_label": kv.get("general.size_label"),
        "n_params": n_params,
        "bpw_file": size * 8 / n_params if n_params else None,
        "bpw_tensors": data_bytes * 8 / n_params if n_params else None,
        "tensor_dims": nested,
        "meta": meta,
        "token_ids": {k.rsplit(".", 1)[-1]: v for k, v in kv.items()
                       if k.startswith("tokenizer.ggml.") and k.endswith("_token_id")},
        "ggml_type_hist": _hist(t["type"] for t in tensors),
    }
    if shapes:
        out["tensors"] = tensors
    return out


def _prod(xs):
    p = 1
    for x in xs:
        p *= x
    return p


def _hist(types):
    h = {}
    for t in types:
        h[str(t)] = h.get(str(t), 0) + 1
    return dict(sorted(h.items(), key=lambda kv: int(kv[0])))


def kv_upper_bound(meta, bytes_per_elem=2):
    """每 token 的 KV **上界**（f16）：全层 × 最大 kv 头数 × (k 长 + v 长) × 2 B，再乘满 ctx。

    它不认滑窗，也不认 `*_swa` 的小头维，所以它是上界而**不是需求**：本文件上界是真值的 6.9 倍
    （实测见 `RESULT.md::res5`）。要用它判「装不装得下」就会把结论带偏，判装不装得下要用
    `kv_true_bytes`。保留它是因为上界不依赖逐层归属，可以当「头部自洽」的参照。
    """
    def g(*names):
        for n in names:
            if n in meta:
                return meta[n]
        return None
    n_layer = g("block_count")
    kv_head = g("attention.head_count_kv")
    k_len = g("attention.key_length")
    v_len = g("attention.value_length")
    if isinstance(kv_head, list):
        kv_head = max(kv_head) if kv_head else None
    if None in (n_layer, kv_head, k_len, v_len):
        return None
    return int(n_layer * kv_head * (k_len + v_len) * bytes_per_elem)


def kv_true_bytes(meta, n_ctx, bytes_per_elem=2):
    """按层记账的**真值** KV 字节数（f16）：滑窗层只留 `min(ctx, sliding_window)` 个 token 且用
    `*_swa` 的头维，全局层留满 ctx 且用全量头维。

    头部里有逐层归属（`attention.sliding_window_pattern` 与逐层 `head_count_kv`），所以这一口径是
    确定的，不是估算：本机 30 层 = 25 层滑窗（8 头 × 256+256）+ 5 层全局（2 头 × 512+512），
    4096 ctx 下 293,601,280 B = 0.273 GiB。`attention.shared_kv_layers` 非 0 的文件这一口径会偏大
    （本文件它是 0）。
    """
    n_layer = meta.get("block_count")
    heads = meta.get("attention.head_count_kv")
    k_full = meta.get("attention.key_length")
    v_full = meta.get("attention.value_length")
    if None in (n_layer, heads, k_full, v_full):
        return None
    if not isinstance(heads, list):
        heads = [heads] * n_layer
    pattern = meta.get("attention.sliding_window_pattern")
    if not isinstance(pattern, list) or len(pattern) != n_layer:
        pattern = [False] * n_layer
    k_swa = meta.get("attention.key_length_swa", k_full)
    v_swa = meta.get("attention.value_length_swa", v_full)
    window = meta.get("attention.sliding_window")
    total = 0
    for i in range(n_layer):
        if pattern[i] and window:
            total += heads[i] * (k_swa + v_swa) * bytes_per_elem * min(n_ctx, int(window))
        else:
            total += heads[i] * (k_full + v_full) * bytes_per_elem * n_ctx
    return int(total)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    if not os.path.exists(path):
        print(f"缺文件：{path}", file=sys.stderr)
        return 2
    h = read_header(path, shapes="--shapes" in argv)
    print(json.dumps(h, ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(tuple(sys.argv[1:])))
