#!/usr/bin/env python3
"""Multi-turn BFCL runner (M9) for llama-server, using the bundled evaluator.

Runs the stateful multi-turn categories (multi_turn_base, multi_turn_long_context)
by driving a real tool loop: user turn -> model tool calls -> execute against the
bundled `func_source_code` classes -> feed results back -> next step/turn.

Scoring uses the bundled `multi_turn_checker` (final instance-state + execution-response
comparison) for a strict all-or-nothing pass, plus two continuous metrics computed here
for resolution: turn_match_rate (fraction of non-empty GT turns fully matched) and
call_rate (fraction of GT function calls matched by name+arguments).

Only native tool-calling mode is used, matching the M7/M8 protocol (greedy, thinking off).

Requires the bfclenv interpreter:
  .wrapup/bfclenv/bin/python .wrapup/bfcl_multi_run.py gen ...   (在仓库根执行)
"""
import argparse
import ast
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bfcl_run import fix_schema, tools_schema  # noqa: E402

from bfcl_eval.constants.executable_backend_config import (  # noqa: E402
    MULTI_TURN_FUNC_DOC_FILE_MAPPING,
)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import (  # noqa: E402
    execute_multi_turn_func_call,
)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import (  # noqa: E402
    multi_turn_checker,
)

DATA = os.path.join(HERE, "bfclenv/lib/python3.11/site-packages/bfcl_eval/data")
FUNCDOC = os.path.join(DATA, "multi_turn_func_doc")
ADIR = os.path.join(DATA, "possible_answer")


def load_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def post(url, payload, timeout=600):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def build_function_list(entry):
    funcs = []
    for cls in entry["involved_classes"]:
        funcs.extend(load_jsonl(os.path.join(FUNCDOC, MULTI_TURN_FUNC_DOC_FILE_MAPPING[cls])))
    return funcs


def fmt_call(name, args):
    parts = [f"{k}={repr(v)}" for k, v in (args or {}).items()]
    return f"{name}({', '.join(parts)})"


def parse_tool_calls(msg):
    calls = []
    for c in (msg.get("tool_calls") or []):
        fn = c.get("function", {})
        try:
            a = json.loads(fn.get("arguments") or "{}")
        except Exception:
            a = {}
        if not isinstance(a, dict):
            a = {}
        calls.append({"id": c.get("id") or f"call_{len(calls)}",
                      "name": fn.get("name"), "arguments": a})
    return calls


def run_entry(entry, base, tools, max_tokens, max_steps, model_name, tag):
    """Drive one multi-turn conversation; return (per-turn step call-strings, raw log)."""
    initial_config = entry.get("initial_config", {})
    involved = entry["involved_classes"]
    cat = entry["id"].rsplit("_", 1)[0]
    long_context = "long_context" in cat
    messages = []
    turn_results = []
    raw_log = []
    for turn in entry["question"]:
        for m in turn:
            messages.append({"role": m["role"], "content": m["content"]})
        steps = []
        for _step in range(max_steps):
            payload = {"messages": messages, "temperature": 0.0,
                       "max_tokens": max_tokens, "tools": tools,
                       "chat_template_kwargs": {"enable_thinking": False}}
            try:
                r = post(base + "/v1/chat/completions", payload)
            except Exception as e:
                raw_log.append({"error": str(e)})
                break
            msg = r["choices"][0]["message"]
            calls = parse_tool_calls(msg)
            raw_log.append({"assistant": (msg.get("content") or "")[:500],
                            "calls": [{"name": c["name"], "arguments": c["arguments"]} for c in calls]})
            if not calls:
                break
            callstrs = [fmt_call(c["name"], c["arguments"]) for c in calls]
            steps.append(callstrs)
            results, _ = execute_multi_turn_func_call(
                callstrs, initial_config, involved, model_name, entry["id"],
                long_context=long_context, is_evaL_run=False)
            assistant_msg = {"role": "assistant", "content": msg.get("content") or "",
                             "tool_calls": [
                                 {"id": c["id"], "type": "function",
                                  "function": {"name": c["name"],
                                               "arguments": json.dumps(c["arguments"])}}
                                 for c in calls]}
            messages.append(assistant_msg)
            for c, res in zip(calls, results):
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": str(res)})
        turn_results.append(steps)
    return turn_results, raw_log


# ---------- continuous metrics ----------

def _ordered_params(entry, fname):
    for cls in entry["involved_classes"]:
        for fd in load_jsonl(os.path.join(FUNCDOC, MULTI_TURN_FUNC_DOC_FILE_MAPPING[cls])):
            if fd["name"] == fname:
                return list((fd.get("parameters") or {}).get("properties", {}).keys())
    return None


def parse_gt_call(s, entry):
    """('name', {arg: value}) for a GT call string; positional args mapped by doc order."""
    node = ast.parse(s, mode="eval").body
    if not isinstance(node, ast.Call):
        return None, None
    name = node.func.id if isinstance(node.func, ast.Name) else (
        node.func.attr if isinstance(node.func, ast.Attribute) else None)
    args = {}
    for kw in node.keywords:
        args[kw.arg] = ast.literal_eval(kw.value)
    if node.args:
        order = _ordered_params(entry, name) or []
        for i, a in enumerate(node.args):
            key = order[i] if i < len(order) else f"_{i}"
            args[key] = ast.literal_eval(a)
    return name, args


def norm_val(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return v.strip().lower()
    return v


def call_matches(gt_name, gt_args, model_calls):
    for mc in model_calls:
        if mc["name"] != gt_name:
            continue
        ma = mc["arguments"]
        if all(k in ma and norm_val(ma[k]) == norm_val(v) for k, v in gt_args.items()):
            return True
    return False


def continuous_metrics(decoded, gt, entry):
    """decoded: list[turn] of list[step] of [callstr]; gt: list[turn] of [gt callstr]."""
    total = matched = 0
    turns_nonempty = turns_full = 0
    for t, gt_calls in enumerate(gt):
        model_calls = [c for step in decoded[t] for c in step]
        # model calls as dicts
        model_parsed = []
        for s in model_calls:
            # s is a string like name(k=v); parse via ast
            try:
                n, a = parse_gt_call(s, entry)
                model_parsed.append({"name": n, "arguments": a})
            except Exception:
                pass
        if gt_calls:
            turns_nonempty += 1
            hits = 0
            for s in gt_calls:
                try:
                    n, a = parse_gt_call(s, entry)
                except Exception:
                    n, a = None, None
                total += 1
                if n is not None and call_matches(n, a, model_parsed):
                    matched += 1
                    hits += 1
            if hits == len(gt_calls):
                turns_full += 1
    return {
        "call_rate": matched / total if total else None,
        "turn_match_rate": turns_full / turns_nonempty if turns_nonempty else None,
        "n_gt_calls": total,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", default="multi_turn_base,multi_turn_long_context")
    ap.add_argument("--model", required=True, help="panel tag (used for instance names)")
    ap.add_argument("--samples", required=True)
    ap.add_argument("--base_url", default="http://127.0.0.1:8080")
    ap.add_argument("--max_tokens", type=int, default=512)
    ap.add_argument("--max_steps", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    gt_by_cat = {}
    for cat in args.categories.split(","):
        gt_by_cat[cat] = {r["id"]: r["ground_truth"]
                          for r in load_jsonl(os.path.join(ADIR, f"BFCL_v4_{cat}.json"))}

    out = []
    per_cat = {}
    t0 = time.time()
    for cat in args.categories.split(","):
        recs = load_jsonl(os.path.join(DATA, f"BFCL_v4_{cat}.json"))
        if args.limit:
            recs = recs[:args.limit]
        for rec in recs:
            tools = tools_schema(build_function_list(rec))
            decoded, raw_log = run_entry(rec, args.base_url.rstrip("/"), tools,
                                         args.max_tokens, args.max_steps,
                                         args.model, cat)
            gt = gt_by_cat[cat][rec["id"]]
            try:
                res = multi_turn_checker(decoded, gt, rec, cat, args.model)
                strict = bool(res.get("valid"))
                err = None if strict else res.get("error_type")
            except Exception as e:
                strict, err = False, f"checker_exception:{e}"
            cm = continuous_metrics(decoded, gt, rec)
            out.append({"id": rec["id"], "category": cat, "strict": strict,
                        "error": err, "metrics": cm, "decoded": decoded,
                        "log": raw_log})
            d = per_cat.setdefault(cat, {"n": 0, "strict": 0, "gt_calls": 0, "matched": 0,
                                         "turns": 0, "turns_full": 0})
            d["n"] += 1
            d["strict"] += int(strict)
            d["gt_calls"] += cm["n_gt_calls"]
            if cm["call_rate"] is not None:
                d["matched"] += round(cm["call_rate"] * cm["n_gt_calls"])
            print(f"\r  {cat} {d['n']} strict={d['strict']}", end="", file=sys.stderr)

    with open(args.samples, "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")

    agg = {"model": args.model, "n": len(out), "strict_correct": sum(r["strict"] for r in out),
           "strict_score": (sum(r["strict"] for r in out) / len(out)) if out else 0.0,
           "per_category": {}, "protocol": "bfcl-native-tools-nothink-greedy-multiturn",
           "categories": args.categories, "limit": args.limit,
           "elapsed_s": round(time.time() - t0)}
    for cat, d in per_cat.items():
        cr = [r["metrics"]["call_rate"] for r in out
              if r["category"] == cat and r["metrics"]["call_rate"] is not None]
        tr = [r["metrics"]["turn_match_rate"] for r in out
              if r["category"] == cat and r["metrics"]["turn_match_rate"] is not None]
        agg["per_category"][cat] = {
            "n": d["n"], "strict_acc": d["strict"] / d["n"] if d["n"] else 0.0,
            "call_rate": (sum(cr) / len(cr)) if cr else None,
            "turn_match_rate": (sum(tr) / len(tr)) if tr else None,
        }
    dest = args.samples.replace(".jsonl", "_eval.json")
    with open(dest, "w") as f:
        json.dump(agg, f, indent=1)
    print("\n" + json.dumps(agg, indent=1), file=sys.stderr)


if __name__ == "__main__":
    main()
