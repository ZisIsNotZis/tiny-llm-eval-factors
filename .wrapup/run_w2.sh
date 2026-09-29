#!/bin/bash
# W2 — scale-generalisation ladder on the newly restored Q2/Q3 weights.
#
# Directly attacks the #1 pending question in questions.md ("largest feasible
# anchor for the Q2->Q3 + KV panel") and re-tests the *underpowered* Qwen3.5-4B
# ladder with replicates so it gets real error bars.
#
# Frozen protocol: ctx 2048, KV q8_0/q8_0, top_p 0.95 / top_k 40 / min_p 0.05,
#                 greedy (temp 0) unless noted.
#
# Panels:
#   A  Qwen3.5-9B  : Q2_K_XL vs Q3_K_XL   x  humaneval,mbpp  x  greedy  x  2 reps
#   B  Qwen3.5-4B  : Q2_K_XL vs Q3_K_XL   x  humaneval       x  greedy  x  2 reps
set -u
cd /home/z/hf/research/.wrapup
PY=evalpy/bin/evalplus.codegen
EV=evalpy/bin/evalplus.evaluate
ROOT=/home/z/hf/research/.wrapup/wres
LOG=/home/z/hf/research/.wrapup/w2.log
SUMMARY=/home/z/hf/research/.wrapup/w2_summary.jsonl
PORT=8080
BASE=http://127.0.0.1:$PORT/v1
REPS=${REPS:-2}

echo "=== W2 start $(date) ===" >> "$LOG"

start_server() {  # model
  llama-server -m "$1" --port $PORT --host 127.0.0.1 -ngl 99 -c 2048 \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  SRV=$!
  for i in $(seq 1 90); do curl -s $BASE/models >/dev/null 2>&1 && break; sleep 2; done
  if ! curl -s $BASE/models >/dev/null 2>&1; then
    echo "SERVER FAILED for $1" >> "$LOG"; return 1
  fi
  echo "server ready: $1" >> "$LOG"; return 0
}

run_one() {  # tag modelpath bench temp rep
  local tag="$1" model="$2" bench="$3" temp="$4" rep="$5"
  local alias="w2-${tag}-r${rep}"
  local extra=""; [ "$temp" = "0.0" ] && extra="--greedy True"
  local out="$ROOT/$bench/${alias}_openai_temp_${temp}.jsonl"
  echo "[$(date +%H:%M:%S)] codegen $tag $bench t=$temp r=$rep" >> "$LOG"
  timeout 7200 $PY "$alias" "$bench" --backend openai --base_url "$BASE" \
    --temperature "$temp" $extra --root "$ROOT" >> "$LOG" 2>&1
  python3 dedup_jsonl.py "$out" >> "$LOG" 2>&1
  echo "[$(date +%H:%M:%S)] evaluate $tag $bench t=$temp r=$rep" >> "$LOG"
  timeout 7200 $EV "$bench" --samples="$out" >> "$LOG" 2>&1
  local ev="$ROOT/$bench/${alias}_openai_temp_${temp}_eval_results.json"
  local score
  score=$(python3 -c "
import json
d=json.load(open('$ev'))['eval']
p=sum(1 for k,v in d.items() if (v[0].get('plus_status')=='pass'))
print(p/len(d))" 2>/dev/null)
  echo "{\"model\":\"$tag\",\"bench\":\"$bench\",\"temp\":$temp,\"rep\":$rep,\"score\":${score:-null}}" >> "$SUMMARY"
  echo "[$(date +%H:%M:%S)] DONE $tag $bench t=$temp r=$rep score=$score" >> "$LOG"
}

panel() {  # tag modelpath "bench1 bench2"
  local tag="$1" model="$2" benches="$3"
  start_server "$model" || return
  for bench in $benches; do
    for rep in $(seq 1 $REPS); do
      run_one "$tag" "$model" "$bench" 0.0 "$rep"
    done
  done
  kill $SRV 2>/dev/null; sleep 3
}

panel qwen9b-q2 /home/z/hf/Qwen3.5-9B-UD-Q2_K_XL.gguf "humaneval"
panel qwen9b-q3 /home/z/hf/Qwen3.5-9B-UD-Q3_K_XL.gguf "humaneval"
panel qwen4b-q2 /home/z/hf/Qwen3.5-4B-UD-Q2_K_XL.gguf "humaneval"
panel qwen4b-q3 /home/z/hf/Qwen3.5-4B-UD-Q3_K_XL.gguf "humaneval"

echo "=== W2 end $(date) ===" >> "$LOG"
