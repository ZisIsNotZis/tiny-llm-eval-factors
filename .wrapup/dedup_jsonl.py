#!/usr/bin/env python3
"""Deduplicate an evalplus samples jsonl (keep the last entry per task_id).

evalplus.codegen can append duplicate task entries under --resume; evaluate
asserts one sample per problem, so dedup is required.
"""
import json
import sys

path = sys.argv[1]
best = {}
order = []
with open(path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        tid = o["task_id"]
        if tid not in best:
            order.append(tid)
        best[tid] = o
with open(path, "w") as f:
    for tid in order:
        f.write(json.dumps(best[tid]) + "\n")
print(f"deduped {path}: {len(order)} unique tasks")
