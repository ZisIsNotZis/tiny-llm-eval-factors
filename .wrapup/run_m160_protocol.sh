#!/bin/bash
# m160 — MultiPL-E protocol-controlled panel (raw vs chat), cpp+py.
#
# WHY: the standard MultiPL-E column mixed protocols and language sets across
# models.  gemma-4-26B-A4B scored 0.03-0.06 under `mpl-raw-greedy` (raw
# completion) but 0.83/0.65 under `mpl-chat-nothink` (m26 log: raw completion
# makes gemma-4 emit markdown prose, a verified harness failure).  Before the
# report can decide which MultiPL-E cells are trustworthy, one panel must run
# BOTH protocols on the SAME files, same languages, same ctx.
#
# Design (controlled: only `mode` changes):
#   held  = model file, language, ctx=2048, greedy, max_tokens=768
#   varied = mode in {raw, chat}; the raw floor can only hurt an instruct model
#            whose template needs a chat turn.
#   models = gemma-4-12b Q2/Q3 (a "12B crash" suspect with no cpp+py at all),
#            gemma-4-26B-A4B Q3 (has raw), Qwen3.8-27B Q3 (chat control, has raw).
#   langs  = cpp, py  (the canonical set used by the report's standard column)
#
# Run under the GPU flock:
#   bash gpu_locked.sh bash run_m160_protocol.sh
# Subset (cells are `<tag>:<lang>:<mode>`, space separated):
#   ONLY="q38-27b-q3:cpp:chat" bash run_m160_protocol.sh
# Writes .wrapup/m160_summary.jsonl in the MultiPL-E summary shape.
#
# Prompt set: .wrapup/prompts/humaneval-<lang>.jsonl, tracked and hashed in
# .wrapup/prompts/SHA256SUMS.  The first m160 attempt (20:46) lost all 16 cells
# to /tmp/MultiPL-E/prompts being cleaned; the preflight below turns that into
# one explicit ABORT instead of sixteen silent "CORRUPT" cells.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(dirname "$HERE")
cd "$HERE" || exit 1
LOG=$HERE/m160.log
SUMMARY=$HERE/m160_summary.jsonl
MRES=$HERE/mres
PROMPTS=${MULTIPLE_PROMPTS:-$HERE/prompts}
PORT=${PORT:-8086}
BASE=http://127.0.0.1:$PORT
CTX=${CTX:-2048}
PY=python3
CHAT_KW='{"enable_thinking": false}'
MODELS="g12b-q2:gemma-4-12b-it-UD-Q2_K_XL.gguf g12b-q3:gemma-4-12b-it-UD-Q3_K_XL.gguf g26b-q3:gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf q38-27b-q3:Qwen3.8-27B-UD-Q3_K_XL.gguf"
MODES="raw chat"
ONLY=${ONLY:-}

mkdir -p "$MRES"
TAG="M160"
echo "[$TAG] panel start $(date) models=[$MODELS] modes=[$MODES] only=[$ONLY]" >> "$LOG"

# --- preflight: the prompt set is the experiment's input, so it is checked and
# --- its hash bound into the log before any GPU time is spent.
preflight() {
  local lang f h
  for lang in cpp py; do
    f="$PROMPTS/humaneval-$lang.jsonl"
    if [ ! -s "$f" ]; then
      echo "[$TAG] ABORT: prompt set missing $f (git checkout -- .wrapup/prompts/)" >> "$LOG"
      return 1
    fi
    h=$(sha256sum "$f" | cut -d' ' -f1)
    echo "[$TAG] prompts $lang sha256=$h" >> "$LOG"
  done
  ( cd "$PROMPTS" && sha256sum -c SHA256SUMS --quiet ) >/dev/null 2>&1 || {
    echo "[$TAG] ABORT: prompt set does not match SHA256SUMS in $PROMPTS (content changed; a panel run against an unpinned prompt set is not comparable)" >> "$LOG"
    return 1
  }
  echo "[$TAG] preflight ok: prompt set matches SHA256SUMS" >> "$LOG"
}
preflight || exit 2

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
    kill -0 "$srv" 2>/dev/null || { echo "[$TAG] server DIED $1" >> "$LOG"; return 1; }
    curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && return 0
    sleep 2
  done
  echo "[$TAG] server TIMEOUT $1" >> "$LOG"; kill "$srv" 2>/dev/null; return 1
}

# Reports the number of empty completions, or UNREADABLE when the samples file
# is missing/unparseable.  The old version answered 999 for both, which is how
# 16 cells burned GPU time against a missing prompt set and were recorded as if
# the model had produced nothing.
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

cell_wanted() {
  [ -z "$ONLY" ] && return 0
  local c
  for c in $ONLY; do [ "$c" = "$1" ] && return 0; done
  return 1
}

run_cell() {   # $1 tag  $2 lang  $3 model  $4 mode
  local tag="$1" lang="$2" model="$3" mode="$4"
  local samples="$MRES/m160-${tag}-${lang}-${mode}.jsonl"
  cell_wanted "$tag:$lang:$mode" || return 0
  start_server "$model" || return 1
  echo "[$TAG] gen $tag $lang mode=$mode $(date +%H:%M:%S)" >> "$LOG"
  if [ "$mode" = chat ]; then
    timeout 5400 "$PY" mpl_run.py gen --lang "$lang" --mode chat --greedy \
      --max_tokens 768 --strip-thought --chat-kwargs "$CHAT_KW" \
      --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  else
    timeout 5400 "$PY" mpl_run.py gen --lang "$lang" --mode raw --greedy \
      --max_tokens 768 \
      --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  fi
  local state; state=$(samples_state "$samples")
  case "$state" in
    UNREADABLE:*)
      echo "[$TAG] GEN-FAILED $tag $lang mode=$mode $state" >> "$LOG"
      kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; return 1 ;;
  esac
  local empty=${state%%/*}
  if [ "$empty" -gt 32 ]; then
    echo "[$TAG] CORRUPT $tag $lang mode=$mode empty=${state}" >> "$LOG"
    kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; return 1
  fi
  timeout 2400 "$PY" mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
  "$PY" - "$tag" "$lang" "${samples%.jsonl}_eval.json" "$SUMMARY" "$mode" <<'PY' >> "$LOG" 2>&1
import json, sys, collections
tag, lang, ev, dest, mode = sys.argv[1:6]
d = json.load(open(ev))
st = collections.Counter(x.get("status") for x in d.get("details", []))
n = d["n"]
# all-Exception == infrastructure failure, not a measured 0 -> record as null
score = None if (n and st.get("Exception", 0) == n) else d["score"]
proto = "mpl-%s-greedy-768" % ("chat-nothink" if mode == "chat" else "raw")
row = {"model": tag, "lang": lang, "n": n, "pass": d["pass"],
       "score": score, "protocol": proto, "statuses": dict(st)}
with open(dest, "a") as f:
    f.write(json.dumps(row) + "\n")
print("recorded", tag, lang, mode, n, score, dict(st))
PY
  kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; sleep 3
  return 0
}

# smoke test before the long loop
smoke_file="${MODELS%% *}"; smoke_file="${smoke_file#*:}"
echo "[$TAG] smoke: loading $smoke_file" >> "$LOG"
if start_server "$smoke_file"; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 180 -X POST "$BASE/completion" \
     -H 'Content-Type: application/json' \
     -d '{"prompt":"def f():\n    return 1","n_predict":8,"temperature":0}')
  echo "[$TAG] smoke: health=ok completion_http=$code" >> "$LOG"
  kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""
  [ "$code" = "200" ] || { echo "[$TAG] ABORT: smoke completion != 200" >> "$LOG"; exit 1; }
else
  echo "[$TAG] ABORT: smoke load failed" >> "$LOG"; exit 1
fi

for spec in $MODELS; do
  tag="${spec%%:*}"; model="${spec#*:}"
  for mode in $MODES; do
    for lang in cpp py; do
      ok=0
      for attempt in 1 2; do
        if run_cell "$tag" "$lang" "$model" "$mode"; then ok=1; break; fi
        echo "[$TAG] retry $tag $lang $mode (attempt $attempt)" >> "$LOG"
        sleep 5
      done
      cell_wanted "$tag:$lang:$mode" || ok=1
      [ "$ok" = 1 ] || echo "[$TAG] GAVE UP $tag $lang $mode" >> "$LOG"
    done
  done
done

echo "[$TAG] panel end $(date)" >> "$LOG"
