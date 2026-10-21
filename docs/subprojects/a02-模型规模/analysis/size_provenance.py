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
# 真值的第二来源：入库的 fixture（GGUF 本身不入 git）。`A02_HF_ROOT` 只为负控——
# 指向一个不存在的目录就等价于「干净 clone 里没有 GGUF」，此时检查必须靠 fixture 仍然全绿。
HF = Path(os.environ.get("A02_HF_ROOT", "/home/z/hf"))
FIXTURE = HERE / "fixtures" / "gguf_truth.json"
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
    fixture = (json.loads(FIXTURE.read_text(encoding="utf-8"))["models"]
               if FIXTURE.is_file() else {})
    per_row = []
    missing = []
    for r in read_rows():
        p = HF / r["model"]
        st = None
        source = None
        if p.is_file():
            st = gguf_structure_cached(p, cache)
            source = "gguf-tensors"
        else:
            missing.append({"model": r["model"], "rows": r["n"],
                            "in_bpw_map": r["model"] in bpw,
                            "in_fixture": r["model"] in fixture})
        truth = st["n_params"] / 1e9 if st else None   # 统一到「十亿参数」，与 __size 同单位
        if truth is None and r["model"] in fixture:
            # 现场没有 GGUF 就退回入库的 fixture（同一批头解析结果，见 build_fixtures.py）。
            truth = fixture[r["model"]]["n_params"] / 1e9
            st = {"n_params": fixture[r["model"]]["n_params"],
                  "expert_params": fixture[r["model"]]["expert_params"],
                  "active_params": fixture[r["model"]]["active_params"],
                  "expert_count": fixture[r["model"]]["expert_count"],
                  "expert_used": fixture[r["model"]]["expert_used"],
                  "arch": fixture[r["model"]]["arch"]}
            source = "fixture"
        if truth is None and r["model"] in bpw and r["_file_size"]:
            # fixture 也没有时退回 bpw_map：bpw = 8 × 字节数 ÷ 参数量，反过来解出参数量。
            truth = 8.0 * r["_file_size"] / bpw[r["model"]]
            source = "bpw-map"
        channel = attribute(r["__size"], r["_file_size"], truth)
        per_row.append({
            "model": r["model"], "family": r["__model"], "rows": r["n"],
            "db_size": r["__size"], "db_active": r["__activation_size"],
            "file_size_gb": r["_file_size"], "gguf": st,
            "truth_params": truth, "truth_source": source,
            "on_disk": p.is_file(),
            "channel": channel,
            "size_over_truth": (r["__size"] / truth) if (truth and r["__size"]) else None,
            "label_says_moe": (r["__activation_size"] is not None and r["__size"] is not None
                               and r["__activation_size"] < r["__size"]),
            "gguf_says_moe": bool(st and st["expert_count"] > 0),
        })
    per_row.sort(key=lambda d: (d["channel"], -(d["db_size"] or 0)))
    CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True), encoding="utf-8")
    return per_row, missing


def db_counts():
    """库当前的总行数与 `__size` 为空的行数。断言只说「与库一致」，不说「等于 3233」。"""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    n, nulls = con.execute("select count(*), sum(__size is null) from experiments").fetchone()
    con.close()
    return n, int(nulls)


def channel_ok(d):
    """每个通道的成员必须满足它自己的定义。这是关系式，不是快照，新数据进来也不会红。"""
    ch, size, fs, t = d["channel"], d["db_size"], d["file_size_gb"], d["truth_params"]
    if ch == "size-null":
        return size is None
    if ch == "two-times-file-bytes":
        return bool(fs and size and abs(size - 2.0 * fs) <= 1e-6 * fs)
    if ch == "clamped-to-file-bytes":
        return bool(fs and size and abs(size - fs) <= 1e-6 * fs)
    if ch == "token-rounded":
        return bool(t and size and abs(size / t - 1.0) <= 0.10)
    if ch == "label-below-total":
        return bool(t and size and t / size >= 1.10)
    if ch == "size-too-large-for-file":
        return bool(fs and size and 8.0 * fs / size < 1.0)
    return True          # undecidable / other 由别的条款管


def report(per_row, missing):
    ch = Counter()
    for d in per_row:
        ch[d["channel"]] += d["rows"]
    on_disk = sum(d["rows"] for d in per_row if d["on_disk"])
    print(f"rows: {sum(d['rows'] for d in per_row)} over {len(per_row)} (model, size) groups;"
          f" GGUF on disk for {on_disk} rows ({len(missing)} groups absent from {HF})")
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
    db_rows, db_null = db_counts()
    want(total == db_rows, f"归位的行数 = 库的总行数（{total} vs 库 {db_rows}）")
    # 通道→定义：每个通道的成员都得真的满足那条定义（关系式，不是计数快照）
    bad_def = [d for d in per_row if not channel_ok(d)]
    want(not bad_def, "每个通道的成员都满足该通道的定义：" +
         f"实际违反 {[(d['model'], d['channel']) for d in bad_def][:3]}")
    # 真值来源与通道必须自洽：有真值的组不能判「不可判」，判「不可判」的组必须没有真值。
    # 这条在干净 clone（没有 GGUF、只靠 fixture）与现场（有 GGUF）两种情形下都必须成立。
    with_truth = [d for d in per_row if d["truth_params"] is not None]
    undec = [d for d in per_row if d["channel"] == "undecidable"]
    want(not [d for d in with_truth if d["channel"] == "undecidable"],
         f"有真值的组不得判 undecidable（实际 {len([d for d in with_truth if d['channel'] == 'undecidable'])}）")
    want(all(d["truth_params"] is None for d in undec),
         "判 undecidable 的组必须真的没有真值")
    # 没有真值时只有三条与文件字节数有关的通道还能判（它们不需要真值），其余只能叫 undecidable。
    NO_TRUTH_OK = {"undecidable", "two-times-file-bytes", "clamped-to-file-bytes",
                   "size-too-large-for-file"}
    leak = [d for d in per_row if d["truth_params"] is None and d["channel"] not in NO_TRUTH_OK]
    want(not leak, "没有真值的组不得被判成需要真值的通道（token-rounded / label-below-total / other）："
                   f"实际 {[(d['model'], d['channel']) for d in leak][:3]}")
    explained = [d for d in per_row if d["truth_params"] is None and d["channel"] != "undecidable"]
    want(len(undec) + len(explained) == len([d for d in per_row if d["truth_params"] is None]),
         f"无真值组 = undecidable + 由字节数解释（{len(undec)} + {len(explained)} vs "
         f"{len([d for d in per_row if d['truth_params'] is None])}）")
    # fixture 覆盖关系：库里每个在 fixture 里的模型文件，都必须拿到真值（fixture 腐化就会红）
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))["models"] if FIXTURE.is_file() else {}
    lost_fx = [d for d in per_row if d["model"] in fx and d["truth_params"] is None]
    want(not lost_fx, f"fixture 里有的模型都拿到了真值（缺 {len(lost_fx)} 个："
                      f"{[d['model'] for d in lost_fx][:3]}）")
    want(all(d["truth_source"] in ("gguf-tensors", "fixture", "bpw-map") for d in with_truth),
         "有真值的组都记了来源（gguf-tensors / fixture / bpw-map）")
    want(len(with_truth) > 0, "至少有一组真值（否则下游全是未测）")
    unres = [m for m in missing if not (m["in_bpw_map"] or m["in_fixture"])]
    want(len(missing) - len(unres) == len([m for m in missing if m["in_fixture"]]),
         "缺文件里已由 fixture 或 bpw_map 兜住的，都真的有来源")
    want(ch_rows["other"] == 0, f"没有『真参数量已知却解释不通』的行（实际 {ch_rows['other']}）")
    want(ch_rows["size-null"] == db_null,
         f"`__size` 为空的行 = 库里为空的行（{ch_rows['size-null']} vs 库 {db_null}）")
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
    glm_files = {d["model"] for d in per_row if d["model"].startswith("GLM-4.7-Flash-UD-")}
    want(bool(glm_files), "GLM-4.7-Flash 非 REAP 档在库里")
    for d in glm:
        want(d["channel"] == "two-times-file-bytes",
             f"{d['model']}: 通道应为 two-times-file-bytes（实际 {d['channel']}）")
    if glm:
        sizes = sorted({round(d["db_size"], 6) for d in glm})
        truth = {round(d["truth_params"], 6) for d in glm if d["truth_params"]}
        want(len(sizes) >= 2 and len(truth) == 1,
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
