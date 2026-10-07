#!/usr/bin/env python3
"""Reorganise the study BY BENCHMARK -> RESULTS_BY_BENCHMARK.md

x-axis = effective bpw (8*file_bytes/n_params, .wrapup/bpw_map.json) because the
nominal UD-Q2_K_XL label spans 2.76-5.04 bpw.  Code rows come from the DB with
protocol='multipl-e-raw-greedy-768'; n per language is taken from the summary files.
Every number names its run_tag.  Item-level CIs only.
"""
import collections
import glob
import json
import math
import os
import sqlite3

W = ".wrapup"
BPW = json.load(open(f"{W}/bpw_map.json"))
con = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)

# ---- n per language, from the summary files (mode over models) --------------
_LANGN = collections.defaultdict(list)
for f in glob.glob(f"{W}/*_summary.jsonl"):
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("lang") and r.get("n"):
            _LANGN[r["lang"]].append(r["n"])
LANG_N = {k: collections.Counter(v).most_common(1)[0][0] for k, v in _LANGN.items()}


def disp(m):
    return m.replace(".gguf", "").replace("Qwen_Qwen", "Qwen")


def tag_of(model, quant):
    r = con.execute("""SELECT run_tag FROM experiments WHERE model=? AND __quant=?
                       AND run_tag IS NOT NULL LIMIT 1""", (model, quant)).fetchone()
    return r[0] if r else "-"


def code_rows():
    """(model, quant) -> {lang: score} from the canonical greedy ladder."""
    g = collections.defaultdict(dict)
    for m, q, l, s in con.execute("""SELECT model,__quant,language,AVG(_score) FROM experiments
            WHERE bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768'
              AND run_tag IS NOT NULL
            GROUP BY 1,2,3"""):
        g[(m, q)][l] = s
    return g


def pooled(d):
    num = den = 0.0
    for l, s in d.items():
        n = LANG_N.get(l, 161)
        num += s * n
        den += n
    return (num / den, int(den)) if den else (None, 0)


def pooled_on(d, langs):
    num = den = 0.0
    for l in langs:
        if l in d:
            n = LANG_N.get(l, 161)
            num += d[l] * n
            den += n
    return (num / den, int(den)) if den else (None, 0)


def ci(a, n2, b, n3):
    """a, b are already rates; n2, n3 the item counts."""
    if not n2 or not n3:
        return None
    se = math.sqrt(a * (1 - a) / n2 + b * (1 - b) / n3)
    d = b - a
    return d, se, d - 1.96 * se, d + 1.96 * se


def f(x, d=4):
    return "-" if x is None else f"{x:.{d}f}"


def main():
    o = []
    A = o.append
    A("# 结果按 benchmark 重排")
    A("")
    A("横轴 = **有效 bpw = 8×文件字节/参数量**（解析 GGUF 头），因为标称档位不是比特数（§0）。")
    A("代码一律 `multipl-e-raw-greedy-768`；工具调用一律 native-FC；多轮一律 `bfcl-official-multiturn-temp0`。")
    A("CI 为 item 级。`[HARNESS]` = 输出格式/方言导致的假 0，不是数据点。")
    A("")

    # ---------------- §0
    A("## 0. 横轴修正：标称档位 ≠ 比特数")
    A("")
    A("| 模型 | 标称 | **有效 bpw** | GB |")
    A("|---|---|---|---|")
    seen = set()
    for m, q, fs in con.execute("""SELECT DISTINCT model,__quant,_file_size FROM experiments
                                   WHERE run_tag IS NOT NULL ORDER BY _file_size"""):
        if m in seen or m not in BPW:
            continue
        seen.add(m)
        A(f"| {disp(m)} | {q} | **{BPW[m]:.3f}** | {fs:.2f} |")
    A("")
    A("同一个 `UD-Q2_K_XL`：LFM2.5-8B-A1B 是 **2.76 bpw**，Nemotron-3-Nano-4B 是 **5.04 bpw**。")
    A("下文“Q2→Q3”因此都改读作**实际 bpw 的一段位移**，位移量每对模型不同。")
    A("")

    # ---------------- §1.1 code
    cr = code_rows()
    A("## 1.1 代码（MultiPL-E，raw，greedy）")
    A("")
    A("| 模型 | 档位 | **bpw** | pooled | n | cpp | py | java | js | rs | rb | run_tag |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|")
    rr = []
    for (m, q), d in cr.items():
        if m not in BPW:
            continue
        p, n = pooled(d)
        rr.append((BPW[m], m, q, p, n, d))
    for b, m, q, p, n, d in sorted(rr):
        A(f"| {disp(m)} | {q} | {b:.2f} | **{f(p)}** | {n} | " +
          " | ".join(f(d.get(l), 3) for l in ("cpp", "py", "java", "js", "rs", "rb")) +
          f" | {tag_of(m, q)} |")
    A("")

    # ---------------- §1.1b Q2->Q3 with CI
    A("### 1.1b 代码上 Q2→Q3 这一步（item 级 CI，按真实 bpw 位移）")
    A("")
    A("| 模型 | bpw 位移 | Δpooled | 95% CI | 显著 | run_tag |")
    A("|---|---|---|---|---|---|")
    fams = collections.defaultdict(dict)
    for (m, q), d in cr.items():
        base = m.split("-UD-Q")[0].split("-Q2_K")[0].split("-Q3_K")[0]
        fams[base][q] = (m, d)
    for base, qs in sorted(fams.items()):
        q2 = [q for q in qs if q.replace("UD-", "").startswith("Q2")]
        q3 = [q for q in qs if q.replace("UD-", "").startswith("Q3")]
        if not (q2 and q3):
            continue
        (m2, d2), (m3, d3) = qs[q2[0]], qs[q3[0]]
        p2, n2 = pooled(d2)
        p3, n3 = pooled(d3)
        r = ci(p2, n2, p3, n3)
        if not r:
            continue
        dd, se, lo, hi = r
        A(f"| {disp(m2)} | {BPW[m2]:.2f}→{BPW[m3]:.2f} (+{BPW[m3]-BPW[m2]:.2f}) | {dd:+.4f} | "
          f"[{lo:+.4f}, {hi:+.4f}] | {'**是**' if abs(dd) > 1.96*se else '否'} | {tag_of(m2,q2[0])} |")
    A("")

    # ---------------- §1.2 BFCL single-turn
    A("## 1.2 工具调用·单轮（BFCL v4，native-FC）")
    A("")
    cats = ["bfcl-irrelevance", "bfcl-multiple", "bfcl-parallel",
            "bfcl-parallel_multiple", "bfcl-simple_python"]
    g = collections.defaultdict(dict)
    for m, q, b, s in con.execute("""SELECT model,__quant,_bench,AVG(_score) FROM experiments
            WHERE bench_family='bfcl' AND protocol='bfcl-native-tools-nothink-greedy'
              AND run_tag IS NOT NULL GROUP BY 1,2,3"""):
        if b in cats:
            g[(m, q)][b[5:]] = s
    A("| 模型 | 档位 | **bpw** | irrelev | multiple | parallel | par_multi | simple_py | 均值 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for (m, q), d in sorted(g.items(), key=lambda kv: BPW.get(kv[0][0], 9)):
        v = [d.get(c[5:]) for c in cats]
        ok = [x for x in v if x is not None]
        A(f"| {disp(m)} | {q} | {BPW.get(m,float('nan')):.2f} | " +
          " | ".join(f(x) if x is not None else "-" for x in v) +
          f" | **{sum(ok)/len(ok):.4f}** |")
    A("")
    A("`[HARNESS]` granite-4.1-3b 的 Q2 行：live_parallel / live_parallel_multiple 恰 0.0000，")
    A("且 4 个需发调用的类别全 ≤0.02，而 irrelevance 0.99 —— native-FC 方言不匹配，非 Q2 低分证据。")
    A("")

    # ---------------- §1.3 multi-turn
    A("## 1.3 Agentic·多轮（BFCL-MT，temp0）")
    A("")
    gm = collections.defaultdict(dict)
    for m, q, b, s in con.execute("""SELECT model,__quant,_bench,AVG(_score) FROM experiments
            WHERE bench_family='bfcl-multiturn' AND run_tag IS NOT NULL GROUP BY 1,2,3"""):
        gm[(m, q)][b[5:]] = s
    A("| 模型 | 档位 | **bpw** | base | long_ctx | miss_func | miss_param |")
    A("|---|---|---|---|---|---|---|")
    for (m, q), d in sorted(gm.items(), key=lambda kv: BPW.get(kv[0][0], 9)):
        A(f"| {disp(m)} | {q} | {BPW.get(m,float('nan')):.2f} | " +
          " | ".join(f(d.get(c)) for c in
                     ("multi_turn_base", "multi_turn_long_context",
                      "multi_turn_miss_func", "multi_turn_miss_param")) + " |")
    A("")
    A("**多轮是量化最敏感的 benchmark**：2B 在 Q2 时 base/long_ctx/miss_func/miss_param 全部 **0.025/0.005/0.005/0.005**，")
    A("Q3 恢复到 0.185/0.111/0.080/0.105 —— 每个类别各自的天花板。")
    A("对比：同一模型在**代码**上 Q2→Q3 是 0.092→0.218（也有损但没归零）。")
    A("")

    # ---------------- §1.4 PPL
    A("## 1.4 PPL（同横轴，与跑分对照）")
    A("")
    pj = json.load(open("ppl_join.json"))
    A("| 模型 | 档位阶 | ppl | 代码 pass@1 |")
    A("|---|---|---|---|")
    for fam, v in pj.items():
        for lv in v["levels"]:
            A(f"| {fam} | {lv['level']} | {lv['ppl']:.4f} | {f(lv.get('pass_at_1'))} |")
    A("")

    # ---------------- §2 ternary
    A("## 2. Ternary / 亚 2-bit（单列，与常规量化放同一 bpw 轴）")
    A("")
    A("| 模型 | **bpw** | 代码 pooled | MT base | MT miss_func | MT miss_param | BFCL 单轮均值 |")
    A("|---|---|---|---|---|---|---|")
    tern = ["Ternary-Bonsai-1.7B-Q2_0_g64.gguf", "Ternary-Bonsai-4B-Q2_0_g64.gguf",
            "Ternary-Bonsai-8B-Q2_0_g64.gguf", "Ternary-Bonsai-27B-Q2_g64.gguf",
            "Bonsai-27B-Q1_0.gguf", "Qwen_Qwen3.5-35B-A3B-IQ1_M.gguf"]
    for m in tern:
        if m not in BPW:
            continue
        row = [d for (mm, q), d in cr.items() if mm == m]
        cp = pooled(row[0])[0] if row else None

        def mt(cat):
            r = con.execute("""SELECT AVG(_score) FROM experiments WHERE model=? AND _bench=?
                               AND run_tag IS NOT NULL""", (m, "bfcl-multi_turn_" + cat)).fetchone()
            return r[0]
        bs = con.execute("""SELECT AVG(_score) FROM experiments WHERE model=? AND
             bench_family='bfcl' AND _bench!='bfcl-live_irrelevance'""", (m,)).fetchone()[0]
        A(f"| {disp(m)} | **{BPW[m]:.3f}** | {f(cp)} | {f(mt('base'))} | {f(mt('miss_func'))} | "
          f"{f(mt('miss_param'))} | {f(bs)} |")
    A("")
    A("**Ternary-Bonsai-27B 在 2.26 bpw 上，多轮/工具调用全面达到或超过 3.7–5.4 bpw 的常规量化**；")
    A("但同一族的 `GLM-4.7-Flash-UD-TQ1_0`（2.23 bpw）在代码上只有它自己 Q2 的一半 → **配方特异**。")
    A("")

    # ---------------- §3 scheme
    A("## 3. 量化方案：迭代/imatrix(IQ) vs K-quant vs 厂商标签")
    A("")
    A("核心问题：**在真实 bpw / 真实文件大小相同时，换方案有没有用？**")
    A("")
    A("| 对比 | 基准 | 配置A | bpw | 配置B | bpw | **Δ = A−B** | 95% CI | 显著 | run_tag |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for base, a_q, b_q, tag in [("Qwen3.5-2B", "UD-IQ3_XXS", "UD-Q2_K_XL", "m50-imatrix-vs-k"),
                                ("Qwen3.5-4B", "UD-IQ3_XXS", "UD-Q2_K_XL", "m50-imatrix-vs-k")]:
        ma, mb = f"{base}-{a_q}.gguf", f"{base}-{b_q}.gguf"
        da = cr.get((ma, a_q)); db = cr.get((mb, b_q))
        if not (da and db):
            continue
        common = [l for l in da if l in db]          # match the language set
        pa, na = pooled_on(da, common); pb, nb = pooled_on(db, common)
        r = ci(pb, nb, pa, na)   # d = A(IQ) - B(K)
        A(f"| {base} imatrix vs K | 代码({'/'.join(sorted(common))}) | {a_q} | {BPW[ma]:.2f} | {b_q} | {BPW[mb]:.2f} | "
          f"{r[0]:+.4f} | [{r[2]:+.4f}, {r[3]:+.4f}] | {'**是**' if abs(r[0])>1.96*r[1] else '否'} | {tag} |")
    mv, mu = "Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf", "Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf"
    dv, du = cr.get((mv, "Q3_K_M")), cr.get((mu, "UD-Q3_K_XL"))
    if dv and du:
        common = [l for l in dv if l in du]
        pv, nv = pooled_on(dv, common); pu, nu = pooled_on(du, common)
        r = ci(pv, nv, pu, nu)   # vendor minus UD
        A(f"| 厂商 Q3_K_M vs UD-Q3_K_XL | 代码({'/'.join(sorted(common))}) | Q3_K_M | {BPW[mv]:.2f} | UD-Q3_K_XL | {BPW[mu]:.2f} | "
          f"{r[0]:+.4f} | [{r[2]:+.4f}, {r[3]:+.4f}] | {'**是**' if abs(r[0])>1.96*r[1] else '否'} | m37-vendor-matched-size |")
    A("")
    A("**方案 > 比特数的证据比原先报告的弱**：把语言集对齐后（cpp+py 两模型都是 322 题），")
    A("- 2B：IQ3_XXS(3.96bpw) 比 Q2_K_XL(4.11bpw) **高 +0.065，CI[+0.009,+0.121]，显著** —— 更小且更好；")
    A("- 4B：同方向 (+0.047) 但 **CI[−0.028,+0.121] 跨 0，不显著**。")
    A("原先“4/4 单元格全胜”是**按符号一致**记的，不是逐格显著；此处更正为 **2B 显著、4B 仅方向一致**。")
    A("**厂商标签本身无效**（Q3_K_M vs UD-Q3_K_XL 差 0.009，CI 跨 0）。")
    A("专家感知混合精度（m55，LFM2.5-8B-A1B）：专家 Q2_K+其余 Q5_K_M = **2.92 bpw / 0.1025**，")
    A("均匀 Q3_K_M = 3.88 bpw / 0.0807 → 更小且名义更好，但 Δ=+0.022 CI[-0.023,+0.066] **不显著**。")
    A("")

    # ---------------- §4 size
    A("## 4. 模型规模 × benchmark（固定档位）")
    A("")
    import sys as _s
    _s.path.insert(0, W)
    from gguf_params import gguf_params as _gp
    nparam = {}
    for m in BPW:
        try:
            nparam[m] = _gp(os.path.realpath("/home/z/hf/" + m))[0] / 1e9
        except Exception:
            pass
    A("| benchmark | 档位阶 | 模型（按参数量升序）| 参数量 B | **bpw** | 分数 |")
    A("|---|---|---|---|---|---|")
    for label, filt in [("代码", "bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768'"),
                        ("BFCL单轮", "bench_family='bfcl' AND protocol='bfcl-native-tools-nothink-greedy'"),
                        ("多轮base", "bench_family='bfcl-multiturn' AND _bench='bfcl-multi_turn_base'")]:
        g2 = collections.defaultdict(list)
        for m, s in con.execute(f"SELECT model,AVG(_score) FROM experiments WHERE {filt} AND run_tag IS NOT NULL GROUP BY 1"):
            g2[m].append(s)
        rows4 = sorted(((nparam.get(m, 0), m, sum(v) / len(v)) for m, v in g2.items()))
        for p, m, s in rows4:
            A(f"| {label} | 混杂 | {disp(m)} | {p:.2f} | {BPW.get(m, float('nan')):.2f} | {s:.4f} |")
    A("")
    A("**规模与分数在代码上基本单调，但有两个明确反例**：gemma-4-26B-A4B（25.2B，Q2/Q3 只有 0.04）")
    A("和 gemma-4-12b-it（11.9B，0.00~0.006，`[HARNESS]`）在**参数更多时分数低于 3B 的 Llama/granite**。")
    A("所以“越大越好”在**同族内**成立，跨族不成立——训练质量与分词器的影响大于参数量。")
    A("")

    # ---------------- §5 KV
    A("## 5. KV 量化 × benchmark")
    A("")
    A("数据只有 **Qwen3.5-2B / 代码 / cpp** 一格（m30），**没有任何其他 benchmark 的 KV 数据**——")
    A("因此**不能**对 KV 做跨 benchmark 断言，以下是全部证据：")
    A("")
    A("| ctx | KV f16/f16 | f16/q8_0 | q8_0/f16 | q8_0/q8_0 |")
    A("|---|---|---|---|---|")
    for cx in (2048, 16384, 49152):
        cells = []
        for kv in (('f16', 'f16'), ('f16', 'q8_0'), ('q8_0', 'f16'), ('q8_0', 'q8_0')):
            r = con.execute("""SELECT AVG(_score) FROM experiments WHERE run_tag='m30-kv-ctx'
                 AND _bench='humaneval-cpp' AND protocol LIKE ? AND protocol LIKE ?""",
                           (f"%ctx={cx},%", f"%kv={kv[0]}/{kv[1]}%")).fetchone()[0]
            cells.append("-" if r is None else f"{r:.4f}")
        A(f"| {cx} | " + " | ".join(cells) + " |")
    A("")
    A("**同一 ctx 下 4 种 KV 配置几乎逐格相同** → KV 量化无信号。分数真正崩掉来自 **ctx/padding**")
    A("（2048→16384 就 0.067→0.000）。注意每格 **n=1**，证据强度弱。prompt 被填充到 ~15k/48k token 本身就会毁掉答案。")
    A("")
    A("flash-attn（m44）：Q3 上 `faon_f16` 与 `faoff_f16` **逐字节相同**，是**非操作**；Q2 上才不同——")
    A("所以 m29 的 `-fa` “null”是**非测量**，不是结果。")
    A("")

    # ---------------- §6 sampling
    A("## 6. 采样参数 × benchmark")
    A("")
    A("数据只有 **Qwen3.5-2B / 代码（cpp+py）**——同样**无法**跨 benchmark 断言。")
    A("")
    A("| 轴 | 取值 | cpp | py | run_tag |")
    A("|---|---|---|---|---|")
    tc = {}
    for t, l, s in con.execute("""SELECT temp,language,AVG(_score) FROM experiments
         WHERE run_tag='m27-sampling' GROUP BY 1,2"""):
        tc.setdefault(t, {})[l] = s
    for t in sorted(tc):
        A(f"| temp | {t} | {tc[t].get('cpp',0):.4f} | {tc[t].get('py',0):.4f} | m27-sampling |")
    tk = {}
    for k, l, s in con.execute("""SELECT top_k,language,AVG(_score) FROM experiments
         WHERE run_tag='m31-topk' GROUP BY 1,2"""):
        tk.setdefault(k, {})[l] = s
    for k in sorted(tk, key=lambda x: int(x)):
        A(f"| top_k | {k} | {tk[k].get('cpp',0):.4f} | {tk[k].get('py',0):.4f} | m31-topk |")
    A("")
    A("**top_k ≥ 20 完全相同（0.1718/0.2484，逐格一致）**，只有 K=1 不同（cpp 更高、py 更低，双向）；")
    A("温度改变绝对分数（0.3 最好）但不改变量化结论。**两者都只在代码上测过。**")
    A("")

    open("RESULTS_BY_BENCHMARK.md", "w").write("\n".join(o) + "\n")
    print("wrote RESULTS_BY_BENCHMARK.md:", len(o), "lines")


if __name__ == "__main__":
    main()
