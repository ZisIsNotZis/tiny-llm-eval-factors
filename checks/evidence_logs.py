#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`docs/subprojects/*/RESULT.md` 点名的每个 `.wrapup/…` 路径，在 clone 里必须有处置（p-entry3）。

判据是**声明**，不是「盘上有没有」：同一个 token 在本机与干净 clone 里得到同一个结论，因为判类只看
`.gitignore` 的规则、`git ls-files` 的索引与 `REBUILDABLE_CLASSES` 那张表，不读 `.wrapup` 里有没有文件。

token 先按形状分三档，各按各的规则判：

    exact    没有通配/花括号：路径本身入库（`tracked`），或其 `.gz` 入库（`gz`），或落在一条已声明
             类的规则下**且形状属于该类**（`class`），或是一个已入库文件的前缀 / 盘上真实目录（`dir`）。
             聚合产物（`evalplus.json`、`lmeval_panel.json`、`ident_control.json`、`probe-output.txt`）
             不在任何类的形状里，所以精确点名它们而没入库 → FAIL：这一档的严格度不许降。
    dir      以 `/` 结尾、或末段没有扩展名（文档指的是目录，如 `.wrapup/mres/i01-floor`、`.wrapup/bfcl_out`）：
             该目录本身（或其内容的代表路径）落在一条**已声明类**的规则下才算有处置。
    pattern  含 `*` / `?` / `[` / `{`（含 `/*.log`、`*.jsonl`、`{a,b}/`）：花括号展开成若干候选，
             每个候选（通配符换成占位符后）落进一条已声明类，或至少命中一个**入库文件**，才算有处置。
             「文档用模式指一群运行期产物」是合法处置，因为它声明的是「这一批运行目录里的产物」，
             而不是某一份必须入库的聚合产物。

两个方向都是踩出来的：

  * **token 不许被截断。** 旧 `PATH_RE` 在通配符/花括号/尾斜杠处截断，于是 `.wrapup/a01_type_probe_*.log`
    被取成 `.wrapup/a01_type_probe_`——正则认不出的形状只好全判「无处置」，干净 clone 里红 13 条。
    现在通配、花括号、尾斜杠都留在 token 里，形状由 token 自己说。
  * **`class` 这一档受控。** `.wrapup/mres/*` 与 `.wrapup/mres/*/*` 是「运行目录里的东西都可重建」的
    catch-all，它会把聚合产物一起吞掉——那几份是被 `evidence:`/`repro:` 点名的事实载体，其中的断言
    无法从随仓库分发的东西重算，所以它们必须入库；能被 catch-all 的**形状**认领的只有逐题原始样本
    （`*.jsonl`）、codegen / props 落盘目录、运行目录本身、per-run 结果文件（`*_eval.json`、
    `lmeval_<task>_<ts>.json`、`spec_panel.json` / `variant_panel.json` / `histograms.jsonl` / `cmd.txt`）。
    一条精确点名的路径落在**未声明**的 ignore 规则下时，结论是「无处置」。

`.log` 另加一条：登记表里的 9 个文件必须 tracked 且 gunzip 后的字节数与登记值相同——`.gz` 里装的
必须是那一份，不是别的。登记值是文件指纹，不是从别处可算出的数，所以写在这里；条数与字节合计
**只从这张表和盘上文件当场算**，文档引用本命令的输出，不抄数字（抄出来的那个合计曾经三处不同）。

    python3 checks/evidence_logs.py                # exit 0 = 每条都有处置；exit 1 = 有路径没人认领
    python3 checks/evidence_logs.py --root /tmp/x  # 负控用临时 clone，语义完全相同
"""
from __future__ import annotations

import argparse
import fnmatch
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

# 已声明的可重建缓存类：**(类名, 规则, 该类允许的路径形状)**，三件各自写清。
#   - 规则是 `git check-ignore -v` 印出来的那一条，不是「随便哪条规则命中了」；
#   - 形状只对 `exact` 档的精确路径生效（`None` = 该规则下任何形状都算）：`mres/` 的 catch-all 里
#     只有下面列出的形状算「可重建」，四份聚合产物不在其中——它们必须入库；
#   - `pattern` 与 `dir` 两档按**规则**判（形状换成代表路径后再问一次规则），因为模式指的是「一批」。
# README 的 Ships / Does not ship 两栏引用这张表，不另写一份类清单（一处为准）。
_MRES_RULES = (".wrapup/mres/*", ".wrapup/mres/*/*")
REBUILDABLE_CLASSES = (
    ("venv / 评测环境（`bootstrap_venv.sh` 重建）",
     (".wrapup/evalpy/", ".wrapup/msenv/", ".wrapup/wres/", ".wrapup/lmenv/",
      ".wrapup/bfclenv/", ".wrapup/mplenv/", ".wrapup/jars/"),
     None),
    ("wrapup 顶层运行目录（`.wrapup/*/`：运行期产物，重跑即重生成）",
     (".wrapup/*/",),
     None),
    ("mres 逐题原始产物 / codegen 落盘目录（重跑即重生成）",
     _MRES_RULES,
     r"(?:\.jsonl$|/codegen/)"),
    ("mres 运行目录本身（运行期产物，重跑即重生成）",
     _MRES_RULES,
     r"(?:^|/)[^./]+$"),
    ("props 目录（服务端 `/props` 回读，重跑即重取）",
     _MRES_RULES,
     r"/props(?:/|$)"),
    ("per-run 结果文件（数字的载体是 `experiments.sqlite` 与入库的 panel 聚合，per-run 文件不入库）",
     _MRES_RULES,
     r"(?:/lmeval_(?!panel\.json$).+\.json$|_eval\.json$"
     r"|/(?:spec_panel|variant_panel)\.json$|/histograms\.jsonl$|/cmd\.txt$)"),
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

# 形状里带通配符的 token：文档写的是模式，不是一条精确路径。
WILDCARD_CHARS = "*?[{"

# `.wrapup/…` 路径 token。通配符、花括号组、尾斜杠都**留在 token 里**（旧版在通配符处截断，把
# `.wrapup/a01_type_probe_*.log` 取成 `.wrapup/a01_type_probe_`，正则认不出这个形状）。花括号组整体
# 是一个单元：`{gsm8k-r*,gsm8k-noReasoning-flag-r*,bfcl-r*}` 连同内部的逗号与通配一起取。
PATH_RE = re.compile(r"\.wrapup/(?:[A-Za-z0-9._/\[\]*?-]|\{[^{}\s`]*\})+")


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


def declared_rule(rule: str) -> bool:
    return bool(rule) and rule in DECLARED_RULES


def class_label(path: str) -> str:
    """`exact` 这一档：命中的规则必须是已声明的类，且路径形状属于那一类。返回类名或空串。"""
    rule = ignored_rule(path)
    if not rule:
        return ""
    for label, rules, shape in REBUILDABLE_CLASSES:
        if rule in rules and (shape is None or re.search(shape, path)):
            return label
    return ""


def is_prefix_of_tracked(path: str) -> bool:
    """`.wrapup/res`、`.wrapup/mres/i01-slot-np1-` 这类前缀由它下面的真实文件指认，不是一条能
    打开的证据行（例如 shell 循环里的 `$f` 或目录名）。"""
    return any(t.startswith(path) for t in tracked_files())


def named_paths() -> list[str]:
    """文档里出现的 `.wrapup/…` token（去重、排序；通配/花括号/尾斜杠原样保留）。"""
    found: set[str] = set()
    for doc in sorted(_result_docs()):
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


def pattern_disposition(token: str) -> str:
    """`pattern` 一档：每个花括号候选都要有处置，否则整条无处置。"""
    for alt in expand_braces(token):
        rep = representative(alt)
        if tracked(rep) or declared_rule(ignored_rule(rep)):
            continue
        if any(fnmatch.fnmatchcase(t, alt) for t in tracked_files()):
            continue
        if is_prefix_of_tracked(rep):
            continue
        return ""
    return "pattern"


def dir_disposition(path: str) -> str:
    """`dir` 一档：目录本身、或它的内容（代表路径）落在一条已声明类的规则下。"""
    p = path.rstrip("/")
    if declared_rule(ignored_rule(p)):
        return "dir"
    if is_prefix_of_tracked(p) or os.path.isdir(os.path.join(REPO, p)):
        return "dir"
    # 目录本身常被 `!.wrapup/mres/*/` 放行（好让里面的文件被单独放行/忽略），规则问不出来；
    # 那就问它的内容归哪条规则管——运行目录里的内容落在已声明类里，这个目录就是可重建的运行目录。
    for probe in (p + "/__probe__.jsonl", p + "/__probe__"):
        if declared_rule(ignored_rule(probe)):
            return "dir"
    return ""


def disposition(token: str, shape: str) -> str:
    if tracked(token):
        return "tracked"
    if tracked(token + ".gz"):
        return "gz"
    if shape == "pattern":
        return pattern_disposition(token)
    if shape == "dir":
        return dir_disposition(token)
    label = class_label(token)
    if label:
        return "class"
    if is_prefix_of_tracked(token) or os.path.isdir(os.path.join(REPO, token)):
        return "dir"
    return ""


def main(argv: list[str] | None = None) -> int:
    global REPO, _TRACKED
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=REPO, help="仓库根（负控用临时 clone；默认本脚本的上一级）")
    REPO = os.path.abspath(ap.parse_args(argv).root)
    _TRACKED = None

    named = named_paths()
    counts = {"tracked": 0, "gz": 0, "dir": 0, "pattern": 0, "class": 0, "": 0}
    failures: list[str] = []
    for token in named:
        kind = disposition(token, shape_of(token))
        counts[kind] += 1
        if not kind:
            rule = ignored_rule(token)
            why = f"落在未声明的 ignore 规则 `{rule}` 下" if rule else "不在盘上/未入库/不在任何已声明的类里"
            failures.append(f"FAIL 无处置（{why}）：{token}")

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
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
