#!/bin/bash
# m161 — re-measure the 6 chat/py cells plus one end-to-end control cell with
# the FIXED MultiPL-E postprocess (commit b57a71f, mpl_run.py::strip_fences).
#
# WHY: the stored chat/py samples in m26 were scored under the pre-fix
# postprocess (`completion.strip()` before the fence pass) and re-scoring them
# with the fixed code still gives pass 0 (result.res21), so those cells cannot be
# recovered from the old samples and the models are re-generated against the
# pinned prompt set.  Re-generating is not a rescue for every cell: under the
# fixed harness gemma-4-26B-A4B py is still Exception-dominated (159/161,
# 160/161) because the model writes the function body's first line at column 0,
# which is model behaviour and not something the harness re-indents
# (result.res24).
#
# Correctness gate: a post-hoc re-evaluation of the already stored
# q38-27b-q3 cpp chat samples with the fixed code gives 138/161 = 0.8571, and
# that re-score of the OLD samples is the reference (CONTROL_REF) -- it is not
# this cell's current value and not the rerun's number: the fresh generation of
# the same cell scored 140/161 = 0.8696 (result.res24).  A fresh generation is
# run FIRST and must land inside 0.8571 +/- 0.03 = [0.8271, 0.8871]; if it does
# not, the harness fix has not taken effect on the generation side either and
# the run stops instead of producing six quietly wrong cells.
#
# Protocol (unchanged from m26/m160 chat, do not edit):
#   llama-server -ngl 99 -c 2048 --cache-type-k q8_0 --cache-type-v q8_0
#     --jinja --top-p 0.95 --top-k 40 --min-p 0.05
#   mpl_run.py gen --mode chat --greedy --max_tokens 768 --strip-thought
#     --chat-kwargs '{"enable_thinking": false}'
#   mpl_run.py eval --lang <lang> --samples <cell>.jsonl
# Only the model file, the language and the cell tag vary.
#
# Run under the GPU flock:
#   bash .wrapup/gpu_locked.sh bash .wrapup/run_m161_chat_py.sh
# Subset (cells are `<tag>:<lang>`, space separated):
#   ONLY="q38-27b-q3:cpp" bash .wrapup/run_m161_chat_py.sh
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$HERE" || exit 1
LOG=$HERE/m161.log
SUMMARY=$HERE/m161_summary.jsonl
MRES=$HERE/mres
PROMPTS=${MULTIPLE_PROMPTS:-$HERE/prompts}
PORT=${PORT:-8086}
BASE=http://127.0.0.1:$PORT
CTX=${CTX:-2048}
PY=python3
CHAT_KW='{"enable_thinking": false}'
PROTOCOL="mpl-chat-nothink-greedy-768"
# control cell first: it is the falsification gate for the harness fix
MODELS="q38-27b-q3:Qwen3.8-27B-UD-Q3_K_XL.gguf g12b-q2:gemma-4-12b-it-UD-Q2_K_XL.gguf g12b-q3:gemma-4-12b-it-UD-Q3_K_XL.gguf g26b-q2:gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf g26b-q3:gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf q38-27b-q2:Qwen3.8-27B-UD-Q2_K_XL.gguf"
ONLY=${ONLY:-}
CONTROL_TAG=q38-27b-q3
CONTROL_LANG=cpp
CONTROL_REF=0.8571
CONTROL_TOL=0.03

mkdir -p "$MRES"
# A full panel starts the summary fresh; a subset run (ONLY=...) appends to the
# rows the earlier cells already produced, because the panel is measured across
# several invocations and truncating here would discard measured cells.
[ -n "$ONLY" ] || : > "$SUMMARY"
TAGLOG="M161"
echo "[$TAGLOG] panel start $(date) models=[$MODELS] cells=[6x py chat + 1x cpp chat control] only=[$ONLY] protocol=$PROTOCOL" >> "$LOG"

# --- preflight: the prompt set is the experiment's input, so its contents are
# --- hashed into the log and checked against SHA256SUMS before GPU time is spent.
preflight() {
  local f h missing=0
  for f in "$PROMPTS"/humaneval-*.jsonl; do
    [ -s "$f" ] || { echo "[$TAGLOG] ABORT: prompt set missing $f" >> "$LOG"; missing=1; continue; }
    h=$(sha256sum "$f" | cut -d' ' -f1)
    echo "[$TAGLOG] prompt $(basename "$f") sha256=$h" >> "$LOG"
  done
  [ "$missing" = 0 ] || return 1
  ( cd "$PROMPTS" && sha256sum -c SHA256SUMS --quiet ) >/dev/null 2>&1 || {
    echo "[$TAGLOG] ABORT: prompt set does not match SHA256SUMS in $PROMPTS (a panel run against an unpinned prompt set is not comparable)" >> "$LOG"
    return 1
  }
  echo "[$TAGLOG] preflight ok: prompt set matches SHA256SUMS" >> "$LOG"
}
preflight || exit 2

echo "[$TAGLOG] llama-server $(llama-server --version 2>&1 | tr '\n' ' ')" >> "$LOG"

pid=$(ss -ltnp 2>/dev/null | grep ":$PORT" | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$pid" ] && kill "$pid"; sleep 2

srv=""
cleanup() { [ -n "$srv" ] && kill "$srv" 2>/dev/null; }
trap cleanup EXIT

start_server() {
  llama-server -m "/home/z/hf/$1" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$CTX" \
    --cache-type-k q8_0 --cache-type-v q8_0 --jinja \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  srv=$!
  for _ in $(seq 1 180); do
    kill -0 "$srv" 2>/dev/null || { echo "[$TAGLOG] server DIED $1" >> "$LOG"; return 1; }
    curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && return 0
    sleep 2
  done
  echo "[$TAGLOG] server TIMEOUT $1" >> "$LOG"; kill "$srv" 2>/dev/null; return 1
}

# Number of empty completions, or UNREADABLE when the samples file is missing or
# unparseable -- the two states stay distinct so an infrastructure failure is
# never recorded as a model that produced nothing.
samples_state() {
  "$PY" - "$1" <<'PY'
import json, os, sys
p = sys.argv[1]
if not os.path.exists(p):
    print("UNREADABLE:file-missing"); raise SystemExit
try:
    rows = [json.loads(l) for l in open(p)]
except Exception as e:
    print(f"UNREADABLE:{type(e).__name__}"); raise SystemExit
print(f"{sum(1 for r in rows if not (r.get('completion') or '').strip())}/{len(rows)}")
PY
}

cell_wanted() {
  [ -z "$ONLY" ] && return 0
  local c
  for c in $ONLY; do [ "$c" = "$1" ] && return 0; done
  return 1
}

stop_server() { [ -n "$srv" ] && { kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; }; }

# Writes one summary row.  An all-Exception cell is an infrastructure failure,
# not a measured zero, so its score is recorded as null (m48: SyntaxError /
# Exception / Timeout are distinct and are never folded into one 0).
record() {   # $1 tag  $2 lang  $3 eval-json
  "$PY" - "$1" "$2" "$3" "$SUMMARY" "$PROTOCOL" <<'PY' >> "$LOG" 2>&1
import json, sys, collections
tag, lang, ev, dest, proto = sys.argv[1:6]
d = json.load(open(ev))
st = collections.Counter(x.get("status") for x in d.get("details", []))
n = d["n"]
score = None if (n and st.get("Exception", 0) == n) else d["score"]
row = {"model": tag, "lang": lang, "n": n, "pass": d["pass"],
       "score": score, "protocol": proto, "statuses": dict(st)}
with open(dest, "a") as f:
    f.write(json.dumps(row) + "\n")
print("[M161] recorded", tag, lang, "n=%d pass=%d score=%s" % (n, d["pass"], score), dict(st))
PY
}

run_cell() {   # $1 tag  $2 lang  $3 model
  local tag="$1" lang="$2" model="$3"
  local samples="$MRES/m161-${tag}-${lang}-chat.jsonl"
  cell_wanted "$tag:$lang" || return 0
  start_server "$model" || return 1
  echo "[$TAGLOG] gen $tag $lang mode=chat start=$(date +%H:%M:%S)" >> "$LOG"
  timeout 1800 "$PY" mpl_run.py gen --lang "$lang" --mode chat --greedy \
    --max_tokens 768 --strip-thought --chat-kwargs "$CHAT_KW" \
    --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  local rc=$?
  echo "[$TAGLOG] gen $tag $lang mode=chat end=$(date +%H:%M:%S) rc=$rc" >> "$LOG"
  [ "$rc" = 124 ] && echo "[$TAGLOG] GEN-TIMEOUT $tag $lang (1800s cap, not retried beyond once)" >> "$LOG"
  local state; state=$(samples_state "$samples")
  case "$state" in
    UNREADABLE:*)
      echo "[$TAGLOG] GEN-FAILED $tag $lang mode=chat $state" >> "$LOG"
      stop_server; return 1 ;;
  esac
  local empty=${state%%/*}
  if [ "$empty" -gt 32 ]; then
    echo "[$TAGLOG] CORRUPT $tag $lang mode=chat empty=${state}" >> "$LOG"
    stop_server; return 1
  fi
  timeout 2400 "$PY" mpl_run.py eval --lang "$lang" --samples "$samples" >> "$LOG" 2>&1
  record "$tag" "$lang" "${samples%.jsonl}_eval.json"
  stop_server; sleep 3
  return 0
}

# --- control cell: fresh generation of q38-27b-q3 cpp chat, scored against the
# --- post-hoc re-evaluation of the old samples.  A deviation means the fix did
# --- not take effect on the generation side; stop before measuring anything else.
control_gate() {
  local ev="$MRES/m161-${CONTROL_TAG}-${CONTROL_LANG}-chat_eval.json"
  cell_wanted "$CONTROL_TAG:$CONTROL_LANG" || {
    echo "[$TAGLOG] control gate skipped: $CONTROL_TAG $CONTROL_LANG not in ONLY=[$ONLY] (a subset run cannot move it)" >> "$LOG"
    return 0
  }
  [ -s "$ev" ] || { echo "[$TAGLOG] control not measured, skipping gate" >> "$LOG"; return 1; }
  "$PY" - "$ev" "$CONTROL_REF" "$CONTROL_TOL" "$LOG" <<'PY'
import json, sys
ev, ref, tol, log = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
d = json.load(open(ev))
score, lo, hi = d["score"], ref - tol, ref + tol
verdict = "PASS" if lo <= score <= hi else "FAIL"
line = ("[M161] CONTROL %s %d/%d score=%.4f band=[%.4f,%.4f] ref=%.4f tol=+-%.2f verdict=%s"
        % (d["lang"], d["pass"], d["n"], score, lo, hi, ref, tol, verdict))
open(log, "a").write(line + "\n")
print(line)
raise SystemExit(0 if verdict == "PASS" else 3)
PY
}

# smoke test before the long loop
smoke_file="${MODELS%% *}"; smoke_file="${smoke_file#*:}"
echo "[$TAGLOG] smoke: loading $smoke_file" >> "$LOG"
if start_server "$smoke_file"; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 180 -X POST "$BASE/completion" \
     -H 'Content-Type: application/json' \
     -d '{"prompt":"def f():\n    return 1","n_predict":8,"temperature":0}')
  echo "[$TAGLOG] smoke: health=ok completion_http=$code" >> "$LOG"
  stop_server
  [ "$code" = "200" ] || { echo "[$TAGLOG] ABORT: smoke completion != 200" >> "$LOG"; exit 1; }
else
  echo "[$TAGLOG] ABORT: smoke load failed" >> "$LOG"; exit 1
fi

# run one cell with at most one retry; `ok=0` means the cell is unmeasured
run_with_retry() {   # $1 tag  $2 lang  $3 model
  local tag="$1" lang="$2" model="$3" attempt ok=0
  for attempt in 1 2; do
    if run_cell "$tag" "$lang" "$model"; then ok=1; break; fi
    cell_wanted "$tag:$lang" || { ok=1; break; }
    [ "$attempt" = 1 ] && { echo "[$TAGLOG] retry $tag $lang mode=chat (attempt 1)" >> "$LOG"; sleep 5; }
  done
  [ "$ok" = 1 ] || echo "[$TAGLOG] GAVE UP $tag $lang mode=chat (unmeasured)" >> "$LOG"
}

# control cell FIRST: the falsification gate costs one cell when the harness is
# still broken, and six if it were run last
for spec in $MODELS; do
  if [ "${spec%%:*}" = "$CONTROL_TAG" ]; then
    echo "[$TAGLOG] control gate cell: $CONTROL_TAG $CONTROL_LANG ref=$CONTROL_REF +-$CONTROL_TOL" >> "$LOG"
    run_with_retry "$CONTROL_TAG" "$CONTROL_LANG" "${spec#*:}"
    control_gate || { echo "[$TAGLOG] ABORT: control cell outside band, stopping before the other six cells" >> "$LOG"; echo "[$TAGLOG] panel end $(date)" >> "$LOG"; exit 3; }
  fi
done

# Every model gets its py cell, including the control tag: this loop is always
# lang=py, while the gate above is lang=cpp, so they are different cells.
for spec in $MODELS; do
  tag="${spec%%:*}"; model="${spec#*:}"
  run_with_retry "$tag" py "$model"
done

echo "[$TAGLOG] panel end $(date)" >> "$LOG"
