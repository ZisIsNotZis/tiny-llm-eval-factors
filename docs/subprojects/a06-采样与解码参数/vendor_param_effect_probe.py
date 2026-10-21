#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a06: does the vendor arm's sampling actually reach the sampler?

The question this settles: a parameter can be written into a protocol string and
still never be applied.  "The output changed when I changed X" is a weak test --
on one prompt, a real effect can coincide and a large parameter can be invisible.
So this probe uses STRUCTURAL endpoints instead of nudges:

  * temperature -- `temperature=0` (argmax) vs `temperature=1.0` must differ while
    the seed is fixed and each setting repeats identically;
  * top_k       -- `top_k=1` collapses the candidate set to the argmax, so its
    output must EQUAL the temperature-0 output.  A parameter that is being ignored
    cannot make that happen;
  * top_p       -- `top_p=0.1` is the same kind of collapse, same test;
  * min_p       -- `min_p=0.9` keeps only near-max tokens, so it must differ from
    the open `temperature=1.0` sample;
  * presence_penalty -- 0 vs 2.0 vs 5.0 must produce at least two distinct texts.

It runs both channels the a06 vendor arm uses, because they are different code
paths inside llama-server:

  /completion              <- `mpl_run.py` raw mode (R1)
  /v1/chat/completions     <- lm-eval `local-chat-completions` (R2)

Precondition: a llama-server already listening on --port, launched WITH the five
vendor values as server flags, so `/props` is expected to echo them.  Run it under
the same GPU flock as the server; it issues short requests and does not restart
the server.

    python3 "docs/subprojects/a06-采样与解码参数/vendor_param_effect_probe.py" --port 8141

Exit status: 0 when every check passes on both endpoints; 1 when any check fails
(and it prints which); 2 when the server is unreachable or `/props` does not echo
the vendor values, because then the probe cannot tell "ignored by the sampler"
from "never handed to the server".
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

WANT = {"temperature": 1.0, "top_p": 1.0, "top_k": 20, "min_p": 0.0,
        "presence_penalty": 2.0}
SEED = 1234
N = 60

PROMPTS_TEXT = ["Write one short sentence about rivers.",
                "Name three colours, separated by commas."]
PROMPTS_CODE = ["def count_words(s):\n    \"\"\"Return the number of words in s.\"\"\"\n",
                "Write a Python function that returns the sum of the first n squares.\n"]


def call(port, path, payload, timeout=180):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read()), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}: {exc.read()[:200].decode(errors='replace')}"


def completion(port, prompt, body):
    d, err = call(port, "/completion",
                  {"prompt": prompt, "n_predict": N, "seed": SEED,
                   "cache_prompt": False, **body})
    if err:
        return None, err
    return d["content"], None


def chat(port, msg, body):
    d, err = call(port, "/v1/chat/completions",
                  {"model": "x", "max_tokens": N, "seed": SEED,
                   "messages": [{"role": "user", "content": msg}], **body})
    if err:
        return None, err
    return d["choices"][0]["message"]["content"], None


BODIES = {"T0": {"temperature": 0.0},
          "T1": {"temperature": 1.0},
          "T1k1": {"temperature": 1.0, "top_k": 1},
          "T1p01": {"temperature": 1.0, "top_p": 0.1},
          "T1m09": {"temperature": 1.0, "min_p": 0.9},
          "T1pp0": {"temperature": 1.0, "presence_penalty": 0.0},
          "T1pp5": {"temperature": 1.0, "presence_penalty": 5.0}}


def run_channel(label, fn, prompts, port):
    print(f"\n== {label} ==")
    failures = []
    for i, p in enumerate(prompts):
        got = {}
        for name, body in BODIES.items():
            txt, err = fn(port, p, body)
            if err:
                print(f"  prompt {i} {name}: {err}")
                failures.append(f"{label} prompt {i} {name}: {err}")
                continue
            got[name] = txt
        if len(got) < len(BODIES):
            continue
        rep_t0, e0 = fn(port, p, {"temperature": 0.0})
        rep_t1, e1 = fn(port, p, {"temperature": 1.0})
        checks = [
            ("seed makes temp-0 repeatable", e0 is None and got["T0"] == rep_t0),
            ("seed makes temp-1 repeatable", e1 is None and got["T1"] == rep_t1),
            ("temperature 0 vs 1.0 differ", got["T0"] != got["T1"]),
            ("top_k=1 equals greedy", got["T1k1"] == got["T0"]),
            ("top_p=0.1 equals greedy", got["T1p01"] == got["T0"]),
            ("min_p=0.9 differs from temp-1.0", got["T1m09"] != got["T1"]),
            ("presence_penalty 0 vs 2.0 differ", got["T1pp0"] != got["T1"]),
            ("presence_penalty 5.0 vs 2.0 differ", got["T1pp5"] != got["T1"]),
        ]
        print(f"  prompt {i}: {p[:36]!r}")
        for name, ok in checks:
            print(f"    {name:<36}: {'PASS' if ok else 'FAIL'}")
            if not ok:
                failures.append(f"{label} prompt {i}: {name}")
        print(f"    texts: " + " | ".join(f"{k}={v[:28]!r}" for k, v in got.items()))
    return failures


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="8141")
    args = ap.parse_args(argv)

    try:
        props, err = call(args.port, "/props", None) if False else (None, None)
        with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/props", timeout=10) as r:
            props = json.loads(r.read())
    except Exception as exc:  # noqa: BLE001
        print(f"UNMEASURED: no server on port {args.port}: {exc!r}", file=sys.stderr)
        return 2
    params = props.get("default_generation_settings", {}).get("params", {})
    got = {k: params.get(k) for k in WANT}
    bad = [k for k in WANT if got[k] is None or abs(float(got[k]) - WANT[k]) > 1e-6]
    print(f"server /props params: {got}")
    print(f"server n_slots      : {props.get('total_slots')}")
    if bad:
        print(f"UNMEASURED: /props does not echo the vendor values {bad}; "
              f"launch the server with the five flags first", file=sys.stderr)
        return 2

    failures = []
    failures += run_channel("/completion  (R1: mpl_run.py raw)", completion,
                            PROMPTS_CODE, args.port)
    failures += run_channel("/v1/chat/completions  (R2: lm-eval)", chat,
                            PROMPTS_TEXT, args.port)
    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) did not hold")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: all five vendor values reach the sampler on both channels")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
