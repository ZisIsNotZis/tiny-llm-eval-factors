#!/bin/bash
# M8 (T3 step 1) — BFCL live_* single-turn categories, native tools.
#
# Adds the six live_* categories to bfcl_run.py. Protocol matches M7 so results are
# comparable with the earlier tool-calling panel: native OpenAI tool-calling, thinking
# disabled via chat_template_kwargs, greedy, ctx 8192, KV q8_0/q8_0, 512 max tokens.
# Relevance handling: live_irrelevance => no call expected; live_relevance => a call is
# required (bundled data ships no possible_answer for either).
set -u
cd /home/z/hf/research/.wrapup
LOG=/home/z/hf/research/.wrapup/m8.log
SUMMARY=/home/z/hf/research/.wrapup/m8_summary.jsonl
MRES=/home/z/hf/research/.wrapup/mres
PORT=8080
BASE=http://127.0.0.1:$PORT
PY=python3
CATS="${CATS:-live_simple,live_multiple,live_parallel,live_parallel_multiple,live_irrelevance,live_relevance}"
PANELS="${PANELS:-qwen2b-q3:Qwen3.5-2B-UD-Q3_K_XL.gguf qwen4b-q2:Qwen3.5-4B-UD-Q2_K_XL.gguf qwen4b-q3:Qwen3.5-4B-UD-Q3_K_XL.gguf e2b-q2:gemma-4-E2B-it-UD-Q2_K_XL.gguf e2b-q3:gemma-4-E2B-it-UD-Q3_K_XL.gguf gr3b-q2:granite-4.1-3b-Q2_K.gguf gr3b-q3:granite-4.1-3b-Q3_K_M.gguf}"
LIMIT="${LIMIT:-0}"

mkdir -p "$MRES"
echo "=== M8 start $(date) cats=[$CATS] limit=$LIMIT panels=[$PANELS] ===" >> "$LOG"

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
  start_server "$model" || { echo "SKIP $tag (load fail)" >> "$LOG"; continue; }
  samples="$MRES/m8-${tag}.jsonl"
  echo "[$(date +%H:%M:%S)] gen $tag" >> "$LOG"
  timeout 10800 $PY bfcl_run.py gen --categories "$CATS" --samples "$samples" \
    --mode tools --max_tokens 512 --limit "$LIMIT" --base_url "$BASE" >> "$LOG" 2>&1
  $PY bfcl_run.py eval --samples "$samples" >> "$LOG" 2>&1
  $PY - "$tag" "${samples%.jsonl}_eval.json" "$SUMMARY" <<'PY' >> "$LOG" 2>&1
import json,sys
tag,ev,dest=sys.argv[1:4]
d=json.load(open(ev))
with open(dest,"a") as f:
    f.write(json.dumps({"model":tag,"n":d["n"],"correct":d["correct"],
                        "score":d["score"],"per_category":d["per_category"],
                        "protocol":"bfcl-native-tools-nothink-greedy"})+"\n")
print("recorded",tag,d["n"],round(d["score"],4))
PY
  echo "[$(date +%H:%M:%S)] DONE $tag" >> "$LOG"
  kill $SRV 2>/dev/null; sleep 3
done

echo "=== M8 end $(date) ===" >> "$LOG"
