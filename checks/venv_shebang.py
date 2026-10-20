#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""venv 入口点的 shebang 必须指向存在的解释器。

venv 是 gitignore 的，但它创建的入口点脚本把创建时的解释器绝对路径写进 shebang。工程根搬过之后
（`/home/z/hf/research` → 本仓库），老的 venv 会让 `lm_eval` 之类的命令直接 `FileNotFoundError`，
而失败信息里只有「找不到文件」，看不出根因。

    python3 checks/venv_shebang.py [ROOT]     # ROOT 默认 .wrapup
"""
from __future__ import annotations

import os
import sys

ROOT = ".wrapup"


def scan(root):
    """[(路径, shebang 里的解释器)] —— 只报 shebang 指向不存在解释器的入口点。"""
    bad = []
    for dirpath, _dirs, files in os.walk(root):
        if os.path.basename(dirpath) != "bin":
            continue
        for name in sorted(files):
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                continue
            try:
                with open(path, "rb") as fh:
                    head = fh.readline(400)
            except OSError:
                continue
            if not head.startswith(b"#!"):
                continue
            parts = head[2:].decode("utf-8", "replace").strip().split()
            if not parts:
                continue
            interp = parts[0]
            if not (interp.startswith("/") or interp.startswith(".wrapup")):
                continue      # `#!/usr/bin/env python3` 之类由 PATH 决定，不在这里判
            if not os.path.exists(interp):
                bad.append((path, interp))
    return bad


def main(argv):
    root = argv[0] if argv else os.path.join(os.getcwd(), ROOT)
    bad = scan(root)
    if bad:
        print(f"FAIL: {len(bad)} 个入口点的 shebang 指向不存在的解释器：")
        for path, interp in bad[:20]:
            print(f"  - {path} -> {interp}")
        print("  重建：bash bootstrap_venv.sh <venv 目录> <requirements>")
        return 1
    print(f"venv shebangs: ok under {root}（入口点不存在或指向存在的解释器）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
