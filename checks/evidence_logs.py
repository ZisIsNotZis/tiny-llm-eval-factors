#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`docs/subprojects/*/RESULT.md` 点名的每个 `.wrapup/…` 路径，在 clone 里必须有处置（p-entry3）。

判据五条，缺一即红：

    tracked    路径本身入库
    gz         路径本身不在，但 `<path>.gz` 入库（`.log` 的处置：被点名的才入库，且压缩入库）
    dir        文档指的是一个目录 / 前缀（`…/a01-wp5-r{1,2}/`、`.wrapup/mres/m14*/`）——目录本身
               不是一条能打开的证据行，只要求它指的是盘上真实存在的目录或入库文件的前缀
    glob       文档写的是通配/花括号模式（token 后面紧跟 `*`、`?`、`[` 或 `{`）：展开到的**每一个**
               命中都必须在已声明的类里（或已入库，或是一个目录）
    class      路径落在 `.gitignore` 的一条**已声明可重建缓存类**的规则下，且路径的形状属于那一类
               （见下面的 `REBUILDABLE_CLASSES`，全库只有这一份清单；README 引用它，不另写一份）
    其余（不在盘上、没入库、落在别的 ignore 规则下）→ FAIL 并逐条点名，同时点名那条规则

两个方向都是踩出来的：

  * **精确点名的路径不做 glob 推断。** 旧写法用 `glob(path + "*")` 判所有 token，于是一个精确点名、
    在盘上、被 ignore 的文件被判成「通配」——它匹配的是它自己，绿的是「被忽略」，不是「有处置」。
    现在只有文档里真的写了通配符（token 紧跟 `*`/`?`/`[`/`{`）才展开。
  * **`class` 这一档受控。** `.wrapup/mres/*` 与 `.wrapup/mres/*/*` 是「运行目录里的东西都可重建」的
    catch-all，它会把聚合产物（`evalplus.json`、`lmeval_panel.json`、`ident_control.json`、
    `probe-output.txt`）一起吞掉——那几份是被 `evidence:`/`repro:` 点名的事实载体，其中的断言无法从
    随仓库分发的东西重算，所以它们必须入库；能被 catch-all 认领的只有逐题原始样本（`*.jsonl`）与
    codegen 落盘目录。一条精确点名的路径落在**未声明**的 ignore 规则下时，结论是「无处置」。

`.log` 另加一条：登记表里的 9 个文件必须 tracked 且 gunzip 后的字节数与登记值相同——`.gz` 里装的
必须是那一份，不是别的。登记值是文件指纹，不是从别处可算出的数，所以写在这里；条数与字节合计
**只从这张表和盘上文件当场算**，文档引用本命令的输出，不抄数字（抄出来的那个合计曾经三处不同）。

    python3 checks/evidence_logs.py                # exit 0 = 每条都有处置；exit 1 = 有路径没人认领
    python3 checks/evidence_logs.py --root /tmp/x  # 负控用临时 clone，语义完全相同
"""
from __future__ import annotations

import argparse
import glob
import gzip
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

# 已声明的可重建缓存类：**(ignore 规则, 该类允许的路径形状)**。
#   - 规则是 `git check-ignore -v` 印出来的那一条，不是「随便哪条规则命中了」；
#   - 形状只对 `class` 档的精确路径生效（`None` = 该规则下任何形状都算）：`mres/` 的 catch-all 里
#     只有逐题样本与 codegen 落盘目录算「可重建」，聚合产物不算；
#   - 通配（`glob`）一档按规则判：文档用它指「某次运行的一组产物」，粒度到目录/规则级才讲得通。
# README 的 Ships / Does not ship 两栏引用这张表，不另写一份类清单（一处为准）。
REBUILDABLE_CLASSES = (
    ("venv / 评测环境（`bootstrap_venv.sh` 重建）",
     (".wrapup/evalpy/", ".wrapup/msenv/", ".wrapup/wres/", ".wrapup/lmenv/",
      ".wrapup/bfclenv/", ".wrapup/mplenv/", ".wrapup/jars/"),
     None),
    ("mres 逐题原始产物 / codegen 落盘目录（重跑即重生成）",
     (".wrapup/mres/*", ".wrapup/mres/*/*"),
     r"(?:\.jsonl$|/codegen/)"),
    ("ppl_corpora（按上游命令重下）",
     (".wrapup/ppl_corpora/",),
     None),
    ("运行日志与进程戳",
     ("*.log", ".wrapup/*.log", ".wrapup/*.out", ".wrapup/*.pid"),
     None),
    ("DB 备份与 SQLite 旁路文件",
     ("experiments.sqlite.bak*", "*.sqlite-wal", "*.sqlite-shm"),
     None),
    ("可重绘的图与暂存缓冲",
     ("figures/", ".tmp/"),
     None),
)

# 通配符：token **紧跟**这些字符之一时，文档写的是模式，不是一条精确路径。
WILDCARD_LEAD = "*?[{"

# `.wrapup/…` 路径 token（在通配符处截断，模式性由后面的字符判定）。
PATH_RE = re.compile(r"\.wrapup/[A-Za-z0-9._/-]*[A-Za-z0-9_-]")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def tracked(path: str) -> bool:
    return git("ls-files", "--error-unmatch", "--", path).returncode == 0


_TRACKED: list[str] | None = None


def tracked_files() -> list[str]:
    global _TRACKED
    if _TRACKED is None:
        _TRACKED = [p for p in git("ls-files", "-z").stdout.split("\0") if p]
    return _TRACKED


def ignored_rule(path: str) -> str:
    """路径被 .gitignore 判为忽略时返回命中的那条规则，否则返回空串。

    文档里指目录时常不写结尾的 `/`（`.wrapup/lmenv`），而 `.gitignore` 的目录类规则写在 `/` 上，
    所以先按原样问一次、再按「目录形式」问一次。

    `check-ignore -v` 在**否定规则**命中时也退 0 并印出 `!pattern`，所以不能拿它的退出码当
    「被忽略」：`!` 开头的规则是放行，放行不是处置。
    """
    for probe in (path, path + "/"):
        proc = git("check-ignore", "-v", "--", probe)
        if proc.returncode != 0:
            continue
        head = proc.stdout.split("\t", 1)[0]
        parts = head.split(":", 2)
        rule = parts[2] if len(parts) == 3 else ""
        if rule and not rule.startswith("!"):
            return rule
    return ""


DECLARED_RULES = {rule for _, rules, _ in REBUILDABLE_CLASSES for rule in rules}


def ignored_by_declared_rule(path: str) -> bool:
    """通配一档用：命中的规则在已声明的类里即可（不看形状）。"""
    return ignored_rule(path) in DECLARED_RULES


def class_label(path: str) -> str:
    """`class` 这一档：命中的规则必须是已声明的类，且路径形状属于那一类。返回类名或空串。"""
    rule = ignored_rule(path)
    if not rule:
        return ""
    for label, rules, shape in REBUILDABLE_CLASSES:
        if rule in rules and (shape is None or re.search(shape, path)):
            return label
    return ""


def glob_matches_are_declared(pattern: str) -> bool:
    """通配/花括号写法：展开到的每个命中都必须是入库文件、目录，或已声明的类。"""
    hits = glob.glob(os.path.join(REPO, pattern))
    if not hits:
        return False
    for hit in hits:
        rel = os.path.relpath(hit, REPO)
        if tracked(rel) or os.path.isdir(hit) or ignored_by_declared_rule(rel):
            continue
        return False
    return True


def is_prefix_of_tracked(path: str) -> bool:
    """`.wrapup/mres/m165-*_eval.json` 这类前缀由它下面的真实文件指认，不是一条能打开的证据行。"""
    return any(t.startswith(path) for t in tracked_files())


def named_paths() -> list[tuple[str, bool]]:
    """`(token, 是不是通配模式)`。模式性由 token 后面紧跟的字符决定（`*`、`?`、`[`、`{`）。"""
    found: dict[str, bool] = {}
    for doc in glob.glob(os.path.join(REPO, "docs", "subprojects", "*", "RESULT.md")):
        with open(doc, encoding="utf-8") as fh:
            text = fh.read()
        for m in PATH_RE.finditer(text):
            nxt = text[m.end():m.end() + 1]
            found[m.group()] = found.get(m.group(), False) or nxt in WILDCARD_LEAD
    return sorted(found.items())


def disposition(path: str, is_pattern: bool) -> str:
    if tracked(path):
        return "tracked"
    if tracked(path + ".gz"):
        return "gz"
    if is_prefix_of_tracked(path) or os.path.isdir(os.path.join(REPO, path)):
        return "dir"
    if is_pattern and glob_matches_are_declared(path + "*"):
        return "glob"
    if class_label(path):
        return "class"
    return ""


def main(argv: list[str] | None = None) -> int:
    global REPO, _TRACKED
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=REPO, help="仓库根（负控用临时 clone；默认本脚本的上一级）")
    REPO = os.path.abspath(ap.parse_args(argv).root)
    _TRACKED = None

    named = named_paths()
    counts = {"tracked": 0, "gz": 0, "dir": 0, "glob": 0, "class": 0, "": 0}
    failures: list[str] = []
    for path, is_pattern in named:
        kind = disposition(path, is_pattern)
        counts[kind] += 1
        if not kind:
            rule = ignored_rule(path)
            why = f"落在未声明的 ignore 规则 `{rule}` 下" if rule else "不在盘上/未入库/不在任何已声明的类里"
            failures.append(f"FAIL 无处置（{why}）：{path}" + ("*" if is_pattern else ""))

    raw_total = 0
    gz_total = 0
    for path, raw_bytes in sorted(EVIDENCE_LOGS.items()):
        gz_path = os.path.join(REPO, path + ".gz")
        if not tracked(path + ".gz"):
            failures.append(f"FAIL 登记的 .log 未被跟踪：{path}.gz")
            continue
        gz_total += os.path.getsize(gz_path)
        with gzip.open(gz_path, "rb") as fh:
            got = len(fh.read())
        if got != raw_bytes:
            failures.append(f"FAIL {path}.gz 解开是 {got} 字节，登记的是 {raw_bytes} 字节")
        raw_total += raw_bytes

    print(f"点名的 `.wrapup/…` 路径 {len(named)} 条："
          f"入库 {counts['tracked']}、压缩入库 {counts['gz']}、目录/前缀 {counts['dir']}、通配 {counts['glob']}、"
          f"按类忽略 {counts['class']}、无处置 {counts['']}")
    print(f"登记 {len(EVIDENCE_LOGS)} 个 `.log`：原始 {raw_total} 字节 → gzip 后 {gz_total} 字节"
          f"（逐个解开核对，字节数与登记值相同）")
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
