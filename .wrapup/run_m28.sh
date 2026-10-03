#!/bin/bash
# M28 (BRAINSTORM 4B) — MTP draft length x SPEED on Qwen3.5-2B-UD-Q4_K_XL (MTP GGUF).
#
# Sweeps --spec-draft-n-max n in {0,1,2,3,4} (0 = spec off baseline) and measures
# generation tok/s + draft acceptance on three prompt classes: code / prose / long-context.
# Speed fit only — no benchmark scoring. Each (mode,n) row is appended as it is measured.
set -u
cd /home/z/hf/research/.wrapup
LOG=/home/z/hf/research/.wrapup/m28.log
OUT=/home/z/hf/research/.wrapup/m28_speed.jsonl
M=/home/z/hf/models--unsloth--Qwen3.5-2B-MTP-GGUF/snapshots/e05864f8066d874d5f85aaff007ae57a2a7d1efe/Qwen3.5-2B-UD-Q4_K_XL.gguf
TAG=qwen3.5-2b-q4
PORT=8125
BASE=http://127.0.0.1:$PORT

echo "=== M28 start $(date) model=$M ===" >> "$LOG"

for n in 0 1 2 3 4; do
  SPEC="--spec-type none"
  [ "$n" -gt 0 ] && SPEC="--spec-type draft-mtp --spec-draft-n-max $n"
  echo "[$(date +%H:%M:%S)] server draft_n=$n" >> "$LOG"
  llama-server -m "$M" --port $PORT --host 127.0.0.1 -ngl 99 -c 16384 \
    --cache-type-k q8_0 --cache-type-v q8_0 --seed 1234 $SPEC >> "$LOG" 2>&1 &
  SRV=$!
  ready=0
  for i in $(seq 1 120); do
    if curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"'; then ready=1; break; fi
    sleep 1
  done
  if [ "$ready" != 1 ]; then echo "SERVER FAIL draft_n=$n" >> "$LOG"; kill $SRV 2>/dev/null; continue; fi
  python3 m28_speed.py --base_url "$BASE" --draft_n "$n" --model "$TAG" --out "$OUT" \
    --reps 3 >> "$LOG" 2>&1
  kill $SRV 2>/dev/null; wait $SRV 2>/dev/null
  sleep 2
done

echo "=== M28 end $(date) ===" >> "$LOG"
