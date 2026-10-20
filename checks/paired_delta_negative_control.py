#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：报告第一节的因果叙述是**生成的**，不是写死的。

复核指出原文把「Qwen3.5-2B 在 3.96→4.11 掉点」归因于方案差异，而实测只有 HumanEval+ 的配对区间
不含 0，其余跨 0。这个负控把 `a01` 的那条事实改成「所有区间都跨 0」，再让报告重新生成文字：

  * 只要文字跟着改成「区间全部跨 0／不声称掉点」，就说明它真的由事实生成；
  * 若文字仍然声称掉点或被数据支持，就说明它还是写死的。

    python3 checks/paired_delta_negative_control.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "report_inputs"))
import build_paired_deltas as bpd  # noqa: E402
import make_report  # noqa: E402

BASE = REPO / "report_inputs" / "paired_deltas.json"


def rendered(index_path):
    """用给定索引重渲染那段文字（临时改模块里的路径常量，不动仓库文件）。"""
    saved = make_report.PAIRED_DELTAS
    make_report.PAIRED_DELTAS = str(index_path)
    try:
        return make_report.inversion_callout()
    finally:
        make_report.PAIRED_DELTAS = saved


def main():
    honest = json.loads(BASE.read_text(encoding="utf-8"))
    sig = [m["metric"] for m in honest["metrics"] if m["significant"]]
    if not sig:
        print("FAIL: 现在的索引里没有显著项，这个负控需要至少一个被区间支持的差异")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="paired-delta-negative-control-"))
    try:
        # 1) 忠实渲染：必须点名那个显著基准
        text_ok = rendered(BASE)
        print(f"baseline  : significant={sig}, text claims them: {all(m in text_ok for m in sig)}")
        if not all(m in text_ok for m in sig):
            print("FAIL: 基线渲染没有点名被支持的基准")
            return 1

        # 2) 把所有区间改成跨 0 的副本
        bent = json.loads(json.dumps(honest))
        for m in bent["metrics"]:
            m["lo"], m["hi"], m["significant"] = -abs(m["delta"]) - 0.01, abs(m["delta"]) + 0.01, False
        path = tmp / "paired_deltas.json"
        path.write_text(json.dumps(bent, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        text_bent = rendered(path)
        claims_drop = ("区间不含 0" in text_bent) or ("「同时下降」" in text_bent and "不能说" not in text_bent)
        says_none = "区间全部跨 0" in text_bent or "分不出差别" in text_bent
        print(f"all CIs spanning 0: says no difference: {says_none}, still claims a supported drop: {claims_drop}")
        if claims_drop or not says_none:
            print("FAIL: 区间全部跨 0 时文字仍然声称掉点——说明它是写死的")
            print(text_bent[:600])
            return 1

        # 3) 索引与事实一致（不是手改的索引）
        rc = os.system(f'cd "{REPO}" && python3 report_inputs/build_paired_deltas.py --check >/dev/null 2>&1')
        print(f"index matches the fact: {rc == 0}")
        if rc != 0:
            print("FAIL: paired_deltas.json 与 a01 的事实不一致：python3 report_inputs/build_paired_deltas.py")
            return 1
        print("PASS: the callout follows the paired-CI fact; bend the fact and the text stops claiming a drop")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
