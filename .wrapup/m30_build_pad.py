#!/usr/bin/env python3
"""Build long-input prompt files for the m30 KV-at-length grid.

The earlier m30 was a null by construction: MultiPL-E prompts are short, so
varying the server's `-c` only changed the *allocated* window and every KV cell
scored identically. This builder makes the INPUT long: each of the first N cpp
HumanEval items is prepended with a realistic code preamble assembled from the
*other* items (their MultiPL-E prompt + canonical Python solution), padded to a
token budget just below the target context.

Token counts come from the live llama-server `/tokenize` endpoint (exact for the
model under test); no tokenizer library is assumed.

Output: <outdir>/m30_pad_ctx<CTX>.jsonl  (schema: name/prompt/stop_tokens, so it
drops into `mpl_run.py gen --prompt-file`; `mpl_run.py eval` is untouched and
still scores against the canonical tests) and a `<...>_meta.json` sidecar.
"""
import argparse
import json
import os
import urllib.request

DATA = "/tmp/MultiPL-E/prompts/humaneval-cpp.jsonl"
ORIG = "/tmp/MultiPL-E/datasets/originals"


def tokenize(base_url, text):
    req = urllib.request.Request(
        base_url.rstrip("/") + "/tokenize",
        data=json.dumps({"content": text}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return len(json.loads(r.read().decode())["tokens"])


def build_units(items):
    units = []
    for it in items:
        sol_path = os.path.join(ORIG, it["name"] + ".py")
        try:
            sol = open(sol_path).read()
        except OSError:
            sol = ""
        units.append(it["prompt"] + "\n// canonical Python solution (reference):\n" + sol)
    return units


def pad_one(base_url, real_prompt, units, tok_units, tok_real, budget, skip, target):
    """Assemble filler text whose token count is as close to `budget` as we can get."""
    parts, used, k = [], 0, skip
    # Greedy: cycle through the other units until the token budget is reached.
    while used < budget:
        k = (k + 1) % len(units)
        if k == skip:
            continue
        parts.append(units[k])
        used += tok_units[k]
    filler = "\n".join(parts)
    for _ in range(4):  # trim overshoot; BPE counts are not exactly additive
        full = filler + "\n" + real_prompt
        n = tokenize(base_url, full)
        if n <= target:
            return full, n
        ratio = len(full) / max(n, 1)          # chars per token
        cut = int((n - target) * ratio) + 8
        if len(filler) <= cut:
            break
        filler = filler[:len(filler) - cut]
    full = filler + "\n" + real_prompt
    return full, tokenize(base_url, full)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--ctxs", required=True, help="comma-separated, e.g. 2048,16384,49152")
    ap.add_argument("--reserve", type=int, default=1024,
                    help="tokens left below ctx for generation + specials")
    args = ap.parse_args()

    items = [json.loads(l) for l in open(DATA)][:args.n]
    units = build_units(items)
    tok_units = [tokenize(args.base_url, u) for u in units]
    tok_real = [tokenize(args.base_url, it["prompt"]) for it in items]
    os.makedirs(args.outdir, exist_ok=True)

    for ctx in [int(c) for c in args.ctxs.split(",")]:
        target = ctx - args.reserve
        rows, counts = [], []
        for i, it in enumerate(items):
            budget = target - tok_real[i]
            full, n = pad_one(args.base_url, it["prompt"], units, tok_units,
                              tok_real[i], budget, i, target)
            rows.append({"name": it["name"], "prompt": full,
                         "stop_tokens": it.get("stop_tokens") or []})
            counts.append(n)
        dest = os.path.join(args.outdir, f"m30_pad_ctx{ctx}.jsonl")
        with open(dest, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        meta = {"ctx": ctx, "target_prompt_tokens": target, "n": len(rows),
                "mean_prompt_tokens": sum(counts) / len(counts),
                "min_prompt_tokens": min(counts), "max_prompt_tokens": max(counts)}
        with open(dest.replace(".jsonl", "_meta.json"), "w") as f:
            json.dump(meta, f)
        print(json.dumps(meta))


if __name__ == "__main__":
    main()
