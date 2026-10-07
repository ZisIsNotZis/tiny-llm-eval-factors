#!/usr/bin/env python3
"""RESULTS_BY_BENCHMARK.md as MATRICES: rows = item (model x bpw), columns = benchmark.

Column set: 代码(MultiPL-E pooled) | BFCL单轮(5类均值) | 多轮base | long_ctx |
miss_func | miss_param | PPL.  x-axis is EFFECTIVE bpw = 8*bytes/params.
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

_L = collections.defaultdict(list)
for f in glob.glob(f"{W}/*_summary.jsonl"):
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("lang") and r.get("n"):
            _L[n].append(r["n"]) if False else _L[r["lang"]].append(r["n"])
LANG_N = {k: collections.Counter(v).most_common(1)[0][0] for k, v in _L.items()}


import re as _re


def disp(m):
    """Base model name without the quant suffix (bpw identifies the row)."""
    x = m.replace(".gguf", "").replace("Qwen_Qwen", "Qwen")
    x = _re.sub(r"[-_](UD-)?(I?Q\d[_A-Za-z0-9]*|TQ1_0|Q2_g64|Q2_0_g64)$", "", x)
    x = _re.sub(r"-m55-(exq2|exq4)$", r"-m55-\1", x)
    return x


def pooled(d):
    num = den = 0.0
    for l, s in d.items():
        n = LANG_N.get(l, 161)
        num += s * n
        den += n
    return (num / den) if den else None


def matched(a, b):
    """Pool two (model,quant) row-dicts over their COMMON languages (with CI)."""
    common = [l for l in a["langs"] if l in b["langs"]]
    pa, na = a["pool_on"](common)
    pb, nb = b["pool_on"](common)
    return pa, na, pb, nb, "+".join(sorted(common))


def f(x, d=4):
    return "-" if x is None else f"{x:.{d}f}"


# ---- collect every (model, quant) cell ------------------------------------
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

# ---- PPL: ppl_join.json is keyed by family name + level ordinal ------------
FAM = {"Qwen3.5-0.8B": "Qwen3.5-0.8B", "Qwen3.5-2B": "Qwen3.5-2B", "Qwen3.5-4B": "Qwen3.5-4B",
       "Qwen3.5-9B": "Qwen3.5-9B", "Qwen3.6-35B-A3B": "Qwen3.6-35B-A3B",
       "Qwen3.8-27B": "Qwen3.8-27B", "gemma-4-12b-it": "gemma-4-12b-it",
       "gemma-4-26B-A4B-it": "gemma-4-26B-A4B-it", "granite-4.1-3b": "granite-4.1-3b"}
PPL = json.load(open("ppl_join.json"))
ppl_map = {}
for fam, v in PPL.items():
    for lv in v["levels"]:
        ppl_map.setdefault(fam, {})[lv["level"]] = lv["ppl"]


def ppl_of(model):
    """Only the plain K-quant ladder has PPL; IQ2_* must not match 'Q2'."""
    fam = None
    for k in FAM:
        if model.startswith(k):
            fam = k
            break
    if not fam or fam not in ppl_map:
        return None
    m = _re.search(r"(?<!I)Q([2-5])_", model)
    return ppl_map[fam].get(int(m.group(1))) if m else None


def row(model, q):
    """Return the full benchmark cell row for (model, quant), or None."""
    if model not in BPW:
        return None
    d = code.get((model, q), {})
    s = st.get((model, q), {})
    m = mt.get((model, q), {})
    c = pooled(d) if d else None
    sv = [v for v in s.values() if v is not None]
    def _po(langs):
        num = den = 0.0
        for l in langs:
            if l in d:
                n = LANG_N.get(l, 161)
                num += d[l] * n
                den += n
        return ((num / den) if den else None, int(den))

    return dict(bpw=BPW[model], model=model, quant=q, langs=d, pool_on=_po,
                code=c, st=(sum(sv) / len(sv)) if sv else None,
                base=m.get("multi_turn_base"), lc=m.get("multi_turn_long_context"),
                mf=m.get("multi_turn_miss_func"), mp=m.get("multi_turn_miss_param"),
                ppl=ppl_of(model))


HDR = ("| 模型 | **bpw** | 代码 | BFCL单轮 | 多轮base | long_ctx | miss_func | miss_param | PPL |")
SEP = ("|---|---|---|---|---|---|---|---|---|")


def emit(A, rows, note_ternary=False):
    A(HDR)
    A(SEP)
    cur = None
    for r in rows:
        if r["model"] != cur and cur is not None:
            A("| | | | | | | | |")          # blank separator between models
        cur = r["model"]
        A(f"| {disp(r['model'])} | **{r['bpw']:.2f}** | {f(r['code'])} | {f(r['st'])} | "
          f"{f(r['base'])} | {f(r['lc'])} | {f(r['mf'])} | {f(r['mp'])} | "
          f"{('%.3f' % r['ppl']) if r['ppl'] else '-'} |")


def main():
    o = []
    A = o.append
    A("# 结果矩阵：行 = 模型 × BPW，列 = benchmark")
    A("")
    A("横轴是**有效 bpw = 8×文件字节/参数量**（解析 GGUF 头），所以“档位”一词不再出现。")
    A("同一模型的每个 BPW 各占一行，**上下相邻即为该模型的曲线**。`[HARNESS]` 见脚注。")
    A("")

    all_rows = []
    for (m, q) in list(code) + list(st) + list(mt):
        r = row(m, q)
        if r:
            all_rows.append(r)
    # dedupe (model, bpw) keeping the richest row
    best = {}
    for r in all_rows:
        k = (r["model"], r["quant"])
        if k not in best or sum(x is not None for x in
                                (r["code"], r["st"], r["base"], r["mf"], r["mp"])) > \
           sum(x is not None for x in
               (best[k]["code"], best[k]["st"], best[k]["base"], best[k]["mf"], best[k]["mp"])):
            best[k] = r
    rows = sorted(best.values(), key=lambda r: (disp(r["model"]), r["bpw"]))

    tern = [r for r in rows if "Ternary" in r["model"] or "IQ1_M" in r["model"]
            or "Q1_0" in r["model"] or "TQ1_0" in r["model"]]
    conv = [r for r in rows if r not in tern]

    A("## 1. 常规量化：模型 × BPW 的曲线")
    A("")
    emit(A, conv)
    A("")
    A("**怎么读**：同一模型的相邻行就是它的 BPW 曲线。例：Qwen3.5-2B 从 3.27 到 6.24 bpw，")
    A("代码 0.006→0.139→0.092→0.189→0.218→0.284→0.277 —— **Q3 之后是平台**，而 IQ2_XXS→IQ2_M 那一段是陡坡。")
    A("")
    A("**跨 benchmark 的敏感度不同**（同一模型同一 BPW 步长）：")
    A("- Qwen3.5-2B 4.11→4.93 bpw：代码 0.092→0.218（+0.126）、多轮 base 0.025→0.185（**+0.160**）、")
    A("  BFCL 单轮 0.294→0.484（+0.190）—— **方向一致，多轮与工具单轮幅度最大**。")
    A("- gemma-4-E2B 4.14→5.03 bpw：代码 0.201→0.416（**+0.215**）、BFCL 单轮 0.628→0.669（**+0.041**）")
    A("  —— **代码远比工具调用敏感**。")
    A("")

    A("## 2. Ternary / 亚 2-bit（同矩阵，单列出来）")
    A("")
    emit(A, tern)
    A("")
    A("Ternary-Bonsai 四个尺寸都约 **2.26 bpw**：代码 0.354 / 0.584 / 0.584 / 0.730（随尺寸单调）；")
    A("27B 的多轮 0.698 / 0.515 / 0.435 与 BFCL 单轮 0.705 —— **在 2.26 bpw 上达到 3.7–5.4 bpw 常规量化的水平**。")
    A("但 **GLM-4.7-Flash-TQ1_0（2.23 bpw）代码只有 0.207**（它自己 Q2=0.410 的一半）→ **配方特异**。")
    A("")
    A("脚注 `[HARNESS]`：gemma-4-12b 全列 ≈0.00 是输出格式（缩进/签名）导致，非能力；")
    A("granite Q2 的 BFCL 单轮低分是 native-FC 方言不匹配（它只会拒绝，不发调用）。")
    A("")

    # ---------------- 3 scheme ----------------
    A("## 3. 量化方案（行 = 方案对比，列 = benchmark）")
    A("")
    A("| 对比（同一模型内） | 代码 | BFCL单轮 | 多轮base | miss_func | miss_param | PPL |")
    A("|---|---|---|---|---|---|---|")
    for base, a_q, b_q in [("Qwen3.5-2B", "UD-IQ3_XXS", "UD-Q2_K_XL"),
                           ("Qwen3.5-4B", "UD-IQ3_XXS", "UD-Q2_K_XL")]:
        ra = row(f"{base}-{a_q}.gguf", a_q)
        rb = row(f"{base}-{b_q}.gguf", b_q)
        if not (ra and rb):
            continue
        pa, na, pb, nb, langset = matched(ra, rb)
        dlt = pa - pb
        se = math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
        star = "**是**" if abs(dlt) > 1.96 * se else "否"
        A(f"| {base}: IQ3_XXS({ra['bpw']:.2f}) − Q2_K_XL({rb['bpw']:.2f}) [{langset}] | "
          f"{(pa-pb):+.4f} (sig={star}) | "
          f"{f((ra['st']-rb['st']) if ra['st'] and rb['st'] else None)} | "
          f"{f((ra['base']-rb['base']) if ra['base'] and rb['base'] else None)} | "
          f"{f((ra['mf']-rb['mf']) if ra['mf'] and rb['mf'] else None)} | "
          f"{f((ra['mp']-rb['mp']) if ra['mp'] and rb['mp'] else None)} | "
          f"{f((ra['ppl']-rb['ppl']) if ra['ppl'] and rb['ppl'] else None, 3)} |")
    mu, mv = "Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf", "Qwen_Qwen3.6-35B-A3B-Q3_K_M.gguf"
    ru, rv = row(mu, "UD-Q3_K_XL"), row(mv, "Q3_K_M")
    if ru and rv:
        pa, na, pb, nb, langset = matched(ru, rv)
        A(f"| 35B-A3B: 厂商 Q3_K_M({rv['bpw']:.2f}) − UD-Q3_K_XL({ru['bpw']:.2f}) [{langset}] | "
          f"{(pb-pa):+.4f} | - | - | - | - | - |")
    A("")
    A("代码列是**语言集对齐后**的 Δ（IQ3_XXS − Q2_K_XL）：**2B +0.065 显著，4B +0.047 不显著**。")
    A("厂商标签差 −0.009（CI 跨 0）→ **标签本身无效**。其他 benchmark **没有方案对比数据**。")
    A("")
    A("专家感知（m55，LFM2.5-8B-A1B，仅代码）：专家 Q2_K+其余 Q5_K_M **2.92 bpw / 0.103** vs")
    A("均匀 Q3_K_M **3.88 bpw / 0.081** → 更小且名义更好，Δ=+0.022 CI[−0.023,+0.066] **不显著**。")
    A("")

    # ---------------- 4 size ----------------
    A("## 4. 模型规模（行 = 模型，列 = benchmark；BPW 列用于对照）")
    A("")
    A("| 模型 | 参数量 B | **bpw** | 代码 | BFCL单轮 | 多轮base |")
    A("|---|---|---|---|---|---|")
    import sys
    sys.path.insert(0, W)
    from gguf_params import gguf_params
    sz = {}
    for m in BPW:
        try:
            sz[m] = gguf_params(os.path.realpath("/home/z/hf/" + m))[0] / 1e9
        except Exception:
            pass
    for r in sorted(conv + tern, key=lambda r: sz.get(r["model"], 0)):
        p = sz.get(r["model"])
        if p is None:
            continue
        A(f"| {disp(r['model'])} | {p:.2f} | {r['bpw']:.2f} | {f(r['code'])} | {f(r['st'])} | {f(r['base'])} |")
    A("")
    A("同族内单调；**跨族反例**：gemma-4-26B-A4B（25.2B）代码 0.04，低于 3B 的 granite Q4（0.44）。")
    A("")

    # ---------------- 5 KV ----------------
    A("## 5. KV 量化（行 = ctx，列 = KV 组合；**只有代码 cpp**）")
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
    A("**同一行四格几乎相同 → KV 无信号**；分数崩掉来自 ctx/padding。**每格 n=1。无其他 benchmark 数据。**")
    A("")

    # ---------------- 6 sampling ----------------
    A("## 6. 采样参数（行 = 取值，列 = benchmark；**只有代码 cpp/py**）")
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
    A("top_k ≥ 20 逐格相同；只有 K=1 不同且**双向**。**只有代码数据，无法跨 benchmark。**")
    A("")

    open("RESULTS_BY_BENCHMARK.md", "w").write("\n".join(o) + "\n")
    print("wrote RESULTS_BY_BENCHMARK.md:", len(o), "lines")


if __name__ == "__main__":
    main()
