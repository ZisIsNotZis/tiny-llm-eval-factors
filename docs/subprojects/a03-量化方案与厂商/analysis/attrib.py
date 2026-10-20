#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a03：把「方案」与「来源（厂商/上传者）」各自拆成可估系数，并打印识别来源与探测下限。

只读 `experiments.sqlite` + 入库夹具。每基准单独一个模型，绝不跨基准池化：

    score = a + b·bpw + c·[IQ 系列] + d·[来源=local] + e·[来源=bartowski] + Σ_family 固定效应 + ε

  * `b` = 同族内每 +1 比特/权重的分数变化，本层用它当「比特预算能买多少分」的尺子；
  * `c` = **同族、同比特预算下换成 IQ 系列**的效应。只在「同族里同时有 IQ 与 K 文件」的族里被识别；
  * `d` = **同族、同比特预算下换成 `local`（本仓自建 m55 配方）**——它**不是**厂商效应：
    这两份文件的比特分配本来就被有意改过（a04 的轴），所以 `d` 读作「我们自己的分配配方」；
  * `e` = **同族、同比特预算下换一个上传者**（bartowski vs unsloth）的效应，这才是「厂商标签」本身。
    它**只由 Qwen3.6-35B-A3B 一族识别**，而且该族的三个点里两个是 unsloth、一个是 bartowski，
    所以 `e` 是拿汇总斜率外推出的残差，**符号可以与它唯一来源的那一对相反**（脚本会逐基准判并打印
    翻转计数）。因此本层不用 `e` 下厂商结论，只用逐对区间（`pairs.py`）下。

识别规则先于模型判定：族内取值恒定的哑变量与族固定效应共线，一律判「不可识别」并打印，不靠
最小范数解编一个系数出来。来源只取入库夹具（`analysis/fixtures/vendor_map.json`，每个文件带
run_tag→路径证据），不从文件名猜；来源标为 `ambiguous`/`unknown` 的行**不进回归**并打印。
区间是正态近似（1.96·se），逐题二项项没有进这个模型——同一格的逐题结果没有落库，所以区间只含
运行内（逐文件之间）的残差。

用法：
    python3 "docs/subprojects/a03-量化方案与厂商/analysis/attrib.py"
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import pairs  # noqa: E402  —— 数据装载与家族/方案/来源定义只有一个 home

# 真实来源类别。`ambiguous`/`unknown`/`?` 是不可归因（面板没写出可用路径），这些行
# **不进回归**并打印；其余真实但非 unsloth/local/bartowski 的来源归作「其他来源」。
SRC = ("unsloth", "local", "bartowski")
UNATTRIBUTABLE = ("ambiguous", "unknown", "?")


def rows_for(cells, vendors, bench):
    """(参与回归的行, 被排除的[(文件, 来源)])——排除要打印而不是静默。"""
    rows, dropped = [], []
    for m, c in cells.items():
        if bench not in c:
            continue
        cq = pairs.quant_label(m)
        vs = sorted(vendors.get(m, ["?"]))
        src = vs[0] if len(vs) == 1 else "ambiguous"
        if src in UNATTRIBUTABLE:
            dropped.append((m, src))
            continue
        rows.append({"model": m, "family": pairs.a01.family_of(m), "bpw": pairs.BPW_MAP[m],
                     "score": c[bench]["score"], "quant": cq,
                     "iq": 1.0 if pairs.scheme_of(cq) == "IQ" else 0.0,
                     "src": src if src in SRC else "其他"})
    return rows, dropped


def varies_within_family(rows, key):
    """该列在至少一个族里取到两个值 ⇒ 与族固定效应不共线（可识别）。"""
    by = {}
    for r in rows:
        by.setdefault(r["family"], set()).add(r[key])
    return {f: sorted(v, key=str) for f, v in sorted(by.items()) if len(v) > 1}


def build(rows):
    """(列名, 设计矩阵, 观测, 保留的哑变量[(名, 取函数, 识别族)], 不可识别[(名, 原因)])。"""
    fams = sorted({r["family"] for r in rows})
    cand = [("IQ", lambda r: r["iq"]),
            ("local", lambda r: 1.0 if r["src"] == "local" else 0.0),
            ("bartowski", lambda r: 1.0 if r["src"] == "bartowski" else 0.0),
            ("其他来源", lambda r: 1.0 if r["src"] == "其他" else 0.0)]
    cols = ["bpw"]
    keep, dropped = [], []
    for name, fn in cand:
        probe = [dict(r, _v=fn(r)) for r in rows]
        who = varies_within_family(probe, "_v")
        if not who:
            dropped.append((name, "没有任何族同时含两个取值"))
            continue
        keep.append((name, fn, who))
        cols.append(name)
    cols += [f"fam:{f}" for f in fams[1:]]
    X, y = [], []
    for r in rows:
        x = [r["bpw"]] + [fn(r) for _n, fn, _w in keep]
        x += [1.0 if r["family"] == f else 0.0 for f in fams[1:]]
        X.append(x)
        y.append(r["score"])
    return cols, np.array(X, float), np.array(y, float), keep, dropped


def fit(X, y, cols):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = len(y) - np.linalg.matrix_rank(X)
    s2 = float(resid @ resid) / max(dof, 1)
    try:
        cov = s2 * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:        # 共线：不编区间
        se = np.full(len(beta), float("nan"))
    return dict(zip(cols, beta)), dict(zip(cols, se)), dof


def cell(est, se):
    if se != se:
        return f"{est:+.4f} ±    n/a    "
    return f"{est:+.4f} [{est - 1.96 * se:+.4f},{est + 1.96 * se:+.4f}]"


def main():
    cells, dups = pairs.load()
    vendors = pairs.vendor_of()
    print(f"格 = {len(cells)} 个文件 × 各自基准；族 = {len({pairs.a01.family_of(m) for m in cells})}；"
          f"同格多行取 n_items 最大者 {len(dups)} 处")
    print("区间 = 正态近似 1.96·se，只含运行内（逐文件之间）的残差；同一格的逐题结果没有落库，跨 run 项不在内\n")
    print(f"{'基准':<7} {'斜率 b':>21} {'IQ 效应':>21} {'local 配方':>21} {'bartowski':>21}  n")
    ident = {}          # 系数名 → {基准: [识别族]}
    halfw = {}          # 系数名 → [(基准, 1.96·se)]
    betas = {}          # 系数名 → {基准: 点估计}
    dropped_any = {}
    excluded = set()
    for bench in pairs.BENCH_ORDER:
        rows, dropped = rows_for(cells, vendors, bench)
        excluded |= {m for m, _s in dropped}
        if len(rows) < 8:
            print(f"{pairs.SHORT[bench]:<7} 只有 {len(rows)} 格，不估")
            continue
        cols, X, y, keep, dropped_cols = build(rows)
        b, se, _dof = fit(X, y, cols)
        for name, _fn, who in keep:
            ident.setdefault(name, {})[bench] = sorted(who)
        for name, why in dropped_cols:
            dropped_any.setdefault(name, why)
        ident.setdefault("bpw", {})[bench] = ["<同族内位宽变化>"]
        for k in ("bpw", "IQ", "local", "bartowski"):
            if k in b and se[k] == se[k]:
                halfw.setdefault(k, []).append((pairs.SHORT[bench], 1.96 * se[k]))
                betas.setdefault(k, {})[bench] = b[k]
        get = lambda k: cell(b[k], se[k]) if k in b else "不可识别".rjust(21)  # noqa: E731
        print(f"{pairs.SHORT[bench]:<7} {get('bpw'):>21} {get('IQ'):>21} {get('local'):>21} "
              f"{get('bartowski'):>21}  {len(rows)}")

    by_fam_bpw = {}
    for m in cells:
        by_fam_bpw.setdefault(pairs.a01.family_of(m), set()).add(pairs.BPW_MAP[m])
    n_fam_within = sum(1 for v in by_fam_bpw.values() if len(v) > 1)
    print("\n识别来源与探测下限（跨 9 个基准汇总；「不可分辨」= 该量级以内的效应本设计探测不到）：")
    print("  口径：半宽 = 该列自己的 95% 半宽（1.96·se）。引**一个**数时引「逐基准最大」这一列，")
    print("        它是探测下限的最小值（能排除的最小效应量级），**不是** 9 列同时成立的联合区间；")
    print("        论文/报告里的 0.27 / 0.37 / 0.49 就是这一列，与本表同源。")
    print(f"  {'系数':<10} {'识别基准数':>6} {'识别的族（并集）':<42} {'逐基准半宽':<15} "
          f"{'逐基准最大':>8} 点估计方向")
    for k in ("bpw", "IQ", "local", "bartowski"):
        if k not in halfw:
            print(f"  {k:<10} {0:>6} {'—':<42} {'—':<15} {'—':>8} 不可识别")
            continue
        fams = sorted({fam for who in ident.get(k, {}).values() for fam in who})
        if k == "bpw":
            fams = [f"{n_fam_within} 个族的族内位宽差"]
        hw = [h for _b, h in halfw[k]]
        pts = [v for v in betas.get(k, {}).values()]
        sign = "全正" if all(p > 0 for p in pts) else ("全负" if all(p < 0 for p in pts) else "混合")
        print(f"  {k:<10} {len(ident.get(k, {})):>6} {', '.join(fams):<42} "
              f"{min(hw):.3f}–{max(hw):.3f}{'':<4} {max(hw):>8.3f} {sign}")
    env = {k: max(h for _b, h in v) for k, v in halfw.items()}
    if env:
        print("  逐基准最大半宽（探测下限，文档与报告只引这一组）："
              + "，".join(f"{k} {env[k]:.3f}" for k in ("IQ", "local", "bartowski") if k in env))
    for name, why in sorted(dropped_any.items()):
        print(f"  不可识别：{name}——{why}")
    if excluded:
        print(f"  不进回归（来源不可归因）：{sorted(excluded)}")

    # bartowski 系数 vs 它唯一来源的那一对：逐基准比符号，翻转计数必须打印出来。
    fam = "Qwen3.6-35B-A3B"
    pl = [p for p in pairs.enumerate_pairs(cells, vendors, 0.45)
          if p["family"] == fam and p["kind"] in ("vendor", "vendor+scheme")]
    if pl and "bartowski" in betas:
        p = pl[0]
        flip, same = [], []
        for bench in pairs.BENCH_ORDER:
            if bench not in p["cells"] or bench not in betas["bartowski"]:
                continue
            coef, pair_d = betas["bartowski"][bench], p["cells"][bench]["delta"]
            (flip if coef * pair_d < 0 else same).append(pairs.SHORT[bench])
        print(f"\n  外推假象检查（bartowski 系数 vs {fam} 的逐对差 {p['quant_low']}→{p['quant_high']}）：")
        print(f"    符号相反 {len(flip)}/{len(flip) + len(same)} 列：{flip}")
        print(f"    符号相同 {len(same)} 列：{same}")
        print("    ⇒ 该系数由单对识别、并拿汇总斜率外推，符号与来源对相反时**不得**当厂商效应读；")
        print("      厂商结论只用 `pairs.py` 的逐对区间（`vendor-qwen36`）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
