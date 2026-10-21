#!/usr/bin/env python3
"""Gate control: an audit must either measure, or say honestly that it could not.

Two ways a check lies, and this gate exists to catch both:

  * false GREEN -- it exits 0 without measuring anything (a skipped assertion, an
    imported module that was not there, a run in a tree without the evidence);
  * false RED -- it exits non-zero *because* its inputs are absent, and the caller
    reads that as "the conclusion is wrong" instead of "the evidence is not here".

So the verdict is not "did it exit 0".  It is the combination of exit code and
output markers:

    exit 0 + at least one measured line        -> GREEN (it really measured)
    exit 2 + a reported UNMEASURED line        -> GREEN (it correctly reported that
                                                  its inputs are not obtainable --
                                                  this is what a clean clone looks
                                                  like, and it is not a failure)
    exit 0 + no measured line                  -> RED   (claims to pass unmeasured)
    exit 2 + no UNMEASURED line                -> RED   (silently gave up)
    exit 1, or a crash / missing interpreter   -> RED   (with the inputs present a
                                                          red verdict is a real
                                                          divergence; without them
                                                          it should have been 2)

Both environments are exercised: the real tree (interpreter present, artefacts
present) and a simulated clone (`I01_REPO_ROOT` points at an empty directory, so the
artefacts and the venvs are gone).  Both must come out with no RED.

`--self-test` runs the classifier against two fabricated scripts, so the gate's own
judgement is a control and not a claim: one prints nothing and exits 0 (must be RED),
one prints UNMEASURED and exits 2 (must be GREEN).

Run from the repository root:

    python3 "docs/subprojects/i01-判分与基准有效性/audits/unmeasured_gate_check.py"
    python3 "docs/subprojects/i01-判分与基准有效性/audits/unmeasured_gate_check.py" --self-test
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# Two roots on purpose: REPO_REAL is always the tree this file lives in (so the
# "present" block means what it says even when the caller is simulating a clone), and
# EMPTY_ROOT is where a simulated clone lives.
REPO_REAL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
CLONE_ROOT = os.environ.get("I01_REPO_ROOT") or REPO_REAL
PY = sys.executable

# script, the interpreter that can import it, and whether to run it in "present" mode
# (an absent-mode run only needs the script itself and a starving environment)
def audits(root):
    return [
        ("bfcl_audit.py", os.path.join(root, ".wrapup", "bfclenv", "bin", "python"), {}),
        ("noise_floor_compare.py", PY, {}),
        ("multipl_e_audit.py", PY, {}),
        ("lmeval_audit.py", os.path.join(root, ".wrapup", "lmenv", "bin", "python"),
         {"HF_HOME": "@EMPTY@", "HF_DATASETS_CACHE": "@EMPTY@/datasets", "HF_HUB_CACHE": "@EMPTY@/hub"}),
        ("evalplus_audit.py", os.path.join(root, ".wrapup", "evalpy", "bin", "python"), {}),
    ]
RED = []
GREEN = []


def run(script_path, interp, root, extra=None):
    """(rc, output).  A missing interpreter is reported as rc 127, never raised: in a
    clone the venvs are absent by design and that must not crash the gate."""
    if not os.path.exists(interp):
        return 127, "interpreter absent: %s" % interp
    env = dict(os.environ)
    env["I01_REPO_ROOT"] = root
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("HF_DATASETS_OFFLINE", "1")
    for k, v in (extra or {}).items():
        env[k] = v.replace("@EMPTY@", root)
    try:
        r = subprocess.run([interp, script_path], capture_output=True, text=True,
                           env=env, timeout=1800)
    except Exception as e:  # a crash in the harness is a real failure of the gate
        return 1, "gate could not run the subprocess: %r" % (e,)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def measured_lines(out):
    return [l for l in out.splitlines()
            if l.startswith("  OK") or "identical=" in l or "rows=" in l or "arg_ok(" in l]


def reported_unmeasured(out):
    return [l for l in out.splitlines()
            if l.strip().startswith("UNMEASURED") or l.strip().startswith("EXIT 2")]


def classify(rc, out):
    """The contract, in one place.  Returns (verdict, reason)."""
    if rc == 0 and measured_lines(out):
        return "GREEN", "measured %d line(s)" % len(measured_lines(out))
    if rc == 2 and reported_unmeasured(out):
        return "GREEN", "reported not-obtainable (exit 2 + UNMEASURED)"
    if rc == 0:
        return "RED", "exit 0 with no measured line (false green)"
    if rc == 2:
        return "RED", "exit 2 without an UNMEASURED line (silent)"
    return "RED", "exit %d" % rc


def check(script, interp, root, extra, label):
    if not os.path.exists(interp):
        # A venv is not shipped (README: bootstrap rebuilds it), so "interpreter
        # absent" is the not-obtainable case, not a verdict about the conclusion.
        verdict, reason, rc, out = "GREEN", "interpreter absent (venv rebuilt by bootstrap)", 127, ""
        print("  %-5s %-26s %-8s rc=%-3d %s" % (label, script, verdict, rc, reason))
        GREEN.append((label, script, reason))
        return verdict, out
    rc, out = run(os.path.join(HERE, script), interp, root, extra)
    verdict, reason = classify(rc, out)
    print("  %-5s %-26s %-8s rc=%-3d %s" % (label, script, verdict, rc, reason))
    (GREEN if verdict == "GREEN" else RED).append((label, script, reason))
    return verdict, out


def self_test():
    """Two fabricated scripts: the gate's own judgement must separate them."""
    ok = True
    with tempfile.TemporaryDirectory() as td:
        fake_exit0 = os.path.join(td, "fake_exit0.py")
        open(fake_exit0, "w").write("print('all good')\nraise SystemExit(0)\n")
        fake_unm = os.path.join(td, "fake_unmeasured.py")
        open(fake_unm, "w").write("print('UNMEASURED: no artefacts in this tree')\n"
                                  "print('EXIT 2: missing input is not a pass')\n"
                                  "raise SystemExit(2)\n")
        for path, want in ((fake_exit0, "RED"), (fake_unm, "GREEN")):
            rc, out = run(path, PY, td)
            verdict, reason = classify(rc, out)
            good = verdict == want
            ok = ok and good
            print("  %-5s %-22s -> %-5s (wanted %s) rc=%d %s"
                  % ("OK" if good else "FAIL", os.path.basename(path), verdict, want, rc, reason))
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    print("gate contract: GREEN = (exit 0 + measured lines) or (exit 2 + UNMEASURED);"
          " everything else is RED")
    print("environment: real tree=%s, simulated clone=%s" % (REPO_REAL, CLONE_ROOT))
    with tempfile.TemporaryDirectory() as empty:
        print("\n[absent inputs] a simulated clean clone: artefacts and venvs gone")
        for script, interp, extra in audits(empty):
            check(script, interp, empty, extra, "absnt")
        print("\n[present inputs] the real tree")
        for script, interp, extra in audits(REPO_REAL):
            check(script, interp, REPO_REAL, {}, "pres")

    print("\nSUMMARY: %d green, %d red" % (len(GREEN), len(RED)))
    for label, script, reason in RED:
        print("  red: [%s] %s -- %s" % (label, script, reason))
    return 0 if not RED else 1


if __name__ == "__main__":
    sys.exit(main())
