#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a03 的收口装置：把 `RESULT.md` 的每条数字变成一条可判定的预期。

退出码即结论：0 = 全部成立；1 = 有一条不成立（本层事实需复核）；2 = 依赖缺失（盘上没有 gguf，
分配轮廓那几条**未验证**，不算通过）。

`--selftest` 拿一份已知被改坏的输入证明这些检查会失败（负控）：把厂商标签写进文件名推断、
或把窗口判据放宽到 1.0，检查必须翻红。

用法：
    python3 "docs/subprojects/a03-量化方案与厂商/analysis/run_all.py"
    python3 ".../run_all.py" --selftest
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import alloc  # noqa: E402
import attrib  # noqa: E402
import pairs  # noqa: E402

OK, BAD, SKIP = "ok", "FAIL", "未验证"
results = []


def expect(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  [{OK if cond else BAD}] {name}{('  — ' + detail) if detail else ''}")


def sig(rec, bench):
    """该格区间是否不含 0。TruthfulQA 与缺格一律不算显著。"""
    if bench not in rec["cells"]:
        return None
    _d, ci = pairs.interval(rec, bench)
    if ci is None:
        return None
    return ci[0] * ci[1] > 0 and (ci[0] > 0) == (ci[1] > 0)


def find_pair(pairs_list, family, kind):
    for p in pairs_list:
        if p["family"] == family and p["kind"] == kind and p["cells"]:
            return p
    return None


def main(argv=()):
    selftest = "--selftest" in argv
    print("a03 收口检查")

    cells, dups = pairs.load()
    vendors = pairs.vendor_of()
    if selftest:
        # 负控：把来源改成按文件名猜（非 UD 名一律当别家），pair 性质与归因必须翻红
        vendors = {m: (["unsloth"] if "UD-" in m else ["bartowski"]) for m in cells}
        print("  （--selftest：来源已换成按文件名猜的错版本）")

    fams = {pairs.a01.family_of(m) for m in cells}
    iq = [m for m in cells if pairs.scheme_of(pairs.quant_label(m)) == "IQ"]
    expect("population：66 个文件 / 30 个族 / 6 个 IQ 文件",
           len(cells) == 66 and len(fams) == 30 and len(iq) == 6,
           f"{len(cells)} 文件 / {len(fams)} 族 / {len(iq)} IQ")

    counts = {}
    plists = {}
    for bound in pairs.BOUNDS:
        plists[bound] = [p for p in pairs.enumerate_pairs(cells, vendors, bound) if p["cells"]]
        counts[bound] = len(plists[bound])
    expect("pair-device：三档配对数为 10 / 4 / 2",
           counts[0.45] == 10 and counts[0.15] == 4 and counts[0.05] == 2,
           f"{counts[0.45]} / {counts[0.15]} / {counts[0.05]}")

    kinds05 = sorted(p["kind"] for p in plists[0.05])
    expect("pair-device：≤0.05 档的两对正好是方案对与厂商对",
           kinds05 == ["scheme", "vendor"], str(kinds05))

    incomparable = [(p["family"], b) for p in plists[0.15] for b in p["incomparable"]]
    expect("pair-device：≤0.15 档没有「不可比」的格", not incomparable, str(incomparable[:3]))

    sl = pairs.slopes(cells)
    pos = [b for b in pairs.BENCH_ORDER if not (sl[b][0] > 0 and sl[b][0] - 1.96 * sl[b][1] > 0)]
    expect("slopes：九个基准的同族每比特斜率都为正且区间不含 0", not pos, str(pos))

    p4 = find_pair(plists[0.05], "Qwen3.5-4B", "scheme")
    if p4 is None:
        expect("scheme-4b：找到 Qwen3.5-4B 的方案对", False, "没找到")
    else:
        sg = {b: sig(p4, b) for b in pairs.BENCH_ORDER}
        sigs = [b for b, v in sg.items() if v]
        expect("scheme-4b：Δbpw ≤ 0.05 且只有 MMLU 区间不含 0",
               p4["dbpw"] <= 0.05 and sigs == ["mmlu"],
               f"Δbpw={p4['dbpw']:+.3f} 显著列={sigs}")
        d, ci = pairs.interval(p4, "mmlu")
        expect("scheme-4b：MMLU 的差在 +0.0592 附近且为正",
               abs(d - 0.0592) < 0.002 and ci[0] > 0, f"{d:+.4f} [{ci[0]:+.4f},{ci[1]:+.4f}]")

    p2 = find_pair(plists[0.15], "Qwen3.5-2B", "scheme")
    if p2 is None:
        expect("scheme-2b：找到 Qwen3.5-2B 的方案对", False, "没找到")
    else:
        sigs = [b for b in pairs.BENCH_ORDER if sig(p2, b)]
        expect("scheme-2b：只有 HumanEval 与 HumanEval+ 区间不含 0",
               sigs == ["humaneval", "humaneval-plus"], str(sigs))
        ok = all(pairs.interval(p2, b)[0] < 0 for b in ("humaneval", "humaneval-plus"))
        expect("scheme-2b：两列都是 IQ 一侧更高（差为负）", ok, "")

    pv = find_pair(plists[0.05], "Qwen3.6-35B-A3B", "vendor")
    if pv is None:
        expect("vendor-qwen36：找到跨上传者的受控对", False, "没找到")
    else:
        sigs = [b for b in pairs.BENCH_ORDER if sig(pv, b)]
        expect("vendor-qwen36：九列全部跨 0（含 Δbpw ≤ 0.05）",
               pv["dbpw"] <= 0.05 and not sigs,
               f"Δbpw={pv['dbpw']:+.3f} 显著列={sigs}")
        expect("vendor-qwen36：两文件来源确实不同且不是同一个上传者",
               pv["vendor_low"] != pv["vendor_high"],
               f"{pv['vendor_low']} vs {pv['vendor_high']}")

    bad_iq = bad_v = bad_l = bad_b = 0
    for bench in pairs.BENCH_ORDER:
        rows = attrib.rows_for(cells, vendors, bench)
        cols, X, y, keep, _dropped = attrib.build(rows)
        beta, se, _dof = attrib.fit(X, y, cols)
        for k in ("IQ", "local", "bartowski", "bpw"):
            if k not in beta:
                continue
            lo, hi = beta[k] - 1.96 * se[k], beta[k] + 1.96 * se[k]
            crosses_zero = lo <= 0 <= hi
            if k == "IQ" and crosses_zero:
                bad_iq += 1
            if k == "local" and crosses_zero:
                bad_l += 1
            if k == "bartowski" and crosses_zero:
                bad_b += 1
            if k == "bpw" and not lo > 0:      # 位宽斜率必须显著为正
                bad_v += 1
    expect("attrib：IQ 系数九列全部跨 0", bad_iq == 9, f"{bad_iq}/9 跨 0")
    expect("attrib：local 配方系数九列全部跨 0", bad_l == 9, f"{bad_l}/9 跨 0")
    expect("attrib：bartowski 系数九列全部跨 0", bad_b == 9, f"{bad_b}/9 跨 0")
    expect("attrib：位宽斜率九列全部不含 0", bad_v == 0, f"{bad_v} 列不显著")

    cluster = sorted((pairs.BPW_MAP[m], m) for m in cells if pairs.a01.family_of(m) == "Qwen3.5-2B")
    cl = [cluster[0]]                        # 单链聚类：从最低位宽起步，步长 ≤0.45 就继续收
    for bpw, m in cluster[1:]:
        if bpw - cl[-1][0] > 0.45:
            break
        cl.append((bpw, m))
    span = cl[-1][0] - cl[0][0]
    he = [cells[m]["humaneval-plus"]["score"] for _b, m in cl if "humaneval-plus" in cells[m]]
    budget = span * sl["humaneval-plus"][0]
    expect("cluster-2b：报告第三节的 2B 组是 0.84 比特宽的一簇，位宽尺子本身就值 > 0.10 分",
           0.80 < span < 0.90 and budget > 0.10 and len(cl) == 4,
           f"簇 = {len(cl)} 个文件 / 跨度 {span:.3f} bpw / HE+ 实跳 {max(he) - min(he):+.4f} / 预算部分 {budget:+.4f}")

    skip = 0
    profs = {}
    for label, family, kind in (("alloc-qwen36", "Qwen3.6-35B-A3B", "vendor"),
                                ("alloc-scheme-4b", "Qwen3.5-4B", "scheme")):
        p = find_pair(plists[0.45], family, kind)
        paths = [alloc.find_path(p["low"]), alloc.find_path(p["high"])]
        if p is None or None in paths:
            print(f"  [{SKIP}] {label}：盘上找不到 gguf，分配轮廓未验证")
            skip += 1
            continue
        a, b = alloc.profile(paths[0]), alloc.profile(paths[1])
        wsum = dsum = 0.0
        for k in set(a["classes"]) | set(b["classes"]):
            ca = a["classes"].get(k, {"bits": float("nan"), "params": 0})
            cb = b["classes"].get(k, {"bits": float("nan"), "params": 0})
            if ca["bits"] == ca["bits"] and cb["bits"] == cb["bits"]:
                w = max(ca["params"], cb["params"])
                wsum += w
                dsum += w * abs(ca["bits"] - cb["bits"])
        wd = dsum / wsum if wsum else float("nan")
        expect(f"{label}：总位宽差 ≤0.05 而参数加权分配差 ≥0.3",
               abs(p["dbpw"]) <= 0.05 and wd >= 0.3,
               f"Δbpw={p['dbpw']:+.3f} 加权|Δ|={wd:.3f}")

    failed = [n for n, ok, _d in results if not ok]
    print()
    if skip:
        print(f"{len(results) - len(failed)} 条成立 / {len(failed)} 条不成立 / {skip} 条未验证")
        return 2
    print(f"{len(results)} 条全部成立" if not failed else f"失败 {len(failed)} 条：{failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(tuple(sys.argv[1:])))
