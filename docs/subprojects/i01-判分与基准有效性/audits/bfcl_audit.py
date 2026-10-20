#!/usr/bin/env python3
"""BFCL scoring audit (WP4): under what conditions is a stored BFCL number wrong?

Two things a reader of the report cannot tell from the report:

  1. the single-turn categories are NOT scored by the bundled BFCL evaluator -- they
     are scored by `.wrapup/bfcl_run.py::evaluate` (a hand-written name+argument
     matcher), while the multi-turn categories ARE scored by the bundled official
     `multi_turn_checker`.  So "BFCL 0.6x" mixes two scoring implementations.
  2. the per-category rows carry no item count in the database (`n_items` is NULL),
     and the two natural aggregates differ: item-weighted (micro, what the panel
     summary's `score` is) and category-weighted (macro, what averaging the stored
     rows gives).  On a stored live panel the gap reaches 17 points, because
     `live_irrelevance` is 39% of the items and rewards silence.

Method: take real records and real ground truth out of the bundled dataset, craft the
completion whose verdict is in question, and run the shipped scorer
(`.wrapup/bfcl_run.py eval`) on it -- one invocation per case, so each verdict is
attributable.  Expectations include the *bypasses* (a case that must be scored as a
pass although the call is wrong), so the day the scorer is fixed this audit fails
instead of silently agreeing with it.

Run from the repository root (no GPU, no model, no network):

    python3 "docs/subprojects/i01-判分与基准有效性/audits/bfcl_audit.py"

Exit 0 = every expectation held; 1 = a divergence (printed); 2 = the bundled dataset
is missing (unmeasured, never a pass).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DATA = os.path.join(REPO, ".wrapup", "bfclenv", "lib", "python3.11", "site-packages", "bfcl_eval", "data")
SCORER = os.path.join(REPO, ".wrapup", "bfcl_run.py")
DIVERGED = []


def note(ok, label, detail):
    print(("  OK   " if ok else "  FAIL ") + label + " :: " + detail)
    if not ok:
        DIVERGED.append(label)


def load_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def score_one(category, doc_id, calls, workdir):
    """Run the shipped scorer on one (category, id, predicted calls) and return pass."""
    samples = os.path.join(workdir, "s.jsonl")
    out = os.path.join(workdir, "s_eval.json")
    with open(samples, "w") as f:
        f.write(json.dumps({"id": doc_id, "category": category, "calls": calls, "raw": ""}) + "\n")
    r = subprocess.run([sys.executable, SCORER, "eval", "--samples", samples, "--out", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("scorer failed: %s" % (r.stderr[-400:]))
    d = json.load(open(out))
    return d["correct"] == 1, d


def case(workdir, category, doc_id, calls, expect_pass, why):
    got, d = score_one(category, doc_id, calls, workdir)
    note(got == expect_pass, "%s %s" % (category, why),
         "scored %s expected %s (n=%d correct=%d)"
         % ("PASS" if got else "FAIL", "PASS" if expect_pass else "FAIL", d["n"], d["correct"]))
    return got


def gt_to_call(gt_list):
    """[{"fn": {"arg": [accepted...]}}] -> the call a perfect model would emit."""
    call = {"name": None, "arguments": {}}
    for entry in gt_list:
        for name, args in entry.items():
            call["name"] = name
            for k, accepted in args.items():
                call["arguments"][k] = accepted[0]
    return call


def main() -> int:
    if not os.path.isdir(DATA):
        print("UNMEASURED: bundled BFCL dataset not found at %s" % DATA)
        return 2
    print("scorer: %s (single-turn, in-repo); ground truth: %s" % (SCORER, DATA))
    print("shape of one ground-truth record:")
    sp = os.path.join(DATA, "possible_answer", "BFCL_v4_simple_python.json")
    sp_rows = load_jsonl(sp)
    print("  %s" % json.dumps(sp_rows[0], ensure_ascii=False)[:200])
    doc_id = sp_rows[0]["id"]
    gt = gt_to_call(sp_rows[0]["ground_truth"])
    print("  a perfect model would emit: %s" % json.dumps(gt, ensure_ascii=False))

    with tempfile.TemporaryDirectory() as wd:
        print("\n[single-turn] ordinary categories, name + argument matching:")
        case(wd, "simple_python", doc_id, [gt], True, "gt_verbatim")
        wrong = json.loads(json.dumps(gt))
        first_arg = sorted(wrong["arguments"])[0]
        wrong["arguments"][first_arg] = "definitely-not-the-accepted-value"
        case(wd, "simple_python", doc_id, [wrong], False, "wrong_argument_value")
        case(wd, "simple_python", doc_id, [{"name": "not_a_function", "arguments": {}}], False,
             "wrong_function_name")
        case(wd, "simple_python", doc_id, [], False, "empty_when_a_call_is_required")
        case(wd, "simple_python", doc_id, [gt, gt], False, "duplicated_call")

        print("\n[single-turn] the two loopholes in the matcher:")
        # arg_ok() falls back to float(pred) == float(accepted), so a string passes a
        # numeric ground truth; call_ok() only iterates the ground truth's keys, so an
        # extra argument is never examined.
        # `arg_ok` is not type-tolerant the way its docstring suggests: the float()
        # coercion is applied to the ACCEPTED value only, so a number emitted where the
        # ground truth is a string passes, the reverse does not, and a boolean passes a
        # ground truth of 1 because Python says True == 1.0.
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("bfcl_run", SCORER)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            probes = [
                ("number_for_string_gt", 10, ["10"], True),
                ("string_for_number_gt", "10", [10], False),
                ("case_and_space_folded", " New York ", ["new york"], True),
                ("boolean_for_numeric_1", True, [1], True),
            ]
            for name, pred, accepted, want in probes:
                got = mod.arg_ok(pred, accepted)
                note(got == want, "arg_ok %s" % name,
                     "arg_ok(%r, %r) = %s expected %s" % (pred, accepted, got, want))
        except Exception as e:
            print("  UNMEASURED: arg_ok probes failed (%s)" % e)
        extra = json.loads(json.dumps(gt))
        extra["arguments"]["an_argument_that_does_not_belong"] = 999
        case(wd, "simple_python", doc_id, [extra], True, "extra_wrong_argument")

        print("\n[irrelevance] the category that rewards silence:")
        irr_path = os.path.join(DATA, "BFCL_v4_irrelevance.json")
        irr = load_jsonl(irr_path)[0]
        case(wd, "irrelevance", irr["id"], [], True, "no_call")
        case(wd, "irrelevance", irr["id"], [{"name": "any_function", "arguments": {}}], False,
             "any_call_at_all")

        print("\n[live_relevance] the category whose ground truth is missing:")
        rel_gt = os.path.join(DATA, "possible_answer", "BFCL_v4_live_relevance.json")
        rel_path = os.path.join(DATA, "BFCL_v4_live_relevance.json")
        if os.path.exists(rel_gt):
            print("  UNMEASURED: a possible_answer file now exists for live_relevance, so the")
            print("  bypass below may have been fixed upstream; re-derive the expectation.")
        elif os.path.exists(rel_path):
            rel = load_jsonl(rel_path)[0]
            print("  %s ships no possible_answer file: %s exists=%s"
                  % ("live_relevance", rel_gt, os.path.exists(rel_gt)))
            print("  the scorer therefore checks only that SOME call was made (`len(calls) > 0`).")
            case(wd, "live_relevance", rel["id"], [], False, "no_call")
            case(wd, "live_relevance", rel["id"],
                 [{"name": "a_function_that_does_not_exist", "arguments": {"x": 1}}], True,
                 "wrong_call_still_passes")
        else:
            print("  UNMEASURED: live_relevance questions not present in this dataset build")

    print("\n[aggregation] stored panels: item-weighted (micro) vs category-weighted (macro)")
    overall = []
    for f in ("m4b_summary.jsonl", "m8_summary.jsonl"):
        path = os.path.join(REPO, ".wrapup", f)
        if not os.path.exists(path):
            print("  UNMEASURED: %s absent" % f)
            continue
        rows = []
        for line in open(path):
            d = json.loads(line)
            pc = d["per_category"]
            tot = sum(v["n"] for v in pc.values())
            micro = sum(v["acc"] * v["n"] for v in pc.values()) / tot
            macro = sum(v["acc"] for v in pc.values()) / len(pc)
            biggest = max(pc.items(), key=lambda kv: kv[1]["n"])
            rows.append((abs(micro - macro), d["model"], micro, macro, tot, biggest))
        worst = max(rows)
        gap, model, micro, macro, tot, biggest = worst
        print("  %-20s rows=%d  worst: model=%s micro=%.4f macro=%.4f gap=%.4f "
              "(n=%d; largest category %s %d items)"
              % (f, len(rows), model, micro, macro, gap, tot, biggest[0], biggest[1]["n"]))
        overall.append((gap, f, model, micro, macro))
    if overall:
        gap, f, model, micro, macro = max(overall)
        note(gap > 0.05, "the two aggregates differ materially somewhere",
             "worst gap=%.4f (%s model=%s: micro=%.4f macro=%.4f)" % (gap, f, model, micro, macro))

    print("\n[database] can the stored rows reproduce either aggregate?")
    try:
        import sqlite3
        con = sqlite3.connect("file:%s?mode=ro" % os.path.join(REPO, "experiments.sqlite"), uri=True)
        nulls = con.execute("SELECT count(*) FROM experiments WHERE bench_family LIKE 'bfcl%' "
                            "AND n_items IS NULL").fetchone()[0]
        total = con.execute("SELECT count(*) FROM experiments WHERE bench_family LIKE 'bfcl%'").fetchone()[0]
        cats = con.execute("SELECT count(DISTINCT _bench) FROM experiments WHERE bench_family LIKE 'bfcl%'").fetchone()[0]
        print("  bfcl rows=%d, rows with n_items NULL=%d, distinct categories=%d" % (total, nulls, cats))
        note(nulls == total, "bfcl rows carry no item count",
             "%d/%d rows have n_items NULL, so a micro-average cannot be computed from the DB" % (nulls, total))
    except Exception as e:
        print("  UNMEASURED: database not readable (%s)" % e)

    print("\nSUMMARY: %d expectation(s) diverged" % len(DIVERGED))
    for d in DIVERGED:
        print("  diverged: " + d)
    return 0 if not DIVERGED else 1


if __name__ == "__main__":
    sys.exit(main())
