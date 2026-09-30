#!/bin/bash
# M4 — tool-calling (BFCL) panel.
#
# The study had no agentic/function-calling axis at all; this adds one.
# Protocol: prompt-based tool calling, thinking disabled via chat_template_kwargs,
# greedy, ctx 8192, KV q8_0/q8_0, 512 max tokens.
set -u
cd /home/z/hf/research/.wrapup
LOG=/home/z/hf/research/.wrapup/m4.log
SUMMARY=/home/z/hf/research/.wrapup/m4_summary.jsonl
MRES=/home/z/hf/research/.wrapup/mres
PORT=8080
BASE=http://127.0.0.1:$PORT
PY=python3
CATS="${CATS:-simple_python,multiple,parallel,parallel_multiple,irrelevance}"
PANELS="${PANELS:-q2:Qwen3.5-4B-UD-Q2_K_XL.gguf q3:Qwen3.5-4B-UD-Q3_K_XL.gguf}"

mkdir -p "$MRES"
echo "=== M4 start $(date) cats=[$CATS] panels=[$PANELS] ===" >> "$LOG"

start_server() {
  llama-server -m "/home/z/hf/$1" --port $PORT --host 127.0.0.1 -ngl 99 -c 8192 \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  SRV=$!
  for i in $(seq 1 150); do
    if curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"'; then
      echo "server ready: $1" >> "$LOG"; return 0
    fi
    sleep 2
  done
  echo "SERVER FAIL $1" >> "$LOG"; return 1
}

for spec in $PANELS; do
  tag="${spec%%:*}"; model="${spec#*:}"
  start_server "$model" || continue
  samples="$MRES/m4-${tag}.jsonl"
  echo "[$(date +%H:%M:%S)] gen $tag" >> "$LOG"
  timeout 10800 $PY bfcl_run.py gen --categories "$CATS" --samples "$samples" \
    --mode prompt --max_tokens 512 --base_url "$BASE" >> "$LOG" 2>&1
  $PY bfcl_run.py eval --samples "$samples" >> "$LOG" 2>&1
  $PY - "$tag" "${samples%.jsonl}_eval.json" "$SUMMARY" <<'PY' >> "$LOG" 2>&1
import json,sys
tag,ev,dest=sys.argv[1:4]
d=json.load(open(ev))
with open(dest,"a") as f:
    f.write(json.dumps({"model":tag,"n":d["n"],"correct":d["correct"],
                        "score":d["score"],"per_category":d["per_category"],
                        "protocol":"bfcl-prompt-nothink-greedy"})+"\n")
print("recorded",tag,d["n"],round(d["score"],4))
PY
  echo "[$(date +%H:%M:%S)] DONE $tag" >> "$LOG"
  kill $SRV 2>/dev/null; sleep 3
done

echo "=== M4 end $(date) ===" >> "$LOG"
