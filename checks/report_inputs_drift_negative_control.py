#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`report_inputs/*.json` 与来源不一致时，`reproduce.sh` 必须非零退出（p-entry2 的负控）。

为什么这样跑（设计判断，不是批准）：`reproduce.sh` 的所有路径都由脚本自身位置推出，所以它不能
在一个临时树上跑；整条链路又要两分钟，把它当本脚本的子步骤会在每次复现核对里再花两分钟。
故 `reproduce.sh` 接受 `REPRODUCE_INPUTS_ONLY=1`，只跑「报告输入与来源一致」那一节（约 2 秒）并以
同一套 `record FAIL` 决定退出码——本脚本调用的是**真的 `./reproduce.sh`**，不是它的复制品，
因此「改坏一份输入 → 这条命令非零退出」是被端到端证明的，而不是被推断的。

三个用例，缺一个都不算证明过：

    baseline  未改动 → exit 0            （否则后面那次红可能是别的原因）
    drift     就地改坏 `open_questions.json` 一个字节 → exit 1，且输出点名该输入
    absent    把 `gsq.json` 暂时移走 → exit 0 且该行是 SKIP（缺席不是漂移，不许误判成红）

就地改坏是最小的注入面：只动一个文件、只动一次、`finally` 里按原字节写回并按 sha256 复核。
被中断时留下的是 `.drift-nc.bak`（未跟踪）与可能仍被改坏的那一份——两者都在 `git status` 里看得见，
下一步照原字节写回即可。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DRIFT_INPUT = os.path.join(REPO, "report_inputs", "open_questions.json")
ABSENT_INPUT = os.path.join(REPO, "report_inputs", "gsq.json")
BACKUP_SUFFIX = ".drift-nc.bak"


def run_inputs_only() -> tuple[int, str]:
    env = dict(os.environ, REPRODUCE_INPUTS_ONLY="1")
    proc = subprocess.run([os.path.join(REPO, "reproduce.sh")], cwd=REPO, env=env,
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def fail(message: str) -> int:
    print(f"FAIL {message}")
    return 1


def main() -> int:
    # baseline：不改任何东西时必须绿，否则下面那次红说明不了任何事
    rc, out = run_inputs_only()
    if rc != 0:
        return fail(f"baseline 未改动却 exit {rc}：\n{out}")
    if "报告输入漂移判 FAIL" in out:
        return fail("baseline 里出现了漂移判据自己的行，注入面不干净")

    original = open(DRIFT_INPUT, "rb").read()
    original_sha = sha256(DRIFT_INPUT)
    backup = DRIFT_INPUT + BACKUP_SUFFIX
    shutil.copyfile(DRIFT_INPUT, backup)
    try:
        # drift：改坏一个字节（长度不变，内容不同），模拟「来源重算过、输入没跟上」
        corrupted = bytearray(original)
        corrupted[len(corrupted) // 2] ^= 0x01
        with open(DRIFT_INPUT, "wb") as fh:
            fh.write(bytes(corrupted))
        rc, out = run_inputs_only()
        if rc == 0:
            return fail("改坏 open_questions.json 之后 ./reproduce.sh 仍 exit 0 —— 漂移没有变红")
        if "open_questions.json 与 PLAN.md 不一致" not in out:
            return fail(f"改坏之后非零退出（{rc}）但没有点名该输入：\n{out}")
        # 先把那一份按原字节写回：下面的缺席用例必须在干净树上跑，否则它红的原因说不清。
        with open(DRIFT_INPUT, "wb") as fh:
            fh.write(original)
        if sha256(DRIFT_INPUT) != original_sha:
            return fail("漂移用例之后 open_questions.json 没有按原字节写回")

        # absent：把一份输入整体移走 → 该行必须是 SKIP，整体仍绿
        stash = ABSENT_INPUT + BACKUP_SUFFIX
        shutil.copyfile(ABSENT_INPUT, stash)
        try:
            os.remove(ABSENT_INPUT)
            rc, out = run_inputs_only()
            if rc != 0:
                return fail(f"缺 gsq.json 时 exit {rc} —— 缺席被误判成漂移：\n{out}")
            if "SKIP" not in out or "gsq.json 不在场" not in out:
                return fail(f"缺 gsq.json 时没有给出缺席行：\n{out}")
        finally:
            shutil.copyfile(stash, ABSENT_INPUT)
            os.remove(stash)
    finally:
        with open(DRIFT_INPUT, "wb") as fh:
            fh.write(original)
        os.remove(backup)

    for path, want in ((DRIFT_INPUT, original_sha), (ABSENT_INPUT, None)):
        if not os.path.exists(path):
            return fail(f"负控结束后 {os.path.relpath(path, REPO)} 不在了")
        if want and sha256(path) != want:
            return fail(f"负控结束后 {os.path.relpath(path, REPO)} 的 sha256 变了")
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "report_inputs"],
                           cwd=REPO, capture_output=True, text=True, check=False)
    if dirty.stdout.strip():
        return fail(f"负控结束后 report_inputs 有未归位的改动：\n{dirty.stdout}")
    print("PASS 漂移→非零退出并点名；缺席→SKIP 仍绿；改动已按原字节写回")
    return 0


if __name__ == "__main__":
    sys.exit(main())
