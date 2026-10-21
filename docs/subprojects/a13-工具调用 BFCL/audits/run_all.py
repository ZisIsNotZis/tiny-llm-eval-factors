#!/usr/bin/env python3
"""a13 的判定入口：一条命令跑完本轴的可执行证据。

    python3 "docs/subprojects/a13-工具调用 BFCL/audits/run_all.py"

三件事，任一不成立就非 0 退出：
  1. 单轮换判分器的对照（`official_vs_homegrown.py`）必须 exit 0：79 个格可判、负控两侧成立、
     15 个预测文件全部绑定到 DB 行。
  2. 多轮判分器的可执行负控（`multiturn_checker_negative_control.py`）必须 exit 0：正确回放判
     PASS，改错的/格式坏的/什么都不做的三条都必须判 FAIL。
  3. **库与证据必须一致**（不比对易变的行数，而比对不变量）：每个可比格在 `experiments` 里的
     `_score` 必须逐位等于重打分产物里的 `official_acc` 且 `protocol` 是官方身份；prompt 那 20
     行必须是自研身份；bfcl 行的协议串只能取已知的四个值；`n_items` 为 NULL 的行必须全是多轮。

行数与哈希（实验库仍被 a06/i02 写）只作为**快照**打印，不作判据：判据是上面那些关系，
别人新增行不会把它们弄红，而本轴自己的值一旦漂移就会红。

退出码：0 全绿；1 有空不成立；2 输入缺失（不可得，不算通过）。
"""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DB = REPO / "experiments.sqlite"
ARTIFACT = HERE / "official_vs_homegrown.json"
SCRIPTS = [HERE / "official_vs_homegrown.py", HERE / "multiturn_checker_negative_control.py"]
BFCLENV = REPO / ".wrapup/bfclenv/bin/python"

KNOWN_PROTOCOLS = {
    "bfcl-native-tools-nothink-greedy-official-ast-checker",
    "bfcl-prompt-nothink-greedy-homegrown-matcher",
    "bfcl-official-multiturn-temp0",
    "bfcl-official-multiturn-temp0-partial",
}
OFFICIAL = "bfcl-native-tools-nothink-greedy-official-ast-checker"
PROMPT_HOMEGROWN = "bfcl-prompt-nothink-greedy-homegrown-matcher"

missing = [str(p) for p in (DB, ARTIFACT, BFCLENV, *SCRIPTS) if not p.exists()]
if missing:
    sys.stderr.write(f"MISSING INPUT: {missing}\n")
    sys.exit(2)

problems = []

for script in SCRIPTS:
    r = subprocess.run([str(BFCLENV), str(script)], capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    print(f"[{'PASS' if r.returncode == 0 else 'FAIL'}] {script.name}: {last}")
    if r.returncode != 0:
        problems.append(f"{script.name} exit {r.returncode}: {r.stderr.strip().splitlines()[-1:]}")

doc = json.load(open(ARTIFACT, encoding="utf-8"))
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
for fname, cats in doc["per_file"].items():
    model = doc["binding"][fname]["model"]
    for cat, rec in cats.items():
        if not rec.get("comparable", True):
            continue
        # 同一模型在同一类别下可能还有 prompt 协议那一行（另一个测量），所以按官方身份取行。
        row = con.execute(
            "SELECT _score, protocol FROM experiments WHERE model=? AND _bench=? AND protocol=?",
            (model, f"bfcl-{cat}", OFFICIAL)).fetchone()
        if row is None:
            problems.append(f"库里缺该格：{model} bfcl-{cat}")
        elif abs(float(row[0]) - rec["official_acc"]) > 1e-9 or row[1] != OFFICIAL:
            problems.append(f"该格与重打分产物不一致：{model} bfcl-{cat} "
                            f"db={row[0]}/{row[1]} artifact={rec['official_acc']}")

stale = con.execute(
    "SELECT count(*) FROM experiments WHERE bench_family='bfcl' "
    "AND protocol='bfcl-native-tools-nothink-greedy'").fetchone()[0]
if stale:
    problems.append(f"仍有 {stale} 行停在历史协议串 bfcl-native-tools-nothink-greedy（身份未标）")

n_prompt = con.execute("SELECT count(*) FROM experiments WHERE bench_family='bfcl' AND protocol=?",
                       (PROMPT_HOMEGROWN,)).fetchone()[0]
if n_prompt != 20:
    problems.append(f"prompt 协议应 20 行自研身份，实得 {n_prompt}")

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
