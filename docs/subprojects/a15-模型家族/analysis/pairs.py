#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受控对清单：同基准、同量化档、其余身份栏全同、实测参数量相差 ≤10% 的**跨家族**格。

只读 `experiments.sqlite`（以 `mode=ro` 打开，写不进去），真参数从 a02 入库的 GGUF fixture 读
（`docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json`），不看文件名的 size 标签。

    python3 "docs/subprojects/a15-模型家族/analysis/pairs.py"            # 写 analysis/pairs.json
    python3 "docs/subprojects/a15-模型家族/analysis/pairs.py" --print   # 只打印人读摘要

**家族 = `mktables.family_of` 的规范形（canonical family）**：先取 `.wrapup/mktables.py::family_of(model)`
（随仓库分发，剥掉量化/配方后缀并归一化 `Qwen_` 前缀），再做一次**后缀合并到不动点**：

> 若两个文件的实测参数量完全相同（a02 fixture 的 `n_params`），且 B 的文件名主干以
> `canonical_family(A) + "-"` 开头，则 canonical(B) := canonical(A)；反复做到不再变化。

理由：`family_of` 不剥「家族名 + 供应商/配方尾巴」这类后缀（`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`、
`LFM2.5-8B-A1B-a04-uni45`、`gemma-4-26B-A4B-it-qat`），而**同样的张量形状**说明它就是同一份基座权重的一个
臂（arm），不是另一个家族。合并完全由「文件名前缀 + 实测参数量相等」两条机械条件决定，没有标签白名单；
脚本打印合并表与「每个规范家族吃掉了几个原始标签」，并用一条闭合性自检盯着（不存在「同一参数量、B 以
`canon(A) + "-"` 开头却仍未合并」的文件对）。

会因此被合并的原始标签（本库当前）：`LFM2.5-8B-A1B-a04-uni45` → `LFM2.5-8B-A1B`；
`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`、`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` → `Qwen3.8-27B`；
`gemma-4-26B-A4B-it-qat` → `gemma-4-26B-A4B`。反过来，参数量不同的尾巴**不会**被合并（`Ornith-1.5-9B`
与 `Qwen3.5-9B` 参数量相同但互不为前缀；`Qwen3.5-9B-DeepSeek-V4-Flash` 参数量不同），它们仍算不同家族。

家族标签曾错过一次：第一版用 `experiments.__model`（`exp.py` 从文件名解析的标签），于是
`Qwen3.6-35B-A3B` / `Qwen_Qwen3.6-35B-A3B` 这类同一份权重的标签对被当成跨家族对。

两层口径，本文件与 `effects.py` 与 `RESULT.md` 一律按名字区分：

  * `label_matched`：16 个身份栏逐栏相等（`__quant` 用 IS 语义，NULL==NULL 也算相等）+ `protocol`
    非空 + `_score` 非空 + 尺寸差 ≤10% + 家族不同。**名字只说明标签相同**：`__quant` 为 NULL 时
    这一栏什么都没钉住（库里有 1542 个这样的格），所以 `label_matched` 不等于「同一比特预算」。
  * `bpw_matched`：在 `label_matched` 之上再要求 `|bpw_a − bpw_b| ≤ BPW_MATCH_TOL`（0.25 bpw =
    半个档宽，档宽 `LEVEL_W`=0.5 bpw）。位宽是实测的 GGUF 张量 bpw，不是标签。**家族效应、可读家族对、
    翻转计数一律只在这个子集上算**（见 `effects.py`）。

候选（candidate）的定义：同一基准 + 同一个 `__quant`（IS 语义）上两个**不同家族**的模型文件。
同一家族的配对不是候选：它们要么是同族不同尺寸（尺寸轴，a02），要么是同一份权重的配方/标签变体
（进 `recipe_controls`）。

每个候选按固定顺序判一遍，第一个成立的排除原因写进 `excluded`（每个候选恰好落一处——要么在
`cells` 里至少一格，要么在 `excluded` 里一行，`candidates == excluded + candidates_with_cells` 这条
关系式由脚本打印并在 `run_all.py` 里复核）：

    1. protocol_null         两侧没有任何一对 run 的 `protocol` 同时非空
    2. score_null            在 1 之后，没有任何一对 run 的 `_score` 同时非空
    3. identity_mismatch:…   没有任何一对 run 在 16 个身份栏上全部相等（冒号后点名从不相等的栏，
                             若每栏各自都有相等的 run 对、却凑不出全相等的一对，则写 `:combination`）
    4. no_truth              通过了身份匹配，但某一侧的文件不在 GGUF fixture 里（点名缺哪个）
    5. size_gt_10pct         |n_a-n_b| / max(n_a,n_b) > 0.10
    6. score_ambiguous       同一身份格里某个文件有多条**不同**分数的 run，无法定一个数

一个候选可能有多个身份格：已经产出了受控格、但另有一个歧义格的，那些歧义格进 `partial_ambiguity`
（不占 `excluded` 的一行，否则账不平）。

退出码：0 清单产出；2 输入不可得（库、fixture 或 `.wrapup/mktables.py` 不在）或**候选为空**。
"""

from __future__ import annotations

import argparse
import importlib.util
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
DEFAULT_MKTABLES = REPO / ".wrapup/mktables.py"
DEFAULT_OUT = HERE / "pairs.json"

SIZE_TOL = 0.10      # 实测参数量相对差的上限
LEVEL_W = 0.5        # bpw；一个「量化档」的宽度（本库相邻 Q 档相距 0.5–1.0 bpw）
BPW_MATCH_TOL = LEVEL_W / 2.0   # bpw；两侧位宽差 ≤ 半档才算「同一比特预算」

# 身份栏：一个受控对要求这些列在两行上逐个相等（NULL==NULL 用 SQL 的 IS 语义）。
# 顺序在这里定义一次，排除原因里的点名与 `ctx` 的列序都由它来。
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

SELECT_COLS = ["rowid", "model", "_bench", "_score", "run_tag"] + IDENTITY


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


def load_mktables(path: Path):
    """报告的家族定义只有一处：`mktables.family_of`。拿不到它就 exit 2，不自己再发明一套。"""
    if not path.is_file():
        raise SystemExit(f"BLOCKED: {path} not found — family_of would be undefined")
    spec = importlib.util.spec_from_file_location("a15_mktables", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def bpw_gap(truth: dict, a: str, b: str) -> float:
    return abs(truth[a]["bpw_tensors"] - truth[b]["bpw_tensors"])


def match_groups(ra: list[dict], rb: list[dict]) -> tuple[str | None, list]:
    """把两侧的 run 按 16 个身份栏配对。

    返回 (`None`, 身份组列表) 或 (排除原因, [])。原因顺序：protocol_null → score_null →
    identity_mismatch:…（点名从不相等的栏）。
    """
    pr = [(x, y) for x, y in itertools.product(ra, rb)
          if x["protocol"] is not None and y["protocol"] is not None]
    if not pr:
        return "protocol_null", []
    sc = [(x, y) for x, y in pr if x["_score"] is not None and y["_score"] is not None]
    if not sc:
        return "score_null", []
    matched = [(x, y) for x, y in sc if all(same(x[c], y[c]) for c in IDENTITY)]
    if not matched:
        never = [c for c in IDENTITY if not any(same(x[c], y[c]) for x, y in sc)]
        return "identity_mismatch:" + (",".join(never) if never else "combination"), []
    groups: dict[tuple, list] = defaultdict(list)
    for x, y in matched:
        groups[identity_key(x)].append((x, y))
    return None, sorted(groups.items(), key=lambda kv: tuple(str(v) for v in kv[0]))


def cell_from_group(bench, quant, a, b, fam_a, fam_b, gp, truth) -> dict | None:
    """一个身份组 → 一格；组内某个文件有多条不同分数时返回 None（歧义）。"""
    sa = {x["_score"] for x, _ in gp}
    sb = {y["_score"] for _, y in gp}
    if len(sa) > 1 or len(sb) > 1:
        return None
    x0, _y0 = gp[0]
    na, nb = truth[a]["n_params"], truth[b]["n_params"]
    gap = abs(truth[a]["bpw_tensors"] - truth[b]["bpw_tensors"])
    return {
        "bench": bench,
        "quant": quant,
        "family_a": fam_a,
        "family_b": fam_b,
        "model_a": a,
        "model_b": b,
        "score_a": sorted(sa)[0],
        "score_b": sorted(sb)[0],
        "n_items": x0["n_items"],
        "n_params_a": na,
        "n_params_b": nb,
        "bpw_tensors_a": truth[a]["bpw_tensors"],
        "bpw_tensors_b": truth[b]["bpw_tensors"],
        "bpw_gap": round(gap, 6),
        "bpw_matched": gap <= BPW_MATCH_TOL,
        "quant_label_missing": quant is None,
        "same_n_params": na == nb,
        "size_delta": round(abs(na - nb) / max(na, nb), 6),
        "protocol": x0["protocol"],
        "ctx_sig": {c: x0[c] for c in CTX_COLS},
        "run_tags_a": sorted({x["run_tag"] for x, _ in gp if x["run_tag"] is not None}),
        "run_tags_b": sorted({y["run_tag"] for _, y in gp if y["run_tag"] is not None}),
        "rows_a": len({x["rowid"] for x, _ in gp}),
        "rows_b": len({y["rowid"] for _, y in gp}),
    }


def model_stem(model: str) -> str:
    return model[:-len(".gguf")] if model.endswith(".gguf") else model


def canonical_families(files: list[str], truth: dict, mktables) -> tuple[dict, dict, int]:
    """`family_of` → 规范家族（后缀合并到不动点）。

    返回 (canonical: model→family, merges: canonical→原始标签集合, rounds)。合并条件只有两条：
    两个文件的实测参数量相等，且 B 的主干以 `canonical(A) + "-"` 开头。没有标签白名单：任何
    「家族名 + 尾巴」且张量形状相同的文件都会被并进去。反复做到不动点，所以链式尾巴
    （`X-y-z` 先并成 `X-y` 再并成 `X`）也能收敛。
    """
    raw = {m: mktables.family_of(m) for m in files}
    canon = dict(raw)
    rounds = 0
    while True:
        rounds += 1
        changed = False
        for b in files:
            if b not in truth:
                continue
            stem_b = model_stem(b)
            for a in files:
                if a == b or a not in truth:
                    continue
                if truth[a]["n_params"] != truth[b]["n_params"]:
                    continue
                if not stem_b.startswith(canon[a] + "-"):
                    continue
                if canon[b] != canon[a]:
                    canon[b] = canon[a]
                    changed = True
        if not changed:
            break
        if rounds > 50:                      # 不动点应当几步内到达；到了上限说明规则自相矛盾
            raise RuntimeError("canonical family iteration did not converge in 50 rounds")
    merges: dict[str, set] = defaultdict(set)
    for m in files:
        merges[canon[m]].add(raw[m])
    return canon, {k: sorted(v) for k, v in merges.items()}, rounds


def arm_of(model: str, mktables) -> str:
    """一条量化阶梯的 id：同一 id 的两个文件只差比特预算（同一配方、同一位宽阶梯）。

    `mktables.split_quant` 把文件名拆成 (去掉量化 token 的主干, 量化 token)；`is_recipe` 认出
    `mNN-…` 这种**面板/配方标签**（它变的不是位宽，而是配方本身）。所以：

    * 普通文件（`…-UD-Q2_K_XL`、`…-Q3_K_M`）→ 主干，量化 token 被剥掉：同一台阶链上的文件同 id；
    * 配方标签文件（`…-m55-exq4`）或无量化 token 的文件（`…-a04-uni45`、`…-GSQ-RCO-IQ3_S-mtp`）
      → 整个主干保留：它是**臂**，不与同一家族的位宽阶梯混成「相邻两档」。

    交互分析因此只在「两侧的 arm id 都不变、只有位宽变」的格之间算相邻档——合并家族名（canonical）
    之后仍然不会把「换臂」当成「提位宽」。
    """
    stem, quant = mktables.split_quant(model)
    if quant is not None and mktables.is_recipe(model):
        return model_stem(model)
    return stem


def canonical_closure_violations(files: list[str], canon: dict, truth: dict) -> list[tuple]:
    """闭合性自检：按照合并规则，**不应该**还剩「同参数量 + B 以 canon(A) + '-' 开头却未合并」的对。"""
    out = []
    for b in files:
        if b not in truth:
            continue
        stem_b = model_stem(b)
        for a in files:
            if a == b or a not in truth:
                continue
            if truth[a]["n_params"] != truth[b]["n_params"]:
                continue
            if stem_b.startswith(canon[a] + "-") and canon[b] != canon[a]:
                out.append((a, b))
    return sorted(out)


def build(rows: list[dict], truth: dict, mktables) -> dict:
    # 1) 每个 (bench, model, __quant) 的 run 列表。候选本身就在一个 (bench, __quant) 上，所以只拿
    #    同 `__quant` 的行来配对：`__quant` 那一栏因此恒等，与「16 栏全等」的判据一致。
    by_bench_model: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by_bench_model[(r["_bench"], r["model"], r["__quant"])].append(r)
    files = sorted({r["model"] for r in rows})
    canon, merges, merge_rounds = canonical_families(files, truth, mktables)
    raw_family = {m: mktables.family_of(m) for m in files}
    arms = {m: arm_of(m, mktables) for m in files}
    closure_bad = canonical_closure_violations(files, canon, truth)
    family_of = canon

    # 2) 按 (bench, quant) 枚举模型文件对，按「家族是否相同」分成两条池子。
    by_bench_quant: dict[tuple, set] = defaultdict(set)
    for r in rows:
        by_bench_quant[(r["_bench"], r["__quant"])].add(r["model"])
    bench_models: dict[str, set] = defaultdict(set)
    for bench, model, _q in by_bench_model:
        bench_models[bench].add(model)

    cross_family_all = 0
    cross_family_quant_same = 0
    candidates: list[tuple] = []
    same_family_pool: list[tuple] = []
    for (bench, quant), models in sorted(by_bench_quant.items(),
                                         key=lambda kv: (kv[0][0], str(kv[0][1]))):
        for a, b in itertools.combinations(sorted(models), 2):
            if family_of[a] == family_of[b]:
                same_family_pool.append((bench, quant, a, b))
                continue
            cross_family_quant_same += 1
            candidates.append((bench, quant, a, b))
    for bench, models in bench_models.items():
        for a, b in itertools.combinations(sorted(models), 2):
            if family_of[a] != family_of[b]:
                cross_family_all += 1

    cells: list[dict] = []
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
        reason, groups = match_groups(ra, rb)
        if reason is not None:
            excluded.append(dict(base, reason=reason))
            continue
        # 3. no_truth
        missing = [m for m in (a, b) if m not in truth]
        if missing:
            excluded.append(dict(base, reason="no_truth",
                                 detail="absent from gguf_truth.json: " + ", ".join(missing)))
            continue
        # 4. size
        delta = size_delta(truth, a, b)
        if delta > SIZE_TOL:
            excluded.append(dict(base, reason="size_gt_10pct",
                                 detail=f"size_delta={delta:.4f} > {SIZE_TOL}"))
            continue

        # 5. 一条受控格 = 一个身份键（含 __quant）上的一对分数
        got = 0
        ambig: list[dict] = []
        for key, gp in groups:
            c = cell_from_group(bench, quant, a, b, family_of[a], family_of[b], gp, truth)
            if c is None:
                sa = sorted({x["_score"] for x, _ in gp})
                sb = sorted({y["_score"] for _, y in gp})
                ambig.append(dict(base, reason="score_ambiguous",
                                  detail=f"model_a scores={sa} model_b scores={sb}"))
                continue
            cells.append(c)
            got += 1
        # 账要平：每个候选恰好落一处——要么产出了受控格（歧义只进 `partial_ambiguity`），要么以
        # **第一条**成立的原因进 `excluded`。
        if got:
            candidates_with_cells += 1
            partial.extend(ambig)
        elif ambig:
            excluded.append(ambig[0])

    # 3) 配方对照：同一家族、**同一份权重**（实测参数量相同）、两侧位宽差 ≤ 半档的格。
    #    这些是「同权重、同比特预算、换文件/换配方/换标签」的 sanity 读数，数值照给，不进家族计数。
    recipe: list[dict] = []
    for bench, quant, a, b in same_family_pool:
        if a not in truth or b not in truth:
            continue
        if truth[a]["n_params"] != truth[b]["n_params"]:
            continue          # 同族不同尺寸 = 尺寸轴（a02），不是配方对照
        if bpw_gap(truth, a, b) > BPW_MATCH_TOL:
            continue          # 同权重但比特预算不同 = 量化轴（a01），不是配方对照
        reason, groups = match_groups(by_bench_model[(bench, a, quant)],
                                      by_bench_model[(bench, b, quant)])
        if reason is not None:
            continue
        for _key, gp in groups:
            c = cell_from_group(bench, quant, a, b, family_of[a], family_of[b], gp, truth)
            if c is not None:
                recipe.append(c)

    # 确定性编号：先按 (bench, model_a, model_b, 身份键) 排序再发号，重跑同一输入得同一份清单。
    def sort_key(p):
        return (p["bench"], p["model_a"], p["model_b"],
                tuple(str(p["ctx_sig"][c]) for c in CTX_COLS))

    cells.sort(key=sort_key)
    recipe.sort(key=sort_key)

    # 落盘时压缩：家族名在上层 `families` 表里查，`protocol` 本就在 `ctx_sig` 里，`ctx` 按
    # `ctx_columns` 的列序存成数组。同一格的内容不变，只去掉重复的字符串。
    def slim(p: dict, prefix: str, i: int) -> dict:
        return {
            "id": f"{prefix}{i:04d}",
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
            "bpw_gap": p["bpw_gap"],
            "bpw_matched": p["bpw_matched"],
            "quant_label_missing": p["quant_label_missing"],
            "same_n_params": p["same_n_params"],
            "size_delta": p["size_delta"],
            "ctx": [p["ctx_sig"][c] for c in CTX_COLS],
            "tags_a": p["run_tags_a"],
            "tags_b": p["run_tags_b"],
            "rows_a": p["rows_a"],
            "rows_b": p["rows_b"],
        }

    cells = [slim(p, "fam", i) for i, p in enumerate(cells, 1)]
    recipe = [slim(p, "rec", i) for i, p in enumerate(recipe, 1)]

    reasons = Counter(e["reason"] for e in excluded)
    size_rejected: Counter = Counter()
    for e in excluded:
        if e["reason"] == "size_gt_10pct":
            size_rejected[" | ".join(sorted((e["family_a"], e["family_b"])))] += 1

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
    bpw_matched = [c for c in cells if c["bpw_matched"]]
    # 家族对只在**家族层**上数（两侧实测参数量不同）：同参数量的对子是「同一脚手架换权重/配方」，
    # 不是家族对比。`effects.py` 用同一个定义，所以两边的 `family_pairs_with_cells` 必须相等。
    fam_tier = [c for c in cells if not c["same_n_params"]]
    family_pairs_all = sorted({f"{family_of[c['model_a']]} | {family_of[c['model_b']]}" for c in fam_tier})
    family_pairs_readable = sorted({f"{family_of[c['model_a']]} | {family_of[c['model_b']]}"
                                    for c in bpw_matched if not c["same_n_params"]})
    return {
        "what": ("跨家族受控对清单：同基准、同量化档（标签）、16 个身份栏全等、实测参数量差 ≤10%；"
                 "家族 = mktables.family_of；两层口径 label_matched / bpw_matched"),
        "generated_by": "docs/subprojects/a15-模型家族/analysis/pairs.py",
        "family_definition": ("canonical = mktables.family_of(model)，再做后缀合并到不动点：若两文件实测 "
                              "n_params 相等且 B 的主干以 canonical(A) + '-' 开头，则 canonical(B) := "
                              "canonical(A)"),
        "truth_fixture": "docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json",
        "size_tolerance": SIZE_TOL,
        "level_width_bpw": LEVEL_W,
        "bpw_match_tol": BPW_MATCH_TOL,
        "identity_columns": IDENTITY,
        "encoding": ("`cells` 与 `recipe_controls` 是对象数组（一格一对象）；`excluded` 按列存，列序见 "
                     "`columns.excluded`，字符串值是 `strings` 里的下标（null 仍是 null）。"
                     "`cells[].ctx` 是除 __quant 外的 15 个身份栏，列序见 `ctx_columns`；"
                     "家族名不存进格子里，在 `families`（模型文件 → 家族）里查。"),
        "columns": {"excluded": ["bench", "quant", "family_a", "family_b", "model_a",
                                 "model_b", "reason", "size_delta"]},
        "strings": [s for s, _ in sorted(pool.items(), key=lambda kv: kv[1])],
        "counts": {
            "candidates": len(candidates),
            "candidates_with_controlled_cells": candidates_with_cells,
            "label_matched_cells": len(cells),
            "bpw_matched_cells": len(bpw_matched),
            "quant_label_missing_cells": sum(1 for c in cells if c["quant_label_missing"]),
            "quant_label_missing_bpw_matched": sum(1 for c in bpw_matched if c["quant_label_missing"]),
            "same_n_params_cells": sum(1 for c in cells if c["same_n_params"]),
            "same_n_params_bpw_matched": sum(1 for c in bpw_matched if c["same_n_params"]),
            "recipe_control_cells": len(recipe),
            "excluded": len(excluded),
            "partial_ambiguity_rows": len(partial),
            "bench_pairs_cross_family_all": cross_family_all,
            "bench_pairs_dropped_by_quant": cross_family_all - cross_family_quant_same,
            "same_family_pairs_pool": len(same_family_pool),
            "db_rows_read": len(rows),
            "files": len(files),
            "families": len(set(family_of.values())),
            "raw_family_labels": len(set(raw_family.values())),
            "merged_raw_labels": sum(1 for v in merges.values() if len(v) > 1),
            "labels_absorbed": sum(len(v) - 1 for v in merges.values()),
            "merge_rounds": merge_rounds,
            "closure_violations": len(closure_bad),
            "excluded_by_reason": dict(sorted(reasons.items())),
            "family_pairs_with_cells": len(family_pairs_all),
            "family_pairs_with_cells_all_tiers": len({f"{family_of[c['model_a']]} | "
                                                      f"{family_of[c['model_b']]}" for c in cells}),
            "family_pairs_bpw_matched": len(family_pairs_readable),
            "benches_with_cells": sorted({c["bench"] for c in cells}),
            "family_pairs_rejected_by_size": dict(sorted(size_rejected.items(),
                                                         key=lambda kv: (-kv[1], kv[0]))),
        },
        "families": {m: f for m, f in sorted(family_of.items())},
        "raw_families": {m: f for m, f in sorted(raw_family.items())},
        "arms": {m: a for m, a in sorted(arms.items())},
        "family_merges": {k: v for k, v in sorted(merges.items()) if len(v) > 1},
        "closure_violations": [list(x) for x in closure_bad],
        "ctx_columns": CTX_COLS,
        "cells": cells,
        "recipe_controls": recipe,
        "excluded": excluded_rows,
        "partial_ambiguity": [[ref(e["bench"]), ref(e["quant"]), ref(e["family_a"]),
                               ref(e["family_b"]), ref(e["model_a"]), ref(e["model_b"]),
                               ref(e["reason"]), None] for e in partial],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    ap.add_argument("--mktables", type=Path, default=DEFAULT_MKTABLES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--print", dest="show", action="store_true", help="只打印摘要，不写 JSON")
    args = ap.parse_args(argv)

    if not args.db.is_file():
        print(f"BLOCKED: dataset not found: {args.db}", file=sys.stderr)
        return 2
    if not args.truth.is_file():
        print(f"BLOCKED: truth fixture not found: {args.truth}", file=sys.stderr)
        return 2
    if not args.mktables.is_file():
        print(f"BLOCKED: mktables not found: {args.mktables} (family_of is undefined without it)",
              file=sys.stderr)
        return 2

    ledger = build(load_rows(args.db), load_truth(args.truth), load_mktables(args.mktables))
    c = ledger["counts"]
    if not c["candidates"]:
        print("BLOCKED: zero candidates — refusing to report an empty inventory", file=sys.stderr)
        return 2

    print("cross-family controlled-pair inventory (family = canonical family_of)")
    print(f"  db rows read / files / families : {c['db_rows_read']} / {c['files']} / {c['families']} "
          f"(canonical; {c['raw_family_labels']} raw family_of labels, "
          f"{c['labels_absorbed']} absorbed in {c['merge_rounds']} round(s))")
    for canon_name, labels in ledger["family_merges"].items():
        print(f"      merged: {canon_name:<40} ← {', '.join(labels)}")
    # 完整规范家族列表：每个家族吃掉几个原始标签、有几个文件、几格（label / bpw）。
    fam_files: Counter = Counter(ledger["families"].values())
    fam_cells: Counter = Counter();
    fam_cells_bpw: Counter = Counter()
    for x in ledger["cells"]:
        k = ledger["families"][x["model_a"]] + " | " + ledger["families"][x["model_b"]]
        fam_cells[ledger["families"][x["model_a"]]] += 1
        fam_cells[ledger["families"][x["model_b"]]] += 1
        if x["bpw_matched"]:
            fam_cells_bpw[ledger["families"][x["model_a"]]] += 1
            fam_cells_bpw[ledger["families"][x["model_b"]]] += 1
    print(f"  canonical families ({len(fam_files)}): raw labels / files / cells(label) / cells(bpw)")
    for name in sorted(fam_files):
        nraw = len(ledger["family_merges"].get(name, [name]))
        print(f"      {name:<44} {nraw:>2} / {fam_files[name]:>2} / "
              f"{fam_cells[name]:>4} / {fam_cells_bpw[name]:>3}")
    print(f"  candidates (bench+quant+filepair): {c['candidates']}")
    print(f"  label_matched cells             : {c['label_matched_cells']}")
    print(f"  bpw_matched cells (<= {BPW_MATCH_TOL} bpw): {c['bpw_matched_cells']}")
    print(f"  quant label missing             : {c['quant_label_missing_cells']} label_matched, "
          f"{c['quant_label_missing_bpw_matched']} of them bpw_matched")
    print(f"  same true n_params (same scaffold): {c['same_n_params_cells']} cells, "
          f"{c['same_n_params_bpw_matched']} of them bpw_matched")
    print(f"  excluded candidates             : {c['excluded']}")
    print(f"  partial ambiguity rows          : {c['partial_ambiguity_rows']}")
    print(f"  same-family pool (not candidates): {c['same_family_pairs_pool']} file pairs")
    print(f"  recipe controls (same weights, bpw-matched): {c['recipe_control_cells']} cells")
    print(f"  cross-family bench pairs, all   : {c['bench_pairs_cross_family_all']}")
    print(f"  dropped for quant mismatch      : {c['bench_pairs_dropped_by_quant']}")
    print("  excluded by reason              : "
          + ", ".join(f"{k}={v}" for k, v in c["excluded_by_reason"].items()))
    print(f"  family pairs with cells         : {c['family_pairs_with_cells']} "
          f"(bpw_matched: {c['family_pairs_bpw_matched']})")
    read: dict[str, int] = defaultdict(int)
    for p in ledger["cells"]:
        if p["bpw_matched"]:
            read[f"{ledger['families'][p['model_a']]} | {ledger['families'][p['model_b']]}"] += 1
    for fp, n in sorted(read.items()):
        print(f"      {fp:<55} {n} readable cell(s)")
    print("  benches with cells              : " + ", ".join(c["benches_with_cells"]))
    sr = c["family_pairs_rejected_by_size"]
    print(f"  10% size criterion rejects      : {sum(sr.values())} candidate(s) over "
          f"{len(sr)} family pair(s); largest:")
    for fp, n in list(sr.items())[:6]:
        print(f"      {fp:<55} {n} candidate(s)")
    # 关系式自检（不是快照常量）：每个候选恰好一次；每一格的两层口径与位宽闸门一致。
    balanced = c["candidates"] == c["excluded"] + c["candidates_with_controlled_cells"]
    gate_ok = all(x["bpw_matched"] == (x["bpw_gap"] <= BPW_MATCH_TOL) for x in ledger["cells"])
    recipe_ok = all(x["bpw_matched"] and x["same_n_params"] for x in ledger["recipe_controls"])
    closure_ok = not ledger["closure_violations"]
    print(f"SELFCHECK candidates == excluded + candidates_with_cells: "
          f"{c['candidates']} == {c['excluded']} + {c['candidates_with_controlled_cells']} "
          f"{'ok' if balanced else 'MISMATCH'}")
    print(f"SELFCHECK bpw_matched == (bpw_gap <= {BPW_MATCH_TOL}) on every cell: "
          f"{'ok' if gate_ok else 'MISMATCH'}")
    print(f"SELFCHECK every recipe control is same-weights AND bpw_matched: "
          f"{'ok' if recipe_ok else 'MISMATCH'}")
    print(f"SELFCHECK canonical families are closed (no same-n_params arm left unmerged): "
          f"{'ok' if closure_ok else 'MISMATCH'} "
          f"{ledger['closure_violations'][:3] if not closure_ok else ''}")
    if not (balanced and gate_ok and recipe_ok and closure_ok):
        return 1

    if args.show:
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    shown = args.out.relative_to(REPO) if REPO in args.out.parents else args.out
    print(f"  ledger written                  : {shown}")
    print(f"COUNT candidates={c['candidates']} label_matched={c['label_matched_cells']} "
          f"bpw_matched={c['bpw_matched_cells']} recipe_controls={c['recipe_control_cells']} "
          f"excluded={c['excluded']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
