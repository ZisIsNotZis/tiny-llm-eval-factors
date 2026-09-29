#!/usr/bin/env python3
"""Collect scores + bad_rates for the W1/W2 wrap-up runs from eval_results.json.

evalplus 0.3.1 does not persist `pass_at_k` in `*_eval_results.json`, so the
score is recomputed from the per-task `plus_status` map. Writes
w1_summary.jsonl / w2_summary.jsonl.
"""
import glob
import json
import os
import re
import sys

ROOT = "/home/z/hf/research/.wrapup/wres"


def score_of(ev):
    with open(ev) as f:
        d = json.load(f)["eval"]
    if not d:
        return None
    p = sum(1 for k, v in d.items() if v[0].get("plus_status") == "pass")
    return p / len(d)


def bad_of(jsonl):
    t = b = 0
    with open(jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            t += 1
            if not (json.loads(line).get("solution") or "").strip():
                b += 1
    return b / t if t else None


def main(tag):
    out = []
    pat = re.compile(r"^w1-2bq4-r(\d+)_openai_temp_([0-9.]+)_eval_results\.json$")
    pat2 = re.compile(r"^w2-(.+)-r(\d+)_openai_temp_([0-9.]+)_eval_results\.json$")
    for ev in glob.glob(f"{ROOT}/*/*_eval_results.json"):
        base = os.path.basename(ev)
        if tag == "w1" and not base.startswith("w1-"):
            continue
        if tag == "w2" and not base.startswith("w2-"):
            continue
        m = pat.match(base) or pat2.match(base)
        if not m:
            continue
        bench = ev.split("/")[-2]
        jsonl = ev.replace("_eval_results.json", ".jsonl")
        if not os.path.exists(jsonl):
            continue
        if pat.match(base):
            model, rep, temp = "Qwen3.5-2B-UD-Q4_K_XL", m.group(1), m.group(2)
        else:
            model, rep, temp = m.group(1), m.group(2), m.group(3)
        out.append({"model": model, "bench": bench, "temp": float(temp),
                    "rep": int(rep), "score": score_of(ev), "bad_rate": bad_of(jsonl)})
    out.sort(key=lambda r: (r["model"], r["bench"], r["temp"], r["rep"]))
    dest = f"/home/z/hf/research/.wrapup/{tag}_summary.jsonl"
    with open(dest, "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {dest}: {len(out)} runs")
    for r in out:
        print("  ", r["model"], r["bench"], f"t={r['temp']}", f"r={r['rep']}",
              f"score={r['score']:.4f}" if r["score"] is not None else "score=NA",
              f"bad={r['bad_rate']:.3f}" if r["bad_rate"] is not None else "bad=NA")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "w1")
