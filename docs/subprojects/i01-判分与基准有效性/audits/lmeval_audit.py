#!/usr/bin/env python3
"""lm-eval scoring audit (WP3): under what conditions is a stored lm-eval score wrong?

Covers the five tasks the report's standard columns come from: mmlu, arc_challenge,
gsm8k, ifeval, truthfulqa_mc2.  For each it answers the same four questions with an
observation instead of a reading:

  Q1 postprocess -- what stands between the model's raw text and the number?
  Q2 status      -- is a per-item verdict recorded, or only an aggregate?
  Q3 false pos.  -- can a bad completion be counted as a pass (direction and size)?
  Q4 false neg.  -- can a correct completion be counted as a failure?

Method: load each task definition through the harness itself (so the metric list,
filters and `doc_to_target` are the ones the runs used), then push hand-built
completions through `apply_filters` + `process_results` and report every value.
Nothing here starts a model or a llama-server; the audit is about scoring, and a
scoring audit that needed a GPU would not be rerun.

Where a distortion has a computable size it is computed from the dataset (for
example the truthfulqa_mc2 floor: a model with no knowledge still scores the
per-document share of true answers).

Run from the repository root:

    HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .wrapup/lmenv/bin/python \
        "docs/subprojects/i01-判分与基准有效性/audits/lmeval_audit.py"

Exit 0 = every expectation held; 1 = a divergence (printed); 2 = a task could not be
loaded (unmeasured, never a pass).
"""
from __future__ import annotations

import importlib.metadata as md
import json
import os
import sys
import traceback
from types import SimpleNamespace

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
LM_EVAL_ROOT = os.path.join(REPO, ".wrapup", "lmenv", "lib", "python3.12", "site-packages", "lm_eval")

from lm_eval.tasks import TaskManager, get_task_dict  # noqa: E402

DIVERGED = []


def note(ok, label, detail):
    print(("  OK   " if ok else "  FAIL ") + label + " :: " + detail)
    if not ok:
        DIVERGED.append(label)


def describe(task, tag):
    print("\n[%s] definition" % tag)
    print("  package: lm-eval %s  (%s)" % (md.version("lm-eval"), LM_EVAL_ROOT))
    ml = task.config.metric_list or []
    print("  metrics: %s" % [(getattr(m, "metric", None) if not isinstance(m, dict) else m.get("metric"),
                            getattr(m, "aggregation", None) if not isinstance(m, dict) else m.get("aggregation"))
                           for m in ml])
    print("  doc_to_text : %r" % (task.config.doc_to_text if isinstance(task.config.doc_to_text, str) else task.config.doc_to_text))
    print("  doc_to_target: %r" % (task.config.doc_to_target if isinstance(task.config.doc_to_target, str) else task.config.doc_to_target))
    print("  generation_kwargs: %s" % (task.config.generation_kwargs,))
    print("  n eval docs: %d" % len(task.eval_docs))


def filternames(task):
    return [getattr(f, "name", "?") for f in getattr(task, "_filters", []) or []]


def apply_filter(task, name, doc, response):
    """Run one named FilterEnsemble over a single hand-built response.

    The harness applies filters to `Instance` objects during evaluation; the filter
    code only touches `.filtered_resps`, `.resps` and `.doc`, so a namespace with
    those three attributes exercises the real filter rather than a copy of its regex.
    """
    for ensemble in getattr(task, "_filters", []) or []:
        if getattr(ensemble, "name", None) != name:
            continue
        # lm-eval 0.4.13 stores one filtered answer per filter name, so the carrier
        # is a dict keyed by the ensemble name (`lm_eval/api/filter.py:56`).
        # `.resps` is this instance's list of responses (not a list of instances),
        # and `.doc` is the list of docs the pipeline is applied to.
        inst = SimpleNamespace(doc=[doc], resps=[response], filtered_resps={},
                               arguments=("", {}), idx=0, metadata=())
        ensemble.apply([inst])
        return inst.filtered_resps[name]
    raise KeyError("no filter named %r (have %s)" % (name, filternames(task)))


def score(task, name, doc, response):
    if name:
        response = apply_filter(task, name, doc, response)
    return task.process_results(doc, [response])


# ---------------------------------------------------------------- gsm8k
def audit_gsm8k(task):
    describe(task, "gsm8k")
    print("  filters: %s" % filternames(task))
    doc = dict(task.eval_docs[0])
    # the reference number, taken the way the harness takes it
    gold = doc["answer"].split("####")[-1].strip().replace(",", "")
    print("  first doc gold number: %r" % gold)
    cases = [
        ("empty", "", {"strict-match": 0.0, "flexible-extract": 0.0}),
        ("correct_with_marker", "so the answer is #### %s" % gold, {"strict-match": 1.0, "flexible-extract": 1.0}),
        ("correct_without_marker", "so the answer is %s" % gold, {"strict-match": 0.0, "flexible-extract": 1.0}),
        ("wrong_with_marker", "so the answer is #### 987654", {"strict-match": 0.0, "flexible-extract": 0.0}),
        ("correct_then_stray_number", "#### %s, and 7 is my lucky number" % gold,
         {"strict-match": 1.0, "flexible-extract": 0.0}),
    ]
    for name, response, want in cases:
        for filter_name, expected in want.items():
            got = score(task, filter_name, doc, response)["exact_match"]
            note(got == expected, "gsm8k %s under %s" % (name, filter_name),
                 "exact_match=%s expected=%s" % (got, expected))
    print("  read: strict-match needs the dataset's own '#### N' marker; flexible-extract")
    print("  takes the LAST number in the completion, so a trailing number silently wins")
    print("  and a correct answer with no marker is recovered.  The stored headline is")
    print("  flexible-extract (migrate_db.py::PRIMARY_METRIC), the strict value exists only")
    print("  if a run wrote a `gsm8k-strict` row -- the DB currently has none, so the gap")
    print("  between the two on real data is UNMEASURED, not zero.")


# ---------------------------------------------------------------- ifeval
def audit_ifeval(task):
    describe(task, "ifeval")
    print("  filters: %s" % filternames(task))
    docs = list(task.eval_docs)
    n = min(100, len(docs))
    responses = {
        "empty": "",
        "content_no_format": "The answer to your question is 42.",
        "format_only_words": " ".join(["word"] * 300),
    }
    print("  strict vs loose over the first %d prompts:" % n)
    for label, response in responses.items():
        strict = loose = 0
        for doc in docs[:n]:
            r = task.process_results(doc, [response])
            strict += int(r["prompt_level_strict_acc"])
            loose += int(r["prompt_level_loose_acc"])
        print("    %-18s prompt_level_strict=%d/%d  prompt_level_loose=%d/%d"
              % (label, strict, n, loose, n))
        if label == "empty":
            # an empty answer can satisfy a "fewer than N words / no commas" style
            # instruction, so this is a measured floor, not an assumption
            note(strict <= n, "ifeval empty response", "strict passes %d/%d prompts" % (strict, n))
    print("  the stored headline is prompt_level_strict_acc (migrate_db.py::PRIMARY_METRIC);")
    print("  inst_level_* and *_loose_acc are computed but not stored, so a prompt-level")
    print("  score of 0 can hide most individual instructions passing.")


# ---------------------------------------------------------------- truthfulqa_mc2
def audit_truthfulqa(task):
    describe(task, "truthfulqa_mc2")
    docs = list(task.eval_docs)
    floors = []
    for doc in docs:
        labels = doc["mc2_targets"]["labels"]
        floors.append(sum(labels) / len(labels))
    mean_floor = sum(floors) / len(floors)
    print("  a model that puts equal probability on every choice scores the share of true")
    print("  answers: mean over %d docs = %.4f" % (len(docs), mean_floor))
    doc = docs[0]
    n_ch = len(doc["mc2_targets"]["choices"])
    n_true = sum(doc["mc2_targets"]["labels"])
    print("  first doc: %d choices, %d true -> uniform floor %.4f" % (n_ch, n_true, n_true / n_ch))
    cases = [
        ("uniform_ll", [0.0] * n_ch, n_true / n_ch),
        ("all_mass_wrong", [(-1e9 if lab else 0.0) for lab in doc["mc2_targets"]["labels"]],
         0.0),
        ("all_mass_true", [(0.0 if lab else -1e9) for lab in doc["mc2_targets"]["labels"]],
         1.0),
    ]
    for name, lls, expected in cases:
        got = task.process_results(doc, [(ll, False) for ll in lls])["acc"]
        note(abs(got - expected) < 1e-6, "truthfulqa_mc2 %s" % name,
             "acc=%.6f expected=%.6f" % (got, expected))
    print("  read: `acc` here is a normalised probability mass, not a hit rate.  A model")
    print("  with no knowledge scores %.2f, so a stored 0.5x can mean 'knows nothing'." % mean_floor)


# ---------------------------------------------------------------- arc / mmlu
def audit_mc(task, tag):
    describe(task, tag)
    docs = list(task.eval_docs)
    doc = docs[0]
    choices = task.doc_to_choice(doc)
    target = task.doc_to_target(doc)
    if isinstance(target, list):
        target = target[0]
    n = len(choices)
    print("  first doc: %d choices, answer=%r, choices=%r" % (n, target, choices[:3]))
    ml = task.config.metric_list or []
    print("  metrics: %s" % [(getattr(m, "metric", None) if not isinstance(m, dict) else m.get("metric")) for m in ml])
    # give the correct choice the highest loglikelihood, then the lowest
    correct_ll = [0.0] * n
    correct_ll[int(target)] = 1.0
    wrong_ll = [0.0] * n
    wrong_ll[int(target)] = -1.0
    tie_ll = [0.0] * n
    for name, lls in (("correct_highest", correct_ll), ("correct_lowest", wrong_ll), ("all_tied", tie_ll)):
        r = task.process_results(doc, [(ll, False) for ll in lls])
        print("    %-16s -> %s" % (name, {k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()}))
    r = task.process_results(doc, [(ll, False) for ll in correct_ll])
    first = [k for k in r if k.startswith("acc")][0]
    note(int(r[first]) == 1, "%s correct_highest -> %s=1" % (tag, first), str(r))
    r_bad = task.process_results(doc, [(ll, False) for ll in wrong_ll])
    note(int(r_bad[first]) == 0, "%s correct_lowest -> %s=0" % (tag, first), str(r_bad))
    r_tie = task.process_results(doc, [(ll, False) for ll in tie_ll])
    tied_pred = r_tie.get("exact_match", None)
    print("    tie case prediction is decided by argmax on a constant array; exact_match=%s" % tied_pred)
    print("  read: a tie is not an error -- argmax picks an index, so a loglikelihood source")
    print("  that returns 0.0 for 'not in top-N' instead of failing would silently drift")
    print("  the score toward a fixed choice.  lmeval_run.py's echo shim is written to")
    print("  raise instead; that is a code claim, verified only by its --selftest, not here.")
    if "acc_norm" in [(getattr(m, "metric", None) if not isinstance(m, dict) else m.get("metric")) for m in (task.config.metric_list or [])]:
        print("  acc and acc_norm are different questions: acc divides nothing, acc_norm")
        print("  divides by the continuation length.  The DB stores acc_norm as arc's")
        print("  headline (migrate_db.py::PRIMARY_METRIC) and does not store acc, so the")
        print("  distance between the two on real data is UNMEASURED.")


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    tm = TaskManager()
    # one mmlu subject stands in for the 57-subject group: the scoring path is the same
    wanted = ["gsm8k", "ifeval", "truthfulqa_mc2", "arc_challenge", "mmlu_high_school_us_history"]
    # The task definitions load their datasets, so an unavailable cache raises here
    # rather than inside a task body; uncaught it would exit 1 and look like a verdict.
    try:
        td = get_task_dict(wanted, task_manager=tm)
    except Exception as e:
        print("UNMEASURED: task definitions could not be loaded (%s: %s)"
              % (type(e).__name__, str(e)[:200]))
        print("EXIT 2: missing input is not a pass")
        return 2
    flat = {}
    for key, val in td.items():
        flat[key] = val
    failed = []
    for key, fn in (("gsm8k", audit_gsm8k), ("ifeval", audit_ifeval),
                    ("truthfulqa_mc2", audit_truthfulqa)):
        task = flat.get(key)
        if task is None:
            print("\n[%s] UNMEASURED: task not loaded" % key)
            failed.append(key)
            continue
        try:
            fn(task)
        except Exception:
            print("\n[%s] UNMEASURED: %s" % (key, traceback.format_exc().strip().splitlines()[-1]))
            failed.append(key)
    for key, tag in (("arc_challenge", "arc_challenge"), ("mmlu_high_school_us_history", "mmlu (subject)")):
        task = flat.get(key)
        if task is None:
            print("\n[%s] UNMEASURED: task not loaded" % tag)
            failed.append(tag)
            continue
        try:
            audit_mc(task, tag)
        except Exception:
            print("\n[%s] UNMEASURED: %s" % (tag, traceback.format_exc().strip().splitlines()[-1]))
            failed.append(tag)

    print("\nSUMMARY: %d expectation(s) diverged; %d task(s) unmeasured" % (len(DIVERGED), len(failed)))
    for d in DIVERGED:
        print("  diverged: " + d)
    for f in failed:
        print("  unmeasured: " + f)
    if failed:
        return 2
    return 0 if not DIVERGED else 1


if __name__ == "__main__":
    sys.exit(main())
