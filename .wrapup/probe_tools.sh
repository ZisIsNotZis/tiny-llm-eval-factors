#!/bin/bash
# Probe native tool-call support for each model: /props template marker + real request.
cd /home/z/hf/research/.wrapup
OUT=/home/z/hf/research/.wrapup/tools_probe.jsonl
: > "$OUT"
for m in gemma-4-E2B-it-UD-Q3_K_XL gemma-4-E4B-it-UD-Q3_K_XL granite-4.1-3b-Q3_K_M Qwen3.5-2B-UD-Q3_K_XL; do
  pid=$(ss -ltnp 2>/dev/null | grep ':8080' | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$pid" ] && kill $pid; sleep 2
  (llama-server -m "/home/z/hf/$m.gguf" --port 8080 --host 127.0.0.1 -ngl 99 -c 8192 --jinja \
     --cache-type-k q8_0 --cache-type-v q8_0 > /tmp/probe_$m.log 2>&1 &)
  for i in $(seq 1 90); do curl -s --max-time 3 http://127.0.0.1:8080/health 2>/dev/null | grep -q ok && break; sleep 2; done
  HAS=$(curl -s --max-time 10 http://127.0.0.1:8080/props | python3 -c "import json,sys;d=json.load(sys.stdin);t=d.get('chat_template') or '';print('yes' if ('<tools>' in t or 'tool_call' in t) else 'no')" 2>/dev/null)
  RES=$(timeout 180 curl -s http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' -d '{
    "messages":[{"role":"user","content":"What is the current weather in Paris right now?"}],
    "temperature":0,"max_tokens":512,"chat_template_kwargs":{"enable_thinking":false},
    "tools":[{"type":"function","function":{"name":"get_current_weather","description":"Get current weather","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}]}' \
    | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin); m=d['choices'][0]['message']; tc=m.get('tool_calls')
    if tc: print('tool_call:'+tc[0]['function']['name']+' '+str(tc[0]['function']['arguments'])[:60])
    else: print('no_tool_call:content='+repr((m.get('content') or '')[:60]))
except Exception as e: print('error:'+str(e)[:60])" 2>/dev/null)
  printf '{"model":"%s","template_tools":"%s","result":"%s"}\n' "$m" "$HAS" "$RES" >> "$OUT"
  echo "$m template=$HAS $RES"
done
pid=$(ss -ltnp 2>/dev/null | grep ':8080' | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$pid" ] && kill $pid
echo "=== PROBE END ===" >> "$OUT"
