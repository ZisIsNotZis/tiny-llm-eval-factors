#!/bin/bash
# M9 (T3 step 2) — multi-turn BFCL (stateful tool loop) using the bundled func_source_code.
#
# Categories: multi_turn_base + multi_turn_long_context (no out-of-band function prompting,
# so they wire cleanly in native tools mode). Protocol matches M7/M8 (native tools, greedy,
# thinking off) except ctx 16384 to fit the long-context category. Scores recorded by
# bfcl_multi_run.py: strict (all-or-nothing multi_turn_checker) + call_rate/turn_match_rate.
set -u
cd /home/z/hf/research/.wrapup
LOG=/home/z/hf/research/.wrapup/m9.log
SUMMARY=/home/z/hf/research/.wrapup/m9_summary.jsonl
MRES=/home/z/hf/research/.wrapup/mres
PORT=8080
BASE=http://127.0.0.1:$PORT
PY=/home/z/hf/research/.wrapup/bfclenv/bin/python
CATS="${CATS:-multi_turn_base,multi_turn_long_context}"
PANELS="${PANELS:-qwen2b-q2:Qwen3.5-2B-UD-Q2_K_XL.gguf qwen2b-q3:Qwen3.5-2B-UD-Q3_K_XL.gguf qwen4b-q2:Qwen3.5-4B-UD-Q2_K_XL.gguf qwen4b-q3:Qwen3.5-4B-UD-Q3_K_XL.gguf e2b-q2:gemma-4-E2B-it-UD-Q2_K_XL.gguf e2b-q3:gemma-4-E2B-it-UD-Q3_K_XL.gguf gr3b-q2:granite-4.1-3b-Q2_K.gguf gr3b-q3:granite-4.1-3b-Q3_K_M.gguf}"
LIMIT="${LIMIT:-0}"
CTX="${CTX:-16384}"

mkdir -p "$MRES"
echo "=== M9 start $(date) cats=[$CATS] limit=$LIMIT ctx=$CTX panels=[$PANELS] ===" >> "$LOG"

start_server() {
  llama-server -m "/home/z/hf/$1" --port $PORT --host 127.0.0.1 -ngl 99 -c $CTX \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  SRV=$!
  for i in $(seq 1 180); do
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
  samples="$MRES/m9-${tag}.jsonl"
  echo "[$(date +%H:%M:%S)] gen $tag" >> "$LOG"
  timeout 21600 $PY bfcl_multi_run.py --categories "$CATS" --model "$tag" \
    --samples "$samples" --limit "$LIMIT" --base_url "$BASE" >> "$LOG" 2>&1
  if [ -f "${samples%.jsonl}_eval.json" ]; then
    $PY - "$tag" "${samples%.jsonl}_eval.json" "$SUMMARY" <<'PY' >> "$LOG" 2>&1
import json,sys
tag,ev,dest=sys.argv[1:4]
d=json.load(open(ev))
with open(dest,"a") as f:
    f.write(json.dumps(d)+"\n")
print("recorded",tag,d["n"],round(d["strict_score"],4))
PY
  else
    echo "NO EVAL $tag" >> "$LOG"
  fi
  echo "[$(date +%H:%M:%S)] DONE $tag" >> "$LOG"
  kill $SRV 2>/dev/null; sleep 3
done

echo "=== M9 end $(date) ===" >> "$LOG"
