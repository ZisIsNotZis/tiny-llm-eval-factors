#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a01 量化位宽：把 `.wrapup/mres` 派生的数字做成入库 fixture，并做漂移校验（WP6 / 干净 clone 门）。

为什么需要：`.gitignore` 把 `.wrapup/mres/*` 全部忽略（只放行 `*_eval.json`），所以干净 clone 里
没有逐题完成物，`run_all.py` 里依赖它们的两组断言（判分通道 `t2-channel-excluded`、12B MMLU 的
逐科目对照 `gemma12b-mmlu-uniform`）在 clone 里无法现算。这个脚本把那些数字抽成一份入库快照
（`analysis/fixtures/mres_snapshot.json`），并记下每个来源文件的 sha256；`run_all.py` 从快照断言，
在本机存在 `.wrapup/mres` 时再与现算值交叉校验。

    python3 "docs/subprojects/a01-量化位宽/analysis/make_fixtures.py" --write    # 重写快照
    python3 "docs/subprojects/a01-量化位宽/analysis/make_fixtures.py" --check    # 漂移校验
    python3 ".../make_fixtures.py" --check --fixture /tmp/x.json                 # 对指定副本校验

退出码：0 = 一致；1 = 漂移（打印差异的键）；2 = 无法校验（本机没有 `.wrapup/mres`，BLOCKED，不是通过）。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel_audit                                      # noqa: E402
import mmlu_subjects                                      # noqa: E402

REPO = channel_audit.REPO
FIXTURE = os.path.join(HERE, "fixtures", "mres_snapshot.json")
PANELS = ["m61-qwen-2b-iq2xxs", "m62-qwen-2b-iq2m", "m63-qwen-2b-iq3xxs", "m64-qwen-2b-q2kxl",
          "m65-qwen-2b-q3kxl", "m66-qwen-2b-q4kxl", "m67-qwen-2b-q5kxl"]
DATASETS = ["humaneval", "mbpp"]
MMLU_TAGS = ["m105-gemma-12b-q3kxl", "m141-native-gemma12b-q4"]
GEN = 'python3 "docs/subprojects/a01-量化位宽/analysis/make_fixtures.py" --write'


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_paths():
    out = {}
    for panel in PANELS:
        for ds in DATASETS:
            base = os.path.join(REPO, ".wrapup", "mres", panel, "codegen", ds)
            for pat in ("*temp_0.0.jsonl", "*temp_0.0.raw.jsonl", "*_eval_results.json"):
                for p in glob.glob(os.path.join(base, pat)):
                    out[os.path.relpath(p, REPO)] = sha256(p)
    for tag in MMLU_TAGS:
        for p in sorted(glob.glob(os.path.join(REPO, ".wrapup", "mres", tag, "lmeval_mmlu_*.json")))[-1:]:
            out[os.path.relpath(p, REPO)] = sha256(p)
    return out


def build():
    """从 `.wrapup/mres` 现算快照；没有产物时返回 None（BLOCKED）。"""
    if not os.path.isdir(os.path.join(REPO, ".wrapup", "mres")):
        return None
    audit = {}
    for panel in PANELS:
        for ds in DATASETS:
            r = channel_audit.audit(panel, ds)
            if r is not None:
                audit[f"{panel}/{ds}"] = r
    if not audit:
        return None
    mmlu = {}
    for tag in MMLU_TAGS:
        acc, path = mmlu_subjects.subjects(tag)
        if acc is None:
            continue
        mmlu[tag] = {"file": os.path.relpath(path, REPO), "n_subjects": len(acc),
                     "acc": {k: round(v, 6) for k, v in sorted(acc.items())}}
    return {
        "_provenance": {
            "generated_by": GEN,
            "written_against": "experiments.sqlite 与 .wrapup/mres 的本机状态；来源逐文件 sha256 见 sources",
            "why": (".wrapup/mres/* 被 .gitignore 忽略，干净 clone 里没有逐题完成物；这份快照是这些数字的"
                    "入库副本，判定入口是 run_all.py，漂移校验是 make_fixtures.py --check"),
            "rule": "改动任何 .wrapup/mres 产物后必须 --check；不一致时先看是不是重新判分/重跑造成的，再决定是否 --write",
            "sources": source_paths(),
        },
        "channel_audit": audit,
        "mmlu_subjects": mmlu,
    }


def diff(a, b, path=""):
    """返回差异列表（键路径 + 两侧值），只比数字与结构。"""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k == "_provenance":
                continue
            if k not in a:
                out.append(f"{path}/{k}: 快照缺失")
            elif k not in b:
                out.append(f"{path}/{k}: 现算缺失")
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, float) and isinstance(b, float):
        if abs(a - b) > 1e-9:
            out.append(f"{path}: 快照 {a} ≠ 现算 {b}")
    elif a != b:
        out.append(f"{path}: 快照 {a!r} ≠ 现算 {b!r}")
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fixture", default=FIXTURE)
    a = ap.parse_args(argv)
    live = build()
    if live is None:
        print("BLOCKED: 本机没有可用的 .wrapup/mres 产物，漂移无法校验（这不是通过）")
        return 2
    if a.write:
        os.makedirs(os.path.dirname(a.fixture), exist_ok=True)
        with open(a.fixture, "w", encoding="utf-8") as fh:
            json.dump(live, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
        n = len(live["channel_audit"]) + len(live["mmlu_subjects"])
        print(f"written: {os.path.relpath(a.fixture, REPO)}  ({n} 组数字，来源 {len(live['_provenance']['sources'])} 个文件)")
        return 0
    if a.check:
        if not os.path.isfile(a.fixture):
            print(f"MISSING: {a.fixture}")
            return 1
        snap = json.load(open(a.fixture, encoding="utf-8"))
        ds = diff(snap, live)
        if ds:
            print(f"DRIFT: {len(ds)} 处与现算不一致（{os.path.relpath(a.fixture, REPO)}）")
            for d in ds[:20]:
                print("  -", d)
            return 1
        print(f"OK: 快照与现算一致（{len(live['channel_audit'])} 组通道数字 + "
              f"{len(live['mmlu_subjects'])} 组 MMLU 科目表，来源 {len(live['_provenance']['sources'])} 个文件）")
        return 0
    ap.error("需要 --write 或 --check")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
