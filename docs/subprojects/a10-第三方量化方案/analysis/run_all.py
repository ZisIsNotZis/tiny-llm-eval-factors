#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a10 第三方量化方案：本层的验收装置。退出码就是结论。

    0  全部断言成立
    1  有断言翻红（打印是哪一条、夹具与源的哪个值不一样）
    2  看不到输入（缺夹具 / 缺库 / 库缺格）—— 「不可得」不是「通过」

断言只读**入库夹具** `analysis/fixtures/a10_map.json`、`experiments.sqlite` 与 `.wrapup/bpw_map.json`，
所以干净 clone 里同样能跑（gguf 不在 git 里，它的一切数都在夹具里，`build_fixture.py --check` 负责漂移）。

`--selftest` 用三份**已知错误的副本**（把 IQ3_S 的 HumanEval 分数抬高 0.05、改掉一个跨上传者的
张量指纹、把 IQ3_XXS 的 embed 比特抬高 0.5）证明这些检查会失败；不然「绿」只证明脚本能跑。

    0 = 全部断言成立 / 三次扰动都被抓到（负控成立）
    1 = 有断言翻红 / 有扰动没被抓到（负控不成立）

用法：
    python3 "docs/subprojects/a10-第三方量化方案/analysis/run_all.py"
    python3 ".../run_all.py" --selftest
"""
from __future__ import annotations

import argparse
import copy
import json
import sqlite3
import sys

import panel
import position as pos

NATIVE_MONO_COLUMNS = 7          # 2.878 → 3.850 这一步在 9 列里有 7 列是负的（见 ladder-own-step）


def cells_from_fixture(doc):
    """夹具里的分数格 → `position.py` 认识的结构。"""
    return {m: {b: dict(c) for b, c in per.items()} for m, per in doc["cells"].items()}


def resolved(ci):
    return ci is not None and ci[0] * ci[1] > 0 and abs(ci[0]) > 1e-12 and abs(ci[1]) > 1e-12


def check(name, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def run(doc, db_path):
    """全部断言。返回 (通过条数, 失败条数)。"""
    ok = bad = 0
    files = doc["files"]
    cells = cells_from_fixture(doc)
    tp = doc["third_party"]
    nat = doc["native"]
    benches = doc["bench_order"]

    def A(name, cond, detail=""):
        nonlocal ok, bad
        if check(name, cond, detail):
            ok += 1
        else:
            bad += 1

    # ---- 1. 同族是实测的：张量集合与参数量逐项相同 ----
    ref = files[nat[0]]
    A("tensor-set: 五个面板文件的张量数、参数量、张量名集合逐项相同",
      all(files[m]["n_tensors"] == ref["n_tensors"]
          and files[m]["n_params"] == ref["n_params"]
          and files[m]["names_sha"] == ref["names_sha"] for m in tp + nat),
      f"张量 {ref['n_tensors']} 个、参数 {ref['n_params']:,}")

    # ---- 2. 同 tier 标签换上传者/换 base 权重后，逐张量分配是否相同 ----
    for tp_file, tier in doc["tier"].items():
        for sib, meta in doc["siblings"].items():
            if meta["tier"] != tier:
                continue
            a, b = files[tp_file], files[sib]
            A(f"recipe-determinate: {tier} 在 {meta['vendor']} 手里逐张量比特相同",
              a.get("tensor_sha") == b.get("tensor_sha"),
              f"{sib} tensor_sha 相同 = {a.get('tensor_sha') == b.get('tensor_sha')}")

    # ---- 3. 位宽与 bpw_map 一致；逐类比重复现总位宽 ----
    for m in tp + nat:
        A(f"bpw-map: {m} 的夹具位宽 == .wrapup/bpw_map.json",
          abs(files[m]["bpw_file"] - panel.BPW[m]) < 5e-4,
          f"{files[m]['bpw_file']:.4f} vs {panel.BPW[m]:.4f}")
    for m in tp + nat:
        tot_e = sum(c["params"] for c in files[m]["classes"].values())
        tot_b = sum(c["bytes"] for c in files[m]["classes"].values())
        A(f"alloc-recomputes: {m} 的 Σ字节×8÷Σ参数 复现位宽（差 ≤0.02）",
          abs(8.0 * tot_b / tot_e - files[m]["bpw_file"]) <= 0.02,
          f"{8.0 * tot_b / tot_e:.4f} vs {files[m]['bpw_file']:.4f}")

    # ---- 4. 几何：最近原生档的位宽缺口与分配差 ----
    import alloc_a10  # 只借它的加权 |Δ| 定义，不重新读盘
    for tp_file, want_dbpw, want_alloc in ((tp[0], 0.180, 0.209), (tp[1], -0.301, 0.301)):
        ties = panel.nearest_native(panel.BPW[tp_file])
        near = ties[0][1]
        dbpw = panel.BPW[tp_file] - panel.BPW[near]
        A(f"geometry: {panel.TIER[tp_file]} 的最近原生档与 Δbpw",
          near == (nat[0] if want_dbpw > 0 else nat[1]) and abs(dbpw - want_dbpw) < 5e-3,
          f"最近 {near}, Δbpw={dbpw:+.3f}（期望 {want_dbpw:+.3f}）")
        w, _per = alloc_a10.weighted_abs_diff(files[tp_file], files[near])
        A(f"alloc-gap: {panel.TIER[tp_file]} 对最近原生档的参数加权 |Δ|",
          abs(w - want_alloc) < 5e-3, f"{w:.3f} 比特/参数（期望 {want_alloc:.3f}）")

    # ---- 5. 位置：逐基准的区间与「分得开」的格数 ----
    sl = pos.slopes()
    out = {m: pos.position_of(m, cells, sl) for m in tp}
    near_res = {}
    for m in tp:
        near_res[m] = [b for b in benches
                       if "ci" in out[m]["nearest"][0]["cells"].get(b, {})
                       and resolved(out[m]["nearest"][0]["cells"][b]["ci"])]
    A("position-nearest: IQ3_XXS 对最近原生档 9 列全部不可分辨",
      near_res[tp[0]] == [], f"分得开的列 = {near_res[tp[0]]}")
    A("position-nearest: IQ3_S 对最近原生档只有 HumanEval 一列分得开",
      near_res[tp[1]] == ["humaneval"], f"分得开的列 = {near_res[tp[1]]}")
    he = out[tp[1]]["nearest"][0]["cells"]["humaneval"]
    A("position-nearest: 那一列的差值与区间",
      abs(he["delta"] - 0.0671) < 5e-4 and he["ci"][0] > 0
      and abs(he["ci"][0] - 0.0031) < 2e-3, f"Δ={he['delta']:+.4f} CI=[{he['ci'][0]:+.4f},{he['ci'][1]:+.4f}]")
    A("position-nearest: 那一列的比特预算与差反向（缺口不是解释）",
      he["budget"] < 0, f"比特预算={he['budget']:+.4f}")
    inter_res = {m: [b for b in benches
                     if "ci" in out[m]["interp"]["cells"][b]
                     and resolved(out[m]["interp"]["cells"][b]["ci"])] for m in tp}
    A("position-interp: 两个档对插值档的 18 个格里 0 格分得开",
      inter_res[tp[0]] == [] and inter_res[tp[1]] == [],
      f"{inter_res}")
    total = 2 * 9 + 2 * 9
    with_ci = total - 4          # TruthfulQA 不套二项区间（`i01::res26`）：两个档 × 两种比法
    n_res = len(near_res[tp[0]]) + len(near_res[tp[1]]) + len(inter_res[tp[0]]) + len(inter_res[tp[1]])
    A("multiplicity: 全部 36 个格里只有 32 个有区间，其中 1 格分得开（95% 名义水平下期望 1.6 格）",
      total == 36 and with_ci == 32 and n_res == 1, f"{n_res}/{with_ci}（共 {total} 格）")

    # ---- 6. 插值的分母：原生阶梯自己不单调 ----
    steps = pos.ladder_steps(cells)
    neg = [b for b, c in steps[0]["cells"].items() if c["delta"] < 0]
    A(f"ladder-own-step: 2.878 → 3.850 这一步在 {NATIVE_MONO_COLUMNS} 列上是负的",
      len(neg) == NATIVE_MONO_COLUMNS, f"负的列 {neg}")
    nonpos = [b for b, c in steps[1]["cells"].items() if c["delta"] <= 0]
    A("ladder-own-step: 3.850 → 4.173 这一步有 1 列 ≤0",
      len(nonpos) == 1, f"≤0 的列 {nonpos}")

    # ---- 7. 本库不存在「同字节 + 同分配 + 不同方案」的配对 ----
    pairs_same_bits = [(t, n) for t in tp for n in nat
                       if abs(panel.BPW[t] - panel.BPW[n]) <= 0.05]
    pairs_same_alloc = [(t, n) for t in tp for n in nat
                        if files[t]["tensor_sha"] == files[n]["tensor_sha"]]
    A("no-held-arm: 与第三方档同字节（|Δbpw| ≤ 0.05）的原生档个数 = 0",
      pairs_same_bits == [], f"{pairs_same_bits}")
    A("no-held-arm: 与第三方档同分配（逐张量比特相同）的原生档个数 = 0",
      pairs_same_alloc == [], f"{pairs_same_alloc}")

    # ---- 8. 报告的分类器看不见这批文件名（只在报告里念，不改 mktables） ----
    sys.path.insert(0, str(panel.REPO / ".wrapup"))
    import mktables
    for m in tp:
        stem, q = mktables.split_quant(m)
        A(f"classifier-blind: {m} 的档位解析为 None 且方案类判成「原生 K」",
          q is None and mktables.scheme_class(m) == "原生 K",
          f"split_quant → ({stem!r}, {q!r})，scheme_class → {mktables.scheme_class(m)!r}")

    # ---- 9. 库内事实：-mtp 没有当草稿用；MultiPL-E 列没有格 ----
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    for m in tp:
        rows = con.execute("SELECT DISTINCT spec_type, spec_draft_n_max FROM experiments"
                           " WHERE model=?", (m,)).fetchall()
        A(f"no-spec: {m} 的行 spec_type=none 且 spec_draft_n_max=0",
          rows == [("none", "0")], f"{rows}")
        n_mpl = con.execute("SELECT COUNT(*) FROM experiments WHERE model=?"
                            " AND (protocol LIKE 'mpl%' OR protocol LIKE 'multipl%')",
                            (m,)).fetchone()[0]
        A(f"unmeasured-mpl: {m} 在 MultiPL-E 协议上的行数 = 0（未测，不是 0 分）",
          n_mpl == 0, f"{n_mpl} 行")
    con.close()

    # ---- 10. 夹具的分数格与库一致（漂移检查；db 由调用方给） ----
    live, _dups = panel.cells()
    drift = [f"{m}/{b}" for m in tp + nat for b in benches
             if abs(live[m][b]["score"] - doc["cells"][m][b]["score"]) > 1e-12
             or live[m][b]["n_items"] != doc["cells"][m][b]["n_items"]]
    A("fixture-drift: 夹具里的 45 个分数格与 experiments.sqlite 一致",
      drift == [], f"{drift[:5]}")
    return ok, bad


def selftest(doc, db_path):
    """用已知错误的副本证明检查会失败：三次扰动，三次都必须翻红。"""
    global_ok = True
    tp = doc["third_party"]

    cases = []

    d1 = copy.deepcopy(doc)
    d1["cells"][tp[1]]["humaneval"]["score"] += 0.05
    cases.append(("抬高 IQ3_S 的 HumanEval 分数 0.05", d1,
                  "position-nearest: 那一列的差值与区间"))

    d2 = copy.deepcopy(doc)
    sib = next(k for k, v in doc["siblings"].items() if v["tier"] == doc["tier"][tp[0]])
    d2["files"][sib]["tensor_sha"] = "0" * 64
    cases.append(("改掉一个跨上传者的张量指纹", d2, "recipe-determinate"))

    d3 = copy.deepcopy(doc)
    d3["files"][tp[0]]["classes"]["embed"]["bits"] += 0.5
    cases.append(("把 IQ3_XXS 的 embed 比特抬高 0.5", d3, "alloc-gap"))

    for label, dd, needle in cases:
        print(f"\n-- 自检：{label}（期望翻红，且翻在「{needle[:40]}…」上）")
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _ok, badn = run(dd, db_path)
        failed = [ln.strip() for ln in buf.getvalue().splitlines() if "[FAIL]" in ln]
        hit = any(needle in ln for ln in failed)
        print(f"   翻红 {badn} 条；命中预期条目: {hit}")
        if badn == 0 or not hit:
            print("   自检不成立：扰动没有让预期断言翻红")
            global_ok = False
    return 0 if global_ok else 1


def main(argv=()):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true",
                    help="用已知错误的副本证明检查会翻红（负控成立时退出 0）")
    a = ap.parse_args(list(argv) or None)
    doc = panel.load_fixture()
    db_path = panel.REPO / "experiments.sqlite"
    if not db_path.is_file():
        print(f"看不到输入：缺 {db_path}（退出 2，不是 0）", file=sys.stderr)
        return 2
    print(f"夹具 {panel.FIXTURE.relative_to(panel.REPO)}；库 {db_path.name}")
    print(f"第三方档 {doc['third_party']}\n原生阶梯 {doc['native']}\n")
    if a.selftest:
        return selftest(doc, db_path)
    ok, bad = run(doc, db_path)
    print(f"\n{ok} 条成立，{bad} 条翻红")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
