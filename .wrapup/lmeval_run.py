#!/usr/bin/env python3
"""One lm-evaluation-harness panel for a single GGUF model.

Starts llama-server on an explicitly chosen free port, waits for health, runs the
standard tasks one lm_eval invocation each, writes results, kills the server.

Two transports are used (protocol is recorded per task in cmd.txt):

  * generative  (gsm8k, ifeval)      -> `lm_eval --model local-chat-completions`
                                        against llama-server /v1/chat/completions
                                        with `--apply_chat_template` so llama-server
                                        applies the model's own jinja template.
  * loglikelihood (mmlu, arc_challenge, truthfulqa_mc2)
                                     -> `lm_eval --model gguf` against a local echo
                                        shim (this file) that reconstructs OpenAI
                                        `echo` prompt logprobs, which llama-server
                                        build 4399 no longer serves (it rejects/ignores
                                        `echo`; see RESEARCH_METHOD.md notes).

The shim is exact: for every continuation token it asks llama-server for the
next-token distribution (`/v1/completions`, max_tokens=1, logprobs=N, temperature 0)
and reads the token's own logprob out of `top_logprobs`.  If the token is not in the
returned top-N it escalates N once and then raises a hard error -- it never returns
0.0 and never guesses.  A task that produces no number is written as null and listed
under "errors" with the raw stderr tail.

Usage:
  lmeval_run.py --model /home/z/hf/X.gguf --tag mu1-mmlu [--limit 100] [--tasks ...]
  lmeval_run.py --model /home/z/hf/X.gguf --selftest      # shim exactness check
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

ROOT = Path("/home/z/hf/research")
WR = ROOT / ".wrapup"
MRES = WR / "mres"
LMENV_PY = WR / "lmenv/bin/python"
LMENV_LM_EVAL = WR / "lmenv/bin/lm_eval"
SHIM_LAUNCHER = WR / "lmeshim/lm_eval_cli.py"

LOGLIK_TASKS = ["mmlu", "arc_challenge", "truthfulqa_mc2"]
GEN_TASKS = ["gsm8k", "ifeval"]
# Headline metric per task, in preference order ("," is part of lm_eval's metric key).
PRIMARY_METRIC = {
    "mmlu": ["acc,none", "acc"],
    "arc_challenge": ["acc_norm,none", "acc_norm", "acc,none"],
    "truthfulqa_mc2": ["acc,none", "acc"],
    "gsm8k": ["exact_match,strict-match", "exact_match,flexible-extract", "exact_match,none"],
    "ifeval": ["prompt_level_strict_acc,none", "prompt_level_strict_acc", "inst_level_strict_acc,none"],
}

# llama.cpp returns OpenAI's new logprobs shape; TOP_N is how many candidates we ask
# for when looking a continuation token up.  TOP_N_RETRY is used once if the first
# lookup misses, after which the shim raises (a missing logprob is 无结果, not 0.0).
TOP_N = 100
TOP_N_RETRY = 8000
# Last-resort tier: ask for the whole vocabulary.  llama-server honours any n_probs up
# to n_vocab (~151k), so this guarantees the target token is present whenever it exists
# at all.  A few ARC items rank the correct-answer token below 8000; without this tier
# the shim correctly refuses to guess and the whole task is lost.
TOP_N_FULL = 200000

CTX_SIZE = 8192
# With --reasoning off this is generous (answers are short); with --reasoning on it is
# the budget that must survive a full thinking block, otherwise content comes back empty.
MAX_GEN_TOKS = 1024
NP_SLOTS = 1
NGL = 99


class ShimError(RuntimeError):
    pass


def log(msg: str, logfile: Path | None = None) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    if logfile is not None:
        with logfile.open("a") as fh:
            fh.write(line + "\n")


def free_port(start: int = 8900, span: int = 100) -> int:
    """Pick a TCP port that is free and prove it with `ss -ltn`."""
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
    raise SystemExit(f"no free port in {start}..{start + span}")


class EchoShim:
    """Rebuild OpenAI-style `echo` prompt logprobs on top of llama-server.

    llama-server build 4399 only returns logprobs for *generated* tokens, so a
    continuation token T is scored by asking for the next-token distribution after
    T's prefix and reading T's own logprob out of that distribution's top_logprobs.
    """

    def __init__(self, llama_base: str, logfile: Path):
        self.llama = llama_base.rstrip("/")
        self.logfile = logfile
        # llama-server caches the prompt KV between requests; reuse it.
        self.session = requests.Session()
        self._tok_cache: dict[str, list[int]] = {}
        self._tok_lock = threading.Lock()
        self.requests_made = 0

    def log(self, msg: str) -> None:
        log(msg, self.logfile)

    # ---- llama-server primitives -------------------------------------------------
    def tokenize(self, text: str) -> list[int]:
        with self._tok_lock:
            cached = self._tok_cache.get(text)
        if cached is not None:
            return cached
        r = self.session.post(f"{self.llama}/tokenize", json={"content": text}, timeout=120)
        r.raise_for_status()
        toks = r.json()["tokens"]
        with self._tok_lock:
            if len(self._tok_cache) < 4096:
                self._tok_cache[text] = toks
        return toks

    def _distribution(self, prompt_ids: list[int], n_probs: int) -> tuple[int, str, float, dict[int, tuple[str, float]]]:
        """Next-token distribution after prompt_ids. Returns (argmax_id, argmax_str, argmax_lp, {id: (str, lp)})."""
        self.requests_made += 1
        r = self.session.post(
            f"{self.llama}/v1/completions",
            json={"prompt": prompt_ids, "max_tokens": 1, "temperature": 0,
                  "logprobs": n_probs, "seed": 1234},
            timeout=900,
        )
        r.raise_for_status()
        lp = r.json()["choices"][0]["logprobs"]["content"][0]
        top = {int(t["id"]): (t["token"], float(t["logprob"])) for t in lp["top_logprobs"]}
        return int(lp["id"]), lp["token"], float(lp["logprob"]), top

    # ---- OpenAI echo emulation ---------------------------------------------------
    def echo(self, context: str, continuation: str) -> dict:
        if not continuation:
            raise ShimError("empty continuation")
        c_ids = self.tokenize(context)
        p_ids = self.tokenize(context + continuation)
        if p_ids[: len(c_ids)] != c_ids:
            raise ShimError(
                f"tokenizer is not prefix-stable: tokenize(context) is not a prefix of "
                f"tokenize(context+continuation) (ctx={len(c_ids)} full={len(p_ids)})"
            )
        cont_ids = p_ids[len(c_ids):]
        if not cont_ids:
            raise ShimError("continuation tokenises to zero tokens")

        tokens = [context]
        text_offset = [0, len(context)]
        token_logprobs = [0.0]
        top_logprobs: list[dict[str, float]] = [{}]

        for j in range(len(c_ids), len(p_ids)):
            target = p_ids[j]
            argmax_id, argmax_str, argmax_lp, top = self._distribution(p_ids[:j], TOP_N)
            if target not in top:
                argmax_id, argmax_str, argmax_lp, top = self._distribution(p_ids[:j], TOP_N_RETRY)
            if target not in top:
                # Full-vocabulary tier: exact, just a larger payload.  Only a handful of
                # items ever reach it.
                argmax_id, argmax_str, argmax_lp, top = self._distribution(p_ids[:j], TOP_N_FULL)
            if target not in top:
                raise ShimError(
                    f"continuation token id={target} absent even from the full-vocabulary "
                    f"distribution at prompt position {j} -- refusing to guess"
                )
            tok_str, tok_lp = top[target]
            tokens.append(tok_str)
            text_offset.append(text_offset[-1] + len(tok_str))
            token_logprobs.append(tok_lp)
            top_logprobs.append({s: v for s, v in top.values()})

        # One extra "generated" entry, taken from the last distribution's own response,
        # exactly as the legacy echo shape expects (lm_eval's get_result sums [idx:-1]).
        tokens.append(argmax_str)
        text_offset.append(text_offset[-1] + len(argmax_str))
        token_logprobs.append(argmax_lp)
        top_logprobs.append({s: v for s, v in top.values()})

        return {
            "choices": [{
                "text": continuation,
                "index": 0,
                "logprobs": {
                    "tokens": tokens,
                    "text_offset": text_offset,
                    "token_logprobs": token_logprobs,
                    "top_logprobs": top_logprobs,
                },
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": len(p_ids), "completion_tokens": 1,
                      "total_tokens": len(p_ids) + 1},
            "object": "text_completion",
        }

    def completions(self, body: dict) -> dict:
        if body.get("echo"):
            if "__continuation" not in body or "__context" not in body:
                raise ShimError(
                    "loglikelihood request without __context/__continuation: the shim cannot "
                    "recover the context boundary from a concatenated prompt and will not guess"
                )
            return self.echo(body["__context"], body["__continuation"])
        # anything else: plain proxy (generation, tokenizer, health ...)
        r = self.session.post(f"{self.llama}/v1/completions", json=body, timeout=1800)
        return r.json()


def make_handler(shim: EchoShim):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _respond(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as exc:  # noqa: BLE001
                self._respond(400, {"error": f"bad json: {exc}"})
                return
            try:
                if self.path.rstrip("/") != "/v1/completions":
                    self._respond(404, {"error": f"shim serves /v1/completions only, got {self.path}"})
                    return
                self._respond(200, shim.completions(body))
            except ShimError as exc:
                shim.log(f"SHIM ERROR: {exc}")
                self._respond(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                shim.log(f"SHIM FAIL: {exc!r}")
                self._respond(500, {"error": repr(exc)})

        def do_GET(self):  # noqa: N802
            self._respond(404, {"error": "shim has no GET endpoints"})

        def log_message(self, *args):  # silence request logging
            return

    return Handler


def start_shim(shim: EchoShim, port: int) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(shim))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ------------------------------------------------------------------------------------
def llama_version(binary: str) -> str:
    out = subprocess.run([binary, "--version"], capture_output=True, text=True)
    return (out.stdout + out.stderr).strip().replace("\n", " | ")


def resolve_model(model: str) -> str:
    p = Path(model)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        raise SystemExit(f"model not found: {model}")
    return str(Path(os.path.realpath(p)))


def start_llama(binary: str, model: str, port: int, logfile: Path,
                reasoning: str = "off") -> subprocess.Popen:
    # `--reasoning off` is set at the SERVER level, not by editing the prompt: without it
    # an instruct model spends the whole generation budget inside reasoning_content and
    # the scored `content` comes back empty (measured: gsm8k/ifeval scored 0.0000 with
    # empty raw responses).  The prompt text is left exactly as the benchmark defines it.
    cmd = [binary, "-m", model, "--port", str(port), "--host", "127.0.0.1",
           "-c", str(CTX_SIZE), "-np", str(NP_SLOTS), "-ngl", str(NGL), "--jinja",
           "--reasoning", reasoning]
    log("llama-server: " + " ".join(cmd), logfile)
    fh = logfile.open("a")
    proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(300):
        try:
            if requests.get(f"http://127.0.0.1:{port}/health", timeout=3).json().get("status") == "ok":
                return proc
        except Exception:  # noqa: BLE001
            pass
        if proc.poll() is not None:
            raise SystemExit(f"llama-server exited early (rc={proc.returncode}); see {logfile}")
        time.sleep(1)
    raise SystemExit(f"llama-server never became healthy; see {logfile}")


def stop_llama(proc: subprocess.Popen | None, logfile: Path) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
    log("llama-server stopped", logfile)


# ------------------------------------------------------------------------------------
def run_cmd(cmd: list[str], env: dict, task_log: Path, timeout: int) -> int:
    with task_log.open("a") as fh:
        fh.write("# " + " ".join(cmd) + "\n")
        fh.flush()
        try:
            return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                  env=env, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            fh.write(f"\n[panel] TIMEOUT after {timeout}s\n")
            return 124


def extract_metric(results: dict, task: str) -> tuple[float | None, str | None]:
    entry = results.get(task)
    if entry is None:
        for key in results:
            if key == task or key.startswith(task + "/"):
                entry = results[key]
                break
    if not isinstance(entry, dict):
        return None, None
    for key in PRIMARY_METRIC.get(task, []):
        val = entry.get(key)
        if isinstance(val, (int, float)):
            return float(val), key
    for key, val in entry.items():
        if key != "alias" and isinstance(val, (int, float)):
            return float(val), key
    return None, None


def extract_n(doc: dict, task: str) -> int | None:
    entry = (doc.get("results") or {}).get(task)
    if isinstance(entry, dict) and isinstance(entry.get("sample_len"), int):
        return entry["sample_len"]
    samples = doc.get("n-samples") or doc.get("n_samples") or {}
    entry = samples.get(task)
    if isinstance(entry, dict):
        if isinstance(entry.get("effective"), int):
            return entry["effective"]
        if isinstance(entry.get("original"), int):
            return entry["original"]
    if isinstance(entry, int):
        return entry
    return None


def newest_output(pattern: str) -> Path | None:
    hits = sorted(glob.glob(pattern), key=os.path.getmtime)
    return Path(hits[-1]) if hits else None


def tail(path: Path, n: int = 40) -> list[str]:
    if not path.exists():
        return [f"(no log at {path})"]
    lines = path.read_text(errors="replace").splitlines()
    return lines[-n:]


# ------------------------------------------------------------------------------------
def task_spec(task: str, shim_port: int, llama_port: int, limit: int | None,
              out_dir: Path) -> tuple[list[str], Path]:
    out_json = out_dir / f"lmeval_{task}.json"
    limit_args = [] if not limit else ["--limit", str(limit)]
    if task in GEN_TASKS:
        cmd = [str(LMENV_LM_EVAL), "--model", "local-chat-completions",
               "--model_args", f"base_url=http://127.0.0.1:{llama_port}/v1/chat/completions",
               "--tasks", task, "--apply_chat_template", "--gen_kwargs",
               f"temperature=0,max_gen_toks={MAX_GEN_TOKS}",
               *limit_args, "--output_path", str(out_json)]
    else:
        cmd = [str(LMENV_PY), str(SHIM_LAUNCHER),
               "--model", "gguf",
               "--model_args", f"base_url=http://127.0.0.1:{shim_port},max_length={CTX_SIZE}",
               "--tasks", task,
               *limit_args, "--output_path", str(out_json)]
    return cmd, out_json


def run_panel(args) -> int:
    model = resolve_model(args.model)
    tag = args.tag
    out_dir = MRES / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    panel_log = out_dir / "panel.log"
    llama_port = args.llama_port or free_port(8900)
    shim_port = args.shim_port or free_port(llama_port + 1)
    for port in (llama_port, shim_port):
        if f":{port} " in subprocess.run(["ss", "-ltnH"], capture_output=True, text=True).stdout:
            raise SystemExit(f"port {port} is already bound -- refusing to touch another project's server")

    llama_bin = args.llama_bin
    version = llama_version(llama_bin)
    limit = args.limit  # None/0 => full suite
    tasks = args.tasks or (LOGLIK_TASKS + GEN_TASKS)

    log(f"=== panel tag={tag} model={model}", panel_log)
    log(f"llama-server binary: {llama_bin} :: {version}", panel_log)
    log(f"ports: llama={llama_port} shim={shim_port}", panel_log)
    log(f"tasks={tasks} limit={limit}", panel_log)

    shim = EchoShim(f"http://127.0.0.1:{llama_port}", panel_log)
    srv = start_shim(shim, shim_port)
    proc = None
    panel = {"tag": tag, "model": model, "tasks": {}, "n": {}, "errors": [],
             "reasoning": args.reasoning, "ctx_size": CTX_SIZE, "max_gen_toks": MAX_GEN_TOKS}
    timings = {}
    try:
        proc = start_llama(llama_bin, model, llama_port, out_dir / "server.log", args.reasoning)
        # a healthy port is not proof the weights answer: demand one real completion
        probe = requests.post(f"http://127.0.0.1:{llama_port}/v1/completions",
                              json={"prompt": "1+1=", "max_tokens": 1, "temperature": 0},
                              timeout=300).json()
        log(f"smoke completion ok: {probe['choices'][0]['text']!r}", panel_log)

        env = dict(os.environ)
        # Every dataset we need is already cached under ~/.cache/huggingface.  Without these
        # flags lm_eval re-contacts huggingface.co on every task and a transient DNS failure
        # (common on this network) kills the task -- measured: mmlu came back null with
        # "[Errno -3] Temporary failure in name resolution" while the cache was intact.
        env["HF_HUB_OFFLINE"] = "1"
        env["HF_DATASETS_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        for task in tasks:
            cmd, out_json = task_spec(task, shim_port, llama_port, limit, out_dir)
            task_log = out_dir / f"lmeval_{task}.log"
            log(f"--- {task}: running", panel_log)
            t0 = time.time()
            rc = run_cmd(cmd, env, task_log, timeout=args.task_timeout)
            elapsed = time.time() - t0
            timings[task] = elapsed
            produced = newest_output(str(out_dir / f"lmeval_{task}*.json"))
            value, metric = (None, None)
            n = None
            if rc == 0 and produced is not None:
                try:
                    doc = json.loads(produced.read_text())
                    value, metric = extract_metric(doc.get("results", {}), task)
                    n = extract_n(doc, task)
                except Exception as exc:  # noqa: BLE001
                    rc = rc or 1
                    log(f"{task}: could not parse {produced}: {exc!r}", panel_log)
            panel["tasks"][task] = value
            panel["n"][task] = n
            if value is None:
                panel["errors"].append({"task": task, "returncode": rc,
                                        "metric": metric,
                                        "output_json": str(produced) if produced else None,
                                        "stderr_tail": tail(task_log)})
                log(f"{task}: NO RESULT (rc={rc}) after {elapsed:.1f}s", panel_log)
            else:
                log(f"{task}: {metric}={value:.4f} n={n} in {elapsed:.1f}s", panel_log)
    finally:
        stop_llama(proc, panel_log)
        srv.shutdown()

    panel["timings_s"] = {k: round(v, 1) for k, v in timings.items()}
    panel["llama_server"] = {"binary": llama_bin, "version": version, "port": llama_port,
                             "args": ["-c", CTX_SIZE, "-np", NP_SLOTS, "-ngl", NGL, "--jinja"]}
    panel["shim"] = {"port": shim_port, "top_n": TOP_N, "top_n_retry": TOP_N_RETRY,
                     "llama_requests": shim.requests_made}
    panel["limit_per_task"] = limit
    (out_dir / "lmeval_panel.json").write_text(json.dumps(panel, indent=2) + "\n")

    cmd_lines = []
    for task in tasks:
        cmd, _ = task_spec(task, shim_port, llama_port, limit, out_dir)
        cmd_lines.append(" ".join(cmd))
    (out_dir / "cmd.txt").write_text(
        "\n".join(cmd_lines)
        + f"\n\n# llama-server: {llama_bin} -m {model} --port {llama_port} --host 127.0.0.1"
          f" -c {CTX_SIZE} -np {NP_SLOTS} -ngl {NGL} --jinja\n"
        + f"# echo shim: http://127.0.0.1:{shim_port} (in-process, see lmeval_run.py) -> {version}\n"
    )
    (out_dir / "DONE").write_text(f"{tag} {datetime.now().isoformat(timespec='seconds')}\n")
    log(f"panel done: {out_dir}/lmeval_panel.json", panel_log)
    ok = [t for t in tasks if panel["tasks"].get(t) is not None]
    log(f"real numbers: {ok}", panel_log)
    return 0


# ------------------------------------------------------------------------------------
def run_selftest(args) -> int:
    model = resolve_model(args.model)
    out_dir = MRES / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    panel_log = out_dir / "shim_selftest.log"
    llama_port = args.llama_port or free_port(8900)
    shim_port = args.shim_port or free_port(llama_port + 1)
    llama_bin = args.llama_bin
    version = llama_version(llama_bin)
    log(f"=== shim selftest :: {llama_bin} :: {version}", panel_log)
    shim = EchoShim(f"http://127.0.0.1:{llama_port}", panel_log)
    srv = start_shim(shim, shim_port)
    proc = None
    ok = True
    try:
        proc = start_llama(llama_bin, model, llama_port, out_dir / "server.log")
        context = "The capital of France is"
        r = requests.post(f"http://127.0.0.1:{llama_port}/v1/completions",
                          json={"prompt": context, "max_tokens": 1, "temperature": 0,
                                "logprobs": TOP_N}, timeout=300).json()
        lp = r["choices"][0]["logprobs"]["content"][0]
        argmax_tok, argmax_lp = lp["token"], float(lp["logprob"])
        top = [(t["token"], float(t["logprob"])) for t in lp["top_logprobs"]]
        non_argmax = top[1]

        def shim_lp(continuation: str) -> float:
            body = {"echo": True, "__context": context, "__continuation": continuation,
                    "max_tokens": 1, "logprobs": 1, "temperature": 0}
            return shim.completions(body)["choices"][0]["logprobs"]["token_logprobs"][1]

        # HTTP round-trip as well, so the served path is what we validated
        http = requests.post(f"http://127.0.0.1:{shim_port}/v1/completions",
                             json={"echo": True, "__context": context,
                                   "__continuation": non_argmax[0], "max_tokens": 1,
                                   "logprobs": 1, "temperature": 0}, timeout=300).json()
        http_lp = http["choices"][0]["logprobs"]["token_logprobs"][1]

        a_lp = shim_lp(argmax_tok)
        b_lp = shim_lp(non_argmax[0])
        print(f"CASE A continuation={argmax_tok!r} (argmax)")
        print(f"  shim lp_cont      = {a_lp!r}")
        print(f"  llama lp(argmax)  = {argmax_lp!r}")
        print(f"  abs diff          = {abs(a_lp - argmax_lp):.3e}")
        print(f"CASE B continuation={non_argmax[0]!r} (non-argmax, rank 2)")
        print(f"  shim lp_cont      = {b_lp!r}")
        print(f"  llama top_logprob = {non_argmax[1]!r}")
        print(f"  abs diff          = {abs(b_lp - non_argmax[1]):.3e}")
        print(f"HTTP round-trip  lp_cont = {http_lp!r}  diff vs arg B = {abs(http_lp - non_argmax[1]):.3e}")
        print("top-5:", [(t, round(v, 4)) for t, v in top[:5]])
        if abs(a_lp - argmax_lp) > 1e-6:
            print("FAIL: case A mismatch"); ok = False
        if abs(b_lp - non_argmax[1]) > 1e-6:
            print("FAIL: case B mismatch"); ok = False
        if abs(http_lp - non_argmax[1]) > 1e-6:
            print("FAIL: HTTP round-trip mismatch"); ok = False
        print("SELFTEST", "PASS" if ok else "FAIL")
        log(f"selftest {'PASS' if ok else 'FAIL'}", panel_log)
    finally:
        stop_llama(proc, panel_log)
        srv.shutdown()
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", default="selftest")
    ap.add_argument("--limit", type=int, default=None,
                    help="lm_eval --limit (per task); 0/omitted = full suite")
    ap.add_argument("--tasks", nargs="+", default=None)
    ap.add_argument("--llama-bin", default=os.environ.get("LLAMA_SERVER", "llama-server"))
    ap.add_argument("--llama-port", type=int, default=None)
    ap.add_argument("--shim-port", type=int, default=None)
    ap.add_argument("--task-timeout", type=int, default=7200)
    ap.add_argument("--reasoning", default="off", choices=["off", "on", "auto"],
                    help="server-level thinking mode; recorded in the panel json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.limit == 0:
        args.limit = None
    return run_selftest(args) if args.selftest else run_panel(args)


if __name__ == "__main__":
    sys.exit(main())
