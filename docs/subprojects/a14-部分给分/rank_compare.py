#!/usr/bin/env python3
"""a14 WP3/WP5 — 同一批完成物上二元 pass@1 与逐测试比例的对照。

两个 Y 读自同一批落盘完成物的两份逐题产物：
  * 二元：`.wrapup/mres/<tag>_eval.json` 的 `details[].pass`（harness 的判定，项目报告用的就是它）
  * 比例：`.wrapup/testfrac_<tag>.jsonl` 的 `frac`（分母 = 该题测试源码里的断言数）

配对规则（机械、可复核）：同语言、同一批题数、tag 只在**一个**连字号位置不同 —— 即「只改了一个
命名字段的两个设置」。跨语言不配对、不池化（`AGENTS.md`）。

  python3 "docs/subprojects/a14-部分给分/rank_compare.py"
  python3 "docs/subprojects/a14-部分给分/rank_compare.py" --negative-control   # 打乱一道题的比例，反转计数必须变

退出码：0 = 全部算完；2 = 输入不可得（缺产物/配对为空）。
"""
import argparse
import glob
import json
import os
import random
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
WRAPUP = os.path.join(REPO, ".wrapup")
MRES = os.path.join(WRAPUP, "mres")


def load_cells():
    """{tag: {lang, n, pass, pass_at_1, mean_frac, micro_frac, per_item{name:frac}}}"""
    cells = {}
    for f in sorted(glob.glob(os.path.join(WRAPUP, "testfrac_*.jsonl"))):
        if f.endswith("_summary.jsonl"):
            continue
        tag = os.path.basename(f)[len("testfrac_"): -len(".jsonl")]
        ev = os.path.join(MRES, tag + "_eval.json")
        if not os.path.exists(ev):
            continue
        rows = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        evp = {r["name"]: bool(r["pass"]) for r in json.load(open(ev, encoding="utf-8"))["details"]}
        if set(evp) != {r["name"] for r in rows}:
            raise SystemExit(f"UNMEASURED  {tag}: 逐题文件与 _eval.json 题集不同，拒绝配对")
        n = len(rows)
        passed = sum(1 for v in evp.values() if v)
        fracs = [r["frac"] for r in rows if r["n_tests"] > 0]
        tot_t = sum(r["n_tests"] for r in rows if r["n_tests"] > 0)
        tot_p = sum(r["n_pass"] for r in rows if r["n_tests"] > 0)
        cells[tag] = {
            "lang": tag.rsplit("-", 1)[-1],
            "n": n,
            "pass": passed,
            "pass_at_1": passed / n,
            "mean_frac": sum(fracs) / len(fracs) if fracs else None,
            "micro_frac": tot_p / tot_t if tot_t else None,
            "per_item": {r["name"]: r["frac"] for r in rows},
        }
    if not cells:
        raise SystemExit("UNMEASURED  `.wrapup/testfrac_*.jsonl` + `<tag>_eval.json` 一对都没配上")
    return cells


def one_segment_apart(a, b):
    """两个 tag 只在恰好一个连字号位置不同。"""
    pa, pb = a.split("-"), b.split("-")
    if len(pa) != len(pb):
        return False
    return sum(1 for x, y in zip(pa, pb) if x != y) == 1


def pairs(cells):
    out = []
    tags = sorted(cells)
    for i, a in enumerate(tags):
        for b in tags[i + 1:]:
            ca, cb = cells[a], cells[b]
            if ca["lang"] != cb["lang"] or ca["n"] != cb["n"]:
                continue
            if not one_segment_apart(a, b):
                continue
            out.append((a, b))
    return out


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else float("nan")


def boot_ci(vals, n=2000, seed=0):
    if not vals:
        return (None, None)
    rnd = random.Random(seed)
    N = len(vals)
    means = sorted(sum(vals[rnd.randrange(N)] for _ in range(N)) / N for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def analyse(cells, prs):
    stats = {
        "pairs": len(prs),
        "reversal": [],
        "binary_tie_live": [],
        "binary_tie_dead": [],
        "frac_tie_live": [],
        "near_tie": [],
    }
    for a, b in prs:
        ca, cb = cells[a], cells[b]
        dpass = cb["pass"] - ca["pass"]
        dbin = dpass / ca["n"]
        dfrac = cb["mean_frac"] - ca["mean_frac"]
        if dbin * dfrac < 0:
            stats["reversal"].append((a, b, dpass, dbin, dfrac))
        if dpass == 0:
            common = sorted(set(ca["per_item"]) & set(cb["per_item"]))
            diffs = [cb["per_item"][k] - ca["per_item"][k] for k in common]
            lo, hi = boot_ci(diffs, seed=7)
            rec = (a, b, dfrac, lo, hi, sum(1 for d in diffs if d > 1e-9),
                   sum(1 for d in diffs if d < -1e-9))
            (stats["binary_tie_live"] if lo is not None and (lo > 0 or hi < 0)
             else stats["binary_tie_dead"]).append(rec)
        if abs(dfrac) < 1e-12 and dpass != 0:
            stats["frac_tie_live"].append((a, b, dpass))
        if 0 < abs(dpass) <= 2:
            common = sorted(set(ca["per_item"]) & set(cb["per_item"]))
            diffs = [cb["per_item"][k] - ca["per_item"][k] for k in common]
            lo, hi = boot_ci(diffs, seed=11)
            stats["near_tie"].append((a, b, dpass, dbin, dfrac, lo, hi,
                                      sum(1 for d in diffs if d > 1e-9),
                                      sum(1 for d in diffs if d < -1e-9)))
    return stats


def se_table(cells):
    """两个 Y 在同一批题上的估计精度：二元用二项标准误，比例用题间 bootstrap。"""
    print("\n## 4 同一批题上两个 Y 的估计标准误（题间不确定性，不是跑间噪声）")
    print(f"{'tag':28} {'n':>4} {'pass@1':>8} {'SE(bin)':>8} {'mean_frac':>10} {'SE(frac)':>9} {'SE 比':>6}")
    rows = []
    for tag in sorted(cells):
        c = cells[tag]
        n, p = c["n"], c["pass_at_1"]
        se_bin = (p * (1 - p) / n) ** 0.5
        vals = list(c["per_item"].values())
        lo, hi = boot_ci(vals, n=1000, seed=3)
        sd = (sum((v - sum(vals) / len(vals)) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
        se_frac = sd / len(vals) ** 0.5
        rows.append((tag, n, p, se_bin, c["mean_frac"], se_frac))
        print(f"{tag:28} {n:>4} {p:>8.4f} {se_bin:>8.4f} {c['mean_frac']:>10.4f} {se_frac:>9.4f} "
              f"{(se_frac / se_bin if se_bin else float('nan')):>6.2f}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative-control", action="store_true",
                    help="把每格一题的比例换成另一题的比例（打乱），反转计数必须变化")
    args = ap.parse_args()

    cells = load_cells()
    if args.negative_control:
        base = analyse(load_cells(), pairs(load_cells()))
        base_spear = {lang: spearman(*[[cells[t][k] for t in sorted(cells) if cells[t]["lang"] == lang]
                                       for k in ("pass_at_1", "mean_frac")])
                      for lang in {c["lang"] for c in cells.values()}}
        # 已知错误的副本：同语言内把 mean_frac 在各格之间打乱，破坏「二元—比例」的对应关系。
        # （不可以用「在题间打乱 frac」——那个变换保均值，平均比例不变，测不到东西。）
        rnd = random.Random(0)
        for lang in sorted({c["lang"] for c in cells.values()}):
            ts = [t for t in sorted(cells) if cells[t]["lang"] == lang]
            vals = [cells[t]["mean_frac"] for t in ts]
            rnd.shuffle(vals)
            for t, v in zip(ts, vals):
                cells[t]["mean_frac"] = v
        st = analyse(cells, pairs(cells))
        spear = {lang: spearman(*[[cells[t][k] for t in sorted(cells) if cells[t]["lang"] == lang]
                                  for k in ("pass_at_1", "mean_frac")])
                 for lang in sorted(base_spear)}
        print(f"负控（同语言内打乱 mean_frac）：反转 {len(st['reversal'])} 对（原样 {len(base['reversal'])}），"
              f"二元并列且比例分开 {len(st['binary_tie_live'])} 对（原样 {len(base['binary_tie_live'])}）")
        print("  Spearman 原样 " + " ".join(f"{k}={v:.3f}" for k, v in sorted(base_spear.items())))
        print("  Spearman 打乱 " + " ".join(f"{k}={v:.3f}" for k, v in sorted(spear.items())))
        seen = (len(st["reversal"]) != len(base["reversal"]) or len(st["binary_tie_live"]) != len(base["binary_tie_live"])
                or any(abs(spear[k] - base_spear[k]) > 0.05 for k in base_spear))
        print("  OK  统计跟着比例变了，排序对照看得见比例" if seen
              else "  FAIL  统计没变，排序对照对比例不敏感")
        return 0 if seen else 1

    prs = pairs(cells)
    if not prs:
        print("UNMEASURED  没有满足配对规则的格对")
        return 2

    print(f"格：{len(cells)}；可配对（同语言同题数、tag 只差一个字段）：{len(prs)} 对")
    print("\n## 1 每格的三个 Y")
    print(f"{'tag':28} {'lang':5} {'n':>4} {'pass':>5} {'pass@1':>7} {'mean_frac':>10} {'micro_frac':>11} {'Δ比例-二元':>10}")
    for tag in sorted(cells):
        c = cells[tag]
        d = c["mean_frac"] - c["pass_at_1"]
        print(f"{tag:28} {c['lang']:5} {c['n']:>4} {c['pass']:>5} {c['pass_at_1']:>7.4f} "
              f"{c['mean_frac']:>10.4f} {c['micro_frac']:>11.4f} {d:>+10.4f}")

    print("\n## 2 二元与比例的排序一致度（按语言，不池化）")
    for lang in sorted({c["lang"] for c in cells.values()}):
        ts = [t for t in sorted(cells) if cells[t]["lang"] == lang]
        xs = [cells[t]["pass_at_1"] for t in ts]
        ys = [cells[t]["mean_frac"] for t in ts]
        print(f"  {lang}: {len(ts)} 格，Spearman(pass@1, mean_frac) = {spearman(xs, ys):.4f}")

    st = analyse(cells, prs)
    print(f"\n## 3 配对差（{st['pairs']} 对）")
    print(f"  符号反转（二元说 A>B、比例说 B>A）：{len(st['reversal'])} 对")
    for a, b, dpass, dbin, dfrac in sorted(st["reversal"], key=lambda r: -abs(r[4]))[:12]:
        print(f"    {a} vs {b}: 题数差 {dpass:+d}, 二元 {dbin:+.4f}, 比例 {dfrac:+.4f}")
    print(f"  二元并列（pass 数相同）且比例在 95% 配对 bootstrap 下分开：{len(st['binary_tie_live'])} 对")
    for a, b, dfrac, lo, hi, pos, neg in sorted(st["binary_tie_live"], key=lambda r: -(r[4] - r[3]))[:12]:
        print(f"    {a} vs {b}: Δ比例 {dfrac:+.4f} 95%[{lo:+.4f},{hi:+.4f}] 题级 +/-: {pos}/{neg}")
    print(f"  二元并列但比例也没分开：{len(st['binary_tie_dead'])} 对")
    print(f"  比例并列而二元不同：{len(st['frac_tie_live'])} 对")
    print(f"  近似并列（二元只差 1–2 道题）：{len(st['near_tie'])} 对")
    nt = st["near_tie"]
    agree = sum(1 for r in nt if r[3] * r[4] > 0)
    print(f"    其中比例同向：{agree} 对；反向：{len(nt) - agree} 对")
    sig = 0
    for a, b, dpass, dbin, dfrac, lo, hi, pos, neg in sorted(nt, key=lambda r: -abs(r[4])):
        excl = lo is not None and (lo > 0 or hi < 0)
        sig += 1 if excl else 0
        print(f"    {a} vs {b}: 题数差 {dpass:+d}, 二元 {dbin:+.4f}, 比例 {dfrac:+.4f} "
              f"95%[{lo:+.4f},{hi:+.4f}] {'分开' if excl else '不分'} +/- {pos}/{neg}")
    print(f"    其中比例的 95% 配对区间不含 0（即比例确实把这对分开了）：{sig} 对")
    se_table(cells)
    return 0


if __name__ == "__main__":
    sys.exit(main())
