#!/usr/bin/env python3
"""a13 的判定入口：一条命令跑完本轴的可执行证据。

    python3 "docs/subprojects/a13-工具调用 BFCL/audits/run_all.py"

三件事，任一不成立就非 0 退出：
  1. 单轮换判分器的对照（`official_vs_homegrown.py`）必须 exit 0：79 个格可判、负控两侧成立、
     15 个预测文件全部绑定到 DB 行。
  2. 多轮判分器的可执行负控（`multiturn_checker_negative_control.py`）必须 exit 0：正确回放判
     PASS，改错的/格式坏的/什么都不做的三条都必须判 FAIL。
  3. **库与证据必须一致**（不比对易变的行数，而比对不变量）：每个可比格在 `experiments` 里的
     `_score` 必须逐位等于重打分产物里的 `official_acc` 且 `protocol` 是官方身份；不许有行停在两条
     退役协议串（`bfcl-native-tools-nothink-greedy` / `bfcl-prompt-nothink-greedy`）上；bfcl 行的
     协议串只能取已知的五个值；`n_items` 为 NULL 的行必须全是多轮。

子检查崩溃（非 0 退出、读不到产物、绑定缺项）都只记 FAIL 并继续走完，不向调用者抛异常：
判定入口自己崩掉，等于把一个可诊断的不一致变成一条 traceback。

行数与哈希（实验库仍被 a06/i02 写）只作为**快照**打印，不作判据：判据是上面那些关系，
别人新增行不会把它们弄红，而本轴自己的值一旦漂移就会红。

`A13_DB=<path>` 可把库换成副本，用于「漂移必须变红」的负控（见 RESULT.md::res15）。

退出码：0 全绿；1 有空不成立；2 输入缺失（不可得，不算通过）。
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DB = Path(os.environ.get("A13_DB", REPO / "experiments.sqlite"))
ARTIFACT = HERE / "official_vs_homegrown.json"
SCRIPTS = [HERE / "official_vs_homegrown.py", HERE / "multiturn_checker_negative_control.py"]
BFCLENV = REPO / ".wrapup/bfclenv/bin/python"

KNOWN_PROTOCOLS = {
    "bfcl-native-tools-nothink-greedy-official-ast-checker",
    "bfcl-native-tools-nothink-greedy-homegrown-matcher",
    "bfcl-prompt-nothink-greedy-homegrown-matcher",
    "bfcl-official-multiturn-temp0",
    "bfcl-official-multiturn-temp0-partial",
}
OFFICIAL = "bfcl-native-tools-nothink-greedy-official-ast-checker"
PROMPT_HOMEGROWN = "bfcl-prompt-nothink-greedy-homegrown-matcher"
# 两条退役串：值与身份脱钩的旧串。任何一行停在这里都算「身份未标」。
RETIRED_PROTOCOLS = (
    "bfcl-native-tools-nothink-greedy",
    "bfcl-prompt-nothink-greedy",
)

missing = [str(p) for p in (DB, ARTIFACT, BFCLENV, *SCRIPTS) if not p.exists()]
if missing:
    sys.stderr.write(f"MISSING INPUT: {missing}\n")
    sys.exit(2)

problems = []


def run_subcheck(script):
    """Run one child check; a crash is a FAIL line, never a propagated exception."""
    try:
        r = subprocess.run([str(BFCLENV), str(script)], capture_output=True, text=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {script.name}: could not run ({type(exc).__name__}: {exc})")
        problems.append(f"{script.name} could not run: {exc}")
        return
    ok = r.returncode == 0
    out = (r.stdout or "").strip().splitlines()
    err = (r.stderr or "").strip().splitlines()
    print(f"[{'PASS' if ok else 'FAIL'}] {script.name}: "
          f"{(out or err or [''])[-1]}")
    if not ok:
        problems.append(f"{script.name} exit {r.returncode}: {(err or out or [''])[-1]}")


for script in SCRIPTS:
    run_subcheck(script)

try:
    doc = json.load(open(ARTIFACT, encoding="utf-8"))
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
except Exception as exc:  # noqa: BLE001
    print(f"[FAIL] evidence/db could not be read: {type(exc).__name__}: {exc}")
    problems.append(f"evidence or db unreadable: {exc}")
    doc, con = None, None

bad_null = []
if doc is not None:
    binding = doc.get("binding", {})
    for fname, cats in doc.get("per_file", {}).items():
        model = (binding.get(fname) or {}).get("model")
        if model is None:
            problems.append(f"证据里缺该文件的绑定：{fname}")
            continue
        for cat, rec in cats.items():
            if not rec.get("comparable", True):
                continue
            # 同一模型在同一类别下可能还有 prompt 协议那一行（另一个测量），所以按官方身份取行。
            row = con.execute(
                "SELECT _score, protocol FROM experiments WHERE model=? AND _bench=? AND protocol=?",
                (model, f"bfcl-{cat}", OFFICIAL)).fetchone()
            if row is None:
                problems.append(f"库里缺该格：{model} bfcl-{cat}")
            elif abs(float(row[0]) - rec["official_acc"]) > 1e-9:
                problems.append(f"该格与重打分产物不一致：{model} bfcl-{cat} "
                                f"db={row[0]} artifact={rec['official_acc']}")

    stale = con.execute(
        "SELECT protocol, count(*) FROM experiments WHERE bench_family='bfcl' "
        f"AND protocol IN ({','.join('?' * len(RETIRED_PROTOCOLS))}) GROUP BY 1",
        RETIRED_PROTOCOLS).fetchall()
    if stale:
        problems.append(f"仍有行停在退役协议串（判分器身份未标）：{stale}")

    # prompt 协议的身份是全有全无：行数会随面板增减（a13 的判据是关系，不是行数），
    # 所以这里不钉死条数，只要求没有一行停在退役串上（上面的 stale）+ 没有未知串（下面的
    # bad_proto），两条合起来就是「prompt 行的 `protocol` 只能是自研身份」。
    n_prompt = con.execute(
        "SELECT count(*) FROM experiments WHERE bench_family='bfcl' AND protocol=?",
        (PROMPT_HOMEGROWN,)).fetchone()[0]
    if n_prompt == 0:
        problems.append("prompt 协议一行都没有（身份串 " + PROMPT_HOMEGROWN + " 在库里不存在）")

    bad_proto = con.execute(
        f"SELECT protocol, count(*) FROM experiments WHERE bench_family LIKE 'bfcl%' "
        f"AND protocol NOT IN ({','.join('?' * len(KNOWN_PROTOCOLS))}) GROUP BY 1",
        tuple(KNOWN_PROTOCOLS)).fetchall()
    if bad_proto:
        problems.append(f"出现未知协议串：{bad_proto}")

    bad_null = con.execute(
        "SELECT bench_family, count(*) FROM experiments WHERE bench_family LIKE 'bfcl%' "
        "AND n_items IS NULL GROUP BY 1").fetchall()
    if [f for f, _ in bad_null if f != "bfcl-multiturn"]:
        problems.append(f"n_items 为 NULL 的行不全是多轮：{bad_null}")

    snap = con.execute(
        "SELECT protocol, count(*), count(n_items) FROM experiments "
        "WHERE bench_family LIKE 'bfcl%' GROUP BY 1").fetchall()
    sha = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()[:16]
    print(f"\n快照（不作判据）：artifact sha256[:16]={sha}；"
          + "；".join(f"{p} {n}行(n={k})" for p, n, k in snap))
    if bad_null:
        print(f"  仍缺题量：{bad_null}（原因见 RESULT.md::res4，不是漏填）")

if problems:
    print("\nFAIL:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("\nPASS: 判分器对照、多轮负控、库与证据一致")
