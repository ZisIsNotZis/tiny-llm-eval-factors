#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a10：五个面板的启动命令是否只在 `-m` 的模型路径上不同。

为什么这一步是本层的前置条件：五个文件的分数跨两次会话、跨三个上传者采集，若命令行里
还有别的差（`--limit`、`-c`、`-np`、shim 版本、采样参数），那么 `position.py` 的每一列差
里就混了协议差，整套位置判断作废。库里的 `protocol` 串只覆盖其中一部分，`cmd.txt` 是那份记录。

`cmd.txt` 在 `.wrapup/mres/<run_tag>/`，**不入库**（`.gitignore` 把 `mres/*` 排除）。所以本检查
在干净 clone 里看不到输入：这时它必须退出 2（不可得），而不是 0（通过）。

退出码：0 = 只在模型路径上不同；1 = 还有别的差（打印）；2 = 看不到输入。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import panel

TAGS = ["m91-qwen38-27b-q2kxl", "m100-qwen38-27b-q3kxl", "m152-qwen38-27b-iq4xs",
        "m150-qwen38-gsqrco-iq3xxs", "m151-qwen38-gsqrco-iq3s"]
ARGS = r"(-c \d+) (-np \d+) (-ngl \d+)( --jinja)?"


def norm(text, tag):
    """把与本检查无关的两样东西抹掉：run_tag 目录名、`-m` 后面的模型路径。"""
    text = text.replace(tag, "<run>")
    return re.sub(r"(-m )\S+", r"\1<model>", text)


def main():
    base = panel.REPO / ".wrapup" / "mres"
    missing = [t for t in TAGS if not (base / t / "cmd.txt").is_file()]
    if missing:
        print(f"看不到输入：缺 {len(missing)} 个 cmd.txt（{missing[:2]}…）；"
              "这是「不可得」，退出 2", file=sys.stderr)
        return 2
    texts = {t: norm((base / t / "cmd.txt").read_text(encoding="utf-8", errors="replace"), t)
             for t in TAGS}
    ref = TAGS[0]
    bad = []
    for t in TAGS[1:]:
        a, b = texts[ref].splitlines(), texts[t].splitlines()
        if len(a) != len(b):
            bad.append((t, "行数不同", len(a), len(b)))
            continue
        for i, (la, lb) in enumerate(zip(a, b), 1):
            if la != lb:
                bad.append((t, f"第 {i} 行", la.strip(), lb.strip()))
    for t, why, x, y in bad:
        print(f"[FAIL] {t} {why}：\n   基准 {x}\n   这条 {y}")
    # 逐项断言：五个文件的服务器参数与五个 lmeval 任务的参数逐条相同
    for pat, what in ((ARGS, "服务器参数 -c/-np/-ngl/--jinja"),
                      (r"--tasks (\S+)", "lmeval 任务名"),
                      (r"--limit (\d+)", "lmeval --limit"),
                      (r"--gen_kwargs ([^ ]+)", "生成参数")):
        vals = {t: re.findall(pat, texts[t]) for t in TAGS}
        same = len({tuple(map(tuple, v)) if isinstance(v[0], tuple) else tuple(v)
                    for v in vals.values()}) == 1
        print(f"  [{'ok' if same else 'FAIL'}] {what} 五个面板一致：{list(vals[ref])}")
        if not same:
            bad.append((what, "不一致", vals[ref], vals))
    # 代码面板（evalplus）自己的协议块：`evalplus.json` 的 `protocol` 与版本
    prot = {}
    for t in TAGS:
        p = base / t / "evalplus.json"
        if not p.is_file():
            print(f"看不到输入：缺 {p.relative_to(panel.REPO)}", file=sys.stderr)
            return 2
        doc = json.loads(p.read_text(encoding="utf-8"))
        prot[t] = (json.dumps(doc.get("protocol"), sort_keys=True), doc.get("evalplus"))
    same = len(set(prot.values())) == 1
    print(f"  [{'ok' if same else 'FAIL'}] evalplus 协议块与版本一致：{prot[ref]}")
    if not same:
        for t in TAGS:
            print(f"    {t}: {prot[t]}")
        bad.append(("evalplus 协议", "不一致", prot[ref], prot))
    print(f"\n{len(TAGS)} 个面板：{'只在模型路径上不同' if not bad else f'{len(bad)} 处差异'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
