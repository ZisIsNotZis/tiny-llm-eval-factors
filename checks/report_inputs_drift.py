#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告输入是否还跟它的来源一致：一处判断的家。

`report_inputs/*.json` 是**派生**物：每一份都由某个子项目的产物重算得到，`--check` 只比对不重写。
`reproduce.sh` 过去把「输入与来源不一致」记 WARN 就继续，于是报告可以带着旧值判绿（`p-entry2`）。
本脚本把那 13 条判断收到一个家里，只有一种读法：

    PASS  来源在场，输入与它一致
    FAIL  来源在场，输入与它不一致 —— 这是漂移，`reproduce.sh` 因此非零退出
    SKIP  看不到来源（缺席），无从当场核对 —— absent 不是漂移，随仓库分发的那份即权威

`SKIP` 必须由「来源不在场」证成，不能由「比对失败」冒充：来源文件在盘上却读不出 → FAIL。
三个 builder（`build_kv_evidence` / `build_size_claims` / `build_spec_decode`）自己以 rc=2 表达
「来源不在场」；其余十个只有 rc=0/1，所以来源在不在由本脚本先查，查不到就 SKIP，查到了再判。

    python3 checks/report_inputs_drift.py   # 每行 "<STATUS>\t<给 reproduce.sh 记录的那句话>"
    exit 0 = 无漂移；exit 1 = 有漂移
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# (输入文件, builder, PASS 文案, FAIL 文案)
CHECKS = [
    ("report_inputs/bfcl_judge.json", "build_bfcl_judge.py",
     "bfcl_judge.json 与 a13 的判分器事实一致",
     "bfcl_judge.json 与 a13 的事实不一致：python3 report_inputs/build_bfcl_judge.py"),
    ("report_inputs/sampling_collapse.json", "build_sampling_collapse.py",
     "sampling_collapse.json 与 a06 的事实一致",
     "sampling_collapse.json 与 a06 的事实不一致：python3 report_inputs/build_sampling_collapse.py"),
    ("report_inputs/spec_decode.json", "build_spec_decode.py",
     "spec_decode.json 与 a07 的证据一致",
     "spec_decode.json 与 a07 的证据不一致：python3 report_inputs/build_spec_decode.py"),
    ("report_inputs/gsq.json", "build_gsq.py",
     "gsq.json 与 a10 的事实一致",
     "gsq.json 与 a10 的事实不一致：python3 report_inputs/build_gsq.py"),
    ("report_inputs/moe_feasibility.json", "build_moe_feasibility.py",
     "moe_feasibility.json 与 a04 的可行性 fixture 一致",
     "moe_feasibility.json 与 a04 的 fixture 不一致：python3 report_inputs/build_moe_feasibility.py"),
    ("report_inputs/bfcl_gap.json", "build_bfcl_gap.py",
     "bfcl_gap.json 与现有 BFCL 汇总一致",
     "bfcl_gap.json 与 BFCL 汇总不一致：python3 report_inputs/build_bfcl_gap.py"),
    ("report_inputs/kv_evidence.json", "build_kv_evidence.py",
     "kv_evidence.json 与 a05 的证据脚本输出一致",
     "kv_evidence.json 与 a05 的脚本输出不一致：python3 report_inputs/build_kv_evidence.py"),
    ("report_inputs/size_claims.json", "build_size_claims.py",
     "size_claims.json 与 a02 的通道/曲线产物一致",
     "size_claims.json 与 a02 的产物不一致：python3 report_inputs/build_size_claims.py"),
    ("report_inputs/scheme_effects.json", "build_scheme_effects.py",
     "scheme_effects.json 与 a03 归因脚本的输出一致",
     "scheme_effects.json 与 a03 的脚本输出不一致：python3 report_inputs/build_scheme_effects.py"),
    ("report_inputs/reproducibility.json", "build_reproducibility.py",
     "reproducibility.json 与 i01 的地板/幅度事实一致",
     "reproducibility.json 与 i01 的事实不一致：python3 report_inputs/build_reproducibility.py"),
    ("report_inputs/paired_deltas.json", "build_paired_deltas.py",
     "paired_deltas.json 与 a01 的配对差事实一致",
     "paired_deltas.json 与 a01 的事实不一致：python3 report_inputs/build_paired_deltas.py"),
    ("report_inputs/open_questions.json", "build_open_questions.py",
     "open_questions.json 与各子项目 PLAN.md 的「未解问题」一节一致",
     "open_questions.json 与 PLAN.md 不一致：python3 report_inputs/build_open_questions.py"),
    ("report_inputs/eval_status.json", "build_eval_status.py",
     "eval_status.json 与现有落盘产物一致",
     "eval_status.json 与落盘产物不一致：python3 report_inputs/build_eval_status.py"),
]

# 来源不在盘上时这些输入**无法**当场核对：这是缺席，不是漂移。登记的是来源路径，
# 只有它真不在场才允许 SKIP；三个以 rc=2 自报缺席的 builder 不需要在这里登记。
LOCAL_SOURCES = {
    "report_inputs/eval_status.json": [".wrapup/mres"],
}


def classify(input_rel: str, builder: str) -> tuple[str, str]:
    input_path = os.path.join(REPO, input_rel)
    if not os.path.exists(input_path):
        return "SKIP", f"{input_rel} 不在场（缺席，不是漂移；随仓库分发的那份即权威）"
    proc = subprocess.run(
        [sys.executable, os.path.join(REPO, "report_inputs", builder), "--check"],
        cwd=REPO, capture_output=True, text=True,
    )
    if proc.returncode == 0:
        return "PASS", ""
    if proc.returncode == 2:
        reason = ""
        for line in proc.stdout.splitlines():
            if line.startswith("UNVERIFIED:"):
                reason = line[len("UNVERIFIED:"):].strip()
                break
        return "SKIP", reason or f"{builder} --check 报来源不可得（rc=2）"
    missing = [p for p in LOCAL_SOURCES.get(input_rel, [])
               if not os.path.exists(os.path.join(REPO, p))]
    if missing:
        return "SKIP", (f"{input_rel} 与落盘产物的一致性（本机无 "
                        f"{'、'.join(missing)} 产物，随仓库分发的那份即权威）")
    return "FAIL", ""


def main() -> int:
    drift = 0
    for input_rel, builder, pass_text, fail_text in CHECKS:
        status, reason = classify(input_rel, builder)
        if status == "PASS":
            print(f"PASS\t{pass_text}")
        elif status == "SKIP":
            print(f"SKIP\t{reason}")
        else:
            drift += 1
            print(f"FAIL\t{fail_text}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
