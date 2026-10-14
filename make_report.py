#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量化 × 基准分数：逐项报告（全中文，总分总，每项配图）。

唯一数据源 = experiments.sqlite。表格结构由 .wrapup/mktables.py 的 build_tables()
（同样只读数据库）提供；不解析任何 markdown，不读取任何二次转述文件。
运行：python3 make_report.py  ->  report.html
"""
from __future__ import annotations
import base64, html, json, math, os, sqlite3, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, ".wrapup")
from bpw_sensitivity import BENCH, load  # noqa
import mktables  # noqa

# --- 唯一数据源 = experiments.sqlite；下面这些常量只是“哪些 run_tag 属于哪个对照”的设计信息 ---
BPWMAP = json.load(open(".wrapup/bpw_map.json"))   # 有效位宽来源（8×字节÷参数量）
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


def tag_bpw(tag):
    r = CON.execute("SELECT model FROM experiments WHERE run_tag=? LIMIT 1", (tag,)).fetchone()
    return BPWMAP.get(r[0]) if r and r[0] in BPWMAP else None


def pair_delta(a_tag, b_tag):
    """delta = a - b, 题目级 SE 的 95% CI。"""
    a, b = raw_scores(a_tag), raw_scores(b_tag)
    out = {}
    for k in BENCH_ORDER:
        ca, cb = a.get(k), b.get(k)
        if ca and cb and ca[0] is not None and cb[0] is not None:
            pa, na = ca; pb, nb = cb
            se = math.sqrt(pa * (1 - pa) / max(na or 1, 1) + pb * (1 - pb) / max(nb or 1, 1))
            out[k] = (pa - pb, se, pa - pb - 1.96 * se, pa - pb + 1.96 * se)
        else:
            out[k] = None
    return out


def interp_native(bpw):
    pts = sorted((x, tag) for tag, x in NATIVE_LADDER)
    out = {}
    for k in BENCH_ORDER:
        xs, ys = [], []
        for x, tag in pts:
            sc = raw_scores(tag).get(k)
            if sc and sc[0] is not None:
                xs.append(x); ys.append(sc[0])
        out[k] = float(np.interp(bpw, xs, ys)) if len(xs) >= 2 else None
    return out

CON = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)
CANON = [(b, proto) for b, _k, proto in BENCH]
BENCH_ORDER = [b for b, _, _ in BENCH]
ZH7 = {"humaneval-plus": "代码 HumanEval+", "mbpp-plus": "代码 MBPP+", "mmlu": "知识 MMLU",
       "arc_challenge": "科学 ARC-c", "truthfulqa_mc2": "真实 TruthfulQA", "gsm8k": "推理 GSM8K",
       "ifeval": "指令 IFEval"}
FIGDIR = "figures/report"
os.makedirs(FIGDIR, exist_ok=True)

_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
try:
    fm.fontManager.addfont(_CJK)
    plt.rcParams["font.sans-serif"] = [fm.FontProperties(fname=_CJK).get_name(), "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
except Exception:
    pass

# 列名中文（基准保留缩写）
COLZH = {"HumanEval": "代码 HumanEval", "HumanEval+": "代码 HumanEval+", "MBPP": "代码 MBPP",
         "MBPP+": "代码 MBPP+", "MultiPL-E": "多语言代码", "MMLU": "知识 MMLU",
         "ARC-c": "科学 ARC-c", "TruthfulQA": "真实 TruthfulQA", "GSM8K": "推理 GSM8K",
         "IFEval": "指令 IFEval", "code": "代码", "long-ctx": "长上下文", "prose": "散文",
         "code-256": "代码(256)"}


def zh_label(lab):
    return COLZH.get(lab, lab)


def val(cells, k):
    c = cells.get(k)
    return c[0] if c and c[0] is not None else float("nan")


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def save(fig, name):
    p = f"{FIGDIR}/{name}.png"
    fig.tight_layout()
    fig.savefig(p, dpi=135, bbox_inches="tight")
    plt.close(fig)
    return p


# ---------------- figures (all DB-only) ----------------
def fig_slopes():
    zhb = {"humaneval-plus": "代码 HE+", "mbpp-plus": "代码 MBPP+", "mmlu": "知识 MMLU",
           "arc_challenge": "科学 ARC-c", "truthfulqa_mc2": "真实 TruthfulQA",
           "gsm8k": "推理 GSM8K", "ifeval": "指令 IFEval"}
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
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.bar([zhb[b] for b, _ in stat],
           [s for _, s in stat], color="#c0392b")
    for i, (_, s) in enumerate(stat):
        ax.text(i, s + .003, f"{s:.3f}", ha="center", fontsize=10)
    ax.set_ylabel("每 +1 有效位宽的分数变化")
    ax.set_title("同一个量化步长，在不同基准上造成的损失")
    ax.grid(axis="y", alpha=.25)
    return save(fig, "A_slopes")


def fig_size(t):
    benches = [k for k in ("humaneval_plus", "mmlu", "gsm8k") if k in t["col_keys"]]
    series = {}
    for c1, c2, cells in t["rows"]:
        m = mktables.size_value(c2)
        if m <= 0:
            continue
        series.setdefault(c1, []).append((m, [val(cells, b) for b in benches]))
    fig, axes = plt.subplots(1, len(benches), figsize=(4.6 * len(benches), 4), squeeze=False)
    for j, b in enumerate(benches):
        ax = axes[0][j]
        for c1, pts in series.items():
            pts = sorted(pts)
            ax.plot([p[0] for p in pts], [p[1][j] for p in pts], "-o", label=c1, lw=1.3, ms=5)
        ax.set_title(zh_label(mktables.BENCH_LABELS[mktables.BENCH_KEYS.index(b)]))
        ax.set_xlabel("参数量（B）"); ax.grid(alpha=.25)
    axes[0][0].set_ylabel("分数")
    axes[0][-1].legend(fontsize=7)
    fig.suptitle("同量化配方下，模型规模与分数的关系")
    return save(fig, "B_size")


def fig_moe(t):
    benches = t["col_keys"]
    labels = [c2 for _, c2, _ in t["rows"]]
    data = np.array([[val(cells, b) for b in benches] for _, _, cells in t["rows"]])
    fig, ax = plt.subplots(figsize=(11, 4.6))
    x = np.arange(len(labels)); w = .8 / len(benches)
    for j, b in enumerate(benches):
        ax.bar(x + (j - len(benches) / 2) * w, data[:, j], w, label=zh_label(t["col_labels"][j]))
    ax.set_xticks(x); ax.set_xticklabels([l.replace(" · ", "\n") for l in labels], fontsize=8)
    ax.set_ylabel("分数"); ax.legend(fontsize=7, ncol=2); ax.grid(axis="y", alpha=.25)
    ax.set_title("MoE 逐层比特分配：同权重，只换“哪些层拿低比特”")
    return save(fig, "D_moe")


def fig_scheme(t):
    benches = [k for k in ("humaneval_plus", "mmlu") if k in t["col_keys"]]
    groups = {}
    for c1, c2, cells in t["rows"]:
        groups.setdefault(c1, []).append((c2, cells))
    n = len(groups)
    fig, axes = plt.subplots(1, max(1, n), figsize=(5.2 * max(1, n), 4.2), squeeze=False)
    for ax, (c1, items) in zip(axes[0], groups.items()):
        x = np.arange(len(items)); w = .8 / max(1, len(benches))
        for j, b in enumerate(benches):
            ax.bar(x + (j - len(benches) / 2) * w, [val(cells, b) for _, cells in items], w,
                   label=mktables.BENCH_LABELS[mktables.BENCH_KEYS.index(b)])
        ax.set_xticks(x); ax.set_xticklabels([c for c, _ in items], rotation=20, ha="right", fontsize=8)
        ax.set_title(c1, fontsize=9); ax.grid(axis="y", alpha=.25)
        axes[0][0].set_ylabel("分数")
    axes[0][-1].legend(fontsize=8)
    fig.suptitle("同一位宽区间内：不同量化方案 / 厂商的分数")
    return save(fig, "C_scheme")


def fig_kv(t):
    benches = t["col_keys"]
    keep = ("f16/f16", "q8_0/q8_0", "q4_0/q4_0")
    rows = [(c2, cells) for c1, c2, cells in t["rows"] if c2 in keep and "ctx8192" in c1]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    x = np.arange(len(benches)); w = .8 / max(1, len(rows))
    for k, (lab, cells) in enumerate(rows):
        ax.bar(x + (k - len(rows) / 2) * w, [val(cells, b) for b in benches], w, label=lab)
    ax.set_xticks(x); ax.set_xticklabels([zh_label(l) for l in t["col_labels"]], fontsize=8)
    ax.set_ylabel("分数"); ax.legend(); ax.grid(axis="y", alpha=.25)
    ax.set_title("KV-Cache 量化：f16 / q8_0 / q4_0")
    return save(fig, "E_kv")


def fig_sampling(t):
    mk = t["col_keys"].index("multipl_e")
    temp, topk = {}, {}
    for c1, c2, cells in t["rows"]:
        try:
            x = float(c2)
        except ValueError:
            continue
        (temp if "temperature" in c1 else topk)[x] = val(cells, "multipl_e")
    fig, ax = plt.subplots(figsize=(8, 4.4))
    if temp:
        k = sorted(temp); ax.plot([str(x) for x in k], [temp[x] for x in k], "-o", label="温度")
    if topk:
        k = sorted(topk); ax.plot([str(x) for x in k], [topk[x] for x in k], "-s", label="top_k")
    ax.set_xlabel("取值"); ax.set_ylabel("多语言代码 通过率")
    ax.legend(fontsize=9); ax.grid(alpha=.25)
    ax.set_title("采样参数对代码分数的影响（2B）")
    return save(fig, "F_sampling")


def fig_speed(t):
    keys = t["col_keys"]
    series = {}
    for c1, c2, cells in t["rows"]:
        model = c1.split(" · ")[0]
        try:
            d = int(c2)
        except ValueError:
            continue
        series.setdefault(model, []).append((d, val(cells, keys[-1])))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for model, pts in series.items():
        pts = sorted(pts)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "-o", label=model, ms=4)
    ax.set_xlabel("草稿深度"); ax.set_ylabel("每秒生成 token（%s）" % zh_label(keys[-1]))
    ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("投机解码：草稿深度对速度的影响")
    return save(fig, "G1_speed")


def fig_specq(t):
    he = t["col_keys"].index("humaneval") if "humaneval" in t["col_keys"] else None
    mm = t["col_keys"].index("mmlu") if "mmlu" in t["col_keys"] else None
    series = {}
    for c1, c2, cells in t["rows"]:
        model = c1.split(" · ")[0]
        try:
            d = int(c2)
        except ValueError:
            continue
        series.setdefault(model, []).append((d, val(cells, "humaneval"), val(cells, "mmlu")))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    for model, pts in series.items():
        pts = sorted(pts)
        axes[0].plot([p[0] for p in pts], [p[1] for p in pts], "-o", label=model, ms=4)
        axes[1].plot([p[0] for p in pts], [p[2] for p in pts], "-o", label=model, ms=4)
    axes[0].set_title("代码 HumanEval"); axes[1].set_title("知识 MMLU（逐位相同）")
    for a in axes:
        a.set_xlabel("草稿深度"); a.set_ylabel("分数"); a.grid(alpha=.25)
    axes[1].legend(fontsize=7)
    fig.suptitle("投机解码：草稿深度对分数的影响")
    return save(fig, "G2_quality")


def fig_thinking(t):
    gk = "gsm8k"
    series = {}
    for c1, c2, cells in t["rows"]:
        mode = "on" if "on" in c2 else "off"
        series.setdefault(c1, {})[mode] = val(cells, gk)
    models = [m for m in series if "on" in series[m] and "off" in series[m]]
    fig, ax = plt.subplots(figsize=(11, 4.3))
    x = np.arange(len(models)); w = .4
    ax.bar(x - w / 2, [series[m]["off"] for m in models], w, label="思考关")
    ax.bar(x + w / 2, [series[m]["on"] for m in models], w, label="思考开", color="#c0392b")
    ax.set_xticks(x); ax.set_xticklabels(models, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("推理 GSM8K 分数"); ax.legend(); ax.grid(axis="y", alpha=.25)
    ax.set_title("思考开关对 GSM8K 的影响")
    return save(fig, "H_thinking")


def fig_qat():
    zhb = {"humaneval-plus": "代码HE+", "mbpp-plus": "代码MBPP+", "mmlu": "知识MMLU",
           "arc_challenge": "科学ARC", "truthfulqa_mc2": "真实TQA", "gsm8k": "推理GSM8K", "ifeval": "指令IFEval"}
    deltas = [pair_delta(q, n) for _, _, q, n in QAT_PAIRS]
    fig, axes = plt.subplots(1, len(QAT_PAIRS), figsize=(3.4 * len(QAT_PAIRS), 4.2), squeeze=False)
    for ax, (label, recipe, _q, _n), dl in zip(axes[0], QAT_PAIRS, deltas):
        bs = [b for b in BENCH_ORDER if dl.get(b)]
        vals = [dl[b][0] for b in bs]
        sig = [(dl[b][2] > 0 or dl[b][3] < 0) for b in bs]
        ax.bar(range(len(bs)), vals, color=["#c0392b" if s else "#95a5a6" for s in sig])
        ax.axhline(0, color="#333", lw=.8)
        ax.set_xticks(range(len(bs))); ax.set_xticklabels([zhb[b] for b in bs], rotation=60, ha="right", fontsize=7)
        ax.set_title(f"{label}\n{recipe}", fontsize=9); ax.grid(axis="y", alpha=.25)
        if ax is axes[0][0]:
            ax.set_ylabel("QAT − 原生 的分数差")
    fig.suptitle("量化感知训练 vs 原生（红=95% 区间不跨 0）")
    return save(fig, "QAT")


def fig_gsq():
    zhb = {"humaneval-plus": "代码HE+", "mmlu": "知识MMLU", "gsm8k": "推理GSM8K"}
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for b in ("humaneval-plus", "mmlu", "gsm8k"):
        xs, ys = [], []
        for tag, bpw in NATIVE_LADDER:
            sc = raw_scores(tag).get(b)
            xs.append(bpw); ys.append(sc[0] if sc and sc[0] is not None else np.nan)
        ax.plot(xs, ys, "-o", label="原生 " + zhb[b])
        for k, tag, bpw in GSQ_QUANTS:
            g = raw_scores(tag).get(b)
            if g and g[0] is not None:
                ax.scatter([bpw], [g[0]], marker="*", s=170, zorder=5, label=f"{k} {zhb[b]}")
    ax.set_xlabel("有效位宽"); ax.set_ylabel("分数")
    ax.legend(fontsize=8); ax.grid(alpha=.25)
    ax.set_title("GSQ-RCO（星）与原生阶梯（线）")
    return save(fig, "GSQ")


# ---------------- HTML ----------------
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
.cover td{background:#eef4fb !important;font-weight:600}
figure{margin:18px 0;text-align:center}
img{width:100%;max-width:1250px;border:1px solid var(--bd);border-radius:6px}
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
              "".join("<th>%s</th>" % zh_label(l) for l in t["col_labels"]))]
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
            elif isinstance(c[1], str):
                tds.append("<td>%.4f <span class='nr'>%s</span></td>" % (c[0], html.escape(c[1])))
            else:
                tds.append("<td>%.4f <span class='nr'>(%s)</span></td>" % (c[0], c[1] or 0))
        out.append("<tr><td>%s</td><td>%s</td>%s</tr>" % (html.escape(c1), html.escape(c2), "".join(tds)))
    out.append("</table></div>")
    return "\n".join(out)


def raw_scores(tag):
    out = {}
    for b, proto in CANON:
        r = CON.execute("SELECT _score,n_items FROM experiments WHERE run_tag=? AND protocol=? AND _bench=?",
                        (tag, proto, b)).fetchone()
        out[b] = (r[0], r[1]) if r and r[0] is not None else None
    return out


def qat_tables():
    ks = BENCH_ORDER; labs = [ZH7[b] for b in ks]
    rows = []
    for label, recipe, q, n in QAT_PAIRS:
        for which, tag in (("QAT", q), ("原生", n)):
            bpw = tag_bpw(tag)
            rows.append((f"{label} {recipe} {which}", f"{bpw:.3f}" if bpw else "—", raw_scores(tag)))
    t1 = {"title": "量化感知训练：原始分数", "c1_name": "系列", "c2_name": "有效位宽",
          "col_keys": ks, "col_labels": labs, "rows": rows,
          "counts": {k: sum(1 for _, _, c in rows if c.get(k)) for k in ks}, "data_cols": len(ks)}
    rows2 = []
    for label, recipe, q, n in QAT_PAIRS:
        dl = pair_delta(q, n); cells = {}
        for b in ks:
            c = dl.get(b)
            if c:
                cells[b] = (c[0], f"[{c[2]:+.3f},{c[3]:+.3f}]")
        rows2.append((f"{label} {recipe}", "QAT − 原生", cells))
    t2 = {"title": "量化感知训练：差值", "c1_name": "系列", "c2_name": "差值",
          "col_keys": ks, "col_labels": labs, "rows": rows2,
          "counts": {k: sum(1 for _, _, c in rows2 if c.get(k)) for k in ks}, "data_cols": len(ks)}
    return [t1, t2]


def gsq_tables():
    ks = BENCH_ORDER; labs = [ZH7[b] for b in ks]
    rows = [("原生 " + tag, f"{bpw:.3f}", raw_scores(tag)) for tag, bpw in NATIVE_LADDER]
    rows += [(k, f"{bpw:.3f}", raw_scores(tag)) for k, tag, bpw in GSQ_QUANTS]
    t1 = {"title": "GSQ-RCO：原始分数", "c1_name": "系列", "c2_name": "有效位宽",
          "col_keys": ks, "col_labels": labs, "rows": rows,
          "counts": {k: sum(1 for _, _, c in rows if c.get(k)) for k in ks}, "data_cols": len(ks)}
    nearest_all = {k: min(NATIVE_LADDER, key=lambda r: abs(r[1] - bpw))[0] for k, _t, bpw in GSQ_QUANTS}
    rows2 = []
    for k, tag, bpw in GSQ_QUANTS:
        dl = pair_delta(tag, nearest_all[k]); cells = {}
        for b in ks:
            c = dl.get(b)
            if c:
                cells[b] = (c[0], f"[{c[2]:+.3f},{c[3]:+.3f}]")
        rows2.append((k + " vs 最近原生", "GSQ − 原生", cells))
    for k, tag, bpw in GSQ_QUANTS:
        interp = interp_native(bpw); cells = {}
        g = raw_scores(tag)
        for b in ks:
            if g.get(b) and interp.get(b) is not None:
                d = g[b][0] - interp[b]
                cells[b] = (d, "插值")
        rows2.append((k + " vs 插值原生", "GSQ − 原生", cells))
    t2 = {"title": "GSQ-RCO：差值", "c1_name": "系列", "c2_name": "差值",
          "col_keys": ks, "col_labels": labs, "rows": rows2,
          "counts": {k: sum(1 for _, _, c in rows2 if c.get(k)) for k in ks}, "data_cols": len(ks)}
    return [t1, t2]


def render_section(H, title, intro, tables, figure):
    H.append(f"<section><h2>{title}</h2>")
    H.append(f"<p class='intro'>{intro}</p>")
    for t in tables:
        if t.get("note"):
            H.append(f"<p class='intro'>{html.escape(t['note'])}</p>")
        H.append(render_table(t))
    if figure and os.path.exists(figure):
        H.append(f"<figure><img src='data:image/png;base64,{b64(figure)}'></figure>")
    H.append("</section>")


def main():
    TBL = {t["title"].split(".")[0].strip(): t for t in mktables.build_tables()}
    specs = [
        ("一、权重量化位宽", "X = 量化位宽。固定同一模型家族，只换量化文件；横轴用真实有效位宽（8×字节÷参数量）。下表每个家族给出它在各档位上的原始分数，括号内为题目数。",
         [TBL["A"]], fig_slopes()),
        ("二、模型规模", "X = 参数量。固定量化配方，比较不同大小的模型。", [TBL["B"]], fig_size(TBL["B"])),
        ("三、量化方案 / 厂商", "X = 量化方案或厂商。固定模型与相近的有效位宽区间。", [TBL["C"]], fig_scheme(TBL["C"])),
        ("四、MoE 逐层比特分配", "X = 哪些层拿低比特（专家层 vs 其余层）。固定同一套 base 权重。", [TBL["D"]], fig_moe(TBL["D"])),
        ("五、KV-Cache 量化", "X = KV 缓存精度。固定模型、权重位宽与上下文。", [TBL["E"]], fig_kv(TBL["E"])),
        ("六、采样 / 解码参数", "X = 采样参数（温度、top_k）。固定模型、位宽与上下文。", [TBL["F"]], fig_sampling(TBL["F"])),
        ("七、投机解码：速度", "X = 草稿深度。固定模型与上下文，单位是每秒生成的 token 数。", [TBL["G1"]], fig_speed(TBL["G1"])),
        ("八、投机解码：质量", "X = 草稿深度。同一次运行，看分数是否受损。", [TBL["G2"]], fig_specq(TBL["G2"])),
        ("九、思考开关", "X = 是否开启思考（reasoning）。固定模型文件。", [TBL["H"]], fig_thinking(TBL["H"])),
        ("十、量化感知训练（QAT）", "X = 是否经过 QAT 训练。固定模型尺寸与标称配方。", qat_tables(), fig_qat()),
        ("十一、GSQ-RCO 量化方案", "X = 量化方案（第三方 GSQ-RCO vs 原生阶梯）。固定 base 模型，同时对比“最近原生档位”和“按位宽插值的原生”。", gsq_tables(), fig_gsq()),
        ("十二、扩散式解码（DiffusionGemma）", "X = 解码范式（扩散 vs 自回归）。本机 llama.cpp 不认 <code>diffusion-gemma</code> 架构，处理侧无数据；对照侧为同尺寸自回归 gemma-4-26B-A4B。", [], None),
    ]
    H = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
         '<title>量化 × 基准分数：逐项报告</title>', f'<style>{CSS}</style></head><body>']
    H.append("<h1>量化 × 基准分数：逐项报告</h1>")
    H.append("<h2>总：这个研究要回答什么</h2>")
    H.append("<div class='lead'>问题：<b>把大模型量化压缩之后，它在各项任务上的实际分数会掉多少，又取决于什么。</b>"
             "做法是把每个可能的影响因素当成自变量 <b>X</b>（量化位宽、量化方案、模型规模、KV 缓存、采样参数、"
             "投机解码深度、思考开关……），基准分数当成因变量 <b>Y</b>；所有比较都在<b>同一模型家族内部</b>进行，"
             "只换量化文件，架构与参数量天然固定。<br><br>"
             "横轴统一用真实<b>有效位宽</b>（每个权重平均比特数 = 8×文件字节÷参数量），不用 Q2/Q3 标称标签。"
             "全部数据来自 <code>experiments.sqlite</code>（唯一数据源），本页由 <code>make_report.py</code> 直接生成。</div>")
    for title, intro, tables, fig in specs:
        render_section(H, title, intro, tables, fig)
    H.append("<h2>总：显著性回顾</h2>")
    H.append("<p class='intro'>按“显著 / 测不出 / 未测”归类。测不出指 95% 区间跨过 0，<b>不等于相等</b>。</p>")
    H.append("<table class='recap'><tr><th>研究项</th><th>显著</th><th>测不出（不显著）</th><th>未测</th></tr>"
             "<tr><td>权重量化位宽</td><td class='sig'>Q2→Q3 多数家族显著为正；GSM8K/代码损失最大，TruthfulQA 最小</td><td>Q3 以上</td><td>—</td></tr>"
             "<tr><td>模型规模</td><td class='sig'>2B 在 Q2 困难任务整体触底</td><td>大模型/MoE 在 Q2 已接近上限</td><td>—</td></tr>"
             "<tr><td>量化方案 / 厂商</td><td class='sig'>同大小下 IQ 优于 K</td><td>厂商标签</td><td>—</td></tr>"
             "<tr><td>MoE 逐层比特分配</td><td class='sig'>牺牲非专家层大幅掉分</td><td>—</td><td>—</td></tr>"
             "<tr><td>KV-Cache 量化</td><td>—</td><td>f16/q8_0/q4_0 全部测不出</td><td>—</td></tr>"
             "<tr><td>采样 / 解码参数</td><td class='sig'>温度压低代码分</td><td>温度 0 下 top_k；知识类基准无变化</td><td>—</td></tr>"
             "<tr><td>投机解码：速度</td><td class='sig'>草稿深度提速，模型越大收益越大</td><td>—</td><td>—</td></tr>"
             "<tr><td>投机解码：质量</td><td>—</td><td>所有深度分数无差别</td><td>—</td></tr>"
             "<tr><td>思考开关</td><td class='sig'>小预算下开思考更低</td><td>多数配置接近</td><td>—</td></tr>"
             "<tr><td>量化感知训练 QAT</td><td class='sig'>Q2 下 QAT 更差</td><td>所有 Q4 配对</td><td>31B 显存不足</td></tr>"
             "<tr><td>GSQ-RCO 方案</td><td>—</td><td class='sig'>28 个差值全部测不出</td><td>—</td></tr>"
             "<tr><td>扩散式解码</td><td>—</td><td>—</td><td class='nr'>运行时缺失</td></tr></table>")
    H.append("<p class='intro'><b>一句话：</b>量化损失在代码、推理、指令上明显，在选择题知识与事实性问答上很小；"
             "同文件大小时“换方案”比“数字数”更值得关注。日常选择：<b>至少 Q3，Q3 以上除非能测出收益否则不必多花比特</b>。</p>")
    H.append("</body></html>")
    open("report.html", "w").write("\n".join(H))
    print("wrote report.html", sum(len(x) for x in H), "bytes")


if __name__ == "__main__":
    main()
