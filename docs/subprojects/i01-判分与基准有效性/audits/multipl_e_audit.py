#!/usr/bin/env python3
"""MultiPL-E scoring audit (WP5): where the postprocess sits, and how a wrong body
can still be scored as a pass.

The previous facts in this subproject (RESULT.md res20, res21) are about the fence
defect and about indentation.  This audit turns them into a repeatable negative
control and adds the direction nobody has tested: a completion that is wrong but
exits 0.

It takes a completion that really passed (out of a stored cell, so "correct" is not
my opinion), derives hand-built variants whose verdict is known, and scores each one
through the shipped scorer (`.wrapup/mpl_run.py eval`).  Two facts the report cannot
show on its own fall out of that:

  * the postprocess lives in the GENERATION step (`strip_fences` is applied in
    `mpl_run.py gen`), not in the scorer -- so a stored sample re-scored today keeps
    whatever the generation step did to it, and a rollout that writes samples by any
    other path is scored raw;
  * the pass criterion is "the compiled program exits 0", and the dataset's tests are
    appended after the completion, so a completion whose body is wrong but which ends
    with an early `exit(0)`/`raise SystemExit(0)` is scored as a pass.

Run from the repository root:

    python3 "docs/subprojects/i01-判分与基准有效性/audits/multipl_e_audit.py"

Exit 0 = every expectation held (including the early-exit bypass, so that fixing it
would fail this audit); 1 = a divergence; 2 = the stored cell or prompt set is
missing (unmeasured, never a pass).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

REPO = os.environ.get("I01_REPO_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
MRES = os.path.join(REPO, ".wrapup", "mres")
PROMPTS = os.path.join(REPO, ".wrapup", "prompts")
RUNNER = os.path.join(REPO, ".wrapup", "mpl_run.py")
CELL = "i01-slot-np1-p1-py-chat"
DIVERGED = []

# What an early exit looks like per language; the audit only exercises py, and names
# the others so the finding is not read as a python-only quirk.
EARLY_EXIT = {
    "py": 'raise SystemExit(0)',
    "js": 'process.exit(0)',
    "cpp": 'exit(0);',
    "java": 'System.exit(0);',
}


def note(ok, label, detail):
    print(("  OK   " if ok else "  FAIL ") + label + " :: " + detail)
    if not ok:
        DIVERGED.append(label)


def load_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def strip_fences(text):
    """The shipped postprocess, imported rather than re-implemented."""
    sys.path.insert(0, os.path.join(REPO, ".wrapup"))
    from mpl_run import strip_fences as sf  # noqa: E402
    return sf(text)


def main() -> int:
    samples_path = os.path.join(MRES, CELL + ".jsonl")
    eval_path = os.path.join(MRES, CELL + "_eval.json")
    prompt_path = os.path.join(PROMPTS, "humaneval-py.jsonl")
    for p in (samples_path, eval_path, prompt_path):
        if not os.path.exists(p):
            print("UNMEASURED: %s missing" % p)
            print("EXIT 2: missing input is not a pass")
            return 2

    samples = {r["name"]: r["completion"] for r in load_jsonl(samples_path)}
    ev = json.load(open(eval_path))
    passing = [d["name"] for d in ev["details"] if d["pass"]]
    if not passing:
        print("UNMEASURED: %s has no passing item to build correct-answer variants from" % CELL)
        print("EXIT 2: missing input is not a pass")
        return 2
    name = passing[0]
    body = samples[name]
    print("reference completion: %s (from %s, status=%s)" % (name, CELL, "OK"))
    print("  first line: %r" % body.split("\n")[0][:90])

    dedented = "\n".join(l.lstrip() for l in body.split("\n"))
    variants = [
        ("as_is", body, "pass"),
        ("fenced_raw", "```python\n" + body + "\n```\n", "fail"),
        ("fenced_after_strip", strip_fences("```python\n" + body + "\n```\n"), "pass"),
        ("unterminated_fence_after_strip", strip_fences("```python\n" + body + "\n"), "pass"),
        ("prose_prefixed_after_strip", strip_fences("Here is the code:\n" + body), "fail"),
        ("body_dedented", dedented, "fail"),
        ("empty", "", "fail"),
        ("wrong_body_with_early_exit", "pass\n" + EARLY_EXIT["py"] + "\n", "pass"),
        ("wrong_body_plain", "pass\n", "fail"),
    ]

    with tempfile.TemporaryDirectory() as wd:
        rows, plan = [], []
        for tag, completion, want in variants:
            rows.append({"name": name, "completion": completion})
            plan.append((tag, want))
        path = os.path.join(wd, "i01-mpl-%s.jsonl" % name.replace("/", "_"))
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        out = os.path.join(wd, "out.json")
        r = subprocess.run([sys.executable, RUNNER, "eval", "--lang", "py",
                            "--samples", path, "--out", out],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("UNMEASURED: scorer failed: %s" % r.stderr[-400:])
            print("EXIT 2: missing input is not a pass")
            return 2
        details = json.load(open(out))["details"]

    print("\nscores through the shipped scorer, one variant per line:")
    for (tag, want), d in zip(plan, details):
        got = "pass" if d["pass"] else "fail"
        note(got == want, "multipl-e py %s" % tag,
             "status=%s verdict=%s expected=%s" % (d["status"], got, want))

    print("\nstatus vocabulary this scorer records per item: OK / SyntaxError / Exception / Timeout")
    print("  (a cell's histogram is computed by the panel's record() into the log line")
    print("   'recorded <tag> <lang> ... {statuses}', not stored in <cell>_eval.json)")

    print("\nearly exit is a per-language channel, not a python quirk:")
    for lang, expr in EARLY_EXIT.items():
        print("  %-5s %s" % (lang, expr))
    print("  only py is exercised here; the others follow from the same 'program exits 0' rule")

    print("\nSUMMARY: %d expectation(s) diverged" % len(DIVERGED))
    for d in DIVERGED:
        print("  diverged: " + d)
    return 0 if not DIVERGED else 1


if __name__ == "__main__":
    sys.exit(main())
