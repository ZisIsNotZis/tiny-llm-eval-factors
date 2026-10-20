#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# Diagnostic: is llama-server's --top-k flag actually applied to /completion requests
# that do NOT carry a top_k field (the mpl_run.py raw protocol)?
# Runs two servers (top_k=1 and top_k=64) on the same prompts at temp 0.3 seed 1234
# and compares the outputs.
set -u
W=${REPO_ROOT}/.wrapup
M=Qwen3.5-2B-UD-Q2_K_XL.gguf
PY=python3
port_srv() {  # port topk
  local port="$1" tk="$2"
  llama-server -m "/home/z/hf/$M" --port "$port" --host 127.0.0.1 -ngl 99 -c 4096 \
    --cache-type-k q8_0 --cache-type-v q8_0 --top-p 0.95 --top-k "$tk" --min-p 0.05 \
    --seed 1234 >"$W/topk_probe_$tk.log" 2>&1 &
  echo $!
}
wait_ok() {
  for i in $(seq 1 60); do
    curl -s --max-time 3 "http://127.0.0.1:$1/health" 2>/dev/null | grep -q '"status":"ok"' && return 0
    sleep 1
  done
  return 1
}
query() {  # port temp -> completion text
  curl -s --max-time 120 "http://127.0.0.1:$1/completion" -H 'Content-Type: application/json' \
    -d "{\"prompt\":\"def fib(n):\\n    if n < 2:\\n        return n\\n    return\",\"n_predict\":64,\"temperature\":$2}"
}

for T in 0.3 1.0; do
  for tk in 1 64; do
    pid=$(port_srv $((8200 + tk)) "$tk")
    wait_ok $((8200 + tk)) || { echo "server $tk FAILED"; kill $pid; continue; }
    out=$(query $((8200 + tk)) "$T")
    echo "$out" > "$W/topk_probe_t${T}_k${tk}.json"
    kill $pid 2>/dev/null; wait $pid 2>/dev/null; sleep 1
  done
  echo "=== temp $T: top_k=1 vs top_k=64 ==="
  python3 - "$W/topk_probe_t${T}_k1.json" "$W/topk_probe_t${T}_k64.json" <<'PY'
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
ca, cb = a.get("content",""), b.get("content","")
print("k1 :", repr(ca[:120]))
print("k64:", repr(cb[:120]))
print("IDENTICAL" if ca == cb else "DIFFER")
PY
done
