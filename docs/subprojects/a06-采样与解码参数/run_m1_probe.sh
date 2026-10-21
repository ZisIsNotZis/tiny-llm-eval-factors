#!/bin/bash
# a06 M1: the mechanism discriminator for the vendor-setting collapse.
#
# QUESTION (pre-registered in RESULT.md::vendor-collapse-mechanism, decided BEFORE
# running): the vendor setting collapses q3-cpp from 39/161 to 4/161.  Two
# non-exclusive hypotheses:
#   H-A  `presence_penalty=2.0` taxes every token that already appeared, and code
#        lives on repeated structural tokens (indent, `return`, `std::`, `{}`,
#        reused identifiers), so the model is pushed onto non-code strings.
#   H-B  `top_p=1.0` + `min_p=0.0` leave the tail unbounded, so at temp 1.0 the
#        sampler reaches far-tail tokens regardless of any penalty.
#
# TEST: change exactly ONE value -- `presence_penalty` 2.0 -> 0.0 -- and leave
# temp 1.0, top_p 1.0, top_k 20, min_p 0.0, seed 1234, ctx 4096 untouched.  A
# 40-item probe of the same cell, because this decides a DIRECTION, not a score.
#
#   collapse gone (well above the 0.05 floor)  -> H-A is the main cause
#   still ~1/40                              -> H-A rejected, points at H-B
#   halved but not gone                       -> not decisive; buy M3 (2x2)
#
# The probe is NOT a score: 40 items is not comparable to the 161-item cells and
# must never be pooled with them (AGENTS.md, a12's probe rule).
#
# Must run under the GPU flock, and only when R1 is not holding it:
#   bash .wrapup/gpu_locked.sh bash "docs/subprojects/a06-采样与解码参数/run_m1_probe.sh"
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
W="$REPO_ROOT/.wrapup"
cd "$W" || exit 2

# The five sampling values are overridable so one script covers every arm of the
# mechanism question; the defaults are M1 (presence_penalty=0, truncation left off).
#   M1 (run) TEMP=1.0 TOP_P=1.00 MIN_P=0.0 PRES=0.0   -> rejected H-A
#   M2       TEMP=1.0 TOP_P=0.95 MIN_P=0.05 PRES=0.0  -> H-B vs "temperature 1.0 itself"
TAG=${TAG:-m1}
TEMP=${TEMP:-1.0}; TOP_P=${TOP_P:-1.00}; TOP_K=${TOP_K:-20}; MIN_P=${MIN_P:-0.0}
PRES=${PRES:-0.0}; SEED=${SEED:-1234}
CTX=${CTX:-4096}; MAXTOK=${MAXTOK:-768}; LIMIT=${LIMIT:-40}
PROTO="mpl-raw-t1.0-768;ctx=${CTX};sampling=temp=${TEMP},top_p=${TOP_P},top_k=${TOP_K},min_p=${MIN_P},presence_penalty=${PRES};probe=first${LIMIT}"
OUT="$W/mres/m165-mechanism"
LOG="$OUT/${TAG}_probe.log"
LLAMA=${LLAMA_SERVER:-/home/z/.local/bin/llama-server}
MODEL=/home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf
PORT=8151; BASE="http://127.0.0.1:$PORT"; PY=python3

mkdir -p "$OUT"
echo "=== ${TAG} probe start $(date) ===" >> "$LOG"
[ -f "$MODEL" ] || { echo "MISSING MODEL $MODEL" >> "$LOG"; exit 2; }
if curl -s --max-time 3 "$BASE/health" >/dev/null 2>&1; then
  echo "ABORT: port $PORT already in use" >> "$LOG"; exit 2
fi

echo "[$(date +%H:%M:%S)] server pres=$PRES temp=$TEMP top_p=$TOP_P top_k=$TOP_K min_p=$MIN_P seed=$SEED ctx=$CTX" >> "$LOG"
"$LLAMA" -m "$MODEL" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$CTX" -np 1 \
  --jinja --reasoning off --temp "$TEMP" --top-p "$TOP_P" --top-k "$TOP_K" \
  --min-p "$MIN_P" --presence-penalty "$PRES" --seed "$SEED" >> "$LOG" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT INT TERM
for _ in $(seq 1 120); do
  curl -sf "$BASE/health" >/dev/null 2>&1 && break
  kill -0 "$SRV" 2>/dev/null || { echo "SERVER DIED" >> "$LOG"; exit 3; }
  sleep 1
done

# The single-variable claim is only true if /props shows exactly one changed value.
curl -s "$BASE/props" > "$OUT/props_${TAG}.json"
$PY - "$OUT/props_${TAG}.json" "$TEMP" "$TOP_P" "$TOP_K" "$MIN_P" "$PRES" >> "$LOG" 2>&1 <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))["default_generation_settings"]["params"]
want = {"temperature": float(sys.argv[2]), "top_p": float(sys.argv[3]),
        "top_k": int(float(sys.argv[4])), "min_p": float(sys.argv[5]),
        "presence_penalty": float(sys.argv[6])}
got = {k: p.get(k) for k in want}
bad = [k for k in want if got[k] is None or abs(float(got[k]) - want[k]) > 1e-6]
print("probe /props:", got, "mismatch:", bad)
sys.exit(0 if not bad else 1)
PY
[ $? -eq 0 ] || { echo "ABORT: server did not take the requested values" >> "$LOG"; exit 5; }

samples="$OUT/${TAG}-q3-cpp-probe${LIMIT}.jsonl"
echo "[$(date +%H:%M:%S)] gen limit=$LIMIT" >> "$LOG"
timeout 1800 $PY mpl_run.py gen --lang cpp --mode raw --temperature "$TEMP" \
  --max_tokens "$MAXTOK" --limit "$LIMIT" --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1 \
  || { echo "GEN FAIL" >> "$LOG"; exit 4; }
$PY mpl_run.py eval --lang cpp --samples "$samples" >> "$LOG" 2>&1 || { echo "EVAL FAIL" >> "$LOG"; exit 4; }

$PY - "${samples%.jsonl}_eval.json" "$OUT/${TAG}_summary.jsonl" "$PROTO" "$LIMIT" "$TAG" "$TEMP" "$TOP_P" "$TOP_K" "$MIN_P" "$PRES" >> "$LOG" 2>&1 <<'PY'
import json, sys, collections
ev, dest, proto, limit, tag, t, tp, tk, mp, pp = sys.argv[1:12]
d = json.load(open(ev))
hist = collections.Counter(x["status"] for x in d["details"])
rec = {"cell": f"{tag}-q3-cpp-probe{limit}", "model": "q3", "lang": "cpp",
       "n": d["n"], "pass": d["pass"], "score": d["score"],
       "temp": float(t), "top_p": float(tp), "top_k": int(float(tk)),
       "min_p": float(mp), "presence_penalty": float(pp),
       "seed": 1234, "ctx": 4096,
       "probe_items": int(limit), "is_score": False,
       "status_histogram": dict(hist), "protocol": proto}
with open(dest, "a") as fh:
    fh.write(json.dumps(rec, sort_keys=True) + "\n")
print("recorded", rec["cell"], d["n"], d["pass"], round(d["score"], 4), dict(hist))
PY
echo "=== ${TAG} probe end $(date) ===" >> "$LOG"
tail -4 "$LOG"
