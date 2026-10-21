#!/bin/bash
# a06 R1 of the vendor arm: the code columns, where the five vendor sampling
# values can only be set at SERVER LAUNCH.
#
# Why server-side: `mpl_run.py`'s raw payload carries only
# prompt/temperature/n_predict/stop (`mpl_run.py:146-150`) and `evalplus.codegen`
# has only `--temperature`, so `top_p`/`top_k`/`min_p`/`presence_penalty` never
# reach the sampler through either client.  `run_m31.sh:66-68` solved this the
# same way for `top_k`: restart the server per cell with the value as a server
# flag.  Consequence, and the reason this is a good check: on this route `/props`
# reports all five values, so `/props` IS the proof they took effect.  (The other
# route -- lm-eval `--gen_kwargs` -- passes them per request, so there `/props`
# stays at the server default `temperature=0.8` and proves nothing.)
#
# DESIGN: Qwen3.5-2B UD-Q2/Q3/Q4 x cpp/py on MultiPL-E raw (161 items), ctx 4096
# to match the m3/m27/m31 anchors column for column, seed 1234 to match m27/m31,
# plus one EvalPlus HumanEval cell on Q3 to give the arm a code column on the
# standard set.  The protocol string carries `ctx=` and `sampling=` so
# `make_report.mpl_protocol_label` cannot fold these cells into a greedy row and
# so a different ctx cannot be pooled with them.
#
# Values are copied verbatim from the unsloth Qwen3.5-2B card (non-thinking, text
# tasks): temperature=1.0, top_p=1.00, top_k=20, min_p=0.0, presence_penalty=2.0,
# repetition_penalty=1.0.  Provenance: docs/subprojects/a06-.../evidence/
# vendor-card-excerpt-*.md
#
# Resumable: every finished cell appends one JSON line to $SUM, so a kill loses
# at most the cell in flight.
#
# Must run under the GPU flock:
#   bash .wrapup/gpu_locked.sh bash "docs/subprojects/a06-采样与解码参数/run_vendor_arm.sh"
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
W="$REPO_ROOT/.wrapup"
cd "$W" || exit 2

TEMP=1.0; TOP_P=1.00; TOP_K=20; MIN_P=0.0; PRES=2.0; SEED=1234
CTX=4096; MAXTOK=768
PROTO="mpl-raw-t1.0-768;ctx=${CTX};sampling=temp=${TEMP},top_p=${TOP_P},top_k=${TOP_K},min_p=${MIN_P},presence_penalty=${PRES}"
OUT="$W/mres/m165-vendor"
LOG="$OUT/vendor_r1.log"
SUM="$OUT/vendor_r1_summary.jsonl"
PROPS="$OUT/props"
LLAMA=${LLAMA_SERVER:-/home/z/.local/bin/llama-server}
PORT=8141; BASE="http://127.0.0.1:$PORT"; PY=python3
EVALPLUS=$W/evalpy/bin/evalplus.codegen
EVALPLUS_EV=$W/evalpy/bin/evalplus.evaluate

mkdir -p "$OUT" "$PROPS"
echo "=== m165 vendor R1 start $(date) ===" >> "$LOG"
SRV=""
cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; return 0; }
trap cleanup EXIT INT TERM

done_cell() {  # done_cell <key> -> 0 when the cell already has a summary line
  [ -f "$SUM" ] && grep -q "\"cell\": \"$1\"" "$SUM"
}

start_server() {  # start_server <model-path> <tag>
  local model="$1" tag="$2"
  if curl -s --max-time 3 "$BASE/health" >/dev/null 2>&1; then
    if pgrep -f "llama-server .*-m /home/z/hf/" >/dev/null 2>&1; then
      pkill -f "llama-server .*-m /home/z/hf/"; sleep 3
    else
      echo "[$(date +%H:%M:%S)] ABORT: port $PORT held by a foreign server" >> "$LOG"; return 2
    fi
  fi
  echo "[$(date +%H:%M:%S)] server $tag ctx=$CTX temp=$TEMP top_p=$TOP_P top_k=$TOP_K min_p=$MIN_P pres=$PRES seed=$SEED" >> "$LOG"
  "$LLAMA" -m "$model" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$CTX" -np 1 \
    --jinja --reasoning off --temp "$TEMP" --top-p "$TOP_P" --top-k "$TOP_K" \
    --min-p "$MIN_P" --presence-penalty "$PRES" --seed "$SEED" >> "$LOG" 2>&1 &
  SRV=$!
  for _ in $(seq 1 120); do
    curl -sf "$BASE/health" >/dev/null 2>&1 && return 0
    kill -0 "$SRV" 2>/dev/null || { echo "SERVER DIED $tag" >> "$LOG"; return 1; }
    sleep 1
  done
  echo "SERVER TIMEOUT $tag" >> "$LOG"; return 1
}

assert_props() {  # assert_props <tag> -> writes $PROPS/<tag>.json, fails on mismatch
  local tag="$1" got
  curl -s "$BASE/props" > "$PROPS/$tag.raw.json" 2>/dev/null
  got=$($PY - "$PROPS/$tag.raw.json" "$PROPS/$tag.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
p = d.get("default_generation_settings", {}).get("params", {})
want = {"temperature": 1.0, "top_p": 1.0, "top_k": 20, "min_p": 0.0, "presence_penalty": 2.0}
got = {k: p.get(k) for k in want}
bad = [k for k in want if got[k] is None or abs(float(got[k]) - want[k]) > 1e-6]
json.dump({"want": want, "got": got, "mismatch": bad,
           "n_slots": d.get("total_slots")},
          open(sys.argv[2], "w"), indent=1, sort_keys=True)
print("MISMATCH " + ",".join(bad) if bad else "OK")
PY
)
  echo "[$(date +%H:%M:%S)] /props $tag: $got" >> "$LOG"
  [ "$got" = "OK" ]
}

assert_slots() {  # n_slots must equal -np 1
  local n
  n=$(grep -o "n_slots = [0-9]*" "$LOG" | tail -1 | grep -o "[0-9]*$")
  [ "${n:-0}" = "1" ] || { echo "SLOT MISMATCH n_slots=${n:-none}" >> "$LOG"; return 1; }
}

for spec in "q2:Qwen3.5-2B-UD-Q2_K_XL.gguf" "q3:Qwen3.5-2B-UD-Q3_K_XL.gguf" "q4:Qwen3.5-2B-UD-Q4_K_XL.gguf"; do
  tag="${spec%%:*}"; model="/home/z/hf/${spec#*:}"
  [ -f "$model" ] || { echo "MISSING MODEL $model" >> "$LOG"; exit 2; }
  if done_cell "${tag}-cpp" && done_cell "${tag}-py" && done_cell "${tag}-humaneval"; then
    echo "[$(date +%H:%M:%S)] skip $tag (all cells recorded)" >> "$LOG"; continue
  fi
  start_server "$model" "$tag" || exit 3
  assert_slots || { kill "$SRV" 2>/dev/null; SRV=""; exit 4; }
  if ! assert_props "$tag"; then
    echo "[$(date +%H:%M:%S)] ABORT: server did not take the vendor sampling values" >> "$LOG"
    kill "$SRV" 2>/dev/null; SRV=""; exit 5
  fi

  for lang in cpp py; do
    [ "$(done_cell "${tag}-${lang}" && echo yes)" = "yes" ] && { echo "skip ${tag}-${lang}" >> "$LOG"; continue; }
    samples="$OUT/mpl-${tag}-${lang}-vendor.jsonl"
    echo "[$(date +%H:%M:%S)] gen $tag $lang" >> "$LOG"
    timeout 3600 $PY mpl_run.py gen --lang "$lang" --mode raw --temperature "$TEMP" \
      --max_tokens "$MAXTOK" --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1 || { echo "GEN FAIL $tag $lang" >> "$LOG"; continue; }
    $PY mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1 || { echo "EVAL FAIL $tag $lang" >> "$LOG"; continue; }
    $PY - "$tag" "$lang" "${samples%.jsonl}_eval.json" "$SUM" "$PROTO" "$CTX" > /dev/null <<'PY' >> "$LOG" 2>&1
import json, sys
tag, lang, ev, dest, proto, ctx = sys.argv[1:7]
d = json.load(open(ev))
rec = {"cell": f"{tag}-{lang}", "model": tag, "lang": lang, "n": d["n"],
       "pass": d["pass"], "score": d["score"], "temp": 1.0, "top_p": 1.0,
       "top_k": 20, "min_p": 0.0, "presence_penalty": 2.0, "seed": 1234,
       "ctx": int(ctx), "protocol": proto, "samples": ev.replace("_eval.json", ".jsonl")}
with open(dest, "a") as f:
    f.write(json.dumps(rec) + "\n")
print("recorded", rec["cell"], d["n"], round(d["score"], 4))
PY
    echo "[$(date +%H:%M:%S)] DONE $tag $lang" >> "$LOG"
  done
  kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""; sleep 2
done

# ---- EvalPlus HumanEval on Q3: the code column on the standard set -----------
if [ "$(done_cell "q3-humaneval" && echo yes)" != "yes" ]; then
  start_server /home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf q3-code || exit 3
  assert_slots || { kill "$SRV" 2>/dev/null; SRV=""; exit 4; }
  assert_props q3-code || { echo "ABORT props q3-code" >> "$LOG"; kill "$SRV" 2>/dev/null; SRV=""; exit 5; }
  cg="$OUT/codegen/vendor-recommended"
  mkdir -p "$cg"
  echo "[$(date +%H:%M:%S)] codegen humaneval" >> "$LOG"
  timeout 3600 "$EVALPLUS" "m165-vendor-q3-code" humaneval --backend openai \
    --base_url "$BASE/v1" --temperature "$TEMP" --root "$cg" >> "$LOG" 2>&1 \
    || echo "CODEGEN FAIL" >> "$LOG"
  samples=$(find "$cg" -name "*_openai_temp_*.jsonl" ! -name "*.raw.*" | head -1)
  if [ -n "$samples" ]; then
    "$EVALPLUS_EV" humaneval --samples "$samples" >> "$LOG" 2>&1 || echo "EVALPLUS EVAL FAIL" >> "$LOG"
    ev=$(find "$cg" -name "*_eval_results.json" | head -1)
    if [ -n "$ev" ]; then
      $PY - "$ev" "$SUM" "$PROTO" "$CTX" >> "$LOG" 2>&1 <<'PY'
import json, sys, collections
ev, dest, proto, ctx = sys.argv[1:5]
d = json.load(open(ev))["eval"]
status = collections.Counter(v["base_status"] for ent in d.values()
                             for v in (ent if isinstance(ent, list) else [ent]))
n = len(d); npass = status.get("pass", 0)
rec = {"cell": "q3-humaneval", "model": "q3", "lang": "python", "n": n,
       "pass": npass, "score": npass / n if n else None,
       "temp": 1.0, "top_p": 1.0, "top_k": 20, "min_p": 0.0,
       "presence_penalty": 2.0, "seed": 1234, "ctx": int(ctx),
       "protocol": proto + ";bench=evalplus-humaneval",
       "status_histogram": dict(status), "eval_results": ev}
with open(dest, "a") as f:
    f.write(json.dumps(rec) + "\n")
print("recorded q3-humaneval", n, npass, dict(status))
PY
    fi
  else
    echo "NO SAMPLES for evalplus" >> "$LOG"
  fi
  kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""; sleep 1
fi

echo "=== m165 vendor R1 end $(date) ===" >> "$LOG"
echo "--- summary ---"
cat "$SUM" 2>/dev/null
