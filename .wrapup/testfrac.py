#!/usr/bin/env python3
"""T2 — continuous (per-test) code metric for MultiPL-E completions.

Reuses the compile/run machinery of mpl_run.py but instead of a single binary
"program exited 0" it counts how many of the *provided* unit tests pass.

Usage:
  testfrac.py --lang cpp --samples mres/m3-q3-cpp.jsonl --out testfrac_m3-q3-cpp.jsonl

Instrumentation per language (tests are appended to prompt+completion exactly as
mpl_run.eval_one does):
  * cpp : #undef assert then a macro that prints <P>/<F> per assertion (survives
          the process dying mid-way, so partial credit is retained).
  * js  : the required node:assert methods are monkey-patched to count instead of
          throw; counts are dumped from a process 'exit' handler.
  * py  : assert statements are rewritten via ast into try/except counters; an
          atexit handler dumps the counts.
  * java: assert( is rewritten to a counting helper; a shutdown hook dumps counts.

Output: one JSON object per test item, plus an aggregate summary line printed to
stderr by the caller.
"""
import argparse
import ast
import concurrent.futures
import json
import os
import re
import subprocess
import tempfile

PROMPTS = "/tmp/MultiPL-E/prompts"
JAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jars", "javatuples-1.2.jar")

CPP_INJECT = r"""
#undef assert
#include <cstdio>
#define assert(...) do { bool _ok=false; try { _ok=(bool)(__VA_ARGS__); } \
catch(...) { _ok=false; } std::printf(_ok?"<P>":"<F>"); std::fflush(stdout); } while(0)
"""

JS_PREAMBLE = r"""
const _TF = require('node:assert');
globalThis._tfc = {t:0, p:0};
function _tfw(n){const f=_TF[n]; if(typeof f!=='function')return;
  _TF[n]=function(...a){globalThis._tfc.t++; try{f.apply(_TF,a);globalThis._tfc.p++;}catch(e){}};}
['deepEqual','equal','strictEqual','notStrictEqual','notEqual','ok','throws','doesNotThrow','match','doesNotMatch','fail'].forEach(_tfw);
process.on('exit',()=>{console.log('TESTFRAC '+globalThis._tfc.t+' '+globalThis._tfc.p);});
"""

PY_PREAMBLE = (
    "import atexit as _atexit, sys as _sys\n"
    "_t=[0]; _p=[0]\n"
    "@_atexit.register\n"
    "def _tf_dump():\n"
    "    _sys.stdout.write('TESTFRAC %d %d\\n' % (_t[0], _p[0]))\n"
)

JAVA_HELPERS = r"""
    static int _tft = 0, _tfp = 0;
    static void _tf(boolean b) { _tft++; if (b) _tfp++; }
    static { Runtime.getRuntime().addShutdownHook(new Thread(() ->
        System.out.println("TESTFRAC " + _tft + " " + _tfp))); }
"""


class PyAssertRewriter(ast.NodeTransformer):
    """Replace every `assert <expr>` with total++ plus a guarded passed++."""

    def visit_Assert(self, node):
        self.generic_visit(node)
        inc_t = ast.parse("_t[0] += 1").body[0]
        cond = ast.If(test=node.test,
                      body=[ast.parse("_p[0] += 1").body[0]], orelse=[])
        guard = ast.Try(body=[cond],
                        handlers=[ast.ExceptHandler(
                            type=ast.Name(id="BaseException", ctx=ast.Load()),
                            name=None, body=[ast.Pass()])],
                        orelse=[], finalbody=[])
        return [ast.copy_location(inc_t, node), ast.copy_location(guard, node)]


def instrument_py(tests):
    tree = PyAssertRewriter().visit(ast.parse(tests))
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def count_marks(text, pair=("<P>", "<F>")):
    p = text.count(pair[0])
    f = text.count(pair[1])
    return f + p, p


def parse_testfrac(text):
    m = re.search(r"TESTFRAC\s+(\d+)\s+(\d+)", text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def run_cpp(prompt, completion, tests, wd):
    idx = tests.find("int main")
    if idx < 0:
        return None, None, "NoMain"
    src = prompt + completion + tests[:idx] + CPP_INJECT + tests[idx:]
    path = os.path.join(wd, "prog.cpp")
    with open(path, "w") as f:
        f.write(src)
    b = os.path.join(wd, "a.out")
    c = subprocess.run(["g++", path, "-o", b, "-std=c++17"],
                       capture_output=True, timeout=90)
    if c.returncode != 0:
        return None, None, "SyntaxError"
    try:
        r = subprocess.run([b], capture_output=True, timeout=20, cwd=wd)
    except subprocess.TimeoutExpired:
        return None, None, "Timeout"
    t, p = count_marks(r.stdout.decode("utf-8", "replace"))
    return t, p, "OK" if t else "NoOutput"


def run_js(prompt, completion, tests, wd):
    src = prompt + completion + "\n" + JS_PREAMBLE + tests
    path = os.path.join(wd, "prog.js")
    with open(path, "w") as f:
        f.write(src)
    try:
        r = subprocess.run(["node", path], capture_output=True, timeout=15, cwd=wd)
    except subprocess.TimeoutExpired:
        return None, None, "Timeout"
    got = parse_testfrac(r.stdout.decode("utf-8", "replace"))
    if not got:
        return None, None, "NoOutput"
    return got[0], got[1], "OK"


def run_py(prompt, completion, tests, wd):
    try:
        itests = instrument_py(tests)
    except SyntaxError:
        return None, None, "TestParseError"
    src = PY_PREAMBLE + "\n" + prompt + completion + "\n" + itests
    path = os.path.join(wd, "prog.py")
    with open(path, "w") as f:
        f.write(src)
    try:
        r = subprocess.run(["python3", path], capture_output=True, timeout=10, cwd=wd)
    except subprocess.TimeoutExpired:
        return None, None, "Timeout"
    got = parse_testfrac(r.stdout.decode("utf-8", "replace"))
    if not got:
        return None, None, "NoOutput"
    return got[0], got[1], "OK"


def run_java(prompt, completion, tests, wd):
    idx = tests.find("public static void main")
    if idx < 0:
        return None, None, "NoMain"
    instr = re.sub(r"(?<![\w.])assert\s*\(", "_tf(", tests)
    src = prompt + completion + instr[:idx] + JAVA_HELPERS + instr[idx:]
    path = os.path.join(wd, "Problem.java")
    with open(path, "w") as f:
        f.write(src)
    od = os.path.join(wd, "out")
    os.makedirs(od, exist_ok=True)
    c = subprocess.run(["javac", "-encoding", "UTF8", "-cp", JAR, "-d", od, path],
                       capture_output=True, timeout=90)
    if c.returncode != 0:
        return None, None, "SyntaxError"
    try:
        r = subprocess.run(["java", "-ea", "-cp", f"{od}:{JAR}", "Problem"],
                           capture_output=True, timeout=20, cwd=wd)
    except subprocess.TimeoutExpired:
        return None, None, "Timeout"
    got = parse_testfrac(r.stdout.decode("utf-8", "replace"))
    if not got:
        return None, None, "NoOutput"
    return got[0], got[1], "OK"


RUNNERS = {"cpp": run_cpp, "js": run_js, "py": run_py, "java": run_java}


def expected_count(lang, tests):
    """Static number of provided unit tests.

    The executed count alone is not enough: a program that crashes after 2 of 5
    assertions must not look like a full pass, so the denominator is taken from
    the test source.  MultiPL-E tests are flat (one assertion per case).
    """
    if lang in ("cpp", "java"):
        return len(re.findall(r"(?<![\w.])assert\s*\(", tests))
    if lang == "js":
        return len(re.findall(r"assert\.", tests))
    if lang == "py":
        try:
            return sum(1 for n in ast.walk(ast.parse(tests))
                       if isinstance(n, ast.Assert))
        except SyntaxError:
            return 0
    return 0


def eval_item(args):
    lang, prompt, completion, tests, name = args
    expected = expected_count(lang, tests)
    with tempfile.TemporaryDirectory() as wd:
        try:
            t, p, status = RUNNERS[lang](prompt, completion, tests, wd)
        except Exception as e:  # noqa: BLE001
            return {"name": name, "n_tests": expected, "n_pass": 0,
                    "frac": 0.0, "binary_pass": False,
                    "status": f"HarnessError:{e}"}
    obs_p = p or 0
    n_pass = min(obs_p, expected)
    frac = n_pass / expected if expected else 0.0
    binary = expected > 0 and obs_p >= expected
    return {"name": name, "n_tests": expected, "n_pass": n_pass,
            "frac": round(frac, 6), "binary_pass": bool(binary), "status": status}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=list(RUNNERS))
    ap.add_argument("--samples", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    problems = {json.loads(l)["name"]: json.loads(l)
                for l in open(f"{PROMPTS}/humaneval-{args.lang}.jsonl")}
    samples = [json.loads(l) for l in open(args.samples)]
    if args.limit:
        samples = samples[:args.limit]

    jobs = []
    for s in samples:
        p = problems.get(s["name"])
        if p is None:
            continue
        jobs.append((args.lang, p["prompt"], s.get("completion", ""),
                     p["tests"], s["name"]))

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(eval_item, jobs):
            results.append(r)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    n = len(results)
    npass = sum(1 for r in results if r["binary_pass"])
    # mean fraction over items that produced at least one test
    fracs = [r["frac"] for r in results if r["n_tests"]]
    mean_frac = sum(fracs) / len(fracs) if fracs else 0.0
    # micro fraction: total tests passed / total tests run over those items
    tot_t = sum(r["n_tests"] for r in results if r["n_tests"])
    tot_p = sum(r["n_pass"] for r in results if r["n_tests"])
    micro = tot_p / tot_t if tot_t else 0.0
    summary = {"samples": args.samples, "lang": args.lang, "n": n,
               "pass": npass, "pass_at_1": round(npass / n, 6) if n else 0.0,
               "mean_frac": round(mean_frac, 6), "micro_frac": round(micro, 6),
               "mean_tests_per_item": round(tot_t / len(fracs), 3) if fracs else 0.0}
    print(json.dumps(summary))
    with open(args.out.rsplit(".jsonl", 1)[0] + "_summary.jsonl", "w") as f:
        f.write(json.dumps(summary) + "\n")


if __name__ == "__main__":
    main()
