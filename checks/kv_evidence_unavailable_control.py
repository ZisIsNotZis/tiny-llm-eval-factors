#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：「a05 的输入不在场」必须以 2 退出并点名缺失路径，不能冒充「索引过期」。

干净 clone 里 `kv_evidence.json` 无法当场核对，因为 a05 的证据脚本要 `.wrapup/mres` 的落盘产物，
而那批产物不随仓库分发。没有这条控制时，`build_kv_evidence.py --check` 会把它报成
「找不到 f16→q4_0 的逐题配对」（=1，读起来就是索引过期），`reproduce.sh` 于是打出一条假 WARN。

两例：
  1. 把 a05 的脚本复制到一棵没有 `.wrapup` 的空树下（脚本自己算 REPO，缺输入就会 traceback）→
     必须退出 2，且 stderr 里出现那条确实缺失的路径；
  2. 同一份副本旁边补上 `.wrapup/mres` 之外的目录结构也不该变绿——所以只要求第 1 例；
     另外核对正常路径没有被这条控制带偏：本机的 a05 输入在场时退出码不得是 2
     （不在场就是干净 clone 的正常情况，这一条记为不适用）。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILDER = REPO / "report_inputs" / "build_kv_evidence.py"
A05_SCRIPT = REPO / "docs" / "subprojects" / "a05-KV 缓存精度" / "analysis" / "kv_evidence.py"


def run_builder(script: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, A05_KV_EVIDENCE_SCRIPT=str(script))
    return subprocess.run([sys.executable, str(BUILDER), "--check"],
                          capture_output=True, text=True, cwd=str(REPO), env=env)


def main() -> int:
    if not A05_SCRIPT.exists():
        print(f"FAIL: a05 的证据脚本不在场：{A05_SCRIPT.relative_to(REPO)}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="kv-unavailable-control-"))
    try:
        # a05 的脚本用 HERE.parents[3] 当仓库根，所以副本要放在三层目录之下：
        # <tmp>/a/b/c/analysis/kv_evidence.py → 它以为仓库根是 <tmp>，而 <tmp> 没有 .wrapup。
        dest = tmp / "a" / "b" / "c" / "analysis" / "kv_evidence.py"
        dest.parent.mkdir(parents=True)
        shutil.copy2(A05_SCRIPT, dest)

        r = run_builder(dest)
        expected_missing = str(tmp / ".wrapup" / "mres" / "m130-kv" / "variant_panel.json")
        named = expected_missing in r.stderr
        ok = r.returncode == 2 and named
        print(f"1) a05 脚本在没有 .wrapup 的树下 → exit 2: {r.returncode == 2}；"
              f"点名缺失路径 {expected_missing.replace(str(tmp), '<tmp>')}: {named}")
        if not ok:
            print(f"FAIL: 期望 exit 2 并点名缺失路径，实际 exit {r.returncode}：{r.stderr.strip()[:400]}")
            return 1

        # 正常路径没有被这条控制带偏：本机的 a05 输入若在场，退出码必须是 0 或 1（一致 / 过期），
        # 不能是 2——2 在干净 clone 里是正常情况（.wrapup/mres 不随仓库分发），这条记为不适用。
        real = subprocess.run([sys.executable, str(BUILDER), "--check"],
                              capture_output=True, text=True, cwd=str(REPO))
        if real.returncode == 2:
            print("2) 本机 a05 的落盘输入不在场（干净 clone 的正常情况），这一条不适用")
            return 0
        if real.returncode not in (0, 1):
            print(f"FAIL: 真实脚本上的退出码既不是 0/1 也不是 2，而是 {real.returncode}："
                  f"{real.stderr.strip()[:300]}")
            return 1
        print(f"2) 本机 a05 的输入在场，真实脚本上退出 {real.returncode}（0=一致 1=过期），不是 2")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
