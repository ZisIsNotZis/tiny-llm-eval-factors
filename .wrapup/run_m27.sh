#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M27 (BRAINSTORM 4A) — does the best SAMPLING setting shift with quant?
#
# Qwen3.5-2B (Unsloth UD K_XL) at Q2/Q3/Q4 x temperature {0.0,0.3,0.6} on
# MultiPL-E cpp+py. Sampling is the variable, so temperature is passed per
# request by mpl_run.py and top_k=40/top_p=0.95/min_p=0.05 stay server-side
# (the frozen protocol). --seed 1234 makes every temp>0 cell reproducible.
#
# temp 0.0 for q2 is the harness anchor against m3 (mpl-raw-greedy-768).
# Rows are appended per cell, shape: {"model","lang","n","pass","score","temp","protocol"}.
set -u
cd ${REPO_ROOT}/.wrapup
LOG=${REPO_ROOT}/.wrapup/m27.log
SUM=${REPO_ROOT}/.wrapup/m27_summary.jsonl
MRES=${REPO_ROOT}/.wrapup/mres
PORT=8126
BASE=http://127.0.0.1:$PORT
mkdir -p "$MRES"

# tag : gguf : temps
PANELS=(
  "q2:Qwen3.5-2B-UD-Q2_K_XL.gguf:0.0 0.3 0.6"
  "q3:Qwen3.5-2B-UD-Q3_K_XL.gguf:0.3 0.6"
  "q4:Qwen3.5-2B-UD-Q4_K_XL.gguf:0.3 0.6"
)
LANGS="cpp py"

echo "=== M27 start $(date) ===" >> "$LOG"

for spec in "${PANELS[@]}"; do
  tag="${spec%%:*}"; rest="${spec#*:}"; model="${rest%%:*}"; temps="${rest#*:}"
  echo "[$(date +%H:%M:%S)] server $tag $model temps=[$temps]" >> "$LOG"
  llama-server -m "/home/z/hf/$model" --port $PORT --host 127.0.0.1 -ngl 99 -c 4096 \
    --cache-type-k q8_0 --cache-type-v q8_0 --top-p 0.95 --top-k 40 --min-p 0.05 --seed 1234 \
    >> "$LOG" 2>&1 &
  SRV=$!
  ready=0
  for i in $(seq 1 150); do
    if curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"'; then ready=1; break; fi
    sleep 2
  done
  if [ "$ready" != 1 ]; then echo "SERVER FAIL $tag" >> "$LOG"; kill $SRV 2>/dev/null; continue; fi

  for T in $temps; do
    for lang in $LANGS; do
      samples="$MRES/m27-${tag}-t${T}-${lang}.jsonl"
      echo "[$(date +%H:%M:%S)] gen $tag t=$T $lang" >> "$LOG"
      if [ "$T" = "0.0" ]; then
        timeout 3600 python3 mpl_run.py gen --lang "$lang" --mode raw --greedy \
          --temperature "$T" --max_tokens 768 --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
        proto="mpl-raw-greedy-768"
      else
        timeout 3600 python3 mpl_run.py gen --lang "$lang" --mode raw \
          --temperature "$T" --max_tokens 768 --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
        proto="mpl-raw-t${T}-768"
      fi
      python3 mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
      python3 - "$tag" "$lang" "$T" "${samples%.jsonl}_eval.json" "$SUM" "$proto" <<'PY' >> "$LOG" 2>&1
import json, sys
tag, lang, temp, ev, dest, proto = sys.argv[1:7]
d = json.load(open(ev))
row = {"model": tag, "lang": lang, "n": d["n"], "pass": d["pass"],
       "score": d["score"], "temp": float(temp), "protocol": proto}
with open(dest, "a") as f:
    f.write(json.dumps(row) + "\n")
print("recorded", json.dumps(row))
PY
      echo "[$(date +%H:%M:%S)] DONE $tag t=$T $lang" >> "$LOG"
    done
  done
  kill $SRV 2>/dev/null; wait $SRV 2>/dev/null
  sleep 2
done

echo "=== M27 end $(date) ===" >> "$LOG"
