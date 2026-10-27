#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`checks/recap_consistency.py` 的负控：证明它会为四种错误变红。

  1. 改掉一句为已撤回的措辞（「同大小下方案有差」）→ 红；
  2. 删掉一行结论 → 行数不等 → 红；
  3. 把「详见」改成一个不存在的节号 → 编号不是 1..16 → 红；
  4. 未改动的报告 → 绿。

每次注入都在临时副本里做，原报告不碰。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CHECK = os.path.join(HERE, "recap_consistency.py")
REPORT = os.path.join(REPO, "report.html")


def run(report_path: str) -> int:
    env = dict(os.environ)
    # 检查脚本把 REPORT 固定成仓库里的那份；用 cwd 里的一份副本代替。
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "checks"), exist_ok=True)
        shutil.copy(report_path, os.path.join(td, "report.html"))
        # 检查脚本把 REPO 定义成自己所在目录的父目录；放在 <td>/checks/ 下，REPO 才是 <td>。
        shutil.copy(CHECK, os.path.join(td, "checks", "recap_consistency.py"))
        return subprocess.run([sys.executable, os.path.join(td, "checks", "recap_consistency.py")],
                              cwd=td, capture_output=True, text=True).returncode


def main() -> int:
    if not os.path.exists(REPORT):
        print("BLOCKED report.html 不在场")
        return 2
    text = open(REPORT, encoding="utf-8").read()
    ok = 0
    checks = []

    def check(name, cond):
        nonlocal ok
        checks.append((name, cond))
        if cond:
            ok += 1

    # 0) baseline green
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        base = fh.name
    try:
        check("baseline 绿", run(base) == 0)

        # 1) retracted phrasing
        bad = text.replace("本设计分辨率内，同字节下方案与厂商都不可分辨；标签代理的是比特分配",
                           "同大小下方案有差", 1)
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
            fh.write(bad)
            p1 = fh.name
        check("注入已撤回措辞 → 红", run(p1) != 0)

        # 2) delete one recap row (the first <tr><td> row inside recap)
        row = re.search(r"<tr><td>量化位宽</td>.*?</tr>", text, re.S)
        check("找得到要删的那一行", row is not None)
        bad2 = text.replace(row.group(0), "", 1) if row else text
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
            fh.write(bad2)
            p2 = fh.name
        check("删一行 → 红", run(p2) != 0)

        # 3) wrong section ref
        bad3 = re.sub(r"<td>§1</td>", "<td>§99</td>", text, count=1)
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
            fh.write(bad3)
            p3 = fh.name
        check("详见指向不存在的节 → 红", run(p3) != 0)
    finally:
        for p in (base, locals().get("p1"), locals().get("p2"), locals().get("p3")):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    for name, cond in checks:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    if ok == len(checks):
        print(f"NEGATIVE CONTROL OK: {ok}/{len(checks)}（原报告未被改动）")
        return 0
    print(f"NEGATIVE CONTROL FAIL: {ok}/{len(checks)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
