#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`report_inputs/eval_status.json` 的读取口：报告正文与建表共用这一份产物。

产物由 `report_inputs/build_eval_status.py` 从不可入库的逐题落盘
`.wrapup/mres/*_eval.json` 抽取，字段是文件名的语言后缀、题数 n、通过数 pass 和状态直方图。
库内 MultiPL-E 行不带 `n_items`，所以一个格要打印题量，只能问它配对的产物：
`n_for(lang, score)` 按「通过数 / 题数 == 分数」找回该格的 n，找不回就返回 None——
调用方必须把未知题量打印成未知，不得填一个默认值。
"""
from __future__ import annotations

import collections
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "eval_status.json")

# 产物文件名里的语言后缀；这份清单随产物本身，报告与建表都从这里取。
LANGS = ("cpp", "py", "js", "java", "rs", "rb")

_CACHE = {}


def records():
    """[{file, lang, n, pass, status}]；文件缺失时抛错，不返回空表。"""
    if "records" not in _CACHE:
        if not os.path.exists(PATH):
            raise SystemExit(f"报告输入缺失：{PATH}（由 report_inputs/build_eval_status.py 生成）；"
                             f"不把缺失当成 0 份文件。")
        out = []
        for rec in json.load(open(PATH, encoding="utf-8"))["files"]:
            base = re.sub(r"(-chat)?(_fixed)?$", "", rec["file"][:-len("_eval.json")])
            lang = next((l for l in LANGS if base.endswith("-" + l) or base.endswith("_" + l)), None)
            out.append({"file": rec["file"], "name": base, "lang": lang,
                        "n": int(rec["n"]), "pass": int(rec["pass"]),
                        "status": collections.Counter(rec["status"])})
        _CACHE["records"] = out
    return _CACHE["records"]


def n_for(lang, score, hints=()):
    """该 (语言, 分数) 配对的产物题数；无法唯一确定时返回 None。

    分数本身不足以定题量：pass=0 的格与任何一份 pass=0 的产物都配得上，60 题探针和
    161 题整格于是分不开。所以分数只用来筛候选，真正的消歧靠产物文件名里的线索
    （`ctx2048`、`kvf16_f16` 这类由该格自己的协议串给出来的 facet）：线索必须全部出现在
    候选的文件名里，剩下的候选若给出同一个 n，才算定下来。

    定不下来就返回 None —— 调用方必须把它打印成「题量未知」，不得猜一个、也不得退化成
    一个看起来像整格的裸分数。
    """
    hits = [r for r in records()
            if r["lang"] == lang and r["n"] and abs(r["pass"] / r["n"] - score) < 1e-9]
    if hints:
        # 每个 facet 是一组可选写法：同一对 KV 在协议串与产物文件名里可能顺序相反
        hits = [r for r in hits if all(any(h in r["name"] for h in group) for group in hints)]
    ns = {r["n"] for r in hits}
    return ns.pop() if len(ns) == 1 else None


def hints_from_label(label):
    """从协议串取出能定位产物的 facet（目前是 `ctx=` 与 `kv=`）。

    每项是一组可选写法：同一对 KV 在协议串里写 `q8_0/f16`、在产物文件名里写成
    `kvf16_q8_0`，两种顺序都得认。
    """
    groups = []
    m = re.search(r"ctx=(\d+)", label or "")
    if m:
        groups.append(("ctx" + m.group(1),))
    m = re.search(r"kv=([\w]+)/([\w]+)", label or "")
    if m:
        a, b = m.group(1), m.group(2)
        groups.append(("kv" + a + "_" + b, "kv" + b + "_" + a))
    return groups
