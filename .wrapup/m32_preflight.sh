#!/bin/bash
# m32 preflight: prove Ternary-Bonsai-27B can emit a REAL tool call two ways,
# because the official BFCL qwen_fc handler drives the model through the manual
# <tool_call> format over /v1/completions (NOT the native tools= endpoint):
#   (a) native tools= via /v1/chat/completions  -> expect message.tool_calls
#   (b) the exact qwen_fc manual prompt over /v1/completions -> expect <tool_call>
#
# VRAM BUG THIS FIXES (2026-10-06): the first version started this server at
# `-c 262144 -np 2` (131072 tokens/slot), sized for the *long-context* category.
# On a 24 GB GPU shared with a foreign llama-server (helpagent :8834, ~3.9 GB)
# the 27B Q2 (7.58 GB) then cannot fit its compute buffers and dies with
# `cudaMalloc failed: out of memory` *before any tool call is sent* -> the panel
# aborted with a false "model cannot tool-call". A tool-call preflight needs no
# long context, so start light (CTX_LIST default 32768 -> 16384 -> 8192 at
# NP=1), step the ctx down on failure, and always print the llama-server log
# tail so an OOM is visible instead of being misread as model incapability.
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/m32_preflight.log
SLOG=$W/m32_preflight_server.log   # raw llama-server output, so the tail is clean
M=Ternary-Bonsai-27B-Q2_g64.gguf
PORT=${M32_PREFLIGHT_PORT:-8132}; BASE=http://127.0.0.1:$PORT
CTX_LIST=${CTX_LIST:-"32768 16384 8192"}
NP=${NP:-1}
: > "$LOG"
echo "=== m32 preflight $(date) ===" | tee -a "$LOG"

srv=""
cleanup() { if [ -n "$srv" ]; then kill "$srv" 2>/dev/null; srv=""; fi; }
trap cleanup EXIT

# 1) bring the server up, stepping the context down until one fits.
start_ok=0
for ctx in $CTX_LIST; do
  echo "[preflight] llama-server ctx=$ctx np=$NP port=$PORT" | tee -a "$LOG"
  : > "$SLOG"
  llama-server -m "/home/z/hf/$M" --port "$PORT" --host 127.0.0.1 -ngl 99 \
    -c "$ctx" -np "$NP" --jinja --cache-type-k q8_0 --cache-type-v q8_0 >> "$SLOG" 2>&1 &
  srv=$!
  for i in $(seq 1 150); do
    curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && break
    kill -0 "$srv" 2>/dev/null || break   # a dead server (CUDA OOM) never gets healthy
    sleep 2
  done
  if curl -s --max-time 5 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"'; then
    echo "[preflight] server healthy at ctx=$ctx" | tee -a "$LOG"
    start_ok=1; break
  fi
  echo "[preflight] server FAILED at ctx=$ctx; llama-server log tail:" | tee -a "$LOG"
  tailout=$(tail -n 15 "$SLOG")
  printf '%s\n' "$tailout" | sed 's/^/[preflight-tail] /' | tee -a "$LOG"
  kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; sleep 3
done
if [ "$start_ok" != 1 ]; then
  echo "SERVER FAIL (no ctx in '$CTX_LIST' could start)" | tee -a "$LOG"
  echo "=== preflight end $(date) ===" | tee -a "$LOG"
  exit 1
fi

echo "--- (a) native tools= (/v1/chat/completions) ---" | tee -a "$LOG"
python3 - "$BASE" <<'PY' | tee -a "$LOG"
import json, sys, urllib.request
base = sys.argv[1]
body = {
  "model": "x",
  "messages": [{"role": "user",
                "content": "What is the weather in Paris right now? Use the tool."}],
  "tools": [{"type": "function", "function": {
      "name": "get_weather",
      "description": "Get the current weather for a city",
      "parameters": {"type": "object",
                     "properties": {"city": {"type": "string", "description": "city name"}},
                     "required": ["city"]}}}],
  "temperature": 0,
  "max_tokens": 200,
}
req = urllib.request.Request(base + "/v1/chat/completions",
                             data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
r = json.loads(urllib.request.urlopen(req, timeout=300).read().decode())
msg = r["choices"][0]["message"]
tc = msg.get("tool_calls")
print("content:", repr((msg.get("content") or "")[:300]))
print("tool_calls:", json.dumps(tc))
print("NATIVE_TOOL_CALL_OK" if tc else "NATIVE_TOOL_CALL_MISSING")
PY

echo "--- (b) qwen_fc manual format (/v1/completions) ---" | tee -a "$LOG"
python3 - "$BASE" <<'PY' | tee -a "$LOG"
import json, sys, urllib.request
base = sys.argv[1]
# Reproduce the qwen_fc._format_prompt shape for one tool + one user turn.
prompt = (
 "<|im_start|>system\n"
 "You are a helpful assistant.\n\n# Tools\n\nYou may call one or more functions "
 "to assist with the user query.\n\nYou are provided with function signatures within "
 "<tools></tools> XML tags:\n<tools>\n"
 '{"name": "get_weather", "description": "Get the current weather for a city", '
 '"parameters": {"type": "object", "properties": {"city": {"type": "string"}}, '
 '"required": ["city"]}}\n'
 "</tools>\n\nFor each function call, return a json object with function name and "
 "arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n"
 '{"name": <function-name>, "arguments": <args-json-object>}\n</tool_call><|im_end|>\n'
 "<|im_start|>user\nWhat is the weather in Paris right now? Use the tool.<|im_end|>\n"
 "<|im_start|>assistant\n"
)
body = {"prompt": prompt, "temperature": 0, "n_predict": 200}
req = urllib.request.Request(base + "/completion", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
r = json.loads(urllib.request.urlopen(req, timeout=300).read().decode())
txt = r.get("content", "")
print("completion:", repr(txt[:400]))
ok = "<tool_call>" in txt and ("name" in txt) and ("arguments" in txt)
print("MANUAL_TOOL_CALL_OK" if ok else "MANUAL_TOOL_CALL_MISSING")
PY
echo "=== preflight end $(date) ===" | tee -a "$LOG"
