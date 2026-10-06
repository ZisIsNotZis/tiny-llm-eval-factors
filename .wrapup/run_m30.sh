#!/bin/bash
# M30 (QUEUE #4) — KV-cache quantisation x INPUT length (fixed 2026-10-05).
#
# WHY THE PREVIOUS RUN WAS A NULL BY CONSTRUCTION:
#   MultiPL-E prompts are ~100-300 tokens, so the 2026-10-03 grid varied only the
#   *allocated* window (`-c`) while every cell fed the model the same short input.
#   All four KV types scored identically at every ctx (e.g. f16/f16 0.2484 at
#   8192, 24576 AND 49152) — by construction, not by finding.
#
# FIX: pad the INPUT. Each of the first 60 cpp HumanEval items is prepended with a
# realistic code preamble (other HumanEval prompts + their canonical solutions),
# padded to a token budget just under the target ctx (see m30_build_pad.py). Now
# the KV cache genuinely holds ~ctx tokens and the cache type is exercised at
# length. ctx in {2048, 16384, 49152} is the only window knob; the prompt is
# sized from the observed lengths (SSOT 3.4).
#
# KV in {f16/f16, q8_0/f16, f16/q8_0, q8_0/q8_0}. FA is pinned ON for all cells:
# a quantised V cache requires flash-attn in build 4399 ("quantized V cache
# requires flash_attn"), so it is the only setting that admits all four combos;
# the FA main effect is measured separately in m29. One model (Qwen3.5-2B
# UD-Q3_K_XL), one language (cpp), 60 items/cell, greedy, 768 max tokens, frozen
# server defaults top_p .95 / top_k 40 / min_p .05.
#
# Rows: {"model","lang","n","pass","score","ctx","kv","prompt_tokens","fa","protocol"}.
#
# Must run under the GPU flock (the chain does this):
#   bash gpu_locked.sh bash run_m30.sh
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=${M30_LOG:-$W/m30.log}
SUM=$W/m30_summary.jsonl
MRES=$W/mres
PAD=/tmp/m30_pad
PORT=8130; BASE=http://127.0.0.1:$PORT; PY=python3
MODEL=Qwen3.5-2B-UD-Q3_K_XL.gguf
CTXS="2048 16384 49152"
KVS=("f16 f16" "q8_0 f16" "f16 q8_0" "q8_0 q8_0")
SRV=""
mkdir -p "$MRES" "$PAD"
echo "=== M30 start $(date) ===" >> "$LOG"
rm -f "$SUM"

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

wait_health() {
  local i
  for i in $(seq 1 150); do
    curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && return 0
    sleep 2
  done
  return 1
}

# Phase 1 — build the padded prompt files once (any load works; /tokenize needs
# no context, so a 512-token server is enough).
echo "[$(date +%H:%M:%S)] M30 build padded prompt files" >> "$LOG"
clear_port
llama-server -m "/home/z/hf/$MODEL" --port "$PORT" --host 127.0.0.1 -ngl 99 -c 512 -fa on \
  >> "$LOG" 2>&1 &
SRV=$!
if wait_health; then
  timeout 3600 $PY m30_build_pad.py --base-url "$BASE" --outdir "$PAD" --n 60 \
    --ctxs "$(echo "$CTXS" | tr ' ' ',')" >> "$LOG" 2>&1
  echo "[$(date +%H:%M:%S)] M30 pad build rc=$? files=$(ls "$PAD" | tr '\n' ' ')" >> "$LOG"
else
  echo "[$(date +%H:%M:%S)] M30 pad-builder server FAILed" >> "$LOG"
fi
kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""; sleep 2

for ctx in $CTXS; do
  if [ ! -s "$PAD/m30_pad_ctx${ctx}.jsonl" ]; then
    echo "[$(date +%H:%M:%S)] M30 ABORT: padded prompt file missing for ctx=$ctx" >> "$LOG"
    exit 1
  fi
done

run_cell() {  # ctx ktype vtype
  local ctx="$1" kt="$2" vt="$3" ok SM samples mpt
  clear_port
  echo "[$(date +%H:%M:%S)] M30 server ctx=$ctx kv=$kt/$vt" >> "$LOG"
  llama-server -m "/home/z/hf/$MODEL" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$ctx" \
    -fa on --cache-type-k "$kt" --cache-type-v "$vt" \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  SRV=$!
  if ! wait_health; then
    echo "[$(date +%H:%M:%S)] M30 SERVER FAIL ctx=$ctx kv=$kt/$vt" >> "$LOG"
    kill "$SRV" 2>/dev/null; SRV=""; return 1
  fi
  SM=$(curl -s --max-time 180 "$BASE/completion" -H 'Content-Type: application/json' \
    -d '{"prompt":"def add(a, b):\n    return a","n_predict":8,"temperature":0}')
  if ! echo "$SM" | grep -q '"content"'; then
    echo "[$(date +%H:%M:%S)] M30 SMOKE FAIL ctx=$ctx kv=$kt/$vt" >> "$LOG"
    kill "$SRV" 2>/dev/null; SRV=""; return 1
  fi

  samples="$MRES/m30-ctx${ctx}-kv${kt}_${vt}-cpp.jsonl"
  echo "[$(date +%H:%M:%S)] M30 gen ctx=$ctx kv=$kt/$vt cpp" >> "$LOG"
  timeout 10800 $PY mpl_run.py gen --lang cpp --mode raw --greedy --max_tokens 768 \
    --prompt-file "$PAD/m30_pad_ctx${ctx}.jsonl" \
    --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  $PY mpl_run.py eval --lang cpp --samples "$samples" >> "$LOG" 2>&1
  mpt=$($PY - "$PAD/m30_pad_ctx${ctx}_meta.json" <<'PY'
import json, sys
print(round(json.load(open(sys.argv[1]))["mean_prompt_tokens"], 1))
PY
)
  $PY - "$ctx" "$kt" "$vt" "$mpt" "${samples%.jsonl}_eval.json" "$SUM" <<'PY' >> "$LOG" 2>&1
import json, sys
ctx, kt, vt, mpt, ev, dest = sys.argv[1:7]
d = json.load(open(ev))
rec = {"model": "qwen2b-q3", "lang": "cpp", "n": d["n"], "pass": d["pass"],
       "score": d["score"], "ctx": int(ctx), "kv": f"{kt}/{vt}",
       "prompt_tokens": float(mpt), "fa": "on",
       "protocol": f"mpl-raw-greedy-768;ctx={ctx},kv={kt}/{vt},fa=on,prefix={mpt}tok"}
with open(dest, "a") as f:
    f.write(json.dumps(rec) + "\n")
print("recorded q3 ctx", ctx, "kv", kt, vt, "n", d["n"], "score", round(d["score"], 4))
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
cat "$SUM" >> "$LOG" 2>/dev/null
