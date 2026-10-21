#!/usr/bin/env python3
"""a08 的判定入口：一条命令跑完这一轴的可执行证据。

    python3 "docs/subprojects/a08-思考开关/analysis/run_all.py"

三项，任一不成立就非 0 退出：
  1. `thinking_pairs.py --check`：库 + 随仓库走的证据副本重算出来的三张 fixture 表，
     必须与提交的那份逐字相同。这一步在干净 clone 里也能绿，因为证据副本（panel json 与
     server.log 的 gz）随仓库走，`--check` 不从 `.wrapup/mres` 读。
  2. `thinking_pairs.py --selftest`：负控，改坏一份 fixture 副本必须让检查变红。
  3. **臂的身份必须闭合**：`fixtures/arm_runs.tsv` 里每条 `rc=0` 的臂，必须在
     `fixtures/logs/` 有它的 panel json、在 `thinking_cells.tsv` 有它的格、并且它的
     server.log 副本里有 `n_slots = 1`（起服断言落地为证据，而不只是当时打印过）。

退出码：0 全绿；1 有空不成立；2 输入缺失（不可得，不算通过）。
"""
from __future__ import annotations

import csv
import gzip
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE.parent / "fixtures"
LOGDIR = FIX / "logs"
PAIRS_SCRIPT = HERE / "thinking_pairs.py"
ARM_RUNS = FIX / "arm_runs.tsv"
DB = HERE.parents[3] / "experiments.sqlite"

missing = [str(p) for p in (DB, PAIRS_SCRIPT, FIX / "thinking_cells.tsv",
                           FIX / "thinking_pairs.tsv", FIX / "reasoning_census.tsv") if not p.exists()]
if missing:
    print("MISSING: " + ", ".join(missing), file=sys.stderr)
    sys.exit(2)

fails: list[str] = []


def run(*argv: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(PAIRS_SCRIPT), *argv], capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


rc, out = run("--check")
print(f"[1] thinking_pairs --check: rc={rc}\n    {out}")
if rc != 0:
    fails.append(f"thinking_pairs --check rc={rc}")

rc, out = run("--selftest")
print(f"[2] thinking_pairs --selftest: rc={rc}\n    {out}")
if rc != 0:
    fails.append(f"thinking_pairs --selftest rc={rc}")

# [3] 臂的身份闭合
cells_tag = {row["tag"] for row in csv.DictReader((FIX / "thinking_cells.tsv").open(),
                                                 delimiter="\t")}
arms = []
if ARM_RUNS.exists():
    arms = [r for r in csv.DictReader(ARM_RUNS.open(), delimiter="\t") if r.get("tag")]
checked = 0
for a in arms:
    if a.get("rc") not in ("0", 0):
        print(f"    arm {a['tag']}: rc={a['rc']} —— 未得数的臂不算 PASS，也不进判据")
        continue
    tag = a["tag"]
    panel = LOGDIR / f"{tag}.lmeval_panel.json"
    log = LOGDIR / f"{tag}.server.log.gz"
    if not panel.exists():
        fails.append(f"arm {tag}: 缺 panel json 副本")
    else:
        p = json.loads(panel.read_text())
        prof = (p.get("profiles") or {}).get(a["task"]) or {}
        for key, want in (("reasoning", a["reasoning"]), ("max_gen_toks", int(a["max_gen_toks"])),
                          ("ctx", int(a["ctx"]))):
            if str(prof.get(key)) != str(want):
                fails.append(f"arm {tag}: panel profiles[{a['task']}].{key}={prof.get(key)} != {want}")
    if not log.exists():
        fails.append(f"arm {tag}: 缺 server.log 副本")
    elif "n_slots = 1," not in gzip.open(log, "rt", errors="replace").read():
        fails.append(f"arm {tag}: server.log 里没有 n_slots = 1")
    if tag not in cells_tag:
        fails.append(f"arm {tag}: thinking_cells.tsv 里没有它的格（测量没落到证据里）")
    checked += 1
print(f"[3] 臂身份闭合: 检查 {checked} 条 rc=0 的臂"
      + ("" if arms else "（还没有 arm_runs.tsv：WP2 未开跑时为 0 条）"))

# 供人读的小结：每一类的对照数，以及没有对照的类
pairs = list(csv.DictReader((FIX / "thinking_pairs.tsv").open(), delimiter="\t"))
by_class: dict[str, int] = {}
for p in pairs:
    if p["off_tag"] != "NO-OFF-CELL":
        by_class[p["class"]] = by_class.get(p["class"], 0) + 1
census = list(csv.DictReader((FIX / "reasoning_census.tsv").open(), delimiter="\t"))
with_on = {c["class"] for c in census if c["reasoning"] == "on"}
print("[4] 每类对照数: " + ", ".join(f"{k}={v}" for k, v in sorted(by_class.items()))
      + " | 库里完全没有 on 格的类: "
      + ", ".join(sorted({c["class"] for c in census} - with_on)))

if fails:
    print("FAIL:\n  " + "\n  ".join(fails), file=sys.stderr)
    sys.exit(1)
print("PASS a08: 三项全绿")
sys.exit(0)
