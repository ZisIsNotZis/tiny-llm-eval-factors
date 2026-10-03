#!/bin/bash
# M31 (QUEUE #5) — sampling top_k x weight quant.
#
# m27 held top_k=40 and found temperature ~null on MultiPL-E (2B Q2/Q3/Q4 x
# {0.0,0.3,0.6}). The legacy pooled fit instead gives top_k a real coefficient
# (btopk=+0.187) and the legacy panel's dominant decoding knob was top_k, so the
# live question is whether top_k, not temp, moves scores and whether its optimum
# shifts with quant.
#
# Design: 2B Q2/Q3/Q4 x top_k {20,40,64} at temp 0.3, MultiPL-E cpp+py
# (161 items each) = 18 cells. top_k is a llama-server launch flag (server-side
# default), so mpl_run.py and the frozen raw-completion protocol are untouched;
# top_p .95 / min_p .05 stay fixed and --seed 1234 keeps every temp>0 cell
# reproducible. The top_k=40 column is the anchor: same seed/config as m27's
# temp 0.3 cells, so it must reproduce them (else the harness drifted).
#
# Rows: {"model","lang","n","pass","score","temp","top_k","protocol"}.
#
# Must run under the GPU flock (the chain does this):
#   bash gpu_locked.sh bash run_m31.sh
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m30_32.log
SUM=$W/m31_summary.jsonl
MRES=$W/mres
PORT=8131; BASE=http://127.0.0.1:$PORT; PY=python3
PANELS=(
  "q2:Qwen3.5-2B-UD-Q2_K_XL.gguf"
  "q3:Qwen3.5-2B-UD-Q3_K_XL.gguf"
  "q4:Qwen3.5-2B-UD-Q4_K_XL.gguf"
)
TOPK_S="20 40 64"
SRV=""
mkdir -p "$MRES"
echo "=== M31 start $(date) ===" >> "$LOG"

cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; return 0; }
trap cleanup EXIT INT TERM

clear_port() {
  curl -s --max-time 3 "$BASE/health" >/dev/null 2>&1 || return 0
  if pgrep -f "llama-server .*-m /home/z/hf/" >/dev/null 2>&1; then
    pkill -f "llama-server .*-m /home/z/hf/"; sleep 3
  else
    echo "[$(date +%H:%M:%S)] M31 ABORT: port $PORT held by a foreign server" >> "$LOG"
    exit 2
  fi
}

for spec in "${PANELS[@]}"; do
  tag="${spec%%:*}"; model="${spec#*:}"
  for TK in $TOPK_S; do
    clear_port
    echo "[$(date +%H:%M:%S)] M31 server $tag top_k=$TK" >> "$LOG"
    llama-server -m "/home/z/hf/$model" --port "$PORT" --host 127.0.0.1 -ngl 99 -c 4096 \
      --cache-type-k q8_0 --cache-type-v q8_0 \
      --top-p 0.95 --top-k "$TK" --min-p 0.05 --seed 1234 >> "$LOG" 2>&1 &
    SRV=$!
    ok=0
    for i in $(seq 1 150); do
      curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && { ok=1; break; }
      sleep 2
    done
    if [ $ok -ne 1 ]; then
      echo "[$(date +%H:%M:%S)] M31 SERVER FAIL $tag top_k=$TK" >> "$LOG"
      kill "$SRV" 2>/dev/null; SRV=""; continue
    fi
    SM=$(curl -s --max-time 180 "$BASE/completion" -H 'Content-Type: application/json' \
      -d '{"prompt":"def add(a, b):\n    return a","n_predict":8,"temperature":0,"top_p":0.95,"top_k":40,"min_p":0.05}')
    if ! echo "$SM" | grep -q '"content"'; then
      echo "[$(date +%H:%M:%S)] M31 SMOKE FAIL $tag top_k=$TK" >> "$LOG"
      kill "$SRV" 2>/dev/null; SRV=""; continue
    fi

    for lang in cpp py; do
      samples="$MRES/m31-${tag}-tk${TK}-${lang}.jsonl"
      echo "[$(date +%H:%M:%S)] M31 gen $tag top_k=$TK $lang" >> "$LOG"
      timeout 3600 $PY mpl_run.py gen --lang "$lang" --mode raw --temperature 0.3 \
        --max_tokens 768 --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
      $PY mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
      $PY - "$tag" "$lang" "$TK" "${samples%.jsonl}_eval.json" "$SUM" <<'PY' >> "$LOG" 2>&1
import json, sys
tag, lang, tk, ev, dest = sys.argv[1:6]
d = json.load(open(ev))
rec = {"model": tag, "lang": lang, "n": d["n"], "pass": d["pass"],
       "score": d["score"], "temp": 0.3, "top_k": int(tk),
       "protocol": "mpl-raw-t0.3-768"}
with open(dest, "a") as f:
    f.write(json.dumps(rec) + "\n")
print("recorded", tag, lang, "top_k", tk, d["n"], round(d["score"], 4))
PY
      echo "[$(date +%H:%M:%S)] M31 DONE $tag top_k=$TK $lang" >> "$LOG"
    done
    kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""; sleep 2
  done
done

echo "=== M31 end $(date) ===" >> "$LOG"
