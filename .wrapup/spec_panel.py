#!/usr/bin/env python3
"""Speculative-decoding panel: TIME and QUALITY in one run.

The operator's point was that speculative decoding (MTP / draft-mtp) is a *speed* knob, so
a speed table alone is not enough -- it must also be checked for quality damage, because the
draft tokens change the sampled sequence.

The earlier m28 panel measured tok/s only, on one model, and never scored anything, so the
quality half of that question was unanswered.  This panel runs both halves for each
`--spec-draft-n-max` in {0, 1, 4}:

  * SPEED   -- a fixed greedy generation, reading `timings.predicted_per_second` from
               llama-server itself (not wall clock, so server startup is excluded)
  * QUALITY -- lm-eval mmlu (loglikelihood, cheap and deterministic) + gsm8k and ifeval
               (the two generative benchmarks that F9 showed are the most bpw-sensitive),
               and EvalPlus humaneval for the code column

Everything is greedy, thinking off, so the only moving part is the draft depth.

Usage: spec_panel.py --model <gguf> --tag <tag> [--drafts 0,1,4] [--limit 50]
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path("/home/z/hf/research")
WR = ROOT / ".wrapup"
MRES = WR / "mres"
LMEVAL_PY = WR / "lmenv/bin/python"
LMEVAL = WR / "lmenv/bin/lm_eval"
SHIM_LAUNCHER = WR / "lmeshim/lm_eval_cli.py"
EVALPLUS = WR / "evalpy/bin/evalplus.codegen"
EVALPLUS_EV = WR / "evalpy/bin/evalplus.evaluate"
LLAMA = os.environ.get("LLAMA_SERVER", "/home/z/.local/bin/llama-server")
LOCK = "/tmp/llama_gpu.lock"

# Reuse the exact logprob shim from lmeval_run.py.  llama-server build 4399 silently ignores
# OpenAI `echo`, so pointing lm-eval's gguf model straight at llama-server makes every
# loglikelihood task die with "zip() argument 2 is longer than argument 1" -- measured.
import importlib.util as _ilu  # noqa: E402

_spec = _ilu.spec_from_file_location("lmeval_run", str(WR / "lmeval_run.py"))
lmeval_run = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(lmeval_run)

# Every dataset is already cached; without these lm-eval re-contacts the Hub per task.
OFFLINE_ENV = dict(os.environ)
OFFLINE_ENV.update({"HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1"})


def log(msg, f=None):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    if f:
        with open(f, "a") as fh:
            fh.write(line + "\n")


def free_port(start=8900, span=100):
    listening = subprocess.run(["ss", "-ltnH"], capture_output=True, text=True).stdout
    for port in range(start, start + span):
        if f":{port} " in listening:
            continue
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit("no free port")


def start_server(model, port, draft_n, logfile):
    spec = ["--spec-type", "none"] if draft_n == 0 else \
           ["--spec-type", "draft-mtp", "--spec-draft-n-max", str(draft_n)]
    cmd = [LLAMA, "-m", model, "--port", str(port), "--host", "127.0.0.1",
           "-c", "8192", "-np", "1", "-ngl", "99", "--jinja", "--reasoning", "off", *spec]
    log("llama-server: " + " ".join(cmd), logfile)
    fh = open(logfile, "a")
    proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True,
                            env=OFFLINE_ENV)
    for _ in range(300):
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) \
                    .read().decode().find('"ok"') >= 0:
                return proc
        except Exception:
            pass
        if proc.poll() is not None:
            raise SystemExit(f"server died rc={proc.returncode}")
        time.sleep(1)
    raise SystemExit("server never healthy")


def stop_server(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


PROMPT = ("def fibonacci(n):\n"
          "    \"\"\"Return the n-th Fibonacci number, iterative.\"\"\"\n")


def speed_probe(port, reps=3, n_predict=256):
    """tok/s from the server's own timings block, over reps identical greedy generations."""
    rates = []
    for _ in range(reps):
        body = json.dumps({"prompt": PROMPT, "n_predict": n_predict, "temperature": 0,
                           "cache_prompt": False}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{port}/completion", data=body,
                                     headers={"Content-Type": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=1800).read())
        t = d.get("timings", {})
        if t.get("predicted_per_second"):
            rates.append(float(t["predicted_per_second"]))
    return (sum(rates) / len(rates)) if rates else None


def run(cmd, logfile, timeout=7200):
    with open(logfile, "a") as fh:
        fh.write("# " + " ".join(cmd) + "\n")
        fh.flush()
        # env is REQUIRED: lm-eval re-contacts huggingface.co on every task unless the
        # offline flags are set, and a network retry storm stalled this panel for 34 min
        # (measured: HEAD https://hf-mirror.com/... retry 1/5, dataset cache intact).
        return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                              timeout=timeout, env=OFFLINE_ENV).returncode


def newest(prefix):
    import glob
    fs = sorted(glob.glob(prefix + "*.json"), key=os.path.getmtime)
    return Path(fs[-1]) if fs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--drafts", default="0,1,4")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--tasks", default="mmlu,gsm8k,ifeval")
    args = ap.parse_args()

    out = MRES / args.tag
    out.mkdir(parents=True, exist_ok=True)
    panel_log = str(out / "panel.log")
    model = os.path.realpath(args.model)
    drafts = [int(x) for x in args.drafts.split(",")]

    # same flock convention as every other panel; never wait, report and exit
    lock_fd = os.open(LOCK, os.O_RDWR | os.O_CREAT)
    try:
        import fcntl
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("ABORT: GPU lock held", panel_log)
        return 3

    env = OFFLINE_ENV
    port = free_port()
    shim_port = free_port(port + 1)
    shim = lmeval_run.EchoShim(f"http://127.0.0.1:{port}", Path(panel_log))
    shim_srv = lmeval_run.start_shim(shim, shim_port)
    panel = {"tag": args.tag, "model": model, "drafts": drafts, "rows": {},
             "errors": [], "llama_server": LLAMA}
    log(f"=== spec panel tag={args.tag} model={model} drafts={drafts}", panel_log)

    for n in drafts:
        row = {"draft_n": n}
        proc = start_server(model, port, n, str(out / "server.log"))
        try:
            row["tok_s"] = speed_probe(port)
            log(f"draft_n={n}: tok/s={row['tok_s']}", panel_log)
            for task in args.tasks.split(","):
                lim = 8 if task == "mmlu" else args.limit
                out_json = out / f"lmeval_{task}_n{n}.json"
                if task in ("mmlu", "arc_challenge", "truthfulqa_mc2"):
                    cmd = [str(LMEVAL_PY), str(SHIM_LAUNCHER), "--model", "gguf",
                           "--model_args", f"base_url=http://127.0.0.1:{shim_port},max_length=8192",
                           "--tasks", task, "--limit", str(lim),
                           "--output_path", str(out_json)]
                else:
                    cmd = [str(LMEVAL), "--model", "local-chat-completions",
                           "--model_args", f"base_url=http://127.0.0.1:{port}/v1/chat/completions",
                           "--tasks", task, "--apply_chat_template",
                           "--gen_kwargs", "temperature=0,max_gen_toks=1024",
                           "--limit", str(lim), "--output_path", str(out_json)]
                rc = run(cmd, str(out / f"lmeval_{task}_n{n}.log"))
                val = None
                produced = newest(str(out / f"lmeval_{task}_n{n}_"))
                if rc == 0 and produced:
                    try:
                        node = json.load(open(produced))["results"].get(task, {})
                        for k in ("exact_match,flexible-extract", "acc,none",
                                  "acc_norm,none", "prompt_level_strict_acc,none"):
                            if node.get(k) is not None:
                                val = node[k]
                                break
                    except Exception:
                        pass
                row[task] = val
                log(f"draft_n={n}: {task}={val}", panel_log)

            # code column, the most bpw-sensitive benchmark in F9
            cg = out / "codegen" / f"n{n}"
            cg.mkdir(parents=True, exist_ok=True)
            rc = run([str(EVALPLUS), f"{args.tag}-n{n}", "humaneval", "--backend", "openai",
                      "--base_url", f"http://127.0.0.1:{port}/v1", "--temperature", "0.0",
                      "--greedy", "True", "--root", str(cg)],
                     str(out / f"code_n{n}.log"))
            cands = [p for p in cg.rglob("*_openai_temp_0.0.jsonl") if ".raw." not in p.name]
            samples = sorted(cands)[0] if cands else None
            if rc == 0 and samples:
                rc2 = run([str(EVALPLUS_EV), "humaneval", "--samples", str(samples)],
                          str(out / f"code_n{n}.log"))
                ev = next(cg.rglob("*_eval_results.json"), None)
                if rc2 == 0 and ev:
                    try:
                        # evalplus 0.3.1 writes eval[task_id] = LIST of per-test dicts each
                        # carrying base_status/plus_status.  Reading it as a plain dict is
                        # what produced the bogus humaneval=0.0 (the '0.00 rule' again).
                        evd = json.load(open(ev))["eval"]
                        n_pass = sum(1 for v in evd.values()
                                     for x in (v if isinstance(v, list) else [v])
                                     if isinstance(x, dict) and x.get("base_status") == "pass")
                        row["humaneval"] = n_pass / len(evd) if evd else None
                        row["humaneval_n"] = len(evd)
                    except Exception as exc:
                        panel["errors"].append({"draft_n": n, "code": repr(exc)})
            log(f"draft_n={n}: humaneval={row.get('humaneval')}", panel_log)
        except Exception as exc:  # noqa: BLE001
            panel["errors"].append({"draft_n": n, "error": repr(exc)})
            log(f"draft_n={n}: ERROR {exc!r}", panel_log)
        finally:
            stop_server(proc)
        panel["rows"][str(n)] = row

    (out / "spec_panel.json").write_text(json.dumps(panel, indent=2) + "\n")
    (out / "DONE").write_text(f"{args.tag} {datetime.now().isoformat(timespec='seconds')}\n")
    log("spec panel done", panel_log)
    shim_srv.shutdown()
    os.close(lock_fd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
