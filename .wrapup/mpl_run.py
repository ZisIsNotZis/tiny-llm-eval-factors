#!/usr/bin/env python3
"""MultiPL-E runner: generate completions from llama-server and execute tests.

Usage:
  mpl_run.py gen  --lang cpp --samples <jsonl> --base_url URL --temperature T \
                  --max_tokens N [--greedy] [--limit K] [--mode raw|chat]
  mpl_run.py eval --lang cpp --samples <jsonl> [--out <results.json>]
  mpl_run.py run   ... (gen then eval)

Protocol (documented for the DB):
  * raw  : POST /completion with the MultiPL-E prompt and the dataset stop tokens
  * chat : POST /v1/chat/completions with a fixed completion instruction

Pass = the compiled program exits 0.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

PROMPTS = "/tmp/MultiPL-E/prompts"
JAR = "/home/z/hf/research/.wrapup/jars/javatuples-1.2.jar"

LANGS = {
    "cpp": {"ext": ".cpp", "timeout": 20},
    "java": {"ext": ".java", "timeout": 20},
    "js": {"ext": ".js", "timeout": 15},
    "rs": {"ext": ".rs", "timeout": 20},
    "rb": {"ext": ".rb", "timeout": 15},
    "pl": {"ext": ".pl", "timeout": 15},
    "py": {"ext": ".py", "timeout": 10},
}

LANG_NAME = {"cpp": "C++", "java": "Java", "js": "JavaScript", "rs": "Rust",
             "rb": "Ruby", "pl": "Perl", "py": "Python"}


def post(url, payload, timeout=600):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def strip_fences(text):
    text = text.strip()
    m = re.search(r"```[a-zA-Z0-9_+-]*\n(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    return text.rstrip()


def truncate_at_stops(text, stops):
    cut = len(text)
    for s in stops or []:
        if not s:
            continue
        i = text.find(s)
        if i != -1:
            cut = min(cut, i)
    return text[:cut]


def gen(args):
    problems = [json.loads(l) for l in open(f"{PROMPTS}/humaneval-{args.lang}.jsonl")]
    if args.limit:
        problems = problems[:args.limit]
    out_path = args.samples
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    base = args.base_url.rstrip("/")
    results = []
    t0 = time.time()
    for i, p in enumerate(problems):
        prompt = p["prompt"]
        stops = p.get("stop_tokens") or []
        try:
            if args.mode == "raw":
                payload = {"prompt": prompt, "temperature": float(args.temperature),
                           "n_predict": args.max_tokens, "stop": stops,
                           "cache_prompt": True}
                if args.greedy:
                    payload["temperature"] = 0.0
                r = post(base + "/completion", payload)
                text = r["content"]
            else:
                instr = (f"Complete the following {LANG_NAME[args.lang]} function. "
                         f"Return only the code that should replace the marked region, "
                         f"without any explanation or markdown fences.\n\n{prompt}")
                payload = {"messages": [{"role": "user", "content": instr}],
                           "temperature": float(args.temperature),
                           "max_tokens": args.max_tokens, "stop": stops}
                if args.greedy:
                    payload["temperature"] = 0.0
                r = post(base + "/v1/chat/completions", payload)
                text = r["choices"][0]["message"].get("content") or ""
        except Exception as e:
            print(f"  ! request failed on {p['name']}: {e}", file=sys.stderr)
            text = ""
        if args.mode == "chat":
            text = strip_fences(text)
        completion = truncate_at_stops(text, stops)
        results.append({"name": p["name"], "completion": completion})
        print(f"\r  gen {i+1}/{len(problems)}", end="", file=sys.stderr)
    print("", file=sys.stderr)
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print(f"gen {args.lang} mode={args.mode} n={len(results)} in {time.time()-t0:.0f}s -> {out_path}",
          file=sys.stderr)


def eval_one(lang, prompt, completion, tests, workdir):
    cfg = LANGS[lang]
    ext = cfg["ext"]
    if lang == "java":
        src = os.path.join(workdir, "Problem.java")
    else:
        src = os.path.join(workdir, "prog" + ext)
    with open(src, "w") as f:
        f.write(prompt + completion + "\n" + tests)
    try:
        if lang == "cpp":
            b = os.path.join(workdir, "a.out")
            c = subprocess.run(["g++", src, "-o", b, "-std=c++17"],
                               capture_output=True, timeout=60)
            if c.returncode != 0:
                return False, "SyntaxError"
            r = subprocess.run([b], capture_output=True, timeout=cfg["timeout"], cwd=workdir)
            return r.returncode == 0, ("OK" if r.returncode == 0 else "Exception")
        if lang == "java":
            od = os.path.join(workdir, "out")
            os.makedirs(od, exist_ok=True)
            c = subprocess.run(["javac", "-encoding", "UTF8", "-cp", JAR, "-d", od, src],
                               capture_output=True, timeout=60)
            if c.returncode != 0:
                return False, "SyntaxError"
            r = subprocess.run(["java", "-ea", "-cp", f"{od}:{JAR}", "Problem"],
                               capture_output=True, timeout=cfg["timeout"], cwd=workdir)
            return r.returncode == 0, ("OK" if r.returncode == 0 else "Exception")
        if lang == "rs":
            b = os.path.join(workdir, "prog")
            c = subprocess.run(["rustc", src, "-o", b], capture_output=True, timeout=90)
            if c.returncode != 0:
                return False, "SyntaxError"
            r = subprocess.run([b], capture_output=True, timeout=cfg["timeout"], cwd=workdir)
            return r.returncode == 0, ("OK" if r.returncode == 0 else "Exception")
        if lang == "js":
            r = subprocess.run(["node", src], capture_output=True, timeout=cfg["timeout"], cwd=workdir)
            return r.returncode == 0, ("OK" if r.returncode == 0 else "Exception")
        if lang == "rb":
            r = subprocess.run(["ruby", src], capture_output=True, timeout=cfg["timeout"], cwd=workdir)
            return r.returncode == 0, ("OK" if r.returncode == 0 else "Exception")
        if lang == "pl":
            env = dict(os.environ)
            env["PERL5LIB"] = "/home/z/perl5/lib/perl5"
            r = subprocess.run(["perl", src], capture_output=True, timeout=cfg["timeout"],
                               cwd=workdir, env=env)
            return r.returncode == 0, ("OK" if r.returncode == 0 else "Exception")
        if lang == "py":
            r = subprocess.run(["python3", src], capture_output=True, timeout=cfg["timeout"], cwd=workdir)
            return r.returncode == 0, ("OK" if r.returncode == 0 else "Exception")
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, f"HarnessError:{e}"
    return False, "Unsupported"


def run_eval(args):
    problems = {json.loads(l)["name"]: json.loads(l)
                for l in open(f"{PROMPTS}/humaneval-{args.lang}.jsonl")}
    samples = [json.loads(l) for l in open(args.samples)]
    npass = 0
    details = []
    for s in samples:
        p = problems.get(s["name"])
        if p is None:
            continue
        with tempfile.TemporaryDirectory() as wd:
            ok, status = eval_one(args.lang, p["prompt"], s["completion"], p["tests"], wd)
        npass += int(ok)
        details.append({"name": s["name"], "pass": bool(ok), "status": status})
    n = len(details)
    score = npass / n if n else 0.0
    out = {"lang": args.lang, "n": n, "pass": npass, "score": score, "details": details}
    dest = getattr(args, "out", None) or (args.samples.rsplit(".jsonl", 1)[0] + "_eval.json")
    with open(dest, "w") as f:
        json.dump(out, f)
    print(f"eval {args.lang} n={n} pass={npass} score={score:.4f} -> {dest}", file=sys.stderr)
    print(json.dumps({"lang": args.lang, "n": n, "score": round(score, 4)}))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--lang", required=True, choices=list(LANGS))
    g.add_argument("--samples", required=True)
    g.add_argument("--base_url", default="http://127.0.0.1:8080")
    g.add_argument("--temperature", default="0.0")
    g.add_argument("--max_tokens", type=int, default=768)
    g.add_argument("--greedy", action="store_true")
    g.add_argument("--limit", type=int, default=0)
    g.add_argument("--mode", choices=["raw", "chat"], default="raw")
    g.set_defaults(fn=gen)
    e = sub.add_parser("eval")
    e.add_argument("--lang", required=True, choices=list(LANGS))
    e.add_argument("--samples", required=True)
    e.add_argument("--out")
    e.set_defaults(fn=run_eval)
    for name in ("run",):
        r = sub.add_parser(name)
        r.add_argument("--lang", required=True, choices=list(LANGS))
        r.add_argument("--samples", required=True)
        r.add_argument("--base_url", default="http://127.0.0.1:8080")
        r.add_argument("--temperature", default="0.0")
        r.add_argument("--max_tokens", type=int, default=768)
        r.add_argument("--greedy", action="store_true")
        r.add_argument("--limit", type=int, default=0)
        r.add_argument("--mode", choices=["raw", "chat"], default="raw")
        r.set_defaults(fn=lambda a: (gen(a), run_eval(a)))
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
