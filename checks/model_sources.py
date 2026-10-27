#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告附录的「模型来源」列必须由随仓库分发的索引决定，不是现场解析本机目录（res77 的守卫）。

缺陷是什么（`docs/subprojects/i02-测量基础设施/RESULT.md::res77`）：`make_report.py` 过去在采集机上把
`/home/z/hf/<basename>.gguf`（`exp.py` 实际加载的入口，指向 mscache 目录或 HF 缓存快照的符号链接）
现场 `realpath`，反推机构 / 仓库 / 相对路径。换机后该目录不存在，来源列静默退化成
「未知（本地文件，未找到下载来源）」/「—」，从库重建的报告于是与仓库里那份不同字节。

这个脚本观察两件事，都以退出码说话：

  1. **索引本身**：`report_inputs/model_sources.json` 结构合法、`file` 唯一、按 `file` 排序
     （排序是确定性要求：同一份内容只有一种写法，diff 才只看真正的改动）。
  2. **印出来的值**：`report.html` 附录里每一行模型都有条目，且「量化发布方 / GGUF 仓库 /
     加载路径」三列与索引逐字相同；渲染到的模型还必须在库（`experiments.sqlite`）里存在，
     报告不许凭空造模型；正文里不许再出现老缺陷留下的「未知（本地文件，未找到下载来源）」。

    python3 checks/model_sources.py
    exit 0 = 一致；exit 1 = 不一致（逐条点名）；exit 2 = report.html 不在场（不可得，不冒充绿）

空扫描判 FAIL：一条模型行都没解析到，说明解析假设坏了，那不是「全都对」。
"""
from __future__ import annotations

import html
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SOURCES_JSON = os.path.join(REPO, "report_inputs", "model_sources.json")
REPORT = os.path.join(REPO, "report.html")
DB = os.path.join(REPO, "experiments.sqlite")
FIELDS = ("file", "vendor", "repo", "path")
# 老缺陷的证据串：索引在场时它一个都不许出现。
LEGACY_UNKNOWN = "未知（本地文件，未找到下载来源）"

# 附录每行：<code>file</code> … 量化发布方 / GGUF 仓库 / 加载路径（最后三列）
ROW = re.compile(
    r"<tr><td><code>([^<]+\.gguf)</code></td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td>"
    r"<td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td class='nr'>(.*?)</td></tr>",
    re.S)
REPRO_BLOCK = re.compile(r"<div class='repro'>.*?</table></div></div>", re.S)


def load_sources() -> dict:
    """读索引并做结构/确定性检查；问题写进返回的 errors 列表。"""
    if not os.path.exists(SOURCES_JSON):
        raise SystemExit(f"FAIL 模型来源索引缺失：{os.path.relpath(SOURCES_JSON, REPO)}\n"
                         f"  这份索引随仓库分发，是附录「模型来源」列的唯一来源。")
    with open(SOURCES_JSON, encoding="utf-8") as fh:
        try:
            doc = json.load(fh)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"FAIL 模型来源索引不是合法 JSON：{os.path.relpath(SOURCES_JSON, REPO)}：{exc}")
    entries = doc.get("sources") if isinstance(doc, dict) else None
    if not isinstance(entries, list) or not entries:
        raise SystemExit(f"FAIL 模型来源索引里没有非空的 sources 列表：{os.path.relpath(SOURCES_JSON, REPO)}")
    out, errors = {}, []
    for i, ent in enumerate(entries, 1):
        if not isinstance(ent, dict) or any(k not in ent for k in FIELDS):
            errors.append(f"第 {i} 条缺字段（要 {', '.join(FIELDS)}）：{ent!r}")
            continue
        name = ent["file"]
        if not isinstance(name, str) or not name.endswith(".gguf"):
            errors.append(f"第 {i} 条的 file 不是 .gguf 文件名：{name!r}")
            continue
        if not isinstance(ent["vendor"], str) or not ent["vendor"]:
            errors.append(f"{name}：vendor 为空")
        if ent["repo"] is not None and not isinstance(ent["repo"], str):
            errors.append(f"{name}：repo 只能是字符串或 null")
        if ent["path"] is None:
            # 本地自建臂没有下载来源，也没有可记录的加载入口；只允许这一类用 null。
            if ent["repo"] is not None or not str(ent["vendor"]).startswith("本地自建"):
                errors.append(f"{name}：path=null 只允许用于本地自建臂（且 repo 必须为 null）")
        elif not isinstance(ent["path"], str) or not ent["path"]:
            errors.append(f"{name}：path 为空")
        if name in out:
            errors.append(f"{name}：重复条目")
        out[name] = ent
    order = [ent.get("file") for ent in entries if isinstance(ent, dict)]
    if order != sorted(order):
        first = next((a for a, b in zip(order, sorted(order)) if a != b), "")
        errors.append(f"sources 不是按 file 排序（确定性要求）：第一条失序的是 {first!r}")
    return out, errors


def report_rows() -> list:
    """report.html 附录里的每一行 → (file, vendor, repo, path)。"""
    with open(REPORT, encoding="utf-8") as fh:
        text = fh.read()
    rows = []
    for block in REPRO_BLOCK.findall(text):
        for m in ROW.finditer(block):
            g = [html.unescape(x) for x in m.groups()]
            rows.append((g[0], g[6], g[7], g[8]))
    return rows, text


def db_models() -> set:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return {r[0] for r in con.execute("SELECT DISTINCT model FROM experiments")}


def main() -> int:
    sources, errors = load_sources()
    if not os.path.exists(REPORT):
        print(f"BLOCKED report.html 不在场，无从核对来源列：{os.path.relpath(REPORT, REPO)}")
        return 2

    rows, text = report_rows()
    if not rows:
        print("FAIL 报告附录里一条模型行都没解析到（空扫描不算通过）")
        return 1

    seen = {}
    for name, vendor, repo, path in rows:
        if name in seen and seen[name] != (vendor, repo, path):
            errors.append(f"{name}：同一份报告里印出了两组来源：{seen[name]} vs {(vendor, repo, path)}")
        seen[name] = (vendor, repo, path)

    missing = sorted(n for n in seen if n not in sources)
    for name in missing:
        errors.append(f"{name}：在报告里被印出，但 {os.path.relpath(SOURCES_JSON, REPO)} 里没有它的条目")
    stale = sorted(n for n in sources if n not in seen)
    for name in sorted(set(seen) & set(sources)):
        want = (sources[name]["vendor"], sources[name]["repo"] or "—", sources[name]["path"] or "—")
        if seen[name] != want:
            errors.append(f"{name}：报告印的是 {seen[name]}，索引写的是 {want}（改过索引就要重建报告）")
    if LEGACY_UNKNOWN in text:
        errors.append(f"报告里仍有老缺陷留下的「{LEGACY_UNKNOWN}」——来源列退回现场解析了")

    known = db_models()
    invented = sorted(n for n in seen if n not in known)
    for name in invented:
        errors.append(f"{name}：报告里印出了库内不存在的模型（报告不许凭空造模型）")

    print(f"索引 {len(sources)} 条；报告附录 {len(rows)} 行 / {len(seen)} 个模型；"
          f"未使用的条目 {len(stale)} 条" + (f"（{', '.join(stale[:3])}…）" if len(stale) > 3 else
                                            (f"（{', '.join(stale)}）" if stale else "")))
    if errors:
        for e in errors:
            print(f"  - {e}")
        print(f"FAIL 来源列与索引不一致：{len(errors)} 处")
        return 1
    print("PASS 每个被印出的模型都有条目，三列与索引逐字相同，且渲染集是库内模型集的子集")
    return 0


if __name__ == "__main__":
    sys.exit(main())
