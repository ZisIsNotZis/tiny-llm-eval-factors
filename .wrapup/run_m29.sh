#!/bin/bash
# M29 — Tier 3A: attention/compute precision (flash-attn) x weight quant.
#
# Design (approved; 2x2 minus one):
#   cell faon_f16  : FA on  + K q8_0 + V f16   } FA main effect, IDENTICAL KV
#   cell faoff_f16 : FA off + K q8_0 + V f16   }
#   cell faon_q8   : FA on  + K q8_0 + V q8_0  } V-cache-quant effect at identical FA
# The 4th cell (FA off + V q8_0) is IMPOSSIBLE on llama.cpp build 4399:
# "quantized V cache requires flash_attn to be enabled". Hence 2x2 minus one.
# Anchors: Qwen3.5-2B UD-Q2_K_XL and UD-Q3_K_XL. Languages: cpp, py.
# Otherwise the frozen protocol: ctx 4096, top_p .95 / top_k 40 / min_p .05,
# raw completion (MultiPL-E native), greedy, 768 max tokens.
#
# NOTE: m3's standard 2B cells (q2/q3) used `-fa auto` + K/V q8_0 -> effectively
# FA-on; cell faon_q8 is the same config and is the bridge to those cells.
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m24_29.log
SUMMARY=$W/m29_summary.jsonl
MRES=$W/mres
PORT=8080; BASE=http://127.0.0.1:$PORT; PY=python3
mkdir -p "$MRES"
echo "=== M29 start $(date) ===" >> "$LOG"

run_cell() {  # tag model fa ktype vtype cell
  local tag="$1" model="$2" fa="$3" kt="$4" vt="$5" cell="$6"
  local SRV
  if curl -s --max-time 3 "$BASE/health" >/dev/null 2>&1; then
    if pgrep -f "llama-server .*-m /home/z/hf/" >/dev/null 2>&1; then
      pkill -f "llama-server .*-m /home/z/hf/"; sleep 3
    else
      echo "[$(date +%H:%M:%S)] M29 ABORT $tag/$cell: port $PORT held by foreign server" >> "$LOG"; return 2
    fi
  fi
  llama-server -m "/home/z/hf/$model" --port $PORT --host 127.0.0.1 -ngl 99 -c 4096 \
    -fa "$fa" --cache-type-k "$kt" --cache-type-v "$vt" \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  SRV=$!
  trap 'kill $SRV 2>/dev/null' EXIT INT TERM
  local ok=0
  for i in $(seq 1 150); do curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"' && { ok=1; break; }; sleep 2; done
  if [ $ok -ne 1 ]; then echo "[$(date +%H:%M:%S)] M29 SERVER FAIL $tag/$cell $model fa=$fa kv=$kt/$vt" >> "$LOG"; kill $SRV 2>/dev/null; return 1; fi
  local SM
  SM=$(curl -s --max-time 180 $BASE/completion -H 'Content-Type: application/json' \
    -d '{"prompt":"def add(a, b):\n    return a","n_predict":8,"temperature":0,"top_p":0.95,"top_k":40,"min_p":0.05}')
  if ! echo "$SM" | grep -q '"content"'; then echo "[$(date +%H:%M:%S)] M29 SMOKE FAIL $tag/$cell" >> "$LOG"; kill $SRV 2>/dev/null; return 1; fi
  echo "[$(date +%H:%M:%S)] M29 smoke ok $tag/$cell fa=$fa kv=$kt/$vt" >> "$LOG"
  local lang samples
  for lang in cpp py; do
    samples="$MRES/m29-${tag}-${cell}-${lang}.jsonl"
    echo "[$(date +%H:%M:%S)] M29 gen $tag/$cell $lang" >> "$LOG"
    timeout 7200 $PY mpl_run.py gen --lang "$lang" --mode raw --greedy \
      --max_tokens 768 --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
    $PY mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
    $PY - "$tag" "$lang" "${samples%.jsonl}_eval.json" "$SUMMARY" "$cell" "$fa" "$kt" "$vt" <<'PY' >> "$LOG" 2>&1
import json,sys
tag,lang,ev,dest,cell,fa,kt,vt=sys.argv[1:9]
d=json.load(open(ev))
rec={"model":tag,"lang":lang,"n":d["n"],"pass":d["pass"],"score":d["score"],
     "cell":cell,"fa":fa,"cache_k":kt,"cache_v":vt,
     "protocol":f"mpl-raw-greedy-768;fa={fa},kv={kt}/{vt}",
     "design":"fa2x2minus1: cell FA-off+Vq8_0 impossible on llama.cpp build4399 (quantized V cache requires flash_attn)"}
with open(dest,"a") as f: f.write(json.dumps(rec)+"\n")
print("recorded",tag,cell,lang,d["n"],round(d["score"],4))
PY
    echo "[$(date +%H:%M:%S)] M29 DONE $tag/$cell $lang" >> "$LOG"
  done
  kill $SRV 2>/dev/null; sleep 3
}

for tm in "q2:Qwen3.5-2B-UD-Q2_K_XL.gguf" "q3:Qwen3.5-2B-UD-Q3_K_XL.gguf"; do
  tag="${tm%%:*}"; model="${tm#*:}"
  run_cell "$tag" "$model" on  q8_0 f16  faon_f16
  run_cell "$tag" "$model" off q8_0 f16  faoff_f16
  run_cell "$tag" "$model" on  q8_0 q8_0 faon_q8
done
echo "=== M29 end $(date) ===" >> "$LOG"
