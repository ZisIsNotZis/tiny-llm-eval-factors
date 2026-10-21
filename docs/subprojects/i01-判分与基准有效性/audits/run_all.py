#!/usr/bin/env python3
"""The subproject's acceptance entry point: one command, one verdict.

It runs two groups and reports both honestly, because they have different reach:

  LOGIC      `scoring_logic_check.py` -- executes the scoring code that lives in the
             repository itself on inputs built inline.  Reproducible in a clean clone
             (python3 + g++), so it must be green everywhere.
  DATA       the five real-data audits.  They read artefacts that are gitignored on
             purpose (`.wrapup/mres/*`, the three venvs, the bundled BFCL dataset), so
             in a clean clone they cannot run.  They report `EXIT 2 / UNMEASURED` with
             the missing file, and that is what this driver propagates -- "could not
             run" is never "passed".

Exit codes:
  0  logic green and every data audit measured and green   (a full tree with artefacts)
  1  something is red: a logic check diverged, or an audit found a divergence
  2  nothing red, but at least one thing is unmeasured     (the clean-clone case, and
     also any day a venv or an artefact is missing)

So "green" means *the evidence was present and held*.  A clone gets exit 2 with the
ledger below, which is the same semantics README states for what a clone cannot
rebuild: the conclusions are here, their measurement inputs are not.

Run from the repository root:

    python3 "docs/subprojects/i01-判分与基准有效性/audits/run_all.py"
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("I01_REPO_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

# (script, interpreter, group)
JOBS = [
    ("scoring_logic_check.py", sys.executable, "LOGIC"),
    ("bfcl_audit.py", os.path.join(REPO, ".wrapup", "bfclenv", "bin", "python"), "DATA"),
    ("noise_floor_compare.py", sys.executable, "DATA"),
    ("multipl_e_audit.py", sys.executable, "DATA"),
    ("lmeval_audit.py", os.path.join(REPO, ".wrapup", "lmenv", "bin", "python"), "DATA"),
    ("evalplus_audit.py", os.path.join(REPO, ".wrapup", "evalpy", "bin", "python"), "DATA"),
    ("unmeasured_gate_check.py", sys.executable, "GATE"),
]

LABEL = {0: "green", 1: "RED", 2: "UNMEASURED"}


def main() -> int:
    env = dict(os.environ)
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("HF_DATASETS_OFFLINE", "1")
    rows, red, unmeasured = [], [], []
    for script, interp, group in JOBS:
        path = os.path.join(HERE, script)
        if not os.path.exists(path):
            rows.append((group, script, "MISSING", "the script itself is absent"))
            unmeasured.append(script)
            continue
        if not os.path.exists(interp):
            rows.append((group, script, "UNMEASURED", "interpreter %s absent" % interp))
            unmeasured.append(script)
            continue
        r = subprocess.run([interp, path], capture_output=True, text=True, env=env, timeout=5400)
        out = (r.stdout or "") + (r.stderr or "")
        first_missing = ""
        for line in out.splitlines():
            # only a real verdict line counts, not prose that happens to mention the word
            if line.startswith("  UNMEASURED") or line.startswith("  diverged") \
                    or line.startswith("UNMEASURED"):
                first_missing = line.strip()[:150]
                break
        rows.append((group, script, LABEL.get(r.returncode, "rc=%d" % r.returncode), first_missing))
        if r.returncode == 1:
            red.append(script)
        elif r.returncode != 0:
            unmeasured.append(script)

    print("%-6s %-28s %-12s %s" % ("group", "check", "verdict", "first note"))
    for group, script, verdict, note in rows:
        print("%-6s %-28s %-12s %s" % (group, script, verdict, note))
    print()
    if red:
        print("RESULT: RED (%s)" % ", ".join(red))
        return 1
    if unmeasured:
        print("RESULT: EXIT 2 -- logic checks that ran are green, but %d check(s) could not run:"
              % len(unmeasured))
        print("        %s" % ", ".join(unmeasured))
        print("        A clean clone lands here by design: the measurement inputs are")
        print("        gitignored, so the conclusions travel but their evidence does not.")
        return 2
    print("RESULT: GREEN -- every logic check and every real-data audit was measured and held")
    return 0


if __name__ == "__main__":
    sys.exit(main())
