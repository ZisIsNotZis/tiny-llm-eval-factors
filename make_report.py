#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地模型设置选择对基准分数的影响：逐项报告。

结构：研究概述 → 每一项研究一节（定义 / 原始数据 / 原始数据图 / 分析）→ 结论与显著性总结。
每张图独立成图、带图例；表头全中文。唯一数据源 = experiments.sqlite。
运行：python3 make_report.py  ->  report.html
"""
from __future__ import annotations
import base64, html, json, math, os, sqlite3, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, ".wrapup")
import mktables  # noqa

CON = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)
FIGDIR = "figures/report"
os.makedirs(FIGDIR, exist_ok=True)

_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
try:
    fm.fontManager.addfont(_CJK)
    plt.rcParams["font.sans-serif"] = [fm.FontProperties(fname=_CJK).get_name(), "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
except Exception:
    pass

BENCH = [
    ("humaneval-plus", "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mbpp-plus", "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mmlu", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("arc_challenge", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("truthfulqa_mc2", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("gsm8k", "lmeval-0.4.13-chat-reasoning-off"),
    ("ifeval", "lmeval-0.4.13-chat-reasoning-off"),
]
BENCH_ORDER = [b for b, _ in BENCH]
CANON = {b: p for b, p in BENCH}
# 中文标签：同时按列键和显示名索引（mktables 的列标签是显示名）
LBL = {
    "humaneval": "代码 HumanEval", "humaneval_plus": "代码 HumanEval+", "mbpp": "代码 MBPP",
    "mbpp_plus": "代码 MBPP+", "multipl_e": "多语言代码", "mmlu": "知识 MMLU",
    "arc_challenge": "科学 ARC-c", "truthfulqa_mc2": "真实 TruthfulQA", "gsm8k": "推理 GSM8K",
    "ifeval": "指令 IFEval",
    # 连字符键（规范协议用的键）
    "humaneval-plus": "代码 HumanEval+", "mbpp-plus": "代码 MBPP+",
    # 显示名键（mktables 列标签）
    "HumanEval": "代码 HumanEval", "HumanEval+": "代码 HumanEval+", "MBPP": "代码 MBPP",
    "MBPP+": "代码 MBPP+", "MultiPL-E": "多语言代码", "MMLU": "知识 MMLU", "ARC-c": "科学 ARC-c",
    "TruthfulQA": "真实 TruthfulQA", "GSM8K": "推理 GSM8K", "IFEval": "指令 IFEval",
    "code": "代码", "long-ctx": "长上下文", "prose": "散文", "code-256": "代码(256)",
}

BPWMAP = json.load(open(".wrapup/bpw_map.json"))
QAT_PAIRS = [
    ("gemma-4-12B-it", "UD-Q4_K_XL", "m140-qat-gemma12b-q4", "m141-native-gemma12b-q4"),
    ("gemma-4-31B-it", "UD-Q4_K_XL", "m142-qat-gemma31b-q4", "m143-native-gemma31b-q4"),
    ("gemma-4-26B-A4B-it", "UD-Q4_K_XL", "m144-qat-gemma26b-a4b-q4", "m145-native-gemma26b-a4b-q4"),
    ("gemma-4-E2B-it", "UD-Q4_K_XL", "m147-qat-gemma-e2b-q4", "m148-native-gemma-e2b-q4"),
    ("gemma-4-E2B-it", "UD-Q2_K_XL", "m146-qat-gemma-e2b-q2", "m119-gemma-e2b-q2kxl"),
    ("gemma-4-E4B-it", "UD-Q4_K_XL", "m155-qat-gemma-e4b-q4", "m156-native-gemma-e4b-q4"),
    ("gemma-4-E4B-it", "UD-Q2_K_XL", "m149-qat-gemma-e4b-q2", "m121-gemma-e4b-q2kxl"),
]
NATIVE_LADDER = [("m91-qwen38-27b-q2kxl", 2.878), ("m100-qwen38-27b-q3kxl", 3.850),
                 ("m152-qwen38-27b-iq4xs", 4.173)]
GSQ_QUANTS = [("GSQ-RCO IQ3_XXS", "m150-qwen38-gsqrco-iq3xxs", 3.058),
              ("GSQ-RCO IQ3_S", "m151-qwen38-gsqrco-iq3s", 3.549)]


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def save(fig, name):
    fig.tight_layout()
    p = f"{FIGDIR}/{name}.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


def raw_scores(tag):
    out = {}
    for b, proto in CANON.items():
        r = CON.execute("SELECT _score,n_items FROM experiments WHERE run_tag=? AND protocol=? AND _bench=?",
                        (tag, proto, b)).fetchone()
        out[b] = (r[0], r[1]) if r and r[0] is not None else None
    return out


def tag_bpw(tag):
    r = CON.execute("SELECT model FROM experiments WHERE run_tag=? LIMIT 1", (tag,)).fetchone()
    return BPWMAP.get(r[0]) if r and r[0] in BPWMAP else None


def pair_delta(a, b):
    A, B = raw_scores(a), raw_scores(b)
    out = {}
    for k in BENCH_ORDER:
        ca, cb = A.get(k), B.get(k)
        if ca and cb and ca[0] is not None and cb[0] is not None:
            pa, na = ca; pb, nb = cb
            se = math.sqrt(pa * (1 - pa) / max(na or 1, 1) + pb * (1 - pb) / max(nb or 1, 1))
            out[k] = (pa - pb, se, pa - pb - 1.96 * se, pa - pb + 1.96 * se)
        else:
            out[k] = None
    return out


# ---------- 通用图：每个基准一张，X 对 Y，每 series 一条线/一组柱 ----------
def line_charts(t, xfun, xlabel, prefix):
    out = []
    for k in t["col_keys"]:
        if t["counts"].get(k, 0) == 0:
            continue
        series = {}
        for c1, c2, cells in t["rows"]:
            if not cells.get(k):
                continue
            x = xfun(c2)
            if x is None:
                continue
            series.setdefault(c1, []).append((x, cells[k][0]))
        if not series:
            continue
        fig, ax = plt.subplots(figsize=(11, 4.7))
        for s, pts in sorted(series.items()):
            pts = sorted(pts)
            if len(pts) >= 1:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], "-o", ms=4.5, lw=1.5, label=s)
        ax.set_xlabel(xlabel); ax.set_ylabel("基准分数")
        ax.set_title(f"{LBL.get(k,k)}：基准分数 随 {xlabel} 的变化")
        ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.01, 0.5), framealpha=.9)
        ax.grid(alpha=.25)
        out.append(save(fig, f"{prefix}_{k}"))
    return out


def bar_charts(t, xlabel, prefix, color_by_series=False):
    out = []
    for k in t["col_keys"]:
        if t["counts"].get(k, 0) == 0:
            continue
        xs, ys, ser = [], [], []
        for c1, c2, cells in t["rows"]:
            if cells.get(k):
                xs.append(c2); ys.append(cells[k][0]); ser.append(c1)
        if not xs:
            continue
        fig, ax = plt.subplots(figsize=(8.6, 4.7))
        cols = ["#c0392b", "#2c6fbb", "#27ae60", "#8e44ad", "#e67e22", "#16a085"]
        if color_by_series:
            uniq = sorted(set(ser)); cmap = {s: cols[i % len(cols)] for i, s in enumerate(uniq)}
            ax.bar(range(len(xs)), ys, color=[cmap[s] for s in ser])
            for s in uniq:
                ax.bar(0, 0, color=cmap[s], label=s)
            ax.legend(fontsize=8)
        else:
            ax.bar(range(len(xs)), ys, color="#2c6fbb")
        ax.set_xticks(range(len(xs))); ax.set_xticklabels(xs, rotation=20, ha="right", fontsize=8)
        ax.set_ylabel("基准分数"); ax.set_title(f"{LBL.get(k,k)}：基准分数 按 {xlabel}")
        ax.grid(axis="y", alpha=.25)
        out.append(save(fig, f"{prefix}_{k}"))
    return out


def fig_F(t):
    temp, topk = {}, {}
    for c1, c2, cells in t["rows"]:
        try:
            v = float(c2)
        except ValueError:
            continue
        if cells.get("multipl_e"):
            (temp if "temperature" in c1 else topk)[v] = cells["multipl_e"][0]
    fig, ax = plt.subplots(figsize=(8.6, 4.7))
    if temp:
        k = sorted(temp); ax.plot([str(x) for x in k], [temp[x] for x in k], "-o", label="温度")
    if topk:
        k = sorted(topk); ax.plot([str(x) for x in k], [topk[x] for x in k], "-s", label="top_k")
    ax.set_xlabel("参数取值"); ax.set_ylabel("多语言代码通过率")
    ax.legend(fontsize=9); ax.grid(alpha=.25)
    ax.set_title("采样参数：代码通过率 随 取值")
    return [save(fig, "F_value")]


def fig_G1(t):
    series = {}
    last = t["col_keys"][-1]
    for c1, c2, cells in t["rows"]:
        try:
            d = int(c2)
        except ValueError:
            continue
        if cells.get(last):
            series.setdefault(c1.split(" · ")[0], []).append((d, cells[last][0]))
    fig, ax = plt.subplots(figsize=(9, 4.7))
    for m, pts in series.items():
        pts = sorted(pts); ax.plot([p[0] for p in pts], [p[1] for p in pts], "-o", ms=4.5, label=m)
    ax.set_xlabel("投机解码草稿深度"); ax.set_ylabel("每秒生成 token 数")
    ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("投机解码速度：每秒生成 token 随 草稿深度")
    return [save(fig, "G1_speed")]


def fig_G2(t):
    out = []
    for key, name in (("humaneval", "代码 HumanEval"), ("mmlu", "知识 MMLU")):
        series = {}
        for c1, c2, cells in t["rows"]:
            try:
                d = int(c2)
            except ValueError:
                continue
            if cells.get(key):
                series.setdefault(c1.split(" · ")[0], []).append((d, cells[key][0]))
        if not series:
            continue
        fig, ax = plt.subplots(figsize=(9, 4.7))
        for m, pts in series.items():
            pts = sorted(pts); ax.plot([p[0] for p in pts], [p[1] for p in pts], "-o", ms=4.5, label=m)
        ax.set_xlabel("草稿深度"); ax.set_ylabel("基准分数")
        ax.set_title(f"{name}：分数 随 草稿深度")
        ax.legend(fontsize=8); ax.grid(alpha=.25)
        out.append(save(fig, f"G2_{key}"))
    return out


def fig_H(t):
    series = {}
    for c1, c2, cells in t["rows"]:
        mode = "开" if "on" in c2 else "关"
        series.setdefault(c1, {})[mode] = cells.get("gsm8k", (np.nan,))[0] if cells.get("gsm8k") else np.nan
    models = [m for m in series if "开" in series[m] and "关" in series[m]]
    fig, ax = plt.subplots(figsize=(11, 4.7))
    x = np.arange(len(models)); w = .4
    ax.bar(x - w / 2, [series[m]["关"] for m in models], w, label="思考关")
    ax.bar(x + w / 2, [series[m]["开"] for m in models], w, label="思考开", color="#c0392b")
    ax.set_xticks(x); ax.set_xticklabels(models, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("推理 GSM8K 分数"); ax.legend(); ax.grid(axis="y", alpha=.25)
    ax.set_title("思考开关：GSM8K 分数 按 模型与思考开关")
    return [save(fig, "H_thinking")]


def fig_QAT():
    out = []
    for label, recipe, q, n in QAT_PAIRS:
        a, b = raw_scores(q), raw_scores(n)
        ks = [k for k in BENCH_ORDER if a.get(k) or b.get(k)]
        if not ks:
            continue
        fig, ax = plt.subplots(figsize=(8.6, 4.7))
        x = np.arange(len(ks)); w = .4
        ax.bar(x - w / 2, [a[k][0] if a.get(k) else np.nan for k in ks], w, label="QAT")
        ax.bar(x + w / 2, [b[k][0] if b.get(k) else np.nan for k in ks], w, label="原生", color="#c0392b")
        ax.set_xticks(x); ax.set_xticklabels([LBL[k] for k in ks], rotation=25, ha="right", fontsize=8)
        ax.set_ylabel("基准分数"); ax.set_title(f"{label}（{recipe}）：QAT vs 原生")
        ax.legend(); ax.grid(axis="y", alpha=.25)
        out.append(save(fig, f"QAT_{label}_{recipe}"))
    return out


def fig_GSQ():
    out = []
    for b in ("humaneval-plus", "mmlu", "gsm8k"):
        fig, ax = plt.subplots(figsize=(8.6, 4.7))
        xs, ys = [], []
        for tag, bpw in NATIVE_LADDER:
            sc = raw_scores(tag).get(b)
            xs.append(bpw); ys.append(sc[0] if sc and sc[0] is not None else np.nan)
        ax.plot(xs, ys, "-o", label="原生 UD 阶梯")
        for k, tag, bpw in GSQ_QUANTS:
            g = raw_scores(tag).get(b)
            if g and g[0] is not None:
                ax.scatter([bpw], [g[0]], marker="*", s=200, zorder=5, label=k)
        ax.set_xlabel("有效位宽"); ax.set_ylabel("基准分数")
        ax.set_title(f"{LBL[b]}：分数 随 有效位宽")
        ax.legend(fontsize=8); ax.grid(alpha=.25)
        out.append(save(fig, f"GSQ_{b}"))
    return out


# ---------- HTML ----------
CSS = """
:root{--bd:#cfd8e3;--hd:#1f3a5f;--bg2:#f6f8fb}
*{box-sizing:border-box}
body{font:16px/1.75 "Noto Sans SC","PingFang SC","Microsoft YaHei",-apple-system,"Segoe UI",sans-serif;
     color:#16202a;max-width:1400px;margin:0 auto;padding:32px 26px 90px}
h1{font-size:30px;border-bottom:3px solid var(--hd);padding-bottom:12px;text-align:center}
h2{font-size:22px;margin-top:52px;padding:7px 0 7px 14px;border-left:7px solid var(--hd);background:linear-gradient(90deg,#eaf0f7,transparent)}
h3{font-size:17px;margin:26px 0 8px;color:var(--hd);border-bottom:2px solid #dbe4ee;padding-bottom:4px}
.def{background:#eef4fb;border-left:5px solid #3b7dd8;padding:10px 16px;border-radius:6px;font-size:15px}
.analysis{background:#f7f9fb;border:1px solid var(--bd);border-radius:6px;padding:10px 20px;font-size:15px}
.analysis li{margin:6px 0}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}
th,td{border:1px solid var(--bd);padding:6px 9px;text-align:right;white-space:nowrap}
th{background:var(--hd);color:#fff;text-align:center}
td:first-child,th:first-child{text-align:left}
tr:nth-child(even) td{background:var(--bg2)}
.cover td{background:#eef4fb !important;font-weight:600}
figure{margin:16px 0;text-align:center}
img{width:100%;max-width:1350px;border:1px solid var(--bd);border-radius:6px}
.scroll{overflow-x:auto}
code{background:#eaeef2;padding:1px 5px;border-radius:4px}
.lead{background:#eef4fb;border-left:5px solid #3b7dd8;padding:14px 18px;border-radius:6px;font-size:15.5px}
.recap td.sig{color:#b3261e;font-weight:700}
.nr{color:#8a94a0;font-style:italic}
"""


def render_table(t):
    keys = t["col_keys"]; unit = t.get("unit")
    out = ["<div class='scroll'><table><tr><th>%s</th><th>%s</th>%s</tr>"
           % (html.escape(t["c1_name"]), html.escape(t["c2_name"]),
              "".join("<th>%s</th>" % LBL.get(l, l) for l in t["col_labels"]))]
    out.append("<tr class='cover'><td>覆盖</td><td>行数=%d · 有数据列=%d/%d</td>%s</tr>"
               % (len(t["rows"]), t["data_cols"], len(keys),
                  "".join("<td>%d</td>" % t["counts"][k] for k in keys)))
    for c1, c2, cells in t["rows"]:
        tds = []
        for k in keys:
            c = cells.get(k)
            if c is None or c[0] is None:
                tds.append("<td class='nr'>—</td>")
            elif unit == "tok_s":
                tds.append("<td>%.1f <span class='nr'>(%s)</span></td>" % (c[0], c[1] if c[1] else 0))
            else:
                tds.append("<td>%.4f <span class='nr'>(%s)</span></td>" % (c[0], c[1] or 0))
        out.append("<tr><td>%s</td><td>%s</td>%s</tr>" % (html.escape(c1), html.escape(c2), "".join(tds)))
    out.append("</table></div>")
    return "\n".join(out)


def qat_tables():
    ks = BENCH_ORDER; labs = [LBL[k] for k in ks]
    rows = []; rows2 = []
    for label, recipe, q, n in QAT_PAIRS:
        for which, tag in (("QAT", q), ("原生", n)):
            bpw = tag_bpw(tag)
            rows.append((f"{label} {recipe} {which}", f"{bpw:.3f}" if bpw else "—", raw_scores(tag)))
        dl = pair_delta(q, n); cells = {}
        for b in ks:
            c = dl.get(b)
            if c:
                cells[b] = (c[0], f"[{c[2]:+.3f},{c[3]:+.3f}]")
        rows2.append((f"{label} {recipe}", "QAT − 原生", cells))
    def mk(title, rows):
        return {"title": title, "c1_name": "系列", "c2_name": "有效位宽", "col_keys": ks, "col_labels": labs,
                "rows": rows, "counts": {k: sum(1 for _, _, c in rows if c.get(k)) for k in ks}, "data_cols": len(ks)}
    return [mk("量化感知训练：原始分数", rows), mk("量化感知训练：差值（QAT−原生）", rows2)]


def gsq_tables():
    ks = BENCH_ORDER; labs = [LBL[k] for k in ks]
    rows = [("原生 " + tag, f"{bpw:.3f}", raw_scores(tag)) for tag, bpw in NATIVE_LADDER]
    rows += [(k, f"{bpw:.3f}", raw_scores(tag)) for k, tag, bpw in GSQ_QUANTS]
    return [{"title": "GSQ-RCO：原始分数", "c1_name": "系列", "c2_name": "有效位宽", "col_keys": ks,
             "col_labels": labs, "rows": rows,
             "counts": {k: sum(1 for _, _, c in rows if c.get(k)) for k in ks}, "data_cols": len(ks)}]


def section(H, title, definition, tables, figures, analysis_html):
    H.append(f"<section><h2>{title}</h2>")
    H.append(f"<p class='def'>{definition}</p>")
    H.append("<h3>原始数据</h3>")
    for t in tables:
        H.append(render_table(t))
    if figures:
        H.append("<h3>原始数据图</h3>")
        for f in figures:
            if os.path.exists(f):
                H.append(f"<figure><img src='data:image/png;base64,{b64(f)}'></figure>")
    H.append("<h3>分析</h3>")
    H.append(f"<div class='analysis'>{analysis_html}</div>")
    H.append("</section>")


def main():
    T = {t["title"].split(".")[0].strip(): t for t in mktables.build_tables()}
    H = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
         '<title>本地模型设置选择对基准分数的影响：逐项报告</title>', f'<style>{CSS}</style></head><body>']
    H.append("<h1>本地模型设置选择对基准分数的影响：逐项报告</h1>")

    H.append("<h2>研究概述：这个项目是什么，要研究什么</h2>")
    H.append("<div class='lead'>"
             "<b>这个项目在做什么。</b>给本地部署的大模型换各种<b>设置</b>之后，它在基准上的实际跑分会怎么变？"
             "这里的“设置”是一个很宽的集合，<b>量化只是其中一个子项</b>。每个设置就是一项研究。<br><br>"
             "<b>要研究哪些内容。</b>每个可能的影响因素被当作一个自变量 <b>X</b> 单独研究："
             "① 量化位宽（一个权重平均花几个比特）② 量化方案／厂商 ③ 模型规模 ④ MoE 各层比特分配 ⑤ KV 缓存精度 "
             "⑥ 采样参数 ⑦ 投机解码草稿深度 ⑧ 是否开思考 ⑨ 量化感知训练(QAT) ⑩ 第三方方案(GSQ-RCO) ⑪ 扩散式解码。<br><br>"
             "<b>X 与 Y。</b>每个研究里，<b>X = 该研究改变的那一个量</b>，<b>Y = 基准分数</b>；"
             "同一节内其它被固定的东西（模型、厂商、协议）构成各个<b>系列</b>，画成不同的线。<br><br>"
             "<b>为什么这样比。</b>所有比较都在<b>同一个模型家族内部</b>进行——同一套 base 权重，只换量化文件——"
             "这样架构和参数量天然固定，X 是唯一在变的东西。量化位宽一律用真实值 <b>有效位宽 = 8×文件字节数÷参数量</b>，"
             "而不是厂商标称的档位名（同名档位在不同模型上实际跨度很大）。<br><br>"
             "<b>数据与基准。</b>全部数据来自 <code>experiments.sqlite</code>；7 个标准基准：代码（HumanEval+、MBPP+）、"
             "知识（MMLU）、科学（ARC-Challenge）、事实性（TruthfulQA）、推理（GSM8K）、指令（IFEval）。"
             "表格里每个分数后的括号是题目数；缺失写 <code>—</code>，绝不写 0。</div>")

    sections = [
        ("一、量化位宽（每个权重平均几个比特）",
         "X = 有效位宽（越大表示每个权重平均比特越多）；Y = 各基准分数；系列 = 模型家族（同家族 = 同一套 base 权重，只换量化文件）。",
         [T["A"]], line_charts(T["A"], lambda c2: float(c2.split()[0]), "有效位宽", "A"),
         "<ul>"
         "<li>每条线是一个家族。多数家族在低比特一端分数很低，<b>在约 3–4 比特/权重之间出现明显抬升</b>，再往上（约 4 比特/权重以上）基本走平。</li>"
         "<li>抬升幅度在不同基准上差别很大：代码（HumanEval+/MBPP+）、推理（GSM8K）、指令（IFEval）抬升明显；"
         "知识（MMLU）、科学（ARC-c）、事实性（TruthfulQA）几乎不动。这就是“量化伤害取决于你测哪个基准”的来源。</li>"
         "<li>并非所有家族都这样：Qwen3.6-35B-A3B（大 MoE）在很低的比特上已经很高，抬升不明显——说明伤害大小取决于“低比特是否真的伤了这个模型”。</li>"
         "<li>操作结论：<b>量化位宽至少要到约 4 比特/权重；再往上除非能测出具体收益，否则多花比特买不到分数</b>（花岗岩 granite 是例外，继续加比特仍有收益）。</li>"
         "</ul>"),
        ("二、模型规模（参数量）",
         "X = 模型参数量（单位 B）；Y = 各基准分数；系列 = 家族 + 量化配方。",
         [T["B"]], line_charts(T["B"], lambda c2: mktables.size_value(c2) or None, "参数量（B）", "B"),
         "<ul>"
         "<li>同一配方下，参数量越大分数越高。</li>"
         "<li>小模型之间（0.8B→2B→4B）的差距通常比大模型之间更大——大模型已接近各自的分数上限，规模带来的边际收益变小。</li>"
         "<li>规模还会影响低比特的表现：小模型在低比特的困难任务上会整体触底（见“量化位宽”一节里 2B 的曲线）。</li>"
         "</ul>"),
        ("三、量化方案 / 厂商",
         "X = 量化方案或厂商（在同一模型、相近的有效位宽区间内）；Y = 各基准分数。",
         [T["C"]], bar_charts(T["C"], "方案（厂商）", "C", color_by_series=True),
         "<ul>"
         "<li>在文件字节接近的前提下，换<b>方案</b>（例如 IQ 系列 vs 传统 K 系列）分数会出现可测的差异。</li>"
         "<li>而换<b>厂商</b>标签（同一模型、大小差不到 1%）基本测不出差异。</li>"
         "<li>结论：挑量化时应该比“字节 / 方案”，而不是比厂商标签。</li>"
         "</ul>"),
        ("四、MoE 各层比特分配",
         "X = 哪些层拿低比特（专家层 vs 其余层），固定同一套 base 权重；Y = 各基准分数。",
         [T["D"]], bar_charts(T["D"], "配方", "D"),
         "<ul>"
         "<li>三条配方里，把<b>非专家层</b>压到最低的那条分数最低——尽管它的总比特最多（4.48 比特/权重）。</li>"
         "<li>把<b>专家层</b>压到最低、其余层保持高位的那条，反而保住了大部分能力，且总比特更低（2.92）。</li>"
         "<li>原因：非专家层（注意力、归一化等）每个 token 每次前向都会用到；单个专家只有一部分 token 会走到，"
         "MoE 的路由可以绕开被压坏的专家。所以要保护非专家层，专家层是省比特的安全区。</li>"
         "</ul>"),
        ("五、KV 缓存精度",
         "X = KV 缓存的精度（f16 / q8_0 / q4_0），固定模型、权重位宽与上下文；Y = 各基准分数。",
         [T["E"]], bar_charts(T["E"], "KV 精度（K/V）", "E"),
         "<ul>"
         "<li>三种精度（f16、q8_0、q4_0）的柱几乎等高，即在这类任务上<b>测不出差别</b>。</li>"
         "<li>注意范围：这里的上下文只有约 1k–2k tokens。KV 量化理论上只会在上下文很长时才咬人，"
         "所以这个结论只覆盖短到中等上下文，长上下文未测。</li>"
         "</ul>"),
        ("六、采样 / 解码参数",
         "X = 采样参数（温度、top_k），固定模型、位宽与上下文；Y = 多语言代码通过率。",
         [T["F"]], fig_F(T["F"]),
         "<ul>"
         "<li>温度从 0 升到 0.3/0.7 会压低代码通过率。</li>"
         "<li>top_k 在贪心附近（温度 0）基本不变——这是结构事实：温度 0 时没有分布可截断，top_k 无从生效。</li>"
         "<li>知识类基准（MMLU）对采样完全无反应，因为它用对数似然打分、根本不采样。这反过来证明测量链路是对的。</li>"
         "</ul>"),
        ("七、投机解码（速度）",
         "X = 投机解码草稿深度；Y = 每秒生成 token 数（取自 llama-server 自身计时）；系列 = 模型。",
         [T["G1"]], fig_G1(T["G1"]),
         "<ul>"
         "<li>草稿深度越大，生成速度越快。</li>"
         "<li>模型越大，加速收益越大（0.8B 约 +36%，9B 约 +93%）——小模型本身已受内存带宽限制，草稿路径可利用的余量更小。</li>"
         "</ul>"),
        ("八、投机解码（质量）",
         "X = 草稿深度；Y = 各基准分数；系列 = 模型。",
         [T["G2"]], fig_G2(T["G2"]),
         "<ul>"
         "<li>分数随草稿深度几乎不变，没有一致方向的损伤或增益。</li>"
         "<li>MMLU 在每个模型、每个深度上<b>逐位相同</b>：它走对数似然打分，不经过草稿模型。这是测量正确的正对照。</li>"
         "<li>因此投机解码可以放心开：它买速度，不伤质量（在测试的深度范围内）。</li>"
         "</ul>"),
        ("九、思考开关",
         "X = 是否开启思考（reasoning）；Y = GSM8K 分数；系列 = 模型文件。",
         [T["H"]], fig_H(T["H"]),
         "<ul>"
         "<li>开与关的差随模型与生成预算而定，没有统一方向。</li>"
         "<li>在预算较小的情况下，开思考反而更低：推理流占用了答案预算。</li>"
         "<li>因此主协议统一使用“关思考”；开思考只作为单独诊断轴保留，不与主结果混用。</li>"
         "</ul>"),
        ("十、量化感知训练（QAT）",
         "X = 该量化文件是否经过 QAT 训练，固定模型尺寸与标称配方；Y = 各基准分数（并给出差值表）。",
         qat_tables(), fig_QAT(),
         "<ul>"
         "<li>所有 4-bit 配对里，QAT 与原生在多数基准上基本重合，而 QAT 文件还小 0.44–0.95 比特/权重。</li>"
         "<li>只有 2-bit 配对里 QAT 明显更低（代码、算术、指令）。</li>"
         "<li>所以 QAT 应当被当成“同配方下体积更小”的选项，而不是质量升级。</li>"
         "<li>一个必须说明的事实：这些 QAT 文件用的是另一种量化格式（Q4_0 系列，ggml 类型 2），而原生对照是 K 系列格式，"
         "所以这个差值里还混了“方案”这一个因素，不能纯归给 QAT。</li>"
         "</ul>"),
        ("十一、第三方量化方案（GSQ-RCO）",
         "X = 量化方案（第三方 GSQ-RCO vs unsloth 原生阶梯），固定 Qwen3.8-27B；Y = 各基准分数。",
         gsq_tables(), fig_GSQ(),
         "<ul>"
         "<li>GSQ-RCO 的两个量化档（星标）落在原生阶梯（折线）上或附近。</li>"
         "<li>与“最接近的原生档位”比、与“按有效位宽线性插值后的原生”比，两种比法在所有基准上都测不出差异。</li>"
         "<li>结论：GSQ-RCO 是一个中性方案，没有方案级红利。（这与“同大小下 IQ 优于 K”并不矛盾——"
         "说明方案红利不是普遍规律。）</li>"
         "</ul>"),
        ("十二、扩散式解码（DiffusionGemma）",
         "X = 解码范式（扩散 vs 自回归），对照为同尺寸自回归 gemma-4-26B-A4B；Y = 各基准分数。",
         [], None,
         "<ul><li>本机的 llama.cpp（含 diffusion-cli）不认 <code>diffusion-gemma</code> 架构，处理侧完全没有数据。</li>"
         "<li>因此这一项是<b>未测</b>（不是 0，也不是 null）：需要另建支持该架构的运行时才能比较。</li></ul>"),
    ]
    for title, defn, tables, figs, analysis in sections:
        section(H, title, defn, tables, figs, analysis)

    H.append("<h2>结论与显著性总结</h2>")
    H.append("<p class='def'>显著 = 95% 置信区间不跨 0；测不出 = 区间跨 0（在当前题目数下无法区分，<b>不等于相等</b>）；"
             "未测 = 显存/运行时等原因没有数据。</p>")
    H.append("<table class='recap'><tr><th>研究项</th><th>显著</th><th>测不出</th><th>未测</th></tr>"
             "<tr><td>量化位宽</td><td class='sig'>从低比特到约 4 比特/权重之间多数家族明显抬升；代码/推理幅度最大、知识/事实性最小</td><td>约 4 比特/权重以上基本走平</td><td>—</td></tr>"
             "<tr><td>模型规模</td><td class='sig'>2B 在低比特困难任务整体触底</td><td>大模型/MoE 在低比特已近上限</td><td>激活参数（无受控样本）</td></tr>"
             "<tr><td>量化方案/厂商</td><td class='sig'>同大小下方案有差</td><td>厂商标签</td><td>APEX 无产物</td></tr>"
             "<tr><td>MoE 各层比特分配</td><td class='sig'>牺牲非专家层大幅掉分</td><td>—</td><td>—</td></tr>"
             "<tr><td>KV 缓存精度</td><td>—</td><td>f16/q8_0/q4_0 全测不出（短上下文）</td><td>长上下文</td></tr>"
             "<tr><td>采样/解码参数</td><td class='sig'>温度压低代码分</td><td>温度 0 下 top_k；知识类无变化</td><td>—</td></tr>"
             "<tr><td>投机解码：速度</td><td class='sig'>草稿深度提速（模型越大收益越大）</td><td>—</td><td>—</td></tr>"
             "<tr><td>投机解码：质量</td><td>—</td><td>所有深度分数无差别</td><td>—</td></tr>"
             "<tr><td>思考开关</td><td class='sig'>小预算下开思考更低</td><td>多数配置接近</td><td>—</td></tr>"
             "<tr><td>量化感知训练 QAT</td><td class='sig'>2-bit 下 QAT 更低</td><td>所有 4-bit 配对</td><td>31B（显存不足）</td></tr>"
             "<tr><td>GSQ-RCO 方案</td><td>—</td><td class='sig'>全部差值都测不出</td><td>—</td></tr>"
             "<tr><td>扩散式解码</td><td>—</td><td>—</td><td class='nr'>运行时缺失</td></tr></table>")
    H.append("<p class='def'><b>一句话总结：</b>量化损失在代码、推理、指令上明显，在选择题知识与事实性上很小；"
             "同文件大小时“换方案”比“数字数”更值得关注。日常选择：<b>量化位宽至少约 4 比特/权重，再往上除非能测出收益否则不必多花比特</b>。</p>")
    H.append("</body></html>")
    open("report.html", "w").write("\n".join(H))
    print("wrote report.html", sum(len(x) for x in H), "bytes; figures:", len([1 for _ in os.listdir(FIGDIR)]))


if __name__ == "__main__":
    main()
