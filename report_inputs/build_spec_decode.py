#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `a07` 的投机解码证据抽成派生索引，供报告第七、八节生成文字。

数据全部来自 a07 随仓库分发的 `fixtures/*.tsv`（干净 clone 里也在），不读它的散文：

  * `ident_pairs.tsv`   —— 逐字节对的逐题对照：`kind=floor` 是同配置跨会话（地板），`kind=spec` 是开投机；
  * `ident_arms.tsv`    —— 每一臂的整批 sha256 与题量；
  * `ident_control.tsv` —— 每一臂的分数、题量、`n_slots`、server 占用 MiB；
  * `ident_peritem.tsv` —— 逐题判定（分数 = 通过题数 / 题量，这里直接数，不用分数反推）；
  * `speed_depth.tsv`   —— 五个模型的 tok/s 随草稿深度（含相对深度 0 的百分比）；
  * `device.tsv`        —— 同一 gguf 名在 MTP 仓库与普通仓库里的**文件字节**（头权重开销）；
  * `quality_depth.tsv` —— 九个模型×基准×深度的分数。

    python3 report_inputs/build_spec_decode.py           # 重写 spec_decode.json
    python3 report_inputs/build_spec_decode.py --check   # 与现有 json 比对

三种结局：0 = 一致；1 = 索引落后于 a07 的 fixtures；2 = fixtures 不在场（索引无法当场核对）。
"""
from __future__ import annotations

import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "spec_decode.json")
FIX = os.path.join(REPO, "docs", "subprojects", "a07-投机解码", "fixtures")

RUNS = os.path.join(REPO, "docs", "subprojects", "a07-投机解码", "evidence", "spec-runs.jsonl")

FILES = {name: os.path.join(FIX, name + ".tsv") for name in
         ("ident_pairs", "ident_arms", "ident_control", "ident_peritem",
          "speed_depth", "device", "quality_depth")}


def rows(name):
    with open(FILES[name], encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def build():
    pairs = rows("ident_pairs")
    control = rows("ident_control")
    peritem = rows("ident_peritem")
    speed = rows("speed_depth")
    device = rows("device")
    quality = rows("quality_depth")

    # ---- 字节地板：同配置、不同会话两两逐字节对照 -------------------------
    floor = [p for p in pairs if p["kind"] == "floor"]
    floor_all_same = all(int(p["identical"]) == int(p["n"]) and int(p["differing"]) == 0
                         for p in floor)

    # ---- 投机效应：同一会话内只改草稿深度 ---------------------------------
    def pair(tag_a, arm_a, tag_b, arm_b):
        """按 (tag, arm) 找对照行，**不看顺序**：fixtures 里同一对两个方向的都有。"""
        want = {(tag_a, arm_a), (tag_b, arm_b)}
        for p in pairs:
            if {(p["tag_a"], p["arm_a"]), (p["tag_b"], p["arm_b"])} == want:
                return p
        return None

    eff = pair("m169-ident-08b-mtp", "none", "m169-ident-08b-mtp", "draft-mtp2")
    if eff is None:
        raise SystemExit("ident_pairs.tsv 里找不到同一会话的 none vs draft-mtp2 对")

    # 通过题数直接数逐题判定，不用分数反推
    passes = collections.defaultdict(int)
    items = collections.defaultdict(int)
    for r in peritem:
        key = (r["tag"], r["arm"])
        items[key] += 1
        passes[key] += int(r["pass"])

    # ---- 投机臂自己能不能跨会话复现（否则「差异」不可归因） ----------------
    spec_repro = pair("m125-spec-0.8b", "n2", "m169-ident-08b-mtp", "draft-mtp2")

    # ---- 速度：0.8B 的 n0 → n2，以及「深度越大越快」在哪些模型上不成立 ----
    by_tag = collections.defaultdict(dict)
    for r in speed:
        by_tag[r["tag"]][int(r["depth"])] = (float(r["tok_s"]), float(r["rel_pct"]))
    t08 = by_tag["m125-spec-0.8b"]
    nonmono = []
    for tag, d in sorted(by_tag.items()):
        depths = sorted(d)
        best = max(depths, key=lambda x: d[x][0])
        if best != depths[-1]:
            nonmono.append({"tag": tag, "gguf": next(r["gguf"] for r in speed if r["tag"] == tag),
                            "best_depth": best, "max_depth": depths[-1],
                            "best_tok_s": round(d[best][0], 2),
                            "last_tok_s": round(d[depths[-1]][0], 2)})

    # ---- 两种显存口径：头**权重字节** vs 运行期占用 -----------------------
    dev08 = {r["depth"]: r for r in device if r["tag"] == "m125-spec-0.8b"}
    head_bytes = int(dev08["0"]["mtp_bytes"]) - int(dev08["0"]["plain_bytes"])
    srv = collections.defaultdict(dict)
    for r in control:
        if r["server_mib"]:
            srv[r["tag"]][r["arm"]] = int(r["server_mib"])
    runtime = {}
    for tag in ("m169-vram-08b-mtp", "m169-vram-9b"):
        d = srv.get(tag) or {}
        if "none" in d and "draft-mtp2" in d:
            runtime[tag] = {"none_mib": d["none"], "spec_mib": d["draft-mtp2"],
                            "delta_mib": d["draft-mtp2"] - d["none"]}

    # ---- 质量：会生成的三列在深度上移动多少 -------------------------------
    q = collections.defaultdict(dict)
    for r in quality:
        q[(r["tag"], r["bench"])][int(r["depth"])] = float(r["score"])
    moved, still = [], []
    for (tag, bench), d in sorted(q.items()):
        base = d.get(0)
        if base is None:
            continue
        worst = max(d.items(), key=lambda kv: abs(kv[1] - base))
        rec = {"tag": tag, "bench": bench, "depth": worst[0],
               "score": round(worst[1], 6), "base": round(base, 6),
               "delta": round(worst[1] - base, 6)}
        (still if abs(rec["delta"]) < 1e-12 else moved).append(rec)

    # 墙钟（只为说明「它不能当速度对照」）：同一对臂各自那次跑的 gpu_minutes
    wall = {}
    if os.path.exists(RUNS):
        for line in open(RUNS, encoding="utf-8"):
            r = json.loads(line)
            if r.get("tag") == "m169-ident-08b-mtp" and r.get("gpu_minutes"):
                wall.setdefault(r["arm"], r["gpu_minutes"])

    return {
        "source_dir": os.path.relpath(FIX, REPO),
        "sources": {k: os.path.relpath(v, REPO) for k, v in FILES.items()},
        "byte_floor": {
            "n_pairs": len(floor), "n_items": int(floor[0]["n"]) if floor else None,
            "all_identical": floor_all_same,
            "differing_total": sum(int(p["differing"]) for p in floor),
            "sessions": sorted({p["tag_a"] for p in floor} | {p["tag_b"] for p in floor}),
        },
        "spec_effect": {
            "n_items": int(eff["n"]), "identical": int(eff["identical"]),
            "differing": int(eff["differing"]),
            "pass_none": passes[("m169-ident-08b-mtp", "none")],
            "pass_spec": passes[("m169-ident-08b-mtp", "draft-mtp2")],
            "items_none": items[("m169-ident-08b-mtp", "none")],
            "items_spec": items[("m169-ident-08b-mtp", "draft-mtp2")],
            "pair": {"a": [eff["tag_a"], eff["arm_a"]], "b": [eff["tag_b"], eff["arm_b"]]},
        },
        "spec_reproducible": {
            "pair": [spec_repro["tag_a"], spec_repro["arm_a"],
                     spec_repro["tag_b"], spec_repro["arm_b"]] if spec_repro else None,
            "identical": int(spec_repro["identical"]) if spec_repro else None,
            "n_items": int(spec_repro["n"]) if spec_repro else None,
        },
        "speed_08b": {"gguf": next(r["gguf"] for r in speed if r["tag"] == "m125-spec-0.8b"),
                      "depth0_tok_s": round(t08[0][0], 2), "depth2_tok_s": round(t08[2][0], 2),
                      "depth2_pct": round(t08[2][1], 1),
                      "depth4_tok_s": round(t08[4][0], 2), "depth4_pct": round(t08[4][1], 1)},
        "speed_nonmonotone": nonmono,
        "memory": {"head_bytes_08b": head_bytes,
                   "head_pct_08b": round(head_bytes / int(dev08["0"]["plain_bytes"]) * 100, 2),
                   "runtime": runtime},
        "quality": {"moved": moved, "unchanged": still},
        "wall_clock_minutes": wall,
    }


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    missing = [os.path.relpath(p, REPO) for p in FILES.values() if not os.path.exists(p)]
    if missing:
        print(f"UNVERIFIED: a07 的 fixtures 不在场（{', '.join(missing)}）；"
              f"{os.path.relpath(OUT, REPO)} 无法当场核对", file=sys.stderr)
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
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is stale against a07's fixtures; "
                  f"rerun without --check", file=sys.stderr)
            return 1
        e = doc["spec_effect"]
        print(f"spec_decode.json: up to date (floor 0 over {doc['byte_floor']['n_pairs']} pairs; "
              f"spec {e['identical']}/{e['n_items']} identical, {e['differing']} differ)")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    e = doc["spec_effect"]
    print(f"wrote {os.path.relpath(OUT, REPO)}: byte floor "
          f"{'0' if doc['byte_floor']['all_identical'] else 'NOT 0'} over "
          f"{doc['byte_floor']['n_pairs']} pairs; spec {e['identical']}/"
          f"{e['n_items']} identical, {e['differing']} differ, "
          f"pass {e['pass_none']}→{e['pass_spec']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
