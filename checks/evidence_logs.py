#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`docs/subprojects/*/RESULT.md` 点名的每个 `.wrapup/…` 路径，必须有处置（p-entry3）。

两端（本机 / 干净 clone）的判据不同，脚本按**盘上有没有未入库的 run 文件**分开报：

  * 本机（`.wrapup` 里有未入库的运行产物）才是「逐条核到文件」的那一端：`dir` 一档会走进去，看见
    一个目录里**只有**未入库、又不在任何已声明形状类里的东西（如一份没入库的 `evalplus.json`）就判
    「无处置」并点名它。`pattern` 一档把花括号展开成具体候选，指名一个文件的候选按 `exact` 档同一张
    形状表判，而不是「命中的 ignore 规则已声明」就放过。
  * 干净 clone 里只有入库文件，盘上扫不到任何未入库的 run 文件：`pattern` / `dir` / `exact` 只能按
    **声明 + 索引**判，看不到那些「被点名却没入库」的产物。此时脚本在结论行打出「本次 N 条只能按
    声明判」，并以 **exit 2（不可得）** 退出——不可得不是通过（门 5）。`reproduce.sh` 把它记成
    BLOCKED，不计入 PASS。

token 先按形状分三档，各按各的规则判：

    exact    没有通配/花括号：路径本身入库（`tracked`），或其 `.gz` 入库（`gz`），或落在一条已声明
             类的规则下**且形状属于该类**（`class`），或是一个已入库文件的前缀 / 盘上真实目录（`dir`）。
             聚合产物（`evalplus.json`、`lmeval_panel.json`、`ident_control.json`、`probe-output.txt`）
             不在任何类的形状里，所以精确点名它们而没入库 → FAIL：这一档的严格度不许降。
    pattern  含 `*` / `?` / `[` / `{`。花括号一律展开成若干候选（没有单选项例外），每个候选都要
             有处置：入库、有入库文件命中这个模式、是前缀、或（候选指的是目录时）落在一条已声明规则
             下。候选**指名一个文件**时，落在已声明规则下还不够——它必须同时通过那张形状表，否则就是
             「同一个未入库文件，写成 exact 红、写成模式绿」的那个洞。
    dir      以 `/` 结尾、或末段没有扩展名（文档指的是目录，如 `.wrapup/mres/i01-floor`、`.wrapup/bfcl_out`）。
             判据是「目录里**有**入库证据，或该目录本身是已声明的可重建运行目录」：盘上是**目录**时走进
             它，见到入库 / 压缩入库 / 按类可重建的文件就算有处置；整目录一份这样的文件都没有时判「无处置」
             并点名第一份文件。**目录 token 不保证目录内每一份文件入库**——某个目录里哪些文件是「本地产物、
             不入库」，要在使用点写明（`a01-量化位宽/RESULT.md` 的 `lmeval_panel.json` 那条就是样板）；
             盘上是**文件**（没有扩展名）时按 `exact` 档的形状表判，不得因为形状是 `None` 就放过。目录
             不在场时只按声明判。顶层 `.wrapup/<x>/` 是「运行目录」这一类，只对目录本身成立，走进去时
             目录里的聚合产物照样过形状表（`bfcl_out` 这类空目录不受影响）。

两个方向都是踩出来的：

  * **token 不许被截断。** 旧 `PATH_RE` 在通配符/花括号/尾斜杠处截断，于是 `.wrapup/a01_type_probe_*.log`
    被取成 `.wrapup/a01_type_probe_`——正则认不出的形状只好全判「无处置」，干净 clone 里红 13 条。
    现在通配、花括号、尾斜杠都留在 token 里，形状由 token 自己说。
  * **`class` 这一档受控。** `.wrapup/mres/*` 与 `.wrapup/mres/*/*` 是「运行目录里的东西都可重建」的
     catch-all，它会把聚合产物一起吞掉——那几份是被 `evidence:`/`repro:` 点名的事实载体，其中的断言
    无法从随仓库分发的东西重算，所以它们必须入库；能被 catch-all 的**形状**认领的只有逐题原始样本
    （`*.jsonl`）、codegen / props 落盘目录、per-run 结果文件（`lmeval_<task>_<ts>.json`、
    `spec_panel.json` / `histograms.jsonl` / `cmd.txt`）。
    一条精确点名的路径落在**未声明**的 ignore 规则下时，结论是「无处置」。
  * **`.wrapup/*/` 只对目录本身算类。** 它是「顶层运行目录」这一类的规则，不是一个「里面放什么都行」
    的文件豁免：`exact` 档对一个文件不再用它判类（否则 `.wrapup/aggdir/agg.json` 会因整目录放行变绿）。

**`*_eval.json` 与 `*_panel.json` 不在这张表里**，即使它们被 ignore 规则命中：README 的 Ships 一栏
说逐题评测产物入库（`.gitignore` 也逐类放行），所以一个被点名却没入库的 `*_eval.json` 是**缺证据**，
不是「可重建缓存」。把它放进这张表等于让「本该入库的东西没入库」在检查里变绿。

`.log` 另加一条：登记表里的 9 个文件必须 tracked 且 gunzip 后的字节数与登记值相同——`.gz` 里装的
必须是那一份，不是别的。登记值是文件指纹，不是从别处可算出的数，所以写在这里；条数与字节合计
**只从这张表和盘上文件当场算**，文档引用本命令的输出，不抄数字（抄出来的那个合计曾经三处不同）。

    python3 checks/evidence_logs.py                # exit 0 = 每条都有处置；exit 1 = 有路径没人认领；
                                                   # exit 2 = 看不到 .wrapup，只能按声明判（不可得）
    python3 checks/evidence_logs.py --root /tmp/x  # 负控用临时 clone，语义完全相同
"""
from __future__ import annotations

import argparse
import fnmatch
import glob
import gzip
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 遍历盘上目录时见到过多少个未入库的 run 文件：为 0 说明这是干净 clone（只有入库文件），
# pattern / dir 两档没法用盘上文件核，只能按声明判 → 不可得。
_DISK_UNTRACKED = 0

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

# 「这个类只对目录本身成立」：`exact` 档对一个文件不拿它判类，`dir` 档照样可用。
# `.wrapup/*/` 是顶层运行目录这一类，不是一个「目录里放什么都算可重建」的文件豁免。
DIR_ONLY = "<dir-only>"

# 已声明的可重建缓存类：**(类名, 规则, 该类允许的路径形状)**，三件各自写清。
#   - 规则是 `git check-ignore -v` 印出来的那一条，不是「随便哪条规则命中了」；
#   - 形状只对 `exact` 档的精确路径生效（`None` = 该规则下任何形状都算）；`DIR_ONLY` = 只对目录成立；
#   - `pattern` 一档对「指名一个文件」的候选也用这张形状表，对「指的是目录」的候选按规则判。
# README 的 Ships / Does not ship 两栏引用这张表，不另写一份类清单（一处为准）。
_MRES_RULES = (".wrapup/mres/*", ".wrapup/mres/*/*")
REBUILDABLE_CLASSES = (
    ("venv / 评测环境（`bootstrap_venv.sh` 重建）",
     (".wrapup/evalpy/", ".wrapup/msenv/", ".wrapup/wres/", ".wrapup/lmenv/",
      ".wrapup/bfclenv/", ".wrapup/mplenv/", ".wrapup/jars/"),
     None),
    ("wrapup 顶层运行目录（`.wrapup/*/`：运行期产物，重跑即重生成）",
     (".wrapup/*/",),
     DIR_ONLY),
    ("mres 逐题原始产物 / codegen 落盘目录（重跑即重生成）",
     _MRES_RULES,
     r"(?:\.jsonl$|/codegen/)"),
    ("props 目录（服务端 `/props` 回读，重跑即重取）",
     _MRES_RULES,
     r"/props(?:/|$)"),
    ("per-run 结果文件（数字的载体是 `experiments.sqlite` 与入库的 panel 聚合，per-run 文件不入库）",
     _MRES_RULES,
     r"(?:/lmeval_(?!panel\.json$).+\.json$|/spec_panel\.json$"
     r"|/histograms\.jsonl$|/cmd\.txt$)"),
    ("ppl_corpora（按上游命令重下）",
     (".wrapup/ppl_corpora/",),
     None),
    ("运行日志、进程戳与显存采样旁路文件",
     ("*.log", ".wrapup/*.log", ".wrapup/*.out", ".wrapup/*.pid", "*.mem"),
     None),
    ("DB 备份与 SQLite 旁路文件",
     ("experiments.sqlite.bak*", "*.sqlite-wal", "*.sqlite-shm"),
     None),
    ("可重绘的图与暂存缓冲",
     ("figures/", ".tmp/"),
     None),
)

# 形状里带通配符的 token：文档写的是模式，不是一条精确路径。
WILDCARD_CHARS = "*?[{"

# `.wrapup/…` 路径 token。通配符、花括号组、尾斜杠都**留在 token 里**（旧版在通配符处截断，把
# `.wrapup/a01_type_probe_*.log` 取成 `.wrapup/a01_type_probe_`，正则认不出这个形状）。花括号组整体
# 是一个单元：`{gsm8k-r*,gsm8k-noReasoning-flag-r*,bfcl-r*}` 连同内部的逗号与通配一起取。
PATH_RE = re.compile(r"\.wrapup/(?:[A-Za-z0-9._/\[\]*?-]|\{[^{}\s`]*\})+")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def tracked(path: str) -> bool:
    return path in tracked_set()


_TRACKED: set[str] | None = None


def tracked_set() -> set[str]:
    global _TRACKED
    if _TRACKED is None:
        _TRACKED = {p for p in git("ls-files", "-z").stdout.split("\0") if p}
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


def declared_rule(rule: str) -> bool:
    return bool(rule) and rule in DECLARED_RULES


def class_label(path: str) -> str:
    """`exact` 这一档：命中的规则必须是已声明的类，且路径形状属于那一类。返回类名或空串。"""
    rule = ignored_rule(path)
    if not rule:
        return ""
    for label, rules, shape in REBUILDABLE_CLASSES:
        if rule not in rules:
            continue
        if shape is DIR_ONLY:
            continue  # 目录类不豁免文件（`.wrapup/aggdir/agg.json` 不该因 `.wrapup/*/` 变绿）
        if shape is None or re.search(shape, path):
            return label
    return ""


def class_of_concrete(path: str) -> str:
    """盘上实体文件的静态归类（不调 git，遍历目录内容时用）：路径命中某类的规则模式且形状相符。"""
    for label, rules, shape in REBUILDABLE_CLASSES:
        if shape is DIR_ONLY:
            continue
        for rule in rules:
            if fnmatch.fnmatchcase(path, rule) or fnmatch.fnmatchcase(path, rule.rstrip("/")):
                if shape is None or re.search(shape, path):
                    return label
    return ""


def is_prefix_of_tracked(path: str) -> bool:
    """`.wrapup/res`、`.wrapup/mres/i01-slot-np1-` 这类前缀由它下面的真实文件指认，不是一条能
    打开的证据行（例如 shell 循环里的 `$f` 或目录名）。"""
    return any(t.startswith(path) for t in tracked_set())


def named_paths() -> list[str]:
    """文档里出现的 `.wrapup/…` token（去重、排序；通配/花括号/尾斜杠原样保留）。"""
    found: set[str] = set()
    for doc in _result_docs():
        with open(doc, encoding="utf-8") as fh:
            found.update(m.group() for m in PATH_RE.finditer(fh.read()))
    return sorted(found)


def _result_docs() -> list[str]:
    root = os.path.join(REPO, "docs", "subprojects")
    out: list[str] = []
    for name in sorted(os.listdir(root)):
        doc = os.path.join(root, name, "RESULT.md")
        if os.path.isfile(doc):
            out.append(doc)
    return out


def shape_of(token: str) -> str:
    """token 的形状：pattern / dir / exact。"""
    if any(c in token for c in WILDCARD_CHARS):
        return "pattern"
    base = token.rstrip("/").rsplit("/", 1)[-1]
    if token.endswith("/") or "." not in base:
        return "dir"
    return "exact"


def _whole_dir_class(rule: str) -> bool:
    """命中的规则是否是「整目录可重建」类：该类的形状是 `None` 且规则以 `/` 结尾（venv、ppl_corpora、
    figures 等）。`.wrapup/*/` 是 DIR_ONLY（只对目录本身成立），里面仍要按形状表判，所以不算。"""
    for _label, rules, shape in REBUILDABLE_CLASSES:
        if rule in rules:
            return shape is None and rule.endswith("/")
    return False


def expand_braces(pattern: str) -> list[str]:
    """展开 `{a,b}`、`{1..7}` 与 `{a,b}{c,d}`；花括号里可以再带通配符。"""
    start = pattern.find("{")
    if start < 0:
        return [pattern]
    depth = 0
    for i in range(start, len(pattern)):
        if pattern[i] == "{":
            depth += 1
        elif pattern[i] == "}":
            depth -= 1
            if depth == 0:
                inner = pattern[start + 1:i]
                tail = expand_braces(pattern[i + 1:])
                body = pattern[:start]
                if re.fullmatch(r"-?\d+\.\.-?\d+", inner):
                    lo, hi = (int(x) for x in inner.split(".."))
                    alts = [str(n) for n in range(lo, hi + 1)]
                else:
                    alts = _split_braces(inner)
                out: list[str] = []
                for alt in alts:
                    for rest in tail:
                        out.extend(expand_braces(body + alt + rest))
                return out
    return [pattern]  # 未闭合：当字面量


def _split_braces(inner: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in inner:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def representative(alt: str) -> str:
    """把候选里的通配符换成占位符，得到一个能问 `.gitignore` 的代表路径。"""
    alt = re.sub(r"\[[^\]]*\]", "x", alt)
    alt = alt.replace("**", "x").replace("*", "x").replace("?", "x")
    return alt.rstrip("/")


def _designates_dir(alt: str, rep: str) -> bool:
    """这个候选指的是目录（尾斜杠，或末段没有扩展名）。"""
    return alt.rstrip("/") != alt or "." not in rep.rsplit("/", 1)[-1]


def pattern_disposition(token: str) -> tuple[str, str]:
    """`pattern` 一档：每个花括号候选都要有处置，否则整条无处置。

    候选指名一个文件时，光「命中的 ignore 规则已声明」不算处置——还要过那张形状表，否则同一个未入库
    文件写成 exact 会红、写成模式就绿。候选指的是目录时按声明判（模式指的是一批运行目录）。
    """
    for alt in expand_braces(token):
        rep = representative(alt)
        if tracked(rep) or tracked(rep + ".gz"):
            continue
        if any(fnmatch.fnmatchcase(t, alt) for t in tracked_set()):
            continue
        if is_prefix_of_tracked(rep):
            continue
        rule = ignored_rule(rep)
        if _designates_dir(alt, rep) and declared_rule(rule):
            continue
        if not _designates_dir(alt, rep) and class_label(rep):
            continue
        # 点名盘上真正命中的文件（若有），否则点名代表路径。
        disk = sorted(os.path.relpath(p, REPO) for p in glob.glob(os.path.join(REPO, alt)))
        return "", (disk[0] if disk else rep)
    return "pattern", ""


def dir_disposition(path: str) -> tuple[str, str]:
    """`dir` 一档：返回 (kind, 点名的具体文件 or "")。

    盘上是目录时走进它：只有未入库、又不在任何已声明形状类里的文件才算「无处置」，并点名该文件。
    盘上是文件（没有扩展名）时按 exact 的形状表判。目录不在场时只按声明判（干净 clone）。
    """
    global _DISK_UNTRACKED
    p = path.rstrip("/")
    abs_p = os.path.join(REPO, p)
    if os.path.isfile(abs_p):
        if not tracked(p):
            _DISK_UNTRACKED += 1
        label = class_label(p)  # `class_label` 跳过 DIR_ONLY，无扩展名文件不会因 `None` 被放过
        if label:
            return "class", ""
        return "", p
    if os.path.isdir(abs_p):
        # 目录本身就是一条**整目录**类（venv、ppl_corpora 等：规则以 `/` 结尾，且该类的形状是 `None`）
        # → 直接算有处置。`.wrapup/*/` 只是「顶层运行目录」这一类（DIR_ONLY）：目录本身可重建，目录里
        # 的聚合产物仍要过形状表，所以照走。`.wrapup/mres/*` 这种 catch-all 不算，也要走进目录。
        rule = ignored_rule(p)
        if declared_rule(rule) and _whole_dir_class(rule):
            return "dir", ""
        # `.wrapup` 与 `.wrapup/mres` 只是容器，不对它们做内容判定（它们不是「一个运行目录」）。
        if p in (".wrapup", ".wrapup/mres"):
            return "dir", ""
        # 走进目录：只要里面**有**一份入库/压缩入库/按类可重建的文件，这个运行目录就有处置；
        # 反过来，一个目录里只有未入库、又不在任何已声明形状类里的东西（如一份没入库的
        # `evalplus.json`），整个目录就是一条死引用，点名那份文件。DONE / .timings 这类残留物与
        # 面板/日志同在时不算罪证（它们是运行目录的附着物，不是被点名的聚合产物）。
        has_evidence = False
        bad = ""
        for root, _dirs, files in os.walk(abs_p):
            for name in files:
                rel = os.path.relpath(os.path.join(root, name), REPO)
                if tracked(rel) or tracked(rel + ".gz"):
                    has_evidence = True
                    continue
                _DISK_UNTRACKED += 1
                if class_of_concrete(rel):
                    has_evidence = True
                elif not bad:
                    bad = rel
        if has_evidence or not bad:
            return "dir", ""
        return "", bad
    # 盘上没有这个目录：只能按声明/前缀判（干净 clone 或已被删掉的运行目录）。
    if declared_rule(ignored_rule(p)) or is_prefix_of_tracked(p):
        return "dir", ""
    for probe in (p + "/__probe__.jsonl", p + "/__probe__"):
        if declared_rule(ignored_rule(probe)):
            return "dir", ""
    return "", p


def disposition(token: str) -> tuple[str, str]:
    if tracked(token):
        return "tracked", ""
    if tracked(token + ".gz"):
        return "gz", ""
    shape = shape_of(token)
    if shape == "pattern":
        return pattern_disposition(token)
    if shape == "dir":
        return dir_disposition(token)
    label = class_label(token)
    if label:
        return "class", ""
    if is_prefix_of_tracked(token) or os.path.isdir(os.path.join(REPO, token)):
        return "dir", ""
    return "", token


def main(argv: list[str] | None = None) -> int:
    global REPO, _TRACKED, _DISK_UNTRACKED
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=REPO, help="仓库根（负控用临时 clone；默认本脚本的上一级）")
    REPO = os.path.abspath(ap.parse_args(argv).root)
    _TRACKED = None
    _DISK_UNTRACKED = 0

    docs_root = os.path.join(REPO, "docs", "subprojects")
    if not os.path.isdir(docs_root):
        print(f"BLOCKED: 找不到 {docs_root}（空扫描不是通过）")
        return 2
    named = named_paths()
    if not named:
        # 只有这条守卫会打这一行；负控第 9 例断言的是它，而不是「exit 2」（末尾还有别的守卫也给 2）。
        print("BLOCKED 空扫描：docs/subprojects 的 RESULT.md 里没有扫到任何 `.wrapup/…` token")
        return 2

    counts = {"tracked": 0, "gz": 0, "dir": 0, "pattern": 0, "class": 0, "": 0}
    failures: list[str] = []
    for token in named:
        kind, bad = disposition(token)
        counts[kind] += 1
        if not kind:
            rule = ignored_rule(token)
            why = f"落在未声明的 ignore 规则 `{rule}` 下" if rule else "不在盘上/未入库/不在任何已声明的类里"
            named_bad = bad or token
            if named_bad != token:
                why += "；命中的具体文件"
            failures.append(f"FAIL 无处置（{why}）：{named_bad}")

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
          f"入库 {counts['tracked']}、压缩入库 {counts['gz']}、目录 {counts['dir']}、"
          f"模式 {counts['pattern']}、按类忽略 {counts['class']}、无处置 {counts['']}")
    print(f"登记 {len(EVIDENCE_LOGS)} 个 `.log`：原始 {raw_total} 字节 → gzip 后 {gz_total} 字节"
          f"（逐个解开核对，字节数与登记值相同）")
    for line in failures:
        print(line)
    if failures:
        return 1
    if _DISK_UNTRACKED == 0:
        # 盘上一个未入库的 run 文件都没扫到（干净 clone）：上面每一档都只能按声明/索引判——不可得，不是
        # 通过。本机才是逐条核到文件的那一端。
        print(f"BLOCKED: 本次 {len(named)} 条只能按声明/索引判，无法用盘上文件核"
              f"（盘上扫不到未入库的 run 文件）")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
