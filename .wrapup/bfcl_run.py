#!/usr/bin/env python3
"""BFCL tool-calling runner for llama-server.

Categories (bundled with bfcl-eval, no network needed):
  simple_python / simple_java / simple_javascript  -> single correct call
  multiple                                         -> choose the right one of several
  parallel                                         -> several calls to one function
  parallel_multiple                                -> several calls, several functions
  irrelevance                                      -> must call nothing

Generation modes
  tools  : OpenAI tool-calling (`tools=` param); reads message.tool_calls
  prompt : schemas embedded in the system message; model must emit JSON

Scoring is a pragmatic AST-style match against BFCL `possible_answer` files:
a ground-truth call is matched when the function name matches and every
required argument value is in the accepted list (after light normalisation).
Extra predicted calls break the match (except for irrelevance, where any call is wrong).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

BFCL = "/home/z/hf/research/.wrapup/bfclenv/lib/python3.11/site-packages/bfcl_eval/data"
QDIR = BFCL
ADIR = os.path.join(BFCL, "possible_answer")

VALID = {"simple_python", "simple_java", "simple_javascript", "multiple",
         "parallel", "parallel_multiple", "irrelevance"}


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


def post(url, payload, timeout=300):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def norm(v):
    if isinstance(v, str):
        return v.strip().lower()
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    return v


def arg_ok(pred, accepted):
    """pred matches any accepted value (type-tolerant)."""
    for a in accepted:
        if norm(pred) == norm(a):
            return True
        try:
            if norm(pred) == float(a):
                return True
        except (TypeError, ValueError):
            pass
    return False


def call_ok(pred, gt_call):
    """gt_call = {name: {arg: [accepted...]}}"""
    for name, args in gt_call.items():
        if pred.get("name") != name:
            return False
        pargs = pred.get("arguments") or {}
        if not isinstance(pargs, dict):
            return False
        for k, accepted in args.items():
            if k not in pargs:
                return False
            if not arg_ok(pargs[k], accepted):
                return False
    return True


def parse_prompt_calls(text):
    """Extract calls from a model's JSON answer."""
    text = text.strip()
    m = re.search(r"```[a-zA-Z]*\n(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    # find the outermost JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except Exception:
        return None
    calls = obj.get("calls")
    if calls is None and "name" in obj:
        calls = [obj]
    if not isinstance(calls, list):
        return None
    out = []
    for c in calls:
        if isinstance(c, dict) and "name" in c:
            out.append({"name": c["name"], "arguments": c.get("arguments", {})})
    return out


# BFCL uses Python-ish type names; llama.cpp's json-schema->grammar needs JSON Schema.
TYPE_MAP = {"dict": "object", "tuple": "array", "list": "array", "float": "number",
            "int": "integer", "bool": "boolean", "str": "string", "any": None,
            "Dict": "object", "Tuple": "array", "List": "array", "Float": "number",
            "Integer": "integer", "String": "string"}


def fix_schema(node):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "type" and isinstance(v, str):
                t = TYPE_MAP.get(v, v)
                if t is not None:
                    out[k] = t
            else:
                out[k] = fix_schema(v)
        if out.get("type") == "object" and "properties" not in out:
            out["properties"] = {}
        return out
    if isinstance(node, list):
        return [fix_schema(x) for x in node]
    return node


def tools_schema(functions):
    out = []
    for f in functions:
        f = dict(f)
        f["parameters"] = fix_schema(f.get("parameters") or {"type": "object", "properties": {}})
        out.append({"type": "function", "function": f})
    return out


def gen(args):
    os.makedirs(os.path.dirname(args.samples) or ".", exist_ok=True)
    base = args.base_url.rstrip("/")
    out = []
    if os.path.exists(args.samples) and args.resume:
        out = load_jsonl(args.samples)
        done = {r["id"] for r in out}
    else:
        done = set()
    t0 = time.time()
    for cat in args.categories.split(","):
        cat = cat.strip()
        assert cat in VALID, cat
        recs = load_jsonl(os.path.join(QDIR, f"BFCL_v4_{cat}.json"))
        if args.limit:
            recs = recs[:args.limit]
        for rec in recs:
            if rec["id"] in done:
                continue
            msgs = []
            for turn in rec["question"]:
                for m in turn:
                    msgs.append({"role": m["role"], "content": m["content"]})
            try:
                if args.mode == "tools":
                    payload = {"messages": msgs, "temperature": 0.0,
                               "max_tokens": args.max_tokens,
                               "tools": tools_schema(rec.get("function") or []),
                               "chat_template_kwargs": {"enable_thinking": False}}
                    r = post(base + "/v1/chat/completions", payload)
                    msg = r["choices"][0]["message"]
                    calls = []
                    for c in (msg.get("tool_calls") or []):
                        fn = c.get("function", {})
                        try:
                            a = json.loads(fn.get("arguments") or "{}")
                        except Exception:
                            a = fn.get("arguments")
                        calls.append({"name": fn.get("name"), "arguments": a})
                    raw = msg.get("content") or ""
                else:
                    sysmsg = ("You are a function-calling assistant. Available functions:\n"
                              + json.dumps(rec.get("function") or [], indent=1)
                              + '\nRespond ONLY with JSON: {"calls":[{"name":"...","arguments":{...}}]}. '
                              'If no function is needed respond {"calls":[]}.')
                    payload = {"messages": [{"role": "system", "content": sysmsg}] + msgs,
                               "temperature": 0.0, "max_tokens": args.max_tokens,
                               "chat_template_kwargs": {"enable_thinking": False}}
                    r = post(base + "/v1/chat/completions", payload)
                    _m = r["choices"][0]["message"]
                    raw = (_m.get("content") or "").strip() or (_m.get("reasoning_content") or "")
                    calls = parse_prompt_calls(raw) or []
            except Exception as e:
                print(f"  ! {rec['id']}: {e}", file=sys.stderr)
                calls, raw = [], ""
            out.append({"id": rec["id"], "category": cat, "calls": calls, "raw": raw[:2000]})
            print(f"\r  gen {len(out)}", end="", file=sys.stderr)
    print("", file=sys.stderr)
    with open(args.samples, "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    print(f"gen mode={args.mode} n={len(out)} in {time.time()-t0:.0f}s -> {args.samples}", file=sys.stderr)


def evaluate(args):
    samples = load_jsonl(args.samples)
    gt_cache = {}
    correct = 0
    per_cat = {}
    for s in samples:
        cat = s["category"]
        if cat not in gt_cache:
            gt_cache[cat] = {r["id"]: r["ground_truth"]
                             for r in load_jsonl(os.path.join(ADIR, f"BFCL_v4_{cat}.json"))}
        gt = gt_cache[cat].get(s["id"], [])
        calls = s.get("calls") or []
        if cat == "irrelevance":
            ok = len(calls) == 0
        else:
            ok = (len(calls) == len(gt)
                  and all(any(call_ok(c, g) for c in calls) for g in gt))
        correct += int(ok)
        d = per_cat.setdefault(cat, [0, 0])
        d[0] += int(ok); d[1] += 1
    n = len(samples)
    res = {"n": n, "correct": correct, "score": correct / n if n else 0.0,
           "per_category": {k: {"acc": v[0] / v[1], "n": v[1]} for k, v in per_cat.items()}}
    dest = args.out or args.samples.replace(".jsonl", "_eval.json")
    with open(dest, "w") as f:
        json.dump(res, f)
    print(json.dumps(res, indent=1))
    print(f"-> {dest}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--categories", default="simple_python")
    g.add_argument("--samples", required=True)
    g.add_argument("--base_url", default="http://127.0.0.1:8080")
    g.add_argument("--mode", choices=["tools", "prompt"], default="tools")
    g.add_argument("--max_tokens", type=int, default=512)
    g.add_argument("--resume", action="store_true")
    g.add_argument("--limit", type=int, default=0)
    g.set_defaults(fn=gen)
    e = sub.add_parser("eval")
    e.add_argument("--samples", required=True)
    e.add_argument("--out")
    e.set_defaults(fn=evaluate)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
