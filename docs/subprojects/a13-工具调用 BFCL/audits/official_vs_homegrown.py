#!/usr/bin/env python3
"""Single-turn BFCL, same predictions, two scorers.

Question it answers: if the official AST checker replaced the repo's homegrown matcher
(`.wrapup/bfcl_run.py::evaluate` / `call_ok` / `arg_ok`), which already-reported single-turn
numbers would move, in which direction, and by how much?

Inputs are the surviving prediction files, which are exactly what `bfcl_run.py eval` consumed:
  .wrapup/mres/m4-*.jsonl   non-live categories (5 per file)
  .wrapup/mres/m8-*.jsonl   live_* categories (6 per file)
So no model call and no regeneration is involved: only the judging differs, which is what makes
the delta attributable to the scorer rather than to generation.

Both scorers are invoked, not re-derived:
  homegrown = bfcl_run.call_ok / bfcl_run.arg_ok, plus evaluate()'s three-way branch
  official  = bfcl_eval.eval_checker.ast_eval.ast_checker.ast_checker (bundled bfcl-eval 2026.3.23)
              and, for the relevance/irrelevance categories, the rule in
              eval_runner.py::_evaluate_single_relevance_entry (presence of a decodable call).

The homegrown recomputation is checked against the recorded score in `experiments` for every
(file, category); a mismatch means this script no longer mirrors production and it exits 3.
Because that check binds each file to a (model, protocol) row, it also fixes which DB rows the
deltas apply to -- the binding is measured, not assumed.

Run (needs the bfclenv interpreter for the bundled checker, CPU only, no GPU, no network):
  .wrapup/bfclenv/bin/python "docs/subprojects/a13-工具调用 BFCL/audits/official_vs_homegrown.py"

Exit codes: 0 ok, 2 missing input, 3 homegrown no longer matches the recorded DB scores,
4 negative control failed (a scorer that cannot fail is not evidence).
"""
import glob
import hashlib
import itertools
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WRAPUP = REPO / ".wrapup"
MRES = WRAPUP / "mres"
SITE = WRAPUP / "bfclenv/lib/python3.11/site-packages"
DATA = SITE / "bfcl_eval/data"
ADIR = DATA / "possible_answer"
DB = Path(os.environ.get("A13_DB", REPO / "experiments.sqlite"))

MISSING = [str(p) for p in (MRES, SITE, DATA, ADIR, DB) if not p.exists()]
PRED_FILES = (sorted(glob.glob(str(MRES / "m4-*.jsonl"))) + sorted(glob.glob(str(MRES / "m8-*.jsonl")))
              + [str(MRES / "m22-bonsai.jsonl")])
if MISSING or not PRED_FILES:
    sys.stderr.write("MISSING INPUT: %s%s\n" % (MISSING or "no prediction files under .wrapup/mres"))
    sys.exit(2)

sys.path.insert(0, str(SITE))
sys.path.insert(0, str(WRAPUP))
from bfcl_eval.constants.enums import Language  # noqa: E402
from bfcl_eval.eval_checker.ast_eval.ast_checker import ast_checker  # noqa: E402
from bfcl_run import call_ok, arg_ok as arg_ok_imported  # noqa: E402  (the production matcher, not a copy)

MODEL_NAME = "Qwen/Qwen3-1.7B-FC"  # only reached by ast_checker's convert_func_name for names with "."; a valid config key
HOME_PROTO = "bfcl-native-tools-nothink-greedy"


def load_jsonl(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


GT_CACHE = {}


def ground_truth(cat):
    if cat not in GT_CACHE:
        path = ADIR / f"BFCL_v4_{cat}.json"
        GT_CACHE[cat] = {r["id"]: r["ground_truth"] for r in load_jsonl(path)} if path.exists() else None
    return GT_CACHE[cat]


def home_verdict(cat, calls, gt):
    """Mirror of bfcl_run.py::evaluate's per-item branch; the matcher itself is imported."""
    if "irrelevance" in cat:
        return len(calls) == 0
    if "relevance" in cat:
        return len(calls) > 0
    return len(calls) == len(gt) and all(any(call_ok(c, g) for c in calls) for g in gt)


def official_verdict(cat, calls, gt, func_desc):
    # Substring order matters and is copied from bfcl_run.py::evaluate: "irrelevance"
    # CONTAINS "relevance", so testing "relevance" first would invert every
    # irrelevance item (measured: -0.83 on m4-2bq3 before this order was fixed).
    if "irrelevance" in cat:
        return len(calls) == 0
    if "relevance" in cat:
        # eval_runner.py::_evaluate_single_relevance_entry: decode must succeed and be
        # non-empty; our calls are already decoded native tool calls, so presence is the test.
        return any(isinstance(c.get("arguments"), dict) for c in calls)
    if not calls:
        return False
    if any(not isinstance(c.get("arguments"), dict) for c in calls):
        return False  # decode_ast would raise on an unparseable argument object
    return bool(ast_checker(func_desc, [{c["name"]: c["arguments"]} for c in calls],
                            gt, Language.PYTHON, cat, MODEL_NAME)["valid"])


def home_fail_reason(cat, calls, gt, fd):
    """Why the homegrown matcher said FAIL on an item the official checker passed."""
    if len(calls) != len(gt):
        return "call_count"
    required = {d["name"]: set((d.get("parameters") or {}).get("required") or []) for d in fd}
    for g in gt:
        name, args = next(iter(g.items()))
        match = [c for c in calls if c.get("name") == name]
        if not match:
            return "wrong_name"
        c = match[0]
        pargs = c.get("arguments") if isinstance(c.get("arguments"), dict) else {}
        for k, accepted in args.items():
            if k not in pargs:
                # a key whose accepted list contains "" is optional in the official checker
                return "missing_required" if k in required.get(name, set()) else "missing_optional"
            if not any(arg_ok_imported(pargs[k], [a]) for a in accepted):
                return "value_or_type"
    return "other"


def official_error_type(cat, calls, gt, fd):
    if not calls:
        return "empty_output"
    if any(not isinstance(c.get("arguments"), dict) for c in calls):
        return "undecodable_arguments"
    r = ast_checker(fd, [{c["name"]: c["arguments"]} for c in calls], gt,
                    Language.PYTHON, cat, MODEL_NAME)
    return r.get("error_type") if not r["valid"] else "valid"


def evaluate_file(path):
    rows = load_jsonl(path)
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    out = {}
    for cat, items in sorted(by_cat.items()):
        gt_map = ground_truth(cat)
        presence_only = gt_map is None and ("irrelevance" in cat or "relevance" in cat)
        if gt_map is None and not presence_only:
            out[cat] = {"n": len(items), "comparable": False,
                        "reason": "no possible_answer in bundled dataset"}
            continue
        if presence_only:
            # These categories need no possible_answer on the official path either:
            # eval_runner.py::_evaluate_single_relevance_entry scores only "did a call
            # decode". Both verdicts are therefore computable here, so whether the swap
            # moves anything becomes a measurement instead of an argument.
            h = sum(home_verdict(cat, it.get("calls") or [], []) for it in items)
            o = sum(official_verdict(cat, it.get("calls") or [], [], []) for it in items)
            up = sum(1 for it in items
                     if home_verdict(cat, it.get("calls") or [], [])
                     and not official_verdict(cat, it.get("calls") or [], [], []))
            dn = sum(1 for it in items
                     if official_verdict(cat, it.get("calls") or [], [], [])
                     and not home_verdict(cat, it.get("calls") or [], []))
            out[cat] = {"n": len(items), "comparable": True, "presence_rule": True,
                        "home_correct": h, "official_correct": o,
                        "home_acc": h / len(items), "official_acc": o / len(items),
                        "delta": (o - h) / len(items),
                        "home_pass_official_fail": up, "official_pass_home_fail": dn,
                        "up_reasons": {"presence_rule": up} if up else {},
                        "down_reasons": {"presence_rule": dn} if dn else {},
                        "up_ids": [], "down_ids": []}
            continue
        prompts = {r["id"]: r for r in load_jsonl(DATA / f"BFCL_v4_{cat}.json")}
        home = off = 0
        up = down = 0
        up_ids, down_ids = [], []
        up_why, down_why = Counter(), Counter()
        for it in items:
            gt = gt_map.get(it["id"], [])
            fd = (prompts.get(it["id"]) or {}).get("function") or []
            calls = it.get("calls") or []
            h = home_verdict(cat, calls, gt)
            o = official_verdict(cat, calls, gt, fd) if fd or "relevance" in cat else False
            home += h
            off += o
            if h and not o:
                up += 1
                up_ids.append(it["id"])
                up_why[official_error_type(cat, calls, gt, fd)] += 1
            elif o and not h:
                down += 1
                down_ids.append(it["id"])
                down_why[home_fail_reason(cat, calls, gt, fd)] += 1
        out[cat] = {"n": len(items), "comparable": True,
                    "home_correct": home, "official_correct": off,
                    "home_acc": home / len(items), "official_acc": off / len(items),
                    "delta": (off - home) / len(items),
                    "home_pass_official_fail": up, "official_pass_home_fail": down,
                    "up_ids": up_ids[:10], "down_ids": down_ids[:10],
                    "up_reasons": dict(up_why), "down_reasons": dict(down_why)}
    return out, len(rows)


def bind(files):
    """Bind each file to a DB (model, protocol) by matching every category's homegrown accuracy."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT model, protocol, _bench, _score, n_items FROM experiments "
        "WHERE bench_family LIKE 'bfcl%' AND protocol LIKE 'bfcl%'").fetchall()
    con.close()
    by = defaultdict(dict)
    for model, proto, bench, score, n in rows:
        by[(model, proto)][bench.replace("bfcl-", "")] = (score, n)
    bound, unbound = {}, []
    for path, result in files.items():
        cands = []
        for (model, proto), cats in by.items():
            ok = True
            for cat, r in result.items():
                if not r.get("comparable", True):
                    continue
                got = cats.get(cat)
                # 库里的这一格要么还是自研值（入库前），要么已经是官方值（入库后）；
                # 两者都不匹配才说明文件与库格对不上。
                if got is None or not (abs(got[0] - r["home_acc"]) <= 1e-9
                                       or abs(got[0] - r["official_acc"]) <= 1e-9):
                    ok = False
                    break
            if ok:
                cands.append((model, proto))
        if len(cands) == 1:
            bound[path] = cands[0]
        else:
            unbound.append((os.path.basename(path), cands))
    return bound, unbound


def negative_control():
    """A scorer that cannot fail is not evidence: prove both directions on both scorers."""
    cat = "simple_python"
    gt_map = ground_truth(cat)
    prompts = {r["id"]: r for r in load_jsonl(DATA / f"BFCL_v4_{cat}.json")}
    tid = next(iter(gt_map))
    gt, fd = gt_map[tid], prompts[tid]["function"]
    name, args = next(iter(gt[0].items()))
    good = {"name": name, "arguments": {k: v[0] for k, v in args.items() if v and v[0] != ""}}
    cases = {
        "correct_call": (good, True, True),
        "wrong_name": ({"name": name + "__nosuch", "arguments": good["arguments"]}, False, False),
        "empty_calls": (None, False, False),
    }
    req = fd[0]["parameters"].get("required") or []
    if len(req) > 1:
        cases["missing_required"] = (
            {"name": name, "arguments": {k: v for k, v in good["arguments"].items() if k != req[-1]}},
            False, False)
    res = {}
    for label, (call, want_home, want_off) in cases.items():
        calls = [] if call is None else [call]
        h = home_verdict(cat, calls, gt)
        o = official_verdict(cat, calls, gt, fd)
        res[label] = {"home": h, "official": o, "want_home": want_home, "want_off": want_off,
                      "ok": h == want_home and o == want_off}
    return res


def main():
    results, meta = {}, {}
    for path in PRED_FILES:
        res, n = evaluate_file(path)
        results[path] = res
        meta[os.path.basename(path)] = {
            "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(), "records": n}
    bound, unbound = bind(results)
    ctrl = negative_control()
    ctrl_ok = all(v["ok"] for v in ctrl.values())

    doc = {"generated_by": "audits/official_vs_homegrown.py",
           "inputs": meta, "negative_control": ctrl,
           "binding": {os.path.basename(k): {"model": v[0], "protocol": v[1]}
                       for k, v in bound.items()},
           "unbound_or_ambiguous": unbound,
           "per_file": {os.path.basename(k): v for k, v in results.items()}}
    out = Path(__file__).with_name("official_vs_homegrown.json")
    # The evidence file is only replaced after every check passed: a drifted binding must leave
    # the tracked artifact untouched, otherwise a failing run destroys the thing it is meant to
    # be measured against.
    write_ok = not unbound and ctrl_ok

    # ---- report ----
    print("== negative control ==")
    for k, v in ctrl.items():
        print(f"  {k:18s} home={v['home']!s:5s} official={v['official']!s:5s} "
              f"{'ok' if v['ok'] else 'CONTROL FAILED'}")
    print("\n== per (file, category): homegrown vs official ==")
    hdr = f"{'file':22s} {'category':22s} {'n':>5s} {'home':>7s} {'official':>9s} {'delta':>8s} {'up':>4s} {'down':>5s}"
    print(hdr)
    for path in sorted(results):
        for cat, r in results[path].items():
            if not r.get("comparable", True):
                print(f"{os.path.basename(path):22s} {cat:22s} {r['n']:5d}   {'n/a':>7s} {'n/a':>9s} (no possible_answer)")
                continue
            print(f"{os.path.basename(path):22s} {cat:22s} {r['n']:5d} {r['home_acc']:7.4f} "
                  f"{r['official_acc']:9.4f} {r['delta']:+8.4f} {r['home_pass_official_fail']:4d} "
                  f"{r['official_pass_home_fail']:5d}  home-fail reasons={r['down_reasons']}")
    print("\n== binding of each prediction file to a DB (model, protocol) ==")
    for path in sorted(bound):
        print(f"  {os.path.basename(path):22s} -> {bound[path][0]:34s} {bound[path][1]}")
    for name, cands in unbound:
        print(f"  {name:22s} -> UNBOUND/AMBIGUOUS {cands}")
    print("\n== ranking effect on the 11 single-turn models (5 non-live categories, item-weighted) ==")
    agg = []
    for path, cats in results.items():
        if os.path.basename(path).startswith("m8-"):
            continue
        comp = {c: r for c, r in cats.items() if r.get("comparable", True)}
        if len(comp) < 4:
            continue
        h = sum(r["home_correct"] for r in comp.values()) / sum(r["n"] for r in comp.values())
        o = sum(r["official_correct"] for r in comp.values()) / sum(r["n"] for r in comp.values())
        if path not in bound:
            continue
        agg.append((bound[path][0], h, o))
    inv = []
    for a, b in itertools.combinations(agg, 2):
        if (a[1] - b[1]) * (a[2] - b[2]) < 0:
            inv.append((a[0], b[0]))
    pairs = len(agg) * (len(agg) - 1) // 2
    for m, h, o in sorted(agg, key=lambda x: -x[1]):
        print(f"  {m:34s} home={h:.4f} official={o:.4f} delta={o - h:+.4f}")
    print(f"  pairwise inversions homegrown -> official: {len(inv)}/{pairs}")
    for a, b in inv:
        print(f"    inverted: {a} vs {b}")
    if not write_ok:
        if unbound:
            print(f"\nFAIL: {len(unbound)} prediction file(s) could not be bound to exactly one "
                  f"DB row set -- evidence file NOT rewritten ({out.name} unchanged)")
            return 3
        print(f"\nFAIL: negative control did not behave -- evidence file NOT rewritten "
              f"({out.name} unchanged)")
        return 4
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, out)
    print(f"\nwrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
