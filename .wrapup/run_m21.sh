#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M21 — B1 Bonsai ternary off-curve probe.
#
# Model: Ternary-Bonsai-27B-Q2_g64.gguf — the group-64 pack that the README says
# "matches the 64-value-group Q2_0 packing in llama.cpp", i.e. the variant an
# UPSTREAM llama.cpp build can load (the g128 Q2_0 and PQ2_0 packs need the
# PrismML fork's custom kernels). Verified: this file loads under build 4399.
#
# Protocol identical to m3/m5/m6 so the point drops onto the same bits->score
# curve: ctx 4096, KV q8_0/q8_0, top_p .95 / top_k 40 / min_p .05, raw
# completion (MultiPL-E native), greedy, 768 max tokens.
set -u
cd ${REPO_ROOT}/.wrapup
LOG=${REPO_ROOT}/.wrapup/m21.log
SUMMARY=${REPO_ROOT}/.wrapup/m21_summary.jsonl
MRES=${REPO_ROOT}/.wrapup/mres
PORT=8080
BASE=http://127.0.0.1:$PORT
LANGS="${LANGS:-cpp py}"
PY=python3
PANELS="${PANELS:-bonsai-q2g64:Ternary-Bonsai-27B-Q2_g64.gguf}"

mkdir -p "$MRES"
pid=$(ss -ltnp 2>/dev/null | grep ':8080' | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$pid" ] && kill $pid; sleep 2

echo "=== M21 start $(date) langs=[$LANGS] panels=[$PANELS] ===" >> "$LOG"

start_server() {
  llama-server -m "/home/z/hf/$1" --port $PORT --host 127.0.0.1 -ngl 99 -c 4096 \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  SRV=$!
  for i in $(seq 1 150); do
    if curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"'; then
      echo "server ready: $1" >> "$LOG"; return 0
    fi
    sleep 2
  done
  echo "SERVER FAIL $1" >> "$LOG"; return 1
}

for spec in $PANELS; do
  tag="${spec%%:*}"; model="${spec#*:}"
  start_server "$model" || continue
  for lang in $LANGS; do
    samples="$MRES/m21-${tag}-${lang}.jsonl"
    echo "[$(date +%H:%M:%S)] gen $tag $lang" >> "$LOG"
    timeout 14400 $PY mpl_run.py gen --lang "$lang" --mode raw --greedy \
      --max_tokens 768 --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
    $PY mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
    $PY - "$tag" "$lang" "${samples%.jsonl}_eval.json" "$SUMMARY" <<'PY' >> "$LOG" 2>&1
import json,sys
tag,lang,ev,dest=sys.argv[1:5]
d=json.load(open(ev))
with open(dest,"a") as f:
    f.write(json.dumps({"model":tag,"lang":lang,"n":d["n"],"pass":d["pass"],
                        "score":d["score"],"protocol":"mpl-raw-greedy-768"})+"\n")
print("recorded",tag,lang,d["n"],round(d["score"],4))
PY
    echo "[$(date +%H:%M:%S)] DONE $tag $lang" >> "$LOG"
  done
  kill $SRV 2>/dev/null; sleep 3
done

echo "=== M21 end $(date) ===" >> "$LOG"
