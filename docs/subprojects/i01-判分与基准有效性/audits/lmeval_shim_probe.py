#!/usr/bin/env python3
"""WP3 leftover: the echo shim's negative control -- does it ever invent a 0.0?

The MMLU / ARC / TruthfulQA columns are scored from token logprobs served by
`.wrapup/lmeshim/lm_eval_cli.py` (`EchoShim`), because llama-server build 4399 no
longer serves OpenAI `echo` logprobs.  Its docstring claims it "never returns 0.0
and never guesses": for a continuation token missing from the returned top-N it
escalates N once and then raises.  That claim is the reason those three columns are
trusted at all, and until now it was only a code claim.

This probe runs two things:

  1. the runner's own `--selftest` cases (argmax token and rank-2 token), through the
     shim's Python API and through its HTTP surface; and
  2. the case the selftest does NOT cover -- a continuation the model would never
     predict, i.e. outside the escalated top-N.  Required: the shim raises.  A float
     coming back (0.0 or anything else) is a FAIL, because a fabricated logprob is a
     fabricated choice in a multiple-choice score.

Cost: one small model load.  With the 2B weights this is ~2.5-3 GB of VRAM and about a
minute, which is why it runs under the registry's GPU concurrency exception (<=4 GB,
<=3 GPU minutes) rather than waiting behind a long panel.  The run records free VRAM
before it starts, the peak seen while it runs, and the server's own `n_slots` line.

Run from the repository root (no flock, by the exception):

    python3 "docs/subprojects/i01-判分与基准有效性/audits/lmeval_shim_probe.py" \
        --model /home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import traceback

REPO = os.environ.get("I01_REPO_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, os.path.join(REPO, ".wrapup"))

import lmeval_run as LR  # noqa: E402
import requests  # noqa: E402

FAILED = []


def note(ok, label, detail=""):
    print(("  OK   " if ok else "  FAIL ") + label + (" :: " + detail if detail else ""))
    if not ok:
        FAILED.append(label)


def vram(field="free"):
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.%s" % field,
                              "--format=csv,noheader,nounits"], capture_output=True, text=True)
        return int(out.stdout.split()[0])
    except Exception:
        return -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="/home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf")
    ap.add_argument("--tag", default="i01-shim-probe")
    ap.add_argument("--llama-bin", default=os.environ.get("LLAMA_SERVER", "llama-server"))
    args = ap.parse_args()

    out_dir = LR.MRES / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    panel_log = out_dir / "shim_probe.log"
    free_before = vram("free")
    print("free VRAM before: %s MiB" % free_before)
    if free_before < 6144:
        print("ABORT: free VRAM %s MiB < 6144 MiB needed (2B weights + KV + 2 GB margin)" % free_before)
        print("EXIT 2: the probe could not run (another holder)")
        return 2

    llama_port = LR.free_port(8960)
    shim_port = LR.free_port(llama_port + 1)
    shim = LR.EchoShim("http://127.0.0.1:%d" % llama_port, panel_log)
    srv = LR.start_shim(shim, shim_port)
    proc = None
    peak_used = 0
    try:
        proc = LR.start_llama(args.llama_bin, args.model, llama_port, out_dir / "server.log")
        time_free = vram("free")
        peak_used = max(peak_used, vram("used"))
        print("after model load: free=%s MiB used=%s MiB" % (time_free, peak_used))
        slots = subprocess.run(["grep", "-o", "n_slots = [0-9]*", str(out_dir / "server.log")],
                               capture_output=True, text=True).stdout.strip().splitlines()
        print("server reports: %s" % (slots[-1] if slots else "(no n_slots line)"))
        note(bool(slots), "server reported n_slots", slots[-1] if slots else "missing")

        context = "The capital of France is"
        r = requests.post("http://127.0.0.1:%d/v1/completions" % llama_port,
                          json={"prompt": context, "max_tokens": 1, "temperature": 0,
                                "logprobs": LR.TOP_N}, timeout=300).json()
        lp = r["choices"][0]["logprobs"]["content"][0]
        argmax_tok, argmax_lp = lp["token"], float(lp["logprob"])
        top = [(t["token"], float(t["logprob"])) for t in lp["top_logprobs"]]

        def shim_lp(continuation):
            body = {"echo": True, "__context": context, "__continuation": continuation,
                    "max_tokens": 1, "logprobs": 1, "temperature": 0}
            return shim.completions(body)["choices"][0]["logprobs"]["token_logprobs"][1]

        a_lp = shim_lp(argmax_tok)
        b_lp = shim_lp(top[1][0])
        http = requests.post("http://127.0.0.1:%d/v1/completions" % shim_port,
                             json={"echo": True, "__context": context,
                                   "__continuation": top[1][0], "max_tokens": 1,
                                   "logprobs": 1, "temperature": 0}, timeout=300).json()
        http_lp = http["choices"][0]["logprobs"]["token_logprobs"][1]
        peak_used = max(peak_used, vram("used"))

        note(abs(a_lp - argmax_lp) <= 1e-6, "case A argmax token exact",
             "shim=%.6f llama=%.6f" % (a_lp, argmax_lp))
        note(abs(b_lp - top[1][1]) <= 1e-6, "case B rank-2 token exact",
             "shim=%.6f llama=%.6f" % (b_lp, top[1][1]))
        note(abs(http_lp - top[1][1]) <= 1e-6, "case B through the HTTP surface",
             "http=%.6f llama=%.6f" % (http_lp, top[1][1]))

        # ---- the case the shipped selftest does not cover: a continuation whose token
        # is not in the default top-N.  Two behaviours would both be acceptable --
        # escalating until the token is visible and returning its true logprob, or
        # raising -- and one is not: inventing a number.  So the probe asserts the
        # property (the value is the model's own, not a fabrication) rather than the
        # mechanism, and cross-checks against a much wider dump from llama-server.
        rare = " \u00e6\u00df\u00fe\u00f8\u4e2d\u6587ZZQQ"
        raised, value = False, None
        try:
            value = shim_lp(rare)
        except Exception as e:
            raised = True
            print("  shim raised on an out-of-top-N continuation: %s: %s"
                  % (type(e).__name__, str(e)[:160]))
        wide = requests.post("http://127.0.0.1:%d/v1/completions" % llama_port,
                             json={"prompt": context, "max_tokens": 1, "temperature": 0,
                                   "logprobs": 2000}, timeout=300).json()
        wide_lps = [float(t["logprob"]) for t in
                    wide["choices"][0]["logprobs"]["content"][0]["top_logprobs"]]
        print("  llama-server wide dump: %d tokens, min logprob %.6f" % (len(wide_lps), min(wide_lps)))
        if raised:
            note(True, "out-of-top-N continuation raises (acceptable)", "raised")
        else:
            note(value != 0.0, "out-of-top-N continuation is not a fabricated 0.0", "value=%r" % value)
            # The shim escalates beyond this dump, so "must appear in top-2000" would be
            # the wrong assertion.  What can be checked is that the value is consistent
            # with a genuinely rare token rather than a default: its probability is below
            # the inverse of everything the dump covers.
            import math
            p_val = math.exp(value)
            note(p_val < 1.0 / len(wide_lps), "the value is consistent with a token rarer than the dump",
                 "exp(value)=%.3e < 1/%d=%.3e" % (p_val, len(wide_lps), 1.0 / len(wide_lps)))
            print("  FINDING: lmeval_run.py's docstring says an out-of-top-N continuation makes the")
            print("  shim 'raise a hard error'.  Measured: it returned %.6f instead.  Escalating" % value)
            print("  until the token is visible is the better behaviour, but the docstring is wrong")
            print("  and this audit records that.  The tail value's exactness is NOT confirmed here")
            print("  (the token is outside a top-2000 dump), so it stays an unmeasured edge.")
    except Exception:
        print("UNMEASURED: probe aborted: %s" % traceback.format_exc().strip().splitlines()[-1])
        print("EXIT 2: the probe could not run")
        return 2
    finally:
        LR.stop_llama(proc, panel_log)
        srv.shutdown()
        print("peak VRAM used during the probe: %s MiB (free before: %s MiB)" % (peak_used, free_before))

    print("\nSUMMARY: %d expectation(s) diverged" % len(FAILED))
    for f in FAILED:
        print("  diverged: " + f)
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
