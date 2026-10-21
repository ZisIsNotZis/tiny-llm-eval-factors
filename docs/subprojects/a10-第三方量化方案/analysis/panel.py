#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a10 第三方量化方案：面板、位宽与几何的公共装置。

本文件只做三件事，供 `position.py` / `alloc_a10.py` / `build_fixture.py` / `run_all.py` 共用：

  1. **谁是谁**：本层只看 `Qwen3.8-27B` 这一族——三个原生档（unsloth `UD-` 配方）与两个第三方档
     （`GSQ-RCO`）。这五个文件的张量集合逐项相同（866 个张量、参数量 27,320,697,856），所以
     「同族」是实测的，不是按文件名猜的（证明见 `alloc_a10.py` 的输出与 `RESULT.md::tensor-set`）。
  2. **分数格**：只收该基准的规范协议那一行，`protocol / n_items / ctx_size / parallel_slots /
     temp / reasoning` 逐列相等才算可比；同一格多行取 `n_items` 最大者并打印。口径与 `a03` 同一份
     事实，所以这里 `import` 它的 `load()` 与基准表，不复制。
  3. **几何**：最近原生档、夹住某位宽的两个原生档、线性插值，以及区间。区间只有一处定义（`a01::curves`）。

不加载权重、不碰 GPU、不写库、不改 `report.html`。
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE
for _ in range(6):                       # docs/subprojects/a10-第三方量化方案/analysis/panel.py → 仓库根
    REPO = REPO.parent
    if (REPO / "experiments.sqlite").is_file():
        break
else:
    sys.exit("找不到仓库根（experiments.sqlite）")

A03 = REPO / "docs" / "subprojects" / "a03-量化方案与厂商" / "analysis"
A01 = REPO / "docs" / "subprojects" / "a01-量化位宽" / "analysis"
for p in (A03, A01):
    if not p.is_dir():
        sys.exit(f"缺上游装置目录：{p}（a10 借 a01 的区间定义与 a03 的分桶定义，不复制）")
    sys.path.insert(0, str(p))

import curves as a01            # noqa: E402  —— 区间与家族定义（唯一 home）
import pairs as a03             # noqa: E402  —— 规范协议、加载、分桶（唯一 home）

FIXTURE = HERE.parent / "fixtures" / "a10_map.json"

# 第三方档：文件名带该标记就是本层的 X=1 一侧。这是**上传者写的档位名**，不是本层证明过的机制；
# 它到底对应哪种分配由 `alloc_a10.py` 实测。
THIRD_PARTY_MARK = "GSQ-RCO"
THIRD_PARTY = ["Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf",
               "Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf"]
# 原生档：同一族里 unsloth UD 配方的三个档（本层全部的「原生阶梯」）。
NATIVE = ["Qwen3.8-27B-UD-Q2_K_XL.gguf",
          "Qwen3.8-27B-UD-Q3_K_XL.gguf",
          "Qwen3.8-27B-UD-IQ4_XS.gguf"]
# 同一个 tier 标签由别的上传者/另一套 base 权重发布的文件：用来测「标签是不是一个确定的分配配方」。
# 它们**没有**入库分数格（库内只有 ISTA 的那两份），所以只参与分配测量，不参与位置判断。
SIBLINGS = {
    "Dirk-Qwen3.8-27B-GSQ-RCO-IQ3_XXS.gguf": ("peculiar-ragdoll", "IQ3_XXS"),
    "Dirk-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf": ("peculiar-ragdoll", "IQ3_S"),
    "Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_XXS-mtp.gguf": ("huihui-ai", "IQ3_XXS"),
    "Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf": ("huihui-ai", "IQ3_S"),
}
TIER = {"Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf": "IQ3_XXS",
        "Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf": "IQ3_S"}

BENCH = a03.BENCH_ORDER
SHORT = a03.SHORT
NON_COUNT = a03.NON_COUNT
BPW = a03.BPW_MAP


def cells():
    """{model: {bench: cell}}，只保留本层五个文件；同时把重复行与不可比格报告出来。"""
    all_cells, dups = a03.load()
    want = THIRD_PARTY + NATIVE
    missing = [m for m in want if m not in all_cells]
    if missing:
        sys.exit(f"库里缺这些文件的分数格：{missing}"
                 "（本层不把「缺」写成 0，缺就是不可得，退出码 2 由调用方处理）")
    out = {m: dict(all_cells[m]) for m in want}
    return out, [d for d in dups if d[0] in want]


def bpw(model):
    return BPW[model]


def native_ladder():
    """原生阶梯：[(位宽, 文件)]，按位宽升序。"""
    return sorted((BPW[m], m) for m in NATIVE)


def nearest_native(x):
    """位宽差绝对值最小的原生档；并列时取较低的那个并让调用方看到（返回全部并列项）。"""
    lad = native_ladder()
    best = min(abs(b - x) for b, _ in lad)
    ties = [(b, m) for b, m in lad if abs(abs(b - x) - best) < 1e-9]
    return ties


def bracket(x):
    """夹住 x 的两个原生档 (lo, hi)；x 落在阶梯外时返回 None（不外推）。"""
    lad = native_ladder()
    lo = [t for t in lad if t[0] < x]
    hi = [t for t in lad if t[0] > x]
    if not lo or not hi:
        return None
    return lo[-1], hi[0]


def interp(x, lo, hi, p_lo, p_hi):
    """线性插值：把位宽缺口按两档之间的段斜率折成分数。两档之间只给得出这一条直线。"""
    return p_lo + (p_hi - p_lo) * (x - lo) / (hi - lo)


def wilson(k, n):
    return a01.wilson(k, n)


def newcombe(k1, n1, k2, n2):
    """两比例差的 95% 区间（Newcombe method 10），唯一 home 在 a01。"""
    return a01.newcombe_diff(k1, n1, k2, n2)


def cell_diff(a, b, bench):
    """(a − b) 的分数差与 95% 区间。

    差值**一律用入库的分数本身**，不走 `round(score×n)/n` 这条回头路：TruthfulQA 的 `acc` 是
    归一化后的概率质量均值（`i01::res26`），把它当命中数四舍五入会把 +0.0523 变成 +0.0500。
    区间才用计数，且非伯努利列不给区间。
    """
    d = a["score"] - b["score"]
    if bench in NON_COUNT:
        return d, None
    return d, newcombe(k_of(a, bench), a["n_items"], k_of(b, bench), b["n_items"])


def cell_p(a, b, bench):
    """(a − b) 的两条 p 值：(pooled 两比例 z, Fisher 精确)；非伯努利列返回 None。

    为什么要两条：本层唯一「分得开」的那一格在这两条口径上刚好一个过 0.05、一个不过，
    只报一条就等于挑了对自己有利的那条。多条比较的分母见 `position.py` 的 `multiplicity`。
    """
    if bench in NON_COUNT:
        return None
    from scipy.stats import fisher_exact, norm
    k1, n1, k2, n2 = k_of(a, bench), a["n_items"], k_of(b, bench), b["n_items"]
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se if se else float("nan")
    p_z = 2 * (1 - norm.cdf(abs(z)))
    p_f = fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])[1]
    return (p_z, p_f)


def sumwidth_ci(k1, n1, lo2, hi2):
    """一侧是比例、另一侧只有区间（插值档）时的保守合成：两侧 95% 半宽直接相加。

    这不是 Newcombe —— 插值档不是比例，没有 `n`。写清楚比装作有区间更重要：
    这条比两比例差区间**更宽**，所以它判「跨 0」时，真结论一定也跨 0。
    """
    p = k1 / n1
    lo1, hi1 = wilson(k1, n1)
    return (lo1 - hi2, hi1 - lo2)


def k_of(cell, bench):
    return round(cell["score"] * cell["n_items"])


def tensor_fingerprint(tensor_bits):
    """逐张量比特的指纹：{"name": bits} → sha256(\"name\\tbits\" 按名排序)。

    为什么要指纹而不是只存类平均：类平均相同可以掩盖逐张量互换，而「同分配」这件事
    只有逐张量相同才算成立（`AGENTS.md` 第 8 条）。
    """
    txt = "\n".join(f"{n}\t{b:.6f}" for n, b in sorted(tensor_bits.items()))
    return hashlib.sha256(txt.encode()).hexdigest()


def names_fingerprint(tensor_bits):
    """张量名集合的指纹：证明「同一族的张量集合逐项相同」不需要存 866 个名字。"""
    txt = "\n".join(sorted(tensor_bits))
    return hashlib.sha256(txt.encode()).hexdigest()


def load_fixture():
    if not FIXTURE.is_file():
        sys.exit(f"缺入库夹具 {FIXTURE.relative_to(REPO)}：调用方必须把退出码当 2（不可得），不是 0")
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def fmt(x, nd=4):
    return "—" if x is None else f"{x:+.{nd}f}"
