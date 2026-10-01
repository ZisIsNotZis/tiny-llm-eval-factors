#!/bin/bash
# One M9 panel: start llama-server, run BFCL generate+evaluate for each category.
# Usage: run_m9_panel.sh <tag> <modelfile> <bfcl-handler> [cats]
set -u
cd /home/z/hf/research
WR=/home/z/hf/research/.wrapup
LOG=${LOG:-$WR/m9.log}
SUM=${SUM:-$WR/m9_summary.jsonl}
BFCL=$WR/bfclenv/bin/bfcl
TOK=/home/z/hf/qwen_tok
tag="$1"; file="$2"; handler="$3"; CATS="${4:-multi_turn_base}"
CTX="${CTX:-98304}"
NP="${NP:-2}"

echo "[$(date +%H:%M:%S)] server $file" >> "$LOG"
llama-server -m "/home/z/hf/$file" --port 8080 --host 127.0.0.1 -ngl 99 -c $CTX -np $NP --jinja \
  --cache-type-k q8_0 --cache-type-v q8_0 >> "$LOG" 2>&1 &
srv=$!
for i in $(seq 1 150); do
  curl -s --max-time 3 http://127.0.0.1:8080/health 2>/dev/null | grep -q '"status":"ok"' && break
  sleep 2
done
if ! curl -s --max-time 5 http://127.0.0.1:8080/health 2>/dev/null | grep -q ok; then
  echo "SERVER FAIL $file" >> "$LOG"; kill $srv 2>/dev/null; exit 1
fi

IFS=',' read -ra CL <<< "$CATS"
for cat in "${CL[@]}"; do
  echo "[$(date +%H:%M:%S)] gen $tag $cat" >> "$LOG"
  REMOTE_OPENAI_BASE_URL=http://127.0.0.1:8080/v1 REMOTE_OPENAI_TOKENIZER_PATH=$TOK \
    timeout 7200 $BFCL generate --model "$handler" --test-category "$cat" \
    --skip-server-setup --temperature 0 >> "$LOG" 2>&1
  echo "[$(date +%H:%M:%S)] eval $tag $cat" >> "$LOG"
  acc=$(REMOTE_OPENAI_BASE_URL=http://127.0.0.1:8080/v1 REMOTE_OPENAI_TOKENIZER_PATH=$TOK \
    timeout 3600 $BFCL evaluate --model "$handler" --test-category "$cat" 2>&1 | tee -a "$LOG" \
    | grep -oE "Accuracy: [0-9.]+%" | tail -1 | grep -oE "[0-9.]+")
  python3 -c "
import json
print(json.dumps({'model':'$tag','category':'$cat','handler':'$handler',
                  'accuracy':(float('$acc')/100.0 if '$acc' else None),
                  'protocol':'bfcl-official-multiturn-temp0'}))" >> "$SUM"
  echo "[$(date +%H:%M:%S)] DONE $tag $cat acc=$acc" >> "$LOG"
done
kill $srv 2>/dev/null; sleep 3
echo "[$(date +%H:%M:%S)] panel end $tag" >> "$LOG"
