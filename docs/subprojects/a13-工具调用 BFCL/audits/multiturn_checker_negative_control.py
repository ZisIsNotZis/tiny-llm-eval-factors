#!/usr/bin/env python3
"""Multi-turn BFCL: does the official checker actually fail when it should?

i01's BFCL audit covered the single-turn matcher with executable negative controls but left the
multi-turn checker as "read from the code, not probed" (`audits/bfcl.md` §未测 2). This closes
that gap with four controls on one real dataset entry, using the bundled
`multi_turn_checker` exactly as `.wrapup/bfcl_multi_run.py` calls it -- no re-implementation:

  P  ground truth replayed as the model answer            -> must PASS  (positive control)
  A  same calls, one argument mutated (state differs)     -> must FAIL  (well-formed but wrong)
  B  same answer, one call string malformed (bad format)  -> must not PASS (fail or raise)
  C  no calls at all                                      -> must FAIL  (doing nothing is not a pass)

A checker that cannot be made to fail is not evidence, and a checker that fails everything is not
one either, which is why P is part of the control set.

Run (CPU only, no GPU, no network; needs the bfclenv interpreter):
  .wrapup/bfclenv/bin/python "docs/subprojects/a13-工具调用 BFCL/audits/multiturn_checker_negative_control.py"

Exit: 0 every control behaved as required; 2 input missing; 4 a control did not behave.
"""
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WRAPUP = REPO / ".wrapup"
SITE = WRAPUP / "bfclenv/lib/python3.11/site-packages"
DATA = SITE / "bfcl_eval/data"
ADIR = DATA / "possible_answer"

MISSING = [str(p) for p in (SITE, DATA, ADIR) if not p.exists()]
if MISSING:
    sys.stderr.write(f"MISSING INPUT: {MISSING}\n")
    sys.exit(2)

sys.path.insert(0, str(SITE))
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import (  # noqa: E402
    multi_turn_checker,
)

CATEGORY = "multi_turn_base"
MODEL_NAME = "Qwen/Qwen3-1.7B-FC"


def load_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def checker_verdict(decoded, gt, entry):
    """Run the bundled checker; an exception counts as 'did not pass' and is reported."""
    try:
        res = multi_turn_checker(decoded, gt, entry, CATEGORY, MODEL_NAME)
        return bool(res.get("valid")), res.get("error_type"), None
    except Exception as exc:  # noqa: BLE001 -- a raise is a verdict too, and must be visible
        return False, None, f"{type(exc).__name__}: {exc}"


def mutate_one_argument(turns):
    """Return a copy with one argument value changed -> same shape, different outcome.

    Quoted strings first (the multi-turn fixtures are file/API calls whose arguments are names),
    then integers. The mutation keeps the call syntactically valid, so a FAIL here can only come
    from the executed state, not from a parse error.
    """
    out = [list(x) for x in turns]
    for pattern, bump in ((r"='([^']*)'", lambda v: v + "_x"), (r"=(\d+)", lambda v: str(int(v) + 1))):
        for t, turn in enumerate(turns):
            for i, call in enumerate(turn):
                m = re.search(pattern, call)
                if m:
                    new = call[:m.start(1)] + bump(m.group(1)) + call[m.end(1):]
                    out[t][i] = new
                    return out, f"{call} -> {new}"
    return None, "no mutable argument found"


def break_one_call(turns):
    """Return a copy with one call string made syntactically invalid (same intent)."""
    for t, turn in enumerate(turns):
        for i, call in enumerate(turn):
            if "(" in call:
                out = [list(x) for x in turns]
                out[t][i] = call.rstrip(")")  # drop the closing paren
                return out, f"{call} -> {out[t][i]}"
    return None, "no call to break"


def main():
    entries = {e["id"]: e for e in load_jsonl(DATA / f"BFCL_v4_{CATEGORY}.json")}
    answers = {a["id"]: a["ground_truth"] for a in load_jsonl(ADIR / f"BFCL_v4_{CATEGORY}.json")}
    entry_id = next(i for i in answers if i in entries and answers[i] and any(answers[i]))
    entry, gt = entries[entry_id], answers[entry_id]

    # Replay the ground truth as the model answer: one step per turn holding that turn's calls.
    replay = [[list(turn)] for turn in gt]

    controls = []
    ok, err_type, exc = checker_verdict(replay, gt, entry)
    controls.append(("P ground_truth_replayed", True, ok, err_type, exc, ""))

    mutated, how = mutate_one_argument(gt)
    if mutated is None:
        controls.append(("A mutated_argument", False, None, None, how, "cannot build"))
    else:
        ok, err_type, exc = checker_verdict([[list(t)] for t in mutated], gt, entry)
        controls.append(("A mutated_argument", False, ok, err_type, exc, how))

    broken, how = break_one_call(gt)
    if broken is None:
        controls.append(("B malformed_call", False, None, None, how, "cannot build"))
    else:
        ok, err_type, exc = checker_verdict([[list(t)] for t in broken], gt, entry)
        controls.append(("B malformed_call", False, ok, err_type, exc, how))

    empty = [[] for _ in gt]
    ok, err_type, exc = checker_verdict(empty, gt, entry)
    controls.append(("C no_calls_at_all", False, ok, err_type, exc, ""))

    print(f"entry {entry_id}: {len(gt)} turns, {sum(len(t) for t in gt)} ground-truth calls")
    print(f"{'control':24s} {'want':>6s} {'got':>6s} {'verdict':>8s}  error_type / note")
    bad = 0
    for name, want_pass, got, err_type, exc, note in controls:
        verdict = "ok" if got is want_pass else "CONTROL FAILED"
        if got is not want_pass:
            bad += 1
        print(f"{name:24s} {str(want_pass):>6s} {str(got):>6s} {verdict:>8s}  "
              f"{err_type or exc or '-'}{('  | ' + note) if note else ''}")
    if bad:
        sys.stderr.write(f"{bad} control(s) did not behave as required\n")
        return 4
    print("PASS: the official multi-turn checker passes a correct replay and fails "
          "a wrong-state, a malformed and an empty answer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
