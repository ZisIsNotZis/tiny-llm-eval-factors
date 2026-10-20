#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a03：把「方案」与「来源（厂商/上传者）」各自拆成可估系数，并打印每个系数的识别来源。

只读 `experiments.sqlite`。每基准单独一个模型，绝不跨基准池化：

    score = a + b·bpw + c·[IQ 系列] + d·[来源=local] + e·[来源=bartowski] + Σ_family 固定效应 + ε

  * `b` = 同族内每 +1 比特/权重的分数变化，本层用它当「比特预算能买多少分」的尺子；
  * `c` = **同族、同比特预算下换成 IQ 系列**的效应。只有在「同族里同时有 IQ 与 K 文件」的族里被识别，
    脚本打印识别它的族与格数；一个族都不剩时该系数直接列进「不可识别」。
  * `d` = **同族、同比特预算下换成 `local`（本仓自建 m55 配方）**的效应。它**不是**厂商效应：
    这两份文件的比特分配本来就是被有意改过的（a04 的轴），所以 `d` 读作「我们自己的分配配方」。
  * `e` = **同族、同比特预算下换一个上传者**（bartowski vs unsloth）的效应，这才是「厂商标签」本身。
    它只由 Qwen3.6-35B-A3B 一族识别，脚本会把这件事打印出来，不假装有更多证据。

族内取值恒定的哑变量与族固定效应共线，所以先判定可识别性再进模型：不可识别的列被丢掉并打印，
不靠最小范数解编一个系数出来。厂商取面板写入的模型路径（`pairs.vendor_of`），不从文件名猜。

用法：
    python3 "docs/subprojects/a03-量化方案与厂商/analysis/attrib.py"
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import pairs  # noqa: E402  —— 数据装载与家族/方案/厂商定义只有一个 home

SRC = ("unsloth", "local", "bartowski", "其他")


def rows_for(cells, vendors, bench):
    rows = []
    for m, c in cells.items():
        if bench not in c:
            continue
        cq = pairs.quant_label(m)
        vs = sorted(vendors.get(m, ["?"]))
        src = vs[0] if len(vs) == 1 else "ambiguous"
        rows.append({"model": m, "family": pairs.a01.family_of(m), "bpw": pairs.BPW_MAP[m],
                     "score": c[bench]["score"], "quant": cq,
                     "iq": 1.0 if pairs.scheme_of(cq) == "IQ" else 0.0,
                     "src": src if src in SRC else "其他"})
    return rows


def varies_within_family(rows, key):
    """该列在至少一个族里取到两个值 ⇒ 与族固定效应不共线（可识别）。"""
    by = {}
    for r in rows:
        by.setdefault(r["family"], set()).add(r[key])
    return {f: sorted(v) for f, v in sorted(by.items()) if len(v) > 1}


def build(rows):
    """(列名, 设计矩阵, 观测, 不可识别说明)。"""
    fams = sorted({r["family"] for r in rows})
    cand = [("IQ", lambda r: r["iq"]),
            ("local", lambda r: 1.0 if r["src"] == "local" else 0.0),
            ("bartowski", lambda r: 1.0 if r["src"] == "bartowski" else 0.0),
            ("其他来源", lambda r: 1.0 if r["src"] == "其他" else 0.0)]
    cols = ["bpw"]
    keep = []
    dropped = []
    for name, fn in cand:
        vals = {r["model"]: fn(r) for r in rows}
        tmp = [dict(r, _v=vals[r["model"]]) for r in rows]
        who = varies_within_family(tmp, "_v")
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
    first = None
    for bench in pairs.BENCH_ORDER:
        rows = rows_for(cells, vendors, bench)
        if len(rows) < 8:
            print(f"{pairs.SHORT[bench]:<7} 只有 {len(rows)} 格，不估")
            continue
        cols, X, y, keep, dropped = build(rows)
        b, se, dof = fit(X, y, cols)
        first = first or (rows, keep, dropped)
        get = lambda k: cell(b[k], se[k]) if k in b else "不可识别".rjust(21)  # noqa: E731
        print(f"{pairs.SHORT[bench]:<7} {get('bpw'):>21} {get('IQ'):>21} {get('local'):>21} "
              f"{get('bartowski'):>21}  {len(rows)}")
    if first:
        rows, keep, dropped = first
        print("\n每个系数的识别来源（哪一族同时含两个取值）：")
        for name, _fn, who in keep:
            print(f"  {name}: {who}")
        for name, why in dropped:
            print(f"  {name}: 不可识别——{why}")
    amb = sorted({m for m in cells if len(vendors.get(m, ["?"])) > 1})
    for m in amb:
        print(f"  旁注：{m} 的面板路径不一致 {sorted(vendors[m])}，按 ambiguous 处理（不进任何来源系数）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
