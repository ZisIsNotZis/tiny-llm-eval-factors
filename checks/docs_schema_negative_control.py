#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：证明 `docs/check_docs.py` 真的会失败，而不是一个只会打印 PASS 的形状。

做法是一条安全的最小路径：把 `docs/` 复制到临时目录，先跑一次未改动的副本（必须 PASS），
再分别注入两个已知错误——删掉一条事实的必填字段 `author`、把 `status` 改成枚举外的值——
每次都必须以 1 退出并在输出里点名那个字段。基线 PASS 排除了「临时目录本身有问题」这个
另一种解释，所以失败确实来自被注入的那一处。

    python3 checks/docs_schema_negative_control.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "docs" / "check_docs.py"


def run(docs_root):
    r = subprocess.run([sys.executable, str(CHECKER), str(docs_root)],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def mutate_fact(path, fact_id, mutate):
    """对一条事实做一次文本级改动（保留文件其余部分原样）。"""
    lines = path.read_text(encoding="utf-8").split("\n")
    out, inside = [], False
    for line in lines:
        if line.startswith(f"{fact_id}:"):
            inside = True
            out.append(line)
            continue
        if inside and line and not line.startswith(" "):
            inside = False
        if inside:
            line = mutate(line)
        out.append(line)
    path.write_text("\n".join(out), encoding="utf-8")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="docs-negative-control-"))
    docs = tmp / "docs"
    try:
        shutil.copytree(REPO / "docs", docs)
        target = docs / "method" / "method.yaml"

        rc, out = run(docs)
        print(f"baseline (unmodified copy)         : exit {rc}")
        if rc != 0:
            print(out[-1500:])
            print("FAIL: 复制出来的未改动文档集就没有通过；负控无法成立")
            return 1

        mutate_fact(target, "m1", lambda ln: "" if ln.strip().startswith("author:") else ln)
        rc, out = run(docs)
        named = "author" in out
        print(f"missing required field `author`    : exit {rc}, names the field: {named}")
        if rc != 1 or not named:
            print(out[-1500:])
            print("FAIL: 缺必填字段没有以 1 退出并点名 author")
            return 1

        shutil.copyfile(REPO / "docs" / "method" / "method.yaml", target)
        mutate_fact(target, "m1",
                    lambda ln: "  status: bogus\n" if ln.strip().startswith("status:") else ln)
        rc, out = run(docs)
        named = "status" in out and "bogus" in out
        print(f"out-of-enum value `status: bogus`  : exit {rc}, names the field: {named}")
        if rc != 1 or not named:
            print(out[-1500:])
            print("FAIL: 枚举外取值没有以 1 退出并点名 status")
            return 1

        print("PASS: the checker fails on a fixture that is deliberately broken, "
              "and passes the same fixture unmodified")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
