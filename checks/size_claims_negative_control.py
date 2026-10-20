#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：第二节「同一配方下越大越高被反驳」这句话由区间决定，不是写死的。

两种情形，只改索引副本：
  1. 忠实：gemma-4 Q2_K_XL 的反例步区间不重叠 → 正文必须说「反驳」且点出 −20.1 pp；
  2. 把反例两步的区间改成互相重叠 → 正文必须改口成「重叠（分不出）」，不得再断言反驳。

    python3 checks/size_claims_negative_control.py
"""
from __future__ import annotations

import json, shutil, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import make_report  # noqa: E402

BASE = REPO / "report_inputs" / "size_claims.json"


def rendered(path):
    saved = make_report.SIZE_CLAIMS
    make_report.SIZE_CLAIMS = str(path)
    try:
        return make_report.size_claims_html()
    finally:
        make_report.SIZE_CLAIMS = saved


def main():
    honest = json.loads(BASE.read_text(encoding="utf-8"))
    base = rendered(BASE)
    ok = "不重叠" in base and "被反驳" in base
    print(f"1) baseline (CIs disjoint) : says 不重叠 and 被反驳: {ok}")
    if not ok:
        print("FAIL: 基线没有按不重叠来写"); print(base[:400]); return 1

    tmp = Path(tempfile.mkdtemp(prefix="size-claims-negative-control-"))
    try:
        bent = json.loads(json.dumps(honest))
        bent["inversion"]["overlap"] = True
        p = tmp / "overlap.json"
        p.write_text(json.dumps(bent, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        text = rendered(p)
        changed = "重叠（分不出）" in text and "被反驳" not in text
        print(f"2) CIs made to overlap     : says 重叠（分不出） and drops 被反驳: {changed}")
        if not changed:
            print("FAIL: 区间改成重叠后正文仍断言反驳——说明文字写死了"); print(text[:400])
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: 反驳/分不出的措辞由区间是否重叠决定")
    return 0


if __name__ == "__main__":
    sys.exit(main())
