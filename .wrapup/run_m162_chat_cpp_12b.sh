#!/bin/bash
# m162 — gemma-4-12b chat MultiPL-E **cpp** Q2/Q3 under the canonical chat protocol.
#
# WHY: 12b's only cpp chat cells live in m6b, whose protocol string carries
# `;ctx=4096;tmpl=unverified` because that panel ran a different server
# configuration (four slots at ctx 4096, no observed --jinja).  Its py cells were
# re-measured in m161 under `mpl-chat-nothink-greedy-768`, so 12b had no cpp+py
# pair under one protocol and its standard-column cell was missing rather than
# low.  These two cells give it the pair.
#
# Protocol: copied verbatim from run_m161_chat_py.sh (that script's cpp control
# cell is the measured reference for this path), so only the model file and the
# cell tag differ:
#   llama-server -m <gguf> -ngl 99 -c 2048 --cache-type-k q8_0
#     --cache-type-v q8_0 --jinja --top-p 0.95 --top-k 40 --min-p 0.05
#   mpl_run.py gen --mode chat --greedy --max_tokens 768 --strip-thought
#     --chat-kwargs '{"enable_thinking": false}'
#   mpl_run.py eval --lang cpp --samples <cell>.jsonl
# The recorded protocol string is `mpl-chat-nothink-greedy-768`, with no suffix:
# nothing deviates from the canonical chat cells, and a suffix is reserved for a
# cell that does (as m6b's does).
#
# Run under the GPU flock:
#   bash .wrapup/gpu_locked.sh bash .wrapup/run_m162_chat_cpp_12b.sh
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$HERE" || exit 1
LOG=$HERE/m162.log
SUMMARY=$HERE/m162_summary.jsonl
MRES=$HERE/mres
PROMPTS=${MULTIPLE_PROMPTS:-$HERE/prompts}
PORT=${PORT:-8091}
BASE=http://127.0.0.1:$PORT
CTX=${CTX:-2048}
PY=python3
CHAT_KW='{"enable_thinking": false}'
PROTOCOL="mpl-chat-nothink-greedy-768"
CELLS="g12b-q2:gemma-4-12b-it-UD-Q2_K_XL.gguf g12b-q3:gemma-4-12b-it-UD-Q3_K_XL.gguf"
TAGLOG="M162"

mkdir -p "$MRES"
: > "$SUMMARY"
gpu_start=$(date +%s)
echo "[$TAGLOG] panel start $(date) cells=[g12b-q2:cpp g12b-q3:cpp] protocol=$PROTOCOL ctx=$CTX" >> "$LOG"

# --- preflight: the prompt set is the experiment's input, so its contents are
# --- hashed into the log and checked against SHA256SUMS before GPU time is spent.
preflight() {
  local f h missing=0
  for f in "$PROMPTS"/humaneval-*.jsonl; do
    [ -s "$f" ] || { echo "[$TAGLOG] ABORT: prompt set missing $f" >> "$LOG"; missing=1; continue; }
    h=$(sha256sum "$f" | cut -d' ' -f1)
    echo "[$TAGLOG] prompt $(basename "$f") sha256=$h" >> "$LOG"
  done
  [ "$missing" = 0 ] || return 1
  ( cd "$PROMPTS" && sha256sum -c SHA256SUMS --quiet ) >/dev/null 2>&1 || {
    echo "[$TAGLOG] ABORT: prompt set does not match SHA256SUMS in $PROMPTS (a panel run against an unpinned prompt set is not comparable)" >> "$LOG"
    return 1
  }
  echo "[$TAGLOG] preflight ok: prompt set matches SHA256SUMS" >> "$LOG"
}
preflight || exit 2

echo "[$TAGLOG] llama-server $(llama-server --version 2>&1 | tr '\n' ' ')" >> "$LOG"

pid=$(ss -ltnp 2>/dev/null | grep ":$PORT" | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$pid" ] && kill "$pid"; sleep 2

srv=""
cleanup() { [ -n "$srv" ] && kill "$srv" 2>/dev/null; }
trap cleanup EXIT

start_server() {
  llama-server -m "/home/z/hf/$1" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$CTX" \
    --cache-type-k q8_0 --cache-type-v q8_0 --jinja \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  srv=$!
  for _ in $(seq 1 180); do
    kill -0 "$srv" 2>/dev/null || { echo "[$TAGLOG] server DIED $1" >> "$LOG"; return 1; }
    curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && return 0
    sleep 2
  done
  echo "[$TAGLOG] server TIMEOUT $1" >> "$LOG"; kill "$srv" 2>/dev/null; return 1
}

# Number of empty completions, or UNREADABLE when the samples file is missing or
# unparseable -- the two states stay distinct so an infrastructure failure is
# never recorded as a model that produced nothing.
samples_state() {
  "$PY" - "$1" <<'PY'
import json, os, sys
p = sys.argv[1]
if not os.path.exists(p):
    print("UNREADABLE:file-missing"); raise SystemExit
try:
    rows = [json.loads(l) for l in open(p)]
except Exception as e:
    print(f"UNREADABLE:{type(e).__name__}"); raise SystemExit
print(f"{sum(1 for r in rows if not (r.get('completion') or '').strip())}/{len(rows)}")
PY
}

stop_server() { [ -n "$srv" ] && { kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; }; }

# One summary row per cell.  An all-Exception cell is an infrastructure failure,
# not a measured zero, so its score is recorded as null (m48).
record() {   # $1 tag  $2 lang  $3 eval-json
  "$PY" - "$1" "$2" "$3" "$SUMMARY" "$PROTOCOL" <<'PY' >> "$LOG" 2>&1
import json, sys, collections
tag, lang, ev, dest, proto = sys.argv[1:6]
d = json.load(open(ev))
st = collections.Counter(x.get("status") for x in d.get("details", []))
n = d["n"]
score = None if (n and st.get("Exception", 0) == n) else d["score"]
row = {"model": tag, "lang": lang, "n": n, "pass": d["pass"],
       "score": score, "protocol": proto, "statuses": dict(st)}
with open(dest, "a") as f:
    f.write(json.dumps(row) + "\n")
print("[M162] recorded", tag, lang, "n=%d pass=%d score=%s" % (n, d["pass"], score), dict(st))
PY
}

run_cell() {   # $1 tag  $2 lang  $3 model
  local tag="$1" lang="$2" model="$3"
  local samples="$MRES/m162-${tag}-${lang}-chat.jsonl"
  local t0 t1
  start_server "$model" || return 1
  t0=$(date +%s)
  echo "[$TAGLOG] gen $tag $lang mode=chat start=$(date +%H:%M:%S)" >> "$LOG"
  timeout 1800 "$PY" mpl_run.py gen --lang "$lang" --mode chat --greedy \
    --max_tokens 768 --strip-thought --chat-kwargs "$CHAT_KW" \
    --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  local rc=$?
  echo "[$TAGLOG] gen $tag $lang mode=chat end=$(date +%H:%M:%S) rc=$rc" >> "$LOG"
  [ "$rc" = 124 ] && echo "[$TAGLOG] GEN-TIMEOUT $tag $lang (1800s cap, not retried beyond once)" >> "$LOG"
  local state; state=$(samples_state "$samples")
  case "$state" in
    UNREADABLE:*)
      echo "[$TAGLOG] GEN-FAILED $tag $lang mode=chat $state" >> "$LOG"
      stop_server; return 1 ;;
  esac
  local empty=${state%%/*}
  if [ "$empty" -gt 32 ]; then
    echo "[$TAGLOG] CORRUPT $tag $lang mode=chat empty=${state}" >> "$LOG"
    stop_server; return 1
  fi
  timeout 2400 "$PY" mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
  t1=$(date +%s)
  echo "[$TAGLOG] cell $tag $lang wall=$((t1-t0))s (gen+eval)" >> "$LOG"
  record "$tag" "$lang" "${samples%.jsonl}_eval.json"
  stop_server; sleep 3
  return 0
}

# smoke test: a 24 GB card must load the file before any cell time is spent
smoke_file="${CELLS%% *}"; smoke_file="${smoke_file#*:}"
echo "[$TAGLOG] smoke: loading $smoke_file" >> "$LOG"
if start_server "$smoke_file"; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 180 -X POST "$BASE/completion" \
     -H 'Content-Type: application/json' \
     -d '{"prompt":"int f(){return 1;}","n_predict":8,"temperature":0}')
  echo "[$TAGLOG] smoke: health=ok completion_http=$code" >> "$LOG"
  stop_server
  [ "$code" = "200" ] || { echo "[$TAGLOG] ABORT: smoke completion != 200" >> "$LOG"; exit 1; }
else
  echo "[$TAGLOG] ABORT: smoke load failed" >> "$LOG"; exit 1
fi

# one cell, at most one retry; `ok=0` means the cell is unmeasured
run_with_retry() {   # $1 tag  $2 lang  $3 model
  local tag="$1" lang="$2" model="$3" attempt ok=0
  for attempt in 1 2; do
    if run_cell "$tag" "$lang" "$model"; then ok=1; break; fi
    [ "$attempt" = 1 ] && { echo "[$TAGLOG] retry $tag $lang mode=chat (attempt 1)" >> "$LOG"; sleep 5; }
  done
  [ "$ok" = 1 ] || echo "[$TAGLOG] GAVE UP $tag $lang mode=chat (unmeasured)" >> "$LOG"
}

for spec in $CELLS; do
  run_with_retry "${spec%%:*}" cpp "${spec#*:}"
done

gpu_end=$(date +%s)
echo "[$TAGLOG] GPU wall=$(( (gpu_end-gpu_start)/60 ))m$(( (gpu_end-gpu_start)%60 ))s (whole panel, incl. loads)" >> "$LOG"
echo "[$TAGLOG] panel end $(date)" >> "$LOG"
