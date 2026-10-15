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
    "Phi": "#bcbd22", "Ternary": "#004488",
}
_FALLBACK = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
             "#17becf", "#8c564b", "#7f7f7f", "#e377c2", "#bcbd22", "#004488"]
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


def _end_label(ax, x, y, text, color, fs=7.2, dx=5):
    ax.annotate(text, (x, y), xytext=(dx, 0), textcoords="offset points",
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
        byroot = {}
        for c1, c2, cells in t["rows"]:
            c = cells.get(k)
            if not c or c[0] is None:
                continue
            try:
                x = float(c2.split()[0])
            except ValueError:
                continue
            byroot.setdefault(lineage_root(c1), []).append(
                (c1, x, c[0], _se(c[0], c[1])))
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
            items = sorted(byroot[r], key=lambda z: z[1])
            ax.axvspan(3.0, 4.0, color="#f2b134", alpha=.12, zorder=0)
            for j, (name, x, y, e) in enumerate(items):
                col = shade_run(base, j, len(items))
                ax.errorbar([x], [y], yerr=[1.96 * e], fmt=MARKERS[j % len(MARKERS)],
                            ms=6.5, color=col, lw=0, elinewidth=1.1, capsize=2.5, zorder=3)
                _end_label(ax, x, y, variant_of(name, r), col)
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
                        caption="每格一个模型家族；格内不同颜色深浅 / 标记 = 不同尺寸或配方。"
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
        fig, ax = plt.subplots(figsize=(10.6, 5.2))
        pos = 0.0
        xtick, xlab, gsep, cats = [], [], [], {}
        for c1, items in clusters.items():
            fam = c1.split(" @ ")[0]
            lo, hi = (c1.split(" @ ")[-1].replace(" bpw", "").split("-") + [""])[:2]
            for j, (q, y, e) in enumerate(items):
                is_iq = "IQ" in q
                col = "#0f9b8e" if is_iq else "#2c6fbb"
                ax.bar(pos, y, width=.72, color=col, edgecolor="white", lw=.6, zorder=2)
                ax.errorbar(pos, y, yerr=1.96 * e, fmt="none", ecolor="#222",
                            elinewidth=1, capsize=2.5, zorder=3)
                ax.annotate("%.3f" % y, (pos, y), xytext=(0, 2), textcoords="offset points",
                            ha="center", fontsize=6.8)
                xtick.append(pos)
                xlab.append(q.replace("UD-", ""))
                cats["IQ 系列（信息论量化）" if is_iq else "K 系列（传统量化）"] = col
                pos += 1
            gsep.append(pos - 0.5)
            ax.annotate(f"{fam}\n{lo}–{hi} bpw", (pos - len(items) / 2 - .5, -0.11),
                        xycoords=("data", "axes fraction"), ha="center",
                        fontsize=7.2, color="#444")
            pos += 1.0
        for s in gsep[:-1]:
            ax.axvline(s + .5, color="#cfd8e3", lw=.9, ls=":")
        ax.set_xticks(xtick)
        ax.set_xticklabels(xlab, rotation=38, ha="right", fontsize=7.4)
        ax.set_ylim(0, 1.04)
        _style_axes(ax, "量化方案（同一组内 = 同一模型、有效位宽相近）", "基准分数",
                    f"{LBL.get(k, k)}：方案 / 厂商对比")
        ax.legend(handles=[Patch(color=c, label=l) for l, c in cats.items()],
                  fontsize=8, loc="upper left")
        out.append(save(fig, f"C_{k}",
                        caption="竖虚线分隔不同的“模型 + 位宽匹配组”；组内比较换方案。"
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
    temp, topk = {}, {}
    for c1, c2, cells in t["rows"]:
        c = cells.get("multipl_e")
        if not c or c[0] is None:
            continue
        try:
            v = float(c2)
        except ValueError:
            continue
        model = c1.split(" · ")[0]
        if "temperature" in c1:
            temp.setdefault(model, []).append((v, c[0], _se(c[0], c[1])))
        elif "top_k" in c1:
            key = model + (" (temp 0)" if "temp 0" in c1 else "")
            topk.setdefault(key, []).append((v, c[0], _se(c[0], c[1])))
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.0))
    for ax, data, xlab, title in (
            (axes[0], temp, "温度 temperature", "温度对代码通过率的影响"),
            (axes[1], topk, "top_k", "top_k 对代码通过率的影响")):
        for i, (name, pts) in enumerate(sorted(data.items())):
            pts = sorted(pts)
            col = _FALLBACK[i % len(_FALLBACK)]
            ax.errorbar([p[0] for p in pts], [p[1] for p in pts],
                        yerr=[1.96 * p[2] for p in pts],
                        marker=MARKERS[i % len(MARKERS)], ls=LINESTYLES[i % len(LINESTYLES)],
                        color=col, lw=1.7, ms=6, capsize=2.5, label=name)
        _style_axes(ax, xlab, "多语言代码通过率", title)
        ax.legend(fontsize=7.6, loc="best")
    fig.suptitle("采样 / 解码参数：代码通过率", fontsize=13.5)
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
