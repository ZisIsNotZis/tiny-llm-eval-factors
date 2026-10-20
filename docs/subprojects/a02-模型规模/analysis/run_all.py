#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a02 的唯一验收入口：把四个分析脚本的断言全跑一遍。

    python3 "docs/subprojects/a02-模型规模/analysis/run_all.py"            # 全跑，退出码即结论
    python3 "docs/subprojects/a02-模型规模/analysis/run_all.py" --selftest # 负控：篡改后必须失败

每个脚本自己打印预期，`--check` 的退出码是唯一判据。`--selftest` 用
`size_provenance.py --selftest` 的进程内篡改证明检查会失败——若那个负控没失败，本入口也失败。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PY = sys.executable

STEPS = [
    ("size_provenance.py", "库的每一行 __size 归到一条取数通道"),
    ("size_ladder.py", "三个候选 X 的逐族可用性"),
    ("size_regression.py", "plan5 双变量回归的可识别性"),
    ("size_curves.py", "每家族规模曲线"),
    ("size_moe_position.py", "同激活参数下 MoE 的位置"),
]


def run(script, args):
    return subprocess.run([PY, str(HERE / script), *args], cwd=REPO,
                          capture_output=True, text=True)


def main(argv):
    failed = []
    for script, what in STEPS:
        p = run(script, ["--check"])
        tail = [l for l in p.stdout.strip().split("\n") if "expected true" in l]
        status = "PASS" if p.returncode == 0 else "FAIL"
        print(f"[{status}] {script:24s} {what:32s} {tail[-1] if tail else ''}")
        if p.returncode != 0:
            failed.append(script)
            print(p.stdout[-1500:])
            print(p.stderr[-800:])

    if "--selftest" in argv:
        p = run("size_provenance.py", ["--selftest"])
        seen = "expected failure was seen" in p.stdout
        print(f"[{'PASS' if seen else 'FAIL'}] negative control: 篡改一条通道后检查必须失败")
        if not seen:
            failed.append("selftest")
            print(p.stdout[-800:])

    print(f"\n{len(STEPS) - len(failed)}/{len(STEPS)} checks green"
          + ("" if not failed else f"; failed: {failed}"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
