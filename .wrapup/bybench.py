#!/usr/bin/env python3
"""COMPARISON tables only.  Every table varies exactly ONE factor, holds the rest
fixed, and every row has >=1 data point and every column has >=2 (else pruned).
"""
import collections
import glob
import json
import math
import os
import re
import sqlite3

W = ".wrapup"
BPW = json.load(open(f"{W}/bpw_map.json"))
con = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)

_L = collections.defaultdict(list)
for _f in glob.glob(f"{W}/*_summary.jsonl"):
    for _line in open(_f):
        try:
            _r = json.loads(_line)
        except Exception:
            continue
        if _r.get("lang") and _r.get("n"):
            _L[_r["lang"]].append(_r["n"])
LANG_N = {k: collections.Counter(v).most_common(1)[0][0] for k, v in _L.items()}


def disp(m):
    x = m.replace(".gguf", "").replace("Qwen_Qwen", "Qwen")
    x = re.sub(r"[-_](UD-)?(I?Q\d[_A-Za-z0-9]*|TQ1_0|Q2_g0?_g?64|Q2_0_g64)$", "", x)
    return x


def sl(m):
    """short label: model + bpw"""
    return f"{disp(m)} @{BPW.get(m, float('nan')):.2f}"


def pooled(d):
    num = den = 0.0
    for l, s in d.items():
        n = LANG_N.get(l, 161)
        num += s * n
        den += n
    return (num / den) if den else None


def ci(a, n2, b, n3):
    se = math.sqrt(a * (1 - a) / n2 + b * (1 - b) / n3)
    d = b - a
    return d, se, d - 1.96 * se, d + 1.96 * se


def f(x, d=4):
    return "-" if x is None else f"{x:.{d}f}"


# ---------------------------------------------------------------- data
code = collections.defaultdict(dict)
for m, q, l, s in con.execute("""SELECT model,__quant,language,AVG(_score) FROM experiments
        WHERE bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768'
          AND run_tag IS NOT NULL GROUP BY 1,2,3"""):
    code[(m, q)][l] = s

st = collections.defaultdict(dict)
for m, q, b, s in con.execute("""SELECT model,__quant,_bench,AVG(_score) FROM experiments
        WHERE bench_family='bfcl' AND protocol='bfcl-native-tools-nothink-greedy'
          AND run_tag IS NOT NULL GROUP BY 1,2,3"""):
    st[(m, q)][b[5:]] = s

mt = collections.defaultdict(dict)
for m, q, b, s in con.execute("""SELECT model,__quant,_bench,AVG(_score) FROM experiments
        WHERE bench_family='bfcl-multiturn' AND run_tag IS NOT NULL GROUP BY 1,2,3"""):
    mt[(m, q)][b[5:]] = s


def cells(m, q):
    d = code.get((m, q), {})
    s = st.get((m, q), {})
    g = mt.get((m, q), {})
    sv = [v for v in s.values() if v is not None]
    return {"代码": pooled(d) if d else None,
            "BFCL单轮": (sum(sv) / len(sv)) if sv else None,
            "多轮base": g.get("multi_turn_base"),
            "long_ctx": g.get("multi_turn_long_context"),
            "miss_func": g.get("multi_turn_miss_func"),
            "miss_param": g.get("multi_turn_miss_param")}


ALLCOLS = ["代码", "BFCL单轮", "多轮base", "long_ctx", "miss_func", "miss_param"]


def render(o, rows, cols=None, d=4):
    """rows = list of (label, {col: value}).  Prunes empty rows/cols."""
    cols = cols or ALLCOLS
    cols = [c for c in cols if sum(1 for _, r in rows if r.get(c) is not None) >= 2]
    rows = [(l, r) for l, r in rows if any(r.get(c) is not None for c in cols)]
    if not rows or not cols:
        o.append("*（无有效对比：没有任一列达到 2 个数据点）*")
        return
    o.append("| | " + " | ".join(f"**{c}**" for c in cols) + " |")
    o.append("|---" * (len(cols) + 1) + "|")
    for l, r in rows:
        o.append(f"| {l} | " + " | ".join(f(r.get(c), d) for c in cols) + " |")


def main():
    o = []
    A = o.append
    A("# 受控对比表")
    A("")
    A("每张表**只变一个因素**，其余尽量相同；**行至少 1 个数据点、列至少 2 个数据点**才保留。")
    A("横轴 bpw 为**有效 bpw = 8×文件字节/参数量**。`[H]`=harness 假 0。")
    A("")

    # ============ T1 BPW sweep ============
    A("## T1. 不同 BPW（同一模型，其他参数完全相同）")
    A("")
    for m0 in ("Qwen3.5-2B", "granite-4.1-3b", "Qwen3.5-4B", "gemma-4-E2B-it"):
        rows = []
        for (m, q) in sorted({k for k in list(code) + list(st) + list(mt)},
                             key=lambda k: BPW.get(k[0], 9)):
            if not m.startswith(m0) or "m55" in m:
                continue
            rows.append((f"**{BPW[m]:.2f}** bpw", cells(m, q)))
        # merge duplicate bpw rows (same model measured under 2 tags)
        merged = {}
        for l, r in rows:
            tgt = merged.setdefault(l, {})
            for k, v in r.items():
                if v is not None and tgt.get(k) is None:
                    tgt[k] = v
        rows = list(merged.items())
        if len(rows) < 2:
            continue
        A(f"**{m0}**")
        A("")
        render(o, rows)
        A("")

    A("### T1b. 只有两级 BPW 的模型（即 Q2→Q3 一步，其他全同）")
    A("")
    _t1b = []
    two = [("Phi-4-mini-instruct", 3.51, 4.42), ("MiniCPM5-2B", 3.22, 3.93),
           ("Llama-3.2-3B-Instruct", 3.40, 4.20), ("gemma-4-E4B-it", 4.00, 4.88),
           ("Qwen3.5-9B", 3.68, 4.52), ("Qwen3.6-35B-A3B", 2.83, 3.88),
           ("Qwen3.8-27B", 2.88, 3.85), ("Qwen3.5-0.8B", 4.44, 5.23),
           ("NVIDIA-Nemotron-3-Nano-4B", 5.04, 5.40), ("gemma-4-26B-A4B-it", 3.34, 4.09)]
    for m0, b0, b1 in two:
        cand = [m for m in BPW if m.startswith(m0) and abs(BPW[m] - b0) < 0.05]
        cand1 = [m for m in BPW if m.startswith(m0) and abs(BPW[m] - b1) < 0.05]
        if not (cand and cand1):
            continue
        ca, cb = cells(cand[0], ""), cells(cand1[0], "")
        ca = cells(cand[0], con.execute("SELECT __quant FROM experiments WHERE model=? LIMIT 1",
                                        (cand[0],)).fetchone()[0])
        cb = cells(cand1[0], con.execute("SELECT __quant FROM experiments WHERE model=? LIMIT 1",
                                         (cand1[0],)).fetchone()[0])
        row = []
        for c in ALLCOLS:
            v0, v1 = ca.get(c), cb.get(c)
            row.append(f"{(v1-v0):+.4f}" if v0 is not None and v1 is not None else "-")
        _t1b.append((f"{m0}", f"{b0:.2f}→{b1:.2f}", row))
    _cols = [c for i, c in enumerate(ALLCOLS)
             if sum(1 for _, _, r in _t1b if r[i] != "-") >= 2]
    _idx = [ALLCOLS.index(c) for c in _cols]
    A("| 模型 | bpw 位移 | " + " | ".join(_cols) + " |")
    A("|---" * (len(_cols) + 2) + "|")
    for m0, dsp, row in _t1b:
        A(f"| {m0} | {dsp} | " + " | ".join(row[i] for i in _idx) + " |")
    A("")

    # ============ T2 scheme / vendor ============
    A("## T2. 不同量化方案 / vendor（同一模型、同一体积档，其他相同）")
    A("")
    A("*只有代码 benchmark 有方案对比数据，其余 benchmark 没有跑过 → 该列不显示。*")
    A("")
    A("| 模型 | 对比 | bpw | 代码 Δ | 95% CI | 显著 |")
    A("|---|---|---|---|---|---|")
    for base, aq, bq in [("Qwen3.5-2B", "UD-IQ3_XXS", "UD-Q2_K_XL"),
                         ("Qwen3.5-4B", "UD-IQ3_XXS", "UD-Q2_K_XL")]:
        ma, mb = f"{base}-{aq}.gguf", f"{base}-{bq}.gguf"
        da, db = code.get((ma, aq)), code.get((mb, bq))
        if not (da and db):
            continue
        common = [l for l in da if l in db]
        pa = sum(da[l] * LANG_N.get(l, 161) for l in common) / sum(LANG_N.get(l, 161) for l in common)
        pb = sum(db[l] * LANG_N.get(l, 161) for l in common) / sum(LANG_N.get(l, 161) for l in common)
        na = nb = sum(LANG_N.get(l, 161) for l in common)
        d, se, lo, hi = ci(pb, nb, pa, na)
        A(f"| {base} | IQ3_XXS({BPW[ma]:.2f}) vs Q2_K_XL({BPW[mb]:.2f}) | ≈同 | {d:+.4f} | "
          f"[{lo:+.4f}, {hi:+.4f}] | {'**是**' if abs(d)>1.96*se else '否'} |")
    mv = "Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf"
    muv = "Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf"
    dv, du = code.get((mv, "Q3_K_M")), code.get((muv, "UD-Q3_K_XL"))
    if dv and du:
        common = [l for l in dv if l in du]
        pv = sum(dv[l] * LANG_N.get(l, 161) for l in common) / sum(LANG_N.get(l, 161) for l in common)
        pu = sum(du[l] * LANG_N.get(l, 161) for l in common) / sum(LANG_N.get(l, 161) for l in common)
        n = sum(LANG_N.get(l, 161) for l in common)
        d, se, lo, hi = ci(pu, n, pv, n)
        A(f"| Qwen3.6-35B-A3B | 厂商 Q3_K_M({BPW[mv]:.2f}) vs UD-Q3_K_XL({BPW[muv]:.2f}) | ≈同 | "
          f"{d:+.4f} | [{lo:+.4f}, {hi:+.4f}] | {'**是**' if abs(d)>1.96*se else '否'} |")
    A("")
    A("**结论**：imatrix/IQ 在同体积下更优（2B 显著、4B 仅方向）；**厂商标签本身无效**。")
    A("")

    # ============ T3 MoE ============
    A("## T3. MoE：不同专家量化方案（同一模型 LFM2.5-8B-A1B，同一面板）")
    A("")
    A("| 配方 | bpw | 代码 | 说明 |")
    A("|---|---|---|---|")
    for m, q, note in [("LFM2.5-8B-A1B-m55-Q3_K_M.gguf", "Q3_K_M", "均匀 Q3_K_M（基线）"),
                       ("LFM2.5-8B-A1B-m55-exq2.gguf", "", "专家 Q2_K + 其余 Q5_K_M"),
                       ("LFM2.5-8B-A1B-m55-exq4.gguf", "", "专家 Q4_K + 其余 Q2_K")]:
        r = con.execute("SELECT __quant FROM experiments WHERE model=? LIMIT 1", (m,)).fetchone()
        c = cells(m, r[0])["代码"] if r else None
        A(f"| {note} | {BPW[m]:.2f} | {f(c)} | run_tag m55-expertwise |")
    A("")
    A("专家 Q2/其余 Q5 = **2.92 bpw / 0.103** vs 均匀 = **3.88 bpw / 0.081**；")
    A("专家 Q4/其余 Q2 = **4.48 bpw / 0.068**（体积最大却最差）。")
    A("→ **比特更应该花在非专家部分**，Δ=+0.022 CI[−0.023,+0.066] **未达显著**。**只有代码数据。**")
    A("")

    # ============ T4 base model ============
    A("## T4. 不同 base model（BPW 相近，其他相同）")
    A("")
    buckets = [(2.7, 2.95), (3.1, 3.6), (3.6, 4.15), (4.15, 4.6)]
    for lo, hi in buckets:
        rows = []
        for (m, q) in {k for k in list(code) + list(st) + list(mt)}:
            b = BPW.get(m)
            if b is None or not (lo <= b < hi) or "m55" in m or "Bonsai" in m:
                continue
            rows.append((f"{disp(m)} @{b:.2f}", cells(m, q)))
        merged = {}
        for l, r in rows:
            t = merged.setdefault(l, {})
            for k, v in r.items():
                if v is not None and t.get(k) is None:
                    t[k] = v
        rows = sorted(merged.items())
        if len({l.split(" @")[0] for l, _ in rows}) < 2:
            continue
        A(f"**bpw ∈ [{lo}, {hi})**")
        A("")
        render(o, rows)
        A("")

    # ============ T5 model size ============
    A("## T5. 不同模型规模（同一家族、同一 recipe）")
    A("")
    for fam, qq in [("Qwen3.5", "UD-Q3_K_XL"), ("Qwen3.5", "UD-Q2_K_XL"), ("gemma-4", "UD-Q3_K_XL")]:
        rows = []
        for m in BPW:
            if not m.startswith(fam) or qq.replace("UD-", "") not in m:
                continue
            if "m55" in m:
                continue
            r = con.execute("SELECT __quant FROM experiments WHERE model=? LIMIT 1", (m,)).fetchone()
            if not r:
                continue
            c = cells(m, r[0])
            if any(v is not None for v in c.values()):
                rows.append((f"{disp(m)} @{BPW[m]:.2f}", c))
        if len(rows) < 2:
            continue
        A(f"**{fam} · {qq}**")
        A("")
        render(o, rows)
        A("")

    # ============ T6 KV ============
    A("## T6. 不同 KV 量化（同一模型 Qwen3.5-2B、同一 ctx、其他相同）")
    A("")
    A("*只有代码（cpp）数据。*")
    A("")
    A("| ctx | f16/f16 | f16/q8_0 | q8_0/f16 | q8_0/q8_0 |")
    A("|---|---|---|---|---|")
    for cx in (2048, 16384, 49152):
        cs = []
        for kv in (("f16", "f16"), ("f16", "q8_0"), ("q8_0", "f16"), ("q8_0", "q8_0")):
            r = con.execute("""SELECT AVG(_score) FROM experiments WHERE run_tag='m30-kv-ctx'
                 AND _bench='humaneval-cpp' AND protocol LIKE ? AND protocol LIKE ?""",
                            (f"%ctx={cx},%", f"%kv={kv[0]}/{kv[1]}%")).fetchone()[0]
            cs.append(f(r))
        A(f"| {cx} | " + " | ".join(cs) + " |")
    A("")
    A("**每行四格基本相同 → KV 量化无效**；分数下降由 ctx/padding 造成。每格 n=1。")
    A("")

    # ============ T7 sampling ============
    A("## T7. 不同采样参数（同一模型 Qwen3.5-2B、同一面板，其他相同）")
    A("")
    A("*只有代码（cpp/py）数据。*")
    A("")
    A("| 轴 | 值 | cpp | py |")
    A("|---|---|---|---|")
    tc = collections.defaultdict(dict)
    for t, l, s in con.execute("""SELECT temp,language,AVG(_score) FROM experiments
            WHERE run_tag='m27-sampling' GROUP BY 1,2"""):
        tc[t][l] = s
    for t in sorted(tc):
        A(f"| temp | {t} | {f(tc[t].get('cpp'))} | {f(tc[t].get('py'))} |")
    tk = collections.defaultdict(dict)
    for k, l, s in con.execute("""SELECT top_k,language,AVG(_score) FROM experiments
            WHERE run_tag='m31-topk' GROUP BY 1,2"""):
        tk[k][l] = s
    for k in sorted(tk, key=lambda x: int(x)):
        A(f"| top_k | {k} | {f(tk[k].get('cpp'))} | {f(tk[k].get('py'))} |")
    A("")
    A("top_k ≥ 20 逐格相同（只有 K=1 不同，且 cpp/py 方向相反）；temp 0.3 最好。")
    A("")

    # ============ T8 speculative decoding ============
    A("## T8. 投机解码对**速度**的影响（同一模型、同 ctx=16384、其他相同）")
    A("")
    A("Qwen3.5-2B-UD-Q4_K_XL（`m28-speed`），单位 tok/s：")
    A("")
    A("| spec_draft_n_max | 代码 | 长上下文 | 散文 |")
    A("|---|---|---|---|")
    for n in ("0", "1", "2", "3", "4"):
        r = {}
        for b in ("speed-code", "speed-longctx", "speed-prose"):
            v = con.execute("""SELECT AVG(_tok_s) FROM experiments WHERE run_tag='m28-speed'
                 AND _bench=? AND spec_draft_n_max=?""", (b, n)).fetchone()[0]
            r[b] = v
        A(f"| {n}{'（无投机）' if n=='0' else ''} | {f(r['speed-code'],1)} | "
          f"{f(r['speed-longctx'],1)} | {f(r['speed-prose'],1)} |")
    A("")
    A("**任务相关**：代码 n=3 峰值 **+32%**、散文 n=4 **+19%**，但**长上下文所有 n 都更差**（n=4 时 −16%）。")
    A("")
    A("对照组 gemma-4-12b-it（`m52-speed`）：n=0/2/4/6 下代码 90.38/90.47/90.45/90.02 tok/s **完全平坦**")
    A("→ **该模型的投机通路没有真正生效**（非 null，是非测量）。")
    A("")

    open("RESULTS_BY_BENCHMARK.md", "w").write("\n".join(o) + "\n")
    print("wrote RESULTS_BY_BENCHMARK.md:", len(o), "lines")


if __name__ == "__main__":
    main()
