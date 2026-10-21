#!/usr/bin/env python3
"""The scoring-logic check: the part of this subproject's evidence that a clean clone
CAN reproduce.

Everything here is executed, not asserted from a table: the checks import the shipped
scoring code that lives in the repository itself (`mpl_run.strip_fences` and
`mpl_run.eval_one`, `bfcl_run.arg_ok`/`call_ok`) or apply the rule the harness ships as
data (gsm8k's two extraction regexes), and they build their inputs inline so no
gitignored artefact is needed. Compilers are the only external requirement (g++ for the
C++ case), which is the same requirement the MultiPL-E panel has.

What this check can and cannot catch, stated so nobody reads it as more:
  * it catches a regression in OUR scoring code or in a claim we made about it, and it
    fails if a rule we documented stops holding on the sample we chose;
  * it cannot catch an upstream change in the EvalPlus venv or the lm-eval harness --
    those live outside the repository and are the real-data audits' job
    (`run_all.py` reports them as BLOCKED in a clone rather than green).

Run from the repository root with any python3:

    python3 "docs/subprojects/i01-判分与基准有效性/audits/scoring_logic_check.py"

Exit 0 = every check held; 1 = a divergence (printed); 2 = a required tool is missing
(no compiler), which is unmeasured and not a pass.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile

# Every input this check uses is a tracked file (.wrapup/mpl_run.py, .wrapup/bfcl_run.py,
# the gsm8k rule as data), so it resolves from __file__ and has no root override: a
# clean clone has these, unlike the artefacts the DATA audits read.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, os.path.join(REPO, ".wrapup"))

DIVERGED = []
UNMEASURED = []


def note(ok, label, detail=""):
    print(("  OK   " if ok else "  FAIL ") + label + (" :: " + detail if detail else ""))
    if not ok:
        DIVERGED.append(label)


# ---------------------------------------------------------------- MultiPL-E
def check_multipl_e():
    """The scorer's rule is 'the whole program exits 0', and the postprocess is at
    generation.  Both are shown on inputs built here, through the shipped code."""
    print("\n[MultiPL-E] exit-code rule and postprocess placement")
    try:
        from mpl_run import strip_fences, eval_one
    except Exception as e:
        print("  UNMEASURED: cannot import .wrapup/mpl_run.py (%s)" % e)
        UNMEASURED.append("multipl-e import")
        return
    prompt = "def add(a, b):\n"
    tests = "\n\nassert add(1, 2) == 3\n"
    cases = [
        ("correct_body", "    return a + b\n", True, "the answer really is right"),
        ("wrong_body", "    return a - b\n", False, "wrong value fails the test"),
        ("wrong_body_with_early_exit", "    pass\nraise SystemExit(0)\n", True,
         "the program exits 0 before the asserts run, so a wrong body passes"),
    ]
    with tempfile.TemporaryDirectory() as wd:
        for name, completion, want, why in cases:
            ok, status = eval_one("py", prompt, completion, tests, wd)
            note(ok == want, "py %s" % name, "status=%s pass=%s (%s)" % (status, ok, why))
    # postprocess: a fenced body is only usable if strip_fences ran first
    body = "    return a + b\n"
    fenced = "```python\n" + body + "```\n"
    note(strip_fences(fenced) == body.rstrip(), "strip_fences recovers a fenced body",
         "stripped=%r" % strip_fences(fenced))
    with tempfile.TemporaryDirectory() as wd:
        ok_raw, st_raw = eval_one("py", prompt, fenced, tests, wd)
        ok_strip, st_strip = eval_one("py", prompt, strip_fences(fenced), tests, wd)
        note((not ok_raw) and ok_strip, "a fence is fatal until the postprocess runs",
             "raw status=%s, after strip_fences status=%s" % (st_raw, st_strip))
    # the same rule in C++, through the compiler the panel uses
    if os.system("command -v g++ >/dev/null 2>&1") != 0:
        print("  UNMEASURED: g++ not available, C++ case skipped")
        UNMEASURED.append("g++")
    else:
        with tempfile.TemporaryDirectory() as wd:
            # the MultiPL-E prompt opens the function body, so the completion has to
            # close it; the appended "tests" are a main() that returns non-zero on failure
            ok, status = eval_one("cpp", "int add(int a, int b) {\n",
                                  "  return a + b;\n}\n",
                                  "\nint main(){ if(add(1,2)!=3) return 1; return 0; }\n", wd)
            note(ok, "cpp correct body passes", "status=%s" % status)


# ---------------------------------------------------------------- BFCL
def check_bfcl():
    """arg_ok / call_ok are the single-turn matcher; the one-way tolerance and the
    unexamined extra argument are the two claims worth pinning."""
    print("\n[BFCL] matcher tolerance, executed against the shipped matcher")
    try:
        from bfcl_run import arg_ok, call_ok
    except Exception as e:
        print("  UNMEASURED: cannot import .wrapup/bfcl_run.py (%s)" % e)
        UNMEASURED.append("bfcl import")
        return
    for label, pred, accepted, want in [
        ("10 matches ['10']", 10, ["10"], True),
        ("'10' does not match [10]", "10", [10], False),
        ("case/space folded", " New York ", ["new york"], True),
        ("True matches [1]", True, [1], True),
        ("wrong value rejected", 11, [10], False),
    ]:
        got = arg_ok(pred, accepted)
        note(got == want, "arg_ok %s" % label, "arg_ok(%r,%r)=%s" % (pred, accepted, got))
    gt = {"calculate_triangle_area": {"base": [10], "height": [5]}}
    exact = {"name": "calculate_triangle_area", "arguments": {"base": 10, "height": 5}}
    extra = {"name": "calculate_triangle_area",
             "arguments": {"base": 10, "height": 5, "not_a_real_argument": 999}}
    note(call_ok(exact, gt), "call_ok accepts the exact call", "")
    note(call_ok(extra, gt), "call_ok ignores an extra argument", "an invented argument is never examined")
    bad = {"name": "calculate_triangle_area", "arguments": {"base": 10}}
    note(not call_ok(bad, gt), "call_ok rejects a missing required argument", "")


# ---------------------------------------------------------------- gsm8k
def check_gsm8k():
    """The two extraction rules travel with the task definition as data; applying the
    same regexes is what decides whether '#### 18' or 'the last number' is compared."""
    print("\n[gsm8k] the two filters, applied as the task definition specifies")
    strict_re = re.compile(r"#### (\-?[0-9\.\,]+)")
    flexible_re = re.compile(r"(-?[$0-9.,]{2,})|(-?[0-9]+)")
    ignore = [",", "\\$", "(?s).*#### ", "\\.$"]

    def apply(regex, group_select, text):
        m = regex.findall(text)
        if not m:
            return "[invalid]"
        m = m[group_select]
        if isinstance(m, tuple):
            m = [x for x in m if x][0] if any(m) else "[invalid]"
        return m.strip()

    def normalise(s):
        for pat in ignore:
            s = re.sub(pat, "", s)
        return s.strip().lower()

    def exact(pred, gold):
        return normalise(pred) == normalise(gold)

    gold = "Janet makes 9 * 2 = 18 every day.\n#### 18"
    for label, text, want_strict, want_flex, why in [
        ("marker present", "so the answer is #### 18", True, True, "both filters find 18"),
        ("no marker", "so the answer is 18", False, True, "strict has nothing to match; flexible recovers 18"),
        ("stray number after", "#### 18, and 7 is my lucky number", True, False,
         "flexible takes the LAST number, so 7 wins and the correct answer is lost"),
        ("wrong number", "#### 41", False, False, "wrong stays wrong under both"),
    ]:
        s = exact(apply(strict_re, 0, text), gold)
        f = exact(apply(flexible_re, -1, text), gold)
        note(s == want_strict and f == want_flex, "case %r" % label,
             "strict=%s flexible=%s (%s)" % (s, f, why))


# ---------------------------------------------------------------- EvalPlus
def check_evalplus():
    """Upstream's oracle set is data in the installed package, so in a clone it cannot
    be executed.  What is reproduced here is the *consequence* we published, on the
    values recorded by the real run (audits/evalplus.md): the reduced oracle accepts a
    body that only returns None exactly where every plus expectation is False."""
    print("\n[EvalPlus] the reduced-oracle consequence, recomputed from recorded values")
    # recorded by the real scorer on Mbpp/787 (audits/evalplus.md)
    plus_expected_all_false = True
    note(plus_expected_all_false, "Mbpp/787 plus expectations are all False (recorded)",
         "so `exp == (out is not None)` is satisfied by a body that returns None")
    # apply the oracle as the package writes it: exp == (out is not None)
    def reduced_oracle(exp, out):
        return exp == (out is not None)
    note(reduced_oracle(False, None), "a None body passes a False expectation", "")
    note(not reduced_oracle(True, None), "the same body fails where the expectation is True", "")
    print("  NOTE: this reproduces the consequence, not the upstream code path.  A change in")
    print("  evalplus is caught by the real-data audit (BLOCKED in a clone), not here.")


def main() -> int:
    print("scoring-logic check (reproducible in a clean clone; needs python3 + g++ for one case)")
    check_multipl_e()
    check_bfcl()
    check_gsm8k()
    check_evalplus()
    print("\nSUMMARY: %d expectation(s) diverged; %d input/tool(s) unmeasured"
          % (len(DIVERGED), len(UNMEASURED)))
    for d in DIVERGED:
        print("  diverged: " + d)
    for u in UNMEASURED:
        print("  unmeasured: " + u)
    if UNMEASURED:
        print("  EXIT 2: an unmeasured check is not a pass")
        return 2
    return 0 if not DIVERGED else 1


if __name__ == "__main__":
    sys.exit(main())
