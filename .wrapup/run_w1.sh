#!/bin/bash
# W1 — repeat-noise measurement.
#
# The DB has zero replicates (the unique index forbids them), so run-to-run
# stochasticity was never measured. This script repeats one frozen protocol
# N times to measure it directly, for both greedy and sampling decoding.
#
# Frozen protocol (matches the manualeig quant ladders):
#   model   Qwen3.5-2B-UD-Q4_K_XL
#   ctx     2048
#   KV      q8_0 / q8_0
#   top_p   0.95   top_k 40   min_p 0.05
#   bench   humaneval (164 items)  [+ mbpp]
#
# Outputs: .wrapup/wres/<bench>/<alias>_openai_temp_<t>.jsonl  (completions)
#          .wrapup/wres/<bench>/<alias>_openai_temp_<t>_eval_results.json
#          .wrapup/w1_summary.jsonl  (one line per run)
set -u
cd /home/z/hf/research/.wrapup
PY=evalpy/bin/evalplus.codegen
EV=evalpy/bin/evalplus.evaluate
ROOT=/home/z/hf/research/.wrapup/wres
LOG=/home/z/hf/research/.wrapup/w1.log
SUMMARY=/home/z/hf/research/.wrapup/w1_summary.jsonl
MODEL=/home/z/hf/Qwen3.5-2B-UD-Q4_K_XL.gguf
MODELTAG=Qwen3.5-2B-UD-Q4_K_XL
PORT=8080
BASE=http://127.0.0.1:$PORT/v1
N=${N:-5}

echo "=== W1 start $(date) model=$MODELTAG N=$N ===" >> "$LOG"

# --- start server (reused across all repeats) ---
llama-server -m "$MODEL" --port $PORT --host 127.0.0.1 -ngl 99 -c 2048 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
SRV=$!
for i in $(seq 1 60); do curl -s $BASE/models >/dev/null 2>&1 && break; sleep 2; done
curl -s $BASE/models >/dev/null 2>&1 || { echo "server failed" >> "$LOG"; kill $SRV; exit 1; }
echo "server ready pid=$SRV" >> "$LOG"

run_one() {  # bench temp rep
  local bench="$1" temp="$2" rep="$3"
  local alias="w1-2bq4-r${rep}"
  local extra=""
  [ "$temp" = "0.0" ] && extra="--greedy True"
  local out="$ROOT/$bench/${alias}_openai_temp_${temp}.jsonl"
  echo "[$(date +%H:%M:%S)] codegen $bench temp=$temp rep=$rep" >> "$LOG"
  timeout 3600 $PY "$alias" "$bench" --backend openai --base_url "$BASE" \
    --temperature "$temp" $extra --root "$ROOT" >> "$LOG" 2>&1
  python3 dedup_jsonl.py "$out" >> "$LOG" 2>&1
  echo "[$(date +%H:%M:%S)] evaluate $bench temp=$temp rep=$rep" >> "$LOG"
  timeout 3600 $EV "$bench" --samples="$out" >> "$LOG" 2>&1
  local ev="$ROOT/$bench/${alias}_openai_temp_${temp}_eval_results.json"
  local score bad
  score=$(python3 -c "import json;d=json.load(open('$ev'));print(d['pass_at_k']['plus']['pass@1'])" 2>/dev/null)
  bad=$(python3 -c "
import json
t=b=0
for line in open('$out'):
    line=line.strip()
    if not line: continue
    t+=1
    if not (json.loads(line).get('solution') or '').strip(): b+=1
print(b/t if t else 0)" 2>/dev/null)
  echo "{\"model\":\"$MODELTAG\",\"bench\":\"$bench\",\"temp\":$temp,\"rep\":$rep,\"score\":${score:-null},\"bad_rate\":${bad:-null}}" >> "$SUMMARY"
  echo "[$(date +%H:%M:%S)] DONE $bench temp=$temp rep=$rep score=$score bad=$bad" >> "$LOG"
}

# Trimmed design: greedy repeat (determinism check) + sampling repeat (the key
# measurement) on HumanEval, plus a cross-bench sampling check on MBPP.
for rep in 1 2 3;  do run_one humaneval 0.0 "$rep"; done
for rep in 1 2 3 4 5; do run_one humaneval 0.3 "$rep"; done
for rep in 1 2 3;  do run_one mbpp 0.3 "$rep"; done

kill $SRV 2>/dev/null
echo "=== W1 end $(date) ===" >> "$LOG"
