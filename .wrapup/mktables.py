#!/usr/bin/env python3
"""ONE table per research variable.

col1 = everything held constant, col2 = the varied variable, then one column per
benchmark.  Empty CELLS are allowed.  A whole table is emitted per axis (never
split).  A col1 group is dropped only when it has <2 distinct col2 values (no
comparison possible).  No other row is ever dropped.
"""
import collections
import glob
import json
import re
import sqlite3

W = ".wrapup"
BPW = json.load(open(f"{W}/bpw_map.json"))
con = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)

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


def short(m):
    x = m.replace(".gguf", "").replace("Qwen_Qwen", "Qwen")
    x = re.sub(r"-instruct", "", x, flags=re.I)
    return re.sub(r"[-_](UD-)?(I?Q\d[_A-Za-z0-9]*|TQ1_0|Q2_0_g64|Q2_g64)$", "", x)


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

NONLIVE = ("irrelevance", "multiple", "parallel", "parallel_multiple", "simple_python")


def cells(m, q):
    d = code.get((m, q), {})
    s = [v for k, v in bfcl.get((m, q), {}).items() if v is not None and k in NONLIVE]
    g = mt.get((m, q), {})
    pu = None
    if d:
        pu = (sum(d[l] * LANG_N.get(l, 161) for l in d)
              / sum(LANG_N.get(l, 161) for l in d))
    return {"代码": pu,
            "BFCL单轮": (sum(s) / len(s)) if s else None,
            "多轮base": g.get("multi_turn_base"),
            "long_ctx": g.get("multi_turn_long_context"),
            "miss_func": g.get("multi_turn_miss_func"),
            "miss_param": g.get("multi_turn_miss_param")}


SRC = {}
for (m, q) in set(code) | set(bfcl) | set(mt):
    if m in BPW:
        SRC[(m, q)] = cells(m, q)
QOF = collections.defaultdict(list)
for (m, q) in SRC:
    QOF[m].append(q)


def table(o, title, note, c1, c2, rows, cols=None):
    """rows = [(col1, col2, cells)].  One table.  Drop col1 groups with <2 col2.
    cols = the table's own column set (never filtered down)."""
    cols = cols or BENCH
    grp = collections.defaultdict(dict)
    for a, b, c in rows:
        if any(c.get(x) is not None for x in cols):
            grp[a][b] = c
    keep = {a: v for a, v in grp.items() if len(v) >= 2}
    o.append(f"## {title}")
    o.append("")
    if note:
        o.append(note)
        o.append("")
    if not keep:
        o.append("*没有一组有 ≥2 个对比项，故不写。*")
        o.append("")
        return
    o.append(f"| {c1} | {c2} | " + " | ".join(f"**{b}**" for b in cols) + " |")
    o.append("|---" * (len(cols) + 2) + "|")
    for a in sorted(keep):
        for b in sorted(keep[a], key=lambda x: [float(t) for t in re.findall(r"[0-9.]+", x)] or [0.0]):
            c = keep[a][b]
            o.append(f"| {a} | {b} | " + " | ".join(
                "-" if c.get(x) is None else f"{c[x]:.4f}" for x in cols) + " |")
    o.append("")


def main():
    o = []
    A = o.append
    A("# 量化研究：每个变量一张表")
    A("")
    A("第 1 列 = 保持不变的一切；第 2 列 = 本次变化的变量；之后每列 = 一个 benchmark。")
    A("**空单元格用 `-` 表示（数据本来就没跑），但不写整行全空的行。**")
    A("第 1 列只有 1 个第 2 列取值的组（没有对比）才剔除。")
    A("BPW = 8 × 文件字节 ÷ 参数量。代码 = MultiPL-E raw greedy 768 pooled；")
    A("BFCL单轮 = native-FC 五类均值；多轮 = BFCL-MT temp0。")
    A("")

    # 1 BPW
    rows = []
    for m, qs in QOF.items():
        if len({round(BPW[m], 2)}) < 1:
            continue
        for q in qs:
            rows.append((short(m), f"{BPW[m]:.2f} bpw", SRC[(m, q)]))
    table(o, "1. 变量 = BPW（第 1 列 = 模型，其他全同）",
          "只保留跑过 ≥2 个 BPW 的模型。同一模型内的采样参数、ctx、协议、benchmark 版本完全一致。",
          "模型（其他全同）", "BPW", rows)

    # 2 size
    for fam, models in [("Ternary-Bonsai", ["Ternary-Bonsai-1.7B-Q2_0_g64.gguf",
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
                                                  "Qwen3.5-9B-UD-Q3_K_XL.gguf"])]:
        rows = []
        for m in models:
            if m not in QOF:
                continue
            sz = re.search(r"(\d+\.?\d*)B", m)
            rows.append((fam, (sz.group(1) + "B") if sz else m, SRC[(m, QOF[m][0])]))
        table(o, f"2. 变量 = 模型规模（{fam}，其他全同）",
              "同一家族、同一 recipe，只有规模不同。",
              "家族 + recipe（其他全同）", "规模", rows)

    # 3 vendor
    rows = []
    for base, pairs in [("Qwen3.5-2B @≈4.0bpw", [("Qwen3.5-2B-UD-IQ3_XXS.gguf", "IQ3_XXS"),
                                                 ("Qwen3.5-2B-UD-Q2_K_XL.gguf", "Q2_K_XL")]),
                        ("Qwen3.5-4B @≈3.7bpw", [("Qwen3.5-4B-UD-IQ3_XXS.gguf", "IQ3_XXS"),
                                                 ("Qwen3.5-4B-UD-Q2_K_XL.gguf", "Q2_K_XL")]),
                        ("Qwen3.6-35B-A3B @≈3.9bpw", [("Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf", "厂商 Q3_K_M"),
                                                      ("Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf", "UD-Q3_K_XL")])]:
        for m, lab in pairs:
            if m in QOF:
                rows.append((base, lab, SRC[(m, QOF[m][0])]))
    table(o, "3. 变量 = 量化方案 / vendor（第 1 列 = 模型+体积档，其他全同）",
          "每组的两个方案文件大小基本相同（BPW 差 ≤0.15）。",
          "模型 + 体积档（其他全同）", "方案", rows)

    # 4 MoE
    rows = []
    for m, lab in [("LFM2.5-8B-A1B-m55-exq2.gguf", "专家 Q2_K + 其余 Q5_K_M"),
                   ("LFM2.5-8B-A1B-m55-Q3_K_M.gguf", "均匀 Q3_K_M（基线）"),
                   ("LFM2.5-8B-A1B-m55-exq4.gguf", "专家 Q4_K + 其余 Q2_K")]:
        if m in QOF:
            rows.append((f"LFM2.5-8B-A1B", f"{lab}（{BPW[m]:.2f} bpw）", SRC[(m, QOF[m][0])]))
    table(o, "4. 变量 = MoE 的比特分配（第 1 列 = LFM2.5-8B-A1B，同面板）",
          "三个配方只改专家层与非专家层的比特分配，其余全同。",
          "模型（其他全同）", "配方", rows)

    # 5 KV
    rows = []
    for cx in (2048, 16384, 49152):
        for a, b in (("f16", "f16"), ("f16", "q8_0"), ("q8_0", "f16"), ("q8_0", "q8_0")):
            v = con.execute("""SELECT AVG(_score) FROM experiments WHERE run_tag='m30-kv-ctx'
                AND _bench='humaneval-cpp' AND protocol LIKE ? AND protocol LIKE ?""",
                (f"%ctx={cx},%", f"%kv={a}/{b}%")).fetchone()[0]
            rows.append((f"Qwen3.5-2B @4.11bpw · ctx{cx}", f"{a}/{b}", {"代码": v}))
    table(o, "5. 变量 = KV 量化（第 1 列 = 模型·BPW·ctx，其他全同）",
          "只有代码（cpp）数据，每格 n=1。",
          "模型·BPW·ctx（其他全同）", "KV 类型", rows)

    # 6 sampling
    rows = []
    tc = collections.defaultdict(dict)
    for t, l, v in con.execute("""SELECT temp,language,AVG(_score) FROM experiments
            WHERE run_tag='m27-sampling' GROUP BY 1,2"""):
        tc[t][l] = v
    for t in sorted(tc):
        rows.append(("Qwen3.5-2B @4.11bpw · temperature", t,
                     {"cpp": tc[t]["cpp"], "py": tc[t]["py"]}))
    tk = collections.defaultdict(dict)
    for k, l, v in con.execute("""SELECT top_k,language,AVG(_score) FROM experiments
            WHERE run_tag='m31-topk' GROUP BY 1,2"""):
        tk[k][l] = v
    for k in sorted(tk, key=lambda x: int(x)):
        rows.append(("Qwen3.5-2B @4.11bpw · top_k", k,
                     {"cpp": tk[k]["cpp"], "py": tk[k]["py"]}))
    table(o, "6. 变量 = 采样参数（第 1 列 = 模型·BPW·轴，其他全同）",
          "只有代码数据（cpp / py 两个语言列）。",
          "模型·BPW·轴（其他全同）", "取值", rows, cols=["cpp", "py"])

    # 7 spec decode
    rows = []
    for n in ("0", "1", "2", "3", "4"):
        r = {b: con.execute("""SELECT AVG(_tok_s) FROM experiments WHERE run_tag='m28-speed'
             AND _bench=? AND spec_draft_n_max=?""", (b, n)).fetchone()[0]
             for b in ("speed-code", "speed-longctx", "speed-prose")}
        rows.append(("Qwen3.5-2B @5.70bpw · ctx16384", n,
                     {"代码": r["speed-code"], "长上下文": r["speed-longctx"],
                      "散文": r["speed-prose"]}))
    table(o, "7. 变量 = 投机解码深度（第 1 列 = 模型·BPW·ctx，单位 tok/s）",
          "单位 tok/s；三列是测速场景，不是准确率。",
          "模型·BPW·ctx（其他全同）", "spec_draft_n_max", rows,
          cols=["代码", "长上下文", "散文"])

    rows = []
    for n in ("0", "2", "4", "6"):
        r = {b: con.execute("""SELECT AVG(_tok_s) FROM experiments WHERE run_tag='m52-speed'
             AND model='gemma-4-12b-it-UD-Q3_K_XL.gguf' AND _bench=? AND spec_draft_n_max=?""",
             (b, n)).fetchone()[0] for b in ("speed-code", "speed-prose")}
        rows.append(("gemma-4-12b @4.05bpw · ctx16384", n,
                     {"代码": r["speed-code"], "散文": r["speed-prose"]}))
    table(o, "7b. 对照组：gemma-4-12b 的投机深度（tok/s）",
          "完全平坦 → 该模型的投机通路没有生效，是非测量。",
          "模型·BPW·ctx（其他全同）", "spec_draft_n_max", rows,
          cols=["代码", "散文"])

    open("RESULTS_BY_COMPARISON.md", "w").write("\n".join(o) + "\n")
    print("wrote RESULTS_BY_COMPARISON.md:", len(o), "lines")


if __name__ == "__main__":
    main()
