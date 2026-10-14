#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量化 × 基准分数：逐项报告（总—分—总；每节先原始数据表、再原始数据图、后分析）。

唯一数据源 = experiments.sqlite。表结构由 .wrapup/mktables.py 的 build_tables() 提供（同样只读 DB）。
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

# 规范协议（用于取原始分数）——七个标准基准
BENCH = [
    ("humaneval-plus", "代码", "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mbpp-plus", "代码", "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mmlu", "知识", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("arc_challenge", "科学", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("truthfulqa_mc2", "事实性", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("gsm8k", "推理", "lmeval-0.4.13-chat-reasoning-off"),
    ("ifeval", "指令", "lmeval-0.4.13-chat-reasoning-off"),
]
BENCH_ORDER = [b for b, _, _ in BENCH]
CANON = {b: p for b, _, p in BENCH}
ZH7 = {"humaneval-plus": "代码 HumanEval+", "mbpp-plus": "代码 MBPP+", "mmlu": "知识 MMLU",
       "arc_challenge": "科学 ARC-c", "truthfulqa_mc2": "真实 TruthfulQA", "gsm8k": "推理 GSM8K",
       "ifeval": "指令 IFEval"}
ZH10 = {"humaneval": "代码 HumanEval", "humaneval_plus": "代码 HumanEval+", "mbpp": "代码 MBPP",
        "mbpp_plus": "代码 MBPP+", "multipl_e": "多语言代码", "mmlu": "知识 MMLU",
        "arc_challenge": "科学 ARC-c", "truthfulqa_mc2": "真实 TruthfulQA", "gsm8k": "推理 GSM8K",
        "ifeval": "指令 IFEval"}

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
    fig.savefig(f"{FIGDIR}/{name}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return f"{FIGDIR}/{name}.png"


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


def cell(t, c1, b):
    for a, _c2, cells in t["rows"]:
        if a == c1 and cells.get(b):
            return cells[b][0]
    return None


# ---------------- 原始数据图（X 对 Y，每 series 一条线/一组柱） ----------------
def fig_A(t):
    benches = t["col_keys"]
    fams = sorted({c1 for c1, _, _ in t["rows"]})
    fig, axes = plt.subplots(2, 5, figsize=(23, 8.5), sharex=True)
    for ax, b in zip(axes.ravel(), benches):
        for fam in fams:
            pts = sorted((float(c2.split()[0]), cells[b][0])
                         for c1, c2, cells in t["rows"] if c1 == fam and cells.get(b))
            if len(pts) >= 2:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], "-o", ms=3, lw=1, alpha=.85, label=fam)
        ax.set_title(ZH10.get(b, b), fontsize=10)
        ax.grid(alpha=.25); ax.set_xlabel("有效位宽 bpw")
    axes[0][0].set_ylabel("基准分数"); axes[1][0].set_ylabel("基准分数")
    fig.suptitle("原始数据：基准分数 随 有效位宽（每个模型家族一条线）", fontsize=13)
    return save(fig, "A_raw")


def fig_B(t):
    benches = [b for b in ("humaneval_plus", "mmlu", "gsm8k") if b in t["col_keys"]]
    series = {}
    for c1, c2, cells in t["rows"]:
        s = mktables.size_value(c2)
        if s > 0:
            series.setdefault(c1, []).append((s, [cell(t, c1, b) for b in benches]))
    fig, axes = plt.subplots(1, len(benches), figsize=(5 * len(benches), 4.2), squeeze=False)
    for j, b in enumerate(benches):
        ax = axes[0][j]
        for c1, pts in series.items():
            pts = sorted(pts)
            ax.plot([p[0] for p in pts], [p[1][j] for p in pts], "-o", ms=4, lw=1.2, label=c1)
        ax.set_title(ZH10.get(b, b)); ax.set_xlabel("参数量（B）"); ax.grid(alpha=.25)
    axes[0][0].set_ylabel("基准分数"); axes[0][-1].legend(fontsize=7)
    fig.suptitle("原始数据：基准分数 随 模型参数量（每个量化配方一条线）", fontsize=12)
    return save(fig, "B_raw")


def fig_C(t):
    benches = [b for b in ("humaneval_plus", "mmlu", "gsm8k") if b in t["col_keys"]]
    groups = {}
    for c1, c2, cells in t["rows"]:
        groups.setdefault(c1, []).append((c2, cells))
    n = max(1, len(groups))
    fig, axes = plt.subplots(1, n, figsize=(5.5 * n, 4.2), squeeze=False)
    for ax, (c1, items) in zip(axes[0], groups.items()):
        x = np.arange(len(items)); w = .8 / max(1, len(benches))
        for j, b in enumerate(benches):
            ax.bar(x + (j - len(benches) / 2) * w, [ci.get(b, (np.nan,))[0] if ci.get(b) else np.nan for _, ci in items],
                   w, label=ZH10.get(b, b))
        ax.set_xticks(x); ax.set_xticklabels([c for c, _ in items], rotation=20, ha="right", fontsize=8)
        ax.set_title(c1, fontsize=9); ax.grid(axis="y", alpha=.25)
    axes[0][0].set_ylabel("基准分数"); axes[0][-1].legend(fontsize=8)
    fig.suptitle("原始数据：同一位宽区间内，不同量化方案 / 厂商的分数", fontsize=12)
    return save(fig, "C_raw")


def fig_D(t):
    benches = t["col_keys"]
    labels = [c2 for _, c2, _ in t["rows"]]
    data = np.array([[c.get(b, (np.nan,))[0] if c.get(b) else np.nan for b in benches] for _, _, c in t["rows"]])
    fig, ax = plt.subplots(figsize=(11, 4.6))
    x = np.arange(len(labels)); w = .8 / len(benches)
    for j, b in enumerate(benches):
        ax.bar(x + (j - len(benches) / 2) * w, data[:, j], w, label=ZH10.get(b, b))
    ax.set_xticks(x); ax.set_xticklabels([l.replace(" · ", "\n") for l in labels], fontsize=8)
    ax.set_ylabel("基准分数"); ax.legend(fontsize=7, ncol=2); ax.grid(axis="y", alpha=.25)
    ax.set_title("原始数据：MoE 逐层比特分配（X=配方，Y=分数）")
    return save(fig, "D_raw")


def fig_E(t):
    benches = t["col_keys"]
    rows = [(c2, c) for c1, c2, c in t["rows"]]
    seen, order = set(), []
    for lab, _ in rows:
        if lab not in seen:
            seen.add(lab); order.append(lab)
    fig, ax = plt.subplots(figsize=(10, 4.4))
    x = np.arange(len(benches)); w = .8 / max(1, len(order))
    for k, lab in enumerate(order):
        cells = next(c for l, c in rows if l == lab)
        ax.bar(x + (k - len(order) / 2) * w, [cells.get(b, (np.nan,))[0] if cells.get(b) else np.nan for b in benches],
               w, label=lab)
    ax.set_xticks(x); ax.set_xticklabels([ZH10.get(b, b) for b in benches], fontsize=8)
    ax.set_ylabel("基准分数"); ax.legend(fontsize=8); ax.grid(axis="y", alpha=.25)
    ax.set_title("原始数据：KV-Cache 精度（X=KV类型，Y=分数）")
    return save(fig, "E_raw")


def fig_F(t):
    temp, topk = {}, {}
    for c1, c2, cells in t["rows"]:
        try:
            v = float(c2)
        except ValueError:
            continue
        if cells.get("multipl_e"):
            (temp if "temperature" in c1 else topk)[v] = cells["multipl_e"][0]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    if temp:
        k = sorted(temp); ax.plot([str(x) for x in k], [temp[x] for x in k], "-o", label="温度")
    if topk:
        k = sorted(topk); ax.plot([str(x) for x in k], [topk[x] for x in k], "-s", label="top_k")
    ax.set_xlabel("参数取值"); ax.set_ylabel("多语言代码 通过率")
    ax.legend(fontsize=9); ax.grid(alpha=.25)
    ax.set_title("原始数据：采样参数（X=取值，Y=代码通过率）")
    return save(fig, "F_raw")


def fig_G1(t):
    series = {}
    for c1, c2, cells in t["rows"]:
        try:
            d = int(c2)
        except ValueError:
            continue
        last = t["col_keys"][-1]
        if cells.get(last):
            series.setdefault(c1.split(" · ")[0], []).append((d, cells[last][0]))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for m, pts in series.items():
        pts = sorted(pts)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "-o", ms=4, label=m)
    ax.set_xlabel("投机解码草稿深度"); ax.set_ylabel("每秒生成 token")
    ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("原始数据：投机解码速度（X=草稿深度，Y=tok/s，每个模型一条线）")
    return save(fig, "G1_raw")


def fig_G2(t):
    series = {}
    for c1, c2, cells in t["rows"]:
        try:
            d = int(c2)
        except ValueError:
            continue
        series.setdefault(c1.split(" · ")[0], []).append(
            (d, cells.get("humaneval", (np.nan,))[0] if cells.get("humaneval") else np.nan,
             cells.get("mmlu", (np.nan,))[0] if cells.get("mmlu") else np.nan))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    for m, pts in series.items():
        pts = sorted(pts)
        axes[0].plot([p[0] for p in pts], [p[1] for p in pts], "-o", ms=4, label=m)
        axes[1].plot([p[0] for p in pts], [p[2] for p in pts], "-o", ms=4, label=m)
    axes[0].set_title("代码 HumanEval"); axes[1].set_title("知识 MMLU")
    for a in axes:
        a.set_xlabel("草稿深度"); a.set_ylabel("分数"); a.grid(alpha=.25)
    axes[1].legend(fontsize=7)
    fig.suptitle("原始数据：投机解码质量（X=草稿深度，Y=分数）")
    return save(fig, "G2_raw")


def fig_H(t):
    series = {}
    for c1, c2, cells in t["rows"]:
        mode = "开" if "on" in c2 else "关"
        series.setdefault(c1, {})[mode] = cells.get("gsm8k", (np.nan,))[0] if cells.get("gsm8k") else np.nan
    models = [m for m in series if "开" in series[m] and "关" in series[m]]
    fig, ax = plt.subplots(figsize=(11, 4.3))
    x = np.arange(len(models)); w = .4
    ax.bar(x - w / 2, [series[m]["关"] for m in models], w, label="思考关")
    ax.bar(x + w / 2, [series[m]["开"] for m in models], w, label="思考开", color="#c0392b")
    ax.set_xticks(x); ax.set_xticklabels(models, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("推理 GSM8K 分数"); ax.legend(); ax.grid(axis="y", alpha=.25)
    ax.set_title("原始数据：思考开关（X=模型，Y=GSM8K 分数）")
    return save(fig, "H_raw")


def fig_QAT():
    fig, axes = plt.subplots(1, len(QAT_PAIRS), figsize=(3.2 * len(QAT_PAIRS), 4.2), squeeze=False)
    for ax, (label, recipe, q, n) in zip(axes[0], QAT_PAIRS):
        a, b = raw_scores(q), raw_scores(n)
        ks = [k for k in BENCH_ORDER if a.get(k) or b.get(k)]
        x = np.arange(len(ks)); w = .4
        ax.bar(x - w / 2, [a[k][0] if a.get(k) else np.nan for k in ks], w, label="QAT")
        ax.bar(x + w / 2, [b[k][0] if b.get(k) else np.nan for k in ks], w, label="原生", color="#c0392b")
        ax.set_xticks(x); ax.set_xticklabels([ZH7[k].split()[0] + ZH7[k].split()[1][:4] for k in ks], rotation=60, ha="right", fontsize=6)
        ax.set_title(f"{label}\n{recipe}", fontsize=8); ax.grid(axis="y", alpha=.25)
        if ax is axes[0][0]:
            ax.set_ylabel("基准分数"); ax.legend(fontsize=7)
    fig.suptitle("原始数据：量化感知训练 vs 原生（X=基准，Y=分数）")
    return save(fig, "QAT_raw")


def fig_GSQ():
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for b in ("humaneval-plus", "mmlu", "gsm8k"):
        xs, ys = [], []
        for tag, bpw in NATIVE_LADDER:
            sc = raw_scores(tag).get(b)
            xs.append(bpw); ys.append(sc[0] if sc and sc[0] is not None else np.nan)
        ax.plot(xs, ys, "-o", label="原生 " + ZH7[b])
        for k, tag, bpw in GSQ_QUANTS:
            g = raw_scores(tag).get(b)
            if g and g[0] is not None:
                ax.scatter([bpw], [g[0]], marker="*", s=170, zorder=5, label=f"{k} {ZH7[b]}")
    ax.set_xlabel("有效位宽"); ax.set_ylabel("基准分数")
    ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("原始数据：GSQ-RCO（星）与原生阶梯（线），X=有效位宽，Y=分数")
    return save(fig, "GSQ_raw")


# ---------------- HTML ----------------
CSS = """
:root{--bd:#cfd8e3;--hd:#1f3a5f;--bg2:#f6f8fb}
*{box-sizing:border-box}
body{font:16px/1.75 "Noto Sans SC","PingFang SC","Microsoft YaHei",-apple-system,"Segoe UI",sans-serif;
     color:#16202a;max-width:1400px;margin:0 auto;padding:32px 26px 90px}
h1{font-size:30px;border-bottom:3px solid var(--hd);padding-bottom:12px;text-align:center}
h2{font-size:22px;margin-top:50px;padding:7px 0 7px 14px;border-left:7px solid var(--hd);background:linear-gradient(90deg,#eaf0f7,transparent)}
h3{font-size:16px;margin:22px 0 6px;color:var(--hd)}
.def{background:#eef4fb;border-left:5px solid #3b7dd8;padding:10px 16px;border-radius:6px;font-size:15px}
.analysis{background:#f7f9fb;border:1px solid var(--bd);border-radius:6px;padding:6px 18px;font-size:15px}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}
th,td{border:1px solid var(--bd);padding:6px 9px;text-align:right;white-space:nowrap}
th{background:var(--hd);color:#fff;text-align:center}
td:first-child,th:first-child{text-align:left}
tr:nth-child(even) td{background:var(--bg2)}
.cover td{background:#eef4fb !important;font-weight:600}
figure{margin:18px 0;text-align:center}
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
              "".join("<th>%s</th>" % (ZH10.get(l) or ZH7.get(l) or l) for l in t["col_labels"]))]
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
    ks = BENCH_ORDER; labs = [ZH7[b] for b in ks]
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
    ks = BENCH_ORDER; labs = [ZH7[b] for b in ks]
    rows = [("原生 " + tag, f"{bpw:.3f}", raw_scores(tag)) for tag, bpw in NATIVE_LADDER]
    rows += [(k, f"{bpw:.3f}", raw_scores(tag)) for k, tag, bpw in GSQ_QUANTS]
    def mk(title, rows):
        return {"title": title, "c1_name": "系列", "c2_name": "有效位宽", "col_keys": ks, "col_labels": labs,
                "rows": rows, "counts": {k: sum(1 for _, _, c in rows if c.get(k)) for k in ks}, "data_cols": len(ks)}
    return [mk("GSQ-RCO：原始分数", rows)]


def section(H, title, definition, tables, figure, analysis):
    H.append(f"<section><h2>{title}</h2>")
    H.append(f"<p class='def'>{definition}</p>")
    H.append("<h3>原始数据</h3>")
    for t in tables:
        if t.get("note"):
            H.append(f"<p class='nr'>{html.escape(t['note'])}</p>")
        H.append(render_table(t))
    if figure and os.path.exists(figure):
        H.append("<h3>原始数据图</h3>")
        H.append(f"<figure><img src='data:image/png;base64,{b64(figure)}'></figure>")
    if analysis:
        H.append("<h3>分析</h3>")
        H.append(f"<div class='analysis'>{analysis}</div>")
    H.append("</section>")


def main():
    TBL = {t["title"].split(".")[0].strip(): t for t in mktables.build_tables()}
    H = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
         '<title>量化 × 基准分数：逐项报告</title>', f'<style>{CSS}</style></head><body>']
    H.append("<h1>量化 × 基准分数：逐项报告</h1>")

    # ===== 总 =====
    H.append("<h2>总：这个项目是什么，要研究什么</h2>")
    H.append("<div class='lead'>"
             "<b>项目。</b>把本地大模型量化（压到更低比特）之后，它在各项任务上的<b>实际分数</b>会掉多少，"
             "这个“掉多少”又取决于什么。每个可能的影响因素是一个自变量 <b>X</b>（量化位宽、量化方案、"
             "模型规模、KV 缓存精度、采样参数、投机解码草稿深度、思考开关、量化感知训练等），"
             "<b>Y</b> 是基准分数。所有比较都在<b>同一个模型家族内部</b>进行：同一套 base 权重，只换量化文件；"
             "架构与参数量因此天然固定。横轴统一用真实<b>有效位宽</b>（每个权重平均比特数 = 8×文件字节÷参数量），"
             "不使用 Q2/Q3 标称标签。<br><br>"
             "<b>数据。</b>全部来自 <code>experiments.sqlite</code>（唯一数据源）。标准基准 7 个："
             "代码（HumanEval+/MBPP+）、知识（MMLU）、科学（ARC-Challenge）、事实性（TruthfulQA）、"
             "推理（GSM8K）、指令（IFEval）。<br><br>"
             "<b>本页结构。</b>下面每一项研究单列一节，依次给出：① 该研究的 X / Y 定义；② 原始数据表；"
             "③ 原始数据的图（X 在横轴、Y 在纵轴，每个系列一条线或一组柱）；④ 基于这些数据的分析。"
             "最后是显著性与非显著性回顾。缺失写 <code>—</code>，绝不写 0。"
             "</div>")

    secs = [
        ("一、权重量化位宽",
         "X = 有效位宽（bpw，越大即每个权重平均比特越多）；Y = 7 个基准的分数；系列 = 模型家族（同家族=同一套 base 权重，只换量化文件）。",
         [TBL["A"]], fig_A(TBL["A"]),
         "看每格曲线：低比特一端多数家族分数处在低点，<b>Q2→Q3 之间明显抬升</b>，再往上（Q3→Q4→Q5）基本走平。"
         "不同基准抬升幅度差别很大——代码与推理抬升明显，知识、事实性几乎不动。这正是“量化伤害取决于你测哪个基准”的来源。"),
        ("二、模型规模",
         "X = 模型参数量（B）；Y = 基准分数；系列 = 家族 + 量化配方。",
         [TBL["B"]], fig_B(TBL["B"]),
         "同一配方下，参数量越大分数越高；小模型之间的差距通常比大模型之间更大（大模型已接近各自上限）。"),
        ("三、量化方案 / 厂商",
         "X = 量化方案或厂商（同一模型、相近的有效位宽区间内）；Y = 基准分数。",
         [TBL["C"]], fig_C(TBL["C"]),
         "在字节接近的前提下，不同<b>方案</b>（如 IQ 系列 vs K 系列）分数有可测差异；而不同<b>厂商</b>标签基本测不出差异。"
         "所以选量化应比字节/方案，而不是比厂商标签。"),
        ("四、MoE 逐层比特分配",
         "X = 哪些层拿低比特（专家层 vs 其余层），固定同一套 base 权重；Y = 基准分数。",
         [TBL["D"]], fig_D(TBL["D"]),
         "三条柱里，把<b>非专家层</b>压到最低的那条分数最低——哪怕它的总比特最多。因为非专家层（注意力、归一化等）"
         "每个 token 每次前向都用，而单个专家只有部分 token 会走到。"),
        ("五、KV-Cache 量化",
         "X = KV 缓存的精度（f16 / q8_0 / q4_0），固定模型、权重位宽与上下文；Y = 基准分数。",
         [TBL["E"]], fig_E(TBL["E"]),
         "三种精度的柱几乎等高，即在这类任务上测不出差别（上下文约 1k–2k tokens；更长的上下文未覆盖）。"),
        ("六、采样 / 解码参数",
         "X = 采样参数（温度、top_k），固定模型、位宽与上下文；Y = 多语言代码通过率。",
         [TBL["F"]], fig_F(TBL["F"]),
         "温度变化会压低代码分；top_k 在贪心地板附近基本不变（温度 0 时没有分布可截断，属结构事实）。"),
        ("七、投机解码：速度",
         "X = 投机解码草稿深度；Y = 每秒生成 token 数（来自 llama-server 自身计时）；系列 = 模型。",
         [TBL["G1"]], fig_G1(TBL["G1"]),
         "草稿深度越大速度越快，且模型越大收益越大（小模型本身已受内存带宽限制）。"),
        ("八、投机解码：质量",
         "X = 草稿深度；Y = 基准分数；系列 = 模型。",
         [TBL["G2"]], fig_G2(TBL["G2"]),
         "分数随深度几乎不变；其中 MMLU 在每个深度逐位相同（它走对数似然打分，不经过草稿模型），是测量正确的正对照。"),
        ("九、思考开关",
         "X = 是否开启思考（reasoning）；Y = GSM8K 分数；系列 = 模型文件。",
         [TBL["H"]], fig_H(TBL["H"]),
         "开与关的差随模型与预算而定；小预算下开思考反而更低（推理流挤占了答案预算）。主协议统一用“关”。"),
        ("十、量化感知训练（QAT）",
         "X = 该量化文件是否经过 QAT 训练，固定模型尺寸与标称配方；Y = 各基准分数（并给出差值）。",
         qat_tables(), fig_QAT(),
         "所有 Q4 配对里 QAT 与原生基本重合（而 QAT 文件还小 0.44–0.95 bpw）；只有 Q2 配对里 QAT 明显更低。"
         "即 QAT 是“同配方更小体积”的选项，不是质量升级。（附：QAT 文件是 Q4_0 血统，原生是真 K-quant，差值里还混了方案因素。）"),
        ("十一、GSQ-RCO 量化方案",
         "X = 量化方案（第三方 GSQ-RCO vs unsloth 原生阶梯），固定 Qwen3.8-27B；Y = 基准分数。",
         gsq_tables(), fig_GSQ(),
         "GSQ 的星标点落在原生阶梯线上，说明在匹配有效位宽下它与原生不可区分（最近档位与插值两种比法都测不出差异）。"),
        ("十二、扩散式解码（DiffusionGemma）",
         "X = 解码范式（扩散 vs 自回归），对照为同尺寸自回归 gemma-4-26B-A4B；Y = 基准分数。",
         [], None,
         "本机 llama.cpp 不认 <code>diffusion-gemma</code> 架构，处理侧没有数据，因此本项未测（非 0，非 null）。"),
    ]
    for title, defn, tables, fig, analysis in secs:
        section(H, title, defn, tables, fig, analysis)

    # ===== 总（显著性回顾）=====
    H.append("<h2>总：显著性与非显著性回顾</h2>")
    H.append("<p class='def'>显著 = 95% 置信区间不跨 0；测不出 = 区间跨 0（在当前题目数下无法区分，<b>不等于相等</b>）；未测 = 显存/运行时等原因没产出数据。</p>")
    H.append("<table class='recap'><tr><th>研究项</th><th>显著</th><th>测不出</th><th>未测</th></tr>"
             "<tr><td>权重量化位宽</td><td class='sig'>Q2→Q3 多数家族明显抬升；代码/推理幅度最大、知识/事实性最小</td><td>Q3 以上（Q3≈Q4≈Q5）</td><td>—</td></tr>"
             "<tr><td>模型规模</td><td class='sig'>2B 在低比特困难任务整体触底</td><td>大模型/MoE 在低比特已近上限</td><td>激活参数（无受控样本）</td></tr>"
             "<tr><td>量化方案/厂商</td><td class='sig'>同大小下方案有差</td><td>厂商标签</td><td>APEX 无产物</td></tr>"
             "<tr><td>MoE 逐层比特分配</td><td class='sig'>牺牲非专家层大幅掉分</td><td>—</td><td>—</td></tr>"
             "<tr><td>KV-Cache 量化</td><td>—</td><td>f16/q8_0/q4_0 全测不出（短上下文）</td><td>长上下文</td></tr>"
             "<tr><td>采样/解码参数</td><td class='sig'>温度压低代码分</td><td>温度 0 下 top_k；知识类无变化</td><td>—</td></tr>"
             "<tr><td>投机解码：速度</td><td class='sig'>草稿深度提速（模型越大收益越大）</td><td>—</td><td>—</td></tr>"
             "<tr><td>投机解码：质量</td><td>—</td><td>所有深度分数无差别</td><td>—</td></tr>"
             "<tr><td>思考开关</td><td class='sig'>小预算下开思考更低</td><td>多数配置接近</td><td>—</td></tr>"
             "<tr><td>量化感知训练 QAT</td><td class='sig'>Q2 下 QAT 更低</td><td>所有 Q4 配对</td><td>31B（显存不足）</td></tr>"
             "<tr><td>GSQ-RCO 方案</td><td>—</td><td class='sig'>全部差值都测不出</td><td>—</td></tr>"
             "<tr><td>扩散式解码</td><td>—</td><td>—</td><td class='nr'>运行时缺失</td></tr></table>")
    H.append("<p class='def'><b>一句话：</b>量化损失在代码、推理、指令上明显，在选择题知识与事实性上很小；"
             "同文件大小时“换方案”比“数字数”更值得关注。日常选择：<b>至少 Q3，Q3 以上除非能测出收益否则不必多花比特</b>。</p>")
    H.append("</body></html>")
    open("report.html", "w").write("\n".join(H))
    print("wrote report.html", sum(len(x) for x in H), "bytes")


if __name__ == "__main__":
    main()
