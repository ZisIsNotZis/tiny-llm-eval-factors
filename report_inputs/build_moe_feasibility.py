#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `a04` 的「钉住总比特可行性」fixture 抽成派生索引，供报告第四节生成文字。

读 `a04` 的 `analysis/fixtures/pin_feasibility.json`（脚本产物）：上界公式、每个 MoE 族的
「专家桶最多能挪多少」与实测跨度、以及 22 对里可钉住 / 不可钉住的计数。报告据此写清「总比特
钉住」这个前提、可行性上界 vs 实测跨度的对照、以及 `exq2` vs `exq4` 是预算比较而非分配比较。

    python3 report_inputs/build_moe_feasibility.py           # 重写 moe_feasibility.json
    python3 report_inputs/build_moe_feasibility.py --check   # 与现有 json 比对
"""
from __future__ import annotations

import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "moe_feasibility.json")
SRC = os.path.join(REPO, "docs", "subprojects", "a04-MoE 各层比特分配",
                   "analysis", "fixtures", "pin_feasibility.json")


THIRD_ARM_FACT = "third-arm-pinned"
DELTA_RE = re.compile(r"(HumanEval\+|HumanEval|MBPP\+|MBPP|MMLU|GSM8K|ARC-c|IFEval|TruthfulQA)\s*"
                      r"([+\u2212-]?\d+\.\d+)(?:\s*\[([+\u2212-]?\d+\.\d+)\s*,\s*"
                      r"([+\u2212-]?\d+\.\d+)\])?")
BUDGET_RE = re.compile(r"比特预算对这些差的贡献只有\s*([+\u2212-]?\d+\.\d+).{0,3}?"
                       r"([+\u2212-]?\d+\.\d+)")
BUDGET_HEP_RE = re.compile(r"`?Δbpw`? ?只值 HumanEval\+ ([\d.]+)")


def read_fact(path, fact_id):
    """该标题行（`### id :: 正文` 的正文部分）+ 其下直到下一个标题的内容。"""
    out, cur = "", None
    for line in open(path, encoding="utf-8"):
        if line.startswith("#"):
            cur = line.split("::")[0].strip("# ").strip()
            if cur == fact_id and "::" in line:
                out += line.split("::", 1)[1] + "\n"
            continue
        if cur == fact_id:
            out += line
    return out


def third_arm(fixtures):
    """a04 的第三臂（均匀 vs 专家优先的钉住对照）：逐基准差与预算项。"""
    facts = os.path.join(REPO, "docs", "subprojects", "a04-MoE 各层比特分配", "RESULT.md")
    text = read_fact(facts, THIRD_ARM_FACT)
    if not text:
        return None
    def num(tok):
        return float(tok.replace("−", "-").replace("+", ""))

    deltas = []
    for bench in ("HumanEval+", "HumanEval", "MBPP+", "MBPP", "MMLU", "GSM8K", "ARC-c",
                  "IFEval", "TruthfulQA"):
        pat = re.compile(re.escape(bench) + r"\s*([+\u2212-]?\d+\.\d+)\s*"
                         r"\[\s*([+\u2212-]?\d+\.\d+)\s*,\s*([+\u2212-]?\d+\.\d+)\s*\]")
        m = pat.search(text)
        if not m:
            continue
        lo, hi = num(m.group(2)), num(m.group(3))
        deltas.append({"bench": bench, "delta": num(m.group(1)), "lo": lo, "hi": hi,
                       "resolvable": not (lo <= 0 <= hi)})
    b = BUDGET_RE.search(text)
    hep = BUDGET_HEP_RE.search(text)
    pair = next((x for x in fixtures["pairs"]
                 if {x["a"], x["b"]} == {"LFM2.5-8B-A1B-a04-uni45.gguf",
                                         "LFM2.5-8B-A1B-m55-exq4.gguf"}), None)
    return {
        "fact": THIRD_ARM_FACT,
        "source": os.path.relpath(facts, REPO),
        "deltas": deltas,
        "budget_share_min": float(b.group(1).replace("−", "-")) if b else None,
        "budget_share_max": float(b.group(2).replace("−", "-")) if b else None,
        "budget_humaneval_plus": float(hep.group(1)) if hep else None,
        "dbpw": pair["dbpw"] if pair else None,
        "l1_pw": pair["l1_pw"] if pair else None,
        "boundary": "同族（LFM2.5-8B-A1B）、同 base 权重、单一模型家族，不得外推成跨家族结论",
        "untested": "Tier-1A 的桶内结构仍无对照（需另造一臂，约 47 GPU 分钟）",
    }


def build():
    if not os.path.exists(SRC):
        raise SystemExit(f"找不到 a04 的可行性 fixture：{os.path.relpath(SRC, REPO)}")
    d = json.load(open(SRC, encoding="utf-8"))
    fams = d["families"]
    rows = []
    for name, f in sorted(fams.items()):
        if "expert_span_bound" not in f:
            continue          # 该族不够 2 份文件、算不出上界（fixture 里只留 note）
        rows.append({"family": name, "expert_share": f.get("share_expert"),
                     "layer_swing": f.get("layer_swing"), "bound": f["expert_span_bound"],
                     "files": len(f.get("files", []))})
    spans = [p["expert_span"] for p in d["pairs"]]
    over = [p for p in d["pairs"] if p["expert_span"] > p["expert_span_bound"]]
    return {
        "source": os.path.relpath(SRC, REPO),
        "bound_formula": d["bound_formula"],
        "summary": d["summary"],
        "families": rows,
        "observed_span_min": round(min(spans), 4),
        "observed_span_max": round(max(spans), 4),
        "over_bound": len(over),
        "over_span_min": round(min((p["expert_span"] for p in over), default=0.0), 4),
        "over_span_max": round(max((p["expert_span"] for p in over), default=0.0), 4),
        "pinned": {"pairs": d["summary"]["n_comparable"]},
        "third_arm": third_arm(d),
    }


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    doc = build()
    text = dump(doc)
    if "--check" in argv:
        try:
            have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is missing", file=sys.stderr)
            return 1
        if have != text:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is stale against a04's fixture; rerun without --check", file=sys.stderr)
            return 1
        print(f"moe_feasibility.json: up to date ({doc['over_bound']}/{doc['summary']['n_pairs']} pairs over bound)")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}: {doc['over_bound']}/{doc['summary']['n_pairs']} pairs "
          f"over bound; observed span {doc['observed_span_min']}–{doc['observed_span_max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
