#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README 里关于「哪些产物入库」的说法必须与 `git ls-files` 一致。

来由：README 曾一边说 `.wrapup/mres/*_eval.json` 不入库、一边在 Ships 清单里列它们，而且写的文件数
（337）后来漂成 341。数字写死在 README 会再次漂，所以这里断言两件事：
  1. README 不再说这些产物「不入库」；
  2. 只要 README 里写了具体文件数，就必须等于 `git ls-files` 的实际计数。
"""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
PATTERN = ".wrapup/mres/*_eval.json"


def main():
    text = README.read_text(encoding="utf-8")
    tracked = subprocess.run(["git", "ls-files", PATTERN], cwd=REPO,
                             capture_output=True, text=True).stdout.split()
    n = len(tracked)
    problems = []
    for line in text.split("\n"):
        if PATTERN in line and "不入库" in line:
            problems.append(f"README 仍说 {PATTERN} 不入库：{line.strip()[:80]}")
    stated = re.findall(r"(\d+)\s*files", text)
    if stated and str(n) not in stated:
        problems.append(f"README 写的文件数 {stated} 与 git ls-files 的 {n} 不一致")
    print(f"tracked eval artefacts: {n}; README 里写死的数：{stated or '（无，按 git ls-files 计数）'}")
    if problems:
        print("FAIL:")
        for p in problems:
            print("  -", p)
        return 1
    print("PASS: README 与 git ls-files 对「哪些产物入库」的说法一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
