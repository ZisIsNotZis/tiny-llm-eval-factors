#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把不可入库的评测落盘产物抽成随仓库分发的报告输入。

`.wrapup/mres/*_eval.json` 是每次评测的逐题落盘结果（体积大、可重生成，因此不入 git），
但报告里「全 Exception 的格不是整轮运行失败、也不得记成 0」那一段必须读它：只看数据库
无法区分「这格没测」和「这格每道题都是 Exception」。所以这里把需要的那一点
（文件名、题数、通过数、状态直方图）抽成一个小文件随仓库分发，让干净 clone 也能得到
同一份报告。

用法：
    python3 report_inputs/build_eval_status.py          # 有落盘产物时重写 json，否则报错退出
    python3 report_inputs/build_eval_status.py --check  # 与现有 json 比对（干净 clone 上无可比对对象时说明并退出 0）

输出按文件名排序、无时间戳，同样的落盘产物永远得到同样的字节。
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "eval_status.json")
SOURCE_GLOB = os.path.join(os.path.dirname(HERE), ".wrapup", "mres", "*_eval.json")


def build():
    """[{file, n, pass, status}] —— 逐份评测文件的状态直方图，按文件名排序。"""
    files, skipped = [], 0
    for path in sorted(glob.glob(SOURCE_GLOB)):
        try:
            d = json.load(open(path))
        except Exception:
            skipped += 1
            continue
        det = d.get("details")
        if not isinstance(det, list) or not det:
            skipped += 1
            continue
        files.append({
            "file": os.path.basename(path),
            "n": len(det),
            "pass": int(d.get("pass") or 0),
            "status": dict(sorted(collections.Counter(x.get("status") for x in det).items())),
        })
    return files, skipped


def dump(files):
    return json.dumps({"source": "wrapup/mres/*_eval.json", "files": files},
                      ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main(argv):
    files, skipped = build()
    if not files:
        print(f"no run outputs under {os.path.relpath(SOURCE_GLOB)}; "
              f"the tracked input {os.path.relpath(OUT)} is left unchanged", file=sys.stderr)
        return 2
    text = dump(files)
    if "--check" in argv:
        try:
            have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"FAIL: {os.path.relpath(OUT)} is missing", file=sys.stderr)
            return 1
        if have != text:
            print(f"FAIL: {os.path.relpath(OUT)} is stale against the run outputs; "
                  f"rerun without --check", file=sys.stderr)
            return 1
        print(f"eval_status.json: up to date ({len(files)} files, {skipped} unreadable skipped)")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"wrote {os.path.relpath(OUT)}: {len(files)} files, {skipped} unreadable skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
