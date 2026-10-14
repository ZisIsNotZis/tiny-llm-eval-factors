#!/usr/bin/env python3
"""KV-cache and sampling panels on the STANDARD benchmarks.

Tables E (KV) and F (sampling) in report.html were still backed only by the old
MultiPL-E panel, so they had one column of ten.  The SSOT plan says every variable must be
measured on the full standard set; this panel does that.

One model, several configurations, each running the same reduced-but-sufficient suite:
  mmlu       --limit 8  (per subject, so n=456; loglikelihood, deterministic)
  gsm8k      --limit 50 (the most bpw-sensitive generative column, F9)
  ifeval     --limit 50
  humaneval  full 164   (the most bpw-sensitive code column, F9)

The suite is deliberately not the full one: a variable sweep multiplies the cost by the
number of configurations, and these four columns carry the signal (two loglikelihood/knowledge,
one reasoning, one instruction, one code).

Usage:
  variant_panel.py --model X.gguf --tag m130-kv --axis kv
  variant_panel.py --model X.gguf --tag m131-sampling --axis sampling
"""
from __future__ import annotations

import argparse
import glob
import importlib.util as ilu
import json
import os
import socket
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path("/home/z/hf/research")
WR = ROOT / ".wrapup"
MRES = WR / "mres"
LMEVAL = WR / "lmenv/bin/lm_eval"
LMEVAL_PY = WR / "lmenv/bin/python"
SHIM_LAUNCHER = WR / "lmeshim/lm_eval_cli.py"
EVALPLUS = WR / "evalpy/bin/evalplus.codegen"
EVALPLUS_EV = WR / "evalpy/bin/evalplus.evaluate"
LLAMA = os.environ.get("LLAMA_SERVER", "/home/z/.local/bin/llama-server")
LOCK = "/tmp/llama_gpu.lock"

OFFLINE = dict(os.environ)
OFFLINE.update({"HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})

_spec = ilu.spec_from_file_location("lmeval_run", str(WR / "lmeval_run.py"))
lmeval_run = ilu.module_from_spec(_spec)
_spec.loader.exec_module(lmeval_run)

# axis -> list of (label, extra llama-server args, sampling kwargs for the API)
AXES = {
    "kv": [
        ("f16/f16", ["--cache-type-k", "f16", "--cache-type-v", "f16"], {}),
        ("q8_0/q8_0", ["--cache-type-k", "q8_0", "--cache-type-v", "q8_0"], {}),
        ("q4_0/q4_0", ["--cache-type-k", "q4_0", "--cache-type-v", "q4_0"], {}),
    ],
    "sampling": [
        ("greedy", [], {"temperature": 0}),
        ("temp0.3", [], {"temperature": 0.3}),
        ("temp0.7", [], {"temperature": 0.7}),
        ("greedy-topk1", [], {"temperature": 0, "top_k": 1}),
        ("greedy-topk200", [], {"temperature": 0, "top_k": 200}),
    ],
}


def log(m, f=None):
    line = f"[{datetime.now():%H:%M:%S}] {m}"
    print(line, flush=True)
    if f:
        with open(f, "a") as fh:
            fh.write(line + "\n")


def free_port(start=8900, span=100):
    listening = subprocess.run(["ss", "-ltnH"], capture_output=True, text=True).stdout
    for p in range(start, start + span):
        if f":{p} " in listening:
            continue
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
            except OSError:
                continue
            return p
    raise SystemExit("no free port")


def start_server(model, port, extra, logfile):
    cmd = [LLAMA, "-m", model, "--port", str(port), "--host", "127.0.0.1", "-c", "8192",
           "-np", "1", "-ngl", "99", "--jinja", "--reasoning", "off", *extra]
    log("llama-server: " + " ".join(cmd), logfile)
    fh = open(logfile, "a")
    proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                            start_new_session=True, env=OFFLINE)
    for _ in range(300):
        try:
            if b'"ok"' in urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=3).read():
                return proc
        except Exception:
            pass
        if proc.poll() is not None:
            raise SystemExit(f"server died rc={proc.returncode}")
        time.sleep(1)
    raise SystemExit("server never healthy")


def stop(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


def run(cmd, logfile, timeout=7200):
    with open(logfile, "a") as fh:
        fh.write("# " + " ".join(cmd) + "\n")
        fh.flush()
        return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                              timeout=timeout, env=OFFLINE).returncode


def newest(prefix):
    fs = sorted(glob.glob(prefix + "*.json"), key=os.path.getmtime)
    return Path(fs[-1]) if fs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--axis", required=True, choices=sorted(AXES))
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    out = MRES / args.tag
    out.mkdir(parents=True, exist_ok=True)
    plog = str(out / "panel.log")
    model = os.path.realpath(args.model)

    lock_fd = os.open(LOCK, os.O_RDWR | os.O_CREAT)
    try:
        import fcntl
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("ABORT: GPU lock held", plog)
        return 3

    port = free_port()
    shim_port = free_port(port + 1)
    shim = lmeval_run.EchoShim(f"http://127.0.0.1:{port}", Path(plog))
    shim_srv = lmeval_run.start_shim(shim, shim_port)

    panel = {"tag": args.tag, "model": model, "axis": args.axis, "rows": {}, "errors": []}
    log(f"=== variant panel tag={args.tag} axis={args.axis}", plog)

    for label, extra, kws in AXES[args.axis]:
        row = {"label": label, "llama_args": extra, "sampling": kws}
        proc = start_server(model, port, extra, str(out / "server.log"))
        try:
            kstr = ",".join(f"{k}={v}" for k, v in kws.items()) or "temperature=0"
            for task in ("mmlu", "gsm8k", "ifeval"):
                lim = 8 if task == "mmlu" else args.limit
                oj = out / f"{args.axis}_{label.replace('/', '_')}_{task}.json"
                if task == "mmlu":
                    cmd = [str(LMEVAL_PY), str(SHIM_LAUNCHER), "--model", "gguf",
                           "--model_args", f"base_url=http://127.0.0.1:{shim_port},max_length=8192",
                           "--tasks", task, "--limit", str(lim), "--output_path", str(oj)]
                else:
                    cmd = [str(LMEVAL), "--model", "local-chat-completions",
                           "--model_args", f"base_url=http://127.0.0.1:{port}/v1/chat/completions",
                           "--tasks", task, "--apply_chat_template",
                           "--gen_kwargs", f"{kstr},max_gen_toks=1024",
                           "--limit", str(lim), "--output_path", str(oj)]
                rc = run(cmd, str(out / f"{args.axis}_{label.replace('/', '_')}_{task}.log"))
                val = None
                prod = newest(str(oj)[:-5] + "_")
                if rc == 0 and prod:
                    try:
                        node = json.load(open(prod))["results"].get(task, {})
                        for k in ("exact_match,flexible-extract", "acc,none", "acc_norm,none",
                                  "prompt_level_strict_acc,none"):
                            if node.get(k) is not None:
                                val = node[k]
                                break
                    except Exception:
                        pass
                row[task] = val
                log(f"{label}: {task}={val}", plog)

            cg = out / "codegen" / label.replace("/", "_")
            cg.mkdir(parents=True, exist_ok=True)
            temp = str(kws.get("temperature", 0.0))
            # evalplus asserts "Temperature must be positive for sampling" unless --greedy is
            # given explicitly, so the temperature-0 configurations need the flag.
            greedy = ["--greedy", "True"] if float(temp) == 0.0 else []
            rc = run([str(EVALPLUS), f"{args.tag}-{label.replace('/', '_')}", "humaneval",
                      "--backend", "openai", "--base_url", f"http://127.0.0.1:{port}/v1",
                      "--temperature", temp, *greedy, "--root", str(cg)],
                     str(out / f"{args.axis}_{label.replace('/', '_')}_code.log"))
            # evalplus writes TWO sample files: `<...>_temp_T.jsonl` (full code, prompt included)
            # and `<...>_temp_T.raw.jsonl` (the bare continuation).  Scoring the .raw file as
            # if it were complete code fails all 164 problems -- measured here.  The non-raw
            # file is the one codepanel.sh scores and the one evalplus expects.
            cands = [p for p in cg.rglob("*_openai_temp_*.jsonl") if ".raw." not in p.name]
            samples = sorted(cands)[0] if cands else None
            if rc == 0 and samples:
                run([str(EVALPLUS_EV), "humaneval", "--samples", str(samples)],
                    str(out / f"{args.axis}_{label.replace('/', '_')}_code.log"))
                ev = next(cg.rglob("*_eval_results.json"), None)
                if ev:
                    try:
                        evd = json.load(open(ev))["eval"]
                        npass = sum(1 for v in evd.values()
                                    for x in (v if isinstance(v, list) else [v])
                                    if isinstance(x, dict) and x.get("base_status") == "pass")
                        row["humaneval"] = npass / len(evd) if evd else None
                        row["humaneval_n"] = len(evd)
                    except Exception as exc:
                        panel["errors"].append({"label": label, "code": repr(exc)})
            log(f"{label}: humaneval={row.get('humaneval')}", plog)
        except Exception as exc:  # noqa: BLE001
            panel["errors"].append({"label": label, "error": repr(exc)})
            log(f"{label}: ERROR {exc!r}", plog)
        finally:
            stop(proc)
        panel["rows"][label] = row

    (out / "variant_panel.json").write_text(json.dumps(panel, indent=2) + "\n")
    (out / "DONE").write_text(f"{args.tag} {datetime.now().isoformat(timespec='seconds')}\n")
    log("variant panel done", plog)
    shim_srv.shutdown()
    os.close(lock_fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
