#!/bin/bash
# lg_state.sh <gguf-basename> — print the load-gate verdict recorded in
# .wrapup/loadgate.jsonl: PASS | FAIL | NONE. Exit 0 only for PASS.
# NONE means the CPU load gate has not seen the file yet.
W=/home/z/hf/research/.wrapup
python3 - "$1" "$W/loadgate.jsonl" <<'PY'
import json, sys
name, path = sys.argv[1], sys.argv[2]
state = "NONE"
try:
    for ln in open(path):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("file") == name:
            state = d.get("load", state)
except FileNotFoundError:
    pass
print(state)
sys.exit(0 if state == "PASS" else 1)
PY
