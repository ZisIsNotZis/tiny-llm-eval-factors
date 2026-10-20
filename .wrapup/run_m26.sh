#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# 2C — break the total/active collinearity with ONE GPU panel.
#
# Comparison: dense Qwen3.8-27B (27B total = 27B active) vs sparse
# gemma-4-26B-A4B (26B total, 4B active, 128 experts / top-8).  Matched TOTAL
# (~26-27B), 7x different ACTIVE.
#
# Why a new protocol for BOTH sides:
#   * The existing gemma-4-26B-A4B rows are `mpl-raw-greedy-768` and score at the
#     harness floor (0.02-0.06).  That is a verified harness failure: gemma-4's
#     template primes a reasoning channel, and under raw completion the model
#     emits 2-5x longer markdown *prose* instead of code (t4_gemma_repair.log:
#     every raw probe variant scored 0/40; only a chat turn with
#     enable_thinking=false produced compilable code).
#   * SSOT §3.2 forbids mixing protocols in one comparison, so the dense twin
#     Qwen3.8-27B is re-run under the SAME repaired protocol.
#
# Must run under the GPU flock:  bash gpu_locked.sh bash run_m26.sh
# Writes .wrapup/m26_summary.jsonl in the MultiPL-E summary shape
#   {"model","lang","n","pass","score","protocol"}.
set -u
cd ${REPO_ROOT}/.wrapup
LOG=${REPO_ROOT}/.wrapup/m26.log
SUMMARY=${REPO_ROOT}/.wrapup/m26_summary.jsonl
MRES=${REPO_ROOT}/.wrapup/mres
PORT=${PORT:-8077}
BASE=http://127.0.0.1:$PORT
PROTO=mpl-chat-nothink-greedy-768
CTX=${CTX:-2048}
PY=python3
CHAT_KW='{"enable_thinking": false}'
PANELS="g26b-q2:gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf g26b-q3:gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf q38-27b-q2:Qwen3.8-27B-UD-Q2_K_XL.gguf q38-27b-q3:Qwen3.8-27B-UD-Q3_K_XL.gguf"

mkdir -p "$MRES"
TAG="M26"
echo "[$TAG] panel start $(date) proto=$PROTO ctx=$CTX panels=[$PANELS]" >> "$LOG"

# reap a stale server left on our port by a dead predecessor (we hold the lock)
pid=$(ss -ltnp 2>/dev/null | grep ":$PORT" | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$pid" ] && kill "$pid"; sleep 2

srv=""
cleanup() { [ -n "$srv" ] && kill "$srv" 2>/dev/null; }
trap cleanup EXIT

start_server() {   # $1 = model file -> sets $srv, returns 0 on healthy
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

# ---- smoke test: verify the tooling loads and answers BEFORE the long loop ----
smoke_file="${PANELS%% *}"; smoke_file="${smoke_file#*:}"
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

empty_count() {
  "$PY" - "$1" <<'PY'
import json, sys
try:
    rows = [json.loads(l) for l in open(sys.argv[1])]
except Exception:
    print(999); raise SystemExit
print(sum(1 for r in rows if not (r.get("completion") or "").strip()))
PY
}

run_cell() {   # $1 tag  $2 lang  -> 0 if a valid row was recorded
  local tag="$1" lang="$2" model="$3"
  local samples="$MRES/m26-${tag}-${lang}.jsonl"
  start_server "$model" || return 1
  echo "[$TAG] gen $tag $lang $(date +%H:%M:%S)" >> "$LOG"
  timeout 5400 "$PY" mpl_run.py gen --lang "$lang" --mode chat --greedy \
    --max_tokens 768 --strip-thought --chat-kwargs "$CHAT_KW" \
    --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  local empty; empty=$(empty_count "$samples")
  if [ "${empty:-999}" -gt 32 ]; then
    echo "[$TAG] CORRUPT $tag $lang empty=$empty (server died mid-gen?)" >> "$LOG"
    kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; return 1
  fi
  timeout 1800 "$PY" mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
  "$PY" - "$tag" "$lang" "${samples%.jsonl}_eval.json" "$SUMMARY" "$PROTO" <<'PY' >> "$LOG" 2>&1
import json, sys
tag, lang, ev, dest, proto = sys.argv[1:6]
d = json.load(open(ev))
row = {"model": tag, "lang": lang, "n": d["n"], "pass": d["pass"],
       "score": d["score"], "protocol": proto}
with open(dest, "a") as f:
    f.write(json.dumps(row) + "\n")
print("recorded", tag, lang, d["n"], round(d["score"], 4))
PY
  kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; sleep 3
  return 0
}

for spec in $PANELS; do
  tag="${spec%%:*}"; model="${spec#*:}"
  for lang in cpp py; do
    ok=0
    for attempt in 1 2; do
      if run_cell "$tag" "$lang" "$model"; then ok=1; break; fi
      echo "[$TAG] retry $tag $lang (attempt $attempt failed)" >> "$LOG"
      sleep 5
    done
    [ "$ok" = 1 ] || echo "[$TAG] GAVE UP $tag $lang" >> "$LOG"
  done
done

echo "[$TAG] panel end $(date)" >> "$LOG"
