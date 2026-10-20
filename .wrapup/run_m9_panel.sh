#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# One M9 panel: start llama-server, run BFCL generate+evaluate for each category.
# Usage: run_m9_panel.sh <tag> <modelfile> <bfcl-handler> [cats]
set -u
cd ${REPO_ROOT}
WR=${REPO_ROOT}/.wrapup
LOG=${LOG:-$WR/m9.log}
SUM=${SUM:-$WR/m9_summary.jsonl}
BFCL=$WR/bfclenv/bin/bfcl
TOK=/home/z/hf/qwen_tok
tag="$1"; file="$2"; handler="$3"; CATS="${4:-multi_turn_base}"
CTX="${CTX:-98304}"
NP="${NP:-2}"
PORT="${PORT:-8080}"
# If the requested per-slot ctx cannot be allocated (e.g. another process is
# holding GPU memory), retry once at this smaller ctx instead of failing the
# panel. Unset = no fallback.
FALLBACK_CTX="${FALLBACK_CTX:-}"
# Generation/eval wall-clock caps. The defaults suit the short-prompt categories; a
# long-context category on a 27B needs hours (a 2h cap silently truncates the result
# file, and official `evaluate` then aborts with a length mismatch -> accuracy null).
GEN_TO="${GEN_TO:-7200}"
EVAL_TO="${EVAL_TO:-3600}"
# PARTIAL_EVAL=1 adds `--partial-eval` to `bfcl evaluate`: if generation was truncated
# (timeout / a slow 27B), evaluate scores the subset of ids present in the result file
# instead of aborting on the row-count mismatch and writing a null accuracy. The row
# count is recorded in the summary as `n`/`partial` so a subset score is never passed
# off as a full-category number. Default off = unchanged behaviour for other panels.
PARTIAL_EVAL="${PARTIAL_EVAL:-}"

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

start_server() {  # ctx
  echo "[$(date +%H:%M:%S)] server $file ctx=$1 np=$NP port=$PORT" >> "$LOG"
  llama-server -m "/home/z/hf/$file" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$1" -np $NP --jinja \
    --cache-type-k q8_0 --cache-type-v q8_0 >> "$LOG" 2>&1 &
  srv=$!
  for i in $(seq 1 150); do
    curl -s --max-time 3 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q '"status":"ok"' && break
    # a dead server (e.g. CUDA OOM) never becomes healthy: stop waiting early
    kill -0 $srv 2>/dev/null || break
    sleep 2
  done
  curl -s --max-time 5 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q ok
}

start_server "$CTX"
if [ -n "$FALLBACK_CTX" ] && [ "$FALLBACK_CTX" != "$CTX" ] \
   && ! curl -s --max-time 5 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q ok; then
  echo "[$(date +%H:%M:%S)] server failed at ctx=$CTX; retrying at ctx=$FALLBACK_CTX" >> "$LOG"
  kill $srv 2>/dev/null; wait $srv 2>/dev/null; srv=""; sleep 3
  start_server "$FALLBACK_CTX" && CTX="$FALLBACK_CTX"
fi
if ! curl -s --max-time 5 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q ok; then
  echo "SERVER FAIL $file" >> "$LOG"; kill $srv 2>/dev/null; srv=""; exit 1
fi

# Optional (SMOKE=1): demand one REAL completion before spending GPU time on the
# category loop. A healthy /health only proves the weights parsed; panels that
# only bind the port can still answer nothing (the standing queue rule).
if [ "${SMOKE:-0}" = "1" ]; then
  SM=$(curl -s --max-time 300 http://127.0.0.1:$PORT/completion -H 'Content-Type: application/json' \
    -d '{"prompt":"def add(a, b):\n    return a","n_predict":8,"temperature":0}')
  if echo "$SM" | grep -q '"content"'; then
    echo "[$(date +%H:%M:%S)] smoke ok $tag" >> "$LOG"
  else
    echo "SMOKE FAIL $tag $file -> aborting before the long panel" >> "$LOG"
    kill $srv 2>/dev/null; srv=""; exit 1
  fi
fi

IFS=',' read -ra CL <<< "$CATS"
for cat in "${CL[@]}"; do
  # BFCL `generate` defaults to allow_overwrite=False: without this the second panel that
  # shares this handler (e.g. qwen4b-q2 then qwen4b-q3) would generate nothing and `evaluate`
  # would silently re-score the previous quant's responses.
  RRES=${REPO_ROOT}/.wrapup/bfclenv/lib/python3.11/site-packages/result
  find "$RRES/$(echo "$handler" | tr '/' '_')" -name "BFCL_v4_${cat}_result.json" -delete 2>/dev/null
  echo "[$(date +%H:%M:%S)] gen $tag $cat" >> "$LOG"
  REMOTE_OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1 REMOTE_OPENAI_TOKENIZER_PATH=$TOK \
    timeout "$GEN_TO" $BFCL generate --model "$handler" --test-category "$cat" \
    --skip-server-setup --temperature 0 >> "$LOG" 2>&1
  # A truncated `generate` (timeout / crash) leaves fewer result rows than test entries;
  # official `evaluate` then raises mid-run and the accuracy never prints. Surface the
  # row count up front so the failure is visible instead of looking like a null model.
  RES=${REPO_ROOT}/.wrapup/bfclenv/lib/python3.11/site-packages/result
  nres=$(find "$RES/$(echo "$handler" | tr '/' '_')" -name "BFCL_v4_${cat}_result.json" \
         -exec wc -l {} + 2>/dev/null | awk 'NR==1{print $1}')
  echo "[$(date +%H:%M:%S)] generated $cat rows=${nres:-0} (expect 200)" >> "$LOG"
  if [ "${nres:-0}" != "200" ]; then
    echo "[$(date +%H:%M:%S)] WARN $tag $cat: truncated generation (rows=${nres:-0}/200)" >> "$LOG"
  fi
  echo "[$(date +%H:%M:%S)] eval $tag $cat" >> "$LOG"
  acc=$(REMOTE_OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1 REMOTE_OPENAI_TOKENIZER_PATH=$TOK \
    timeout "$EVAL_TO" $BFCL evaluate --model "$handler" --test-category "$cat" \
    ${PARTIAL_EVAL:+--partial-eval} 2>&1 | tee -a "$LOG" \
    | grep -oE "Accuracy: [0-9.]+%" | tail -1 | grep -oE "[0-9.]+")
  proto='bfcl-official-multiturn-temp0'; [ -n "$PARTIAL_EVAL" ] && proto="$proto-partial"
  python3 -c "
import json
print(json.dumps({'model':'$tag','category':'$cat','handler':'$handler',
                  'accuracy':(float('$acc')/100.0 if '$acc' else None),
                  'n':int('${nres:-0}'),
                  'protocol':'$proto'}))" >> "$SUM"
  echo "[$(date +%H:%M:%S)] DONE $tag $cat acc=$acc" >> "$LOG"
done
kill $srv 2>/dev/null; srv=""; sleep 3
echo "[$(date +%H:%M:%S)] panel end $tag" >> "$LOG"
