#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M6c — full weight-quant ladder on a small (fast) model, across languages.
#
# Answers: where does the quant-response curve saturate, and does the Q2->Q3
# step replicate *below* it (IQ2) and *above* it (Q4/Q5)?
#
# Frozen protocol: ctx 4096, KV q8_0/q8_0, top_p .95 / top_k 40 / min_p .05,
# raw completion (MultiPL-E native), greedy, 768 max tokens.
set -u
cd ${REPO_ROOT}/.wrapup
LOG=${REPO_ROOT}/.wrapup/m6c.log
SUMMARY=${REPO_ROOT}/.wrapup/m6c_summary.jsonl
MRES=${REPO_ROOT}/.wrapup/mres
PORT=8080
BASE=http://127.0.0.1:$PORT
LANGS="${LANGS:-cpp py}"
PY=python3
# tag:model
PANELS="${PANELS:-q36-35b-q2:Qwen3.6-35B-A3B-UD-Q2_K_XL.gguf q36-35b-q3:Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf}"

mkdir -p "$MRES"
# stale-server cleanup
pid=$(ss -ltnp 2>/dev/null | grep ':8080' | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$pid" ] && kill $pid; sleep 2

echo "=== M6c start $(date) langs=[$LANGS] panels=[$PANELS] ===" >> "$LOG"

start_server() {
  llama-server -m "/home/z/hf/$1" --port $PORT --host 127.0.0.1 -ngl 99 -c 2048 \
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
    samples="$MRES/m3-${tag}-${lang}.jsonl"
    echo "[$(date +%H:%M:%S)] gen $tag $lang" >> "$LOG"
    timeout 7200 $PY mpl_run.py gen --lang "$lang" --mode raw --greedy \
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

echo "=== M6c end $(date) ===" >> "$LOG"
