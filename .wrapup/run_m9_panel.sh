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
PORT="${PORT:-8080}"

srv=""
cleanup() { if [ -n "$srv" ]; then kill "$srv" 2>/dev/null; srv=""; fi; }
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

# A panel that dies before its `kill $srv` leaves llama-server holding the port AND the
# inherited GPU flock. If the next panel then trusts the health check, curl answers from the
# *previous* model's server and BFCL scores the wrong model under the new tag (a silent
# wrong-model result). Detect and clear it before starting our own server.
port_locked() { ss -ltnH 2>/dev/null | grep -q ":$PORT "; }
if port_locked; then
  stale=$(fuser -n tcp "$PORT" 2>/dev/null | awk '{print $NF}')
  echo "[$(date +%H:%M:%S)] port $PORT already bound by pid ${stale:-?} ($(ps -o args= -p ${stale:-0} 2>/dev/null | cut -c1-120))" >> "$LOG"
  for pid in $stale; do
    if ps -o args= -p "$pid" 2>/dev/null | grep -q "llama-server .*-m /home/z/hf/"; then
      echo "[$(date +%H:%M:%S)] killing stale llama-server pid $pid left by a previous panel" >> "$LOG"
      kill "$pid" 2>/dev/null
    fi
  done
  for i in $(seq 1 15); do port_locked || break; sleep 1; done
  if port_locked; then
    echo "ABORT $tag: port $PORT still busy; refusing to score another server's responses" >> "$LOG"
    exit 1
  fi
fi

echo "[$(date +%H:%M:%S)] server $file ctx=$CTX np=$NP port=$PORT" >> "$LOG"
llama-server -m "/home/z/hf/$file" --port "$PORT" --host 127.0.0.1 -ngl 99 -c $CTX -np $NP --jinja \
  --cache-type-k q8_0 --cache-type-v q8_0 >> "$LOG" 2>&1 &
srv=$!
for i in $(seq 1 150); do
  curl -s --max-time 3 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q '"status":"ok"' && break
  sleep 2
done
if ! curl -s --max-time 5 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q ok; then
  echo "SERVER FAIL $file" >> "$LOG"; kill $srv 2>/dev/null; srv=""; exit 1
fi

IFS=',' read -ra CL <<< "$CATS"
for cat in "${CL[@]}"; do
  # BFCL `generate` defaults to allow_overwrite=False: without this the second panel that
  # shares this handler (e.g. qwen4b-q2 then qwen4b-q3) would generate nothing and `evaluate`
  # would silently re-score the previous quant's responses.
  RRES=/home/z/hf/research/.wrapup/bfclenv/lib/python3.11/site-packages/result
  find "$RRES/$(echo "$handler" | tr '/' '_')" -name "BFCL_v4_${cat}_result.json" -delete 2>/dev/null
  echo "[$(date +%H:%M:%S)] gen $tag $cat" >> "$LOG"
  REMOTE_OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1 REMOTE_OPENAI_TOKENIZER_PATH=$TOK \
    timeout 7200 $BFCL generate --model "$handler" --test-category "$cat" \
    --skip-server-setup --temperature 0 >> "$LOG" 2>&1
  echo "[$(date +%H:%M:%S)] eval $tag $cat" >> "$LOG"
  acc=$(REMOTE_OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1 REMOTE_OPENAI_TOKENIZER_PATH=$TOK \
    timeout 3600 $BFCL evaluate --model "$handler" --test-category "$cat" 2>&1 | tee -a "$LOG" \
    | grep -oE "Accuracy: [0-9.]+%" | tail -1 | grep -oE "[0-9.]+")
  python3 -c "
import json
print(json.dumps({'model':'$tag','category':'$cat','handler':'$handler',
                  'accuracy':(float('$acc')/100.0 if '$acc' else None),
                  'protocol':'bfcl-official-multiturn-temp0'}))" >> "$SUM"
  echo "[$(date +%H:%M:%S)] DONE $tag $cat acc=$acc" >> "$LOG"
done
kill $srv 2>/dev/null; srv=""; sleep 3
echo "[$(date +%H:%M:%S)] panel end $tag" >> "$LOG"
