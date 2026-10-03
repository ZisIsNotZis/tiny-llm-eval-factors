#!/usr/bin/env python3
"""M28 — draft/MTP length x speed probe (no benchmark; timing only).

For a fixed llama-server MTP config it fires N_PROMPT-mode requests of
``n_predict`` tokens at temperature 0 and reports generation speed plus
draft acceptance from the server's own ``timings`` block.

Usage: m28_speed.py --base_url URL --draft_n N --out m28_speed.jsonl [--reps 3]

Modes (all raw /completion, continuation-style):
  code     MultiPL-E humaneval-cpp prompt #0 continued
  prose    plain English prose continuation
  longctx  ~8k-token concatenation of repo markdown + a summarisation cue
"""
import argparse
import json
import statistics
import time
import urllib.request

PROMPTS = "/tmp/MultiPL-E/prompts"
LONGCTX_FILES = [
    "/home/z/hf/research/FINAL_REPORT.md",
    "/home/z/hf/research/conclusions.md",
    "/home/z/hf/research/RESEARCH_METHOD.md",
]
PROSE = """The history of the printed book begins long before Gutenberg assembled his movable
type, in the woodblock workshops of Tang dynasty China and in the paper mills that had
slowly spread westward along the trade routes. What changed in the middle of the fifteenth
century was not the idea of printing but the economics of it: metal type could be cast,
reused, and reset, so the cost of a second edition fell far below the cost of the first.
Printers discovered that errors propagate as readily as ideas, and that a corrected sheet
"""
N_PREDICT = 256
REPS = 3


def post(url, payload, timeout=600):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def build_prompts():
    first = json.loads(open(f"{PROMPTS}/humaneval-cpp.jsonl").readline())
    longtext = ""
    for path in LONGCTX_FILES:
        longtext += open(path).read() + "\n\n"
        if len(longtext) > 32000:
            break
    return {
        "code": first["prompt"],
        "prose": PROSE,
        "longctx": longtext[:32000] + "\n\nSummarise the main findings above in three sentences.\n",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base_url", default="http://127.0.0.1:8080")
    ap.add_argument("--draft_n", type=int, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--n_predict", type=int, default=N_PREDICT)
    args = ap.parse_args()

    prompts = build_prompts()
    base = args.base_url.rstrip("/")
    with open(args.out, "a") as fh:
        for mode, prompt in prompts.items():
            tps, accepts, prompts_n = [], [], []
            for rep in range(args.reps):
                r = post(base + "/completion",
                         {"prompt": prompt, "temperature": 0.0,
                          "n_predict": args.n_predict, "cache_prompt": True})
                t = r["timings"]
                tps.append(t["predicted_per_second"])
                prompts_n.append(t["prompt_n"])
                if t.get("draft_n"):
                    accepts.append(t["draft_n_accepted"] / t["draft_n"])
                print(f"  {mode} rep{rep} {t['predicted_per_second']:.1f} tok/s "
                      f"prompt_n={t['prompt_n']} draft={t.get('draft_n')}"
                      f"/{t.get('draft_n_accepted')}")
            row = {"model": args.model, "mode": mode, "draft_n": args.draft_n,
                   "tok_s": round(statistics.median(tps), 3),
                   "n_predict": args.n_predict, "reps": args.reps,
                   "prompt_n": prompts_n[0],
                   "tok_s_reps": [round(x, 3) for x in tps]}
            if accepts:
                row["accept"] = round(statistics.mean(accepts), 4)
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"recorded {json.dumps(row)}", flush=True)


if __name__ == "__main__":
    main()
