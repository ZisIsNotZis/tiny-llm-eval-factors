#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量化 × 基准分数：逐项报告（全中文，总分总，每项配图）。

结构：
  总 —— 这个研究是什么
  分 —— 每一项研究一节：中文标题 + 该研究说明 + X/Y 原始数据表 + 该研究的图
  总 —— 显著性回顾（哪些显著、哪些测不出、哪些未测）

数据：experiments.sqlite（去重后）。表格 A–H 由 RESULTS_BY_COMPARISON.md 解析并翻译表头；
新增两轴（量化感知训练、GSQ-RCO）由 DB 现算。
运行：python3 make_report.py
"""
from __future__ import annotations
import base64, html, json, os, re, sqlite3, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, ".")
from bpw_sensitivity import BENCH, load  # noqa

_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
try:
    fm.fontManager.addfont(_CJK)
    plt.rcParams["font.sans-serif"] = [fm.FontProperties(fname=_CJK).get_name(), "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
except Exception:
    pass

CON = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)
BENCH_ORDER = [b for b, _, _ in BENCH]
LABCAT = {"humaneval-plus": "代码HE+", "mbpp-plus": "代码MBPP+", "mmlu": "知识MMLU",
          "arc_challenge": "科学ARC", "truthfulqa_mc2": "真实TQA", "gsm8k": "推理GSM8K",
          "ifeval": "指令IFEval"}
CANON = [(b, proto) for b, _k, proto in BENCH]
AX = json.load(open(".wrapup/axes_findings.json"))
FIGDIR = "figures/report"
os.makedirs(FIGDIR, exist_ok=True)

# 中文表头翻译
HDR = {
    "model family (all else equal)": "模型家族（其余固定）",
    "family @ recipe (all else equal)": "家族 @ 配方（其余固定）",
    "model @ bpw band (all else equal)": "模型 @ 位宽区间（其余固定）",
    "model (all else equal)": "模型（其余固定）",
    "model @bpw · ctx (all else equal)": "模型 @位宽 · 上下文（其余固定）",
    "model · varied axis (all else equal)": "模型 · 变化轴（其余固定）",
    "model · ctx (all else equal)": "模型 · 上下文（其余固定）",
    "effective BPW": "有效位宽",
    "model size": "模型规模",
    "quant scheme (vendor)": "量化方案（厂商）",
    "expert / non-expert recipe": "专家 / 非专家层配方",
    "KV type K/V": "KV 类型 K/V",
    "value": "取值",
    "spec_draft_n_max": "草稿深度",
    "thinking": "思考",
    "code": "代码", "long-ctx": "长上下文", "prose": "散文", "code-256": "代码(256)",
}


def zh(s):
    s = s.strip()
    return HDR.get(s, s)


def num(s):
    m = re.search(r"[-+]?\d+\.?\d*", s.replace("−", "-"))
    return float(m.group()) if m else None


def numf(s):
    v = num(s)
    return v if v is not None else float("nan")


def size_num(s):
    m = re.search(r"(\d+\.?\d*)\s*B", s)
    if not m:
        return None
    v = float(m.group(1))
    if s.startswith("E") or "E2B" in s or "E4B" in s:
        return v
    return v


def md_inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


# ---------- 解析 RESULTS_BY_COMPARISON.md ----------
def parse_md():
    txt = open("RESULTS_BY_COMPARISON.md").read().splitlines()
    secs, cur, buf = [], None, []
    for ln in txt:
        if ln.startswith("## "):
            if cur:
                secs.append((cur, buf))
            cur, buf = ln[3:].strip(), []
        elif cur:
            buf.append(ln)
    if cur:
        secs.append((cur, buf))
    out = []
    for title, body in secs:
        tables, t = [], None
        for ln in body:
            if ln.strip().startswith("|"):
                if t is None:
                    t = []
                t.append(ln)
            else:
                if t:
                    tables.append(t); t = None
        if t:
            tables.append(t)
        out.append((title, tables))
    return out


def table_rows(tbl):
    rows = []
    for i, ln in enumerate(tbl):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if i == 1 and all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows


# ---------- 图 ----------
def save(fig, name):
    p = f"{FIGDIR}/{name}.png"
    fig.tight_layout()
    fig.savefig(p, dpi=135, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_slopes():
    data = load(); fam = {}
    for (f, b), pts in data.items():
        k = sorted(pts)
        if len(k) >= 2 and k[-1] - k[0] >= 0.05:
            fam.setdefault(f, {})[b] = (pts[k[-1]][0] - pts[k[0]][0]) / (k[-1] - k[0])
    stat = []
    for b in BENCH_ORDER:
        v = [f[b] for f in fam.values() if b in f]
        if v:
            stat.append((b, float(np.median(v))))
    stat.sort(key=lambda x: -x[1])
    zhb = {"humaneval-plus": "代码HE+", "mbpp-plus": "代码MBPP+", "mmlu": "知识MMLU",
           "arc_challenge": "科学ARC", "truthfulqa_mc2": "真实TruthfulQA", "gsm8k": "推理GSM8K", "ifeval": "指令IFEval"}
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([zhb[b] for b, _ in stat], [s for _, s in stat], color="#c0392b")
    for i, (_, s) in enumerate(stat):
        ax.text(i, s + .003, f"{s:.3f}", ha="center", fontsize=10)
    ax.set_ylabel("每 +1 位宽（bpw）的分数变化")
    ax.set_title("同一个量化步长，在不同基准上造成的损失")
    ax.grid(axis="y", alpha=.25)
    return save(fig, "A_slopes")


def fig_size(table):
    rows = table_rows(table)
    hdr = rows[0]
    benches = [i for i, c in enumerate(hdr) if any(k in c for k in ("HumanEval+", "MMLU", "GSM8K"))]
    series = {}
    for r in rows[1:]:
        if r[0].startswith("**Σ") or len(r) <= max(benches):
            continue
        key = r[0]
        sz = size_num(r[1])
        if sz is None:
            continue
        series.setdefault(key, []).append((sz, [numf(r[i]) for i in benches]))
    fig, axes = plt.subplots(1, len(benches), figsize=(5 * len(benches), 4), squeeze=False)
    for j, bi in enumerate(benches):
        ax = axes[0][j]
        for key, pts in series.items():
            pts = sorted(pts)
            ax.plot([p[0] for p in pts], [p[1][j] for p in pts], "-o", label=key, lw=1.3, ms=5)
        ax.set_title(hdr[bi].replace("**", ""))
        ax.set_xlabel("参数量（B）"); ax.grid(alpha=.25)
    axes[0][0].set_ylabel("分数")
    axes[0][-1].legend(fontsize=7, loc="best")
    fig.suptitle("同量化配方下，模型规模与分数的关系（每个系列=一个配方）")
    return save(fig, "B_size")


def fig_moe(table):
    rows = table_rows(table)
    hdr = rows[0]
    benches = [i for i, c in enumerate(hdr) if c.startswith("**") and "MultiPL-E" not in c and c != "**"]
    labels, data = [], []
    for r in rows[1:]:
        if r[0].startswith("**Σ"):
            continue
        labels.append(r[1].replace("·", "\n"))
        data.append([numf(r[i]) for i in benches])
    data = np.array(data)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = np.arange(len(labels)); w = .18
    for k, bi in enumerate(benches):
        ax.bar(x + (k - len(benches) / 2) * w, data[:, k], w, label=hdr[bi].replace("**", ""))
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("分数"); ax.legend(fontsize=8); ax.grid(axis="y", alpha=.25)
    ax.set_title("MoE 逐层比特分配：同权重，只换“哪些层拿低比特”")
    return save(fig, "D_moe")


def fig_kv(table):
    rows = table_rows(table)
    hdr = rows[0]
    benches = [i for i, c in enumerate(hdr) if c.startswith("**") and c != "**" and "MultiPL-E" not in c]
    kv = []
    for r in rows[1:]:
        if len(r) > len(hdr) or r[0].startswith("**Σ") or "ctx8192" not in r[0]:
            continue
        v = r[1]
        if v in ("f16/f16", "q8_0/q8_0", "q4_0/q4_0"):
            kv.append((v, [numf(r[i]) for i in benches]))
    if not kv:
        return None
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(benches)); w = .25
    for k, (v, vals) in enumerate(kv):
        ax.bar(x + (k - 1) * w, vals, w, label=v)
    ax.set_xticks(x); ax.set_xticklabels([hdr[i].replace("**", "") for i in benches])
    ax.set_ylabel("分数"); ax.legend(); ax.grid(axis="y", alpha=.25)
    ax.set_title("KV-Cache 量化：f16 / q8_0 / q4_0")
    return save(fig, "E_kv")


def fig_speed(table):
    rows = table_rows(table)
    hdr = rows[0]
    cols = [i for i, c in enumerate(hdr) if c.startswith("**")]
    series = {}
    for r in rows[1:]:
        if r[0].startswith("**Σ"):
            continue
        model = r[0].split(" · ")[0]
        d = num(r[1])
        vals = [numf(r[i]) for i in cols]
        if d is None:
            continue
        series.setdefault(model, []).append((d, vals))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for model, pts in series.items():
        pts = sorted(pts)
        ax.plot([p[0] for p in pts], [p[1][-1] for p in pts], "-o", label=model, lw=1.3, ms=5)
    ax.set_xlabel("草稿深度"); ax.set_ylabel("每秒生成 token（最后一个场景）")
    ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("投机解码：草稿深度对速度的影响")
    return save(fig, "G1_speed")


def fig_specq(table):
    rows = table_rows(table); hdr = rows[0]
    he = next((i for i, c in enumerate(hdr) if "HumanEval" in c), None)
    mm = next((i for i, c in enumerate(hdr) if "MMLU" in c), None)
    series = {}
    for r in rows[1:]:
        if r[0].startswith("**Σ"):
            continue
        model = r[0].split(" · ")[0]
        d = num(r[1])
        if d is None:
            continue
        series.setdefault(model, []).append((d, numf(r[he]) if he is not None and len(r) > he else np.nan,
                                             numf(r[mm]) if mm is not None and len(r) > mm else np.nan))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for model, pts in series.items():
        pts = sorted(pts)
        axes[0].plot([p[0] for p in pts], [p[1] for p in pts], "-o", label=model, ms=4)
        axes[1].plot([p[0] for p in pts], [p[2] for p in pts], "-o", label=model, ms=4)
    axes[0].set_title("HumanEval（代码）"); axes[1].set_title("MMLU（知识，逐位相同）")
    for a in axes:
        a.set_xlabel("草稿深度"); a.grid(alpha=.25); a.set_ylabel("分数")
    axes[1].legend(fontsize=7)
    fig.suptitle("投机解码：草稿深度对分数的影响")
    return save(fig, "G2_quality")


def fig_thinking(table):
    rows = table_rows(table)
    hdr = rows[0]
    gi = next((i for i, c in enumerate(hdr) if "GSM8K" in c), None)
    series = {}
    for r in rows[1:]:
        if r[0].startswith("**Σ") or gi is None:
            continue
        model = r[0]; mode = r[1]
        v = num(r[gi])
        if v is None:
            v = 0.0
        modek = "on" if ("on" in mode or "开" in mode) else "off"
        series.setdefault(model, {})[modek] = v
    models = [m for m in series if "on" in series[m] and "off" in series[m]]
    if not models:
        return None
    off = [series[m]["off"] for m in models]
    on = [series[m]["on"] for m in models]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = np.arange(len(models)); w = .4
    ax.bar(x - w / 2, off, w, label="思考关")
    ax.bar(x + w / 2, on, w, label="思考开", color="#c0392b")
    ax.set_xticks(x); ax.set_xticklabels([m.replace(".gguf", "") for m in models], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("GSM8K 分数"); ax.legend(); ax.grid(axis="y", alpha=.25)
    ax.set_title("思考开关对 GSM8K 的影响")
    return save(fig, "H_thinking")


def fig_scheme():
    labels = ["2B\nIQ3−Q2", "4B\nIQ3−Q2", "合并\n(4/4 为正)", "厂商\nbartowski−unsloth"]
    d = [0.065, 0.047, 0.056, 0.009]
    lo = [0.009, -0.028, 0.008, -0.058]
    hi = [0.121, 0.121, 0.104, 0.077]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    colors = ["#c0392b" if (l > 0 or h < 0) else "#95a5a6" for l, h in zip(lo, hi)]
    ax.bar(labels, d, color=colors)
    ax.errorbar(labels, d, yerr=[[d[i] - lo[i] for i in range(4)], [hi[i] - d[i] for i in range(4)]],
                fmt="none", ecolor="#333", capsize=5)
    ax.axhline(0, color="#333", lw=.8)
    ax.set_ylabel("分数差（A−B）")
    ax.set_title("同文件大小下：换方案有差，换厂商没差")
    ax.grid(axis="y", alpha=.25)
    return save(fig, "C_scheme")


def fig_sampling(table):
    rows = table_rows(table); hdr = rows[0]
    mi = next((i for i, c in enumerate(hdr) if "MultiPL-E" in c), None)
    if mi is None:
        return None
    temp, topk = {}, {}
    for r in rows[1:]:
        if r[0].startswith("**Σ") or len(r) <= mi:
            continue
        if "温度" in r[0] or "temperature" in r[0]:
            axis = "temp"
        elif "top_k" in r[0]:
            axis = "topk"
        else:
            continue
        v = num(r[1]); sc = numf(r[mi])
        if v is None:
            continue
        (temp if axis == "temp" else topk)[round(v, 3)] = sc
    fig, ax = plt.subplots(figsize=(8, 4.4))
    if temp:
        k = sorted(temp); ax.plot([str(x) for x in k], [temp[x] for x in k], "-o", label="温度（2B, MultiPL-E）")
    if topk:
        k = sorted(topk); ax.plot([str(x) for x in k], [topk[x] for x in k], "-s", label="top_k（2B, MultiPL-E）")
    ax.set_xlabel("取值"); ax.set_ylabel("MultiPL-E 通过率")
    ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("采样参数对代码分数的影响")
    return save(fig, "F_sampling")


def raw_scores(tag):
    out = {}
    for b, proto in CANON:
        r = CON.execute("SELECT _score,n_items FROM experiments WHERE run_tag=? AND protocol=? AND _bench=?",
                        (tag, proto, b)).fetchone()
        out[b] = (r[0], r[1]) if r and r[0] is not None else None
    return out


def cellmd(sc, b):
    if not sc or sc.get(b) is None:
        return "—"
    v, n = sc[b]
    return f"{v:.4f} ({n})"


def qat_tables():
    pairs = AX["axis_1_6_qat"]["pairs"]
    hdr = ["系列", "文件", "bpw"] + [LABCAT[b] for b in BENCH_ORDER]
    t1 = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for p in pairs:
        for which, tag, bpw in (("QAT", p["tags"][0], p["bpw_qat"]), ("原生", p["tags"][1], p["bpw_native"])):
            sc = raw_scores(tag)
            t1.append("| " + " | ".join([f"{p['label']} {p['recipe']} {which}", tag, f"{bpw:.3f}"]
                                          + [cellmd(sc, b) for b in BENCH_ORDER]) + " |")
    hdr2 = ["系列"] + [LABCAT[b] + " Δ" for b in BENCH_ORDER]
    t2 = ["| " + " | ".join(hdr2) + " |", "|" + "---|" * len(hdr2)]
    for p in pairs:
        cells = []
        for b in BENCH_ORDER:
            c = p["deltas"].get(b)
            cells.append("-" if c is None else f"{c['delta']:+.4f} [{c['ci_lo']:+.3f},{c['ci_hi']:+.3f}]")
        t2.append("| " + " | ".join([f"{p['label']} {p['recipe']}"] + cells) + " |")
    return [t1, t2]


def gsq_tables():
    d = AX["axis_1_5_gsq_rco"]
    hdr = ["系列", "文件", "bpw"] + [LABCAT[b] for b in BENCH_ORDER]
    t1 = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for r in (d.get("native_ladder") or []):
        sc = raw_scores(r.get("tag", ""))
        t1.append("| " + " | ".join(["原生 " + r.get("label", ""), r.get("tag", ""), f"{r.get('bpw',0):.3f}"]
                                     + [cellmd(sc, b) for b in BENCH_ORDER]) + " |")
    gbpw = {"GSQ-RCO IQ3_XXS": 3.058, "GSQ-RCO IQ3_S": 3.549}
    for k, v in (d.get("quants") or {}).items():
        cells = []
        for b in BENCH_ORDER:
            g = v.get(b, {}).get("gsq") if b in v else None
            cells.append("—" if g is None else f"{g:.4f}")
        t1.append("| " + " | ".join([k, "ISAT-DASLab", f"{gbpw.get(k,0):.3f}"] + cells) + " |")
    hdr2 = ["系列", "基准", "Δ 最近原生", "95% 区间", "Δ 插值原生", "95% 区间"]
    t2 = ["| " + " | ".join(hdr2) + " |", "|" + "---|" * len(hdr2)]
    for k, v in (d.get("quants") or {}).items():
        for b in BENCH_ORDER:
            if b not in v:
                continue
            nr = v[b].get("nearest") or {}; ip = v[b].get("interp") or {}
            def c2(c):
                return ["-", "-"] if not c else [f"{c['delta']:+.4f}", f"[{c['ci_lo']:+.4f},{c['ci_hi']:+.4f}]"]
            t2.append("| " + " | ".join([k, LABCAT[b]] + c2(nr) + c2(ip)) + " |")
    return [t1, t2]


def fig_qat():
    pairs = AX["axis_1_6_qat"]["pairs"]
    zhb = {"humaneval-plus": "代码HE+", "mbpp-plus": "代码MBPP+", "mmlu": "知识MMLU",
           "arc_challenge": "科学ARC", "truthfulqa_mc2": "真实TQA", "gsm8k": "推理GSM8K", "ifeval": "指令IFEval"}
    fig, axes = plt.subplots(1, len(pairs), figsize=(3.6 * len(pairs), 4.2), squeeze=False)
    for ax, p in zip(axes[0], pairs):
        bs = [b for b in BENCH_ORDER if p["deltas"].get(b)]
        vals = [p["deltas"][b]["delta"] for b in bs]
        sig = [(p["deltas"][b]["ci_lo"] > 0 or p["deltas"][b]["ci_hi"] < 0) for b in bs]
        ax.bar(range(len(bs)), vals, color=["#c0392b" if s else "#95a5a6" for s in sig])
        ax.axhline(0, color="#333", lw=.8)
        ax.set_xticks(range(len(bs))); ax.set_xticklabels([zhb[b] for b in bs], rotation=60, ha="right", fontsize=7)
        ax.set_title(f"{p['label']}\n{p['recipe']}", fontsize=9)
        ax.grid(axis="y", alpha=.25)
        if ax is axes[0][0]:
            ax.set_ylabel("QAT − 原生 的分数差")
    fig.suptitle("量化感知训练 vs 原生（红=95%区间不跨0）")
    return save(fig, "QAT")


def fig_gsq():
    d = AX["axis_1_5_gsq_rco"]
    nl = d.get("native_ladder") or []
    fig, ax = plt.subplots(figsize=(9, 4.8))
    benches = [b for b in BENCH_ORDER if b in ("humaneval-plus", "mmlu", "gsm8k")]
    zhb = {"humaneval-plus": "代码HE+", "mmlu": "知识MMLU", "gsm8k": "推理GSM8K"}
    xs = [r["bpw"] for r in nl]
    for b in benches:
        ys = []
        for r in nl:
            row = CON.execute("SELECT _score FROM experiments WHERE run_tag=? AND protocol=? AND _bench=?",
                              (r["tag"], dict(CANON)[b], b)).fetchone()
            ys.append(row[0] if row and row[0] is not None else np.nan)
        ax.plot(xs, ys, "-o", label="原生 " + zhb[b])
        # GSQ points
        for k, v in (d.get("quants") or {}).items():
            if b in v and v[b].get("gsq") is not None:
                bpw = {"GSQ-RCO IQ3_XXS": 3.058, "GSQ-RCO IQ3_S": 3.549}.get(k)
                ax.scatter([bpw], [v[b]["gsq"]], marker="*", s=180, zorder=5,
                           label=(k + " " + zhb[b]))
    ax.set_xlabel("有效位宽 bpw"); ax.set_ylabel("分数")
    ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("GSQ-RCO（星）与原生阶梯（线）")
    return save(fig, "GSQ")


# ---------- 章节定义 ----------
def section(key, cn_title, intro, tables, figure, upnote=""):
    return {"key": key, "title": cn_title, "intro": intro, "tables": tables, "figure": figure, "upnote": upnote}


def render(H, sec):
    H.append(f"<section><h2>{sec['title']}</h2>")
    H.append(f"<p class='intro'>{sec['intro']}</p>")
    for tbl in sec["tables"]:
        rows = table_rows(tbl)
        H.append("<div class='scroll'><table>")
        for i, r in enumerate(rows):
            tag = "th" if i == 0 else "td"
            if i == 0:
                cells = [zh(c) for c in r]
            else:
                cells = [md_inline(c) for c in r]
            H.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
        H.append("</table></div>")
    if sec["figure"] and os.path.exists(sec["figure"]):
        H.append(f"<figure><img src='data:image/png;base64,{b64(sec['figure'])}'></figure>")
    H.append("</section>")


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


CSS = """
:root{--bd:#cfd8e3;--hd:#1f3a5f;--bg2:#f6f8fb}
*{box-sizing:border-box}
body{font:16px/1.75 "Noto Sans SC","PingFang SC","Microsoft YaHei",-apple-system,"Segoe UI",sans-serif;
     color:#16202a;max-width:1340px;margin:0 auto;padding:32px 26px 90px}
h1{font-size:30px;border-bottom:3px solid var(--hd);padding-bottom:12px;text-align:center}
h2{font-size:22px;margin-top:50px;padding:7px 0 7px 14px;border-left:7px solid var(--hd);background:linear-gradient(90deg,#eaf0f7,transparent)}
.intro{background:#f0f3f7;border-radius:6px;padding:9px 15px;color:#2c3947}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}
th,td{border:1px solid var(--bd);padding:6px 9px;text-align:right;white-space:nowrap}
th{background:var(--hd);color:#fff;text-align:center}
td:first-child,th:first-child{text-align:left}
tr:nth-child(even) td{background:var(--bg2)}
figure{margin:18px 0;text-align:center}
img{width:100%;max-width:1250px;border:1px solid var(--bd);border-radius:6px}
.scroll{overflow-x:auto}
code{background:#eaeef2;padding:1px 5px;border-radius:4px}
.lead{background:#eef4fb;border-left:5px solid #3b7dd8;padding:14px 18px;border-radius:6px;font-size:15.5px}
.recap td.sig{color:#b3261e;font-weight:700}
.nr{color:#8a94a0;font-style:italic}
"""


def main():
    md = {t.split(".")[0].strip(): tables for t, tables in parse_md()}
    specs = [
        ("A", "一、权重量化位宽", "X = 量化位宽。固定同一模型家族（架构、参数量不变），只换量化文件；"
         "横轴用真实有效位宽（8×字节÷参数量），不用 Q2/Q3 标签。下表每个家族给出它在各档位上的原始分数。",
         md.get("A", []), fig_slopes()),
        ("B", "二、模型规模", "X = 参数量。固定量化配方，比较不同大小的模型，看规模对分数的影响。",
         md.get("B", []), fig_size(md.get("B", [[]])[0]) if md.get("B") else None),
        ("C", "三、量化方案 / 厂商", "X = 量化方案或厂商。固定模型与相近的有效位宽区间，看“换方案/换厂商”是否有差别。",
         md.get("C", []), fig_scheme()),
        ("D", "四、MoE 逐层比特分配", "X = 哪些层拿低比特（专家层 vs 其余层）。固定同一套 base 权重与总大小。",
         md.get("D", []), fig_moe(md.get("D", [[]])[0]) if md.get("D") else None),
        ("E", "五、KV-Cache 量化", "X = KV 缓存的精度（f16 / q8_0 / q4_0）。固定模型、权重位宽与上下文。",
         md.get("E", []), fig_kv(md.get("E", [[]])[0]) if md.get("E") else None),
        ("F", "六、采样 / 解码参数", "X = 采样参数（温度、top_k）。固定模型、位宽与上下文。",
         md.get("F", []), fig_sampling(md.get("F", [[]])[0]) if md.get("F") else None),
        ("G1", "七、投机解码：速度", "X = 投机解码的草稿深度。固定模型与上下文，单位是每秒生成的 token 数。",
         md.get("G1", []), fig_speed(md.get("G1", [[]])[0]) if md.get("G1") else None),
        ("G2", "八、投机解码：质量", "X = 草稿深度。与上一节同一次运行，这里看分数是否受损。",
         md.get("G2", []), fig_specq(md.get("G2", [[]])[0]) if md.get("G2") else None),
        ("H", "九、思考开关", "X = 是否开启模型的“思考”（reasoning）。固定模型文件。",
         md.get("H", []), fig_thinking(md.get("H", [[]])[0]) if md.get("H") else None),
    ]

    specs.append(("QAT", "十、量化感知训练（QAT）", "X = 是否经过 QAT 训练。固定模型尺寸与标称配方；"
                  "下表给出 QAT 文件与同尺寸原生文件的原始分数，以及差值（红=95%区间不跨 0）。",
                  qat_tables(), fig_qat()))
    specs.append(("GSQ", "十一、GSQ-RCO 量化方案", "X = 量化方案（第三方 GSQ-RCO vs unsloth 原生阶梯）。"
                  "固定 base 模型；因为字节不完全相同，同时对比“最近原生档位”和“按位宽插值的原生”。",
                  gsq_tables(), fig_gsq()))
    specs.append(("DIFF", "十二、扩散式解码（DiffusionGemma）", "X = 解码范式（扩散 vs 自回归）。"
                  "本机 llama.cpp 不认 <code>diffusion-gemma</code> 架构，处理侧无数据；对照侧为同尺寸自回归 gemma-4-26B-A4B。",
                  [], None))

    H = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
         '<title>量化 × 基准分数：逐项报告</title>', f'<style>{CSS}</style></head><body>']
    H.append("<h1>量化 × 基准分数：逐项报告</h1>")
    # 总
    H.append("<h2>总：这个研究要回答什么</h2>")
    H.append("<div class='lead'>我们要回答的问题是：<b>把一个大模型压缩（量化）之后，它在各项任务上的实际分数会掉多少，"
             "这个“掉多少”又取决于什么。</b>做法是把每个可能的影响因素当成一个自变量 <b>X</b>（量化位宽、量化方案、"
             "模型规模、KV 缓存精度、采样参数、投机解码深度、思考开关……），把基准分数当成因变量 <b>Y</b>。<br><br>"
             "为了排除“模型本身不同”的干扰，所有比较都在<b>同一个模型家族内部</b>进行：同一套 base 权重，只换量化文件。"
             "横轴统一用真实<b>有效位宽</b>（每个权重的平均比特数 = 8×文件字节÷参数量），不用 Q2/Q3 这类标称标签。<br><br>"
             "数据规模：208 个模型文件、7 个标准基准（代码、知识、科学、真实、推理、指令）、"
             "去重后约 3300 条测量。本页共十二节，每节一个自变量，给出它的原始数据表与该自变量对应的图。</div>")
    for s in specs:
        render(H, section(*s))
    # 总：显著性与非显著性回顾
    H.append("<h2>总：显著性回顾</h2>")
    H.append("<p class='intro'>把每一节的最终结论按“显著 / 测不出（不显著）/ 未测”归类。"
             "“测不出”指 95% 置信区间跨过 0，即在当前题目数下无法区分，<b>不等于相等</b>。</p>")
    H.append("<table class='recap'><tr><th>研究项</th><th>显著的结果</th><th>测不出（不显著）</th><th>未测</th></tr>"
             "<tr><td>权重量化位宽</td><td class='sig'>Q2→Q3 在多数家族显著为正；GSM8K / 代码损失最大，TruthfulQA 最小</td>"
             "<td>Q3 以上（Q3≈Q4≈Q5）</td><td>—</td></tr>"
             "<tr><td>模型规模</td><td class='sig'>小模型（2B）在 Q2 上困难任务整体触底</td><td>大模型 / MoE 在 Q2 已接近上限，Q2→Q3 测不出</td><td>—</td></tr>"
             "<tr><td>量化方案 / 厂商</td><td class='sig'>同大小下 IQ 方案优于 K 方案</td><td>厂商标签（bartowski vs unsloth）</td><td>—</td></tr>"
             "<tr><td>MoE 逐层比特分配</td><td class='sig'>牺牲非专家层会大幅掉分（哪怕总比特更多）</td><td>—</td><td>—</td></tr>"
             "<tr><td>KV-Cache 量化</td><td>—</td><td>f16 / q8_0 / q4_0 全部测不出差别</td><td>—</td></tr>"
             "<tr><td>采样 / 解码参数</td><td class='sig'>温度压低代码分</td><td>温度 0 下 top_k；知识类基准对所有采样都无变化</td><td>—</td></tr>"
             "<tr><td>投机解码：速度</td><td class='sig'>草稿深度提高速度（模型越大收益越大）</td><td>—</td><td>—</td></tr>"
             "<tr><td>投机解码：质量</td><td>—</td><td>所有深度下分数无差别（MMLU 逐位相同）</td><td>—</td></tr>"
             "<tr><td>思考开关</td><td class='sig'>小预算下思考开反而更低</td><td>多数配置下二者接近</td><td>—</td></tr>"
             "<tr><td>量化感知训练 QAT</td><td class='sig'>Q2 下 QAT 明显更差</td><td>所有 Q4 配对测不出差别</td><td>31B 因显存不足未测</td></tr>"
             "<tr><td>GSQ-RCO 方案</td><td>—</td><td class='sig'>全部 28 个差值都测不出（无方案优势）</td><td>—</td></tr>"
             "<tr><td>扩散式解码</td><td>—</td><td>—</td><td class='nr'>运行时缺失，处理侧未测</td></tr>"
             "</table>")
    H.append("<p class='intro'><b>一句话总结：</b>量化损失在代码、推理、指令这类任务上明显，在选择题知识、事实性问答上很小；"
             "而同文件大小下“换方案”比“数字数”更值得关注。日常选择上，<b>至少用 Q3，Q3 以上除非能测出收益否则不必多花比特</b>。</p>")
    H.append("</body></html>")
    open("report.html", "w").write("\n".join(H))
    print("wrote report.html", sum(len(x) for x in H), "bytes")


if __name__ == "__main__":
    main()
