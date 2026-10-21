#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`docs/subprojects/*/RESULT.md` 点名的每个 `.wrapup/…` 路径，在 clone 里必须有处置（p-entry3）。

判据三条，缺一即红：

    tracked    路径本身入库
    gz         路径本身不在，但 `<path>.gz` 入库（`.log` 的处置：被点名的才入库，且压缩入库）
    class      按 `.gitignore` 的类忽略——这是「可重建缓存」的已声明处置，由 `git check-ignore` 认
    其余（既不在盘上、也没入库、也不在任何一个已声明的类里）→ FAIL 并逐条点名

`.log` 另加一条：登记表里的 9 个文件必须 tracked 且 gunzip 后的字节数与登记值相同——`.gz` 里装的
必须是那一份，不是别的。登记值是文件指纹，不是从别处可算出的数，所以写在这里。

    python3 checks/evidence_logs.py    # exit 0 = 每条都有处置；exit 1 = 有路径没人认领
"""
from __future__ import annotations

import glob
import gzip
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# p-entry3 的处置登记：被点名的 `.log` → 原始字节数（`.gz` 必须还原成这么多）
EVIDENCE_LOGS = {
    ".wrapup/axes_diffusion_gate.log": 263,
    ".wrapup/i01_noise_floor.log": 515433,
    ".wrapup/m160.log": 258379,
    ".wrapup/m163.log": 331017,
    ".wrapup/m30b.log": 635466,
    ".wrapup/m6b.log": 333411,
    ".wrapup/mres/i01-shim-probe/shim_probe.log": 96,
    ".wrapup/mres/m128-spec-9b/server.log": 7212339,
    ".wrapup/mres/m142-qat-gemma31b-q4/code.log": 2751,
}

PATH_RE = re.compile(r"\.wrapup/[A-Za-z0-9._/-]*[A-Za-z0-9_-]")


def tracked_files() -> list[str]:
    out = git("ls-files", "-z").stdout
    return [p for p in out.split("\0") if p]


def glob_matches_are_declared(path: str) -> bool:
    """`a01_type_probe_*.log` 这种写法：展开到的每个文件都必须在已声明的类里（或已入库）。"""
    hits = [m for m in glob.glob(os.path.join(REPO, path + "*"))
            if os.path.basename(m) != os.path.basename(path) + ".gz"]
    if not hits:
        return False
    for m in hits:
        rel = os.path.relpath(m, REPO)
        if git("check-ignore", "-q", rel).returncode != 0 and \
                git("ls-files", "--error-unmatch", rel).returncode != 0:
            return False
    return True


def is_prefix_of_tracked(path: str) -> bool:
    """文档里的路径常常是 glob/花括号展开的前缀（`.wrapup/m`、`.wrapup/mres/i01-floor`）。
    这种写法由它下面的真实文件指认，不是一条能打开的证据行，故只要求「下面有入库的东西」。"""
    return any(t.startswith(path) for t in tracked_files())


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def named_paths() -> list[str]:
    paths: set[str] = set()
    for doc in glob.glob(os.path.join(REPO, "docs", "subprojects", "*", "RESULT.md")):
        with open(doc, encoding="utf-8") as fh:
            paths.update(PATH_RE.findall(fh.read()))
    return sorted(paths)


def disposition(path: str) -> str:
    if git("ls-files", "--error-unmatch", path).returncode == 0:
        return "tracked"
    if git("ls-files", "--error-unmatch", path + ".gz").returncode == 0:
        return "gz"
    if is_prefix_of_tracked(path) or os.path.isdir(os.path.join(REPO, path)):
        return "dir"
    if glob_matches_are_declared(path):
        return "glob"
    if git("check-ignore", "-q", path).returncode == 0:
        return "class"
    return ""


def main() -> int:
    paths = named_paths()
    counts = {"tracked": 0, "gz": 0, "dir": 0, "glob": 0, "class": 0, "": 0}
    failures: list[str] = []
    for path in paths:
        kind = disposition(path)
        counts[kind] += 1
        if not kind:
            failures.append(f"FAIL 无处置（不在盘上/未入库/不在任何已声明的类里）：{path}")

    for path, raw_bytes in sorted(EVIDENCE_LOGS.items()):
        gz_path = os.path.join(REPO, path + ".gz")
        if git("ls-files", "--error-unmatch", path + ".gz").returncode != 0:
            failures.append(f"FAIL 登记的 .log 未被跟踪：{path}.gz")
            continue
        with gzip.open(gz_path, "rb") as fh:
            got = len(fh.read())
        if got != raw_bytes:
            failures.append(f"FAIL {path}.gz 解开是 {got} 字节，登记的是 {raw_bytes} 字节")

    print(f"点名的 `.wrapup/…` 路径 {len(paths)} 条："
          f"入库 {counts['tracked']}、压缩入库 {counts['gz']}、目录/前缀 {counts['dir']}、通配 {counts['glob']}、"
          f"按类忽略 {counts['class']}、无处置 {counts['']}")
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
