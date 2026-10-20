#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a04 的分配轮廓读数装置：把「同一套 base 权重、不同比特分配」的文件对列出来。

用法（仓库根执行）：

    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py"            # 全部轮廓 + 全部同参数对
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py" --family LFM2.5-8B-A1B
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/profiles.py" --scores LFM2.5-8B-A1B

轮廓只有一个来源：a03 的入库夹具 `docs/subprojects/a03-量化方案与厂商/analysis/fixtures/alloc_map.json`
（逐张量类别的 params / bytes / bits，由 gguf 张量信息段实测）。本脚本**只读**它，不重建、不改它；
a03 改了分类法本层就跟着变，这是有意为之——同一个事实不在这里存第二份。

分数只从 `experiments.sqlite` 的只读连接读，按 (`model`, `_bench`) 取 `n_items` 最大的那一行，
并把该行的 `protocol` 打印出来：协议不同就是不可比，调用者自己看得见，不在这里静默合并。

两个量必须分清：

    Δbpw    = bpw_file(A) - bpw_file(B)                  总有效位宽差（整个文件）
    L1_pw   = Σ_c |b_c(A) - b_c(B)| · p_c / p_total      参数加权分配距离（比特/参数）

`L1_pw ≈ |Δbpw|` 说明这一对基本只是总比特变了；`L1_pw ≫ |Δbpw|` 才是总比特钉住、比特挪了位置。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
ALLOC = os.path.join(REPO, "docs", "subprojects", "a03-量化方案与厂商",
                     "analysis", "fixtures", "alloc_map.json")
DB = os.path.join(REPO, "experiments.sqlite")
BENCHES = ["humaneval-plus", "mbpp-plus", "mmlu", "arc_challenge", "gsm8k", "ifeval"]
BPW_BINS = (0.05, 0.15, 0.45)


def load_alloc(path=ALLOC):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["models"]


def family_of(name):
    """族 = 同一套 base 权重。用参数数相等做机械判据，名字只用来分组打印。"""
    return name.split("-UD-")[0].split("-m55-")[0].replace(".gguf", "")


def l1_pw(a, b):
    """参数加权 L1 距离（比特/参数）。要求两份文件参数数相同，否则没有可比性。"""
    if a["n_params"] != b["n_params"]:
        raise ValueError("different n_params: %s vs %s" % (a["n_params"], b["n_params"]))
    total = 0.0
    for cls in a["classes"]:
        if cls not in b["classes"]:
            continue
        pa = a["classes"][cls]["params"]
        total += abs(a["classes"][cls]["bits"] - b["classes"][cls]["bits"]) * pa
    return total / a["n_params"]


def class_delta(a, b):
    out = []
    for cls in a["classes"]:
        if cls in b["classes"]:
            out.append((cls, a["classes"][cls]["bits"], b["classes"][cls]["bits"]))
    return out


def print_profiles(models, family):
    files = sorted((n for n in models if family in n), key=lambda n: models[n]["bpw_file"])
    if not files:
        print("no file matches family %r" % family)
        return 1
    classes = sorted({c for n in files for c in models[n]["classes"]})
    head = "%-40s %7s %6s " % ("file", "bpw", "params")
    print(head + " ".join("%9s" % c for c in classes))
    for n in files:
        m = models[n]
        row = "%-40s %7.3f %6.2fB " % (n, m["bpw_file"], m["n_params"] / 1e9)
        row += " ".join("%9.3f" % m["classes"].get(c, {}).get("bits", float("nan")) for c in classes)
        print(row)
    print()
    print("参数占比（同一套 base 权重时逐文件相同，取第一份）：")
    for c in classes:
        p = models[files[0]]["classes"][c]["params"]
        print("  %-10s %14d  %6.3f%%" % (c, p, 100.0 * p / models[files[0]]["n_params"]))
    return 0


def print_pairs(models, family=None, only_pinned=False):
    """同一套 base 权重（参数数相同）的全部文件对，按 Δbpw 分档。"""
    names = sorted(models)
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if family and (family not in a or family not in b):
                continue
            if models[a]["n_params"] != models[b]["n_params"]:
                continue
            dbpw = models[a]["bpw_file"] - models[b]["bpw_file"]
            l1 = l1_pw(models[a], models[b])
            rows.append((abs(dbpw), l1, a, b, dbpw))
    rows.sort(key=lambda r: (r[0], -r[1]))
    for bound in BPW_BINS:
        sel = [r for r in rows if r[0] <= bound]
        print("=== |Δbpw| ≤ %.2f ：%d 对 ===" % (bound, len(sel)))
        for ad, l1, a, b, dbpw in sel:
            tag = "PIVOT" if l1 >= 0.30 and ad <= bound else "     "
            print("%s Δbpw=%+.3f L1_pw=%5.3f  %-42s %-42s" % (tag, dbpw, l1, a, b))
        print()
    pinned = [r for r in rows if r[0] <= 0.15 and r[1] >= 0.30]
    print("=== 总比特钉住（|Δbpw| ≤ 0.15）且分配距离 ≥0.30 比特/参数的对：%d ===" % len(pinned))
    for ad, l1, a, b, dbpw in pinned:
        print("Δbpw=%+.3f L1_pw=%5.3f  %s  vs  %s" % (dbpw, l1, a, b))
        for cls, ba, bb in class_delta(models[a], models[b]):
            share = 100.0 * models[a]["classes"][cls]["params"] / models[a]["n_params"]
            print("    %-10s %7.3f -> %7.3f  (%5.2f%% 参数)  Δ=%+.3f" % (cls, ba, bb, share, ba - bb))
    return 0, len(pinned)


def print_scores(family):
    """`experiments.sqlite` 只读：该族在标准六基准上的分数 + 该用哪一档协议。"""
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    try:
        cur = con.execute(
            "SELECT model,_bench,_score,n_items,protocol FROM experiments "
            "WHERE model LIKE ? AND protocol!='' AND _score IS NOT NULL",
            ("%" + family + "%",))
        best = {}
        for model, bench, score, n, proto in cur:
            key = (model, bench)
            if key not in best or (n or 0) > (best[key][2] or 0):
                best[key] = (bench, proto, n, score)
    finally:
        con.close()
    models = sorted({k[0] for k in best})
    print("%-40s " % "model" + " ".join("%16s" % b for b in BENCHES))
    for m in models:
        cells = []
        for b in BENCHES:
            v = best.get((m, b))
            cells.append("%16s" % ("%.4f/%d" % (v[3], v[2]) if v else "-"))
        print("%-40s " % m + " ".join(cells))
    print()
    print("协议（同一个 model 各行一律打印，不同即不可比）：")
    for m in models:
        protos = {best[(m, b)][1] for b in BENCHES if (m, b) in best}
        print("  %-40s %s" % (m, sorted(protos)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default=None, help="只打印含该子串的族")
    ap.add_argument("--scores", default=None, help="打印该族在实验库里的分数表（只读）")
    args = ap.parse_args(argv)
    models = load_alloc()
    if args.scores:
        return print_scores(args.scores)
    if args.family:
        print_profiles(models, args.family)
    print_pairs(models, args.family)
    return 0


if __name__ == "__main__":
    sys.exit(main())
