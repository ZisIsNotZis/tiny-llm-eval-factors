#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把各子项目 `PLAN.md` 里的「未解问题」一节抽成一个派生索引，供报告渲染。

子项目的 `PLAN.md` / `RESULT.md` 是工作文档，不是报告内容；报告是给读者看的产物面，所以不去解析
它们的事实格式，只取读者确实需要的那一节：还没解决的问题。这个索引因此是**派生**的——
`make_report.py` 读它，而它由本脚本从 `PLAN.md` 生成，不手工维护。

识别规则（只看标题，不看正文格式）：二级标题（`## `）且标题文字以「未解 / 未决 / 待解 / 开放问题」
或英文 open question 开头。该标题下到**下一个任意级别的标题**之间的列表项是条目；代码围栏内的行
不算标题也不算条目；没有这一节的文件被跳过并计数。

    python3 report_inputs/build_open_questions.py          # 重写 open_questions.json
    python3 report_inputs/build_open_questions.py --check  # 与现有 json 比对

同样的输入永远得到同样的字节：按路径排序，无时间戳。
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "open_questions.json")
SOURCE_GLOB = os.path.join(REPO, "docs", "subprojects", "*", "PLAN.md")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# 只认二级标题（`## `），且标题文字本身必须以这些词开头：`## wp98 :: 未解决的…` 是工作包、
# 不是这一节，`# 未解问题` 是文件标题层级之外的写法，都不算。代码围栏里的 `# …` 一律跳过。
OPEN_RE = re.compile(r"^(未解|未决|待解|开放问题|open\s*questions?)", re.I)
LEVEL2_RE = re.compile(r"^##\s+(?!#)(.*)$")
ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+?)\s*$")


def scan():
    """[(subproject, path, heading, [item, ...])] 与被跳过的文件清单。"""
    sections, skipped = [], []
    for path in sorted(glob.glob(SOURCE_GLOB)):
        sub = os.path.basename(os.path.dirname(path))
        rel = os.path.relpath(path, REPO)
        lines = open(path, encoding="utf-8").read().split("\n")
        heading, items, in_fence = None, [], False
        for line in lines:
            if FENCE_RE.match(line):
                in_fence = not in_fence       # 围栏内的 # 不是标题
                continue
            if in_fence:
                continue
            m = LEVEL2_RE.match(line)
            if m:
                if heading:
                    break                       # 任意级别的下一个标题都终止这一节
                title = m.group(1).strip()
                if OPEN_RE.match(title):
                    heading = title
                continue
            if heading and ANY_HEADING_RE.match(line):
                break                           # `###`/`####` 子标题同样终止（与 docstring 一致）
            if heading:
                it = ITEM_RE.match(line)
                if it:
                    items.append(it.group(1))
        if heading:
            sections.append((sub, rel, heading, items))
        else:
            skipped.append(rel)
    return sections, skipped


def dump(sections, skipped):
    doc = {
        "source": "docs/subprojects/*/PLAN.md",
        "rule": "标题含「未解/未决/待解/开放问题」或 open question；其下的列表项是条目",
        "items": [{"subproject": sub, "path": rel, "heading": heading, "text": text}
                  for sub, rel, heading, items in sections for text in items],
        "sections": [{"subproject": sub, "path": rel, "heading": heading, "count": len(items)}
                     for sub, rel, heading, items in sections],
        "skipped": skipped,
    }
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main(argv):
    sections, skipped = scan()
    text = dump(sections, skipped)
    if "--check" in argv:
        try:
            have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is missing", file=sys.stderr)
            return 1
        if have != text:
            print(f"FAIL: {os.path.relpath(OUT, REPO)} is stale; rerun without --check",
                  file=sys.stderr)
            return 1
        print(f"open_questions.json: up to date ({len(sections)} section(s), "
              f"{sum(len(s[3]) for s in sections)} item(s), {len(skipped)} file(s) skipped)")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}: {len(sections)} section(s), "
          f"{sum(len(s[3]) for s in sections)} item(s), {len(skipped)} file(s) skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
