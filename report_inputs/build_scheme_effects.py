#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `a03` 的方案/厂商归因**脚本输出**抽成派生索引，供报告第三节生成文字。

不抄散文：直接跑 `docs/subprojects/a03-量化方案与厂商/analysis/attrib.py`，解析它打印的系数表
（每个基准一行：位宽斜率 + 三个标签系数，各自带 95% 区间）与识别来源清单，然后算：

  * 哪些标签系数跨 0（= 同字节下探测不到水平位移）；
  * 每个标签的区间半宽（= 这套装置的精度，写进报告的就是它）；
  * 位宽斜率是否九列都不含 0（= 真正的变量是比特，不是标签）。

    python3 report_inputs/build_scheme_effects.py           # 重写 scheme_effects.json
    python3 report_inputs/build_scheme_effects.py --check   # 重跑脚本并比对
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "scheme_effects.json")
SCRIPT = os.path.join(REPO, "docs", "subprojects", "a03-量化方案与厂商", "analysis", "attrib.py")

ROW_RE = re.compile(r"^(\S+)\s+([+-][\d.]+) \[([+-][\d.]+),([+-][\d.]+)\]\s+"
                    r"([+-][\d.]+) \[([+-][\d.]+),([+-][\d.]+)\]\s+"
                    r"([+-][\d.]+) \[([+-][\d.]+),([+-][\d.]+)\]\s+"
                    r"([+-][\d.]+) \[([+-][\d.]+),([+-][\d.]+)\]\s+(\d+)\s*$")
IDENT_RE = re.compile(r"^  (\S+?): (.+)$")
BENCH_LABEL = {"HE": "HumanEval", "HE+": "HumanEval+", "MBPP": "MBPP", "MBPP+": "MBPP+",
               "MMLU": "MMLU", "ARC-c": "ARC-c", "TQA": "TruthfulQA", "GSM8K": "GSM8K",
               "IFEval": "IFEval"}


def run_script():
    r = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0:
        raise SystemExit(f"a03 的归因脚本退出 {r.returncode}：{r.stderr.strip()[:400]}")
    return r.stdout


def parse(out):
    rows, ident = [], {}
    for line in out.split("\n"):
        m = ROW_RE.match(line)
        if m:
            g = m.groups()
            rows.append({
                "bench": BENCH_LABEL.get(g[0], g[0]),
                "slope": {"est": float(g[1]), "lo": float(g[2]), "hi": float(g[3])},
                "IQ": {"est": float(g[4]), "lo": float(g[5]), "hi": float(g[6])},
                "local": {"est": float(g[7]), "lo": float(g[8]), "hi": float(g[9])},
                "bartowski": {"est": float(g[10]), "lo": float(g[11]), "hi": float(g[12])},
                "n": int(g[13]),
            })
            continue
        m = IDENT_RE.match(line)
        if m and not line.startswith("  其他来源"):
            ident[m.group(1)] = m.group(2)
    if not rows:
        raise SystemExit("attrib.py 的输出里没有可解析的系数表；报告不引用它就不会印数字")
    labels = ["IQ", "local", "bartowski"]
    summary = {}
    for label in labels:
        halves = [(row[label]["hi"] - row[label]["lo"]) / 2 for row in rows]
        significant = [row["bench"] for row in rows
                       if not (row[label]["lo"] <= 0 <= row[label]["hi"])]
        summary[label] = {
            "benches": len(rows),
            "significant_benches": significant,
            "crosses_zero_on": len(rows) - len(significant),
            "half_width_min": round(min(halves), 4),
            "half_width_max": round(max(halves), 4),
            "identified_by": ident.get(label, ""),
            # 「{'Qwen3.5-2B': [0.0, 1.0], …}」→ ['Qwen3.5-2B', …]
            "families": re.findall(r"'([^']+)':", ident.get(label, "")),
        }
    slope_sig = all(not (row["slope"]["lo"] <= 0 <= row["slope"]["hi"]) for row in rows)
    return {
        "source_script": os.path.relpath(SCRIPT, REPO),
        "benches": len(rows),
        "rows": rows,
        "labels": summary,
        "slope_significant_on_all": slope_sig,
        "slope_range": [round(min(r["slope"]["est"] for r in rows), 4),
                        round(max(r["slope"]["est"] for r in rows), 4)],
        "unidentifiable_sources": ""
        if "其他来源" in ident else "",
    }


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    doc = parse(run_script())
    text = dump(doc)
    if "--check" in argv:
        try:
            have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is missing", file=sys.stderr)
            return 1
        if have != text:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is stale against the script output; "
                  f"rerun without --check", file=sys.stderr)
            return 1
        print(f"scheme_effects.json: up to date ({doc['benches']} benches, "
              f"labels crossing 0: "
              f"{[k for k, v in doc['labels'].items() if not v['significant_benches']]})")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}: {doc['benches']} benches; "
          f"half-widths " + ", ".join(
              f"{k} {v['half_width_min']:.2f}-{v['half_width_max']:.2f}"
              for k, v in doc["labels"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
