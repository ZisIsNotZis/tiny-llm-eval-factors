#!/bin/bash
# M31 (QUEUE #5) — sampling top_k x weight quant (fixed 2026-10-05).
#
# HISTORY: the 2026-10-03 run already restarted llama-server per cell with
# `--top-k K` (client mpl_run.py raw sends only temperature). Its summary was a
# null, but NOT by construction: K in {20,40,64} changes only ~3-4 of 161
# completions and leaves pass@1 identical on all 6 model*lang cells. The flag was
# re-verified empirically (fresh server, temp 0.3, seed 1234: K=1 vs K=64 differ),
# so the correct fix is to SPAN the axis, not to change where the flag is set.
#
# DESIGN: 2B Q2/Q3/Q4 x top_k {1,20,40,64,200} at temp 0.3, seed 1234, MultiPL-E
# cpp+py (161 items). Server restarted per cell with `--top-k K`; top_p .95 /
# min_p .05 fixed. K=1 and K=200 are the bracketing ANCHORS: top_k=1 collapses the
# candidate set to the argmax, so it must reproduce the greedy cells (a
# consistency check against m3/m27), while K=200 is effectively no truncation, so
# the panel spans greedy -> uncapped and yields a trend instead of a second null.
# The K=40 column still anchors m27's temp-0.3 cells.
#
# Every (model,K) cell is compared against the previous K for the same model+lang
# and the identical-completion count is recorded, so a silently ineffective flag
# is visible in the summary instead of being read as a real null.
#
# Rows: {"model","lang","n","pass","score","temp","top_k","top_k_role",
#        "identical_vs_prev_k","protocol"}.
#
# Must run under the GPU flock (the chain does this):
#   bash gpu_locked.sh bash run_m31.sh
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m31.log
SUM=$W/m31_summary.jsonl
MRES=$W/mres
PORT=8131; BASE=http://127.0.0.1:$PORT; PY=python3
PANELS=(
  "q2:Qwen3.5-2B-UD-Q2_K_XL.gguf"
  "q3:Qwen3.5-2B-UD-Q3_K_XL.gguf"
  "q4:Qwen3.5-2B-UD-Q4_K_XL.gguf"
)
TOPK_S="1 20 40 64 200"
SRV=""
mkdir -p "$MRES"
echo "=== M31 start $(date) ===" >> "$LOG"
rm -f "$SUM"

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
  prev=""
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
      -d '{"prompt":"def add(a, b):\n    return a","n_predict":8,"temperature":0}')
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

      # Did this K actually move the completions vs the previous K? A silently
      # ignored flag would give 161/161 identical; record it per row.
      ident=""
      if [ -n "$prev" ] && [ -f "$prev" ]; then
        ident=$($PY - "$prev" "$samples" <<'PY'
import json, sys
a = [json.loads(l)["completion"] for l in open(sys.argv[1])]
b = [json.loads(l)["completion"] for l in open(sys.argv[2])]
print(sum(x == y for x, y in zip(a, b)))
PY
)
      fi
      if [ "$TK" = "1" ] || [ "$TK" = "200" ]; then role="anchor"; else role="grid"; fi
      $PY - "$tag" "$lang" "$TK" "$role" "$ident" "${samples%.jsonl}_eval.json" "$SUM" <<'PY' >> "$LOG" 2>&1
import json, sys
tag, lang, tk, role, ident, ev, dest = sys.argv[1:8]
d = json.load(open(ev))
rec = {"model": tag, "lang": lang, "n": d["n"], "pass": d["pass"], "score": d["score"],
       "temp": 0.3, "top_k": int(tk), "top_k_role": role,
       "identical_vs_prev_k": (int(ident) if ident != "" else None),
       "protocol": ("mpl-raw-t0.3-768;topk-set=1,20,40,64,200;"
                    "anchors K=1(greedy floor),K=200(no truncation)")}
with open(dest, "a") as f:
    f.write(json.dumps(rec) + "\n")
print("recorded", tag, lang, "top_k", tk, role, d["n"], "score", round(d["score"], 4),
      "identical_vs_prev", ident)
PY
      echo "[$(date +%H:%M:%S)] M31 DONE $tag top_k=$TK $lang" >> "$LOG"
      prev="$samples"
    done
    kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""; sleep 2
  done
done

echo "=== M31 end $(date) ===" >> "$LOG"
cat "$SUM" >> "$LOG" 2>/dev/null
