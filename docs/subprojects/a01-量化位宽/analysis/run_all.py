#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a01 量化位宽：本层全部结论的可执行检查（一条命令，退出码即结论）。

    python3 "docs/subprojects/a01-量化位宽/analysis/run_all.py"          # 检查全部预期
    python3 "docs/subprojects/a01-量化位宽/analysis/run_all.py" --selftest  # 负控：故意改坏一条预期

退出 0 = 每条预期都成立；1 = 至少一条不成立（打印是哪条）；2 = 数据不足（缺文件/缺行）。

每条预期对应 `RESULT.md` 里的一个事实 id，命名与那条事实一致。数据只读 `experiments.sqlite`
（入库）、`.wrapup/bpw_map.json`（入库）与 `analysis/fixtures/mres_snapshot.json`（入库快照，
因为 `.wrapup/mres/*` 被 .gitignore 忽略——干净 clone 里只有这份快照）；本机存在 `.wrapup/mres`
时再与现算值交叉校验。不写库、不改报告。

    --fixture PATH   换一份快照（负控用：删掉一条 → 断言必须变红）
    --selftest       另外把一条断言反过来，证明脚本会失败
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curves                                             # noqa: E402
import channel_audit                                      # noqa: E402
import make_fixtures                                      # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mres_snapshot.json")
FIXTURE_PATH = FIXTURE

DIVERGED = []
COUNT = 0


def expect(ok, fact, detail):
    global COUNT
    COUNT += 1
    print(("  OK   " if ok else "  FAIL ") + f"{fact:<24} :: {detail}")
    if not ok:
        DIVERGED.append(fact)


def pair_rows(cc, needle, qa, qb):
    """返回 {(bench): (kA, nA, kB, nB, lo, hi)}，与 curves.py --pair 同一口径。"""
    res = curves.panel(cc, needle)
    for _fam, pts in res["families"].items():
        qs = [p["quant"] for p in pts]
        if any(qa.lower() in q.lower() for q in qs) and any(qb.lower() in q.lower() for q in qs):
            A = next(p for p in pts if qa.lower() in p["quant"].lower())
            B = next(p for p in pts if qb.lower() in p["quant"].lower())
            out = {}
            for bench in curves.BENCH_ORDER:
                sa, sb = A["scores"].get(bench), B["scores"].get(bench)
                if not sa or not sb:
                    continue
                ka, na = round(sa["score"] * sa["n_items"]), sa["n_items"]
                kb, nb = round(sb["score"] * sb["n_items"]), sb["n_items"]
                lo, hi = curves.newcombe_diff(ka, na, kb, nb) if bench not in curves.NON_COUNT else (None, None)
                out[bench] = (ka, na, kb, nb, lo, hi)
            return out
    return None


def main(argv):
    global FIXTURE_PATH
    FIXTURE_PATH = FIXTURE
    if "--fixture" in argv:
        FIXTURE_PATH = argv[argv.index("--fixture") + 1]
    cc = curves.con()
    selftest = "--selftest" in argv

    # ---- b1-heplus-only：Qwen3.5-2B 的 3.961 → 4.109，只有 HumanEval+ 分得开
    q2 = pair_rows(cc, "qwen3.5-2b", "IQ3_XXS", "Q2_K_XL")
    expect(q2 is not None and len(q2) >= 6, "b1-heplus-only", f"配对行数 {0 if q2 is None else len(q2)}（需 ≥6）")
    if q2:
        lo, hi = q2["humaneval-plus"][4], q2["humaneval-plus"][5]
        expect(lo > 0, "b1-heplus-only", f"HumanEval+ 差区间 [{lo:+.4f}, {hi:+.4f}] 不含 0")
        for b in ("gsm8k", "ifeval", "mbpp-plus", "mmlu", "arc_challenge"):
            lo2, hi2 = q2[b][4], q2[b][5]
            expect(lo2 < 0 < hi2, "b1-heplus-only", f"{curves.SHORT[b]} 差区间 [{lo2:+.4f}, {hi2:+.4f}] 跨 0")

    # ---- q2kxl-iq3-4b：4B 同字节对，方向一致但只有 MMLU 显著
    q4 = pair_rows(cc, "qwen3.5-4b", "IQ3_XXS", "Q2_K_XL")
    expect(q4 is not None and "mmlu" in q4, "q2kxl-iq3-4b", f"4B 配对行数 {0 if q4 is None else len(q4)}")
    if q4:
        lo, hi = q4["mmlu"][4], q4["mmlu"][5]
        expect(lo > 0, "q2kxl-iq3-4b", f"MMLU 差区间 [{lo:+.4f}, {hi:+.4f}] 不含 0")
        lo2, hi2 = q4["humaneval-plus"][4], q4["humaneval-plus"][5]
        expect(lo2 < 0 < hi2, "q2kxl-iq3-4b", f"HumanEval+ 差区间 [{lo2:+.4f}, {hi2:+.4f}] 跨 0")

    # ---- t2-channel-excluded：判分通道不能解释那 22 题（数字来自入库快照，本机有产物时对现算交叉校验）
    snap = {}
    try:
        snap = json.load(open(FIXTURE_PATH, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        expect(False, "fixture", f"读不到入库快照 {FIXTURE_PATH}：{exc}")
    live = make_fixtures.build()                    # 无 .wrapup/mres 时返回 None（干净 clone 的正常情形）
    if live is None:
        print("  note  fixture             :: 本机没有 .wrapup/mres 的逐题产物（clone 里只有入库的 *_eval.json）："
              "跳过与现算的交叉校验，判定只用入库快照")
    else:
        drift = make_fixtures.diff(snap, live)
        expect(not drift, "fixture-fresh",
               "快照与现算一致" if not drift else f"漂移 {len(drift)} 处：{drift[:3]}")
    ca = snap.get("channel_audit", {})
    a = ca.get("m63-qwen-2b-iq3xxs/humaneval")
    b = ca.get("m64-qwen-2b-q2kxl/humaneval")
    expect(bool(a and b), "t2-channel-excluded",
           "两格通道数字都在快照里" if a and b else f"快照缺条目（a={bool(a)} b={bool(b)}）")
    if a and b:
        expect(a["fence_raw"] / a["n"] > 0.9 and b["fence_raw"] / b["n"] > 0.9, "t2-channel-excluded",
               f"原始完成物围栏率 {a['fence_raw']}/{a['n']} 与 {b['fence_raw']}/{b['n']}（两格同样处理）")
        expect("timeout" not in a["plus_status"] and "timeout" not in b["plus_status"], "t2-channel-excluded",
               f"两格 plus 状态都没有 timeout：{a['plus_status']} / {b['plus_status']}")
        expect(b["syntax_err_san"] <= a["syntax_err_san"] and b["no_def_san"] <= a["no_def_san"],
               "t2-channel-excluded",
               f"分数更低的那格 sanitize 后更干净：语法错 {b['syntax_err_san']} ≤ {a['syntax_err_san']}、"
               f"无 def {b['no_def_san']} ≤ {a['no_def_san']}（方向与「通道把 b 判坏」相反）")

    # ---- knee-estimable：只有 Qwen3.5-2B 的 series 有 ≥4 个位宽点、能估拐点
    import numpy as np
    rng = np.random.default_rng(20261020)
    p2b = curves.panel(cc, "qwen3.5-2B")["families"].get("Qwen3.5-2B", [])
    expect(len(p2b) >= 4, "knee-estimable", f"Qwen3.5-2B 位宽点数 {len(p2b)}")
    if len(p2b) >= 4:
        k, ci = curves.knee([(p["bpw"], round(p["scores"]["humaneval-plus"]["score"] * p["scores"]["humaneval-plus"]["n_items"]),
                             p["scores"]["humaneval-plus"]["n_items"]) for p in p2b], rng)
        expect(k is not None and not isinstance(ci, str), "knee-estimable",
               f"HumanEval+ 拐点 {k} 区间 {ci}")
    glm = curves.panel(cc, "GLM-4.7-Flash")["families"].get("GLM-4.7-Flash", [])
    expect(len(glm) == 3, "knee-estimable", f"GLM-4.7-Flash 只有 {len(glm)} 点（<4，故不可估）")

    # ---- adjacent-majority：每列相邻档多数上升
    models = sorted({r[0] for r in cc.execute("SELECT DISTINCT model FROM experiments")})
    fams = {}
    for m in models:
        bw = curves.bpw_of(m)
        if bw is not None:
            fams.setdefault(curves.series_key(m), []).append((bw, m))
    pos = {bch: 0 for bch in curves.BENCH_ORDER}
    neg = {bch: 0 for bch in curves.BENCH_ORDER}
    for _key, items in fams.items():
        items.sort()
        for (b1, m1), (b2, m2) in zip(items, items[1:]):
            for bench in curves.BENCH_ORDER:
                r1 = cc.execute("SELECT _score FROM experiments WHERE model=? AND _bench=? AND protocol=? AND _score IS NOT NULL",
                                (m1, bench, curves.BENCH[bench])).fetchone()
                r2 = cc.execute("SELECT _score FROM experiments WHERE model=? AND _bench=? AND protocol=? AND _score IS NOT NULL",
                                (m2, bench, curves.BENCH[bench])).fetchone()
                if not r1 or not r2:
                    continue
                if r2[0] > r1[0]:
                    pos[bench] += 1
                elif r2[0] < r1[0]:
                    neg[bench] += 1
    for bench in curves.BENCH_ORDER:
        expect(pos[bench] > neg[bench], "adjacent-majority",
               f"{curves.SHORT[bench]} 升 {pos[bench]} / 降 {neg[bench]}")

    # ---- m55-exq-inversion：同 base 权重上比特更多反而更低
    ex = pair_rows(cc, "LFM2.5-8B", "exq2", "exq4")
    expect(ex is not None, "m55-exq-inversion", f"LFM2.5 原生 K 系列的 exq2/exq4 配对 {0 if ex is None else len(ex)} 列")
    if ex:
        for bench in ("humaneval-plus", "mbpp-plus", "mmlu", "gsm8k"):
            lo, hi = ex[bench][4], ex[bench][5]
            expect(lo > 0, "m55-exq-inversion", f"{curves.SHORT[bench]}（少 1.56 比特反而高）区间 [{lo:+.4f}, {hi:+.4f}] 不含 0")

    # ---- ternary-offcurve：GLM-4.7-Flash 的 TQ1 比它自己 3.176 比特档低 30 pp
    glm_tq1 = next((p for p in glm if "TQ1" in p["quant"]), None)
    glm_q2 = next((p for p in glm if p["quant"].endswith("Q2_K_XL")), None)
    expect(glm_tq1 is not None and glm_q2 is not None, "ternary-offcurve", "GLM 的 TQ1_0 与 Q2_K_XL 都在")
    if glm_tq1 and glm_q2:
        d = glm_q2["scores"]["humaneval-plus"]["score"] - glm_tq1["scores"]["humaneval-plus"]["score"]
        expect(d > 0.2, "ternary-offcurve", f"Q2_K_XL(3.176) − TQ1_0(2.226) 的 HumanEval+ 差 {d:+.4f} > 0.20")
        d2 = glm_q2["scores"]["gsm8k"]["score"] - glm_tq1["scores"]["gsm8k"]["score"]
        expect(d2 > 0.2, "ternary-offcurve", f"GSM8K 差 {d2:+.4f} > 0.20")

    # ---- lowbit-spread：2.23–2.28 比特带里 HumanEval+ 跨 42.7 pp
    band = []
    for m in models:
        bw = curves.bpw_of(m)
        if bw is None or not (2.23 <= bw <= 2.28):
            continue
        r = cc.execute("SELECT _score FROM experiments WHERE model=? AND _bench='humaneval-plus'"
                       " AND protocol=? AND _score IS NOT NULL",
                       (m, curves.BENCH["humaneval-plus"])).fetchone()
        if r:
            band.append((bw, m, r[0]))
    if band:
        lo_m = min(band, key=lambda t: t[2])
        hi_m = max(band, key=lambda t: t[2])
        expect(hi_m[2] - lo_m[2] > 0.3, "lowbit-spread",
               f"2.23–2.28 比特带 {len(band)} 个文件：HumanEval+ {lo_m[2]:.4f}（{lo_m[1]}）– "
               f"{hi_m[2]:.4f}（{hi_m[1]}），跨 {hi_m[2]-lo_m[2]:.4f}")

    # ---- gemma12b-mmlu-uniform：12B 原生档 MMLU 跳 22.6 pp 且科目上均匀
    def cell(model, bench):
        r = cc.execute("SELECT _score, n_items FROM experiments WHERE model=? AND _bench=? AND protocol=? AND _score IS NOT NULL",
                       (model, bench, curves.BENCH[bench])).fetchone()
        return r

    nat = "gemma-4-12b-it-UD-Q4_K_XL.gguf"
    q3 = "gemma-4-12b-it-UD-Q3_K_XL.gguf"
    mn, mq = cell(nat, "mmlu"), cell(q3, "mmlu")
    expect(mn and mq, "gemma12b-mmlu-uniform", "两档的 MMLU 行都在")
    if mn and mq:
        expect(mn[0] - mq[0] > 0.2, "gemma12b-mmlu-uniform",
               f"MMLU {mq[0]:.4f} → {mn[0]:.4f}（{mn[0]-mq[0]:+.4f} > 0.20，n={mn[1]}）")
        for bench in ("humaneval-plus", "mbpp-plus", "ifeval"):
            a2, b2 = cell(nat, bench), cell(q3, bench)
            if a2 and b2:
                expect(abs(a2[0] - b2[0]) < 0.05, "gemma12b-mmlu-uniform",
                       f"{curves.SHORT[bench]} 只动 {a2[0]-b2[0]:+.4f}（<0.05，与 MMLU 的跳不同量级）")

    # ---- gemma12b-mmlu-uniform（逐科目表来自快照）：均匀平移而不是少数科目崩坏
    import statistics
    A_acc = (snap.get("mmlu_subjects", {}).get("m105-gemma-12b-q3kxl") or {}).get("acc")
    B_acc = (snap.get("mmlu_subjects", {}).get("m141-native-gemma12b-q4") or {}).get("acc")
    expect(bool(A_acc and B_acc), "gemma12b-mmlu-uniform",
           "两档的逐科目表都在快照里" if A_acc and B_acc else "快照缺 MMLU 科目表")
    if A_acc and B_acc:
        common = sorted(set(A_acc) & set(B_acc))
        ds = [B_acc[k] - A_acc[k] for k in common]
        up = sum(1 for d in ds if d > 0)
        shift = statistics.mean(B_acc[k] for k in common) - statistics.mean(A_acc[k] for k in common)
        expect(len(common) == 61, "gemma12b-mmlu-uniform", f"共同科目 {len(common)}（应 61）")
        expect(up == 51, "gemma12b-mmlu-uniform", f"上升科目 {up}/61")
        expect(abs(statistics.median(ds) - 0.25) < 1e-9, "gemma12b-mmlu-uniform",
               f"中位科目差 {statistics.median(ds):+.4f}（应 +0.2500）")
        expect(abs(shift - 0.2263) < 5e-4, "gemma12b-mmlu-uniform",
               f"整体平移 {shift:+.4f}（应 +0.2263）")


    # ---- gemma12b-mmlu-reproduced（WP5 的两次复测，数字来自入库快照）：值稳定 ⇒ 22.6 pp 不是单次噪声
    runs = snap.get("wp5_mmlu_retest") or []
    expect(len(runs) == 2, "gemma12b-mmlu-reproduced", f"快照里 {len(runs)} 次复测（应 2 次）")
    if len(runs) == 2:
        hist = 0.643640350877193
        expect(all(r["n_items"] == 912 for r in runs), "gemma12b-mmlu-reproduced",
               f"两次题数 {[r['n_items'] for r in runs]}（应都是 912 = 57 科目 × 16）")
        expect(all(abs(r["score"] - hist) < 1e-12 for r in runs), "gemma12b-mmlu-reproduced",
               f"两次都是 {[r['score'] for r in runs]}，与历史 {hist} 逐位相同")
        # 与本层入库的 wp5_result.json 交叉核对（两份产物不许互相漂移）
        wr = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wp5_result.json")
        try:
            wj = json.load(open(wr, encoding="utf-8"))
            pairs = [(x["score"], r["score"]) for x, r in zip(wj.get("runs", []), runs)]
            expect(len(pairs) == 2 and all(abs(a - b) < 1e-12 for a, b in pairs),
                   "gemma12b-mmlu-reproduced",
                   f"wp5_result.json 与快照一致（{[(round(a, 6), round(b, 6)) for a, b in pairs]}）")
            expect((wj.get("peak_proc_mib") or 0) > 0, "gemma12b-mmlu-reproduced",
                   f"wp5_result.json 记了实测峰值 {wj.get('peak_proc_mib')} MiB / 总占用 {wj.get('peak_total_mib')} MiB")
        except (OSError, ValueError) as exc:
            expect(False, "gemma12b-mmlu-reproduced", f"读不到 wp5_result.json：{exc}")

    # ---- q20-loads（WP4 的加载器性质测试，产物入库）：1.7B 三元 Q2_0 能被当前 llama.cpp 读
    tp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "type142_probe.json")
    try:
        t = json.load(open(tp, encoding="utf-8"))
        res = {r["gguf"].split("/")[-1]: r for r in t.get("results", [])}
        r17 = res.get("Ternary-Bonsai-1.7B-Q2_0_g64.gguf")
        expect(bool(r17), "q20-loads", "1.7B 三元 Q2_0 的探针结果在 type142_probe.json 里"
               if r17 else "type142_probe.json 里没有 1.7B Q2_0 那一条")
        if r17:
            expect("加载并生成" in r17["verdict"], "q20-loads", f"{r17['verdict']}（{r17['elapsed_s']}s、峰值 {r17['peak_vram_mib']} MiB）")
        pq = next((v for k, v in res.items() if "PQ2_0" in k), None)
        expect(bool(pq), "pq2-type142", "27B 的 PQ2_0 探针结果在 type142_probe.json 里"
               if pq else "type142_probe.json 里没有 PQ2_0 那一条")
        if pq:
            txt = " ".join(pq.get("stderr_tail") or [])
            expect("ggml type 142" in txt, "pq2-type142",
                   "错误原文含「ggml type 142」（记录里存了 stderr 尾部原文）")
            expect(bool(pq.get("binary")), "pq2-type142", f"二进制版本已记录：{pq.get('binary')}")
            expect(pq.get("peak_vram_mib") == 0, "pq2-type142",
                   f"失败在分配前（峰值 {pq.get('peak_vram_mib')} MiB，空闲显存前后 "
                   f"{pq.get('free_mib_before')}→{pq.get('free_mib_after')}）")
    except (OSError, ValueError) as exc:
        expect(False, "q20-loads", f"读不到 type142_probe.json：{exc}")

    # 负控：把 HumanEval+ 的区间判断反过来，脚本必须失败
    if selftest:
        print("\n[selftest] 故意断言「HumanEval+ 的差区间跨 0」，预期失败：")
        lo, hi = q2["humaneval-plus"][4], q2["humaneval-plus"][5]
        expect(lo < 0 < hi, "b1-heplus-only", f"[selftest] 反过来的断言 [{lo:+.4f}, {hi:+.4f}] 跨 0")

    print(f"\nSUMMARY: {COUNT} 条预期，{len(DIVERGED)} 条不成立 {DIVERGED if DIVERGED else ''}")
    return 1 if DIVERGED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
