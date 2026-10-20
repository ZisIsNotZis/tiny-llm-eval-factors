#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「这一对文件能不能被摆到同一总比特下」逐对冻结成入库夹具（`a03` 的夹具形状）。

用法（仓库根执行）：

    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/build_pin_fixture.py" --write
    python3 "docs/subprojects/a04-MoE 各层比特分配/analysis/build_pin_fixture.py" --check

为什么要有这份夹具：本层那条结构性结论——**90%–93% 的参数是专家，所以钉住总比特时专家桶
最多挪 `(1−s_exp)/s_exp × 层间摆动`，而实测同基权重的专家跨度远超它**——是逐对判定的，不是
一族一句。判据与每个数字都要能被别人复核，所以逐对写进行内文件；它的两个输入（a03 的
`alloc_map.json` 与本层的 `alloc_a04.json`）**都在仓库里**，因此在干净 clone 里 `--check`
同样成立，不需要 gguf、不需要数据库、不占 GPU。

不要手改这个 json：改判据要改 `alloc_pairs.py` 的 `expert_span_bound`，再 `--write` 重建。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import alloc_pairs as ap  # noqa: E402  —— 判据只有一份，夹具只是它的冻结副本

FIXTURE = HERE / "fixtures" / "pin_feasibility.json"


def build():
    doc = {
        "generated_by": "docs/subprojects/a04-MoE 各层比特分配/analysis/build_pin_fixture.py",
        "criterion": "span_exp <= bound  <=>  这一对的专家桶跨度落在其余桶反向摆动能在总比特上抵平的范围内（可等总比特）；否则必然同时改了总比特",
        "bound_formula": "(1 - share_expert) / share_expert * layer_swing",
        "families": {},
        "pairs": [],
    }
    for fam, files in sorted(ap.moe_groups().items()):
        if len(files) < 2:
            doc["families"][fam] = {"files": sorted(files), "note": "只有一个文件，没有同族配对"}
            continue
        ref = ap.ALLOC[files[0]]
        s_exp = ref["classes"][ap.EXPERT_BUCKET]["params"] / ref["n_params"]
        layers = [ap.b_layer(n) for n in files]
        swing = max(layers) - min(layers)
        bound = ap.expert_span_bound(files)
        doc["families"][fam] = {
            "files": sorted(files),
            "n_params": ref["n_params"],
            "share_expert": round(s_exp, 6),
            "share_layer_buckets": round(
                sum(ref["classes"][c]["params"] for c in ap.LAYER_BUCKETS if c in ref["classes"])
                / ref["n_params"], 6),
            "layer_swing": round(swing, 6),
            "expert_span_bound": round(bound, 6),
        }
        ordered = sorted(files, key=lambda n: ap.ALLOC[n]["bpw_file"])
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                span = abs(ap.b_expert(a) - ap.b_expert(b))
                doc["pairs"].append({
                    "family": fam,
                    "a": a,
                    "b": b,
                    "bpw_a": round(ap.ALLOC[a]["bpw_file"], 6),
                    "bpw_b": round(ap.ALLOC[b]["bpw_file"], 6),
                    "dbpw": round(ap.ALLOC[b]["bpw_file"] - ap.ALLOC[a]["bpw_file"], 6),
                    "l1_pw": round(ap.l1_pw(a, b), 6),
                    "strategy_a": ap.strategy(a),
                    "strategy_b": ap.strategy(b),
                    "b_expert_a": round(ap.b_expert(a), 6),
                    "b_expert_b": round(ap.b_expert(b), 6),
                    "expert_span": round(span, 6),
                    "expert_span_bound": round(bound, 6),
                    "verdict": "可等总比特" if span <= bound else "不可等总比特",
                })
    doc["summary"] = {
        "n_pairs": len(doc["pairs"]),
        "n_comparable": sum(p["verdict"] == "可等总比特" for p in doc["pairs"]),
        "n_not_comparable": sum(p["verdict"] == "不可等总比特" for p in doc["pairs"]),
        "n_families_with_pairs": sum(1 for f in doc["families"].values() if "expert_span_bound" in f),
    }
    return doc


def main(argv=None):
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--write", action="store_true")
    ap_.add_argument("--check", action="store_true")
    args = ap_.parse_args(argv)
    live = build()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(live, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        s = live["summary"]
        print("wrote %s：%d 对（可等总比特 %d / 不可等 %d），%d 个有配对的 MoE 族"
              % (FIXTURE, s["n_pairs"], s["n_comparable"], s["n_not_comparable"],
                 s["n_families_with_pairs"]))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("夹具不存在：%s" % FIXTURE)
            return 1
        frozen = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if frozen != live:
            fs, ls = frozen.get("summary", {}), live["summary"]
            print("[DRIFT] 夹具与重算不一致：frozen %s vs live %s" % (fs, ls))
            fmap = {(p["a"], p["b"]): p for p in frozen.get("pairs", [])}
            lmap = {(p["a"], p["b"]): p for p in live["pairs"]}
            for k in sorted(set(fmap) | set(lmap)):
                if fmap.get(k) != lmap.get(k):
                    print("  [pair] %s vs %s" % k)
                    for field in ("expert_span", "expert_span_bound", "verdict", "l1_pw", "dbpw"):
                        if (fmap.get(k) or {}).get(field) != (lmap.get(k) or {}).get(field):
                            print("    %-18s frozen=%r live=%r" % (field,
                                  (fmap.get(k) or {}).get(field), (lmap.get(k) or {}).get(field)))
            for fam in sorted(set(frozen.get("families", {})) | set(live["families"])):
                if frozen.get("families", {}).get(fam) != live["families"].get(fam):
                    print("  [family] %s" % fam)
            return 1
        s = live["summary"]
        print("[ok] %d 对一致（可等总比特 %d / 不可等 %d），%d 个有配对的 MoE 族"
              % (s["n_pairs"], s["n_comparable"], s["n_not_comparable"], s["n_families_with_pairs"]))
        return 0
    ap_.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
