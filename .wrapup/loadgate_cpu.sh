#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# loadgate_cpu.sh <gguf-basename> [tag]
#
# CPU-only load gate (NO GPU, NO /tmp/llama_gpu.lock): start llama-server with
# -ngl 0 and issue ONE real completion. Records the result in
# .wrapup/loadgate.jsonl so a runner can refuse to arm an unverified GGUF.
# This exists because three queue entries (m34/m40/m53) each burned a GPU slot on
# a GGUF whose ggml type the build cannot parse; a CPU parse catches that class of
# failure without touching the GPU lock, so it can run in parallel with the queue.
set -u
W=${REPO_ROOT}/.wrapup
F="$1"; TAG="${2:-$1}"
LG=$W/loadgate.jsonl
LOG=$W/loadgate.log
PORT=8188
if [ ! -e "/home/z/hf/$F" ]; then
  echo "[loadgate] $(date +%H:%M:%S) MISSING $TAG $F" >> "$LOG"; exit 3
fi
if curl -s --max-time 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  pkill -f "llama-server .*--port $PORT" 2>/dev/null; sleep 2
fi
llama-server -m "/home/z/hf/$F" --port $PORT --host 127.0.0.1 -ngl 0 -c 2048 -t 8 \
  >> "$LOG" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT INT TERM
ok=0
for i in $(seq 1 450); do
  if curl -s --max-time 3 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"status":"ok"'; then ok=1; break; fi
  kill -0 $SRV 2>/dev/null || break
  sleep 2
done
res=FAIL
if [ $ok -eq 1 ]; then
  SM=$(curl -s --max-time 300 "http://127.0.0.1:$PORT/completion" -H 'Content-Type: application/json' \
       -d '{"prompt":"def add(a, b):\n    return a","n_predict":8,"temperature":0}')
  echo "$SM" | grep -q '"content"' && res=PASS
fi
kill $SRV 2>/dev/null; wait $SRV 2>/dev/null
trap - EXIT INT TERM
echo "[loadgate] $(date +%H:%M:%S) $TAG $F -> $res" >> "$LOG"
python3 - "$TAG" "$F" "$res" "$LG" <<'PY'
import json, sys
tag, f, res, dest = sys.argv[1:5]
with open(dest, "a") as fh:
    fh.write(json.dumps({"tag": tag, "file": f, "load": res}) + "\n")
PY
[ "$res" = PASS ] || exit 1
