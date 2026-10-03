#!/bin/bash
# One frozen-protocol MultiPL-E panel for BRAINSTORM Tier-1.
# Usage: panel_one.sh <tag> <gguf-basename> <summary.jsonl> <protocol> [langs]
# Protocol matches .wrapup/run_m1.sh / run_m5.sh: ctx 4096, KV q8_0/q8_0,
# top_p .95 / top_k 40 / min_p .05, raw completion, greedy, 768 max tokens.
# Refuses to run if port 8080 is held by a non-project server; smoke-tests the
# model with one real completion before spending GPU time on the panel.
set -u
cd /home/z/hf/research/.wrapup
TAG=$1; MODEL=$2; SUMMARY=$3; PROTO=${4:-mpl-raw-greedy-768}; LANGS=${5:-"cpp py"}
PORT=8080; BASE=http://127.0.0.1:$PORT; PY=python3
LOG=/home/z/hf/research/.wrapup/m23_m24_m25.log
MRES=/home/z/hf/research/.wrapup/mres
mkdir -p "$MRES"

if curl -s --max-time 3 "$BASE/health" >/dev/null 2>&1; then
  if pgrep -f "llama-server .*-m /home/z/hf/" >/dev/null 2>&1; then
    pkill -f "llama-server .*-m /home/z/hf/"; sleep 3
  else
    echo "[$(date +%H:%M:%S)] ABORT $TAG: port $PORT held by foreign server" >> "$LOG"
    exit 2
  fi
fi

llama-server -m "/home/z/hf/$MODEL" --port $PORT --host 127.0.0.1 -ngl 99 -c 4096 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT INT TERM
ok=0
for i in $(seq 1 150); do
  if curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"'; then ok=1; break; fi
  sleep 2
done
if [ $ok -ne 1 ]; then echo "[$(date +%H:%M:%S)] SERVER FAIL $TAG $MODEL" >> "$LOG"; exit 1; fi

SM=$(curl -s --max-time 180 $BASE/completion -H 'Content-Type: application/json' \
  -d '{"prompt":"def add(a, b):\n    return a","n_predict":8,"temperature":0,"top_p":0.95,"top_k":40,"min_p":0.05}')
echo "[$(date +%H:%M:%S)] smoke $TAG: $(echo "$SM" | head -c 200)" >> "$LOG"
if ! echo "$SM" | grep -q '"content"'; then
  echo "[$(date +%H:%M:%S)] SMOKE FAIL $TAG $MODEL" >> "$LOG"; exit 1
fi

for lang in $LANGS; do
  samples="$MRES/mt1-${TAG}-${lang}.jsonl"
  echo "[$(date +%H:%M:%S)] gen $TAG $lang" >> "$LOG"
  timeout 7200 $PY mpl_run.py gen --lang "$lang" --mode raw --greedy \
    --max_tokens 768 --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  $PY mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
  $PY - "$TAG" "$lang" "${samples%.jsonl}_eval.json" "$SUMMARY" "$PROTO" <<'PY' >> "$LOG" 2>&1
import json,sys
tag,lang,ev,dest,proto=sys.argv[1:6]
d=json.load(open(ev))
with open(dest,"a") as f:
    f.write(json.dumps({"model":tag,"lang":lang,"n":d["n"],"pass":d["pass"],
                        "score":d["score"],"protocol":proto})+"\n")
print("recorded",tag,lang,d["n"],round(d["score"],4))
PY
  echo "[$(date +%H:%M:%S)] DONE $TAG $lang" >> "$LOG"
done
echo "[$(date +%H:%M:%S)] PANEL DONE $TAG $MODEL" >> "$LOG"
