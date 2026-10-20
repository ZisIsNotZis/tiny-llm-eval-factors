#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：第三节「同字节下探测不到方案/厂商位移」这句话是生成的，不是写死的。

三种情形，都只改索引副本（`scheme_effects.json`），不动仓库文件：

  1. 忠实：全部标签系数跨 0 → 正文必须说「探测不到」，且不出现「探测到了」；
  2. 把 IQ 的 ARC-c 区间改成不含 0 → 正文必须改口成「探测到」，并点名那个基准；
  3. 把所有区间加宽一倍 → 正文的精度数字必须跟着变（旧的半宽不得再出现）。

    python3 checks/scheme_effects_negative_control.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import make_report  # noqa: E402

BASE = REPO / "report_inputs" / "scheme_effects.json"


def rendered(index_path):
    saved = make_report.SCHEME_EFFECTS
    make_report.SCHEME_EFFECTS = str(index_path)
    try:
        return make_report.scheme_effects_html()
    finally:
        make_report.SCHEME_EFFECTS = saved


def main():
    ok = True
    honest = json.loads(BASE.read_text(encoding="utf-8"))
    base_text = rendered(BASE)
    undetected = "探测不到" in base_text and "探测到了" not in base_text
    print(f"1) baseline (all cross 0) : says 探测不到 and not 探测到了: {undetected}")
    if not undetected:
        print("FAIL: 基线没有按「全部跨 0」来写")
        print(base_text[:400])
        ok = False

    tmp = Path(tempfile.mkdtemp(prefix="scheme-effects-negative-control-"))
    try:
        bent = json.loads(json.dumps(honest))
        row = next(r for r in bent["rows"] if r["bench"] == "ARC-c")
        row["IQ"] = {"est": 0.30, "lo": 0.12, "hi": 0.48}
        bent["labels"]["IQ"]["significant_benches"] = ["ARC-c"]
        bent["labels"]["IQ"]["crosses_zero_on"] = bent["benches"] - 1
        path = tmp / "bent.json"
        path.write_text(json.dumps(bent, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        text_bent = rendered(path)
        detected = "探测到了" in text_bent and "ARC-c" in text_bent and "探测不到方案" not in text_bent
        print(f"2) IQ on ARC-c made significant : says 探测到了 and names ARC-c: {detected}")
        if not detected:
            print("FAIL: 有系数显著时正文仍说「探测不到」")
            print(text_bent[:400])
            ok = False

        wide = json.loads(json.dumps(honest))
        for r in wide["rows"]:
            for label in ("IQ", "local", "bartowski"):
                c = r[label]
                half = (c["hi"] - c["lo"]) / 2 * 2
                c["lo"], c["hi"] = c["est"] - half, c["est"] + half
        for label, v in wide["labels"].items():
            halves = [(r[label]["hi"] - r[label]["lo"]) / 2 for r in wide["rows"]]
            v["half_width_min"], v["half_width_max"] = round(min(halves), 4), round(max(halves), 4)
        path2 = tmp / "wide.json"
        path2.write_text(json.dumps(wide, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        text_wide = rendered(path2)
        old_hi = f"{honest['labels']['bartowski']['half_width_max']:.2f}"
        new_hi = f"{wide['labels']['bartowski']['half_width_max']:.2f}"
        follows = new_hi in text_wide and f"≤{old_hi}" not in text_wide
        print(f"3) all intervals doubled       : precision now {new_hi} (was {old_hi}): {follows}")
        if not follows:
            print("FAIL: 精度数字没有跟着区间变")
            print(text_wide[:400])
            ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if ok:
        print("PASS: 结论句与其精度都来自 a03 的归因脚本输出；把某个系数改成显著或把区间加宽，正文随之改口")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
