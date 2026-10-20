#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：报告「测量可复现性边界」一节的数字是生成的，不是写死的。

三种情形，都在 `i01/RESULT.md` 的临时副本上做（不动仓库文件）：

  1. 忠实生成：正文必须含 `±16/161` 与 `≈ 0.10`；
  2. 把幅度改成 0（`±0/161`）：生成的正文必须随之变成 `±0/161`，而不是继续印 16；
  3. 删掉适用条件那句话：生成器必须**失败**（报告不能在没有条件的情况下引用这个幅度）。

    python3 checks/reproducibility_negative_control.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "report_inputs"))
import build_reproducibility as br  # noqa: E402
import make_report  # noqa: E402

BASE = REPO / "report_inputs" / "reproducibility.json"


def generated(index_path):
    saved = make_report.REPRODUCIBILITY
    make_report.REPRODUCIBILITY = str(index_path)
    try:
        return make_report.reproducibility_html()
    finally:
        make_report.REPRODUCIBILITY = saved


def main():
    ok = True
    baseline = generated(BASE)
    if "±16/161" not in baseline or "0.10" not in baseline:
        print("FAIL: 基线正文里没有 ±16/161 与 ≈0.10")
        return 1
    print("1) baseline            : contains ±16/161 and ≈0.10")

    tmp = Path(tempfile.mkdtemp(prefix="reproducibility-negative-control-"))
    try:
        source = sorted((REPO / "docs").glob("subprojects/i01-*/RESULT.md"))[0]
        text = source.read_text(encoding="utf-8")

        # 2) 幅度改成 0，索引跟着改，正文必须跟着变
        bent_src = tmp / "bent.md"
        bent_src.write_text(text.replace("±16/161（≈0.10）", "±0/161（≈0.00）"), encoding="utf-8")
        saved_glob = br.SOURCE_GLOB
        br.SOURCE_GLOB = str(bent_src)
        try:
            doc = br.scan()
        finally:
            br.SOURCE_GLOB = saved_glob
        bent_index = tmp / "reproducibility.json"
        bent_index.write_text(br.dump(doc), encoding="utf-8")
        text_zero = generated(bent_index)
        changed = "±0/161" in text_zero and "±16/161" not in text_zero
        print(f"2) amplitude set to 0  : text now says ±0/161 and no ±16/161: {changed}")
        if not changed:
            print("FAIL: 幅度改成 0 后正文没变——说明数字是写死的")
            ok = False

        # 3) 删掉适用条件 → 生成器必须失败
        no_cond = text.replace(
            "所以任何两次 run 只有在**提示集哈希 + 后处理版本**都被钉住并记录时才可比；", "所以：")
        assert no_cond != text, "条件句没找到，负控无效"
        no_cond_src = tmp / "no_cond.md"
        no_cond_src.write_text(no_cond, encoding="utf-8")
        br.SOURCE_GLOB = str(no_cond_src)
        try:
            br.scan()
            print("FAIL: 删掉适用条件后生成器仍然成功")
            ok = False
        except SystemExit as exc:
            print(f"3) condition removed   : generator refuses -> {exc}")
        finally:
            br.SOURCE_GLOB = saved_glob
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if ok:
        print("PASS: 这一节的数字与适用条件都来自 i01 的事实，改事实就改文字，缺条件就构建失败")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
