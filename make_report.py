#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地模型设置选择对基准分数的影响：逐项报告。

结构：研究概述 → 每一项研究一节（定义 / 原始数据 / 原始数据图 / 分析）→ 结论与显著性总结。
每张图独立成图、带图例；表头全中文。唯一数据源 = experiments.sqlite。
运行：python3 make_report.py  ->  report.html
"""
from __future__ import annotations
import base64, collections, glob, html, json, math, os, re, sqlite3, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, ".wrapup")
sys.path.insert(0, "report_inputs")
import eval_status  # noqa
import mktables  # noqa

CON = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)
FIGDIR = "figures/report"
os.makedirs(FIGDIR, exist_ok=True)

# CJK 字体是被复现条件的一部分：换成别的字体，每张图的字形与度量都变，报告就不再逐字节相同。
# 所以它不静默回退——缺了就失败并说清装什么，且核对 sha256，字体换了版本也当场说出来。
CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
CJK_FONT_SHA256 = "b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a"
CJK_FONT_PACKAGE = "fonts-noto-cjk"


def _require_cjk_font():
    """字体存在且 sha256 匹配；否则终止并给出安装命令与期望哈希。"""
    import hashlib
    if not os.path.exists(CJK_FONT):
        raise SystemExit(
            f"报告无法构建：缺少 CJK 字体 {CJK_FONT}\n"
            f"  安装：sudo apt-get install -y {CJK_FONT_PACKAGE}\n"
            f"  期望 sha256：{CJK_FONT_SHA256}\n"
            f"  不静默换字体：换字体后每张图都变，报告不再逐字节可复现。")
    digest = hashlib.sha256(open(CJK_FONT, "rb").read()).hexdigest()
    if digest != CJK_FONT_SHA256:
        raise SystemExit(
            f"报告无法构建：CJK 字体版本不是被复现的那个\n"
            f"  文件：{CJK_FONT}\n  实际 sha256：{digest}\n  期望 sha256：{CJK_FONT_SHA256}\n"
            f"  要么装回 {CJK_FONT_PACKAGE} 的对应版本，要么确认新字体后同时更新本常量与 RESULT.md。")
    return digest


CJK_FONT_DIGEST = _require_cjk_font()
fm.fontManager.addfont(CJK_FONT)
plt.rcParams["font.sans-serif"] = [fm.FontProperties(fname=CJK_FONT).get_name(), "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 全局图表风格：统一字号 / 网格 / 边框，保证全文观感一致
try:
    plt.rcParams.update({
        "font.size": 11, "axes.titlesize": 12.5, "axes.labelsize": 11,
        "axes.grid": True, "grid.alpha": .25, "grid.linewidth": .6,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.framealpha": .92, "legend.fontsize": 8.5,
        "figure.dpi": 130, "savefig.dpi": 130, "savefig.bbox": "tight",
    })
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
    "mbpp_plus": "代码 MBPP+", "multipl_e": "多语言代码",
    "multipl_e_cpp": "多语言代码 C++", "multipl_e_py": "多语言代码 Python",
    "MultiPL-E C++": "多语言代码 C++", "MultiPL-E Python": "多语言代码 Python",
    "mmlu": "知识 MMLU",
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


def save(fig, name, caption=None):
    fig.tight_layout()
    p = f"{FIGDIR}/{name}.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return (p, caption) if caption else p


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


# ---------- 模型来源 / 复现信息 ----------
# /home/z/hf/<basename>.gguf 是 exp.py 实际加载的入口；它是 mscache 或 HF 缓存快照的
# 符号链接。解析符号链接目标即可知道“这份 gguf 到底来自哪个机构 / 哪个仓库”。
HFROOT = "/home/z/hf"
_VENDOR_FALLBACK = [
    ("UD-TQ", "unsloth (Unsloth Dynamic)"), ("TSL", "unsloth"), ("UD-", "unsloth (Unsloth Dynamic)"),
    ("it-qat", "unsloth (QAT)"), ("m55", "本地自建 (m55 补丁)"), ("GSQ-RCO", "ISTA-DASLab"),
    ("Ternary", "prism-ml / dealignai"), ("Bonsai", "prism-ml / dealignai"),
]


def _parse_origin(target):
    """从符号链接目标推 (机构, 仓库, 相对路径)。"""
    if "/mscache/" in target:
        rel = target.split("/mscache/", 1)[1]
        parts = rel.split("/")
        org = parts[0]
        repo = parts[1] if len(parts) >= 3 else org
        return org, repo, "mscache/" + rel
    for part in target.split("/"):
        if part.startswith("models--"):
            bits = part.split("--")
            org = bits[1] if len(bits) > 1 else part
            repo = bits[2] if len(bits) > 2 else org
            return org, repo, part
    return None, None, target


def _load_provenance():
    prov = {}
    try:
        names = os.listdir(HFROOT)
    except OSError:
        return prov
    for fn in names:
        if fn.endswith(".gguf"):
            prov[fn] = _parse_origin(os.path.realpath(os.path.join(HFROOT, fn)))
    return prov


PROV = _load_provenance()


def model_meta(model):
    """一个 gguf 的展示元数据（家族 / 规模 / 量化 / 有效位宽 / QAT / 来源）。"""
    base = model if model.endswith(".gguf") else model + ".gguf"
    stem, quant = mktables.split_quant(base)
    fam = mktables.family_of(base)
    _, size = mktables.lineage_and_size(base)
    if size == fam:
        size = "—"
    org, repo, rel = PROV.get(base, (None, None, None))
    if org is None:
        vendor = "未知（本地文件，未找到下载来源）"
        for pat, name in _VENDOR_FALLBACK:
            if pat in base:
                vendor = name
                break
    else:
        vendor = org
    qat = "是" if ("qat" in base.lower() or "-qat-" in base.lower()) else "否"
    return {
        "file": base, "family": fam, "size": size, "quant": quant or "—",
        "bpw": ("%.3f" % BPWMAP[base]) if base in BPWMAP else "—",
        "qat": qat, "vendor": vendor, "repo": repo or "—", "path": rel or "—",
    }


def repro_rows(tables):
    """汇总一组表用到的全部 gguf（按文件排序，去重）。"""
    seen, out = set(), []
    for t in tables:
        for models in t.get("row_models", []) or []:
            for m in models:
                if m and m not in seen:
                    seen.add(m)
                    out.append(model_meta(m))
    return sorted(out, key=lambda d: (d["family"], d["bpw"]))


FIXED_NOTE = ("<b>固定条件（除本节的“变化轴”外全部一致）：</b>同一台 llama-server（本机 llama.cpp 构建）+ 同一个模型文件；"
              "固定 chat 模板、上下文大小、贪心解码（除非该节把采样当变量）、思考关。"
              "标准基准协议：HumanEval+/MBPP+ = <code>evalplus-0.3.1-openai-chat-greedy-plus</code>；"
              "MMLU/ARC-c/TruthfulQA = <code>lmeval-0.4.13-gguf-shim-reasoning-off</code>；"
              "GSM8K/IFEval = <code>lmeval-0.4.13-chat-reasoning-off</code>；"
              "多语言代码 = MultiPL-E 原始贪心 768。<br>"
              "<b>有效位宽</b> = 8 × 文件字节数 ÷ 参数量（真实值，非厂商标称档位）。")


def render_repro(rows, title="用到的模型文件与来源（复现用）"):
    if not rows:
        return ""
    h = [f"<div class='repro'><div class='repro-h'>{title}</div>",
         f"<div class='fixed'>{FIXED_NOTE}</div>",
         "<div class='scroll'><table>",
         "<tr><th>模型文件（gguf，实际加载项）</th><th>家族</th><th>规模</th><th>量化方案</th>"
         "<th>有效位宽</th><th>QAT</th><th>量化发布方</th><th>GGUF 仓库</th>"
         "<th>测量时的加载路径（采集机上已不存在，不是本机文件）</th></tr>"]
    for d in rows:
        h.append("<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                 "<td>%s</td><td>%s</td><td>%s</td><td class='nr'>%s</td></tr>"
                 % (html.escape(d["file"]), html.escape(d["family"]), html.escape(str(d["size"])),
                    html.escape(str(d["quant"])), d["bpw"], d["qat"],
                    html.escape(str(d["vendor"])), html.escape(str(d["repo"])),
                    html.escape(str(d["path"]))))
    h.append("</table></div></div>")
    return "\n".join(h)


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


# ============================ 视觉样式系统 ============================
# 设计原则（全文统一）：
#  1. 颜色编码“品牌 / 血统”(brand)：同色 = 同族，跨所有图一致。
#  2. 线型与标记编码“族内变体”（模型尺寸 / 量化配方）：同色不同形 = 同族不同配置。
#  3. 族数很多的轴（有效位宽、模型规模）按血统拆成小面板，避免多线交缠。
#  4. 每个数据点带 ±1.96·SE 误差棒（SE = √(p(1-p)/n)），可直接读显著性。
#  5. 关键点直接标数值 / 线端直接标注，尽量不依赖大图例。
BRAND_COLOR = {
    "Qwen": "#1f77b4", "gemma": "#d62728", "granite": "#2ca02c",
    "GLM": "#9467bd", "LFM": "#ff7f0e", "Llama": "#17becf",
    "MiniCPM": "#8c564b", "NVIDIA": "#7f7f7f", "Ornith": "#e377c2",
    "Phi": "#bcbd22", "Ternary": "#111111",
}
_FALLBACK = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
             "#17becf", "#8c564b", "#7f7f7f", "#e377c2", "#bcbd22", "#111111"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "<", ">", "*", "h", "8"]
LINESTYLES = ["-", "--", "-.", ":"]
SIZE_TOK = re.compile(
    r"[-_](?:E\d+(?:\.\d+)?B|\d+(?:\.\d+)?B(?:-A\d+(?:\.\d+)?B)?)(?=$|[-_])", re.I)


def brand_of(name):
    m = re.match(r"^[A-Za-z]+", name)
    return m.group(0) if m else name


def brand_color(name):
    b = brand_of(name)
    if b in BRAND_COLOR:
        return BRAND_COLOR[b]
    return _FALLBACK[sum(map(ord, b)) % len(_FALLBACK)]


def lineage_root(name):
    """去掉“@ 配方”、去掉尺寸 token、去掉 -it-qat，得到血统根名。"""
    s = name.split(" @ ")[0].split(" · ")[0]
    s = re.sub(r"[-_]it[-_]qat$", "", s)
    m = SIZE_TOK.search(s)
    if m:
        s = s[:m.start()].rstrip("-_")
    return s or name


def variant_of(name, root):
    v = name.split(" @ ")[0].split(" · ")[0]
    v = v[len(root):].strip("-_") if v.startswith(root) else v
    return v or name


def _se(score, n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return 0.0
    if n <= 0:
        return 0.0
    return math.sqrt(max(score * (1 - score), 0.0) / n)


def _mix(hexc, target, f):
    r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
    return "#%02x%02x%02x" % (round(r + (target[0] - r) * f),
                              round(g + (target[1] - g) * f),
                              round(b + (target[2] - b) * f))


def shade(hexc, f):
    """f>0 变浅，f<0 变深。"""
    return _mix(hexc, (255, 255, 255), f) if f >= 0 else _mix(hexc, (0, 0, 0), -f)


def shade_run(base, i, n):
    """同品牌内第 i/n 个变体的颜色（越靠后越浅，同色系仍可区分）。"""
    return base if n <= 1 else shade(base, 0.5 * i / (n - 1))


def _end_label(ax, x, y, text, color, fs=7.2, dx=5, dy=0):
    ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points",
                fontsize=fs, color=color, va="center", ha="left")


def _style_axes(ax, xlabel=None, ylabel=None, title=None):
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.grid(alpha=.25, lw=.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _bps_note():
    return "误差棒 = 95% 置信区间（由每题 0/1 结果计算）。"


# ---------- A 有效位宽：按家族拆成小面板 ----------
def fig_A(t):
    out = []
    roots = sorted({lineage_root(c1) for c1, _, _ in t["rows"]},
                   key=lambda r: (brand_of(r), r))
    ncol = 4
    nrow = math.ceil(len(roots) / ncol)
    for k in t["col_keys"]:
        if t["counts"].get(k, 0) == 0:
            continue
        # byroot[root] = [(家族名, [(bpw, 分数, SE), ...]), ...]：root 内可能含多个尺寸
        byroot = collections.OrderedDict()
        for c1, c2, cells in t["rows"]:
            c = cells.get(k)
            if not c or c[0] is None:
                continue
            try:
                x = float(c2.split()[0])
            except ValueError:
                continue
            byroot.setdefault(lineage_root(c1), collections.OrderedDict()).setdefault(
                c1, []).append((x, c[0], _se(c[0], c[1])))
        if not byroot:
            continue
        fig, axes = plt.subplots(nrow, ncol, figsize=(3.9 * ncol, 2.95 * nrow),
                                 sharex=True, sharey=True)
        axes = np.atleast_1d(axes).ravel()
        for ax in axes:
            ax.set_visible(False)
        for i, r in enumerate(roots):
            if r not in byroot:
                continue
            ax = axes[i]
            ax.set_visible(True)
            base = brand_color(r)
            members = byroot[r]
            nser = len(members)
            ax.axvspan(3.0, 4.0, color="#f2b134", alpha=.12, zorder=0)
            for j, (name, pts) in enumerate(members.items()):
                col = shade_run(base, j, nser)
                pts = sorted(pts)
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                ax.plot(xs, ys, "-", color=col, lw=1.5, alpha=.95, zorder=2)
                for x, y, e in pts:
                    ax.errorbar([x], [y], yerr=[1.96 * e], fmt=MARKERS[j % len(MARKERS)],
                                ms=6.2, color=col, lw=0, elinewidth=1.1,
                                capsize=2.5, zorder=3)
                if nser > 1:
                    _end_label(ax, xs[-1], ys[-1], variant_of(name, r), col,
                               dy=(7 if j % 2 == 0 else -7))
            ax.set_title(r, fontsize=10, color=shade(base, -0.12), pad=6)
            ax.set_ylim(-0.04, 1.05)
            ax.grid(alpha=.22, lw=.6)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            if i % ncol == 0:
                ax.set_ylabel("基准分数", fontsize=9)
            if i >= len(roots) - ncol:
                ax.set_xlabel("有效位宽", fontsize=9)
        fig.suptitle(f"{LBL.get(k, k)}：基准分数 随 有效位宽（按家族拆开）",
                     fontsize=13.5, y=1.0)
        out.append(save(fig, f"A_{k}",
                        caption="每格一个模型家族；横轴 = 该家族各量化文件的有效位宽。"
                                "一格内若有多条线，用颜色深浅 / 标记区分尺寸或配方（线端标注）。"
                                "若同一家族同时有 UD 动态与非 UD 原生 K 文件，已拆成不同系列（不会连成一条曲线）。"
                                "黄色带 = 约 3–4 比特/权重的“拐点”区间。" + _bps_note()))
    return out


# ---------- B 模型规模：颜色=家族，线型/标记=配方 ----------
def fig_B(t):
    out = []
    for k in t["col_keys"]:
        if t["counts"].get(k, 0) == 0:
            continue
        series = {}
        for c1, c2, cells in t["rows"]:
            c = cells.get(k)
            if not c or c[0] is None:
                continue
            x = mktables.size_value(c2)
            if x is None:
                continue
            series.setdefault(c1, []).append((x, c[0], _se(c[0], c[1])))
        if not series:
            continue
        recipes = sorted({s.split(" @ ")[-1] for s in series})
        fig, ax = plt.subplots(figsize=(10.4, 5.2))
        for s in sorted(series):
            root = lineage_root(s)
            rec = s.split(" @ ")[-1]
            col = brand_color(root)
            ri = recipes.index(rec)
            pts = sorted(series[s])
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            es = [1.96 * p[2] for p in pts]
            ax.errorbar(xs, ys, yerr=es, color=col, marker=MARKERS[ri % len(MARKERS)],
                        ls=LINESTYLES[ri % len(LINESTYLES)], ms=6, lw=1.7,
                        capsize=2.5, elinewidth=1, label=s, zorder=3)
        _style_axes(ax, "模型参数量（B）", "基准分数",
                    f"{LBL.get(k, k)}：基准分数 随 模型规模（同配方）")
        ax.legend(fontsize=7.6, loc="center left", bbox_to_anchor=(1.01, 0.5),
                  framealpha=.92)
        out.append(save(fig, f"B_{k}",
                        caption="颜色 = 家族；线型 / 标记 = 量化配方。同一配方连成一线，"
                                "直接看规模效应。" + _bps_note()))
    return out


# ---------- C 量化方案 / 厂商：分组柱 ----------
def fig_C(t):
    from matplotlib.patches import Patch
    out = []
    for k in t["col_keys"]:
        if t["counts"].get(k, 0) == 0:
            continue
        clusters = collections.OrderedDict()
        for c1, c2, cells in t["rows"]:
            c = cells.get(k)
            if not c or c[0] is None:
                continue
            clusters.setdefault(c1, []).append((c2, c[0], _se(c[0], c[1])))
        if not clusters:
            continue
        fig, ax = plt.subplots(figsize=(10.8, 5.6))
        pos = 0.0
        xtick, xlab, gsep, cats, gpos, glab = [], [], [], {}, [], []
        for c1, items in clusters.items():
            fam = c1.split(" @ ")[0]
            bpw_rng = c1.split(" @ ")[-1].replace(" bpw", "")
            for j, (q, y, e) in enumerate(items):
                is_iq = "IQ" in q
                col = "#0f9b8e" if is_iq else "#2c6fbb"
                ax.bar(pos, y, width=.72, color=col, edgecolor="white", lw=.6, zorder=2)
                ax.errorbar(pos, y, yerr=1.96 * e, fmt="none", ecolor="#222",
                            elinewidth=1, capsize=2.5, zorder=3)
                ax.annotate("%.3f" % y, (pos, y + 1.96 * e), xytext=(0, 3),
                            textcoords="offset points", ha="center", fontsize=6.6)
                xtick.append(pos)
                xlab.append(q.replace("UD-", ""))
                cats["IQ 系列（信息论量化）" if is_iq else "K 系列（传统量化）"] = col
                pos += 1
            gsep.append(pos - 0.5)
            gpos.append(pos - len(items) / 2 - .5)
            glab.append(f"{fam}\n{bpw_rng} bpw")
            pos += 1.1
        for s in gsep[:-1]:
            ax.axvline(s + .55, color="#cfd8e3", lw=.9, ls=":")
        ax.set_xticks(xtick)
        ax.set_xticklabels(xlab, rotation=38, ha="right", fontsize=7.4)
        ax.set_ylim(0, 1.16)
        # 组名放在柱顶之上（白色底衬），不与横轴标签抢位置
        for gp, gl in zip(gpos, glab):
            ax.text(gp, 1.015, gl, ha="center", va="bottom", fontsize=7.0, color="#33475e",
                    bbox=dict(facecolor="white", edgecolor="#cfd8e3", alpha=.92, pad=2.2))
        _style_axes(ax, "量化方案（同一组内 = 同一模型、有效位宽相近）", "基准分数",
                    f"{LBL.get(k, k)}：方案 / 厂商对比")
        ax.legend(handles=[Patch(color=c, label=l) for l, c in cats.items()],
                  fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2)
        out.append(save(fig, f"C_{k}",
                        caption="柱顶白色标签 = “模型 + 位宽匹配组”；竖虚线分隔组。"
                                "组内比较换方案（青 = IQ 系列，蓝 = K 系列）。"
                                "柱顶数字为原始分数，" + _bps_note()))
    return out


# ---------- D MoE 比特分配 ----------
def fig_D(t):
    out = []
    for k in t["col_keys"]:
        if t["counts"].get(k, 0) == 0:
            continue
        rows = [(c2, cells[k][0], _se(cells[k][0], cells[k][1]))
                for _c1, c2, cells in t["rows"] if cells.get(k)]
        if not rows:
            continue
        labels = [r[0] for r in rows]
        ys = [r[1] for r in rows]
        es = [r[2] for r in rows]
        cols = ["#4c72b0", "#55a868", "#c44e52"]
        xs = list(range(len(rows)))
        fig, ax = plt.subplots(figsize=(9.6, 5.0))
        ax.bar(xs, ys, color=cols[:len(rows)], width=.6, edgecolor="white", zorder=2)
        ax.errorbar(xs, ys, yerr=[1.96 * e for e in es], fmt="none", ecolor="#222",
                    elinewidth=1.1, capsize=3, zorder=3)
        for x, y in zip(xs, ys):
            ax.annotate("%.3f" % y, (x, y), xytext=(0, 3), textcoords="offset points",
                        ha="center", fontsize=9)
        wrapped = [re.sub(r", rest ", ",\nrest ", s) for s in labels]
        ax.set_xticks(xs)
        ax.set_xticklabels(wrapped, fontsize=8.2)
        ax.set_ylim(0, 0.98)
        _style_axes(ax, "配方（专家层 / 其余层）", "基准分数",
                    f"{LBL.get(k, k)}：MoE 比特分配 配方对比")
        out.append(save(fig, f"D_{k}",
                        caption="三条配方共用同一套 base 权重，总分比特高低不同；"
                                "比较“把低比特给专家层还是给其余层”。" + _bps_note()))
    return out


# ---------- E KV 缓存精度：按上下文分组 ----------
def fig_E(t):
    out = []
    for k in t["col_keys"]:
        if t["counts"].get(k, 0) == 0:
            continue
        ctxs = collections.OrderedDict()
        for c1, c2, cells in t["rows"]:
            c = cells.get(k)
            if not c or c[0] is None:
                continue
            m = re.search(r"ctx(\d+)", c1)
            ctx = m.group(1) if m else "?"
            ctxs.setdefault(ctx, {})[c2] = (c[0], _se(c[0], c[1]))
        if not ctxs:
            continue
        kvs = sorted({kv for d in ctxs.values() for kv in d})
        fig, ax = plt.subplots(figsize=(9.8, 5.0))
        n = len(kvs)
        w = 0.82 / max(len(ctxs), 1)
        for i, (ctx, d) in enumerate(ctxs.items()):
            xs = [j + (i - (len(ctxs) - 1) / 2) * w for j in range(n)]
            ys = [d[kv][0] if kv in d else np.nan for kv in kvs]
            es = [1.96 * d[kv][1] if kv in d else 0 for kv in kvs]
            ax.bar(xs, ys, width=w * .92, label=f"ctx {ctx}",
                   color=_FALLBACK[i % len(_FALLBACK)], edgecolor="white", lw=.5, zorder=2)
            ax.errorbar(xs, ys, yerr=es, fmt="none", ecolor="#222",
                        elinewidth=.9, capsize=2, zorder=3)
        ax.set_xticks(range(n))
        ax.set_xticklabels(kvs, fontsize=9)
        ax.set_ylim(0, 1.04)
        _style_axes(ax, "KV 缓存精度（K / V）", "基准分数",
                    f"{LBL.get(k, k)}：KV 精度对比（按上下文长度分组）")
        ax.legend(fontsize=8, title="上下文长度", ncol=2)
        out.append(save(fig, f"E_{k}",
                        caption="分组 = 上下文长度；组内比较 KV 精度。" + _bps_note()))
    return out


# ---------- F 采样参数 ----------
def fig_F(t):
    """采样参数：MultiPL-E 的每个语言各自一条线，cpp 与 py 不合成一个数。"""
    mpl_cols = [k for k in t["col_keys"] if k.startswith("multipl_e_")]
    temp, topk = {}, {}
    for c1, c2, cells in t["rows"]:
        try:
            v = float(c2)
        except ValueError:
            continue
        model = c1.split(" · ")[0]
        if "temperature" in c1:
            bucket, key = temp, model
        elif "top_k" in c1:
            bucket, key = topk, model + (" (temp 0)" if "temp 0" in c1 else "")
        else:
            continue
        for k in mpl_cols:
            c = cells.get(k)
            if not c or c[0] is None:
                continue
            lang = MPL_LANG_LBL[k[len("multipl_e_"):]]
            bucket.setdefault((key, lang), []).append((v, c[0], c[1] or 0))
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.0))
    for ax, data, xlab, title in (
            (axes[0], temp, "温度 temperature", "温度对代码通过率的影响"),
            (axes[1], topk, "top_k", "top_k 对代码通过率的影响")):
        for i, ((name, lang), pts) in enumerate(sorted(data.items())):
            # 同一语言、同一取值若有多条测量，按题目数加权平均后合并为一个点
            agg = {}
            for v, y, n in pts:
                agg.setdefault(v, []).append((y, n))
            pts = sorted((v,
                          sum(y * n for y, n in vs) / max(sum(n for _y, n in vs), 1),
                          sum(n for _y, n in vs)) for v, vs in agg.items())
            col = _FALLBACK[i % len(_FALLBACK)]
            err = [1.96 * _se(y, n) for _v, y, n in pts]
            ax.errorbar([p[0] for p in pts], [p[1] for p in pts],
                        yerr=err,
                        marker=MARKERS[i % len(MARKERS)], ls=LINESTYLES[i % len(LINESTYLES)],
                        color=col, lw=1.7, ms=6, capsize=2.5, label=f"{name} · {lang}")
        _style_axes(ax, xlab, "多语言代码通过率", title)
        ax.legend(fontsize=7.6, loc="best")
    fig.suptitle("采样 / 解码参数：代码通过率（按语言分开）", fontsize=13.5)
    return [save(fig, "F_value",
                 caption="左：温度；右：top_k。温度 0 时没有分布可截断，top_k 曲线因此是平的"
                         "（结构事实，不是测量误差）。" + _bps_note())]


# ---------- G1 投机解码速度 ----------
def fig_G1(t):
    series = {}
    last = t["col_keys"][-1]
    for c1, c2, cells in t["rows"]:
        try:
            d = int(c2)
        except ValueError:
            continue
        c = cells.get(last)
        if not c or c[0] is None:
            continue
        series.setdefault(c1.split(" · ")[0], []).append((d, c[0]))
    fig, ax = plt.subplots(figsize=(10.4, 5.4))
    for i, (m, pts) in enumerate(sorted(series.items())):
        pts = sorted(pts)
        col = _FALLBACK[i % len(_FALLBACK)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, marker=MARKERS[i % len(MARKERS)], ls=LINESTYLES[i % len(LINESTYLES)],
                color=col, lw=1.8, ms=6.5, label=m, zorder=3)
        if len(ys) >= 2 and ys[0]:
            gain = (max(ys) / ys[0] - 1) * 100
            _end_label(ax, xs[-1], ys[-1], f"+{gain:.0f}%", col, fs=7.6)
    _style_axes(ax, "投机解码草稿深度", "每秒生成 token 数",
                "投机解码速度：每秒生成 token 随 草稿深度")
    ax.legend(fontsize=7.8, loc="upper left")
    return [save(fig, "G1_speed",
                 caption="线端数字 = 相对深度 0 的最大提速百分比。")]


# ---------- G2 投机解码质量 ----------
def fig_G2(t):
    out = []
    for key, name in (("humaneval", "代码 HumanEval"), ("mmlu", "知识 MMLU")):
        series = {}
        for c1, c2, cells in t["rows"]:
            try:
                d = int(c2)
            except ValueError:
                continue
            c = cells.get(key)
            if not c or c[0] is None:
                continue
            series.setdefault(c1.split(" · ")[0], []).append((d, c[0], _se(c[0], c[1])))
        if not series:
            continue
        fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.8))
        for i, (m, pts) in enumerate(sorted(series.items())):
            pts = sorted(pts)
            col = _FALLBACK[i % len(_FALLBACK)]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            es = [1.96 * p[2] for p in pts]
            axes[0].errorbar(xs, ys, yerr=es, marker=MARKERS[i % len(MARKERS)],
                             ls=LINESTYLES[i % len(LINESTYLES)], color=col, lw=1.6,
                             ms=6, capsize=2.5, label=m)
            d0 = ys[0] if ys else 0
            axes[1].plot(xs, [y - d0 for y in ys], marker=MARKERS[i % len(MARKERS)],
                         ls=LINESTYLES[i % len(LINESTYLES)], color=col, lw=1.6, ms=6, label=m)
        _style_axes(axes[0], "草稿深度", "基准分数", f"{name}：原始分数")
        _style_axes(axes[1], "草稿深度", "相对深度 0 的差值", f"{name}：差值（放大看平不平）")
        axes[1].axhline(0, color="#333", lw=.9, ls="--")
        axes[0].legend(fontsize=7.6, loc="best")
        fig.suptitle(f"投机解码质量：{name}", fontsize=13.5)
        out.append(save(fig, f"G2_{key}",
                        caption="左 = 原始分数；右 = 各深度减去深度 0 的差，"
                                "用来放大看有没有系统性损伤。" + _bps_note()))
    return out


# ---------- H 思考开关 ----------
def fig_H(t):
    rows = []
    for c1, c2, cells in t["rows"]:
        c = cells.get("gsm8k")
        if c and c[0] is not None:
            rows.append((c1, c2, c[0], _se(c[0], c[1])))
    by = collections.OrderedDict()
    for c1, c2, y, e in rows:
        d = by.setdefault(c1, {})
        d["on" if "on" in c2 else "off"] = (y, e)
    models = [m for m in by if "on" in by[m] and "off" in by[m]]
    models.sort(key=lambda m: by[m]["on"][0] - by[m]["off"][0])
    ys = list(range(len(models)))
    fig, ax = plt.subplots(figsize=(10.4, 5.6))
    for y, m in zip(ys, models):
        off, on = by[m]["off"], by[m]["on"]
        ax.plot([off[0], on[0]], [y, y], color="#c9d3de", lw=2.4, zorder=1)
        ax.errorbar([off[0]], [y], xerr=[1.96 * off[1]], fmt="o", color="#2c6fbb",
                    ms=7, elinewidth=1, capsize=2.5, zorder=3)
        ax.errorbar([on[0]], [y], xerr=[1.96 * on[1]], fmt="s", color="#c0392b",
                    ms=7, elinewidth=1, capsize=2.5, zorder=3)
        d = on[0] - off[0]
        ax.annotate("%+.3f" % d, (max(off[0], on[0]), y), xytext=(10, 0),
                    textcoords="offset points", va="center", fontsize=7.6,
                    color="#b3261e" if abs(d) > 0.02 else "#8a94a0")
    ax.set_yticks(ys)
    ax.set_yticklabels([m.replace("-UD-", "\nUD-") for m in models], fontsize=7.6)
    _style_axes(ax, "推理 GSM8K 分数", "模型 / 量化文件",
                "思考开关：GSM8K 分数（按 开−关 差值排序）")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", ls="none", color="#2c6fbb", label="思考关"),
                       Line2D([], [], marker="s", ls="none", color="#c0392b", label="思考开")],
              fontsize=8.5, loc="lower right")
    return [save(fig, "H_thinking",
                 caption="每行一个模型文件；圆点 = 思考关，方块 = 思考开；线端数字 = 开−关差值。" + _bps_note())]


# ---------- QAT：配对柱 + 差值森林图 ----------
def fig_QAT():
    out = []
    for label, recipe, q, n in QAT_PAIRS:
        a, b = raw_scores(q), raw_scores(n)
        ks = [k for k in BENCH_ORDER if a.get(k) or b.get(k)]
        if not ks:
            continue
        fig, ax = plt.subplots(figsize=(9.8, 4.9))
        x = np.arange(len(ks))
        w = .38
        ax.bar(x - w / 2, [a[k][0] if a.get(k) else np.nan for k in ks], w,
               yerr=[1.96 * _se(a[k][0], a[k][1]) if a.get(k) else 0 for k in ks],
               capsize=2.5, label="QAT", color="#4c72b0", error_kw={"elinewidth": 1, "ecolor": "#222"})
        ax.bar(x + w / 2, [b[k][0] if b.get(k) else np.nan for k in ks], w,
               yerr=[1.96 * _se(b[k][0], b[k][1]) if b.get(k) else 0 for k in ks],
               capsize=2.5, label="原生", color="#c44e52", error_kw={"elinewidth": 1, "ecolor": "#222"})
        ax.set_xticks(x)
        ax.set_xticklabels([LBL[k] for k in ks], rotation=25, ha="right", fontsize=8)
        ax.set_ylim(0, 1.04)
        bpq, bpn = tag_bpw(q), tag_bpw(n)
        sub = ""
        if bpq and bpn:
            sub = f"（QAT {bpq:.2f} vs 原生 {bpn:.2f} 比特/权重）"
        _style_axes(ax, "", "基准分数", f"{label}：{recipe} QAT vs 原生 {sub}")
        ax.legend(fontsize=9)
        out.append(save(fig, f"QAT_{label}_{recipe}",
                        caption="青蓝 = QAT 文件，红 = 同标称配方的原生文件。" + _bps_note()))

        dl = pair_delta(q, n)
        rr = [(k, dl[k]) for k in BENCH_ORDER if dl.get(k)]
        if not rr:
            continue
        fig, ax = plt.subplots(figsize=(9.8, 4.6))
        for y, (k, (d, se, lo, hi)) in enumerate(rr):
            sig = lo > 0 or hi < 0
            col = "#b3261e" if sig else "#8a94a0"
            ax.plot([lo, hi], [y, y], color=col, lw=2.4, solid_capstyle="round", zorder=2)
            ax.plot([d], [y], "o", color=col, ms=7, zorder=3)
            ax.annotate("%+.3f" % d, (hi, y), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=7.6, color=col)
        ax.axvline(0, color="#333", lw=1, ls="--")
        ax.set_yticks(range(len(rr)))
        ax.set_yticklabels([LBL[k] for k, _ in rr], fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel("QAT − 原生（分数差，95% 置信区间）")
        ax.set_title(f"{label}：{recipe} 差值森林图（跨 0 = 测不出）", fontsize=12)
        ax.grid(axis="x", alpha=.25)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        out.append(save(fig, f"QATdelta_{label}_{recipe}",
                        caption="横线 = 95% 置信区间。不跨 0 = 显著（红）；跨 0 = 测不出（灰）。"))
    return out


# ---------- GSQ-RCO ----------
def fig_GSQ():
    out = []
    for b in ("humaneval-plus", "mmlu", "gsm8k"):
        fig, ax = plt.subplots(figsize=(9.4, 4.9))
        xs, ys, es = [], [], []
        for tag, bpw in NATIVE_LADDER:
            sc = raw_scores(tag).get(b)
            if sc and sc[0] is not None:
                xs.append(bpw)
                ys.append(sc[0])
                es.append(1.96 * _se(sc[0], sc[1]))
        ax.errorbar(xs, ys, yerr=es, marker="o", ls="-", color="#1f77b4", lw=1.9,
                    ms=7, capsize=2.5, label="原生 UD 阶梯")
        for k, tag, bpw in GSQ_QUANTS:
            g = raw_scores(tag).get(b)
            if g and g[0] is not None:
                ax.errorbar([bpw], [g[0]], yerr=[1.96 * _se(g[0], g[1])], marker="*",
                            ms=20, color="#d62728", elinewidth=1.2, capsize=3, label=k)
        _style_axes(ax, "有效位宽", "基准分数", f"{LBL[b]}：分数 随 有效位宽")
        ax.legend(fontsize=8.5)
        out.append(save(fig, f"GSQ_{b}",
                        caption="折线 = 原生 UD 阶梯；红星 = 第三方 GSQ-RCO 档位。"
                                "星的纵坐标若落在折线上，则该方案无红利。" + _bps_note()))
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
figure{margin:18px 0;text-align:center}
img{width:100%;max-width:1350px;border:1px solid var(--bd);border-radius:6px;background:#fff}
figcaption{margin:6px auto 0;max-width:1100px;font-size:13px;color:#5a6673;line-height:1.6}
.scroll{overflow-x:auto}
code{background:#eaeef2;padding:1px 5px;border-radius:4px}
.lead{background:#eef4fb;border-left:5px solid #3b7dd8;padding:14px 18px;border-radius:6px;font-size:15.5px}
.recap td.sig{color:#b3261e;font-weight:700}
.nr{color:#8a94a0;font-style:italic}
.repro{background:#fbfbf6;border:1px dashed #c9c2a8;border-radius:6px;padding:8px 14px;margin:10px 0}
.repro-h{font-weight:700;color:#6b5620;margin:2px 0 8px;font-size:14px}
.fixed{background:#fff;border:1px solid #e6e0cc;border-radius:5px;padding:8px 12px;margin:0 0 8px;font-size:13px;color:#4a4436;line-height:1.7}
.repro table{font-size:12.5px;margin:0}
.repro th{background:#7a6a34;font-size:12.5px}
.repro td,.repro th{padding:4px 7px}
.callout{background:#fff7e6;border:1px solid #e7b95e;border-left:5px solid #e7a93e;border-radius:6px;padding:10px 16px;margin:10px 0;font-size:15px}
.callout b{color:#8a5a00}
.tag{display:inline-block;background:#e8eef7;color:#33506e;border-radius:8px;padding:0 7px;font-size:11.5px;margin-left:4px}
.inv td,.inv th{font-size:12.5px}
.analysis ul{margin:6px 0 6px 4px;padding-left:20px}
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
            elif c[1] is None:
                tds.append("<td title='该格没有可唯一配对的逐题产物'>%.4f "
                           "<span class='nr'>(题量未知)</span></td>" % c[0])
            else:
                tds.append("<td>%.4f <span class='nr'>(%s)</span></td>" % (c[0], c[1]))
        out.append("<tr><td>%s</td><td>%s</td>%s</tr>" % (html.escape(c1), html.escape(c2), "".join(tds)))
    out.append("</table></div>")
    return "\n".join(out)


def tag_model(tag):
    r = CON.execute("SELECT model FROM experiments WHERE run_tag=? LIMIT 1", (tag,)).fetchone()
    return r[0] if r else None


def qat_tables():
    ks = BENCH_ORDER; labs = [LBL[k] for k in ks]
    rows = []; rows2 = []; all_models = []
    for label, recipe, q, n in QAT_PAIRS:
        for which, tag in (("QAT", q), ("原生", n)):
            bpw = tag_bpw(tag)
            m = tag_model(tag)
            if m:
                all_models.append([m])
            rows.append((f"{label} {recipe} {which}", f"{bpw:.3f}" if bpw else "—",
                         raw_scores(tag), [m] if m else []))
        dl = pair_delta(q, n); cells = {}
        for b in ks:
            c = dl.get(b)
            if c:
                cells[b] = (c[0], f"[{c[2]:+.3f},{c[3]:+.3f}]")
        rows2.append((f"{label} {recipe}", "QAT − 原生", cells, []))
    def mk(title, rows, models):
        return {"title": title, "c1_name": "系列", "c2_name": "有效位宽", "col_keys": ks, "col_labels": labs,
                "rows": [(r[0], r[1], r[2]) for r in rows],
                "row_models": [r[3] if len(r) > 3 else [] for r in rows],
                "counts": {k: sum(1 for r in rows if r[2].get(k)) for k in ks}, "data_cols": len(ks)}
    return [mk("量化感知训练：原始分数", rows, all_models),
            mk("量化感知训练：差值（QAT−原生）", rows2, [])]


def gsq_tables():
    ks = BENCH_ORDER; labs = [LBL[k] for k in ks]
    rows = [("原生 " + tag, f"{bpw:.3f}", raw_scores(tag), [tag_model(tag)])
            for tag, bpw in NATIVE_LADDER]
    rows += [(k, f"{bpw:.3f}", raw_scores(tag), [tag_model(tag)]) for k, tag, bpw in GSQ_QUANTS]
    return [{"title": "GSQ-RCO：原始分数", "c1_name": "系列", "c2_name": "有效位宽", "col_keys": ks,
             "col_labels": labs, "rows": [(r[0], r[1], r[2]) for r in rows],
             "row_models": [[m for m in r[3] if m] for r in rows],
             "counts": {k: sum(1 for r in rows if r[2].get(k)) for k in ks}, "data_cols": len(ks)}]


MPL_LANGS = list(eval_status.LANGS)
MPL_LANG_LBL = {"cpp": "C++", "py": "Python", "js": "JS", "java": "Java", "rs": "Rust", "rb": "Ruby"}
BFCL_BENCH = [
    ("bfcl-simple_python", "单轮·简单"), ("bfcl-multiple", "单轮·多函数"),
    ("bfcl-parallel", "单轮·并行"), ("bfcl-parallel_multiple", "单轮·并行多函数"),
    ("bfcl-irrelevance", "单轮·不相关"),
    ("bfcl-live_simple", "Live·简单"), ("bfcl-live_multiple", "Live·多函数"),
    ("bfcl-live_parallel", "Live·并行"), ("bfcl-live_parallel_multiple", "Live·并行多函数"),
    ("bfcl-live_relevance", "Live·相关"), ("bfcl-live_irrelevance", "Live·不相关"),
    ("bfcl-multi_turn_base", "多轮·基础"), ("bfcl-multi_turn_miss_func", "多轮·缺函数"),
    ("bfcl-multi_turn_miss_param", "多轮·缺参数"), ("bfcl-multi_turn_long_context", "多轮·长上下文"),
]


def mpl_protocol_label(proto):
    """协议串 → 表格/图的一行标签，并保留数据库记下的附加条件。

    `mpl-chat-nothink-greedy-768;ctx=4096;tmpl=unverified`（gemma-4-12b 的 cpp，
    m6b 面板）与 `mpl-chat-nothink-greedy-768`（同一模型的 py，m161 重测）是两套
    不同设置；都缩成 `chat` 会让同一个模型的 cpp 与 py 落在两个同名行上，读起来
    像“固定 chat 模板与上下文”，而数据库保留的正是这两点差异（result.res22）。
    `ctx=`/`kv=`/`tmpl=` 三段是设置本身，原样留下；其余附加段（如 `fa=on`、
    `prefix=…`）不参与区分，标签里省掉。协议名里的采样温度同理：`-t0.3-` 是另一个
    采样设置，不能和贪心那行挤成同一个 `raw`。
    """
    proto = proto or "—"
    head = proto.split(";")[0]
    base = "chat" if "chat" in head else ("raw" if "raw" in head else head)
    t = re.search(r"-t([0-9.]+)-", head)
    if t:
        base += f"·temp={t.group(1)}"
    extra = [part.strip() for seg in proto.split(";")[1:] for part in seg.split(",")
             if part.strip().startswith(("ctx=", "kv=", "tmpl="))]
    return "·".join([base] + extra)


# 同一条协议串下存了两个不同测量值的格（库内无法区分），报告把它列出来。
ambiguous = []


def table_mpl_langs():
    """MultiPL-E per language: one row per (model, display label), columns = languages.

    行键是「模型 + 显示标签」。标签有意省掉不参与区分的附加协议段，所以两个协议串可以落到
    同一个标签上；此时两者是同一个可读行，只有当它们的数值逐语言一致时才合并为一行，
    不一致就报错——否则一行会静默盖掉另一个测量（plan16）。
    """
    grouped = {}
    rows = CON.execute(
        "SELECT model,protocol,language,_score,n_items,run_tag FROM experiments "
        "WHERE bench_family='humaneval-multipl-e' AND _score IS NOT NULL")
    for model, proto, lang, score, n, _tag in rows:
        label = mpl_protocol_label(proto)
        grouped.setdefault((model, label), {}).setdefault(lang, []).append((proto, score, n))
    ambiguous.clear()
    out = []
    for (model, label), per_lang in sorted(grouped.items()):
        merged = {}
        for lang, vals in per_lang.items():
            # 重复测量（同格多次入库）是一个数；同一标签下出现两个不同的数，说明协议串把
            # 一个面板的多个取值（如 m31 的 top_k 扫描，K=1 是贪心地板）折进了同一串，
            # 库内没有列说明哪一行是哪个取值。此时不能只显示一个数而不说：取测量次数
            # 较多的那个，并在报告里列出另一个值，缺陷归入库侧（见 result.res32）。
            counts = collections.Counter(sc for _p, sc, _n in vals)
            if len(counts) > 1:
                pick = counts.most_common(1)[0][0]
                ambiguous.append({
                    "model": model, "label": label, "lang": lang,
                    "shown": pick, "rows": len(vals),
                    "protocols": len({p for p, _s, _n in vals}),
                    "rows_shown": counts[pick],
                    "others": [(v, counts[v]) for v in sorted(counts) if v != pick],
                })
            else:
                pick = vals[0][1]
            n = (vals[0][2] if vals[0][2] is not None
                 else eval_status.n_for(lang, pick, eval_status.hints_from_label(vals[0][0])))
            merged[lang] = (pick, n)
        if not merged:
            continue
        out.append((model, label, merged, [model]))
    order = {"raw": 0, "chat": 1}
    out.sort(key=lambda r: (r[0], order.get(r[1], 9)))
    keys = MPL_LANGS
    return {"title": "多语言代码：逐语言", "c1_name": "模型文件", "c2_name": "生成协议",
            "col_keys": keys, "col_labels": [MPL_LANG_LBL[k] for k in keys],
            "rows": [(a, b, c) for a, b, c, _m in out], "row_models": [m for *_, m in out],
            "counts": {k: sum(1 for _a, _b, c, _m in out if c.get(k)) for k in keys},
            "data_cols": len(keys)}


def table_bfcl():
    """BFCL: one row per (model, protocol), columns = the BFCL categories."""
    cells = {}
    rows = CON.execute(
        "SELECT model,protocol,_bench,_score,n_items FROM experiments "
        "WHERE (bench_family='bfcl' OR bench_family='bfcl-multiturn') AND _score IS NOT NULL")
    names = {b: l for b, l in BFCL_BENCH}
    for model, proto, bench, score, n in rows:
        if bench not in names:
            continue
        cells.setdefault((model, proto or "—"), {})[bench] = (score, n)
    out = [(model, proto, d, [model]) for (model, proto), d in sorted(cells.items()) if d]
    keys = [b for b, _ in BFCL_BENCH]
    return {"title": "工具调用（BFCL）：协议 × 类别", "c1_name": "模型文件", "c2_name": "协议",
            "col_keys": keys, "col_labels": [names[k] for k in keys],
            "rows": [(a, b, c) for a, b, c, _m in out], "row_models": [m for *_, m in out],
            "counts": {k: sum(1 for _a, _b, c, _m in out if c.get(k)) for k in keys},
            "data_cols": len(keys)}


def mpl_ambiguous_note():
    """同一条协议串下存了两个不同测量值的格：逐条列出来，不只在表里显示一个数。

    行键是「模型 + 显示标签」，标签省掉不参与区分的附加段；当这些附加段其实分开了一
    个面板的多个取值（m31 的 top_k 扫描把 K=1 与 K=200 写进同一条协议串）时，库内没有
    列能说明哪一行是哪个取值，报告因此不能只显示一个数而不说。
    """
    if not ambiguous:
        return ""
    items = []
    for a in ambiguous:
        others = "、".join(f"{v:.4f}（{c} 行）" for v, c in a["others"])
        items.append(f"<code>{html.escape(a['model'].replace('.gguf', ''))}</code> 的 "
                     f"{html.escape(a['label'])} · {MPL_LANG_LBL.get(a['lang'], a['lang'])}："
                     f"这个行标签下有 {a['rows']} 行测量（来自 {a['protocols']} 条协议串），"
                     f"其中 {a['rows_shown']} 行是 {a['shown']:.4f}，"
                     f"表中就显示它；另外还印出 {others}")
    return ("<li><b>行键无法区分的格（数据缺陷，逐条列出而不静默取其一）：</b>"
            + "；".join(items) + "。这些格来自 m31 的 top_k 扫描：它把 K=1（贪心地板）与 K=200（不截断）"
            "两种取值写进了同一条协议串，库内没有列说明哪一行属于哪个取值；"
            "处置归入库侧（<code>migrations/backfill_n_items.py</code> 与库内协议串），报告只如实显示两个值。</li>")


def fig_mpl_langs(t):
    langs = t["col_keys"]
    # 行键必须是 (模型, 协议)：否则同一模型的 raw/chat 两行会被混成一行。
    keys = sorted({(c1, c2) for c1, c2, _c in t["rows"]})
    M = np.full((len(keys), len(langs)), np.nan)
    for i, (m, p) in enumerate(keys):
        for c1, c2, cells in t["rows"]:
            if (c1, c2) != (m, p):
                continue
            for j, l in enumerate(langs):
                c = cells.get(l)
                if c and c[0] is not None:
                    M[i, j] = c[0]
    labels = [f"{m.replace('.gguf','')}\n[{p}]" for m, p in keys]
    fig, ax = plt.subplots(figsize=(1.5 + 1.05 * len(langs), 0.46 * len(keys) + 2.2))
    im = ax.imshow(M, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(langs)))
    ax.set_xticklabels([MPL_LANG_LBL[l] for l in langs], fontsize=9)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(labels, fontsize=6.8)
    for i in range(len(keys)):
        for j in range(len(langs)):
            if not np.isnan(M[i, j]):
                ax.text(j, i, "%.2f" % M[i, j], ha="center", va="center", fontsize=7)
    ax.set_title("多语言代码：每个（模型, 协议）的各语言通过率（空白 = 未测）", fontsize=12)
    fig.colorbar(im, ax=ax, shrink=.7, label="通过率")
    return [save(fig, "MPL_langs",
                 "每格 = 该模型在该语言上的 pass（161 题）；空白 = 未测。"
                 "同一行内的差异是真实的语言难度/模板效应；跨行比较时要注意协议（raw/chat）与测集。")]


def fig_bfcl(t):
    out = []
    for bench, label in BFCL_BENCH:
        if t["counts"].get(bench, 0) == 0:
            continue
        items = [(c1, c2, cells[bench][0]) for c1, c2, cells in t["rows"] if cells.get(bench)]
        if not items:
            continue
        items.sort()
        xs = list(range(len(items)))
        protos = sorted({c2 for _c1, c2, _v in items})
        fig, ax = plt.subplots(figsize=(max(7.5, 0.62 * len(items) + 3), 4.6))
        for pi, p in enumerate(protos):
            sel = [(x, v) for x, (_c1, c2, v) in zip(xs, items) if c2 == p]
            if not sel:
                continue
            ax.bar([x + (pi - (len(protos) - 1) / 2) * 0.38 for x, _v in sel],
                   [v for _x, v in sel], width=.36, label=p, zorder=2)
        ax.set_xticks(xs)
        ax.set_xticklabels([c1.replace(".gguf", "") for c1, _c2, _v in items],
                           rotation=40, ha="right", fontsize=7.2)
        ax.set_ylim(0, 1.04)
        _style_axes(ax, "模型文件", "得分", f"工具调用 {label}")
        ax.legend(fontsize=7.6)
        out.append(save(fig, f"BFCL_{bench}",
                        "同一模型不同协议（提示式工具调用 vs 原生 tools）柱子的差异 = 协议效应。"))
    return out


TESTFRAC_SUMMARY = ".wrapup/m41_summary.jsonl"


def _testfrac_n():
    """每格题量取 m41 部分给分汇总里记的 n（该文件随仓库分发）；取不到就没有题量。

    这张表的分数是「每道题通过的测试比例」的均值，不是 pass/n，所以 pass/n 的配对
    找不回它的题量，只能读汇总自己记的值；绝不填一个默认题数。
    """
    out = {}
    try:
        with open(TESTFRAC_SUMMARY, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("lang") and r.get("n") and r.get("mean_frac") is not None:
                    out[(r["lang"], round(float(r["mean_frac"]), 9))] = int(r["n"])
    except FileNotFoundError:
        return {}
    return out


def table_testfrac():
    tf_n = _testfrac_n()
    cells = {}
    for model, arm, lang, score in CON.execute(
            "SELECT model,_bench,language,_score FROM experiments "
            "WHERE run_tag='m41-testfrac' AND _score IS NOT NULL"):
        a = arm.replace("testfrac-", "")
        cells.setdefault((model, a), {})[lang] = (score, tf_n.get((lang, round(score, 9))))
    out = [(m, a, d, [m]) for (m, a), d in sorted(cells.items()) if d]
    keys = MPL_LANGS
    return {"title": "部分给分（每测试通过比例）", "c1_name": "模型文件", "c2_name": "方案类别",
            "col_keys": keys, "col_labels": [MPL_LANG_LBL[k] for k in keys],
            "rows": [(a, b, c) for a, b, c, _m in out], "row_models": [m for *_, m in out],
            "counts": {k: sum(1 for _a, _b, c, _m in out if c.get(k)) for k in keys},
            "data_cols": len(keys)}


def fig_testfrac(t):
    out = []
    for lang in ("cpp", "py"):
        items = [(c1, c2, cells[lang][0]) for c1, c2, cells in t["rows"] if cells.get(lang)]
        if not items:
            continue
        items.sort()
        fig, ax = plt.subplots(figsize=(max(7.5, 0.72 * len(items) + 2.6), 4.6))
        cols = {"ternary": "#c44e52", "conventional": "#4c72b0"}
        ax.bar(range(len(items)), [v for _c1, _c2, v in items],
               color=[cols.get(c2, "#999") for _c1, c2, _v in items], zorder=2)
        for i, (_c1, _c2, v) in enumerate(items):
            ax.annotate("%.2f" % v, (i, v), xytext=(0, 2), textcoords="offset points",
                        ha="center", fontsize=7.5)
        ax.set_xticks(range(len(items)))
        ax.set_xticklabels([c1.replace(".gguf", "") for c1, _c2, _v in items],
                           rotation=40, ha="right", fontsize=7.0)
        ax.set_ylim(0, 1.02)
        _style_axes(ax, "模型文件", "每道题通过的测试比例", f"部分给分（{MPL_LANG_LBL[lang]}）")
        from matplotlib.patches import Patch
        ax.legend(handles=[Patch(color=cols["conventional"], label="原生 K（非三元）"),
                           Patch(color=cols["ternary"], label="三元 / 极低位宽")], fontsize=8)
        out.append(save(fig, f"testfrac_{lang}",
                        "纵轴不是 pass@1 而是“测试通过比例”：用于区分三元模型是“错得更多”还是“错得不同”。"))
    return out


def section(H, title, definition, tables, figures, analysis_html):
    H.append(f"<section><h2>{title}</h2>")
    H.append(f"<p class='def'>{definition}</p>")
    H.append("<h3>原始数据</h3>")
    for t in tables:
        H.append(render_table(t))
    repro = render_repro(repro_rows(tables))
    if repro:
        H.append("<h3>复现信息（表格用到的模型文件与来源）</h3>")
        H.append(repro)
    if figures:
        H.append("<h3>原始数据图</h3>")
        for item in figures:
            path, cap = item if isinstance(item, tuple) else (item, None)
            if not path or not os.path.exists(path):
                continue
            capp = f"<figcaption>{cap}</figcaption>" if cap else ""
            H.append(f"<figure><img src='data:image/png;base64,{b64(path)}'>{capp}</figure>")
    H.append("<h3>分析</h3>")
    H.append(f"<div class='analysis'>{analysis_html}</div>")
    H.append("</section>")


OPEN_QUESTIONS = "report_inputs/open_questions.json"


def open_questions_html():
    """渲染各子项目「未解问题」的派生索引（`report_inputs/build_open_questions.py` 生成）。

    报告不解析子项目的 Markdown 工作文档；这里读的是那个派生索引，每条自带子项目 id 与
    来源路径，读者可以回到原文。索引缺失时构建失败，不静默少一节。
    """
    if not os.path.exists(OPEN_QUESTIONS):
        raise SystemExit(f"报告输入缺失：{OPEN_QUESTIONS}"
                         f"（由 report_inputs/build_open_questions.py 生成）。")
    doc = json.load(open(OPEN_QUESTIONS, encoding="utf-8"))
    if not doc["items"]:
        return "<p class='nr'>（各子项目当前都没有登记未解问题）</p>"
    out = ["<ul>"]
    for it in doc["items"]:
        out.append(f"<li><span class='tag'>{html.escape(it['subproject'])}</span> "
                   f"{html.escape(it['text'])} "
                   f"<span class='nr'>（来源：<code>{html.escape(it['path'])}</code>"
                   f" · {html.escape(it['heading'])}）</span></li>")
    out.append("</ul>")
    skipped = doc.get("skipped") or []
    note = (f"<p class='nr'>索引由各子项目的 PLAN.md 生成；{len(doc['sections'])} 个子项目登记了"
            f"「未解问题」一节，另有 {len(skipped)} 个子项目没有这一节（已跳过："
            + "、".join(f"<code>{html.escape(os.path.basename(os.path.dirname(p)))}</code>"
                        for p in skipped) + "）。</p>")
    return "".join(out) + note


PAIRED_DELTAS = "report_inputs/paired_deltas.json"


def cell_point(model_file, bench):
    """某一格在规范协议下的分数（库里查不到就返回 None，不印）。

    基准在报告里用下划线键（`humaneval_plus`），在库里是连字符（`humaneval-plus`），两种都试。
    """
    for name in (bench, bench.replace("_", "-")):
        proto = CANON.get(name) or CANON.get(name.replace("-", "_"))
        if not proto:
            continue
        r = CON.execute("SELECT _score,n_items FROM experiments WHERE model=? AND protocol=? "
                        "AND _bench=? AND _score IS NOT NULL",
                        (model_file, proto, name)).fetchone()
        if r:
            return r
    return None


def bfcl_aggregation_note():
    """BFCL 没有唯一的「总分」：这一节只说清口径，也不印任何当作总分用的数。"""
    gap = bfcl_micro_macro_gap()
    parts = ["<li><b>BFCL 没有唯一的「总分」，逐类别比较才有意义。</b>本表一行一个"
             "（模型, 生成协议）、一列一个类别，<b>不提供汇总列</b>：任一列都是该类别自己的通过率，"
             "把它们平均起来是 macro，按题数加权是 micro，两者不是同一个量。"
             "面板汇总里记的是按题加权的 micro，而读者从这些类别列能算出来的只有未加权 macro，"
             "<b>两者不可混用</b>。"]
    if gap:
        parts.append(f"本仓库的 BFCL 汇总里，两者相差最多 <b>{gap['gap']:.4f}</b>"
                     f"（<code>{html.escape(str(gap['model']))}</code>：micro {gap['micro']:.4f} vs "
                     f"macro {gap['macro']:.4f}，来自 <code>{html.escape(gap['file'])}</code>）。")
    else:
        parts.append("本机没有可用的 BFCL 汇总，这一项差多少无法给出。")
    n_null = CON.execute("SELECT COUNT(*) FROM experiments WHERE _score IS NOT NULL "
                         "AND n_items IS NULL AND bench_family LIKE 'bfcl%'").fetchone()[0]
    n_all = CON.execute("SELECT COUNT(*) FROM experiments WHERE _score IS NOT NULL "
                        "AND bench_family LIKE 'bfcl%'").fetchone()[0]
    parts.append("题量方面：单轮的题量已按 `per_category` 的类别计数回填，"
                 f"多轮仍有 {n_null}/{n_all} 行没有题量（汇总里没有匹配「类别 + 分数」的记录）；"
                 "micro 需要逐题计数，而产物只有类别级 `acc`/`n`，所以 micro 不可从库复算，"
                 "本报告也不给 BFCL 的任何单一总分数值。</li>")
    return "".join(parts)


SCHEME_EFFECTS = "report_inputs/scheme_effects.json"


def scheme_effects_html():
    """第三节的结论句：同字节下探测不到方案/厂商的水平位移，真正的变量是比特分配。

    数字来自 `report_inputs/scheme_effects.json`，而它由 `a03` 的归因脚本输出解析而来
    （`report_inputs/build_scheme_effects.py`）；所以脚本数据一变，这句话和它的精度就跟着变，
    不会停在旧措辞上。
    """
    if not os.path.exists(SCHEME_EFFECTS):
        raise SystemExit(f"报告输入缺失：{SCHEME_EFFECTS}"
                         f"（由 report_inputs/build_scheme_effects.py 生成）。")
    doc = json.load(open(SCHEME_EFFECTS, encoding="utf-8"))
    labels = doc["labels"]
    detected = {k: v["significant_benches"] for k, v in labels.items() if v["significant_benches"]}
    n_bench = doc["benches"]

    out = []
    if not detected:
        out.append("<li><b>同字节下探测不到方案 / 厂商的水平位移。</b>"
                   f"把家族与比特预算固定住以后，三个标签系数（IQ 方案、本仓配方、另一个上传者）"
                   f"在 {n_bench}/{n_bench} 个基准上<b>全部跨 0</b>；唯一每个基准都不含 0 的是位宽斜率本身"
                   f"（{doc['slope_range'][0]:+.2f} 至 {doc['slope_range'][1]:+.2f} 分/比特）。")
        weakest = sorted(labels.items(), key=lambda kv: -kv[1]["half_width_max"])[:2]
        weak_lo = min(v["half_width_max"] for _k, v in weakest)
        weak_hi = max(v["half_width_max"] for _k, v in weakest)
        out.append("<br><b>精度：</b>各标签的 95% 区间半宽最大到 "
                   + "、".join(f"{k} ≤{v['half_width_max']:.2f}" for k, v in labels.items())
                   + f"。所以识别力最弱的两类（{'、'.join(k for k, _v in weakest)}）"
                   f"在 <b>±{weak_lo:.1f}–{weak_hi:.1f} 量级以内的水平位移不可分辨</b>——"
                   f"这是「探测不到」，不是「没有效应」。识别来源也很窄："
                   + "；".join(f"{k} 由 {len(v['families'])} 族识别（{'、'.join(v['families'])}）"
                              for k, v in labels.items() if v["families"])
                   + "；其余来源在族内取值恒定、与家族固定效应共线，直接不可识别。")
        out.append("<br><b>标签是比特分配的代理，分配在哪才是变量：</b>同名档位跨供应商时，"
                   "分层分配轮廓的差可以远大于总位宽的差（实测轮廓与计数见 "
                   "<code>docs/subprojects/a03-量化方案与厂商/RESULT.md::alloc-qwen36</code>），"
                   "所以「换方案 / 换厂商」应当读成「换了谁把比特放在哪一层」。</li>")
    else:
        shown = "；".join(f"{k} 在 {'、'.join(v)} 上区间不含 0" for k, v in detected.items())
        out.append(f"<li><b>同字节下探测到了标签的水平位移：</b>{html.escape(shown)}。"
                   f"其余部分仍跨 0，逐基准读，不要外推。</li>")
    return "".join(out)


def bfcl_micro_macro_gap():
    """BFCL 汇总里「按题加权 micro」与「类别等权 macro」的最大差（从 run 汇总算，不手抄）。

    面板 summary 的 `score` 是按题加权的 micro；读者从类别列能算出来的只有未加权 macro。
    两者不是同一个量，差多少取决于类别题量是否均衡，所以这里当场算一遍再写进正文。
    """
    import glob
    best = None
    for path in glob.glob(os.path.join(".wrapup", "*_summary.jsonl")):
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            per = r.get("per_category")
            if not isinstance(per, dict) or not per or r.get("score") is None:
                continue
            accs = [v["acc"] for v in per.values()
                    if isinstance(v, dict) and v.get("acc") is not None]
            if not accs:
                continue
            macro = sum(accs) / len(accs)
            gap = abs(r["score"] - macro)
            if best is None or gap > best["gap"]:
                best = {"gap": gap, "micro": r["score"], "macro": macro,
                        "model": r.get("model"), "file": os.path.basename(path)}
    return best


REPRODUCIBILITY = "report_inputs/reproducibility.json"


def reproducibility_html():
    """「测量可复现性边界」一节：地板与输入变更幅度是两件事，分别由 i01 的事实给出。

    数字来自 `report_inputs/reproducibility.json`（由 `i01/RESULT.md` 的 res32/res29 抽出），
    所以改那两条事实、这一节就跟着变；缺输入或缺适用条件时构建失败，不印一个孤立数字。
    """
    if not os.path.exists(REPRODUCIBILITY):
        raise SystemExit(f"报告输入缺失：{REPRODUCIBILITY}（由 report_inputs/build_reproducibility.py 生成）。")
    doc = json.load(open(REPRODUCIBILITY, encoding="utf-8"))
    floor, change = doc["floor"], doc["input_change"]
    out = ["<p class='def'>这一节回答一个读者一定会问的问题：报告里的分数波动到多大就值得当真。"
           "答案是两件事，必须分开读——<b>输入相同时地板是 0 道题</b>；"
           "<b>输入变了则可能翻转十几个题</b>。把后者当前者、或把前者当噪声容忍度，都会读错表。</p>"]

    items = []
    for h in floor["harnesses"]:
        extra = f"，通过数 {h['passed']}/{h['n']}" if "passed" in h else ""
        items.append(f"<li><b>{html.escape(h['name'])}</b>：同配置重复 {h['identical']}/{h['n']} 题逐题相同"
                     f"（上翻 {h['flips_up']}、下翻 {h['flips_down']}、Jaccard {h['jaccard']}{extra}）</li>")
    out.append("<h3>一、输入相同时：地板是 0 道题</h3><ul>" + "".join(items) + "</ul>")
    out.append(f"<p><b>判读规则：</b>{html.escape(floor['rule'])}。"
               f"因此同一提示集哈希、同一后处理版本下的任何非零跨 run 差异，"
               f"都不能写成「噪声」——它是错误，或者是你没记录下来的输入差。</p>")

    out.append("<h3>二、输入变了时：幅度可达十几个题</h3>")
    out.append(f"<p>同一个 cell 在提示集被重建/删除之后重跑，实测出现 "
               f"<b>{change['flips_up'] + change['flips_down']} 题双向翻转</b>"
               f"（{change['flips_up']} 上 / {change['flips_down']} 下，净 "
               f"{change['net']:+d}），即 <b>±{change['amplitude']}/{change['n']} ≈ "
               f"{change['amplitude_ratio']:.2f}</b> 的量级；完成物在 "
               f"{change['text_diff']}/{change['n']} 题上文本不同，其中 "
               f"{change['token_diff']} 题是 token 真的不同。</p>")
    out.append(f"<p><b>适用条件：</b>{html.escape(doc['condition'])}。"
               f"换句话说：跨提示集/跨后处理版本的两次 run 不能互为重复测量；"
               f"两个数字也不得相加（地板 0 说的是重复跑，±{change['amplitude']}/{change['n']} 说的"
               f"是输入变了）。</p>")
    out.append(f"<p class='nr'>来源：<code>{html.escape(doc['source'])}</code> 的 "
               f"<code>{html.escape(floor['fact'])}</code> 与 "
               f"<code>{html.escape(change['fact'])}</code>；本节的数字由 "
               f"<code>report_inputs/build_reproducibility.py</code> 抽取，改那两条事实这一节就跟着变。</p>")
    return "".join(out)


def inversion_callout():
    """第一节的重点解释：两档之间的配对差有多大、哪些被区间支持。

    点估计来自库，区间来自 a01 的配对差事实（经 report_inputs/paired_deltas.json 索引）。
    文字是**生成**的：把那条事实的区间改成跨 0，这里就只会说「无显著差异」，不会继续声称掉点；
    方案差异只作为机制假设出现，并写明什么观察会否证它。
    """
    doc = json.load(open(PAIRED_DELTAS, encoding="utf-8"))
    pair = doc["pair"]
    low, high = pair["low"], pair["high"]
    fam = pair["family"]
    sig = [m for m in doc["metrics"] if m["significant"]]
    ns = [m for m in doc["metrics"] if not m["significant"]]

    low_file = next((f for f in BPWMAP if f.startswith(fam) and
                     abs(BPWMAP[f] - low["bpw"]) < 5e-3), None)
    high_file = next((f for f in BPWMAP if f.startswith(fam) and
                      abs(BPWMAP[f] - high["bpw"]) < 5e-3), None)

    out = [f"<div class='callout'><b>重点解释：{html.escape(fam)} 在 "
           f"{low['bpw']:.2f} 与 {high['bpw']:.2f} 比特/权重这两档之间。</b>"
           f"低档是 <code>{html.escape(low['quant'])}</code>，高档是 "
           f"<code>{html.escape(high['quant'])}</code>——后者每权重比特更多，"
           f"但两者是不同<b>方案</b>（动态分配 vs 信息论量化 + imatrix），所以不能假定分数随比特单调。"]

    out.append("<br>逐基准的两比例差（95% 区间，口径：低档 − 高档，来自 "
               f"<code>{html.escape(doc['source'])}</code> 的 <code>{html.escape(doc['fact'])}</code>）：")
    rows = []
    for m in doc["metrics"]:
        cell_lo = cell_point(low_file, m["key"]) if low_file else None
        cell_hi = cell_point(high_file, m["key"]) if high_file else None
        pts = ""
        if cell_lo and cell_hi:
            pts = f"（点估计 {cell_lo[0]:.4f} → {cell_hi[0]:.4f}）"
        verdict = "区间不含 0" if m["significant"] else "区间跨 0"
        rows.append(f"<li><b>{html.escape(m['metric'])}</b> "
                    f"{m['delta']:+.4f} [{m['lo']:+.4f}, {m['hi']:+.4f}] → {verdict}{pts}</li>")
    out.append("<ul style='margin:6px 0 6px 18px'>" + "".join(rows) + "</ul>")

    if sig:
        names = "、".join(m["metric"] for m in sig)
        out.append(f"<b>被数据支持的差异只有 {html.escape(names)}</b>；"
                   f"其余 {len(ns)} 个基准的区间跨 0，即在这些基准上分不出这两档的差别——"
                   f"不能说它们在两档之间「同时下降」。")
        out.append("<br><b>机制假设（未证实）：</b>两档用的是不同量化方案（动态分配 vs imatrix），"
                   "可能因此产生方向反转。否证方式：换一个家族重复同一对方案时若方向不再出现，"
                   "或同方案同比特差下出现相反方向，这个假设就不成立。")
    else:
        out.append("<b>这 6 个基准的区间全部跨 0</b>：在这两档之间，"
                   "数据分不出差别，因此不声称任何方向上的掉点或提升。")
        out.append("<br>方案差异仍只是一个候选机制，连点估计的方向都没有被区间支持。")
    out.append("</div>")
    return "".join(out)


NON_MEASUREMENTS = "docs/subprojects/i02-测量基础设施/non_measurements.tsv"


def non_measurements_html():
    """非测量登记册：显存不足 / 门槛失败 / 没跑，逐格列出状态、发生了什么和证据。

    它们是缺席而不是 0，所以既不能进任何均值，也不能被画成低分；登记册缺失时构建失败，
    因为那时报告无法证明「这些格是没测」而不是「这些格还没写」。
    """
    if not os.path.exists(NON_MEASUREMENTS):
        raise SystemExit(f"报告输入缺失：{NON_MEASUREMENTS}；未测格无法与 0 区分，不渲染报告。")
    rows = [ln.rstrip("\n").split("\t")
            for ln in open(NON_MEASUREMENTS, encoding="utf-8") if ln.strip()]
    head, body = rows[0], rows[1:]
    out = ["<table><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr>"]
    for r in body:
        out.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>")
    out.append("</table>")
    counts = collections.Counter(r[3] for r in body)
    summary = "、".join(f"<b>{html.escape(k)}</b> {v} 格" for k, v in sorted(counts.items()))
    return (f"<p class='def'>逐格口径：{summary}。这些格子没有数据，因此不参与任何均值、"
            "也不出现在任何图上——空白不等于 0，也不等于「跑完但得分低」。</p>" + "".join(out))


# 已退役的目录：路径本身仍可能存在（`.scratch` 还在仓库里），但已不再作为「事实的家」。
# 报告因此照实打印存在的路径并标注这一点，而不是给一条固定文案。
def _eval_status_index():
    """按 (语言, 通过数, 题数) 索引每份评测的状态直方图。

    数据来自 `report_inputs/eval_status.json`：`report_inputs/build_eval_status.py` 把不可入库的
    逐题落盘产物 `.wrapup/mres/*_eval.json` 抽成这一点随仓库分发，干净 clone 才能得到同一份报告。
    文件缺失时构建失败——这份输入不存在不等于 0 份文件。
    DB 行不带 mres 文件名，所以报告用「语言 + 通过数/题数 == _score」把库行与评测文件配对。
    """
    idx = {}
    for rec in eval_status.records():
        idx.setdefault((rec["lang"], rec["pass"], rec["n"]), []).append((rec["file"], rec["status"]))
    return idx


def _all_exception_files(idx):
    """每道题状态都是 `Exception` 的评测文件：[(文件名, 题数)]。"""
    return [(base, n) for (_lang, _pass, n), files in idx.items() for base, st in files
            if n and st.get("Exception", 0) == n]


def _eval_cell(basename):
    """评测文件名 → 它所属的格；`_fixed` 是同一个格的换后处理重判，不是另一个格。"""
    return re.sub(r"(_fixed)?_eval\.json$", "", basename)


def _cell_status(idx, lang, score):
    """给库中的一个 MultiPL-E 分数找配对的评测状态直方图。

    配对不唯一时只在各份直方图完全一致时接受（返回 file=None）；互相矛盾则视为无法配对。
    """
    if score is None:
        return None
    hits = [(n, base, st) for (l, p, n), files in idx.items() if l == lang and n
            for base, st in files if abs(p / n - score) < 1e-9]
    if not hits:
        return None
    n, base, st = hits[0]
    if any(x[0] != n or x[2] != st for x in hits):
        return None
    return (base if len(hits) == 1 else None), n, st


def data_quality_html():
    """构建时从 DB / eval 文件复核的数据质量问题清单（不是静态文案）。"""
    idx = _eval_status_index()
    # 1) 全 Exception 的评测文件（全 Exception 不是整轮运行失败，也不得写成 0）。
    #    份数分三类：同一格的 `_fixed` 重判、5 题探针、以及 161 题整格；读者不能把
    #    文件数当格数，所以这里同时给出文件数与去重后的格数。
    all_exc = _all_exception_files(idx)
    n_all_exc = len(all_exc)
    n_fixed = sum(1 for base, _n in all_exc if base.endswith("_fixed_eval.json"))
    n_probe = sum(1 for _base, n in all_exc if n == 5)
    n_cells = len({_eval_cell(base) for base, _n in all_exc})
    # 2) 语言覆盖（同一模型在 legacy MultiPL-E 里跑了哪些语言）
    langs = {}
    for model, lang in CON.execute(
            "SELECT DISTINCT model,language FROM experiments "
            "WHERE bench_family='humaneval-multipl-e' AND protocol='multipl-e-raw-greedy-768'"):
        langs.setdefault(model, set()).add(lang)
    partial = sorted((m, "".join(sorted(v))) for m, v in langs.items() if not {"cpp", "py"} <= v)
    # 3) 协议对比（同一模型 raw vs chat）
    prot = CON.execute(
        "SELECT model,protocol,round(avg(_score),4) FROM experiments "
        "WHERE bench_family='humaneval-multipl-e' AND language='cpp' "
        "AND model LIKE 'gemma-4-26B-A4B-it-UD-Q3%' GROUP BY model,protocol").fetchall()
    # 4) chat 协议下 gemma-4-26B-A4B 的每个格：库中 _score + 配对的评测状态直方图
    g26b_cells = []
    for model, lang, score in CON.execute(
            "SELECT model, language, _score FROM experiments "
            "WHERE bench_family='humaneval-multipl-e' AND protocol='mpl-chat-nothink-greedy-768' "
            "AND model LIKE 'gemma-4-26B-A4B%' ORDER BY language, model"):
        tier = model.split("-UD-")[-1][:-len(".gguf")] if "-UD-" in model else model
        pair = _cell_status(idx, lang, score)
        if pair:
            base, n, st = pair
            pair_txt = f"通过 {st.get('OK', 0)}/{n}，<code>Exception</code> {st.get('Exception', 0)}"
            if base:
                pair_txt += f"，<code>{html.escape(base)}</code>"
            g26b_cells.append(f"<code>{html.escape(tier)}</code> {MPL_LANG_LBL.get(lang, lang)} "
                              f"{round(score, 4)}（{pair_txt}）")
        else:
            g26b_cells.append(f"<code>{html.escape(tier)}</code> {MPL_LANG_LBL.get(lang, lang)} "
                              f"{round(score, 4)}（库中当前值，未配到评测文件）")

    h = ["<div class='analysis'>"]
    h.append("<p><b>1. “12B 崩到 0”是数据缺陷，不是模型得分。</b> 旧的多语言代码（MultiPL-E）列把每个模型<br>"
             "<b>碰巧跑过的语言</b>混在一起求平均：有的模型只有 cpp、有的只有 py、gemma-4-12b 只有 java/js/rb/rs。"
             "不同测集不能相减，于是 12b/26B 的旧列近零分数其实是<b>语言覆盖不同</b>造成的假象。<br>"
             f"当前数据库里语言覆盖不完整（不含 cpp+py 全对）的模型有 <b>{len(partial)}</b> 个："
             + "、".join(f"<code>{html.escape(m)}</code>({html.escape(l) or '—'})" for m, l in partial[:12])
             + (" 等" if len(partial) > 12 else "") + "。</p>")
    h.append("<p><b>修复：</b>标准列现在只在 <b>cpp 与 py 都测过</b>时产出 MultiPL-E 单元（有效位宽无关的语言集不再进入比较）；"
             "两者不全者记为缺失（NaN），报告里写 <code>—</code> 且不画点——与“缺失≠ 0”一致。"
             "其它语言（java/js/rs/rb）保留在数据库，供单独的语言子研究。</p>")
    h.append(f"<p><b>2. 全 <code>Exception</code> 的格不是整轮运行失败，也不得记成 0。</b> 构建时扫描 <code>.wrapup/mres/*_eval.json</code> 的状态直方图，"
             f"每道题状态都是 <code>Exception</code> 的有 <b>{n_all_exc}</b> 份文件，来自 <b>{n_cells}</b> 个格："
             f"其中 <b>{n_fixed}</b> 份是同一格的 <code>_fixed</code> 重判（只把后处理换成正确的、重判旧落盘完成物，每道题仍是 <code>Exception</code>），"
             f"<b>{n_probe}</b> 份是 5 题探针（n=5，不是 161 题整格）。它们都不构成可用分数："
             "全 Exception 一律记为缺失（NULL）、不得写成 0；库中对应的格要么是 NULL，要么已被后来的重测取代。"
             "把这类格读成整轮运行失败的旧归因已撤回（<code>docs/subprojects/i01-判分与基准有效性/RESULT.md::res17b</code>）；"
             "把它们归因为旧后处理破坏首行缩进的归因也已撤回（<code>::res21</code>）：同一签名在修正后的 harness 下依然存在，"
             "成因见下一条。</p>")
    h.append("<p><b>重测后这些格按真实通过数记分。</b> gemma-4-26B-A4B 在 chat 协议下的格，库中当前值与配对的评测状态："
             + "；".join(g26b_cells)
             + "。两个 py 格的 <code>Exception</code> 来自模型行为：模型把函数体首行写在第 0 列，拼接后必然缩进错误；"
             "每格「首行在第 0 列」的完成物条数与该格 <code>Exception</code> 条数逐格相等，而同为 py 的 Qwen3.8-27B Q3 格几乎没有这种完成物、得分很高，"
             "所以不是 harness 剥离（<code>docs/subprojects/i01-判分与基准有效性/RESULT.md::res24</code>）。</p>")
    h.append("<p><b>3. 生成协议会改变结论（轴 an7）。</b> 同一模型 gemma-4-26B-A4B 的 cpp："
             + "；".join(f"<code>{html.escape(p)}</code> → {v}" for _m, p, v in prot)
             + "。raw（纯补全）对 gemma 系列是不公平的：它的模板会先输出推理/散文，raw 下几乎全不通过（harness floor）。"
             "所以旧的 raw MultiPL-E 对 gemma 家族不可比。这正是“换协议必须重测”。</p>")
    h.append("<p><b>4. 模型规模曲线“越大越差”有两类原因，要分开看：</b>"
             "(a) <b>方案反向</b>：Qwen3.5-2B 在相邻的跨供应商档位上，字节更多的一档分数反而更低——同名档位跨供应商/方案不可比（当前值见 "
             "<code>docs/subprojects/a01-量化位宽/RESULT.md::res5</code>）；"
             "(b) <b>协议/测集不可比</b>：gemma-4 的 12b/26B 近零来自 raw 协议与语言覆盖，见上。"
             "剩下同家族、同方案、同协议的单调趋势是真实的规模效应。</p>")
    h.append("</div>")
    return "\n".join(h)


def run_tag_inventory():
    rows = CON.execute(
        "SELECT run_tag, count(*) n, count(distinct model) nm, count(distinct _bench) nb, "
        "sum(CASE WHEN source_file LIKE 'mres/%' THEN 1 ELSE 0 END) mres "
        "FROM experiments WHERE run_tag IS NOT NULL AND run_tag<>'' GROUP BY run_tag ORDER BY run_tag").fetchall()
    h = ["<div class='scroll'><table class='inv'><tr><th>run_tag（研究批次）</th><th>行数</th>"
         "<th>模型数</th><th>基准数</th><th>入报告方式</th></tr>"]
    for tag, n, nm, nb, mres in rows:
        where = "标准基准列（表 A–H 的来源）" if mres else "独立面板（部分尚未进报告）"
        cls = "" if mres else " class='nr'"
        h.append(f"<tr><td><code>{html.escape(tag)}</code></td><td>{n}</td><td>{nm}</td><td>{nb}</td>"
                 f"<td{cls}>{where}</td></tr>")
    h.append("</table></div>")
    return "\n".join(h)


def main():
    # 清掉上一次的旧图，避免 report/figures 目录里残留不再引用的文件
    for fn in os.listdir(FIGDIR):
        if fn.endswith(".png"):
            try:
                os.remove(os.path.join(FIGDIR, fn))
            except OSError:
                pass
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

    T_MPL = table_mpl_langs()
    T_BFCL = table_bfcl()
    T_TF = table_testfrac()
    sections = [
        ("一、量化位宽（每个权重平均几个比特）",
         "X = 有效位宽（越大表示每个权重平均比特越多）；Y = 各基准分数；系列 = 模型家族（同家族 = 同一套 base 权重，只换量化文件）。",
         [T["A"]], fig_A(T["A"]),
         inversion_callout() +
         "<ul>"
         "<li>每条线是一个家族。多数家族在低比特一端分数很低，<b>在约 3–4 比特/权重之间出现明显抬升</b>，再往上（约 4 比特/权重以上）基本走平。</li>"
         "<li>抬升幅度在不同基准上差别很大：代码（HumanEval+/MBPP+）、推理（GSM8K）、指令（IFEval）抬升明显；"
         "知识（MMLU）、科学（ARC-c）、事实性（TruthfulQA）几乎不动。这就是“量化伤害取决于你测哪个基准”的来源。</li>"
         "<li>并非所有家族都这样：Qwen3.6-35B-A3B（大 MoE）在很低的比特上已经很高，抬升不明显——说明伤害大小取决于“低比特是否真的伤了这个模型”。</li>"
         "<li>操作结论：<b>量化位宽至少要到约 4 比特/权重；再往上除非能测出具体收益，否则多花比特买不到分数</b>（花岗岩 granite 是例外，继续加比特仍有收益）。</li>"
         "<li><b>看图要点：</b>A 图已按家族拆成一格一格，比原来十几条线叠在一起清楚得多——"
         "黄色带（3–4 比特/权重）内多数格子里的曲线正在爬升，带外右侧趋平；"
         "坡度最陡的格子是 GLM-4.7-Flash、Llama-3.2、Phi-4、granite-4.1，"
         "而 Qwen3.6-35B-A3B、Qwen3.8-27B、Ornith-1.5-9B 的格子几乎是一条平线。</li>"
         "<li><b>系列划分与数据一致性（重要）：</b>一个家族在数据库里若同时存在 UD 动态量化与非 UD 的“原生 K”文件，"
         "本轴会把它们<b>拆成两条独立系列</b>，绝不连成一条曲线——不同供应商的同名档位（如 Q3_K_XL 与 Q3_K_M），"
         "权重分配不同，混在一起会把不可比的东西画成趋势。唯一出现混用的是 <b>Qwen3.6-35B-A3B</b>："
         "UD-Q3_K_XL（3.88）与 bartowski 原生 Q3_K_M（3.86）位宽几乎相同。因为本轴要求“家族内至少 2 个位宽点”，"
         "原生那一支只有 1 个点，被本轴规则剔除；它们的正确对比位置是第三节（方案 / 厂商）——那里才是控制变量的地方，"
         "结果显示两者各基准分数都在噪声内一致，与“厂商标签测不出差异”一致。</li>"
         "</ul>"),
        ("二、模型规模（参数量）",
         "X = 模型参数量（单位 B）；Y = 各基准分数；系列 = 家族 + 量化配方。",
         [T["B"]], fig_B(T["B"]),
         "<ul>"
         "<li>同一配方下，参数量越大分数越高。</li>"
         "<li>小模型之间（0.8B→2B→4B）的差距通常比大模型之间更大——大模型已接近各自的分数上限，规模带来的边际收益变小。</li>"
         "<li>规模还会影响低比特的表现：小模型在低比特的困难任务上会整体触底（见“量化位宽”一节里 2B 的曲线）。</li>"
         "<li><b>看图要点：</b>B 图同色 = 同族，不同线型 / 标记 = 不同配方。Qwen3.5 的三条配方线都在 4B 附近到顶；"
         "gemma-4 的线在 13B 附近有一个向下回折后再上抬的折点——这是不同尺寸在不同配方下的实测值，不是单调趋势。</li>"
         "</ul>"),
        ("三、量化方案 / 厂商",
         "X = 量化方案或厂商（在同一模型、相近的有效位宽区间内）；Y = 各基准分数。",
         [T["C"]], fig_C(T["C"]),
         "<ul>"
         "<li>在文件字节接近的前提下，换<b>方案</b>（例如 IQ 系列 vs 传统 K 系列）分数会出现可测的差异。</li>"
         "<li>而换<b>厂商</b>标签（同一模型、大小差不到 1%）基本测不出差异。</li>"
         "<li>结论：挑量化时应该比“字节 / 方案”，而不是比厂商标签。</li>"
         "<li><b>看图要点：</b>C 图把“同一模型、有效位宽相近”的柱分到组（柱顶白框标出组名与位宽区间），只有组内比较才公平；"
         "一眼可见 Qwen3.5-2B 组里 IQ2_XXS 明显垫底，而其余各组内部两根柱高度接近、误差棒大幅重叠。</li>"
         "<li><b>本节的必要性：</b>正因为 A 轴不把“换供应商方案”当成家族曲线，"
         "Qwen3.6-35B-A3B 的 UD-Q3_K_XL vs 原生 Q3_K_M（3.88 vs 3.86 比特/权重）只在这里比较："
         "两者所有基准差都在噪声内，与“同大小下换厂商标签测不出差异”一致。</li>"
         "</ul>"),
        ("四、MoE 各层比特分配",
         "X = 哪些层拿低比特（专家层 vs 其余层），固定同一套 base 权重；Y = 各基准分数。",
         [T["D"]], fig_D(T["D"]),
         "<ul>"
         "<li>三条配方里，把<b>非专家层</b>压到最低的那条分数最低——尽管它的总比特最多（4.48 比特/权重）。</li>"
         "<li>把<b>专家层</b>压到最低、其余层保持高位的那条，反而保住了大部分能力，且总比特更低（2.92）。</li>"
         "<li>原因：非专家层（注意力、归一化等）每个 token 每次前向都会用到；单个专家只有一部分 token 会走到，"
         "MoE 的路由可以绕开被压坏的专家。所以要保护非专家层，专家层是省比特的安全区。</li>"
         "<li><b>看图要点：</b>D 图三根柱的总比特从左到右是 3.88、2.92、4.48；"
         "最右边那根比特最多、分数却最低，把“压非专家层代价最大”直接画了出来。</li>"
         "</ul>"),
        ("五、KV 缓存精度",
         "X = KV 缓存的精度（f16 / q8_0 / q4_0），固定模型、权重位宽与上下文；Y = 各基准分数。",
         [T["E"]], fig_E(T["E"]),
         "<ul>"
         "<li>三种精度（f16、q8_0、q4_0）的柱几乎等高，即在这类任务上<b>测不出差别</b>。</li>"
         "<li>注意范围：这里的上下文只有约 1k–2k tokens。KV 量化理论上只会在上下文很长时才咬人，"
         "所以这个结论只覆盖短到中等上下文，长上下文未测。</li>"
         "<li><b>看图要点：</b>E 图每个上下文长度一组柱，组内几根几乎等高、误差棒大幅重叠——"
         "这就是“在当前题目数下测不出差异”的直观样子（不等于相等）。</li>"
         "</ul>"),
        ("六、采样 / 解码参数",
         "X = 采样参数（温度、top_k），固定模型、位宽与上下文；Y = 多语言代码通过率。",
         [T["F"]], fig_F(T["F"]),
         "<ul>"
         "<li>温度从 0 升到 0.3/0.7 会压低代码通过率。</li>"
         "<li>top_k 在贪心附近（温度 0）基本不变——这是结构事实：温度 0 时没有分布可截断，top_k 无从生效。</li>"
         "<li>知识类基准（MMLU）对采样完全无反应，因为它用对数似然打分、根本不采样。这反过来证明测量链路是对的。</li>"
         "<li><b>看图要点：</b>F 图左（温度）各条线随温度下走或走平；右（top_k）在温度 0 的那条是严格水平线，"
         "结构上本该如此。</li>"
         "</ul>"),
        ("七、投机解码（速度）",
         "X = 投机解码草稿深度；Y = 每秒生成 token 数（取自 llama-server 自身计时）；系列 = 模型。",
         [T["G1"]], fig_G1(T["G1"]),
         "<ul>"
         "<li>草稿深度越大，生成速度越快。</li>"
         "<li>模型越大，加速收益越大（0.8B 约 +36%，9B 约 +93%）——小模型本身已受内存带宽限制，草稿路径可利用的余量更小。</li>"
         "<li><b>看图要点：</b>G1 图线端直接标了相对深度 0 的提速百分比，模型越大数字越大、曲线越陡。</li>"
         "</ul>"),
        ("八、投机解码（质量）",
         "X = 草稿深度；Y = 各基准分数；系列 = 模型。",
         [T["G2"]], fig_G2(T["G2"]),
         "<ul>"
         "<li>分数随草稿深度几乎不变，没有一致方向的损伤或增益。</li>"
         "<li>MMLU 在每个模型、每个深度上<b>逐位相同</b>：它走对数似然打分，不经过草稿模型。这是测量正确的正对照。</li>"
         "<li>因此投机解码可以放心开：它买速度，不伤质量（在测试的深度范围内）。</li>"
         "<li><b>看图要点：</b>G2 图右侧的“差值”面板把纵轴放大到 ±0.05，所有点仍贴在 0 线上——MMLU 甚至逐点完全相同。</li>"
         "</ul>"),
        ("九、思考开关",
         "X = 是否开启思考（reasoning）；Y = GSM8K 分数；系列 = 模型文件。",
         [T["H"]], fig_H(T["H"]),
         "<ul>"
         "<li>开与关的差随模型与生成预算而定，没有统一方向。</li>"
         "<li>在预算较小的情况下，开思考反而更低：推理流占用了答案预算。</li>"
         "<li>因此主协议统一使用“关思考”；开思考只作为单独诊断轴保留，不与主结果混用。</li>"
         "<li><b>看图要点：</b>H 图用横向哑铃线：圆点 = 思考关，方块 = 思考开，线端数字 = 开−关；"
         "大多数行方块都在圆点左侧（开更低），只有 granite 两行两者几乎重合。</li>"
         "</ul>"),
        ("十、量化感知训练（QAT）",
         "X = 该量化文件是否经过 QAT 训练，固定模型尺寸与标称配方；Y = 各基准分数（并给出差值表）。",
         qat_tables(), fig_QAT(),
         "<ul>"
         "<li>所有 4-bit 配对里，QAT 与原生在多数基准上基本重合，而 QAT 文件还小 0.44–0.95 比特/权重；"
         "唯一的例外是 <b>gemma-4-12B 的 MMLU</b>：QAT 显著更低（−0.197，95% 区间不跨 0）。</li>"
         "<li>2-bit 配对里 QAT 明显更低（代码、算术、指令）。</li>"
         "<li><b>看图要点：</b>森林图把“显著”与“测不出”一眼分开：2-bit 配对的行（红）明显偏向 0 左侧且不跨 0；"
         "4-bit 配对除 12B-MMLU 外都是跨 0 的灰行。</li>"
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
         "<li><b>看图要点：</b>GSQ 图中红星落在原生折线上下不超过一个误差棒；两个星点本身的误差棒很长，"
         "所以“测不出”有一部分是数据分辨力所限。</li>"
         "</ul>"),
        ("十二、扩散式解码（DiffusionGemma）",
         "X = 解码范式（扩散 vs 自回归），对照为同尺寸自回归 gemma-4-26B-A4B；Y = 各基准分数。",
         [], None,
         "<ul><li>本机的 llama.cpp（含 diffusion-cli）不认 <code>diffusion-gemma</code> 架构，处理侧完全没有数据。</li>"
         "<li>因此这一项是<b>未测</b>（不是 0，也不是 null）：需要另建支持该架构的运行时才能比较。</li></ul>"),
        ("十三、多语言代码（MultiPL-E）：逐语言与生成协议",
         "X = 语言（cpp/py/js/java/rs/rb）与生成协议（raw / chat）；Y = 通过率；行 = 模型文件。"
         "这不是“量化位宽”的轴，而是把代码能力的语言维度与协议维度摆出来，用来说明为什么标准列必须固定语言集。",
         [T_MPL], fig_mpl_langs(T_MPL),
         "<ul>"
         "<li>同一模型在不同语言上的通过率差异很大（C++ 与 Python 通常最高，Rust/Ruby/Java 低）。"
         "所以把不同语言平均成一个数之前，必须保证每个模型跑的是同一个语言集，否则不可比。</li>"
         "<li>这就是“12B 崩到 0”的来源：gemma-4-12b 只跑了 java/js/rb/rs，平均后接近 0，而它根本没跑 cpp/py。</li>"
         "<li>raw（纯补全）与 chat（聊天模板、关思考）是两个不同协议；对 gemma 这类模板敏感的模型，"
         "raw 会先输出散文/推理，分数落在 harness floor。报告标准列只用固定协议，且不跨协议混比。</li>"
         "<li><b>行标签里的 <code>·ctx=…</code>／<code>·kv=…</code>／<code>·tmpl=…</code> 是数据库协议串自己记的附加条件，不是排版噪声。</b>"
         "以 gemma-4-12b 为例，它的 cpp 行来自 m6b 面板（<code>ctx=4096</code>、chat 模板未经核对 ⇒ <code>tmpl=unverified</code>），"
         "它的 py 行来自 m161 重测（<code>ctx=2048 --jinja</code>），所以同一个模型的 cpp 与 py 是两套设置，"
         "不能拿来互相解释（<code>docs/subprojects/a01-量化位宽/RESULT.md::res5</code>）。</li>"
         "<li><b>看图要点：</b>热力图中一行内的横向差异 = 语言效应；空白（NaN）= 未测，绝不当作 0。</li>"
         + mpl_ambiguous_note() +
         "</ul>"),
        ("十四、工具调用（BFCL）：协议 × 类别",
         "X = 工具调用协议（提示式 <code>bfcl-prompt</code> vs 原生 <code>bfcl-native-tools</code>，以及多轮官方协议）；"
         "Y = 各类别得分；行 = 模型文件。",
         [T_BFCL], fig_bfcl(T_BFCL),
         "<ul>"
         "<li>这是本报告里另一个“协议就是变量”的例子：同一模型、同一类别，提示式与原生 tools 两种协议的分数差距"
         "常常大于不同模型之间的差距（例如 Qwen3.5-2B 单轮·简单：提示式 0.603 vs 原生 0.217）。"
         "所以工具调用分数必须连同协议一起读，不能只看一个数。</li>"
         "<li>多轮（base / miss_func / miss_param / long_context）目前只在少数锚点上跑过，覆盖很薄，属于<b>待扩测</b>。</li>"
         "<li><b>看图要点：</b>每张图同一模型的柱子高低 = 协议效应；柱子缺失 = 该协议下未测。</li>"
         + bfcl_aggregation_note() +
         "</ul>"),
        ("十五、部分给分（每测试通过比例）",
         "X = 模型（三元/极低位宽 vs 原生 K）；Y = 每道题通过的测试比例（不是 pass@1）；行 = 模型文件。",
         [T_TF], fig_testfrac(T_TF),
         "<ul>"
         "<li>这是“二元 pass@1”之外的辅助度量：如果三元模型与原生模型 pass@1 接近，但每测试通过比例差很多，"
         "说明它们错的测试集不同（部分正确程度不同）。</li>"
         "<li>用途：回答“三元量化是错得更多，还是只是错得不一样”。它与主结论不冲突，只补一个视角。</li>"
         "<li>注意：该度量来自 m41 面板，复用了各面板已有的生成样本（同一协议 <code>mpl-raw-greedy-768</code>），"
         "因此与标准列同源，不引入新协议。</li>"
         "</ul>"),
    ]
    all_tables = []
    for title, defn, tables, figs, analysis in sections:
        section(H, title, defn, tables, figs, analysis)
        all_tables.extend(tables or [])

    H.append("<h2>测量可复现性边界：多少波动值得当真</h2>")
    H.append(reproducibility_html())

    H.append("<h2>数据质量、可比性与待分析</h2>")
    H.append("<p class='def'>这一节不是结论，而是“哪些数字可信、哪些不可比、哪些还没测”的账本："
             "构建时从库与产物复核的数据质量问题、非测量登记册，以及各子项目登记的未解问题索引。"
             "它不引用子项目的工作文档——报告的内容来源是库、<code>report_inputs/</code> 的派生索引"
             "与产品层叙述，所以子项目把工作文档改成什么格式都不会改变报告。</p>")
    H.append(data_quality_html())

    H.append("<h3>非测量登记册（未测 ≠ 0）</h3>")
    H.append(non_measurements_html())

    H.append("<h3>未解问题（各子项目 PLAN.md 的派生索引）</h3>")
    H.append(open_questions_html())

    H.append("<h2>附录：全部研究批次（run_tag）清单</h2>")
    H.append("<p class='def'>报告正文的表格来自标准基准列（<code>mres/%</code>）；其余独立面板也是实际跑过的研究，"
             "本清单把它们列全，标记哪些已进正文、哪些尚待整理。</p>")
    H.append(run_tag_inventory())

    H.append("<h2>附录：本报告用到的全部模型文件与来源</h2>")
    H.append("<p class='def'>下表把正文各节引用的每一个 gguf 文件列出，并给出它的机构（供应商）与仓库，"
             "用于复现与区分“同名档位、不同供应商 / 不同方案”。最后一列是测量当时实际加载入口的解析结果："
             "它记录的是那一轮的运行条件，<b>这些路径（<code>/home/z/hf/…</code>）在采集机上已不存在</b>，"
             "不能当成本机可打开的文件；权重本身不在仓库里，见 README「clone 不能重建什么」。</p>")
    H.append(render_repro(repro_rows(all_tables), title="全部模型文件"))

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
             "<tr><td>量化感知训练 QAT</td><td class='sig'>2-bit 下 QAT 更低；4-bit 中 12B 的 MMLU 显著更低</td><td>4-bit 其余配对</td><td>31B（显存不足）</td></tr>"
             "<tr><td>GSQ-RCO 方案</td><td>—</td><td class='sig'>全部差值都测不出</td><td>—</td></tr>"
             "<tr><td>扩散式解码</td><td>—</td><td>—</td><td class='nr'>运行时缺失</td></tr></table>")
    H.append("<p class='def'><b>一句话总结：</b>量化损失在代码、推理、指令上明显，在选择题知识与事实性上很小；"
             "同文件大小时“换方案”比“数字数”更值得关注。日常选择：<b>量化位宽至少约 4 比特/权重，再往上除非能测出收益否则不必多花比特</b>。</p>"
         "<ul>" + scheme_effects_html() + "</ul>")
    H.append("</body></html>")
    open("report.html", "w").write("\n".join(H))
    print("wrote report.html", os.path.getsize("report.html"), "bytes;",
          "figures:", len([1 for _ in os.listdir(FIGDIR)]),
          "; cjk font: %s sha256=%s" % (CJK_FONT, CJK_FONT_DIGEST))


if __name__ == "__main__":
    main()
