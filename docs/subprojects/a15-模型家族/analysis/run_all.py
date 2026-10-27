#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a15 的唯一验收入口：清单 + 效应 + 两个负控，一条命令到底。

    python3 "docs/subprojects/a15-模型家族/analysis/run_all.py" --selftest

做四件事，全部当场跑（不读缓存、不读手抄的数字）：

  1. `pairs.py` → `analysis/pairs.json`（受控对清单）；
  2. `effects.py` → `analysis/effects.json`（效应与交互）；
  3. `pairs_negative_control.py`（改身份栏 / 改成 11% 尺寸差 → 该对必须掉、必须点名）；
  4. `effects_negative_control.py`（把一对分数改成相等 → `resolvable` / `flips` 必须变）。

另加两类自检，都不依赖快照常量，只判关系式与确定性：

  * 账平：候选数 = 被排除的候选数 + 产出受控格的候选数；`cells` 条数 = 打印的受控计数；
    每一格的 `size_delta` ≤ 容差；每一格的两个模型文件在 `families` 表里都有家族。
  * 确定性：再跑一遍 `pairs.py` / `effects.py` 到临时文件，与入库的两份 JSON 逐字节比较。

退出码：0 全绿；1 有任何自检或负控不成立；2 输入不可得（库 / 真值 fixture 缺）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LEDGER = HERE / "pairs.json"
EFFECTS_JSON = HERE / "effects.json"
DB = REPO / "experiments.sqlite"
TRUTH = REPO / "docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json"

failures: list[str] = []
checks = 0


def check(cond: bool, what: str, detail: str = "") -> bool:
    global checks
    checks += 1
    print(f"  {'ok  ' if cond else 'FAIL'} {what}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(what)
    return bool(cond)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def baseline_sha(stdout: str) -> str:
    """负控在跑 baseline 时打下 `BASELINE_SHA256 <sha>`；拿它当「同输入第二次运行」的字节。"""
    for line in stdout.splitlines():
        if line.startswith("BASELINE_SHA256 "):
            return line.split(None, 1)[1].strip()
    return ""


def run(script: str, *args: str, quiet: bool = False) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(HERE / script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not quiet:
        if proc.stdout.strip():
            print(proc.stdout.rstrip())
        if proc.returncode != 0 and proc.stderr.strip():
            print(proc.stderr.rstrip())
    return proc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true",
                    help="跑全部自检与负控（默认就是全跑；这个开关只为让验收命令不必记参数）")
    args = ap.parse_args(argv)
    t0 = time.time()

    if not DB.is_file():
        print(f"BLOCKED: dataset not found: {DB}", file=sys.stderr)
        return 2
    if not TRUTH.is_file():
        print(f"BLOCKED: truth fixture not found: {TRUTH}", file=sys.stderr)
        return 2

    print("== 1/4 controlled-pair inventory (pairs.py)")
    p = run("pairs.py")
    check(p.returncode == 0, "pairs.py exits 0", p.stderr[-400:])
    check(LEDGER.is_file(), "pairs.json was written")
    if not LEDGER.is_file():
        return 1
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))

    print("\n== 2/4 effects and interaction (effects.py)")
    e = run("effects.py")
    check(e.returncode == 0, "effects.py exits 0", e.stderr[-400:])
    check(EFFECTS_JSON.is_file(), "effects.json was written")
    effects = json.loads(EFFECTS_JSON.read_text(encoding="utf-8"))

    print("\n== 3/4 negative control: controlled-pair inventory (pairs_negative_control.py)")
    nc1 = run("pairs_negative_control.py")
    check(nc1.returncode == 0, "inventory negative control exits 0", nc1.stderr[-400:])

    print("\n== 4/4 negative control: effects (effects_negative_control.py)")
    nc2 = run("effects_negative_control.py")
    check(nc2.returncode == 0, "effects negative control exits 0", nc2.stderr[-400:])

    print("\n== self-checks: the ledger and the effects agree with themselves")
    lc, ec = ledger["counts"], effects["counts"]
    check(lc["candidates"] == lc["excluded"] + lc["candidates_with_controlled_cells"],
          "candidates == excluded + candidates_with_cells",
          f"{lc['candidates']} == {lc['excluded']} + {lc['candidates_with_controlled_cells']}")
    check(len(ledger["cells"]) == lc["controlled_cells"],
          "cells rows == printed controlled count", f"{len(ledger['cells'])} vs {lc['controlled_cells']}")
    check(len(ledger["excluded"]) == lc["excluded"],
          "excluded rows == printed excluded count")
    tol = ledger["size_tolerance"]
    over = [c["id"] for c in ledger["cells"] if c["size_delta"] > tol]
    check(not over, f"every controlled cell obeys size_delta <= {tol}", str(over[:5]))
    fam = ledger["families"]
    nameless = [c["id"] for c in ledger["cells"]
                if c["model_a"] not in fam or c["model_b"] not in fam]
    check(not nameless, "every controlled cell has both families", str(nameless[:5]))
    check(sum(lc["excluded_by_reason"].values()) == lc["excluded"],
          "the per-reason counts add up to the excluded count")
    check(ec["controlled_cells"] == lc["controlled_cells"],
          "effects analysed exactly the cells the ledger carries")
    check(ec["resolvable_bpw_matched"] <= ec["bpw_matched_cells"] <= ec["controlled_cells"],
          "resolvable_bpw_matched <= bpw_matched <= cells")
    check(ec["sign_flips_zero_gap"] <= ec["sign_flips_readable"] <= ec["sign_flips_all"],
          "flips(zero gap) <= flips(constant handicap) <= flips(all)")
    check(not effects["warnings"], "effects.py raised no self-check warning",
          str(effects["warnings"]))

    print("\n== determinism: the negative controls re-ran the same inputs into a temp dir; "
          "their baselines must be byte-identical to the committed artifacts")
    check(baseline_sha(nc1.stdout) == sha256(LEDGER),
          "pairs.json is byte-identical on a second run (same input, different output path)",
          f"temp={baseline_sha(nc1.stdout)} committed={sha256(LEDGER)}")
    check(baseline_sha(nc2.stdout) == sha256(EFFECTS_JSON),
          "effects.json is byte-identical on a second run (same input, different output path)",
          f"temp={baseline_sha(nc2.stdout)} committed={sha256(EFFECTS_JSON)}")

    dt = time.time() - t0
    print()
    if failures:
        print(f"FAILED {len(failures)}/{checks} checks: " + "; ".join(failures))
        return 1
    print(f"OK {checks}/{checks} checks green | candidates={lc['candidates']} "
          f"controlled={lc['controlled_cells']} excluded={lc['excluded']} "
          f"cells_with_intervals={ec['cells_with_intervals']} "
          f"resolvable={ec['resolvable_all']} resolvable_bpw_matched={ec['resolvable_bpw_matched']} "
          f"bpw_matched={ec['bpw_matched_cells']} flips={ec['sign_flips_all']} "
          f"flips_constant_gap={ec['sign_flips_readable']} "
          f"orderings_unstable={ec['orderings_unstable']} | {dt:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
