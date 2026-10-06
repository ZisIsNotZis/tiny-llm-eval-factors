#!/bin/bash
# m32 preflight: prove Ternary-Bonsai-27B can emit a REAL tool call two ways,
# because the official BFCL qwen_fc handler drives the model through the manual
# <tool_call> format over /v1/completions (NOT the native tools= endpoint):
#   (a) native tools= via /v1/chat/completions  -> expect message.tool_calls
#   (b) the exact qwen_fc manual prompt over /v1/completions -> expect <tool_call>
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/m32_preflight.log
M=Ternary-Bonsai-27B-Q2_g64.gguf
PORT=8132; BASE=http://127.0.0.1:$PORT
: > "$LOG"
echo "=== m32 preflight $(date) ===" | tee -a "$LOG"
llama-server -m "/home/z/hf/$M" --port "$PORT" --host 127.0.0.1 -ngl 99 -c 262144 -np 2 \
  --jinja --cache-type-k q8_0 --cache-type-v q8_0 >> "$LOG" 2>&1 &
srv=$!
trap 'kill $srv 2>/dev/null' EXIT
for i in $(seq 1 150); do
  curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && break
  sleep 2
done
curl -s --max-time 5 "$BASE/health" | grep -q ok || { echo "SERVER FAIL" | tee -a "$LOG"; exit 1; }

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
