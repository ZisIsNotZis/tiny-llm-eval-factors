#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受控对清单：跨 `__model`、同基准、同量化档、其余身份栏全同、实测参数量相差 ≤10% 的格。

只读 `experiments.sqlite`（以 `mode=ro` 打开，写不进去），真参数从 a02 入库的 GGUF fixture 读
（`docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json`），不看文件名的 size 标签。

    python3 "docs/subprojects/a15-模型家族/analysis/pairs.py"            # 写 analysis/pairs.json
    python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" --print   # 只打印人读摘要

候选（candidate）的定义，写在这里而不是留在读者脑子里：**同一基准 + 同一个 `__quant`（IS 语义，
NULL==NULL 也算同档）上两个不同 `__model` 的模型文件**。量化档是身份栏之一，所以跨量化档的两个
文件不是「受控对候选」，它们是交互轴（`effects.py`）的原料；`__quant` 不同的跨家族文件对有多少，
本脚本在 `counts.bench_pairs_cross_family_all` 与 `counts.bench_pairs_dropped_by_quant` 里当场
给出，不从候选里静默丢掉。

每个候选按固定顺序判一遍，第一个成立的排除原因写进 `excluded`（因此每个候选恰好落一处——要么
在 `cells` 里至少一格，要么在 `excluded` 里一行，`candidates == excluded + candidates_with_cells` 这条
关系式由脚本自己打印并在 `run_all.py` 里复核）：

    0. family_unknown        某一侧文件的所有行 `__model` 都是 NULL，跨不跨家族不可判
    1. protocol_null         两侧没有任何一对 run 的 `protocol` 同时非空
    2. score_null            在 1 之后，没有任何一对 run 的 `_score` 同时非空
    3. identity_mismatch:…   没有任何一对 run 在 16 个身份栏上全部相等（冒号后点名从不相等的栏，
                             若每栏各自都有相等的 run 对、却凑不出全相等的一对，则写 `:combination`）
    4. no_truth              通过了身份匹配，但某一侧的文件不在 GGUF fixture 里（点名缺哪个）
    5. size_gt_10pct         |n_a-n_b| / max(n_a,n_b) > 0.10
    6. score_ambiguous       同一身份格里某个文件有多条**不同**分数的 run，无法定一个数

一个候选可能有多个身份格：已经产出了受控格、但另有一个歧义格的，那些歧义格进 `partial_ambiguity`
（不占 `excluded` 的一行，否则账不平）。

退出码：0 清单产出；2 输入不可得（库或 fixture 不在）或**候选为空**（看不见输入不算通过）。
"""

from __future__ import annotations

import argparse
import itertools
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEFAULT_DB = REPO / "experiments.sqlite"
DEFAULT_TRUTH = REPO / "docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json"
DEFAULT_OUT = HERE / "pairs.json"

SIZE_TOL = 0.10

# 身份栏：一个受控对要求这些列在两行上逐个相等（NULL==NULL 用 SQL 的 IS 语义）。
# 顺序在这里定义一次，排除原因里的点名与 `ctx_sig` 的键序都由它来。
IDENTITY = [
    "protocol",
    "__quant",
    "ctx_size",
    "parallel_slots",
    "temp",
    "top_p",
    "top_k",
    "min_p",
    "presence_penalty",
    "reasoning",
    "spec_type",
    "spec_draft_n_max",
    "cache_type_k",
    "cache_type_v",
    "max_tokens",
    "n_items",
]
# 去掉量化档后的「上下文签名」：家族效应跨量化档比较时，其余的栏必须逐个不变。
CTX_COLS = [c for c in IDENTITY if c != "__quant"]

SELECT_COLS = ["rowid", "model", "__model", "_bench", "_score", "run_tag"] + IDENTITY


def load_rows(db_path: Path) -> list[dict]:
    """只读打开；`mode=ro` 让「本层不改库」成为连接属性而不是承诺。"""
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        cur = con.execute(f"SELECT {', '.join(SELECT_COLS)} FROM experiments")
        return [dict(zip(SELECT_COLS, r)) for r in cur]
    finally:
        con.close()


def load_truth(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["models"]


def same(a, b) -> bool:
    """IS 语义：None == None 为真，其余按值比较（库里这些栏是 TEXT/INTEGER，不带浮点容差）。"""
    if a is None or b is None:
        return a is None and b is None
    return a == b


def identity_key(row: dict) -> tuple:
    return tuple(row[c] for c in IDENTITY)


def size_delta(truth: dict, a: str, b: str) -> float:
    na = truth[a]["n_params"]
    nb = truth[b]["n_params"]
    return abs(na - nb) / max(na, nb)


def file_families(rows: list[dict]) -> dict[str, str | None]:
    """模型文件 → 家族。

    `__model` 是文件级标签，但库里有 1207 行的 `__model` 是 NULL（早于该列入库的行）。所以按文件
    取**唯一非空值**，而不是按行取最后一个：按行取会把 `{None, 'Qwen3.5'}` 的文件读成 NULL，
    于是它与所有文件都「同族」，跨家族候选全被静默丢掉（这一步真出过一次，见 RESULT.md::bounds
    末尾的记录）。一个文件上出现两个不同的非空家族值时，本函数报错而不是挑一个。
    """
    seen: dict[str, set] = defaultdict(set)
    for r in rows:
        if r["__model"] is not None:
            seen[r["model"]].add(r["__model"])
    out: dict[str, str | None] = {}
    for r in rows:
        vals = seen.get(r["model"], set())
        if len(vals) > 1:
            raise ValueError(f"{r['model']}: more than one __model value {sorted(vals)}")
        out[r["model"]] = next(iter(vals)) if vals else None
    return out


def build(rows: list[dict], truth: dict) -> dict:
    # 1) 每个 (bench, model, __quant) 的 run 列表，供候选枚举与身份匹配复用。候选本身就在一个
    #    (bench, __quant) 上，所以只拿同 `__quant` 的行来配对：`__quant` 那一栏因此恒等，
    #    这与「16 栏全等」的判据一致（它不可能是 mismatch 的那一栏），也把行配对量压下来。
    by_bench_model: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by_bench_model[(r["_bench"], r["model"], r["__quant"])].append(r)
    family_of = file_families(rows)

    # 2) 候选：同基准 + 同 __quant（IS）+ 不同 __model 的两个文件。
    by_bench_quant: dict[tuple, set] = defaultdict(set)
    for r in rows:
        by_bench_quant[(r["_bench"], r["__quant"])].add(r["model"])
    bench_models: dict[str, set] = defaultdict(set)
    for bench, model, _q in by_bench_model:
        bench_models[bench].add(model)

    cross_family_all = 0
    cross_family_quant_same = 0
    family_unknown = 0
    candidates = []
    for (bench, quant), models in sorted(by_bench_quant.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        for a, b in itertools.combinations(sorted(models), 2):
            if family_of[a] is None or family_of[b] is None:
                family_unknown += 1
                candidates.append((bench, quant, a, b))
                continue
            if family_of[a] == family_of[b]:
                continue
            cross_family_quant_same += 1
            candidates.append((bench, quant, a, b))
    for bench, models in bench_models.items():
        for a, b in itertools.combinations(sorted(models), 2):
            if family_of[a] != family_of[b]:
                cross_family_all += 1

    pairs: list[dict] = []
    excluded: list[dict] = []
    partial: list[dict] = []   # 产出了受控格、但同一候选另有歧义身份组的候选
    candidates_with_cells = 0

    for bench, quant, a, b in candidates:
        ra = by_bench_model[(bench, a, quant)]
        rb = by_bench_model[(bench, b, quant)]
        base = {
            "bench": bench,
            "quant": quant,
            "family_a": family_of[a],
            "family_b": family_of[b],
            "model_a": a,
            "model_b": b,
        }
        if family_of[a] is None or family_of[b] is None:
            unknown = [m for m in (a, b) if family_of[m] is None]
            excluded.append(dict(base, reason="family_unknown",
                                 detail="__model is NULL on every row of: " + ", ".join(unknown)))
            continue

        # 1. protocol_null
        pr = [(x, y) for x, y in itertools.product(ra, rb)
              if x["protocol"] is not None and y["protocol"] is not None]
        if not pr:
            excluded.append(dict(base, reason="protocol_null",
                                 detail="no run pair with protocol NOT NULL on both sides"))
            continue
        # 2. score_null
        sc = [(x, y) for x, y in pr if x["_score"] is not None and y["_score"] is not None]
        if not sc:
            excluded.append(dict(base, reason="score_null",
                                 detail="protocol matched but no run pair with _score NOT NULL"))
            continue
        # 3. identity
        matched = [(x, y) for x, y in sc
                   if all(same(x[c], y[c]) for c in IDENTITY)]
        if not matched:
            never = [c for c in IDENTITY
                     if not any(same(x[c], y[c]) for x, y in sc)]
            reason = "identity_mismatch:" + (",".join(never) if never else "combination")
            excluded.append(dict(base, reason=reason,
                                 detail="no run pair equal on all 16 identity columns"))
            continue
        # 4. no_truth
        missing = [m for m in (a, b) if m not in truth]
        if missing:
            excluded.append(dict(base, reason="no_truth",
                                 detail="absent from gguf_truth.json: " + ", ".join(missing)))
            continue
        # 5. size
        delta = size_delta(truth, a, b)
        if delta > SIZE_TOL:
            excluded.append(dict(base, reason="size_gt_10pct",
                                 detail=f"size_delta={delta:.4f} > {SIZE_TOL}"))
            continue

        # 6. 一条受控格 = 一个身份键（含 __quant）上的一对分数
        groups: dict[tuple, list] = defaultdict(list)
        for x, y in matched:
            groups[identity_key(x)].append((x, y))
        got = 0
        ambig: list[dict] = []
        for key, gp in sorted(groups.items(), key=lambda kv: tuple(str(v) for v in kv[0])):
            sa = {x["_score"] for x, _ in gp}
            sb = {y["_score"] for _, y in gp}
            if len(sa) > 1 or len(sb) > 1:
                ambig.append(dict(base, reason="score_ambiguous",
                                  detail=f"model_a scores={sorted(sa)} model_b scores={sorted(sb)}"))
                continue
            x0, y0 = gp[0]
            cells_sorted = sorted({x["_score"] for x, _ in gp})
            pairs.append({
                "bench": bench,
                "quant": quant,
                "family_a": family_of[a],
                "family_b": family_of[b],
                "model_a": a,
                "model_b": b,
                "score_a": cells_sorted[0],
                "score_b": sorted(sb)[0],
                "n_items": x0["n_items"],
                "n_params_a": truth[a]["n_params"],
                "n_params_b": truth[b]["n_params"],
                "bpw_tensors_a": truth[a]["bpw_tensors"],
                "bpw_tensors_b": truth[b]["bpw_tensors"],
                "size_delta": round(delta, 6),
                "protocol": x0["protocol"],
                "ctx_sig": {c: x0[c] for c in CTX_COLS},
                "run_tags_a": sorted({x["run_tag"] for x, _ in gp if x["run_tag"] is not None}),
                "run_tags_b": sorted({y["run_tag"] for _, y in gp if y["run_tag"] is not None}),
                "rows_a": len({x["rowid"] for x, _ in gp}),
                "rows_b": len({y["rowid"] for _, y in gp}),
            })
            got += 1
        # 账要平：每个候选恰好落一处——要么产出了受控格（此时它的歧义只记进 `partial_ambiguity`，
        # 不占 `excluded` 的一行），要么以**第一条**成立的原因进 `excluded`。
        if got:
            candidates_with_cells += 1
            partial.extend(ambig)
        elif ambig:
            excluded.append(ambig[0])

    # 确定性编号：先按 (bench, model_a, model_b, 身份键) 排序再发号，重跑同一输入得同一份清单。
    pairs.sort(key=lambda p: (p["bench"], p["model_a"], p["model_b"],
                              tuple(str(p["ctx_sig"][c]) for c in CTX_COLS)))
    # 落盘时压缩：家族名在上层 `families` 表里查，`protocol` 本就在 `ctx_sig` 里，`ctx` 按
    # `ctx_columns` 的列序存成数组。同一格的内容不变，只去掉重复的字符串。
    slim = []
    for i, p in enumerate(pairs, 1):
        slim.append({
            "id": f"fam{i:04d}",
            "bench": p["bench"],
            "quant": p["quant"],
            "model_a": p["model_a"],
            "model_b": p["model_b"],
            "score_a": p["score_a"],
            "score_b": p["score_b"],
            "n_items": p["n_items"],
            "n_params_a": p["n_params_a"],
            "n_params_b": p["n_params_b"],
            "bpw_a": p["bpw_tensors_a"],
            "bpw_b": p["bpw_tensors_b"],
            "size_delta": p["size_delta"],
            "ctx": [p["ctx_sig"][c] for c in CTX_COLS],
            "tags_a": p["run_tags_a"],
            "tags_b": p["run_tags_b"],
            "rows_a": p["rows_a"],
            "rows_b": p["rows_b"],
        })
    pairs = slim
    families = {m: f for m, f in sorted(family_of.items()) if f is not None}
    excluded.sort(key=lambda e: (e["bench"], str(e["quant"]), e["model_a"], e["model_b"], e["reason"]))

    reasons = Counter(e["reason"] for e in excluded)
    # 「10% 尺寸判据拒掉了什么」按家族对记账：13k 条候选太多，家族对是能读的粒度。
    size_rejected: Counter = Counter()
    for e in excluded:
        if e["reason"] == "size_gt_10pct":
            size_rejected[" | ".join(sorted((e["family_a"], e["family_b"])))] += 1
    # `excluded` 是这个文件里唯一的大表（每个候选一行），所以按列存 + 字符串池：模型文件名很长，
    # 重复 2.3 万次会把清单推到数 MB。`columns.excluded` 与 `strings` 说清楚了列序与索引，
    # 人读的表在 `pairs.py --print` 与 `effects.py` 的输出里。
    pool: dict[str, int] = {}

    def ref(v):
        if v is None or isinstance(v, (int, float)):
            return v
        if v not in pool:
            pool[v] = len(pool)
        return pool[v]

    excluded_rows = [[ref(e["bench"]), ref(e["quant"]), ref(e["family_a"]), ref(e["family_b"]),
                      ref(e["model_a"]), ref(e["model_b"]), ref(e["reason"]),
                      round(size_delta(truth, e["model_a"], e["model_b"]), 6)
                      if e["model_a"] in truth and e["model_b"] in truth else None]
                     for e in excluded]
    return {
        "what": "跨 __model 受控对清单：同基准、同量化档、16 个身份栏全等、实测参数量差 ≤10%",
        "generated_by": "docs/subprojects/a15-模型家族/analysis/pairs.py",
        "truth_fixture": "docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json",
        "size_tolerance": SIZE_TOL,
        "identity_columns": IDENTITY,
        "encoding": ("`cells` 是对象数组（一格一对象）；`excluded` 是按列存的数组，列序见 "
                     "`columns.excluded`，字符串值是 `strings` 里的下标（null 仍是 null）。"
                     "`cells[].ctx` 是除 __quant 外的 15 个身份栏，列序见 `ctx_columns`；"
                     "家族名不存进格子里，在 `families`（模型文件 → 家族）里查。"),
        "columns": {"excluded": ["bench", "quant", "family_a", "family_b", "model_a",
                                "model_b", "reason", "size_delta"]},
        "strings": [s for s, _ in sorted(pool.items(), key=lambda kv: kv[1])],
        "counts": {
            "candidates": len(candidates),
            "controlled_cells": len(pairs),
            "excluded": len(excluded),
            "candidates_with_controlled_cells": candidates_with_cells,
            "candidates_with_family_unknown": family_unknown,
            "partial_ambiguity_rows": len(partial),
            "bench_pairs_cross_family_all": cross_family_all,
            "bench_pairs_dropped_by_quant": cross_family_all - cross_family_quant_same,
            "db_rows_read": len(rows),
            "excluded_by_reason": dict(sorted(reasons.items())),
            "family_pairs_controlled": sorted({f"{family_of[p['model_a']]} | {family_of[p['model_b']]}"
                                              for p in pairs}),
            "benches_with_cells": sorted({p["bench"] for p in pairs}),
            "family_pairs_rejected_by_size": dict(sorted(size_rejected.items(),
                                                        key=lambda kv: (-kv[1], kv[0]))),
        },
        "families": families,
        "ctx_columns": CTX_COLS,
        "cells": pairs,
        "excluded": excluded_rows,
        "partial_ambiguity": [[ref(e["bench"]), ref(e["quant"]), ref(e["family_a"]), ref(e["family_b"]),
                               ref(e["model_a"]), ref(e["model_b"]), ref(e["reason"]), None]
                              for e in partial],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--print", dest="show", action="store_true", help="只打印摘要，不写 JSON")
    args = ap.parse_args(argv)

    if not args.db.is_file():
        print(f"BLOCKED: dataset not found: {args.db}", file=sys.stderr)
        return 2
    if not args.truth.is_file():
        print(f"BLOCKED: truth fixture not found: {args.truth}", file=sys.stderr)
        return 2

    ledger = build(load_rows(args.db), load_truth(args.truth))
    c = ledger["counts"]
    if not c["candidates"]:
        # 看不见输入不算通过：候选为空说明筛选或输入坏了，不是「没有跨家族对」。
        print("BLOCKED: zero candidates — refusing to report an empty inventory", file=sys.stderr)
        return 2

    print("cross-family controlled-pair inventory")
    print(f"  db rows read                    : {c['db_rows_read']}")
    print(f"  candidates (bench+quant+filepair): {c['candidates']}")
    print(f"  controlled cells                : {c['controlled_cells']}")
    print(f"  excluded candidates             : {c['excluded']}")
    print(f"  partial ambiguity rows          : {c['partial_ambiguity_rows']}")
    print(f"  cross-family bench pairs, all   : {c['bench_pairs_cross_family_all']}")
    print(f"  dropped for quant mismatch      : {c['bench_pairs_dropped_by_quant']}")
    print("  excluded by reason              : "
          + ", ".join(f"{k}={v}" for k, v in c["excluded_by_reason"].items()))
    print(f"  family pairs with cells         : {len(c['family_pairs_controlled'])}")
    for fp in c["family_pairs_controlled"]:
        n = sum(1 for p in ledger["cells"]
                if f"{ledger['families'][p['model_a']]} | {ledger['families'][p['model_b']]}" == fp)
        print(f"      {fp:<45} {n} cell(s)")
    print("  benches with cells              : " + ", ".join(c["benches_with_cells"]))
    sr = c["family_pairs_rejected_by_size"]
    print(f"  10% size criterion rejects      : {sum(sr.values())} candidate(s) over "
          f"{len(sr)} family pair(s); largest:")
    for fp, n in list(sr.items())[:8]:
        print(f"      {fp:<45} {n} candidate(s)")
    # 关系式自检（不是快照常量）：每个候选恰好一次——要么产出了受控格，要么被一条原因排除。
    balanced = c["candidates"] == c["excluded"] + c["candidates_with_controlled_cells"]
    print(f"SELFCHECK candidates == excluded + candidates_with_cells: "
          f"{c['candidates']} == {c['excluded']} + {c['candidates_with_controlled_cells']} "
          f"{'ok' if balanced else 'MISMATCH'}")
    if not balanced:
        return 1

    if args.show:
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    shown = args.out.relative_to(REPO) if REPO in args.out.parents else args.out
    print(f"  ledger written                  : {shown}")
    print(f"COUNT candidates={c['candidates']} controlled={c['controlled_cells']} "
          f"excluded={c['excluded']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
