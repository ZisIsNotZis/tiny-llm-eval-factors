#!/usr/bin/env python3
"""Gate control: an audit that could not run must not look like an audit that passed.

The failure this guards against is the one every audit in this repo has had at least
once, and this subproject twice: a script prints `UNMEASURED`, skips its assertion,
and still exits 0, so a run in a tree without the evidence reads as a verified result.

It drives each audit as a SUBPROCESS with that audit's own interpreter (the lm-eval
and evalplus audits need different venvs), twice:

  * absent mode -- `I01_REPO_ROOT` points at an empty temp tree, so every input is
    missing.  Required: exit 2, the output contains "EXIT 2", and the output contains
    at least one "UNMEASURED".  Anything else (0, 1, a traceback, empty output) is a
    gate failure, because a script that crashes or silently succeeds has not shown
    that it distinguishes "held" from "could not run".
  * present mode -- the real tree.  Required: exit 0 AND at least one measured line
    (a line that states a number or an `OK`), so a script that does nothing cannot be
    green either.

`evalplus_audit.py` is only exercised in absent mode here: its present mode runs a
full EvalPlus evaluation (about six minutes) and its evidence for the real tree is
recorded in `audits/evalplus.md`.  That exclusion is printed, not silently skipped.

Run from the repository root:

    python3 "docs/subprojects/i01-判分与基准有效性/audits/unmeasured_gate_check.py"

Exit 0 = every gate behaved; 1 = at least one did not (printed).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable

# (script, interpreter that can import it, exercised in present mode?)
# script, interpreter, present mode exercised?, extra env that makes its inputs absent.
# Each audit is starved of what it actually reads, not of a path it happens to mention:
# the three repo-local audits lose their artefacts, and lmeval_audit loses its HF cache
# (its datasets come from ~/.cache, so pointing REPO elsewhere would prove nothing).
AUDITS = [
    ("bfcl_audit.py", os.path.join(REPO, ".wrapup", "bfclenv", "bin", "python"), True, {}),
    ("noise_floor_compare.py", PY, True, {}),
    ("multipl_e_audit.py", PY, True, {}),
    ("lmeval_audit.py", os.path.join(REPO, ".wrapup", "lmenv", "bin", "python"), False,
     {"HF_HOME": "@EMPTY@", "HF_DATASETS_CACHE": "@EMPTY@/datasets", "HF_HUB_CACHE": "@EMPTY@/hub"}),
    ("evalplus_audit.py", os.path.join(REPO, ".wrapup", "evalpy", "bin", "python"), False, {}),
]
FAILED = []
UNMEASURED = []   # an absent interpreter is unmeasured, not a red verdict


def run(script, interp, root, extra=None):
    env = dict(os.environ)
    env["I01_REPO_ROOT"] = root
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("HF_DATASETS_OFFLINE", "1")
    for k, v in (extra or {}).items():
        env[k] = v.replace("@EMPTY@", root)
    r = subprocess.run([interp, os.path.join(HERE, script)], capture_output=True,
                       text=True, env=env, timeout=1800)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def fail(msg):
    print("  FAIL " + msg)
    FAILED.append(msg)


def main() -> int:
    print("gate: absent input must exit 2 and be reported as unmeasured")
    with tempfile.TemporaryDirectory() as empty:
        for script, interp, present, extra in AUDITS:
            if not os.path.exists(interp):
                print("  UNMEASURED %-26s interpreter %s absent" % (script, interp))
                UNMEASURED.append(script)
                continue
            rc, out = run(script, interp, empty, extra)
            has_exit2 = "EXIT 2" in out
            has_unmeasured = "UNMEASURED" in out
            ok = (rc == 2 and has_exit2 and has_unmeasured)
            print("  %-26s absent: rc=%d EXIT2=%s UNMEASURED=%s" % (script, rc, has_exit2, has_unmeasured))
            if not ok:
                fail("%s: absent mode rc=%d EXIT2=%s UNMEASURED=%s (expected 2/True/True)"
                     % (script, rc, has_exit2, has_unmeasured))
            if not present:
                print("  %-26s present mode not exercised here (slow or needs a GPU-free "
                      "dataset load); its real-tree evidence is in audits/*.md" % "")
                continue
            rc2, out2 = run(script, interp, REPO)
            measured = ("OK   " in out2) or ("identical=" in out2) or ("rows=" in out2)
            ok2 = (rc2 == 0 and measured)
            print("  %-26s present: rc=%d measured_lines=%s" % (script, rc2, measured))
            if not ok2:
                fail("%s: present mode rc=%d measured=%s (expected 0/True)" % (script, rc2, measured))

    print("\nSUMMARY: %d gate failure(s); %d audit(s) not exercisable here"
          % (len(FAILED), len(UNMEASURED)))
    for f in FAILED:
        print("  failed: " + f)
    for u in UNMEASURED:
        print("  unmeasured: " + u)
    if FAILED:
        return 1
    if UNMEASURED:
        print("  EXIT 2: a gate that could not exercise an audit has not verified it")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
