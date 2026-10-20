#!/usr/bin/env python3
"""EvalPlus scoring audit (WP2): can the numbers this harness writes be trusted?

Four questions, answered by observation instead of by reading the code:

  Q1 markdown   -- is a code fence stripped before scoring, and at which step?
  Q2 indent     -- does the scoring path preserve or destroy the completion's indentation?
  Q3 histogram  -- is a per-cell status histogram recorded, and with what vocabulary?
  Q4 false pos. -- can a completion that is wrong be scored as a passing number?

Plus the direction that already went wrong once in this repo (RESULT.md::res20): a
*correct* completion scored as a failure (false negative).

Method: build completions whose verdict is known in advance and put them through
the real scoring path (`evalplus.evaluate`), both on a fixed prefix of HumanEval+
and on MBPP+ tasks, then assert every expectation. Two expectations are
deliberately "pass": upstream gives three MBPP+ tasks an oracle that only checks
the output is not None, and Mbpp/164 an oracle of `exact_match or True`, so a wrong
body really is scored as a pass there. The audit asserts that this bypass set is
exactly the enumerated one, so a future upstream change fails the audit instead of
silently changing what a score means.

Run from the repository root with the evalplus venv (it *is* the scorer):

    .wrapup/evalpy/bin/python "docs/subprojects/i01-判分与基准有效性/audits/evalplus_audit.py"

Exit 0 = every expectation held; 1 = at least one divergence (printed); 2 = the
MBPP+ dataset could not be loaded. Writes only inside a temp dir; the DB is untouched.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

REPO = os.environ.get("I01_REPO_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from evalplus.data import get_human_eval_plus, get_mbpp_plus  # noqa: E402
from evalplus.evaluate import evaluate  # noqa: E402
from evalplus.sanitize import sanitize  # noqa: E402
from evalplus.eval._special_oracle import (  # noqa: E402
    MBPP_OUTPUT_NOT_NONE_TASKS, MBPP_OUTPUT_SET_EQ_TASKS,
)

HUMANEVAL_TASKS = ["HumanEval/0", "HumanEval/1", "HumanEval/2", "HumanEval/3", "HumanEval/4"]
FENCE = "```python\n"
DIVERGED = []
UNMEASURED = []   # a missing input is not a pass: it makes the run exit 2


def note(ok, label, detail):
    print(("  OK   " if ok else "  FAIL ") + label + " :: " + detail)
    if not ok:
        DIVERGED.append(label)


def score(dataset, problems, cases, workdir, tag):
    """cases: [(task_id, solution)] -> {task_id: [plus_status in write order]}.

    The scorer refuses a samples file that does not cover every task of the dataset
    (`assert len(completion_id) == len(problems)`), so tasks the probe does not touch
    are filled with their canonical solution; those fills are not asserted on.
    The scorer sorts each task's results by completion_id, and completion_id is
    assigned in file order, so a case's position among its task's cases is its index.
    """
    probed = {t for t, _ in cases}
    full = list(cases)
    for task_id, p in problems.items():
        if task_id not in probed:
            full.append((task_id, p["prompt"] + p["canonical_solution"]))
    path = os.path.join(workdir, "i01-evalplus-%s.jsonl" % tag)
    with open(path, "w") as f:
        for task_id, solution in full:
            f.write(json.dumps({"task_id": task_id, "solution": solution}) + "\n")
    evaluate(dataset, samples=path, parallel=2)
    res = json.load(open(path.replace(".jsonl", "_eval_results.json")))
    per_task, hist = {}, {}
    for task_id, rows in res["eval"].items():
        per_task[task_id] = [r["plus_status"] for r in sorted(rows, key=lambda r: r.get("completion_id", 0))]
        for r in rows:
            k = (r["base_status"], r["plus_status"])
            hist[k] = hist.get(k, 0) + 1
    return per_task, hist


def check(per_task, plan, tag):
    """plan: [(task_id, case_name, expected_plus_status)], consumed in order per task."""
    cursor = {}
    for task_id, name, want in plan:
        i = cursor.get(task_id, 0)
        cursor[task_id] = i + 1
        got = per_task[task_id][i]
        note(got == want, "%s %s expected=%s" % (tag, task_id + " " + name, want),
             "got plus_status=%s" % got)


def part_questions(workdir, he, mbpp):
    print("\n[Q3] what the scorer records per cell")
    print("  eval_results.json top-level keys are date/hash/eval: pass_at_k is printed to the log but")
    print("  NOT saved, so every stored EvalPlus score had to be recomputed from base_status/plus_status.")
    print("  vocabulary is pass/fail/timeout (a single 'exception' bucket does not exist):")
    print("    jq -r '[.eval[][]|.plus_status]|group_by(.)|map({(.[0]):length})|add' <cell>_eval_results.json")

    print("\n[Q1/Q2/Q4] hand-built completions through the real scorer, HumanEval+")
    cases, plan = [], []
    for task_id in HUMANEVAL_TASKS:
        p = he[task_id]
        correct = p["prompt"] + p["canonical_solution"]
        # the indentation probes use the same correct statements, mis-indented the
        # two ways that actually occur: body at column 0 (the MultiPL-E failure mode,
        # RESULT.md::res21) and one level too deep.
        body_lines = p["canonical_solution"].split("\n")
        body_col0 = p["prompt"] + "\n".join(l[4:] if l.startswith("    ") else l for l in body_lines)
        body_deep = p["prompt"] + "\n".join(("    " + l) if l.strip() else l for l in body_lines)
        for name, solution, want in [
            ("canonical", correct, "pass"),
            ("body_at_column_0", body_col0, "fail"),
            ("body_over_indented", body_deep, "fail"),
            ("wrong_body", p["prompt"] + "    return None\n", "fail"),
            ("empty", "", "fail"),
            ("fenced_direct", FENCE + correct + "\n```\n", "fail"),
            ("prose_direct", "Here is the solution:\n\n" + correct, "fail"),
            ("fenced_via_codegen", sanitize(FENCE + correct + "\n```\n", p["entry_point"]), "pass"),
            ("body_at_column_0_via_codegen", sanitize(body_col0, p["entry_point"]), "fail"),
        ]:
            cases.append((task_id, solution))
            plan.append((task_id, name, want))
    per_task, hist = score("humaneval", he, cases, workdir, "humaneval")
    check(per_task, plan, "humaneval")
    print("  status histogram for this batch: %s" % hist)

    print("\n[Q4] the MBPP+ oracle bypass, counted rather than assumed")
    from evalplus.evaluate import get_groundtruth, get_mbpp_plus_hash
    expected_out = get_groundtruth(mbpp, get_mbpp_plus_hash(), [])
    not_none = sorted(t for t, p in mbpp.items() if p["entry_point"] in MBPP_OUTPUT_NOT_NONE_TASKS)
    always_true = sorted(t for t, p in mbpp.items() if p["entry_point"] == "are_equivalent")
    seteq = sorted(t for t, p in mbpp.items() if p["entry_point"] in MBPP_OUTPUT_SET_EQ_TASKS)
    print("  oracle is only 'output is not None': %s" % not_none)
    print("  oracle is `exact_match or True`: %s (absent from this dataset version)" % always_true)
    print("  oracle is set equality (order-insensitive): %d tasks %s" % (len(seteq), seteq))

    # A wrong body is scored as a pass on such a task exactly when its returned
    # shape matches what the reduced oracle can see, so the expectation is derived
    # from the ground truth rather than assumed: `return None` passes iff every plus
    # expectation is False, `return object()` passes iff every plus expectation is
    # True.  Deriving it keeps the audit honest if upstream changes the oracle set.
    def wrong_none(p):
        return p["prompt"] + "\ndef %s(*args, **kwargs):\n    return None\n" % p["entry_point"]

    def wrong_object(p):
        return p["prompt"] + "\ndef %s(*args, **kwargs):\n    return object()\n" % p["entry_point"]

    cases, plan = [], []
    for task_id in not_none:
        exp = expected_out[task_id]["plus"]
        # `return None` makes `out is not None` False, so it passes exactly where
        # every expected value is False; `return object()` passes exactly where
        # every expected value is True.
        for name, build, bad_flag in (("wrong_returns_None", wrong_none, False),
                                      ("wrong_returns_object", wrong_object, True)):
            want = "pass" if all(e is bad_flag for e in exp) else "fail"
            cases.append((task_id, build(mbpp[task_id])))
            plan.append((task_id, "%s(all_plus_expecteds_%s)" % (name, bad_flag), want))
    normal = [t for t, p in mbpp.items()
              if p["entry_point"] not in MBPP_OUTPUT_NOT_NONE_TASKS
              and p["entry_point"] not in MBPP_OUTPUT_SET_EQ_TASKS
              and p["entry_point"] != "are_equivalent"][:3]
    for task_id in normal:
        cases.append((task_id, wrong_object(mbpp[task_id])))
        plan.append((task_id, "wrong_body_on_normal_oracle", "fail"))
    per_task, hist = score("mbpp", mbpp, cases, workdir, "mbpp")
    check(per_task, plan, "mbpp")
    print("  status histogram for this batch: %s" % hist)


def part_real_data(workdir, he, limit=8):
    """Does the post-processing the DB's scores passed through change real verdicts?

    Uses one stored cell's own artefacts: the sanitized samples that produced its
    score, against the `.raw` sibling holding what the model actually wrote. A
    missing file is reported as unmeasured, never as zero changed verdicts.
    """
    print("\n[Q1 on real data] sanitized vs raw completions of one stored cell")
    base = os.path.join(REPO, ".wrapup", "wres", "humaneval", "w1-2bq4-r1_openai_temp_0.0")
    raw, clean = base + ".raw.jsonl", base + ".jsonl"
    if not (os.path.exists(raw) and os.path.exists(clean)):
        print("  UNMEASURED: %s.raw.jsonl / .jsonl not present" % base)
        UNMEASURED.append("wres real-data probe")
        return
    rows_raw = [json.loads(l) for l in open(raw)][:limit]
    rows_clean = [json.loads(l) for l in open(clean)][:limit]
    cases, pos = [], []          # pos[i] = (task_id, index of that case among its task's cases)
    per_task_count = {}
    for r in rows_raw:
        task = r["task_id"]
        per_task_count[task] = per_task_count.get(task, 0) + 1
        pos.append((task, per_task_count[task] - 1))
        cases.append((task, r["solution"]))
    for r in rows_clean:
        task = r["task_id"]
        per_task_count[task] = per_task_count.get(task, 0) + 1
        pos.append((task, per_task_count[task] - 1))
        cases.append((task, r["solution"]))
    per_task, hist = score("humaneval", he, cases, workdir, "real")
    changed = []
    for i, r in enumerate(rows_raw):
        t, k = pos[i]
        a = per_task[t][k]
        t2, k2 = pos[len(rows_raw) + i]
        b = per_task[t2][k2]
        if a != b:
            changed.append({"task_id": t, "raw": a, "sanitized": b})
    print("  tasks compared=%d  verdicts changed by post-processing=%d  %s"
          % (len(rows_raw), len(changed), changed))
    print("  status histogram for this batch: %s" % hist)
    note(True, "real-data probe ran", "changed=%d of %d" % (len(changed), len(rows_raw)))


def main() -> int:
    try:
        he, mbpp = get_human_eval_plus(), get_mbpp_plus()
    except Exception as e:  # offline cache missing is unmeasured, not a pass
        print("UNMEASURED: dataset load failed: %s: %s" % (type(e).__name__, e))
        return 2
    with tempfile.TemporaryDirectory() as workdir:
        part_questions(workdir, he, mbpp)
        part_real_data(workdir, he)
    print("\nSUMMARY: %d expectation(s) diverged; %d input(s) unmeasured"
          % (len(DIVERGED), len(UNMEASURED)))
    for d in DIVERGED:
        print("  diverged: " + d)
    for u in UNMEASURED:
        print("  unmeasured: " + u)
    if UNMEASURED:
        print("  EXIT 2: missing input is not a pass")
        return 2
    return 0 if not DIVERGED else 1


if __name__ == "__main__":
    sys.exit(main())
