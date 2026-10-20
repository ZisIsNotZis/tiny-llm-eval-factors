#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `a05` 的 KV 证据**脚本输出**抽成派生索引，供报告第五节生成文字。

不抄散文：直接跑 `docs/subprojects/a05-KV 缓存精度/analysis/kv_evidence.py`，解析它打印的
逐题配对行（`f16_f16->q4_0_q4_0: lose 15 gain 11`）、面板分数行、以及它自己断言 `[ok]/[FAIL]`
的几项结论。

    python3 report_inputs/build_kv_evidence.py           # 重写 kv_evidence.json
    python3 report_inputs/build_kv_evidence.py --check   # 重跑脚本并比对
"""
from __future__ import annotations

import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "kv_evidence.json")
SCRIPT = os.path.join(REPO, "docs", "subprojects", "a05-KV 缓存精度", "analysis", "kv_evidence.py")

PAIR_RE = re.compile(r"^\s{4}(base|plus)_status (\S+)->(\S+): lose (\d+) gain (\d+)$")
SCORE_RE = re.compile(r"^\s{2}(\S+)\s+mmlu=([\d.]+) gsm8k=([\d.]+) ifeval=([\d.]+) humaneval\(base\)=([\d.]+) n=(\d+)$")
CHECK_RE = re.compile(r"^\[(ok  |FAIL)\] (A\d|B\d|C\d|D\d|E\d|F\d) (.+?): (.+)$")
# a05 的两口径表：| base f16 → q8_0 | −4（94→90） | 7 | 3 | 10 | 否 |
NUM_RE = re.compile(r"[−+-]?\d+")
TWO_METRICS_PATH_HINT = "kv-two-metrics"


NEEDLE_SUMMARY = os.path.join(REPO, "docs", "subprojects", "a05-KV 缓存精度",
                              "evidence", "needle-retune", "summary.json")


def long_context():
    """长上下文（检索针）那一轮的实测：每档命中数与 q4_0 相对 f16 的配对差。

    读 a05 的 `evidence/needle-retune/summary.json`（脚本产物），不抄散文。
    """
    if not os.path.exists(NEEDLE_SUMMARY):
        return {"tested": False,
                "why": "a05 还没有落 needle-retune 的 summary；长上下文仍未测"}
    d = json.load(open(NEEDLE_SUMMARY, encoding="utf-8"))
    cells = {}
    for c in d["cells"]:
        if "control" in c["cell"]:
            continue
        cells[(c["ctx"], c["kv"])] = {"hits": c["hits"], "n": c["n"]}
    ctxs = sorted({c["ctx"] for c in d["cells"]})
    rows = []
    for ctx in ctxs:
        f = cells.get((ctx, "f16/f16"))
        q = cells.get((ctx, "q4_0/q4_0"))
        if f and q:
            rows.append({"ctx": ctx, "f16_hits": f["hits"], "q4_hits": q["hits"],
                         "n": f["n"], "delta": q["hits"] - f["hits"]})
    control = d.get("control", {})
    strata = d.get("strata", {})
    verdict = strata.get("0.9", {}).get("verdict", "")
    return {
        "tested": True,
        "verdict": verdict,
        "rows": rows,
        "control": {"hits": control.get("hits"), "n": control.get("n"),
                    "passed": control.get("passed")},
        "visibility_floor": "单侧 20 条下可见性下限约 4/20",
        "q8_0_rerun": False,
        "beyond_40k": "40k 以上未测：每个上下文档要一次完整网格（约 5 GPU 分钟/档），本轮只做到 32k",
        "source": os.path.relpath(NEEDLE_SUMMARY, REPO),
    }


def parse_two_metrics(facts_text):
    """a05 的 `kv-two-metrics` 表 → 每对的 (分数差, 丢, 得, 翻转合计, 通过集是否相同)。"""
    pairs = {}
    for line in facts_text.split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or not re.match(r"^(base|plus)\s", cells[0]):
            continue
        head = cells[0].split()
        nums = [int(x.replace("−", "-")) for x in NUM_RE.findall(cells[1])]
        if len(nums) != 3:
            continue
        pairs[f"{head[0]} {head[1]}->{head[3]}"] = {
            "score_delta_items": nums[0], "from_items": nums[1], "to_items": nums[2],
            "lose": int(NUM_RE.search(cells[2]).group(0)),
            "gain": int(NUM_RE.search(cells[3]).group(0)),
            "flips": int(NUM_RE.search(cells[4]).group(0)),
            "same_pass_set": cells[5] == "是",
        }
    return pairs


def read_fact(path, fact_id):
    out, cur = "", None
    for line in open(path, encoding="utf-8"):
        if line.startswith("#"):
            cur = line.split("::")[0].strip("# ").strip() if "::" in line else None
            continue
        if cur == fact_id:
            out += line
    return out


def run():
    r = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, cwd=REPO)
    if r.returncode not in (0, 1):
        raise SystemExit(f"a05 的 kv_evidence.py 退出 {r.returncode}: {r.stderr.strip()[:300]}")
    return r.stdout


def parse(out):
    pairs, scores, checks = {}, {}, {}
    for line in out.split("\n"):
        m = PAIR_RE.match(line)
        if m:
            pairs[(m.group(1), m.group(2), m.group(3))] = {"lose": int(m.group(4)),
                                                           "gain": int(m.group(5))}
            continue
        m = SCORE_RE.match(line)
        if m:
            scores[m.group(1)] = {"mmlu": float(m.group(2)), "gsm8k": float(m.group(3)),
                                  "ifeval": float(m.group(4)), "humaneval_base": float(m.group(5)),
                                  "n": int(m.group(6))}
            continue
        m = CHECK_RE.match(line)
        if m:
            checks[m.group(2)] = {"ok": m.group(1) == "ok  ", "what": m.group(3), "detail": m.group(4)}
    key = ("base", "f16_f16", "q4_0_q4_0")
    if key not in pairs:
        raise SystemExit("a05 的输出里找不到 f16→q4_0 的 base 逐题配对；报告不引用未解析到的数字")
    plus = pairs.get(("plus", "f16_f16", "q4_0_q4_0"))
    q8 = pairs.get(("base", "f16_f16", "q8_0_q8_0"))
    if not (plus and q8):
        raise SystemExit("a05 的输出里缺少 plus 或 q8_0 的配对行")
    base = pairs[key]
    facts = os.path.join(REPO, "docs", "subprojects", "a05-KV 缓存精度", "RESULT.md")
    tm = parse_two_metrics(read_fact(facts, TWO_METRICS_PATH_HINT))
    if not tm:
        raise SystemExit("a05 的 RESULT.md 里找不到 kv-two-metrics 的两口径表；报告不引用未解析到的数字")
    zero_diff_flip = [k for k, v in tm.items() if v["score_delta_items"] == 0 and not v["same_pass_set"]]
    widest = max(tm.items(), key=lambda kv: kv[1]["flips"])
    return {
        "source_script": os.path.relpath(SCRIPT, REPO),
        "source_fact": os.path.relpath(facts, REPO) + "::" + TWO_METRICS_PATH_HINT,
        "two_metrics": tm,
        "zero_diff_but_flipped": zero_diff_flip,
        "widest_flip": {"pair": widest[0], **widest[1]},
        "no_per_item_columns": ["mmlu", "gsm8k", "ifeval"],
        "scores": scores,
        "pairs": {"base_f16_to_q4": base, "plus_f16_to_q4": plus, "base_f16_to_q8": q8},
        "checks": checks,
        "long_context": long_context(),
        "m29_ingested": False,
    }


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    doc = parse(run())
    text = dump(doc)
    if "--check" in argv:
        try:
            have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is missing", file=sys.stderr)
            return 1
        if have != text:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is stale against a05's script output; rerun without --check", file=sys.stderr)
            return 1
        print(f"kv_evidence.json: up to date (base f16->q4_0 lose {doc['pairs']['base_f16_to_q4']['lose']} "
              f"gain {doc['pairs']['base_f16_to_q4']['gain']})")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}: base f16->q4_0 lose {doc['pairs']['base_f16_to_q4']['lose']} "
          f"gain {doc['pairs']['base_f16_to_q4']['gain']}; plus lose {doc['pairs']['plus_f16_to_q4']['lose']} "
          f"gain {doc['pairs']['plus_f16_to_q4']['gain']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
