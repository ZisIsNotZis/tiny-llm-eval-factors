#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：事实 id 的唯一性是**文件作用域**，两条都要能判。

  1. 同一个文件里重复声明同一个 id → check_docs 必须 FAIL 并点名；
  2. 两个不同文件各自声明 `res1`（各子项目各自编号）→ 必须 PASS（这不是冲突）。

做法：临时 docs 树，复制仓库的 docs（schema 与层文件），再加两个 fixture 子项目。
"""
from __future__ import annotations
import shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECK = REPO / "docs" / "check_docs.py"


def run(docs_root):
    r = subprocess.run([sys.executable, str(CHECK), str(docs_root)],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def write(path: Path, body: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="docs-dup-neg-"))
    try:
        docs = tmp / "docs"
        shutil.copytree(REPO / "docs", docs)
        # 1) 同一文件重复声明
        write(docs / "subprojects" / "zz-dup" / "RESULT.md",
              "## res1 :: 第一条事实。\n\n## res1 :: 同一个文件里又声明了一次。\n")
        rc1, out1 = run(docs)
        named = "declared twice" in out1 or "duplicate" in out1
        print(f"1) duplicate id in one file : exit {rc1} (expect 1), names it: {named}")
        ok1 = rc1 == 1 and named

        # 2) 两个文件各自声明 res1（正常情形）
        shutil.rmtree(docs / "subprojects" / "zz-dup")
        write(docs / "subprojects" / "zz-a" / "RESULT.md", "## res1 :: a 的第一条。\n")
        write(docs / "subprojects" / "zz-b" / "RESULT.md", "## res1 :: b 的第一条。\n")
        rc2, out2 = run(docs)
        print(f"2) same id in two files     : exit {rc2} (expect 0)")
        ok2 = rc2 == 0
        if not ok2:
            print(out2[-800:])
        print("PASS: 文件内重复 → FAIL 并点名；跨文件同名 → PASS（作用域是文件）"
              if (ok1 and ok2) else "FAIL")
        return 0 if (ok1 and ok2) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
