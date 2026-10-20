#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# T4 generic runner. Must be invoked under the GPU lock:
#   bash gpu_locked.sh bash t4_run.sh
#
# Env knobs (all optional):
#   PANELS  "tag:model.gguf ..."   (required)
#   LANGS   "cpp py"               (default "cpp py")
#   MODE    raw|chat               (default raw)
#   PROTO   protocol string recorded in the summary (required, no spaces)
#   SUMMARY destination jsonl      (default m10_summary.jsonl)
#   CTX     server ctx             (default 4096)
#   EXTRA_STOP  comma-separated extra stop strings
#   CHAT_KWARGS JSON for chat_template_kwargs (chat mode)
#   STRIP_THOUGHT  1 to strip a leading thought channel
#   PROMPT_SUFFIX  literal string appended to the raw prompt
#   SRV_EXTRA  extra llama-server flags (e.g. "--jinja")
#   LOG     run log
#   META    optional companion jsonl recording ctx/KV/sampling per row
#   PREFIX  filename prefix for samples (default m10)
set -u
cd ${REPO_ROOT}/.wrapup
LOG=${LOG:-${REPO_ROOT}/.wrapup/t4_run.log}
SUMMARY=${SUMMARY:-${REPO_ROOT}/.wrapup/m10_summary.jsonl}
MRES=${MRES:-${REPO_ROOT}/.wrapup/mres}
PORT=${PORT:-8080}
BASE=http://127.0.0.1:$PORT
LANGS="${LANGS:-cpp py}"
PANELS="${PANELS:?set PANELS}"
PROTO="${PROTO:?set PROTO}"
MODE=${MODE:-raw}
CTX=${CTX:-4096}
STRIP_THOUGHT=${STRIP_THOUGHT:-0}
PREFIX=${PREFIX:-m10}
PY=python3

mkdir -p "$MRES"
# stale-server cleanup (we hold the lock, so any :8080 server is ours to reap)
pid=$(ss -ltnp 2>/dev/null | grep ":$PORT" | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$pid" ] && kill "$pid"; sleep 2

GEN_ARGS=(--mode "$MODE" --greedy --max_tokens 768)
[ "$STRIP_THOUGHT" = 1 ] && GEN_ARGS+=(--strip-thought)
[ -n "${EXTRA_STOP:-}" ] && GEN_ARGS+=(--extra-stop "$EXTRA_STOP")
[ -n "${CHAT_KWARGS:-}" ] && GEN_ARGS+=(--chat-kwargs "$CHAT_KWARGS")
[ -n "${PROMPT_SUFFIX:-}" ] && GEN_ARGS+=(--prompt-suffix "$PROMPT_SUFFIX")

echo "=== T4 run start $(date) proto=$PROTO mode=$MODE langs=[$LANGS] panels=[$PANELS] ===" >> "$LOG"

start_server() {
  # shellcheck disable=SC2086
  llama-server -m "/home/z/hf/$1" --port $PORT --host 127.0.0.1 -ngl 99 -c "$CTX" \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --top-p 0.95 --top-k 40 --min-p 0.05 ${SRV_EXTRA:-} >> "$LOG" 2>&1 &
  SRV=$!
  for i in $(seq 1 150); do
    if ! kill -0 $SRV 2>/dev/null; then echo "SERVER DIED $1" >> "$LOG"; return 1; fi
    if curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"'; then
      echo "server ready: $1" >> "$LOG"; return 0
    fi
    sleep 2
  done
  echo "SERVER TIMEOUT $1" >> "$LOG"; kill $SRV 2>/dev/null; return 1
}

for spec in $PANELS; do
  tag="${spec%%:*}"; model="${spec#*:}"
  if ! start_server "$model"; then
    echo "[$(date +%H:%M:%S)] SKIP $tag (server failed)" >> "$LOG"
    continue
  fi
  for lang in $LANGS; do
    samples="$MRES/${PREFIX}-${tag}-${lang}.jsonl"
    echo "[$(date +%H:%M:%S)] gen $tag $lang" >> "$LOG"
    timeout 7200 $PY mpl_run.py gen --lang "$lang" "${GEN_ARGS[@]}" \
      --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
    $PY mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
    $PY - "$tag" "$lang" "${samples%.jsonl}_eval.json" "$SUMMARY" "$PROTO" "${META:-}" "$CTX" <<'PY' >> "$LOG" 2>&1
import json,sys
args=sys.argv[1:8]
tag,lang,ev,dest,proto=args[:5]
meta=args[5] if len(args)>5 else ""
ctx=args[6] if len(args)>6 else ""
try:
    d=json.load(open(ev))
except Exception as e:
    print("no eval",tag,lang,e); sys.exit(0)
row={"model":tag,"lang":lang,"n":d["n"],"pass":d["pass"],
     "score":d["score"],"protocol":proto}
with open(dest,"a") as f:
    f.write(json.dumps(row)+"\n")
if meta:
    with open(meta,"a") as f:
        f.write(json.dumps({"model":tag,"lang":lang,"ctx":int(ctx) if ctx else None,
            "kv":"q8_0/q8_0","sampling":"greedy-t0-p0.95-k40-minp0.05",
            "protocol":proto,"dataset":"multipl-e-humaneval"})+"\n")
print("recorded",tag,lang,d["n"],round(d["score"],4))
PY
    echo "[$(date +%H:%M:%S)] DONE $tag $lang" >> "$LOG"
  done
  kill $SRV 2>/dev/null; sleep 3
done

echo "=== T4 run end $(date) proto=$PROTO ===" >> "$LOG"
