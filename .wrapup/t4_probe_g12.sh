#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# T4 probe: diagnose gemma-4-12B raw-mode thought-channel breakage.
# Holds the GPU lock for the duration. Kills its own server before releasing.
set -u
cd ${REPO_ROOT}/.wrapup
LOG=${REPO_ROOT}/.wrapup/t4_probe_g12.log
PORT=8080
BASE=http://127.0.0.1:$PORT
MODEL="${1:-gemma-4-12b-it-UD-Q3_K_XL.gguf}"

pid=$(ss -ltnp 2>/dev/null | grep ":$PORT" | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$pid" ] && kill $pid; sleep 2

echo "=== probe start $(date) model=$MODEL ===" >> "$LOG"
llama-server -m "/home/z/hf/$MODEL" --port $PORT --host 127.0.0.1 -ngl 99 -c 4096 \
  --cache-type-k q8_0 --cache-type-v q8_0 --jinja \
  --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
SRV=$!
ok=0
for i in $(seq 1 150); do
  if curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"'; then ok=1; break; fi
  sleep 2
done
if [ "$ok" != 1 ]; then echo "SERVER FAIL" >> "$LOG"; kill $SRV 2>/dev/null; exit 1; fi
echo "server ready" >> "$LOG"

python3 - >> "$LOG" 2>&1 <<'PY'
import json, urllib.request
BASE="http://127.0.0.1:8080"
def post(path, payload, timeout=300):
    req=urllib.request.Request(BASE+path, data=json.dumps(payload).encode(),
                               headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())
p=json.loads(open("/tmp/MultiPL-E/prompts/humaneval-py.jsonl").readline())
prompt=p["prompt"]; stops=p.get("stop_tokens") or []
print("### stop_tokens:", stops)

print("\n### A) raw /completion, dataset stops only")
r=post("/completion", {"prompt":prompt,"temperature":0.0,"n_predict":400,"stop":stops})
print(repr(r["content"][:500]))

print("\n### B) raw /completion, +channel stops")
r=post("/completion", {"prompt":prompt,"temperature":0.0,"n_predict":400,"stop":stops+["<|channel>","<channel|>"]})
print(repr(r["content"][:500]))

print("\n### C) raw /completion NO stops (see structure)")
r=post("/completion", {"prompt":prompt,"temperature":0.0,"n_predict":400})
print(repr(r["content"][:900]))

print("\n### D) chat /v1/chat/completions enable_thinking=false")
instr=("Complete the following Python function. Return only the code that should replace "
       "the marked region, without any explanation or markdown fences.\n\n"+prompt)
r=post("/v1/chat/completions", {"messages":[{"role":"user","content":instr}],
        "temperature":0.0,"max_tokens":400,
        "chat_template_kwargs":{"enable_thinking": False}})
print(repr((r["choices"][0]["message"].get("content") or "")[:500]))

print("\n### E) chat /v1/chat/completions default")
r=post("/v1/chat/completions", {"messages":[{"role":"user","content":instr}],
        "temperature":0.0,"max_tokens":400})
print(repr((r["choices"][0]["message"].get("content") or "")[:900]))

print("\n### F) raw /completion + empty thinking-channel prime (<|channel>thought\\n<channel|>)")
r=post("/completion", {"prompt":prompt+"<|channel>thought\n<channel|>",
        "temperature":0.0,"n_predict":400,"stop":stops})
print(repr(r["content"][:500]))

print("\n### G) raw /completion + full turn prime (<|turn>model\\n<|channel>thought\\n<channel|>)")
r=post("/completion", {"prompt":prompt+"<|turn>model\n<|channel>thought\n<channel|>",
        "temperature":0.0,"n_predict":400,"stop":stops})
print(repr(r["content"][:500]))

print("\n### H) chat enable_thinking=false, raw MultiPL-E prompt as user content")
r=post("/v1/chat/completions", {"messages":[{"role":"user","content":prompt}],
        "temperature":0.0,"max_tokens":400,
        "chat_template_kwargs":{"enable_thinking": False}})
print(repr((r["choices"][0]["message"].get("content") or "")[:500]))
PY

kill $SRV 2>/dev/null; sleep 3
echo "=== probe end $(date) ===" >> "$LOG"
wait $SRV 2>/dev/null
