#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M22 — does the ternary off-curve advantage hold across TASK TYPES?
#   (a) official BFCL multi-turn, native-FC Qwen handler
#   (b) our single-turn BFCL native-tools panel (same runner as m4b, for comparability)
set -u
cd ${REPO_ROOT}/.wrapup
LOG=${REPO_ROOT}/.wrapup/m22.log
SUM=${REPO_ROOT}/.wrapup/m22_summary.jsonl
M=/home/z/hf/Ternary-Bonsai-27B-Q2_g64.gguf
echo "=== M22 start $(date) ===" >> "$LOG"

bash gpu_locked.sh bash -c '
  cd ${REPO_ROOT}/.wrapup
  llama-server -m /home/z/hf/Ternary-Bonsai-27B-Q2_g64.gguf --port 8080 --host 127.0.0.1 -ngl 99 \
    -c 131072 -np 2 --jinja --cache-type-k q8_0 --cache-type-v q8_0 >> ${REPO_ROOT}/.wrapup/m22.log 2>&1 &
  srv=$!
  for i in $(seq 1 150); do curl -s --max-time 3 http://127.0.0.1:8080/health 2>/dev/null | grep -q "\"status\":\"ok\"" && break; sleep 2; done
  # (a) single-turn BFCL, native tools (our harness)
  python3 bfcl_run.py gen --categories simple_python,multiple,parallel,parallel_multiple,irrelevance \
      --samples ${REPO_ROOT}/.wrapup/mres/m22-bonsai.jsonl --mode tools --max_tokens 512 \
      --base_url http://127.0.0.1:8080 >> ${REPO_ROOT}/.wrapup/m22.log 2>&1
  python3 bfcl_run.py eval --samples ${REPO_ROOT}/.wrapup/mres/m22-bonsai.jsonl >> ${REPO_ROOT}/.wrapup/m22.log 2>&1
  python3 - <<PY >> ${REPO_ROOT}/.wrapup/m22_summary.jsonl
import json
d=json.load(open("${REPO_ROOT}/.wrapup/mres/m22-bonsai_eval.json"))
print(json.dumps({"model":"bonsai-q2g64","kind":"single-turn","n":d["n"],"score":d["score"],
                  "per_category":d["per_category"],"protocol":"bfcl-native-tools-nothink-greedy"}))
PY
  # (b) official multi-turn
  REMOTE_OPENAI_BASE_URL=http://127.0.0.1:8080/v1 REMOTE_OPENAI_TOKENIZER_PATH=/home/z/hf/qwen_tok \
    timeout 7200 ${REPO_ROOT}/.wrapup/bfclenv/bin/bfcl generate --model Qwen/Qwen3-1.7B-FC \
    --test-category multi_turn_base --skip-server-setup --temperature 0 >> ${REPO_ROOT}/.wrapup/m22.log 2>&1
  acc=$(REMOTE_OPENAI_BASE_URL=http://127.0.0.1:8080/v1 REMOTE_OPENAI_TOKENIZER_PATH=/home/z/hf/qwen_tok \
    timeout 3600 ${REPO_ROOT}/.wrapup/bfclenv/bin/bfcl evaluate --model Qwen/Qwen3-1.7B-FC \
    --test-category multi_turn_base 2>&1 | tee -a ${REPO_ROOT}/.wrapup/m22.log \
    | grep -oE "Accuracy: [0-9.]+%" | tail -1 | grep -oE "[0-9.]+")
  python3 -c "
import json
print(json.dumps({\"model\":\"bonsai-q2g64\",\"kind\":\"multi-turn\",\"category\":\"multi_turn_base\",
  \"accuracy\":(float(\"$acc\")/100 if \"$acc\" else None),\"protocol\":\"bfcl-official-multiturn-temp0\"}))" >> ${REPO_ROOT}/.wrapup/m22_summary.jsonl
  kill $srv 2>/dev/null
' >> "$LOG" 2>&1
echo "=== M22 end $(date) ===" >> "$LOG"
