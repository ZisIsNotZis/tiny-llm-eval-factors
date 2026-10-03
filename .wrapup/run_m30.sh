#!/bin/bash
# M30 (QUEUE #4) — KV-cache quantisation x context-length grid.
#
# Tier 3B is only partially done: a K vs V asymmetry was seen at 8k/24k on one
# model, plus a V-side collapse at 24k on Qwen3.6-27B-IQ2_M (K-only pass@1_plus
# 0.00610 vs V-only 0.00000). The pooled score fit currently gives K a weak
# coefficient (bkK=-0.09, weak) and V a strong one (bkV=+0.52), so the
# asymmetry is a live, pooled-level claim this grid can confirm or break.
#
# Design: ONE model (Qwen3.5-2B UD-Q3_K_XL) x ONE dataset (MultiPL-E cpp, 161
# items) x ctx {8192, 24576, 49152} x KV {f16/f16, q8_0/f16, f16/q8_0, q8_0/q8_0}
# = 12 cells. ctx and KV are the only variables.
#
# FA is pinned ON for every cell: a quantised V cache REQUIRES flash-attn on
# llama.cpp build 4399 ("quantized V cache requires flash_attn"), so `-fa on` is
# the only setting that admits all four combos. The FA main effect is measured
# separately in m29. Otherwise the frozen protocol: top_p .95 / top_k 40 /
# min_p .05, raw completion, greedy, 768 max tokens. Every cell smoke-tests the
# server with one real completion before its generation.
#
# Scope note: MultiPL-E prompts are short, so the ctx knob measures KV-quant
# behaviour at large *allocated* windows — the same protocol as the earlier
# "long-context" KV runs — not a long-sequence stress test.
#
# Rows: {"model","lang","n","pass","score","ctx","kv","fa","protocol"}.
#
# Must run under the GPU flock (the chain does this):
#   bash gpu_locked.sh bash run_m30.sh
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m30_32.log
SUM=$W/m30_summary.jsonl
MRES=$W/mres
PORT=8130; BASE=http://127.0.0.1:$PORT; PY=python3
MODEL=Qwen3.5-2B-UD-Q3_K_XL.gguf
CTXS="8192 24576 49152"
KVS=("f16 f16" "q8_0 f16" "f16 q8_0" "q8_0 q8_0")
SRV=""
mkdir -p "$MRES"
echo "=== M30 start $(date) ===" >> "$LOG"

cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; return 0; }
trap cleanup EXIT INT TERM

clear_port() {
  curl -s --max-time 3 "$BASE/health" >/dev/null 2>&1 || return 0
  if pgrep -f "llama-server .*-m /home/z/hf/" >/dev/null 2>&1; then
    pkill -f "llama-server .*-m /home/z/hf/"; sleep 3
  else
    echo "[$(date +%H:%M:%S)] M30 ABORT: port $PORT held by a foreign server" >> "$LOG"
    exit 2
  fi
}

run_cell() {  # ctx ktype vtype
  local ctx="$1" kt="$2" vt="$3" ok SM samples
  clear_port
  echo "[$(date +%H:%M:%S)] M30 server ctx=$ctx kv=$kt/$vt" >> "$LOG"
  llama-server -m "/home/z/hf/$MODEL" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$ctx" \
    -fa on --cache-type-k "$kt" --cache-type-v "$vt" \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  SRV=$!
  ok=0
  for i in $(seq 1 150); do
    curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && { ok=1; break; }
    sleep 2
  done
  if [ $ok -ne 1 ]; then
    echo "[$(date +%H:%M:%S)] M30 SERVER FAIL ctx=$ctx kv=$kt/$vt" >> "$LOG"
    kill "$SRV" 2>/dev/null; SRV=""; return 1
  fi
  SM=$(curl -s --max-time 180 "$BASE/completion" -H 'Content-Type: application/json' \
    -d '{"prompt":"def add(a, b):\n    return a","n_predict":8,"temperature":0,"top_p":0.95,"top_k":40,"min_p":0.05}')
  if ! echo "$SM" | grep -q '"content"'; then
    echo "[$(date +%H:%M:%S)] M30 SMOKE FAIL ctx=$ctx kv=$kt/$vt" >> "$LOG"
    kill "$SRV" 2>/dev/null; SRV=""; return 1
  fi

  samples="$MRES/m30-q3-ctx${ctx}-kv${kt}_${vt}-cpp.jsonl"
  echo "[$(date +%H:%M:%S)] M30 gen ctx=$ctx kv=$kt/$vt cpp" >> "$LOG"
  timeout 7200 $PY mpl_run.py gen --lang cpp --mode raw --greedy --max_tokens 768 \
    --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  $PY mpl_run.py eval --lang cpp --samples "$samples" >> "$LOG" 2>&1
  $PY - "$ctx" "$kt" "$vt" "${samples%.jsonl}_eval.json" "$SUM" <<'PY' >> "$LOG" 2>&1
import json, sys
ctx, kt, vt, ev, dest = sys.argv[1:6]
d = json.load(open(ev))
rec = {"model": "qwen2b-q3", "lang": "cpp", "n": d["n"], "pass": d["pass"],
       "score": d["score"], "ctx": int(ctx), "kv": f"{kt}/{vt}", "fa": "on",
       "protocol": f"mpl-raw-greedy-768;ctx={ctx},kv={kt}/{vt},fa=on"}
with open(dest, "a") as f:
    f.write(json.dumps(rec) + "\n")
print("recorded q3 ctx", ctx, "kv", kt, vt, d["n"], round(d["score"], 4))
PY
  echo "[$(date +%H:%M:%S)] M30 DONE ctx=$ctx kv=$kt/$vt" >> "$LOG"
  kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""; sleep 2
}

for ctx in $CTXS; do
  for kv in "${KVS[@]}"; do
    set -- $kv
    run_cell "$ctx" "$1" "$2"
  done
done

echo "=== M30 end $(date) ===" >> "$LOG"
