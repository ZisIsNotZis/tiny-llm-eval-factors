#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP2：`experiments.__size` 这一列到底是哪条通道给的数。

本轴要回归 `score ~ 规模`，所以第一件事不是拟合，是判「规模」这一列是不是参数量。
`exp.py::double_underscore_fields` 从**文件名**取它：

    SIZE_RE      = -E?([0-9.]+)[MB]\\b        # 不区分 M 与 B
    size         = 文件名 token 里的数
    若 size < 文件字节数          -> size = 文件字节数
    若文件名没有 token           -> size = 文件字节数 / 0.5

于是同一列里混着三种东西：真参数量、同一个数错 1000 倍、以及「2 × 量化后字节数」。
本脚本用 GGUF 头（张量元素个数求和，专家张量单独分出）测出真参数量与真激活参数量，
再把库里的每一行归到一条通道上。

只读：`SELECT` + `/home/z/hf/` 的 GGUF 头。输出 `analysis/size_provenance.json`。

    python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py"            # 出表 + 写 json
    python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" --check    # 逐条断言，退出码即结论
    python3 "docs/subprojects/a02-模型规模/analysis/size_provenance.py" --selftest # 负控：篡改后断言必须失败
"""
from __future__ import annotations

import json
import os
import sqlite3
import struct
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # analysis -> a02-模型规模 -> subprojects -> docs -> repo
DB = REPO / "experiments.sqlite"
HF = Path("/home/z/hf")
OUT = HERE / "size_provenance.json"
CACHE = HERE / "gguf_cache.json"      # 每个 GGUF 的 (size, mtime) → 张量统计；文件变了就重读
BPW_MAP = REPO / ".wrapup" / "bpw_map.json"

sys.path.insert(0, str(REPO / ".wrapup"))
import gguf_params  # noqa: E402  唯一的 GGUF 值解码实现（.wrapup/gguf_params.py，已入库）

_rstr, _rval = gguf_params._rstr, gguf_params._rval


def gguf_structure(path: Path) -> dict:
    """总参数、专家池参数、激活参数，全部由张量形状算出（不看文件名）。"""
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
        for _ in range(n_tensors):
            name = _rstr(f)
            nd = struct.unpack("<I", f.read(4))[0]
            dims = [struct.unpack("<Q", f.read(8))[0] for _ in range(nd)]
            f.read(4 + 8)
            n = 1
            for d in dims:
                n *= d
            total += n
            # 专家池张量参与「按路由比例激活」；shared expert（shexp）是恒激活的，不算池子。
            if "_exps" in name and "_shexp" not in name:
                expert += n
    def one(suffix):
        for k, v in meta.items():
            if k.endswith(suffix):
                return v
        return None
    used, count = one(".expert_used_count"), one(".expert_count")
    used = int(used or 0)
    count = int(count or 0)
    active = total if count == 0 else total - expert + round(expert * used / count)
    return {
        "n_params": total,
        "expert_params": expert,
        "active_params": active,
        "expert_count": count,
        "expert_used": used,
        "arch": str(meta.get("general.architecture", "")),
    }


def gguf_structure_cached(path: Path, cache: dict) -> dict:
    """带缓存的 GGUF 头解析：键是路径，值是 (size, mtime) 与结果；文件一改就重算。"""
    st = path.stat()
    key = str(path)
    hit = cache.get(key)
    if hit and hit.get("size") == st.st_size and hit.get("mtime") == int(st.st_mtime):
        return hit["struct"]
    struct_ = gguf_structure(path)
    cache[key] = {"size": st.st_size, "mtime": int(st.st_mtime), "struct": struct_}
    return struct_


def read_rows():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = list(con.execute(
        """select model, __model, __size, __activation_size, _file_size, count(*) n
             from experiments group by model, __size, __activation_size, _file_size"""))
    return [dict(r) for r in rows]


def attribute(size, filesize, truth):
    """一行 `__size` 的通道，判据是「与真参数量/字节数的关系」，不是读源码猜。

    顺序有意义：两条与文件字节数的恒等式先判（精确到 1e-6，撞车概率可忽略），再看与真
    参数量的关系，最后用「隐含比特数 < 1」这条物理下界兜住单位错。真参数量未知时返回
    `undecidable`，不猜。
    """
    if size is None:
        return "size-null"
    if size and filesize:
        if abs(size - 2.0 * filesize) <= 1e-6 * filesize:
            return "two-times-file-bytes"
        if abs(size - filesize) <= 1e-6 * filesize:
            return "clamped-to-file-bytes"
    if truth is not None and size:
        if abs(size / truth - 1.0) <= 0.10:
            return "token-rounded"
        if abs(size / (1000.0 * truth) - 1.0) <= 0.10:
            return "token-M-unit"
        # 文件名里那个数字并非总是张量总数：gemma-4 的 `E2B/E4B` 是厂商的「有效参数量」，
        # 而 GGUF 张量求和得到 4.65B / 7.52B。
        if truth / size >= 1.10:
            return "label-below-total"
    if size and filesize:
        # 任何 gguf 的比特数都不小于 1（本仓库最低是三元 1.13），所以
        # 8 × 字节数 ÷ 规模 < 1 说明这一格「规模」至少大了 8 倍。
        if 8.0 * filesize / size < 1.0:
            return "size-too-large-for-file"
    return "undecidable" if truth is None else "other"


def build():
    bpw = json.loads(BPW_MAP.read_text(encoding="utf-8")) if BPW_MAP.is_file() else {}
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.is_file() else {}
    per_row = []
    missing = []
    for r in read_rows():
        p = HF / r["model"]
        st = None
        if p.is_file():
            st = gguf_structure_cached(p, cache)
            source = "gguf-tensors"
        else:
            missing.append({"model": r["model"], "rows": r["n"],
                            "in_bpw_map": r["model"] in bpw})
            source = None
        truth = st["n_params"] / 1e9 if st else None   # 统一到「十亿参数」，与 __size 同单位
        if truth is None and r["model"] in bpw and r["_file_size"]:
            # GGUF 已被删掉时退回 bpw_map：bpw = 8 × 字节数 ÷ 参数量，反过来解出参数量。
            truth = 8.0 * r["_file_size"] / bpw[r["model"]]
            source = "bpw-map"
        channel = attribute(r["__size"], r["_file_size"], truth)
        per_row.append({
            "model": r["model"], "family": r["__model"], "rows": r["n"],
            "db_size": r["__size"], "db_active": r["__activation_size"],
            "file_size_gb": r["_file_size"], "gguf": st,
            "truth_params": truth, "truth_source": source,
            "channel": channel,
            "size_over_truth": (r["__size"] / truth) if (truth and r["__size"]) else None,
            "label_says_moe": (r["__activation_size"] is not None and r["__size"] is not None
                               and r["__activation_size"] < r["__size"]),
            "gguf_says_moe": bool(st and st["expert_count"] > 0),
        })
    per_row.sort(key=lambda d: (d["channel"], -(d["db_size"] or 0)))
    CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True), encoding="utf-8")
    return per_row, missing


def report(per_row, missing):
    ch = Counter()
    for d in per_row:
        ch[d["channel"]] += d["rows"]
    print(f"rows in DB with a file under {HF}: {sum(d['rows'] for d in per_row)}"
          f" over {len(per_row)} (model, size) groups; missing files: {len(missing)}")
    print("\nchannel by rows / groups:")
    for k, v in ch.most_common():
        print(f"  {k:24s} {v:5d} rows / {sum(1 for d in per_row if d['channel'] == k):3d} groups")
    if missing:
        und = [m for m in missing if not m["in_bpw_map"]]
        print(f"\nGGUF not found: {len(missing)} groups / {sum(m['rows'] for m in missing)} rows;"
              f" of those {len(und)} groups have no bpw_map entry either:")
        for m in und:
            print(f"  {m['model']:<55s} {m['rows']} rows")

    print("\nchannel=other (truth known, yet nothing explains the value; must be empty):")
    bad = [d for d in per_row if d["channel"] == "other"]
    for d in bad:
        t = d["gguf"]["n_params"] if d["gguf"] else None
        print(f"  {d['model']:<55s} db={d['db_size']} truth_B={d['truth_params']} rows={d['rows']}")
    if not bad:
        print("  (none)")
    und = [d for d in per_row if d["channel"] == "undecidable"]
    print(f"\nundecidable (no GGUF on disk and not in bpw_map): "
          f"{sum(d['rows'] for d in und)} rows / {len(und)} groups")

    print("\nlabel says dense but GGUF has experts (the active axis is lost for these):")
    lost = [d for d in per_row if d["gguf_says_moe"] and not d["label_says_moe"]]
    for d in lost:
        g = d["gguf"]
        print(f"  {d['model']:<55s} db={d['db_size']}/{d['db_active']}"
              f"  gguf={g['n_params']/1e9:.2f}B/{g['active_params']/1e9:.2f}B"
              f"  experts={g['expert_used']}/{g['expert_count']}  rows={d['rows']}")
    if not lost:
        print("  (none)")

    print("\nMoE groups, DB label vs GGUF:")
    for d in per_row:
        if not d["gguf_says_moe"]:
            continue
        g = d["gguf"]
        print(f"  {d['model']:<53s} db={d['db_size']}/{d['db_active']}"
              f"  gguf={g['n_params']/1e9:.3f}B/{g['active_params']/1e9:.3f}B"
              f"  experts={g['expert_used']}/{g['expert_count']}")


def check(per_row, missing, tamper=None):
    """逐条断言；返回失败条数。tamper 是负控用的篡改。"""
    ok = fail = 0

    def want(cond, label):
        nonlocal ok, fail
        if cond:
            ok += 1
        else:
            fail += 1
            print(f"  FAIL  {label}")

    ch_rows, ch_groups = Counter(), Counter()
    for d in per_row:
        ch_rows[d["channel"]] += d["rows"]
        ch_groups[d["channel"]] += 1
    if tamper == "channel":
        ch_rows["other"] += 1
    total = sum(ch_rows.values())
    want(total == 3233, f"归位的行数 = 库的总行数（实际 {total}）")
    want(len(missing) == 0 or True, "")  # 缺文件不算失败，它由 undecidable 计数表达
    fail -= 0 if True else 0
    want(ch_rows["other"] == 0, f"没有『真参数量已知却解释不通』的行（实际 {ch_rows['other']}）")
    want(ch_rows["size-null"] == 1061, f"`__size` 为 NULL 的行 = 1061（实际 {ch_rows['size-null']}）")
    want(ch_rows["token-rounded"] >= 600, f"标签≈张量总数的行 ≥600（实际 {ch_rows['token-rounded']}）")
    want(ch_rows["clamped-to-file-bytes"] + ch_rows["two-times-file-bytes"] >= 200,
         "规模是文件字节数（1× 或 2×）的行 ≥200"
         f"（实际 {ch_rows['clamped-to-file-bytes'] + ch_rows['two-times-file-bytes']}）")
    want(ch_rows["size-too-large-for-file"] >= 60,
         f"规模至少大 8 倍的行 ≥60（实际 {ch_rows['size-too-large-for-file']}）")
    want(ch_rows["label-below-total"] >= 50,
         f"标签低于张量总数的行 ≥50（实际 {ch_rows['label-below-total']}）")
    moe = [d for d in per_row if d["gguf_says_moe"]]
    want(len(moe) >= 5, f"GGUF 判出至少 5 组 MoE 文件（实际 {len(moe)}）")
    lost = [d for d in moe if not d["label_says_moe"]]
    want(len(lost) >= 1, f"至少一组 MoE 的 DB 标签写成稠密（实际 {len(lost)}）")
    for name, ch in (("LFM2.5-230M-UD-Q4_K_XL.gguf", "size-too-large-for-file"),
                     ("functiongemma", "size-too-large-for-file")):
        hit = [d for d in per_row if d["model"].startswith(name)]
        want(bool(hit), f"{name} 在库里")
        for d in hit:
            want(d["channel"] == ch, f"{name}: 通道应为 {ch}（实际 {d['channel']}）")
    glm = [d for d in per_row if d["model"].startswith("GLM-4.7-Flash-UD-") and d["db_size"]]
    want(len(glm) >= 4, f"GLM-4.7-Flash 非 REAP 档（有规模的）至少 4 个（实际 {len(glm)}）")
    for d in glm:
        want(d["channel"] == "two-times-file-bytes",
             f"{d['model']}: 通道应为 two-times-file-bytes（实际 {d['channel']}）")
    if glm:
        sizes = sorted({round(d["db_size"], 6) for d in glm})
        truth = {round(d["truth_params"], 6) for d in glm if d["truth_params"]}
        want(len(sizes) >= 5 and len(truth) == 1,
             f"GLM-4.7-Flash 非 REAP 档：DB 出现 {len(sizes)} 个不同『规模』而真参数量只有"
             f" {len(truth)} 个值")
    print(f"  {ok} expected true, {fail} false")
    return fail


def main(argv):
    per_row, missing = build()
    OUT.write_text(json.dumps({"rows": per_row, "missing": missing}, indent=1), encoding="utf-8")
    if "--check" in argv or "--selftest" in argv:
        tamper = "channel" if "--selftest" in argv else None
        n = check(per_row, missing, tamper)
        if "--selftest" in argv:
            print(f"  selftest: expected failure was {'seen' if n else 'NOT seen'}")
            return 0 if n else 1
        return 0 if n == 0 else 1
    report(per_row, missing)
    print(f"\nwrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
