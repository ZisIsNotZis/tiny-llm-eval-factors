#!/usr/bin/env python3
"""T4 gemma-4-12B repair: probe candidate protocols, pick the one that actually
produces compilable MultiPL-E completions, then run Q2/Q3 x cpp/py.

Must be invoked under the GPU lock:
    bash gpu_locked.sh python3 t4_gemma_repair.py

The raw /completion protocol made gemma-4-12B emit a `<|channel>thought ...`
reasoning trace (or degenerate text) at every quant. gemma-4's chat template
primes a no-think turn with an empty `<|channel>thought\\n<channel|>` block; in
raw mode no template is applied, so this driver probes several inequivalent fixes
and keeps the empirically best one.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))  # .wrapup/：按脚本自身位置定位
MRES = os.path.join(HERE, "mres")
PORT = 8080
BASE = f"http://127.0.0.1:{PORT}"
LOG = os.path.join(HERE, "t4_gemma_repair.log")
SUMMARY = os.path.join(HERE, "m6b_summary.jsonl")
PY = "python3"

MODELS = {"g12b-q2": "/home/z/hf/gemma-4-12b-it-UD-Q2_K_XL.gguf",
          "g12b-q3": "/home/z/hf/gemma-4-12b-it-UD-Q3_K_XL.gguf"}

# name -> (mode, prompt_suffix, extra_stop, strip_thought, chat_kwargs, proto)
PRIME = "<|channel>thought\n<channel|>"
TURN_PRIME = "<|turn>model\n<|channel>thought\n<channel|>"
CANDIDATES = {
    "raw-baseline": ("raw", "", "", False, "", "mpl-raw-greedy-768"),
    "raw-prime": ("raw", PRIME, "", False, "", "mpl-raw-prime-nothink-greedy-768"),
    "raw-turnprime": ("raw", TURN_PRIME, "", False, "",
                      "mpl-raw-turnprime-nothink-greedy-768"),
    "raw-prime-stop": ("raw", PRIME, "<|channel>", True, "",
                       "mpl-raw-prime-stop-nothink-greedy-768"),
    "chat-nothink": ("chat", "", "", False, '{"enable_thinking": false}',
                     "mpl-chat-nothink-greedy-768"),
}
# tie-break preference (higher priority first)
PREFERENCE = ["raw-turnprime", "raw-prime", "raw-prime-stop", "chat-nothink",
              "raw-baseline"]


def log(*a):
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def health_ok():
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=3) as r:
            return '"status":"ok"' in r.read().decode()
    except Exception:
        return False


def kill_port():
    out = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if f":{PORT}" in line and "pid=" in line:
            pid = line.split("pid=")[1].split(",")[0]
            subprocess.run(["kill", pid])
            time.sleep(2)


def start_server(model):
    kill_port()
    cmd = ["llama-server", "-m", model, "--port", str(PORT), "--host", "127.0.0.1",
           "-ngl", "99", "-c", "4096", "--cache-type-k", "q8_0",
           "--cache-type-v", "q8_0", "--top-p", "0.95", "--top-k", "40",
           "--min-p", "0.05", "--jinja"]
    lf = open(LOG, "a")
    p = subprocess.Popen(cmd, stdout=lf, stderr=lf)
    for _ in range(150):
        if p.poll() is not None:
            log(f"SERVER DIED {model}")
            return None
        if health_ok():
            log(f"server ready {os.path.basename(model)}")
            return p
        time.sleep(2)
    log(f"SERVER TIMEOUT {model}")
    p.kill()
    return None


def gen_eval(tag, lang, cand, limit=0):
    mode, suffix, extra_stop, strip, ck, proto = cand
    samples = os.path.join(MRES, f"m6b-probe-{tag}-{lang}.jsonl" if limit
                           else f"m6b-{tag}-{lang}.jsonl")
    cmd = [PY, "mpl_run.py", "gen", "--lang", lang, "--mode", mode, "--greedy",
           "--max_tokens", "768", "--samples", samples, "--base_url", BASE]
    if limit:
        cmd += ["--limit", str(limit)]
    if suffix:
        cmd += ["--prompt-suffix", suffix]
    if extra_stop:
        cmd += ["--extra-stop", extra_stop]
    if strip:
        cmd += ["--strip-thought"]
    if ck:
        cmd += ["--chat-kwargs", ck]
    subprocess.run(cmd, cwd=HERE, stdout=open(LOG, "a"), stderr=open(LOG, "a"))
    ev = samples.rsplit(".jsonl", 1)[0] + "_eval.json"
    subprocess.run([PY, "mpl_run.py", "eval", "--lang", lang, "--samples", samples],
                   cwd=HERE, stdout=open(LOG, "a"), stderr=open(LOG, "a"))
    d = json.load(open(ev))
    return d, samples


def main():
    log(f"=== gemma repair start {time.strftime('%F %T')} ===")
    # ---- probe on the Q3 model, python, 40 problems ----
    srv = start_server(MODELS["g12b-q3"])
    if srv is None:
        log("FATAL: cannot load gemma-4-12B Q3")
        return 1
    probe_results = {}
    for name, cand in CANDIDATES.items():
        d, samples = gen_eval("q3", "py", cand, limit=40)
        probe_results[name] = (d["pass"], d["n"])
        # keep a short sample of the first completion for the audit log
        first = json.loads(open(samples).readline())
        log(f"PROBE {name}: pass={d['pass']}/{d['n']} proto={cand[5]} "
            f"sample={first['completion'][:160]!r}")
    # ---- choose: max pass, tie-break by PREFERENCE order ----
    maxp = max(v[0] for v in probe_results.values())
    best = next(name for name in PREFERENCE if probe_results[name][0] == maxp)
    log(f"CHOSEN protocol: {best} -> {CANDIDATES[best][5]} "
        f"(probe {probe_results[best]})")
    srv.kill()
    time.sleep(3)
    srv.wait()

    chosen = CANDIDATES[best]
    # ---- full panel Q2/Q3 x cpp/py ----
    open(SUMMARY, "w").close()
    for tag, path in MODELS.items():
        if not os.path.exists(path):
            log(f"MISSING MODEL {path}")
            continue
        srv = start_server(path)
        if srv is None:
            log(f"SKIP {tag} (load failed)")
            continue
        for lang in ("cpp", "py"):
            t0 = time.time()
            d, _ = gen_eval(tag, lang, chosen)
            row = {"model": tag, "lang": lang, "n": d["n"], "pass": d["pass"],
                   "score": d["score"], "protocol": chosen[5]}
            with open(SUMMARY, "a") as f:
                f.write(json.dumps(row) + "\n")
            log(f"RESULT {tag} {lang} pass={d['pass']}/{d['n']} "
                f"score={d['score']:.4f} ({time.time()-t0:.0f}s)")
        srv.kill()
        time.sleep(3)
        srv.wait()
    log(f"=== gemma repair end {time.strftime('%F %T')} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
