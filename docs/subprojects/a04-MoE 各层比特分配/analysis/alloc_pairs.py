#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a04 的受控分配对照装置：只剩「总比特钉住、比特挪了位置」的那些配对才进来。

用法（仓库根执行）：

    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py"                 # 策略分类
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --pairs         # 全部同参数配对
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --pinned        # 只留钉住且大幅挪位的
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/alloc_pairs.py" --pair A.gguf B.gguf

口径全部借上游的一处定义，不复制：

  * 分数格、规范协议、`n_items` 取最大行、协议一致性检查、Newcombe method 10 区间 —— `a03` 的
    `analysis/pairs.py`（它又借 `a01` 的 `curves.newcombe_diff`）；
  * 分配轮廓 —— a03 的入库夹具 `analysis/fixtures/alloc_map.json`（只读）；
  * 本层只新增两件事：参数加权分配距离 `L1_pw` 与策略分类，定义见
    `docs/subprojects/a04-MoE 各层比特分配/AGENTS.md` 第 1 条。

`L1_pw` 与 `Δbpw` 必须一起读：`L1_pw ≈ |Δbpw|` 的配对只是总比特变了，
`L1_pw ≫ |Δbpw|` 才是总比特钉住、比特挪了位置。只有后者是分配对照。
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE
for _ in range(6):
    REPO = REPO.parent
    if (REPO / "experiments.sqlite").is_file():
        break
else:
    sys.exit("找不到仓库根（experiments.sqlite）")

A03_ANALYSIS = REPO / "docs" / "subprojects" / "a03-量化方案与厂商" / "analysis"
sys.path.insert(0, str(A03_ANALYSIS))

import pairs as a03  # noqa: E402  —— 区间、协议、取格口径由 a03 拥有，本层只借用

ALLOC = json.loads((A03_ANALYSIS / "fixtures" / "alloc_map.json").read_text(encoding="utf-8"))["models"]

# 本层自建的臂（语料里没有的配置）在 `fixtures/alloc_a04.json`，由 `build_fixture.py` 从 gguf
# 头重建。把它合并进轮廓表，并把它的 bpw 注进 a03 的 BPW_MAP（否则 a03.load 会把未知文件
# 跳过）：本层不手改 `.wrapup/bpw_map.json` 那份共享数据，自建文件的位宽只从自己的夹具读。
OWN_FIXTURE = HERE.parent / "fixtures" / "alloc_a04.json"
if OWN_FIXTURE.exists():
    _own = json.loads(OWN_FIXTURE.read_text(encoding="utf-8"))["models"]
    for _name, _row in _own.items():
        _row["source_path"] = "/home/z/hf/" + _name
        ALLOC[_name] = _row
        a03.BPW_MAP[_name] = _row["bpw_file"]

# 方向判定只看「层上真正驻留的桶」：attn / 稠密 FFN / 共享专家。
# embed 被 K-quant 的模板钉在 4.5–8.5（同一族内 3.438–8.500 都出现过），是另一套机制，
# 单独打印而不参与方向；norm / router 按 f32 固定；`other` 是混杂桶，同样不参与。
LAYER_BUCKETS = ("attn", "ffn-dense", "ffn-shexp")
EXPERT_BUCKET = "ffn-expert"
UNIFORM_BAND = 0.5          # 比特/参数；|b_exp − b_layer| 不超过它就是「均匀」


def is_moe(name):
    return EXPERT_BUCKET in ALLOC[name]["classes"]


def family_key(name):
    """同一套 base 权重的机械判据：参数数相同。名字不参与。"""
    return ALLOC[name]["n_params"]


def moe_groups(family=None):
    """{族名: [文件...]}，按参数数分组；族名取组内 a01 family_of 最短的那个。"""
    groups = {}
    for n in ALLOC:
        if is_moe(n) and (family is None or family in n):
            groups.setdefault(family_key(n), []).append(n)
    out = {}
    for members in groups.values():
        label = sorted({a01_family(n) for n in members}, key=len)[0]
        out[label] = members
    return out


def l1_pw(a, b):
    """参数加权 L1 分配距离（比特/参数）。两侧必须同参数数，否则不是同一套 base 权重。"""
    if ALLOC[a]["n_params"] != ALLOC[b]["n_params"]:
        raise ValueError("不同参数数，不是同一套 base 权重：%s vs %s" % (a, b))
    total = 0.0
    for cls in ALLOC[a]["classes"]:
        if cls in ALLOC[b]["classes"]:
            pa = ALLOC[a]["classes"][cls]["params"]
            total += abs(ALLOC[a]["classes"][cls]["bits"] - ALLOC[b]["classes"][cls]["bits"]) * pa
    return total / ALLOC[a]["n_params"]


def b_expert(name):
    return ALLOC[name]["classes"][EXPERT_BUCKET]["bits"]


def b_layer(name):
    """层上桶（attn / 稠密 FFN / 共享专家）的参数加权平均比特数。缺桶就按在场桶加权。"""
    classes = ALLOC[name]["classes"]
    num = sum(classes[c]["bits"] * classes[c]["params"] for c in LAYER_BUCKETS if c in classes)
    den = sum(classes[c]["params"] for c in LAYER_BUCKETS if c in classes)
    return num / den if den else float("nan")


def b_embed(name):
    c = ALLOC[name]["classes"].get("embed")
    return c["bits"] if c else float("nan")


def strategy(name):
    """策略 = 张量类别上的比特向量，由机械规则判（`AGENTS.md` 第 1 条）。"""
    if not is_moe(name):
        return "非 MoE"
    gap = b_layer(name) - b_expert(name)
    if abs(gap) <= UNIFORM_BAND:
        return "均匀"
    return "非专家优先" if gap > 0 else "专家优先"


def print_bounds(family=None):
    """钉住总比特时，专家桶最多能挪多少比特 —— 这是架构决定的上界，不是测量。

    钉住：Σ_c Δb_c · p_c = 0。专家桶占 s_e，其余桶占 1−s_e，于是
        |Δb_exp| ≤ (1−s_e)/s_e · max|Δb_其余|，
    而 `max|Δb_其余|` 取语料里该族观测到的层桶跨度（保守取最大跨度）。
    专家占比 91.5% 时，这个上界不到 0.3 比特/参数：**专家层拿多少比特几乎就是总比特**。
    """
    fams = moe_groups(family)
    print("%-18s %8s %8s %9s %11s %12s" %
          ("族", "专家占比", "层桶占比", "层桶跨度", "专家Δ上界", "专家Δ观测"))
    for fam, files in sorted(fams.items()):
        if len(files) < 2:
            continue
        ref = ALLOC[files[0]]
        s_exp = ref["classes"][EXPERT_BUCKET]["params"] / ref["n_params"]
        s_layer = sum(ref["classes"][c]["params"] for c in LAYER_BUCKETS if c in ref["classes"]) / ref["n_params"]
        layers = [b_layer(n) for n in files]
        swing = max(layers) - min(layers)
        exps = [b_expert(n) for n in files]
        bound = (1 - s_exp) / s_exp * swing
        print("%-18s %7.2f%% %7.2f%% %9.2f %11.3f %12.3f" %
              (fam, 100 * s_exp, 100 * s_layer, swing, bound, max(exps) - min(exps)))
    print()
    print("「专家Δ上界」= 在总比特钉住的约束下、靠其余桶反向摆动能给专家桶腾出的最大跨度（比特/参数）。")
    print("「专家Δ观测」= 该族文件之间专家桶实际的最大跨度。观测远超上界的那些文件对，**不可能**被钉住。")


def print_summary(family=None):
    """钉住配对的一行总账：多少对、多少格有区间、多少格不含 0、最大半宽。

    "钉住" = |Δbpw| ≤ 0.05（钉住档）；此外分开报 ≤0.15 档。半宽 = (上限−下限)/2。
    只统计 MoE 对与其中两侧都是同一套 base 权重的对。
    """
    cells, _ = a03.load()
    rows = [r for r in same_base_pairs(family) if is_moe(r[0]) and is_moe(r[1])]
    for bound in (0.05, 0.15, 0.45):
        sel = [r for r in rows if abs(r[2]) <= bound]
        n_int = n_excl = 0
        half = 0.0
        pairs_desc = []
        for a, b, dbpw, l1 in sel:
            low, high = (a, b) if dbpw >= 0 else (b, a)
            rec = a03.pair_record(low, high, cells, {}, bound)
            got = 0
            for bench in a03.BENCH_ORDER:
                if bench not in rec["cells"]:
                    continue
                d, ci = a03.interval(rec, bench)
                if ci is None:
                    continue
                got += 1
                n_int += 1
                half = max(half, (ci[1] - ci[0]) / 2)
                if ci[0] * ci[1] > 0:
                    n_excl += 1
            pairs_desc.append("%s vs %s (Δ%+.3f L1 %.3f, %d 格有区间)" % (a, b, dbpw, l1, got))
        print("=== 钉住档 |Δbpw| ≤ %.2f：MoE 对 %d 对，有区间的格 %d 个，区间不含 0 的 %d 个，最大半宽 %.3f ==="
              % (bound, len(sel), n_int, n_excl, half))
        for d in pairs_desc:
            print("    " + d)
    return 0


def expert_span_bound(files):
    """一族在钉住约束下专家桶能吃到的最大跨度（比特/参数）= (1−s_exp)/s_exp × 层桶跨度。"""
    ref = ALLOC[files[0]]
    s_exp = ref["classes"][EXPERT_BUCKET]["params"] / ref["n_params"]
    layers = [b_layer(n) for n in files]
    return (1 - s_exp) / s_exp * (max(layers) - min(layers))


def print_infeasible(family=None):
    """逐对判「能不能被钉住」：专家桶跨度超过族上界的配对，不可能靠其余桶反向摆动抵平。

    这是 `RESULT.md::expert-bound` 的逐对版本：不需要任何新测量，只读两份入库夹具，
    所以干净 clone 里同样成立（不存第二份夹具，避免同一个事实两个家）。
    """
    fams = moe_groups(family)
    print("%-40s %-40s %7s %7s %9s %8s" %
          ("A", "B", "Δbpw", "L1_pw", "专家Δ", "可钉住"))
    n_inf = n_pin = 0
    for fam, files in sorted(fams.items()):
        if len(files) < 2:
            continue
        bound = expert_span_bound(files)
        for a, b in itertools.combinations(sorted(files, key=lambda n: ALLOC[n]["bpw_file"]), 2):
            dbpw = ALLOC[b]["bpw_file"] - ALLOC[a]["bpw_file"]
            span = abs(b_expert(a) - b_expert(b))
            ok = span <= bound
            n_pin += ok
            n_inf += not ok
            print("%-40s %-40s %+7.3f %7.3f %9.3f %8s" %
                  (a.replace("LFM2.5-8B-A1B-", ""), b.replace("LFM2.5-8B-A1B-", ""),
                   dbpw, l1_pw(a, b), span, "是" if ok else "不可能"))
        print("    （%s 的专家桶上界 %.3f 比特/参数）" % (fam, bound))
    print()
    print("可钉住 %d 对、不可能钉住 %d 对。不可能的那些配对里，专家桶的跨度已经超出"
          "其余桶反向摆动能在总比特上抵平的幅度，所以它们必然同时改了总比特。" % (n_pin, n_inf))
    return 0


def b_layer_alt(name, extra):
    """替代口径的层桶均值：把 `extra` 里的桶也算进「非专家」。只用来说明口径选择有后果。"""
    classes = ALLOC[name]["classes"]
    keys = [c for c in tuple(LAYER_BUCKETS) + tuple(extra) if c in classes]
    den = sum(classes[c]["params"] for c in keys)
    return sum(classes[c]["bits"] * classes[c]["params"] for c in keys) / den if den else float("nan")


def strategy_alt(name, extra):
    gap = b_layer_alt(name, extra) - b_expert(name)
    if abs(gap) <= UNIFORM_BAND:
        return "均匀"
    return "非专家优先" if gap > 0 else "专家优先"


def print_definitions():
    """桶定义的两个候选各自的策略分布。这是「口径选择有后果」的机械证据。"""
    files = [n for n in ALLOC if is_moe(n)]
    for label, extra in (("A 层桶=attn/ffn-dense/ffn-shexp（本层采用）", ()),
                         ("B 层桶=上述+embed（备选，不用）", ("embed",))):
        counts = {}
        for n in files:
            k = strategy(n) if not extra else strategy_alt(n, extra)
            counts[k] = counts.get(k, 0) + 1
        print("%-44s %s" % (label, dict(sorted(counts.items()))))
        if extra:
            for n in sorted(files):
                if strategy(n) != strategy_alt(n, extra):
                    print("    变化：%-40s %s → %s（专家 %.3f / 层桶 %.3f → %.3f）"
                          % (n, strategy(n), strategy_alt(n, extra), b_expert(n),
                             b_layer(n), b_layer_alt(n, extra)))
    print()
    print("定义 A 保住了三个策略（%d 个 MoE 文件）；定义 B 让「专家优先」归零，"
          "全库只剩两个策略，`strategy-counts` 断言随之失效——所以桶定义只能有一份，就是 A。"
          % len(files))


def print_strategies():
    files = [n for n in ALLOC if is_moe(n)]
    files.sort(key=lambda n: (strategy(n), b_expert(n)))
    print("%-8s %-14s %-40s %6s %6s %6s %7s %7s" %
          ("策略", "族", "file", "bpw", "专家", "层桶", "embed", "专家占比"))
    for n in files:
        m = ALLOC[n]
        share = 100.0 * m["classes"][EXPERT_BUCKET]["params"] / m["n_params"]
        print("%-8s %-14s %-40s %6.3f %6.3f %6.3f %7.3f %6.2f%%" %
              (strategy(n), n.split("-UD-")[0].split("-m55-")[0].split("-a04-")[0].replace("Qwen_", ""), n,
               m["bpw_file"], b_expert(n), b_layer(n), b_embed(n), share))
    counts = {}
    for n in files:
        counts[strategy(n)] = counts.get(strategy(n), 0) + 1
    print()
    print("策略计数（MoE 文件 %d 个）：%s" % (len(files), counts))


def same_base_pairs(family=None):
    """同一套 base 权重（同参数数）的全部文件对。"""
    out = []
    for a, b in itertools.combinations(sorted(ALLOC), 2):
        if family and (family not in a or family not in b):
            continue
        if ALLOC[a]["n_params"] != ALLOC[b]["n_params"]:
            continue
        out.append((a, b, ALLOC[b]["bpw_file"] - ALLOC[a]["bpw_file"], l1_pw(a, b)))
    out.sort(key=lambda r: (abs(r[2]), -r[3]))
    return out


def print_pairs(family=None, pinned_only=False):
    cells, dups = a03.load()
    sl = a03.slopes(cells)
    if dups:
        print("（a03.load 报告 %d 处同一格有多行，已按 n_items 最大者取一行；清单用 pairs.py --slopes 看）" % len(dups))
    rows = same_base_pairs(family)
    if pinned_only:
        rows = [r for r in rows if abs(r[2]) <= 0.15 and r[3] >= 0.30]
    for a, b, dbpw, l1 in rows:
        low, high = (a, b) if dbpw >= 0 else (b, a)
        moe = "MoE " if is_moe(a) and is_moe(b) else ("MoE-单侧 " if is_moe(a) or is_moe(b) else "稠密")
        print("=" * 100)
        print("%s Δbpw=%+.3f L1_pw=%.3f  %s  策略 %s → %s" %
                (moe, dbpw, l1, a01_family(a), strategy(a), strategy(b)))
        print("  A %-44s bpw %.3f 专家 %.3f 层桶 %.3f embed %.3f" %
              (a, ALLOC[a]["bpw_file"], b_expert(a) if is_moe(a) else float("nan"),
               b_layer(a), b_embed(a)))
        print("  B %-44s bpw %.3f 专家 %.3f 层桶 %.3f embed %.3f" %
              (b, ALLOC[b]["bpw_file"], b_expert(b) if is_moe(b) else float("nan"),
               b_layer(b), b_embed(b)))
        rec = a03.pair_record(low, high, cells, {}, 0.15)
        for bench in a03.BENCH_ORDER:
            if bench not in rec["cells"]:
                continue
            d, ci = a03.interval(rec, bench)
            s = sl.get(bench, (float("nan"),) * 3)[0]
            expect = s * rec["dbpw"]
            ci_s = "        —        " if ci is None else "[%+.4f,%+.4f]" % ci
            if ci is None:
                sig = "（概率质量均值，不套区间）"
            elif ci[0] * ci[1] > 0:
                sig = "区间不含0"
            else:
                sig = "跨0 → 不可分辨"
            print("    %-7s Δ=%+.4f %s n=%s 比特预算=%+.4f %s" %
                  (a03.SHORT[bench], d, ci_s, rec["cells"][bench]["low"]["n_items"], expect, sig))
        for bench, bad, vals in rec["incomparable"]:
            print("    %-7s 不可比：%s %s" % (a03.SHORT[bench], bad, vals))


def a01_family(name):
    import curves as a01
    return a01.family_of(name)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", action="store_true", help="打印全部同参数配对的逐基准差与区间")
    ap.add_argument("--pinned", action="store_true", help="只打印 |Δbpw|≤0.15 且 L1_pw≥0.30 的配对")
    ap.add_argument("--bounds", action="store_true", help="打印钉住总比特时专家桶能挪多少的上界")
    ap.add_argument("--summary", action="store_true", help="钉住 MoE 配对的总账（格数 / 不含 0 数 / 最大半宽）")
    ap.add_argument("--infeasible", action="store_true", help="逐对判能不能被钉住（只读入库夹具）")
    ap.add_argument("--definitions", action="store_true", help="两种桶定义下的策略分布（口径选择的后果）")
    ap.add_argument("--pair", nargs=2, metavar=("A", "B"), default=None)
    ap.add_argument("--family", default=None)
    args = ap.parse_args(argv)
    if args.pair:
        a, b = args.pair
        dbpw = ALLOC[b]["bpw_file"] - ALLOC[a]["bpw_file"]
        print("Δbpw=%+.3f L1_pw=%.3f 策略 %s → %s" % (dbpw, l1_pw(a, b), strategy(a), strategy(b)))
        return 0
    if args.pairs or args.pinned:
        print_pairs(args.family, pinned_only=args.pinned)
        return 0
    if args.bounds:
        print_bounds(args.family)
        return 0
    if args.infeasible:
        return print_infeasible(args.family)
    if args.definitions:
        print_definitions()
        return 0
    if args.summary:
        return print_summary(args.family)
    print_strategies()
    return 0


if __name__ == "__main__":
    sys.exit(main())
