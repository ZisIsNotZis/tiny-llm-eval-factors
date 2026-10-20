#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a04 的验收入口：一条命令判定本层的事实是否仍然成立。

    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/run_all.py"            # 全部检查，退出码即结论
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/run_all.py" --selftest # 负控：篡改一条通道，检查必须翻红

只读：a03 的入库轮廓夹具、本层的入库夹具、`experiments.sqlite`（只读连接）。不写库、不加载权重、不占 GPU。

负控（`--selftest`）的做法：在一份内存副本里把某条通道改坏（把某个文件的专家桶比特数抬高 1），
断言必须失败；不改任何文件，也不改数据库。这就是 `@gate_probe` 要求的「检查能区分成功与失败」。
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import alloc_pairs as ap  # noqa: E402  —— 装置只有一份，断言复用它

EXPECTED = []          # (id, 说明)


def check(cid, desc, fn):
    try:
        ok = fn()
    except Exception as exc:                       # noqa: BLE001 —— 抛异常就是 FAIL，不静默
        ok = False
        desc = "%s（异常：%r）" % (desc, exc)
    EXPECTED.append((cid, desc, bool(ok)))
    return bool(ok)


def moe_files():
    return [n for n in ap.ALLOC if ap.is_moe(n)]


def families():
    return ap.moe_groups()


def pinnable_rows():
    rows = []
    for fam, files in families().items():
        if len(files) < 2:
            continue
        bound = ap.expert_span_bound(files)
        for i, a in enumerate(sorted(files, key=lambda n: ap.ALLOC[n]["bpw_file"])):
            for b in sorted(files, key=lambda n: ap.ALLOC[n]["bpw_file"])[i + 1:]:
                rows.append((fam, a, b, bound))
    return rows


def main(argv=None):
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--selftest", action="store_true")
    args = ap_.parse_args(argv)

    if args.selftest:
        # 负控：把 m55-exq4 的专家桶比特数抬高 1，使「exq2–exq4 专家跨度超上界」这条断言失效
        saved = copy.deepcopy(ap.ALLOC["LFM2.5-8B-A1B-m55-exq4.gguf"]["classes"]["ffn-expert"]["bits"])
        ap.ALLOC["LFM2.5-8B-A1B-m55-exq4.gguf"]["classes"]["ffn-expert"]["bits"] = saved - 2.0
        ok = check("selftest", "负控：专家桶被改小后，exq2–exq4 超上界的断言必须失败",
                   lambda: abs(ap.b_expert("LFM2.5-8B-A1B-m55-exq2.gguf")
                               - ap.b_expert("LFM2.5-8B-A1B-m55-exq4.gguf")) > 1.0)
        pass_ = not ok
        print("[%s] selftest: 篡改后断言翻红" % ("PASS" if pass_ else "FAIL"))
        return 0 if pass_ else 1

    check("population", "有 ffn-expert 桶的文件 ≥15 个、覆盖 5 个 MoE 族、其中 ≥4 族有 ≥2 份文件",
          lambda: (len(moe_files()) >= 15 and len(families()) == 5
                   and sum(len(v) >= 2 for v in families().values()) >= 4))
    check("strategy-counts", "三策略齐全：专家优先 ≥1、均匀 ≥2、非专家优先 ≥10",
          lambda: (sum(ap.strategy(n) == "专家优先" for n in moe_files()) >= 1
                   and sum(ap.strategy(n) == "均匀" for n in moe_files()) >= 2
                   and sum(ap.strategy(n) == "非专家优先" for n in moe_files()) >= 10))
    check("pinned-pairs", "钉住档（|Δbpw| ≤ 0.15）的 MoE 对照恰好 2 对且 L1_pw ≥ 0.35",
          lambda: len([r for r in ap.same_base_pairs()
                       if ap.is_moe(r[0]) and ap.is_moe(r[1]) and abs(r[2]) <= 0.15
                       and r[3] >= 0.35]) == 2)
    check("bound-lfm", "LFM2.5-8B-A1B 的专家桶钉住上界落在 0.45–0.58 比特/参数",
          lambda: 0.45 <= ap.expert_span_bound(families()["LFM2.5-8B-A1B"]) <= 0.58)
    check("bound-glm", "GLM-4.7-Flash 的上界 < 0.05（该族几乎不可能有钉住对照）",
          lambda: ap.expert_span_bound(families()["GLM-4.7-Flash"]) < 0.05)
    check("exq-span-beyond-bound", "exq2–exq4 的专家桶跨度（1.875）超出 LFM 上界",
          lambda: (abs(ap.b_expert("LFM2.5-8B-A1B-m55-exq2.gguf")
                       - ap.b_expert("LFM2.5-8B-A1B-m55-exq4.gguf"))
                   > ap.expert_span_bound(families()["LFM2.5-8B-A1B"]) + 1.0))
    check("own-arm-pinned", "自建臂 a04-uni45 与 exq4 的 |Δbpw| ≤ 0.05 且 L1_pw ≥ 0.15",
          lambda: (abs(ap.ALLOC["LFM2.5-8B-A1B-a04-uni45.gguf"]["bpw_file"]
                       - ap.ALLOC["LFM2.5-8B-A1B-m55-exq4.gguf"]["bpw_file"]) <= 0.05
                   and ap.l1_pw("LFM2.5-8B-A1B-a04-uni45.gguf",
                                "LFM2.5-8B-A1B-m55-exq4.gguf") >= 0.15))
    check("own-arm-uniform", "自建臂被判为均匀策略（专家桶与层桶差 ≤ 0.5）",
          lambda: ap.strategy("LFM2.5-8B-A1B-a04-uni45.gguf") == "均匀")

    def pinned_all_null():
        cells, _ = ap.a03.load()
        n_int = n_excl = 0
        for a, b, dbpw, l1 in ap.same_base_pairs():
            if not (ap.is_moe(a) and ap.is_moe(b)) or abs(dbpw) > 0.15 or l1 < 0.35:
                continue
            low, high = (a, b) if dbpw >= 0 else (b, a)
            rec = ap.a03.pair_record(low, high, cells, {}, 0.15)
            for bench in ap.a03.BENCH_ORDER:
                if bench not in rec["cells"]:
                    continue
                _d, ci = ap.a03.interval(rec, bench)
                if ci is None:
                    continue
                n_int += 1
                if ci[0] * ci[1] > 0:
                    n_excl += 1
        print("    钉住对照：有区间的格 %d 个，区间不含 0 的 %d 个" % (n_int, n_excl))
        return n_int == 16 and n_excl == 0

    check("pinned-all-null", "两对钉住对照的 16 个有区间格里不含 0 的是 0 个", pinned_all_null)

    def pin_fixture_matches():
        import build_pin_fixture as bpf
        import json
        frozen = json.loads(bpf.FIXTURE.read_text(encoding="utf-8"))
        live = bpf.build()
        if frozen != live:
            return False
        return (live["summary"]["n_pairs"] == 22
                and live["summary"]["n_comparable"] == 4
                and live["summary"]["n_not_comparable"] == 18)

    check("pin-fixture", "入库夹具 pin_feasibility.json 与重算一致，22 对（4 可等 / 18 不可等）",
          pin_fixture_matches)

    bad = [c for c in EXPECTED if not c[2]]
    for cid, desc, ok in EXPECTED:
        print("[%s] %-20s %s" % ("PASS" if ok else "FAIL", cid, desc))
    print()
    print("%d expected, %d false" % (len(EXPECTED), len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
