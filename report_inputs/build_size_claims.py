#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `a02` 的规模通道与曲线**脚本产物**抽成派生索引，供报告第二节生成文字。

报告第二节原来那三句话（X = 参数量、同配方越大越高、小模型差距更大）在 `a02` 的
`report-size-claims-audit` 里逐条被判过；这里不抄散文，直接读它 `analysis/` 下的两个脚本产物：

  * `size_provenance.json`：3233 行的规模取数通道（`token-rounded` 才是诚实的那个）、
    169 组 1970 行由 GGUF 张量求和测得的真参数量；
  * `size_curves.json`：63 条「同族 + 同配方 + 同基准」的规模曲线，每点带 Wilson 区间与
    `harness_suspect` 标记。

算出来的是：标签通道的分布、真参数量的覆盖率、无配方后缀的格数、Q2_K_XL 的反例步
（gemma-4 12B 相对 4B，区间不重叠）、Q2_K_XL 里最大的正向步、以及被标成 harness 失败的两步
（MultiPL-E cpp/py）。

    python3 report_inputs/build_size_claims.py           # 重写 size_claims.json
    python3 report_inputs/build_size_claims.py --check   # 与现有 json 比对

三种结局必须分开（与 `build_kv_evidence.py` 同一条语义）：0 = 一致；1 = 索引确实落后；
2 = a02 的产物不在场，索引**无法当场核对**——那不是「过期」，也不写成 0。
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "size_claims.json")
A02 = os.path.join(REPO, "docs", "subprojects", "a02-模型规模", "analysis")
PROV = os.path.join(A02, "size_provenance.json")
CURVES = os.path.join(A02, "size_curves.json")


def load():
    return json.load(open(PROV, encoding="utf-8")), json.load(open(CURVES, encoding="utf-8"))


def steps(curve):
    pts = curve["points"]
    for a, b in zip(pts, pts[1:]):
        yield a, b, round(b["score"] - a["score"], 4), not (a["ci"][1] < b["ci"][0] or b["ci"][1] < a["ci"][0])


def protocol_rows():
    """带协议的行里有多少真带规模——「size-null 恰好等于带协议的行」是个错说法，这里当场算。

    直接查库（可复算），因为 a02 的 size_provenance.json 还没把这条拆出来。
    """
    import sqlite3
    con = sqlite3.connect(f"file:{os.path.join(REPO, 'experiments.sqlite')}?mode=ro", uri=True)
    try:
        total, with_size = con.execute(
            "SELECT count(*), sum(__size IS NOT NULL) FROM experiments "
            "WHERE protocol IS NOT NULL AND protocol<>''").fetchone()
        by_proto = con.execute(
            "SELECT protocol, count(*) FROM experiments WHERE protocol IS NOT NULL "
            "AND protocol<>'' AND __size IS NOT NULL GROUP BY 1 ORDER BY 2 DESC").fetchall()
        lmeval_total, lmeval_null = con.execute(
            "SELECT count(*), sum(__size IS NULL) FROM experiments "
            "WHERE protocol LIKE 'lmeval%'").fetchone()
    finally:
        con.close()
    return {"total": total, "with_size": with_size, "null": total - with_size,
            "with_size_by_protocol": [{"protocol": p, "rows": n} for p, n in by_proto],
            "lmeval_total": lmeval_total, "lmeval_null": lmeval_null}


def build():
    prov, cur = load()
    ch_rows = collections.Counter()
    ch_models = collections.Counter()
    for r in prov["rows"]:
        ch_rows[r["channel"]] += r["rows"]
        ch_models[r["channel"]] += 1
    # `rows` 已经覆盖全部 3233 行（含 undecidable 那 1112 行）；`missing` 只是同一批不可判模型的名单，
    # 再加一次会把总数翻倍。
    truth_models = [r for r in prov["rows"] if r.get("truth_source") == "gguf-tensors"]
    truth_rows = sum(r["rows"] for r in truth_models)
    # 169 是「(model,size) 组」的条数，不是模型文件数：同一个文件在不同 db_size 下会出现多条。
    truth_files = len({r["model"] for r in truth_models})
    total_rows = sum(r["rows"] for r in prov["rows"])

    q2 = [c for c in cur["curves"] if c["recipe"] == "Q2_K_XL"]
    q3 = [c for c in cur["curves"] if c["recipe"] == "Q3_K_XL"]

    # gemma-4 Q2_K_XL 的 HUManeval 反例步：12B 低于 4B，且区间不重叠
    inv = None
    for c in q2:
        if c["lineage"] != "gemma-4" or c["bench"] != "humaneval":
            continue
        for a, b, d, overlap in steps(c):
            if d < 0 and not overlap:
                inv = {"bench": c["bench"], "recipe": c["recipe"],
                       "from": {"label": a["label"], "params_b": a["params_b"],
                                "score": a["score"], "ci": a["ci"]},
                       "to": {"label": b["label"], "params_b": b["params_b"],
                              "score": b["score"], "ci": b["ci"]},
                       "delta": d, "overlap": overlap}
    if inv is None:
        raise SystemExit("a02 的曲线里找不到 gemma-4 Q2_K_XL 的反例步；报告不能凭记忆写它")

    # 同一 12B 在 Q3_K_XL 那一格
    same_12b = None
    for c in q3:
        if c["lineage"] != "gemma-4" or c["bench"] != "humaneval":
            continue
        # 同一个 12B（~11.9B）在 Q3_K_XL 那一格的分数：取参数最接近反例终点的那一点
        target = inv["to"]["params_b"] if inv else 11.9
        near = min(c["points"], key=lambda p: abs(p["params_b"] - target))
        same_12b = {"score": near["score"], "ci": near["ci"], "label": near["label"],
                    "n_items": near["n_items"], "params_b": near["params_b"]}

    # Q2_K_XL 里最大的正向步（用来判「小模型差距更大」）
    best = None
    for c in q2:
        for a, b, d, overlap in steps(c):
            if d > 0 and (best is None or d > best["delta"]):
                best = {"bench": c["bench"], "lineage": c["lineage"],
                        "from": {"label": a["label"], "params_b": a["params_b"]},
                        "to": {"label": b["label"], "params_b": b["params_b"]},
                        "delta": d, "overlap": overlap}

    # 被标成 harness 失败的两步（MultiPL-E cpp）
    harness = []
    for c in cur["curves"]:
        if not c["bench"].startswith("humaneval-"):
            continue
        for a, b, d, overlap in steps(c):
            if b.get("harness_suspect") or a.get("harness_suspect"):
                harness.append({"bench": c["bench"], "recipe": c["recipe"],
                                "from": {"label": a["label"], "score": a["score"]},
                                "to": {"label": b["label"], "score": b["score"]},
                                "delta": d})
    # 只保留 cpp 那两步（Q2_K_XL 与 Q3_K_XL）：它们与 a02 记录的 −41.6 / −71.4pp 对应
    cpp = [h for h in harness if h["bench"] == "humaneval-cpp"]
    harness = sorted(cpp or harness, key=lambda h: h["delta"])

    return {
        "sources": [os.path.relpath(PROV, REPO), os.path.relpath(CURVES, REPO)],
        "channels": {"rows": dict(ch_rows), "models": dict(ch_models), "total_rows": total_rows},
        "truth": {"groups": len(truth_models), "files": truth_files, "rows": truth_rows,
                  "of_total_rows": total_rows},
        "protocol_rows": protocol_rows(),
        "skipped_no_recipe": cur["skipped_cells"].get("no recipe", []),
        "curves": {"q2": len(q2), "q3": len(q3), "all": len(cur["curves"])},
        "inversion": inv,
        "same_model_q3": same_12b,
        "q2_max_step": best,
        "harness_failures": harness,
    }


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    missing = [p for p in (PROV, CURVES) if not os.path.exists(p)]
    if missing:
        print(f"UNVERIFIED: a02 的产物不在场（{', '.join(os.path.relpath(p, REPO) for p in missing)}）；"
              f"{os.path.relpath(OUT, REPO)} 无法当场核对（随仓库分发的那份即权威）", file=sys.stderr)
        return 2
    doc = build()
    text = dump(doc)
    if "--check" in argv:
        try:
            have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is missing", file=sys.stderr)
            return 1
        if have != text:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is stale against a02's artefacts; "
                  f"rerun without --check", file=sys.stderr)
            return 1
        print(f"size_claims.json: up to date (truth {doc['truth']['files']} files / "
              f"{doc['truth']['rows']} rows; inversion {doc['inversion']['delta']:+.3f})")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}: truth {doc['truth']['files']} files / "
          f"{doc['truth']['rows']} rows; inversion {doc['inversion']['delta']:+.3f}; "
          f"harness failures {[h['delta'] for h in doc['harness_failures']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
