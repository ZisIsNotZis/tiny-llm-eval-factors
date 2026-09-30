#!/bin/bash
# M1 — MultiPL-E resolution panel.
#
# Purpose: give the study's most reproducible effect (the local Q2->Q3 weight-quant
# step) a properly powered estimate by running it across many languages, instead of
# relying on 164 HumanEval items.
#
# Frozen protocol (matches the W1/W2 protocol):
#   ctx 4096, KV q8_0/q8_0, top_p 0.95 / top_k 40 / min_p 0.05, greedy,
#   raw completion (MultiPL-E native), 768 max tokens, dataset stop tokens.
#
# Panels: Qwen3.5-4B UD-Q2_K_XL and UD-Q3_K_XL, each across the languages below.
set -u
cd /home/z/hf/research/.wrapup
LOG=/home/z/hf/research/.wrapup/m1.log
SUMMARY=/home/z/hf/research/.wrapup/m1_summary.jsonl
MRES=/home/z/hf/research/.wrapup/mres
PORT=8080
BASE=http://127.0.0.1:$PORT
LANGS="${LANGS:-cpp java js rs py rb}"
PY=python3

mkdir -p "$MRES"
echo "=== M1 start $(date) langs=[$LANGS] ===" >> "$LOG"

start_server() {
  llama-server -m "$1" --port $PORT --host 127.0.0.1 -ngl 99 -c 4096 \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  SRV=$!
  for i in $(seq 1 150); do
    if curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"'; then
      echo "server ready (health ok): $1" >> "$LOG"; return 0
    fi
    sleep 2
  done
  echo "SERVER FAIL $1" >> "$LOG"; return 1
}

panel() {  # tag modelpath
  local tag="$1" model="$2"
  start_server "$model" || return
  for lang in $LANGS; do
    local samples="$MRES/m1-${tag}-${lang}.jsonl"
    echo "[$(date +%H:%M:%S)] gen $tag $lang" >> "$LOG"
    timeout 7200 $PY mpl_run.py gen --lang "$lang" --mode raw --greedy \
      --max_tokens 768 --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
    $PY mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
    local ev="${samples%.jsonl}_eval.json"
    $PY - "$tag" "$lang" "$ev" "$SUMMARY" <<'PY' >> "$LOG" 2>&1
import json,sys
tag,lang,ev,dest=sys.argv[1:5]
d=json.load(open(ev))
with open(dest,"a") as f:
    f.write(json.dumps({"model":tag,"lang":lang,"n":d["n"],"pass":d["pass"],
                        "score":d["score"],"protocol":"mpl-raw-greedy-768"})+"\n")
print("recorded",tag,lang,d["n"],round(d["score"],4))
PY
    echo "[$(date +%H:%M:%S)] DONE $tag $lang" >> "$LOG"
  done
  kill $SRV 2>/dev/null; sleep 3
}

panel qwen4b-q2 /home/z/hf/Qwen3.5-4B-UD-Q2_K_XL.gguf
panel qwen4b-q3 /home/z/hf/Qwen3.5-4B-UD-Q3_K_XL.gguf

echo "=== M1 end $(date) ===" >> "$LOG"
