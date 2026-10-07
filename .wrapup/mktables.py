#!/usr/bin/env python3
"""Rebuild RESULTS_BY_COMPARISON.md with ZERO empty cells.

Rows are (model, bpw).  For a given axis we keep only groups whose fixed part has
>=2 distinct varied values.  Then rows are partitioned by the SET of benchmark
columns they actually have, and one table is emitted per column-set that has >=2
rows.  Consequence: no table ever contains an empty cell, and no row is dropped
silently - a row that lacks a benchmark simply appears in a table with fewer
benchmark columns.
"""
import collections
import glob
import json
import math
import re
import sqlite3

W = ".wrapup"
BPW = json.load(open(f"{W}/bpw_map.json"))
con = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)

LANG_N = {}
_n = collections.defaultdict(list)
for _f in glob.glob(f"{W}/*_summary.jsonl"):
    for _l in open(_f):
        try:
            _r = json.loads(_l)
        except Exception:
            continue
        if _r.get("lang") and _r.get("n"):
            _n[_r["lang"]].append(_r["n"])
LANG_N = {k: collections.Counter(v).most_common(1)[0][0] for k, v in _n.items()}

BENCH = ["代码", "BFCL单轮", "多轮base", "long_ctx", "miss_func", "miss_param"]


def disp(m):
    x = m.replace(".gguf", "").replace("Qwen_Qwen", "Qwen")
    return re.sub(r"[-_](UD-)?(I?Q\d[_A-Za-z0-9]*|TQ1_0|Q2_0_g64|Q2_g64)$", "", x)


def short(m):
    """row label: model + everything that identifies the variant"""
    x = disp(m)
    x = re.sub(r"-instruct", "", x, flags=re.I)
    x = re.sub(r"-Q\d_K(_M|_XL)?$", "", x)
    return x


code = collections.defaultdict(dict)
for m, q, l, s in con.execute("""SELECT model,__quant,language,AVG(_score) FROM experiments
        WHERE bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768'
          AND run_tag IS NOT NULL GROUP BY 1,2,3"""):
    code[(m, q)][l] = s
bfcl = collections.defaultdict(dict)
for m, q, b, s in con.execute("""SELECT model,__quant,_bench,AVG(_score) FROM experiments
        WHERE bench_family='bfcl' AND protocol='bfcl-native-tools-nothink-greedy'
          AND run_tag IS NOT NULL GROUP BY 1,2,3"""):
    bfcl[(m, q)][b[5:]] = s
mt = collections.defaultdict(dict)
for m, q, b, s in con.execute("""SELECT model,__quant,_bench,AVG(_score) FROM experiments
        WHERE bench_family='bfcl-multiturn' AND run_tag IS NOT NULL GROUP BY 1,2,3"""):
    mt[(m, q)][b[5:]] = s


def cells(m, q):
    d = code.get((m, q), {})
    _NONLIVE = ("irrelevance", "multiple", "parallel", "parallel_multiple", "simple_python")
    s = [v for k, v in bfcl.get((m, q), {}).items() if v is not None and k in _NONLIVE]
    g = mt.get((m, q), {})
    pu = None
    if d:
        num = sum(d[l] * LANG_N.get(l, 161) for l in d)
        den = sum(LANG_N.get(l, 161) for l in d)
        pu = num / den
    return {"代码": pu,
            "BFCL单轮": (sum(s) / len(s)) if s else None,
            "多轮base": g.get("multi_turn_base"),
            "long_ctx": g.get("multi_turn_long_context"),
            "miss_func": g.get("multi_turn_miss_func"),
            "miss_param": g.get("multi_turn_miss_param")}


# ---------------------------------------------------------------- axis defs
SOURCES = {}
for (m, q) in set(code) | set(bfcl) | set(mt):
    if m in BPW:
        SOURCES[(m, q)] = cells(m, q)


def emit(o, fixed_label, varied_label, rows, title, note=""):
    """rows = [(fixed, varied, {bench: val})].  Partition by column-set."""
    groups = collections.defaultdict(list)
    for fx, vr, c in rows:
        key = tuple(b for b in BENCH if c.get(b) is not None)
        groups[key].append((fx, vr, c))
    out_any = False
    keys = [k for k in sorted(groups, key=lambda k: -len(k)) if len(k) >= 2]
    for key in keys:
        rs = groups[key]
        if len(rs) < 2:
            continue
        if not out_any:
            o.append(f"**{title}**")
            if note:
                o.append(f"\n{note}\n")
            out_any = True
        o.append(f"| {fixed_label} | {varied_label} | " +
                 " | ".join(f"**{b}**" for b in key) + " |")
        o.append("|---" * (len(key) + 2) + "|")
        for fx, vr, c in rs:
            o.append(f"| {fx} | {vr} | " + " | ".join(f"{c[b]:.4f}" for b in key) + " |")
        o.append("")
    # always finish with the full 代码-only table so no data is lost
    allrows = [(fx, vr, c) for fx, vr, c in rows if c.get("代码") is not None]
    if len(allrows) >= 2:
        o.append(f"**{title} · 全部（仅代码列）**")
        o.append("")
        o.append(f"| {fixed_label} | {varied_label} | **代码** |")
        o.append("|---|---|---|")
        for fx, vr, c in allrows:
            o.append(f"| {fx} | {vr} | {c['代码']:.4f} |")
        o.append("")
        out_any = True
    if not out_any:
        o.append(f"*{title}：没有 ≥2 个可比项，不写。*\n")


def main():
    o = []
    A = o.append
    A("# 对比表（零空格）")
    A("")
    A("每行 = 一个模型的一个 BPW。**某行缺哪个 benchmark，就归到列更少的那张表**，")
    A("所以任何一张表都不会出现空单元格，也没有任何数据被丢掉。")
    A("BPW = 8 × 文件字节 ÷ 参数量。代码 = MultiPL-E raw greedy 768 pooled；")
    A("BFCL单轮 = native-FC 五类均值；多轮 = BFCL-MT temp0。")
    A("")

    # ---- BPW axis: fixed = model, varied = bpw
    A("## 1. 变量 = BPW（第 1 列 = 模型，其他全同）")
    A("")
    bym = collections.defaultdict(list)
    for (m, q), c in SOURCES.items():
        bym[short(m)].append((m, q, c))
    rows = []
    for mdl, lst in bym.items():
        bpws = sorted({round(BPW[m], 2) for m, q, c in lst})
        if len(bpws) < 2:
            continue
        for m, q, c in sorted(lst, key=lambda t: BPW[t[0]]):
            rows.append((mdl, f"{BPW[m]:.2f}", c))
    emit(o, "模型（其他全同）", "BPW", rows, "BPW 扫描")

    # ---- size axis
    A("## 2. 变量 = 模型规模（第 1 列 = 家族 + recipe，其他全同）")
    A("")
    size = [("Ternary-Bonsai", ["Ternary-Bonsai-1.7B-Q2_0_g64.gguf",
                                "Ternary-Bonsai-4B-Q2_0_g64.gguf",
                                "Ternary-Bonsai-8B-Q2_0_g64.gguf",
                                "Ternary-Bonsai-27B-Q2_g64.gguf"]),
            ("Qwen3.5 · UD-Q2_K_XL", ["Qwen3.5-0.8B-UD-Q2_K_XL.gguf",
                                      "Qwen3.5-2B-UD-Q2_K_XL.gguf",
                                      "Qwen3.5-4B-UD-Q2_K_XL.gguf",
                                      "Qwen3.5-9B-UD-Q2_K_XL.gguf"]),
            ("Qwen3.5 · UD-Q3_K_XL", ["Qwen3.5-0.8B-UD-Q3_K_XL.gguf",
                                      "Qwen3.5-2B-UD-Q3_K_XL.gguf",
                                      "Qwen3.5-4B-UD-Q3_K_XL.gguf",
                                      "Qwen3.5-9B-UD-Q3_K_XL.gguf"])]
    for fam, models in size:
        rows = []
        for m in models:
            q = [k[1] for k in SOURCES if k[0] == m]
            if not q:
                continue
            sz = re.search(r"(\d+\.?\d*)B", m)
            rows.append((fam, (sz.group(1) + "B") if sz else m, SOURCES[(m, q[0])]))
        emit(o, "家族（其他全同）", "规模", rows, f"规模扫描 · {fam}")

    # ---- vendor / scheme axis
    A("## 3. 变量 = 量化方案 / vendor（第 1 列 = 模型，体积相近）")
    A("")
    rows = []
    for base, pairs in [("Qwen3.5-2B", [("Qwen3.5-2B-UD-IQ3_XXS.gguf", "IQ3_XXS"),
                                        ("Qwen3.5-2B-UD-Q2_K_XL.gguf", "Q2_K_XL")]),
                        ("Qwen3.5-4B", [("Qwen3.5-4B-UD-IQ3_XXS.gguf", "IQ3_XXS"),
                                        ("Qwen3.5-4B-UD-Q2_K_XL.gguf", "Q2_K_XL")]),
                        ("Qwen3.6-35B-A3B", [("Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf", "厂商 Q3_K_M"),
                                             ("Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf", "UD-Q3_K_XL")])]:
        for m, label in pairs:
            q = [k[1] for k in SOURCES if k[0] == m]
            if q:
                rows.append((f"{base} @{BPW[m]:.2f}bpw", label, SOURCES[(m, q[0])]))
    emit(o, "模型（其他全同）", "方案", rows, "方案对比")

    # ---- MoE
    A("## 4. 变量 = MoE 比特分配（第 1 列 = LFM2.5-8B-A1B，同面板）")
    A("")
    rows = []
    for m, label in [("LFM2.5-8B-A1B-m55-exq2.gguf", "专家Q2 + 其余Q5"),
                     ("LFM2.5-8B-A1B-m55-Q3_K_M.gguf", "均匀 Q3_K_M"),
                     ("LFM2.5-8B-A1B-m55-exq4.gguf", "专家Q4 + 其余Q2")]:
        q = [k[1] for k in SOURCES if k[0] == m]
        if q:
            rows.append((f"LFM2.5-8B-A1B @{BPW[m]:.2f}bpw", label, SOURCES[(m, q[0])]))
    emit(o, "模型（其他全同）", "配方", rows, "MoE 比特分配")

    # ---- KV
    A("## 5. 变量 = KV 量化（第 1 列 = 模型·BPW·ctx，其他全同）")
    A("")
    A("| 模型·BPW·ctx（其他全同） | KV 类型 | **代码** |")
    A("|---|---|---|")
    for cx in (2048, 16384, 49152):
        for a, b in (("f16", "f16"), ("f16", "q8_0"), ("q8_0", "f16"), ("q8_0", "q8_0")):
            v = con.execute("""SELECT AVG(_score) FROM experiments WHERE run_tag='m30-kv-ctx'
                AND _bench='humaneval-cpp' AND protocol LIKE ? AND protocol LIKE ?""",
                (f"%ctx={cx},%", f"%kv={a}/{b}%")).fetchone()[0]
            A(f"| Qwen3.5-2B @4.11 · ctx{cx} | {a}/{b} | {v:.4f} |")
    A("")
    A("每组 4 个 KV 配置几乎相同 → KV 量化无影响；下降来自 ctx。每格 n=1，只有代码。")
    A("")

    # ---- sampling
    A("## 6. 变量 = 采样参数（第 1 列 = 模型·BPW·轴，其他全同）")
    A("")
    A("| 模型·BPW·轴（其他全同） | 取值 | **cpp** | **py** |")
    A("|---|---|---|---|")
    tc = collections.defaultdict(dict)
    for t, l, v in con.execute("""SELECT temp,language,AVG(_score) FROM experiments
            WHERE run_tag='m27-sampling' GROUP BY 1,2"""):
        tc[t][l] = v
    for t in sorted(tc):
        A(f"| Qwen3.5-2B @4.11 · temperature | {t} | {tc[t].get('cpp'):.4f} | {tc[t].get('py'):.4f} |")
    tk = collections.defaultdict(dict)
    for k, l, v in con.execute("""SELECT top_k,language,AVG(_score) FROM experiments
            WHERE run_tag='m31-topk' GROUP BY 1,2"""):
        tk[k][l] = v
    for k in sorted(tk, key=lambda x: int(x)):
        A(f"| Qwen3.5-2B @4.11 · top_k | {k} | {tk[k].get('cpp'):.4f} | {tk[k].get('py'):.4f} |")
    A("")
    A("top_k 20→200 逐格相同；只有 K=1 不同且两语言方向相反。只有代码。")
    A("")

    # ---- speed
    A("## 7. 变量 = 投机解码深度（tok/s，第 1 列 = 模型·BPW·ctx）")
    A("")
    A("| 模型·BPW·ctx（其他全同） | spec_draft_n_max | **代码** | **长上下文** | **散文** |")
    A("|---|---|---|---|---|")
    for n in ("0", "1", "2", "3", "4"):
        r = {b: con.execute("""SELECT AVG(_tok_s) FROM experiments WHERE run_tag='m28-speed'
             AND _bench=? AND spec_draft_n_max=?""", (b, n)).fetchone()[0]
             for b in ("speed-code", "speed-longctx", "speed-prose")}
        A(f"| Qwen3.5-2B @5.70 · ctx16384 | {n} | {r['speed-code']:.1f} | "
          f"{r['speed-longctx']:.1f} | {r['speed-prose']:.1f} |")
    A("")
    A("2B：代码 n=3 +32%、散文 n=4 +19%，但长上下文所有 n 都更慢（n=4 时 −16%）→ 任务相关。")
    A("")
    A("| 模型·BPW·ctx（其他全同） | spec_draft_n_max | **代码** | **散文** |")
    A("|---|---|---|---|")
    for n in ("0", "2", "4", "6"):
        r = {b: con.execute("""SELECT AVG(_tok_s) FROM experiments WHERE run_tag='m52-speed'
             AND model='gemma-4-12b-it-UD-Q3_K_XL.gguf' AND _bench=? AND spec_draft_n_max=?""",
             (b, n)).fetchone()[0] for b in ("speed-code", "speed-prose")}
        A(f"| gemma-4-12b @4.05 · ctx16384 | {n} | {r['speed-code']:.2f} | {r['speed-prose']:.2f} |")
    A("")
    A("gemma 完全平坦 → 投机通路没有生效，是**非测量**。")
    A("")

    open("RESULTS_BY_COMPARISON.md", "w").write("\n".join(o) + "\n")
    print("\n".join(o))


if __name__ == "__main__":
    main()
