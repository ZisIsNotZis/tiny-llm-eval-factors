#!/bin/bash
# M5 — full weight-quant ladder on a small (fast) model, across languages.
#
# Answers: where does the quant-response curve saturate, and does the Q2->Q3
# step replicate *below* it (IQ2) and *above* it (Q4/Q5)?
#
# Frozen protocol: ctx 4096, KV q8_0/q8_0, top_p .95 / top_k 40 / min_p .05,
# raw completion (MultiPL-E native), greedy, 768 max tokens.
set -u
cd /home/z/hf/research/.wrapup
LOG=/home/z/hf/research/.wrapup/m5.log
SUMMARY=/home/z/hf/research/.wrapup/m5_summary.jsonl
MRES=/home/z/hf/research/.wrapup/mres
PORT=8080
BASE=http://127.0.0.1:$PORT
LANGS="${LANGS:-cpp java js py}"
PY=python3
# tag:model
PANELS="${PANELS:-e2b-q2:gemma-4-E2B-it-UD-Q2_K_XL.gguf e2b-q3:gemma-4-E2B-it-UD-Q3_K_XL.gguf e4b-q2:gemma-4-E4B-it-UD-Q2_K_XL.gguf e4b-q3:gemma-4-E4B-it-UD-Q3_K_XL.gguf gr3b-q2:granite-4.1-3b-Q2_K.gguf gr3b-q3:granite-4.1-3b-Q3_K_M.gguf}"

mkdir -p "$MRES"
echo "=== M5 start $(date) langs=[$LANGS] panels=[$PANELS] ===" >> "$LOG"

start_server() {
  llama-server -m "/home/z/hf/$1" --port $PORT --host 127.0.0.1 -ngl 99 -c 4096 \
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
  for lang in $LANGS; do
    samples="$MRES/m3-${tag}-${lang}.jsonl"
    echo "[$(date +%H:%M:%S)] gen $tag $lang" >> "$LOG"
    timeout 7200 $PY mpl_run.py gen --lang "$lang" --mode raw --greedy \
      --max_tokens 768 --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
    $PY mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
    $PY - "$tag" "$lang" "${samples%.jsonl}_eval.json" "$SUMMARY" <<'PY' >> "$LOG" 2>&1
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
done

echo "=== M5 end $(date) ===" >> "$LOG"
