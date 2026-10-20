#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""禁止已退役的绝对根路径出现在可执行脚本里。

`.wrapup/` 的脚本原先硬编码 `/home/z/hf/research`，而该目录在本机已不存在，于是任何重跑
都在准备阶段静默失败（m160 就是这样死在 setup 里）。脚本改成用自身位置推根：
shell 用 `REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`，python 用
`Path(__file__).resolve().parent.parent`。

历史记录类文件（`*.log`、`*.txt`、`*.json`、`*.out`、`*.args`）**不改写**：它们是当时实际
执行过什么的证据，改掉就等于伪造运行记录。检查只覆盖会被执行的 `*.sh` 与 `*.py`。

    python3 checks/stale_roots.py          # 只检查，有残留就退出 1
    python3 checks/stale_roots.py --fix    # 幂等迁移：改完后仍会检查
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIR = os.path.join(REPO, ".wrapup")
STALE_ROOTS = ("/home/z/hf/research",)
SKIP_DIRS = {"lmenv", "msenv", "evalpy", "bfclenv", "mplenv", "jars", "dl_ready",
             "ppl_corpora", "wres", "mres", "prompts", "__pycache__"}
EXECUTABLE_EXT = (".sh", ".py")

SHELL_ROOT_LINE = ('REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"'
                   '  # 仓库根：脚本按自身位置定位，不再写死绝对路径\n')
PY_ROOT_LINE = ('REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent'
                '  # 仓库根：脚本按自身位置定位，不再写死绝对路径\n')


def carriers():
    """会执行的脚本里仍含退役根路径的文件。"""
    hits = []
    for root, dirs, files in os.walk(SCAN_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if not name.endswith(EXECUTABLE_EXT):
                continue
            path = os.path.join(root, name)
            text = open(path, encoding="utf-8", errors="replace").read()
            if any(r in text for r in STALE_ROOTS):
                hits.append(path)
    return sorted(hits)


def fix(path):
    """把退役根替换成 REPO_ROOT，并在 shebang 后插入 REPO_ROOT 的定义。"""
    text = open(path, encoding="utf-8").read()
    for stale in STALE_ROOTS:
        text = text.replace(stale, "${REPO_ROOT}" if path.endswith(".sh") else "str(REPO_ROOT)")
    if path.endswith(".sh"):
        lines = text.split("\n")
        if not any(ln.startswith("REPO_ROOT=") for ln in lines):
            at = 1 if lines and lines[0].startswith("#!") else 0
            lines.insert(at, SHELL_ROOT_LINE.rstrip("\n"))
        text = "\n".join(lines)
    else:
        if "REPO_ROOT = " not in text:
            lines = text.split("\n")
            # `from __future__` must stay the first statement after the docstring,
            # so the definition goes after the last of those lines.
            future = [i for i, ln in enumerate(lines) if ln.startswith("from __future__")]
            at = (future[-1] + 1) if future else (1 if lines and lines[0].startswith("#!") else 0)
            lines.insert(at, PY_ROOT_LINE.rstrip("\n"))
            text = "\n".join(lines)
    open(path, "w", encoding="utf-8").write(text)
    return path


def syntax_ok(paths):
    """改过的脚本必须还能解析：shell 用 bash -n，python 用 py_compile。"""
    bad = []
    for path in paths:
        if path.endswith(".sh"):
            r = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
        else:
            r = subprocess.run([sys.executable, "-m", "py_compile", path],
                               capture_output=True, text=True)
        if r.returncode != 0:
            bad.append((path, (r.stderr or r.stdout).strip().split("\n")[-1]))
    return bad


def main(argv):
    hits = carriers()
    if "--fix" in argv and hits:
        for path in hits:
            fix(path)
        bad = syntax_ok(hits)
        print(f"migrated {len(hits)} script(s) to REPO_ROOT; syntax errors: {len(bad)}")
        for path, err in bad:
            print(f"  FAIL {os.path.relpath(path, REPO)}: {err}")
        if bad:
            return 1
        hits = carriers()
    if hits:
        print(f"FAIL: {len(hits)} executable script(s) still carry a retired root:")
        for path in hits:
            print("  -", os.path.relpath(path, REPO))
        return 1
    print(f"stale roots: none in executable scripts under {os.path.relpath(SCAN_DIR, REPO)}/"
          f" (records such as *.log/*.txt/*.json keep the path they ran with and are exempt)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
