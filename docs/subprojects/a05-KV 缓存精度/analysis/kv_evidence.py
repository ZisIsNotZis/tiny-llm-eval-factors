#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a05 的全部可复算证据：一条命令打印每条预期是否成立，退出码就是结论。

五个检查，各自对应 `RESULT.md` 的一条事实：

  A. m130 标准基准 KV 面板：逐格分数 + HumanEval 的逐题配对翻动（base 与 plus 两套判分）。
     → `RESULT.md::kv-short-panel`
  B. m29 面板：fa=on 臂的 V=f16 vs V=q8_0（n=161，两模型两语言），并核对重复行是否逐格同值。
     → `RESULT.md::kv-short-m29`
  C. m30 旧网格（未加长输入）：同一 KV 配置在 8192/24576/49152 上的 eval 文件逐字节相同。
     → `RESULT.md::kv-ctx-null-by-construction`
  D. m30 加长网格（填充前缀）：逐格分数、逐题状态哈希、以及长前缀格的首个完成物在写什么。
     → `RESULT.md::kv-ctx-padded-floor`
  E. 库内状态：m30 12 行的 cache_type 列是默认值、报告里 6 个 0.0 格属本层。
     → `RESULT.md::kv-db-columns`
  F. m29 入库会让 fa=on/fa=off 在报告行标签里合并：在**库副本**上跑一次 ingest + 报告行分组。
     → `RESULT.md::kv-m29-ingest-decision`
  G. 两个口径的对照：分数差 vs 逐题翻转，以及哪些对被旧结论判成「无差异」却在翻。
     → `RESULT.md::kv-two-metrics`

只读：真库开 `mode=ro`；F 只改 `.tmp/` 下的副本。不改 `report.html`，不调 `migrate_db.py` 的写入口。

    python3 "docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py"
"""
from __future__ import annotations

import collections
import glob
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]                      # …/docs/subprojects/a05-…/analysis → 仓库根
WR = REPO / ".wrapup"
DB = REPO / "experiments.sqlite"
# 负控：A05_SELFTEST=1 时把一个预期改成已知错误的值，装置必须打印 FAIL 并退出 1。
SELFTEST = os.environ.get("A05_SELFTEST") == "1"
results = []


def expect(name, ok, detail):
    results.append((name, bool(ok), detail))
    print(f"[{'ok  ' if ok else 'FAIL'}] {name}: {detail}")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- A: m130 面板
def m130():
    panel_path = WR / "mres/m130-kv/variant_panel.json"
    panel = json.load(open(panel_path))["rows"]
    print("\n== A. m130 标准基准 KV 面板（Qwen3.5-2B Q3，ctx 8192）")
    for label in ("f16/f16", "q8_0/q8_0", "q4_0/q4_0"):
        r = panel[label]
        print(f"  {label:9s} mmlu={r['mmlu']:.4f} gsm8k={r['gsm8k']:.2f} "
              f"ifeval={r['ifeval']:.2f} humaneval(base)={r['humaneval']:.4f} n={r['humaneval_n']}")
    # 逐题配对：evalplus 的 eval_results.json 每任务一条，base/plus 两套判分各算一次。
    def items(tag, key):
        p = WR / f"mres/m130-kv/codegen/{tag}/humaneval/m130-kv-{tag}_openai_temp_0.0_eval_results.json"
        ev = json.load(open(p))["eval"]
        return {k: v[0][key] for k, v in ev.items()}

    print("  逐题配对（HumanEval 164 题，贪心，同一提示集与后处理；lose=前一个配置通过、后一个不通过）")
    flips = {}
    for key in ("base_status", "plus_status"):
        sets = {t: items(t, key) for t in ("f16_f16", "q8_0_q8_0", "q4_0_q4_0")}
        for n, s in sets.items():
            print(f"    {key:11s} {n:9s} pass={sum(v == 'pass' for v in s.values())}/164")
        for a, b in (("f16_f16", "q8_0_q8_0"), ("f16_f16", "q4_0_q4_0"), ("q8_0_q8_0", "q4_0_q4_0")):
            lose = sum(1 for k in sets[a] if sets[a][k] == "pass" and sets[b][k] != "pass")
            gain = sum(1 for k in sets[a] if sets[a][k] != "pass" and sets[b][k] == "pass")
            flips[(key, a, b)] = (lose, gain)
            print(f"    {key:11s} {a}->{b}: lose {lose} gain {gain}")
    expect("A1 面板 humaneval 列取 base 判分",
           abs(panel["f16/f16"]["humaneval"] - 94 / 164) < 1e-9,
           f"0.5732*164={0.5732 * 164:.1f}，逐题 base 通过 94/164 与面板数一致")
    expect("A2 KV 改变个别题的判定（不是逐题相同）",
           flips[("base_status", "f16_f16", "q4_0_q4_0")][0] > 0,
           f"base f16->q4_0 lose/gain={flips[('base_status', 'f16_f16', 'q4_0_q4_0')]}")
    expect("A3 净值方向不一致（不是单调变差）",
           flips[("base_status", "f16_f16", "q4_0_q4_0")][1] > 0,
           f"base f16->q4_0 净 {flips[('base_status', 'f16_f16', 'q4_0_q4_0')][1] - flips[('base_status', 'f16_f16', 'q4_0_q4_0')][0]:+d}/164")


# ---------------------------------------------------------------- B: m29 面板
def m29():
    rows = [json.loads(l) for l in open(WR / "m29_summary.jsonl")]
    print("\n== B. m29 面板（fa × KV，n=161，raw 协议）")
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["cell"], r["model"], r["lang"])].append(r)
    for k in sorted(by):
        ps = [r["pass"] for r in by[k]]
        print(f"  {k}: pass={ps} n={[r['n'] for r in by[k]]} protocol={by[k][0]['protocol']}")
    dup_same = all(len(set(r["pass"] for r in v)) == 1 for v in by.values())
    expect("B1 每个配置的重复行逐格同值（重复入库可无损折叠）", dup_same,
           f"{len(rows)} 行 / {len(by)} 个配置，重复行取值全同")
    pairs = {}
    for model in ("q2", "q3"):
        for lang in ("cpp", "py"):
            a = by[("faon_f16", model, lang)][0]["pass"]
            b = by[("faon_q8", model, lang)][0]["pass"]
            pairs[(model, lang)] = (a, b)
            print(f"  V=f16 -> V=q8_0 (fa=on) {model} {lang}: {a} -> {b} ({b - a:+d}/161)")
    expect("B2 fa=on 下 V=q8_0 与 V=f16 的差双向且 ≤3/161",
           all(abs(b - a) <= 3 for a, b in pairs.values())
           and any(b > a for a, b in pairs.values()) and any(b < a for a, b in pairs.values()),
           f"逐格差 {[b - a for a, b in pairs.values()]}")


# ------------------------------------------------- C: m30 旧网格（未加长输入）
def m30_null():
    print("\n== C. m30 旧网格：同一 KV 在 8192/24576/49152 上的 eval 文件哈希")
    groups = collections.defaultdict(dict)
    for tag in ("f16_f16", "q8_0_f16", "f16_q8_0", "q8_0_q8_0"):
        for ctx in (8192, 24576, 49152):
            p = WR / f"mres/m30-q3-ctx{ctx}-kv{tag}-cpp_eval.json"
            groups[tag][ctx] = sha(p)[:12]
    for tag, d in groups.items():
        print(f"  {tag}: {d}")
    expect("C1 三个 ctx 的逐题状态逐字节相同（-c 在短提示上不改变任何题）",
           all(len(set(d.values())) == 1 for d in groups.values()),
           "4 个 KV 配置 × 3 个 ctx 全部同哈希")


# ------------------------------------------------- D: m30 加长网格
def m30_padded():
    print("\n== D. m30 加长网格：60 题探针，前缀填到 ctx-1024")
    summ = [json.loads(l) for l in open(WR / "m30_summary.jsonl")]
    tab = {}
    for r in summ:
        tab[(r["ctx"], r["kv"])] = (r["pass"], r["n"], r["prompt_tokens"])
        print(f"  ctx={r['ctx']:5d} kv={r['kv']:9s} pass={r['pass']}/{r['n']} "
              f"prompt_tokens={r['prompt_tokens']}")
    hashes = {}
    for p in sorted(glob.glob(str(WR / "mres/m30-ctx*-kv*-cpp_eval.json"))):
        hashes[os.path.basename(p)] = sha(p)[:12]
    dup = collections.Counter(hashes.values())
    print(f"  逐题状态哈希（{len(hashes)} 份）：{sum(1 for c in dup.values() if c > 1)} 组同哈希")
    # 长前缀格的完成物在做什么：是不是接着写填充段
    for tag in ("m30-ctx16384-kvf16_f16", "m30-ctx49152-kvf16_f16"):
        rows = [json.loads(l) for l in open(WR / f"mres/{tag}-cpp.jsonl")]
        imit = sum(1 for r in rows if "canonical Python solution" in (r["completion"] or ""))
        print(f"  {tag}: {imit}/{len(rows)} 个完成物以填充段的注释开头")
    expect("D1 16k/49k 全部格落在地板（≤1/60）",
           all(v[0] <= 1 for (ctx, _kv), v in tab.items() if ctx > 2048),
           "ctx=16384 与 49152 的 8 个格 pass ∈ {0,1}")
    expect("D2 49k 的四个 KV 配置逐题状态完全相同（没有分辨力）",
           len({hashes[f"m30-ctx49152-kv{t}-cpp_eval.json"] for t in
                ("f16_f16", "q8_0_f16", "f16_q8_0", "q8_0_q8_0")}) == 1,
           "49k 四份 eval 同哈希")
    # D3 的判据就是 D1+D2 之外还要看完成物在写什么：填充段模仿
    imit_ok = True
    for tag in ("m30-ctx49152-kvf16_f16",):
        rows = [json.loads(l) for l in open(WR / f"mres/{tag}-cpp.jsonl")]
        imit = sum(1 for r in rows if "canonical Python solution" in (r["completion"] or ""))
        imit_ok = imit >= len(rows) // 2
    expect("D3 长前缀格的完成物在续写填充段（测量的是模仿伪像，不是长上下文能力）", imit_ok,
           "49k 格过半完成物以 “// canonical Python solution (reference):” 开头")


# ------------------------------------------------- G: 分数差 vs 逐题翻转

def m130_items(tag, key):
    p = WR / f"mres/m130-kv/codegen/{tag}/humaneval/m130-kv-{tag}_openai_temp_0.0_eval_results.json"
    ev = json.load(open(p))["eval"]
    return {k: v[0][key] == "pass" for k, v in ev.items()}


def m29_items(tag, lang):
    d = json.load(open(WR / f"mres/m29-{tag}-{lang}_eval.json"))
    return {x["name"]: bool(x.get("pass")) for x in d["details"]}


def flips(a, b):
    lose = sum(1 for k in a if a[k] and not b[k])
    gain = sum(1 for k in a if not a[k] and b[k])
    return lose, gain, sum(a.values()), sum(b.values())


def two_metrics():
    """同一对配置在两个口径下的对照：分数差（旧结论唯一看的东西）与逐题翻转。"""
    print("\n== G. 两个口径：分数差 vs 逐题翻转（同面板、同协议、贪心、单次运行）")
    rows = []
    # m130：逐题产物只有 HumanEval（base 与 plus 两套判分）；lm-eval 三列按 i01::res26 不落逐题。
    for key in ("base_status", "plus_status"):
        s = {t: m130_items(t, key) for t in ("f16_f16", "q8_0_q8_0", "q4_0_q4_0")}
        for a, b in (("f16_f16", "q8_0_q8_0"), ("f16_f16", "q4_0_q4_0"), ("q8_0_q8_0", "q4_0_q4_0")):
            lo, ga, pa, pb = flips(s[a], s[b])
            rows.append((f"m130 HumanEval {key[:4]}", a, b, pb - pa, pa, lo, ga, 164))
    panel = json.load(open(WR / "mres/m130-kv/variant_panel.json"))["rows"]
    for bench in ("mmlu", "gsm8k", "ifeval"):
        n = {"mmlu": 456, "gsm8k": 50, "ifeval": 50}[bench]
        for a, b in (("f16/f16", "q8_0/q8_0"), ("f16/f16", "q4_0/q4_0"), ("q8_0/q8_0", "q4_0/q4_0")):
            pa, pb = round(panel[a][bench] * n), round(panel[b][bench] * n)
            rows.append((f"m130 {bench}", a, b, pb - pa, pa, None, None, n))
    # m29：两条对比轴（V 变化、FA 变化），逐题产物是全量 161。
    for m in ("q2", "q3"):
        for lang in ("cpp", "py"):
            lo, ga, pa, pb = flips(m29_items(f"{m}-faon_f16", lang), m29_items(f"{m}-faon_q8", lang))
            rows.append((f"m29 {m} {lang}", "faon V=f16", "faon V=q8_0", pb - pa, pa, lo, ga, 161))
    for m in ("q2", "q3"):
        for lang in ("cpp", "py"):
            lo, ga, pa, pb = flips(m29_items(f"{m}-faon_f16", lang), m29_items(f"{m}-faoff_f16", lang))
            rows.append((f"m29 {m} {lang}", "fa=on V=f16", "fa=off V=f16", pb - pa, pa, lo, ga, 161))

    print(f"  {'格':22s} {'A':13s} {'B':13s} {'Δ分':>6s} {'A分':>5s} {'丢':>3s} {'得':>3s} {'翻转':>4s} {'n':>4s}")
    for cell, a, b, d, pa, lo, ga, n in rows:
        flip = "—" if lo is None else f"{lo + ga:4d}"
        los = "  —" if lo is None else f"{lo:3d}"
        gas = "  —" if ga is None else f"{ga:3d}"
        print(f"  {cell:22s} {a:13s} {b:13s} {d:+6d} {pa:5d} {los} {gas} {flip} {n:4d}")
    print("  （'—' = 该列没有逐题产物：lm-eval 未开 --log_samples，i01::res26）")

    scored = [(c, a, b, d, lo, ga) for c, a, b, d, _pa, lo, ga, _n in rows if lo is not None]
    blind = [(c, a, b, d, lo, ga) for c, a, b, d, lo, ga in scored if d == 0 and lo + ga > 0]
    worst = max(scored, key=lambda r: r[4] + r[5])
    print(f"  分数差为 0 但逐题在翻的对：{[(c, d, lo, ga) for c, _a, _b, d, lo, ga in blind]}")
    print(f"  翻转最多的对：{worst[0]} {worst[1]}→{worst[2]} Δ分 {worst[3]:+d}，丢 {worst[4]} 得 {worst[5]}")
    expect("G1 存在分数差 0 而逐题集合不同的对（分数差看不见翻转）", len(blind) >= 2,
           f"{len(blind)} 对：" + "、".join(f"{c} {lo}丢{ga}得" for c, _a, _b, _d, lo, ga in blind))
    expect("G2 分数差完全不能预报逐题翻转（存在翻转 ≥5 倍分数差的对）",
           any(lo + ga >= 5 * max(abs(d), 1) for _c, _a, _b, d, lo, ga in scored),
           "、".join(f"{c} {lo + ga}翻/{d:+d}分" for c, _a, _b, d, lo, ga in scored
                    if lo + ga >= 5 * max(abs(d), 1)))
    expect("G3 翻转是双向的（有丢也有得，不是单调退化）",
           sum(1 for _c, _a, _b, _d, lo, ga in scored if lo > 0 and ga > 0) >= 6,
           f"{sum(1 for _c, _a, _b, _d, lo, ga in scored if lo > 0 and ga > 0)}/{len(scored)} 对同时有丢与得")


# ---------------------------------------------------------------- E: 库内状态
def db_state():
    print("\n== E. 库内状态（只读）")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = list(con.execute(
        "SELECT ctx_size, protocol, n_items, _score, cache_type_k, cache_type_v "
        "FROM experiments WHERE run_tag='m30-kv-ctx' ORDER BY ctx_size, protocol"))
    print(f"  m30-kv-ctx 行数 {len(rows)}；cache_type 列取值 " +
          str(sorted({(r[4], r[5]) for r in rows})))
    zeros = list(con.execute(
        "SELECT count(*) FROM experiments WHERE run_tag='m30-kv-ctx' AND _score=0"))
    print(f"  其中 _score=0 的行 {zeros[0][0]}")
    expect("E1 m30 的 cache_type 列全是默认值 q8_0/q8_0（不能用它分组）",
           {(r[4], r[5]) for r in rows} == {("q8_0", "q8_0")},
           f"{len(rows)}/12 行都是 q8_0/q8_0，KV 真实取值只在 protocol 串里")
    expect("E2 报告里的 8 个 0.0 格里 6 个属本层", zeros[0][0] == (7 if SELFTEST else 6),
           f"m30-kv-ctx 的 0.0 行 = {zeros[0][0]}")
    con.close()


# ------------------------------------------- F: m29 入库对报告行键的影响（库副本）
def m29_collision():
    print("\n== F. m29 入库的影响：在库副本上跑一次 ingest + 报告行分组")
    sys.path.insert(0, str(REPO))
    tmp = REPO / ".tmp"
    tmp.mkdir(exist_ok=True)
    copy = tmp / "a05-report-collision.sqlite"
    shutil.copyfile(DB, copy)
    cwd = os.getcwd()
    os.chdir(REPO)                      # make_report 用相对路径连 experiments.sqlite
    try:
        import make_report
        import migrate_db
        con = sqlite3.connect(copy)
        make_report.CON = con
        make_report.ambiguous.clear()
        make_report.table_mpl_langs()
        base = collections.Counter((a["model"], a["label"], a["lang"]) for a in make_report.ambiguous)
        n = migrate_db.ingest_mpl(
            con, str(WR / "m29_summary.jsonl"), "a05-m29-collision", "m29_summary.jsonl",
            model_map={"q2": "Qwen3.5-2B-UD-Q2_K_XL.gguf", "q3": "Qwen3.5-2B-UD-Q3_K_XL.gguf"})
        con.commit()
        make_report.ambiguous.clear()
        make_report.table_mpl_langs()
        after = [(a["model"], a["label"], a["lang"], a["shown"], a["others"], a["protocols"])
                 for a in make_report.ambiguous]
        new = [a for a in after if (a[0], a[1], a[2]) not in base]
        print(f"  入库行 {n}；报告行标签冲突条目：入库前 {len(base)} → 入库后 {len(after)}")
        for a in new:
            print(f"    新冲突: {a[0]} | {a[1]} | {a[2]} | 显示 {a[3]:.4f} | 另有 {a[4]} | 协议 {a[5]} 条")
        # 未触发冲突的三格：fa=on 与 fa=off 的分数相同 → 行标签把两个设置合并而不报警
        merged_silent = [(m, l) for (m, l) in {("Qwen3.5-2B-UD-Q2_K_XL.gguf", "py"),
                                               ("Qwen3.5-2B-UD-Q3_K_XL.gguf", "cpp"),
                                               ("Qwen3.5-2B-UD-Q3_K_XL.gguf", "py")}
                         if (m, "raw·kv=q8_0/f16", l) not in {(a[0], a[1], a[2]) for a in after}]
        print(f"  fa=on/fa=off 被合并且不报警的格：{merged_silent}")
        expect("F1 入库会让 fa=on 与 fa=off 落到同一个行标签",
               len(new) == 1 and len(merged_silent) == 3,
               f"1 格触发行键冲突（q2 cpp 18 vs 17），3 格静默合并")
        con.close()
    finally:
        os.chdir(cwd)
        copy.unlink(missing_ok=True)


# ------------------------------------------- H: 长上下文针检索（WP4 的落盘产物）
NEEDLE_DIR = HERE.parent / "evidence/needle-retune"


def needle():
    """从落盘证据重算长上下文命中率、配对丢/得与阳性对照。

    没有这些文件就判失败（退出码非 0）——「一条命令复算全部数字」必须包括这一批。
    """
    print("\n== H. 长上下文针检索（evidence/needle-retune/，重算而不引用结论）")
    if not NEEDLE_DIR.is_dir() or not list(NEEDLE_DIR.glob("a05-needle-d*.json")):
        expect("H0 长上下文证据存在", False,
               f"缺 {NEEDLE_DIR.relative_to(REPO)}：无法复算长上下文那批数字")
        return
    cells = {}
    for path in sorted(NEEDLE_DIR.glob("a05-needle-d*.json")):
        d = json.load(open(path))
        hits = sum(1 for it in d["items"] if it["answer"] == it["needle"])
        cells[(d["ctx"], d["kv"], bool(d.get("control")))] = d
        print(f"  {path.name}: 重算 {hits}/{d['n_items']}（文件自报 {d['hits']}）"
              + ("  [对照]" if "control" in path.name else ""))
        if "control" not in path.name:
            if hits != d["hits"]:
                expect("H1 每格 hits 可重算", False, f"{path.name}: {hits} != {d['hits']}")
                return
    expect("H1 每格的 hits 都能从逐条判定重算出来", True,
           f"{len([p for p in cells if not p[2]])} 个格子重算与自报一致")

    def hits_of(ctx, kv):
        d = cells.get((ctx, kv, False))
        return None if d is None else sum(1 for it in d["items"] if it["answer"] == it["needle"])

    print("  逐 ctx 配对（f16/f16 vs q4_0/q4_0，同一批 prompt，逐题比较）")
    diffs = {}
    for ctx in (8192, 16384, 32768):
        a, b = cells.get((ctx, "f16/f16", False)), cells.get((ctx, "q4_0/q4_0", False))
        if not a or not b:
            continue
        A = {it["i"]: it["answer"] == it["needle"] for it in a["items"]}
        B = {it["i"]: it["answer"] == it["needle"] for it in b["items"]}
        lose = sum(1 for k in A if A[k] and not B[k]); gain = sum(1 for k in A if not A[k] and B[k])
        diffs[ctx] = (sum(A.values()), sum(B.values()), lose, gain)
        print(f"    ctx={ctx:5d}: f16 {sum(A.values()):2d}/20  q4_0 {sum(B.values()):2d}/20  "
              f"丢 {lose} 得 {gain}")
    if 32768 in diffs:
        f16_32, q4_32, lose32, gain32 = diffs[32768]
        expect("H2 32k 上 f16 与 q4_0 的配对差不超 2/20（本次设计未观察到差异）",
               abs(q4_32 - f16_32) <= 2,
               f"f16 {f16_32}/20 vs q4_0 {q4_32}/20，丢 {lose32} 得 {gain32}")
        expect("H3 动态范围门（v2）成立：f16 在 32k 上 ≥8/20", f16_32 >= 8,
               f"f16 32k = {f16_32}/20")
    # H4：打分器本身能不能失败——纯函数级负控，不需要 GPU。
    import importlib.util
    spec = importlib.util.spec_from_file_location("needle_grid", HERE / "needle_grid.py")
    ng = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ng)
    cases = {"命中：完成物就是针": ("48157", "48157", True),
             "失败：完成物是别的数": ("12345", "48157", False),
             "失败：完成物没有数字": ("I cannot find it.", "48157", False),
             "失败：占位符 12345（旧对照的实际回答）": ("12345", "48157", False)}
    ok = all((ng.first_digits(comp) == needle) == want for comp, needle, want in cases.values())
    print("  打分器单元检查：" + "；".join(
        f"{k} -> {'命中' if (ng.first_digits(c) == nd) else '失败'}" for k, (c, nd, _w) in cases.items()))
    expect("H4 打分器能记命中也能记失败（对照不再被一票否决）", ok, "四例方向全部符合预期")

    ctl = [d for (ctx, kv, is_ctl), d in cells.items() if is_ctl]
    if ctl:
        c = ctl[0]
        recomp = sum(1 for it in c["items"] if it["answer"] == it["needle"])
        same_path = all((it["answer"] == it["needle"]) == it["hit"] for it in c["items"])
        print(f"  对照 {c['cell']}: {recomp}/{c['n_items']}，"
              f"答案形态 {collections.Counter(it.get("answer_shape", "unrecorded") for it in c["items"])}")
        expect("H5 对照格存在、0/20，且逐条 hit==(answer==needle)", recomp == 0 and same_path,
               f"重算 {recomp}/20，逐条一致={same_path}")
    else:
        expect("H5 对照格可用（不是 absent 一票否决的 void 版本）", False,
               "证据里只有 VOID 对照：旧实现的 0/20 是自证。重跑："
               "needle_grid.py --control-only（命令见 RESULT.md::kv-long-ctx-needle）")


def main():
    m130()
    m29()
    m30_null()
    m30_padded()
    db_state()
    two_metrics()
    m29_collision()
    needle()
    bad = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} 条预期成立"
          + ("（A05_SELFTEST=1：E2 被故意设错，装置应当判 FAIL）" if SELFTEST else ""))
    if bad:
        print("不成立：" + "、".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
