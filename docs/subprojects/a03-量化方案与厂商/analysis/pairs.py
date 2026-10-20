#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a03 量化方案与厂商：同字节配对装置（匹配字节 → 逐基准差 + 区间 + 差因分解）。

X = 量化方案（IQ 系列 vs K 系列）或文件的来源（厂商 / 上传者）；Y = 基准分数。
只读 `experiments.sqlite`，不改库、不改 `report.html`。

口径（`docs/subprojects/a03-量化方案与厂商/AGENTS.md`）：

  * **有效位宽**取 `.wrapup/bpw_map.json`（`8 × 文件字节数 ÷ gguf 精确参数量`），不取库里
    四舍五入的 `__size`，也不取厂商标称档位名。
  * **一族 = 同一套 base 权重只换量化文件**（`mktables.family_of`，保留尺寸）。
    跨族同字节不是受控比较（那是规模轴的活）。
  * **一格 = (模型文件, 基准) 在该基准的规范协议下的那一行**；同一格有多行时取 `n_items` 最大者
    并打印出来，绝不静默挑一行。
  * **区间 = 两比例差的 Newcombe 混合得分区间（method 10）**，直接复用 a01 的
    `curves.newcombe_diff` / `curves.wilson`，让两轴的区间定义只有一个 home；
    TruthfulQA 的 `acc` 是概率质量均值不是命中数（`i01::res26`），所以那一列只报差值不套二项区间。
  * **配对前先验协议**：两侧的 `protocol / n_items / ctx_size / parallel_slots / temp / reasoning`
    必须逐列相等，否则该格判「不可比」并打印，不进任何汇总。
  * **不池化**：语言、协议、基准之间绝不平均。跨族汇总只用「同号计数 + 逐族区间」，
    并打印参与汇总的族数。

差因分解：先测本库「同族内每 +1 比特/权重的分数变化」（族固定效应的 OLS 斜率），
把配对差拆成 `斜率 × Δbpw`（比特预算能解释的部分）与残差（方案/厂商效应）。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE
for _ in range(6):                       # docs/subprojects/<id>/analysis/pairs.py → 仓库根
    REPO = REPO.parent
    if (REPO / "experiments.sqlite").is_file():
        break
else:
    sys.exit("找不到仓库根（experiments.sqlite）")

DB = REPO / "experiments.sqlite"
BPW_MAP = json.loads((REPO / ".wrapup" / "bpw_map.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(REPO / ".wrapup"))
sys.path.insert(0, str(REPO / "docs" / "subprojects" / "a01-量化位宽" / "analysis"))

import curves as a01  # noqa: E402  —— 区间与家族定义由 a01 拥有，本层只借用不复制

# 规范协议逐基准写死，与 make_report.py::BENCH / a01::curves.BENCH 同一份事实。
BENCH = {
    "humaneval": "evalplus-0.3.1-openai-chat-greedy-base",
    "humaneval-plus": "evalplus-0.3.1-openai-chat-greedy-plus",
    "mbpp": "evalplus-0.3.1-openai-chat-greedy-base",
    "mbpp-plus": "evalplus-0.3.1-openai-chat-greedy-plus",
    "mmlu": "lmeval-0.4.13-gguf-shim-reasoning-off",
    "arc_challenge": "lmeval-0.4.13-gguf-shim-reasoning-off",
    "truthfulqa_mc2": "lmeval-0.4.13-gguf-shim-reasoning-off",
    "gsm8k": "lmeval-0.4.13-chat-reasoning-off",
    "ifeval": "lmeval-0.4.13-chat-reasoning-off",
}
BENCH_ORDER = list(BENCH)
SHORT = {"humaneval": "HE", "humaneval-plus": "HE+", "mbpp": "MBPP", "mbpp-plus": "MBPP+",
         "mmlu": "MMLU", "arc_challenge": "ARC-c", "truthfulqa_mc2": "TQA",
         "gsm8k": "GSM8K", "ifeval": "IFEval"}
# 非伯努利列：只报差值，不套两比例区间（`i01::res26`）。
NON_COUNT = {"truthfulqa_mc2"}

# 匹配字节的三档判据（比特/权重）。0.45 是报告第三节/`mktables.MATCH_BPW` 的现行口径，
# 另外两档是本层收紧后的判据：0.15 约等于本库每比特效应的 1.5 倍噪声量级，
# 0.05 近似「字节几乎相同」。
BOUNDS = (0.45, 0.15, 0.05)


def con():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def cell(cc, model, bench):
    """(row dict 或 None, 被丢掉的重复行)。取 n_items 最大的一行，绝不静默合并。"""
    rs = cc.execute(
        "SELECT _score, n_items, run_tag, ctx_size, parallel_slots, temp, reasoning"
        " FROM experiments WHERE model=? AND _bench=? AND protocol=? AND _score IS NOT NULL",
        (model, bench, BENCH[bench])).fetchall()
    if not rs:
        return None, []
    rs.sort(key=lambda r: (-(r[1] or 0), r[2] or ""))
    best = rs[0]
    return {"score": best[0], "n_items": best[1], "run_tag": best[2], "ctx_size": best[3],
            "parallel_slots": best[4], "temp": best[5], "reasoning": best[6],
            "protocol": BENCH[bench]}, rs[1:]


def quant_label(model):
    """文件名的量化档位（`UD-IQ3_XXS` 这类），只当年标签用，不当 X 值。"""
    import mktables
    base = model if model.endswith(".gguf") else model + ".gguf"
    _, q = mktables.split_quant(base)
    return q or "—"


def scheme_of(quant):
    """方案大类 = 文件名里的量化族：IQ（imatrix 信息论量化）/ K（传统 K 系列）/ TQ（三元）/ 其他。"""
    q = quant.upper()
    if q.startswith("UD-"):
        q = q[3:]
    if q.startswith("IQ"):
        return "IQ"
    if q.startswith("TQ"):
        return "TQ"
    if q.startswith("Q"):
        return "K"
    return "其他"


def vendor_in_path(p):
    """模型路径里的厂商/上传者目录。两种缓存写法都认，认不出就记 unknown。

    `/home/z/hf/mscache/<vendor>/<repo>/<file>.gguf` → `<vendor>`
    `/home/z/hf/models--<vendor>--<repo>/blobs/<sha>` → `<vendor>`（HF 缓存把档位名换成 blob 哈希，
    所以这种路径只能靠 run_tag 与库内行对上，不能靠文件名）
    `/home/z/hf/<file>.gguf`（本仓自己压的配方）→ `local`
    """
    parts = p.split("/")
    if "mscache" in parts:
        i = parts.index("mscache")
        if len(parts) > i + 2:
            return parts[i + 1]
        return "unknown"
    for seg in parts:
        if seg.startswith("models--") and seg.count("--") >= 2:
            return seg.split("--")[1]
    if p.startswith("/home/z/hf/"):
        return "local"
    return "unknown"


def vendor_of():
    """{模型文件: {厂商, ...}}，取自面板写入的模型绝对路径，不从文件名猜。

    证据 = `.wrapup/mres/<run_tag>/{evalplus,lmeval_panel,...}.json` 的 `model` 字段。
    面板的 `run_tag` 与库内 `experiments.run_tag` 是同一个键，所以先用 run_tag 对上库里的
    模型文件名，再挂上路径里的厂商；这样 HF 缓存那种 `blobs/<sha>` 路径也能归属。
    同一个文件被多个面板测过时取并集，多于一个就说明有面板用了别的来源。
    """
    cc = con()
    tag_models = {}
    for tag, model in cc.execute("SELECT DISTINCT run_tag, model FROM experiments WHERE run_tag IS NOT NULL"):
        tag_models.setdefault(tag, set()).add(model)
    out = {}
    for f in sorted((REPO / ".wrapup" / "mres").glob("*/*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:               # 面板日志损坏不影响其它面板
            continue
        p = d.get("model") or d.get("model_arg")
        if not isinstance(p, str):
            continue
        tag = f.parent.name
        models = tag_models.get(tag)
        if not models:                  # 面板没有入库行，就没有可归属的文件
            continue
        vendor = vendor_in_path(p)
        for m in models:
            base = m if m.endswith(".gguf") else m + ".gguf"
            out.setdefault(base, set()).add(vendor)
    return out


def load(bench_order=BENCH_ORDER):
    """{model: {bench: cell}}，只收有 bpw 的文件。"""
    cc = con()
    models = sorted({r[0] for r in cc.execute(
        "SELECT DISTINCT model FROM experiments WHERE source_file LIKE 'mres/%' AND reasoning<>'on'"
        " AND _score IS NOT NULL")})
    cells, dups = {}, []
    for m in models:
        if not m.endswith(".gguf"):
            m2 = m + ".gguf"
        else:
            m2 = m
        if m2 not in BPW_MAP:
            continue
        c = {}
        for b in bench_order:
            r, dup = cell(cc, m, b)
            if r is None:
                continue
            c[b] = r
            if dup:
                dups.append((m, b, r["run_tag"], r["n_items"], [(d[2], d[1]) for d in dup]))
        if c:
            cells[m2] = c
    return cells, dups


def slopes(cells):
    """每基准的「同族内每 +1 比特/权重的分数变化」：score ~ bpw + C(family) 的 OLS 斜率。

    族固定效应把规模与配置吸收掉，只留位宽的方向；TruthfulQA 也照算（它是概率质量，
    斜率可比但绝对值不可读，故只作参照）。
    """
    import numpy as np
    by_fam = {}
    for m, c in cells.items():
        by_fam.setdefault(a01.family_of(m), []).append((BPW_MAP[m], c))
    out = {}
    for b in BENCH_ORDER:
        rows = [(fam, bpw, c[b]["score"]) for fam, items in by_fam.items()
                for bpw, c in items if b in c]
        if len(rows) < 6 or len({r[0] for r in rows}) < 3:
            out[b] = (float("nan"), float("nan"), len(rows))
            continue
        fams = sorted({r[0] for r in rows})
        X = [[r[1]] + [1.0 if r[0] == f else 0.0 for f in fams[1:]] for r in rows]
        y = [r[2] for r in rows]
        beta, *_ = np.linalg.lstsq(np.array(X, float), np.array(y, float), rcond=None)
        resid = np.array(y, float) - np.array(X, float) @ beta
        dof = len(rows) - len(beta)
        s2 = float(resid @ resid) / max(dof, 1)
        try:
            cov = s2 * np.linalg.inv(np.array(X, float).T @ np.array(X, float))
            se = float(np.sqrt(cov[0, 0]))
        except Exception:               # 共线时没有 se，报 nan 而不是编一个
            se = float("nan")
        out[b] = (float(beta[0]), se, len(rows))
    return out


def pair_record(a, b, cells, vendors, bound):
    """(低比特文件, 高比特文件) 的逐基准配对记录，含协议一致性检查。"""
    cb, cc_ = cells[a], cells[b]
    rec = {"low": a, "high": b, "bpw_low": BPW_MAP[a], "bpw_high": BPW_MAP[b],
           "dbpw": BPW_MAP[b] - BPW_MAP[a],
           "family": a01.family_of(a), "same_family": a01.family_of(a) == a01.family_of(b),
           "quant_low": quant_label(a), "quant_high": quant_label(b),
           "schema_low": scheme_of(quant_label(a)), "schema_high": scheme_of(quant_label(b)),
           "vendor_low": sorted(vendors.get(a, ["?"])), "vendor_high": sorted(vendors.get(b, ["?"])),
           "cells": {}, "incomparable": [], "bound": bound}
    for bench in BENCH_ORDER:
        rl, rh = cb.get(bench), cc_.get(bench)
        if rl is None or rh is None:
            continue
        keys = ("protocol", "n_items", "ctx_size", "parallel_slots", "temp", "reasoning")
        bad = [k for k in keys if rl[k] != rh[k]]
        if bad:
            rec["incomparable"].append((bench, bad, [(k, rl[k], rh[k]) for k in bad]))
            continue
        rec["cells"][bench] = {"low": rl, "high": rh, "delta": rh["score"] - rl["score"]}
    rec["kind"] = classify(rec)
    return rec


def classify(rec):
    """配对的性质：变的是方案、是厂商、两者都变，还是只有比特预算变。"""
    s = rec["schema_low"] != rec["schema_high"]
    v = rec["vendor_low"] != rec["vendor_high"]
    if v and s:
        return "vendor+scheme"
    if v:
        return "vendor"
    if s:
        return "scheme"
    return "budget"


def enumerate_pairs(cells, vendors, bound):
    by_fam = {}
    for m in cells:
        by_fam.setdefault(a01.family_of(m), []).append(m)
    out = []
    for fam, ms in sorted(by_fam.items()):
        ms = sorted(ms, key=lambda m: BPW_MAP[m])
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                if BPW_MAP[ms[j]] - BPW_MAP[ms[i]] <= bound + 1e-9:
                    out.append(pair_record(ms[i], ms[j], cells, vendors, bound))
    return out


def interval(rec, bench):
    """(差值, 95% 区间或 None)，区间由两格自己的 n_items 定。"""
    c = rec["cells"][bench]
    if bench in NON_COUNT:
        return c["delta"], None
    n1, n2 = c["low"]["n_items"], c["high"]["n_items"]
    if not n1 or not n2:
        return c["delta"], None
    k1 = round(c["low"]["score"] * n1)
    k2 = round(c["high"]["score"] * n2)
    return c["delta"], a01.newcombe_diff(k2, n2, k1, n1)


def fmt_pair(rec, sl):
    """一条配对的可读输出：位宽、性质、每列差值[区间]、比特预算能解释的比例。"""
    head = (f"{rec['family']:<22} {rec['quant_low']:<12}→{rec['quant_high']:<12} "
            f"{rec['bpw_low']:.3f}→{rec['bpw_high']:.3f} Δ={rec['dbpw']:+.3f} "
            f"[{rec['kind']}] vendor {('/'.join(rec['vendor_low']))}→{('/'.join(rec['vendor_high']))}")
    lines = [head]
    for bench in BENCH_ORDER:
        if bench not in rec["cells"]:
            continue
        d, ci = interval(rec, bench)
        s = sl.get(bench, (float("nan"),) * 3)[0]
        expect = s * rec["dbpw"]
        ci_s = "      —      " if ci is None else f"[{ci[0]:+.4f},{ci[1]:+.4f}]"
        sig = "" if ci is None else (" 区间不含0" if (ci[0] > 0) == (ci[1] > 0) and ci[0] * ci[1] > 0 else " 跨0")
        lines.append(f"    {SHORT[bench]:<6} Δ={d:+.4f} {ci_s} n={rec['cells'][bench]['low']['n_items']}"
                     f" 比特预算={expect:+.4f}{sig}")
    for bench, bad, vals in rec["incomparable"]:
        lines.append(f"    {SHORT[bench]:<6} 不可比：{bad} {vals}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bound", type=float, default=0.15,
                    help="匹配字节判据（比特/权重），默认 0.15；0.45 是报告现行口径")
    ap.add_argument("--kind", default=None, choices=("scheme", "vendor", "vendor+scheme", "budget"),
                    help="只打印某一类配对")
    ap.add_argument("--slopes", action="store_true", help="只打印每基准的同族每比特斜率")
    ap.add_argument("--inventory", action="store_true", help="只打印文件 → 方案/厂商/位宽 清单")
    a = ap.parse_args(argv)

    cells, dups = load()
    vendors = vendor_of()
    sl = slopes(cells)

    if a.slopes:
        print("同族内每 +1 比特/权重的分数变化（score ~ bpw + C(family) 的 OLS 斜率）")
        for b in BENCH_ORDER:
            s, se, n = sl[b]
            print(f"  {SHORT[b]:<7} {s:+.4f} ± {1.96 * se if se == se else float('nan'):.4f}  (n={n} 格)")
        return 0

    if a.inventory:
        print(f"{'bpw':>6}  {'vendor':<12} {'方案':<4} {'档位':<14} 家族                      文件")
        for m in sorted(cells, key=lambda m: (a01.family_of(m), BPW_MAP[m])):
            q = quant_label(m)
            print(f"{BPW_MAP[m]:6.3f}  {('/'.join(sorted(vendors.get(m, ['?'])))) :<12} "
                  f"{scheme_of(q):<4} {q:<14} {a01.family_of(m):<24} {m}")
        return 0

    pairs = enumerate_pairs(cells, vendors, a.bound)
    pairs = [p for p in pairs if p["cells"]]
    if a.kind:
        pairs = [p for p in pairs if p["kind"] == a.kind]
    print(f"匹配字节判据 |Δbpw| ≤ {a.bound}；配对 {len(pairs)} 对；"
          f"每格区间 = 两比例差 Newcombe method 10，n 取该格自己的 n_items\n")
    for p in pairs:
        print(fmt_pair(p, sl))
        print()
    if dups:
        print(f"同格多行（取 n_items 最大者）：{len(dups)} 处")
        for d in dups[:10]:
            print("   ", d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
