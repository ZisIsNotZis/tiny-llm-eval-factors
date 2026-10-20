#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP2 后半：规模这个 X 在哪些家族里能当单调量用。

`size_provenance.py` 判出每行的 `__size` 是哪条通道给的；本脚本把结论折成**可用性裁决**，
因为「哪条通道可信」只有落到「这个家族的阶梯能不能比大小」才有意义。

三个候选 X，逐个家族判：

  X = 实测参数量（GGUF 张量求和）  可用 <=> 该文件有实测值
  X = 文件名标签                 可用 <=> 该家族每个文件的 `__size` 通道都是 `token-rounded`
  X = `experiments.__size`        可用 <=> 非空、每个模型只有一个值、且通道是 `token-rounded`

判完再对报告 §2 的那一列（`_bench='humaneval'` + `evalplus-0.3.1-openai-chat-greedy-base`，
n=164）检查「同配方下越大越高」：逐配方看规模序与分数序是否一致，反例给出 Wilson 区间，
用来判「差得动」还是「测不出」。

    python3 "docs/subprojects/a02-模型规模/analysis/size_ladder.py"
    python3 "docs/subprojects/a02-模型规模/analysis/size_ladder.py" --check
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DB = REPO / "experiments.sqlite"
PROV = HERE / "size_provenance.json"
OUT = HERE / "size_ladder.json"

sys.path.insert(0, str(REPO / ".wrapup"))
from mktables import lineage_and_size, recipe_of  # noqa: E402  家族/标签的唯一定义在 i02 的 mktables.py

BENCH, PROTOCOL = "humaneval", "evalplus-0.3.1-openai-chat-greedy-base"


def wilson(p, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load_models():
    prov = json.loads(PROV.read_text(encoding="utf-8"))
    by_file = defaultdict(lambda: {"sizes": set(), "channels": set(), "truth": None,
                                   "truth_source": None, "rows": 0, "null_rows": 0, "gguf": None})
    for r in prov["rows"]:
        f = by_file[r["model"]]
        if r["db_size"] is not None:
            f["sizes"].add(round(r["db_size"], 9))
        f["channels"].add(r["channel"])
        f["truth"] = r["truth_params"] if r["truth_params"] is not None else f["truth"]
        f["truth_source"] = r["truth_source"] or f["truth_source"]
        f["rows"] += r["rows"]
        if r["channel"] == "size-null":
            f["null_rows"] = f.get("null_rows", 0) + r["rows"]
        f["gguf"] = r["gguf"] or f["gguf"]
    return by_file


def scores():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out = {}
    for r in con.execute(
            """select model, _score, n_items from experiments
                where _bench=? and protocol=? and _score is not null""",
            (BENCH, PROTOCOL)):
        out.setdefault(r["model"], []).append((r["_score"], r["n_items"]))
    return out


HONEST = "token-rounded"
# 这两条通道说的是「这一行没有数」或「没有真值可比」，不是「标签被写错了」，
# 所以判标签通道时要把它们与真正的错通道分开。
UNKNOWN = {"size-null", "undecidable"}


def file_status(f):
    """一个模型文件的标签通道状态：honest / dishonest:<通道> / unknown。"""
    ch = set(f["channels"]) - UNKNOWN
    if not ch:
        return "unknown"
    return "honest" if ch == {HONEST} else "dishonest:" + ",".join(sorted(ch))


def verdict(X, files):
    """该家族在候选 X 下是否可用于「族内比大小」，以及理由。"""
    st = {m: file_status(f) for m, f in files.items()}
    honest = [m for m, v in st.items() if v == "honest"]
    dishonest = [m for m, v in st.items() if v.startswith("dishonest")]
    if X == "truth":
        have = [m for m, f in files.items() if f["truth"]]
        return (len(have) >= 2, f"{len(have)}/{len(files)} 个文件有实测参数量"
                                 + ("" if len(have) < len(files) else "（全部）"))
    if X == "label":
        return (not dishonest and len(honest) >= 2,
                f"{len(honest)} 个文件标签=真参数量，{len(dishonest)} 个标签不是参数量"
                + (f"（{', '.join(sorted({st[m] for m in dishonest}))}）" if dishonest else ""))
    if X == "db":
        many = [m for m, f in files.items() if len(f["sizes"]) > 1]
        rows = sum(f["rows"] for f in files.values())
        null = sum(f["null_rows"] for f in files.values())
        cover = (rows - null) / rows if rows else 0.0
        return (not dishonest and not many and len(honest) >= 2,
                f"`__size` 覆盖率 {100 * cover:.0f}%（{rows - null}/{rows} 行有值）；"
                f"{len(many)} 个模型有多个值，{len(dishonest)} 个通道错")
    raise ValueError(X)


def order_check(rungs):
    """rungs = [(truth, score, n)] 按 truth 升序；返回 (是否单调, 反例列表)。"""
    bad = []
    for (t1, s1, n1), (t2, s2, n2) in zip(rungs, rungs[1:]):
        if s2 < s1:
            lo1, hi1 = wilson(s1, n1)
            lo2, hi2 = wilson(s2, n2)
            bad.append({"from": round(t1, 3), "to": round(t2, 3),
                        "drop_pp": round(100 * (s2 - s1), 2),
                        "ci_from": [round(100 * lo1, 1), round(100 * hi1, 1)],
                        "ci_to": [round(100 * lo2, 1), round(100 * hi2, 1)]})
    return (not bad, bad)


def main(argv):
    files = load_models()
    sc = scores()
    lineages = defaultdict(dict)
    for model, f in files.items():
        lin, label = lineage_and_size(model)
        f["label"] = label
        lineages[lin][model] = f

    report = {}
    print(f"{'lineage':22s} {'族内文件':>4s}  X=truth  X=label  X=__size   反例（同配方内变大而分降）")
    for lin in sorted(lineages, key=lambda s: (-len(lineages[s]), s)):
        fam = lineages[lin]
        v_t = verdict("truth", fam)
        v_l = verdict("label", fam)
        v_d = verdict("db", fam)
        # 报告 §2 的 Humaneval 列：同一配方内按 truth 升序看是否单调
        by_recipe = defaultdict(list)
        for m, f in fam.items():
            if f["truth"] and m in sc and sc[m]:
                by_recipe[recipe_of(m)].append((f["truth"], *sc[m][0], m))
        all_bad, n_checked, detail = [], 0, {}
        for rec, pts in sorted(by_recipe.items(), key=lambda kv: str(kv[0])):
            pts.sort()
            rungs = [(t, s_, n) for t, s_, n, _ in pts]
            if len(rungs) < 2:
                continue
            n_checked += 1
            mono, bad = order_check(rungs)
            detail[rec] = {"rungs": [(round(t, 3), round(100 * s_, 1), n_, m)
                                     for t, s_, n_, m in pts], "inversions": bad}
            for b in bad:
                b["recipe"] = rec
            all_bad += bad
        mono = (not all_bad) if n_checked else None
        bad = all_bad
        report[lin] = {
            "files": {m: {"label": f["label"], "truth": f["truth"], "sizes": sorted(f["sizes"]),
                          "channels": sorted(f["channels"]), "score": sc.get(m, [[None, None]])[0][0],
                          "n": sc.get(m, [[None, None]])[0][1]} for m, f in fam.items()},
            "x_truth": {"usable": v_t[0], "why": v_t[1]},
            "x_label": {"usable": v_l[0], "why": v_l[1]},
            "x_db_size": {"usable": v_d[0], "why": v_d[1]},
            "recipes_checked": n_checked, "detail": detail,
            "monotone_in_truth": mono, "inversions": bad,
        }
        print(f"{lin[:22]:22s} {len(fam):>4d}  "
              f"{'yes' if v_t[0] else 'no ':>7s}  {'yes' if v_l[0] else 'no ':>7s}  "
              f"{'yes' if v_d[0] else 'no ':>7s}   "
              + (("none" if mono else
                  f"{len(bad)} 处，最大 {max(abs(b['drop_pp']) for b in bad):.1f}pp")
                 if mono is not None else "—"))

    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(REPO)}   (#bench={BENCH} protocol={PROTOCOL} n=164)")

    if "--check" in argv:
        ok = fail = 0

        def want(cond, label):
            nonlocal ok, fail
            if cond:
                ok += 1
            else:
                fail += 1
                print(f"  FAIL  {label}")

        for lin, label_ok, truth_ok in (("Qwen3.5", True, True),
                                        ("Ternary-Bonsai", True, True),
                                        ("gemma-4", False, True),
                                        ("GLM-4.7-Flash", False, True)):
            want(lin in report, f"{lin} 出现在家族表里")
            if lin not in report:
                continue
            want(report[lin]["x_label"]["usable"] is label_ok,
                 f"{lin}: X=label 可用性应为 {label_ok}（实际 {report[lin]['x_label']['usable']}）")
            want(report[lin]["x_truth"]["usable"] is truth_ok,
                 f"{lin}: X=truth 可用性应为 {truth_ok}（实际 {report[lin]['x_truth']['usable']}）")
        # `__size` 不能当分析 X 的直接证据：报告用的那一列（本脚本的 BENCH/PROTOCOL）
        # 里没有一行带 `__size`。
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        n_both = con.execute("select count(*) from experiments where _bench=? and protocol=? and __size is not null",
                             (BENCH, PROTOCOL)).fetchone()[0]
        n_all = con.execute("select count(*) from experiments where _bench=? and protocol=?",
                            (BENCH, PROTOCOL)).fetchone()[0]
        want(n_both == 0, f"§2 面板（{BENCH}/{PROTOCOL}）里带 __size 的行为 0（实际 {n_both}/{n_all}）")
        # gemma-4 在 Q2_K_XL 上有一个远超噪声的反例（12B 低于 4B），这正是不换数源就不能用的原因。
        g = report.get("gemma-4", {})
        big = [b for b in g.get("inversions", []) if abs(b["drop_pp"]) >= 10]
        want(bool(big), f"gemma-4 至少一处 ≥10pp 的规模反例（实际 {len(big)}）")
        want(report.get("Qwen3.5", {}).get("monotone_in_truth") is True,
             "Qwen3.5 在实测参数量下同配方内单调")
        print(f"  {ok} expected true, {fail} false")
        return 0 if fail == 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
