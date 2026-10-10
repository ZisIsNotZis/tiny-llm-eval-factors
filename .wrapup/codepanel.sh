#!/bin/bash
# One EvalPlus 0.3.1 code panel (HumanEval/HumanEval+ and MBPP/MBPP+), serialised on the GPU.
#
# Usage: codepanel.sh <MODEL_PATH> <TAG> [limit]
#
#   limit   ---------------------------------------------------------------- IGNORED
#   EvalPlus 0.3.1 in .wrapup/evalpy cannot evaluate a subset: `evalplus.evaluate`
#   hard-asserts `len(completion_id) == len(problems)` ("Missing problems in samples")
#   whenever the samples file is smaller than the dataset.  The published EvalPlus
#   headline IS the full set (HumanEval 164 / MBPP 378), so for code we always run the
#   full suite and ignore `limit` for the code stage.  The argument is kept only so the
#   campaign driver can pass the same triple to both panels.  This is printed at start.
#   (The lm-evaluation-harness panel is the one that honours `limit`.)
#
# Protocol (frozen): greedy decoding (temperature 0.0 --greedy True), the model's own
# chat template (llama-server --jinja), ctx 8192, -np 1, -ngl 99, reasoning off.
#
# Scoring: this build's eval_results.json has keys {date, hash, eval} and does NOT
# persist pass_at_k, so pass@1 is computed here from the `eval` dict using EvalPlus's
# own single-sample definition: base = frac(base_status=="pass");
# plus = frac(base_status=="pass" AND plus_status=="pass").  Numerator and denominator
# are recorded for every bench so each number is re-derivable.  A bench that produces
# no number is written as null and listed under "errors" with its raw log tail -- never
# as 0.0 and never with an invented rejection heuristic (RESEARCH_METHOD 2b).
#
# Liveness/locking: this script takes /tmp/llama_gpu.lock with `flock -n` and reports +
# exits 3 if it is held (it never waits).  It starts its own llama-server on a port that
# `ss -ltn` proves free and kills only that server (never one it did not start).  The
# other project owns port 8834 and is left alone.
set -u
cd /home/z/hf/research || exit 2

MODEL="${1:?usage: codepanel.sh <MODEL_PATH> <TAG> [limit]}"
TAG="${2:?usage: codepanel.sh <MODEL_PATH> <TAG> [limit]}"
LIMIT="${3:-0}"

WR=/home/z/hf/research/.wrapup
PY="$WR/evalpy/bin/evalplus.codegen"
EV="$WR/evalpy/bin/evalplus.evaluate"
OUT="$WR/mres/$TAG"
ROOT="$OUT/codegen"
LOG="$OUT/code.log"
mkdir -p "$OUT" "$ROOT" || exit 2

# Hold the GPU flock for the whole run (same lock file gpu_locked.sh / lmeval_panel.sh use).
exec 9>/tmp/llama_gpu.lock
if ! flock -n 9; then
  echo "ABORT $TAG: /tmp/llama_gpu.lock is held by another panel; not waiting." | tee -a "$LOG"
  exit 3
fi

echo "=== codepanel start tag=$TAG model=$MODEL limit=$LIMIT $(date -Is)" | tee -a "$LOG"
echo "[codepanel] limit=$LIMIT is IGNORED for code: EvalPlus always runs the full suite (humaneval 164, mbpp 378)." | tee -a "$LOG"

if [ ! -f "$MODEL" ]; then
  echo "ABORT $TAG: model not found: $MODEL" | tee -a "$LOG"; exit 2
fi
MODEL_REAL="$(readlink -f "$MODEL")"

port_free() { ! ss -ltnH 2>/dev/null | grep -q ":$1 "; }
PORT=""
for p in $(seq 9200 9299); do
  if port_free "$p"; then PORT="$p"; break; fi
done
if [ -z "$PORT" ]; then
  echo "ABORT $TAG: no free port in 9200..9299" | tee -a "$LOG"; exit 2
fi
BASE="http://127.0.0.1:$PORT/v1"

SRV=""
cleanup() { if [ -n "$SRV" ]; then kill "$SRV" 2>/dev/null; SRV=""; fi; }
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

echo "[codepanel] llama-server port=$PORT (proven free by ss -ltn)" | tee -a "$LOG"
# --reasoning-format none: Phi-4-mini Q2 emits text that llama.cpp's peg-native parser
# rejects with a 500 ("output that does not match the expected peg-native format"), which
# makes evalplus retry the item.  Measured: 83/164 humaneval items took 2 h.  We never use
# thoughts or tools here, so the parser is pure overhead and is disabled.
llama-server -m "$MODEL_REAL" --port "$PORT" --host 127.0.0.1 \
  -c 8192 -np 1 -ngl 99 --jinja --reasoning off --reasoning-format none >> "$LOG" 2>&1 &
SRV=$!
ok=0
for _ in $(seq 1 300); do
  if curl -s --max-time 3 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"status":"ok"'; then ok=1; break; fi
  kill -0 "$SRV" 2>/dev/null || break
  sleep 1
done
if [ "$ok" -ne 1 ]; then
  echo "ABORT $TAG: llama-server never became healthy (see $LOG)" | tee -a "$LOG"
  exit 1
fi
# a healthy port is not proof the weights answer: demand one real completion
probe=$(curl -s --max-time 300 "http://127.0.0.1:$PORT/v1/completions" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"1+1=","max_tokens":1,"temperature":0}' 2>/dev/null)
if ! echo "$probe" | grep -q '"choices"'; then
  echo "ABORT $TAG: smoke completion failed: $(echo "$probe" | head -c 200)" | tee -a "$LOG"
  exit 1
fi
echo "[codepanel] smoke completion ok" | tee -a "$LOG"

BENCHES="humaneval mbpp"
: > "$OUT/.timings"
GEN_TO=${GEN_TO:-7200}
EVAL_TO=${EVAL_TO:-3600}
for bench in $BENCHES; do
  alias="$TAG"
  samples="$ROOT/$bench/${alias}_openai_temp_0.0.jsonl"
  ev_json="$ROOT/$bench/${alias}_openai_temp_0.0_eval_results.json"
  blog="$OUT/code_${bench}.log"
  echo "[$(date +%H:%M:%S)] codegen $bench -> $samples" | tee -a "$LOG"
  t0=$(date +%s)
  timeout "$GEN_TO" "$PY" "$alias" "$bench" --backend openai --base_url "$BASE" \
    --temperature 0.0 --greedy True --root "$ROOT" >> "$blog" 2>&1
  grc=$?
  # evalplus.codegen can append duplicate task entries under --resume; evaluate asserts
  # one sample per problem, so dedup before scoring (same as run_w1.sh).
  [ -f "$samples" ] && python3 "$WR/dedup_jsonl.py" "$samples" >> "$blog" 2>&1
  echo "[$(date +%H:%M:%S)] evaluate $bench (codegen rc=$grc)" | tee -a "$LOG"
  timeout "$EVAL_TO" "$EV" "$bench" --samples="$samples" >> "$blog" 2>&1
  erc=$?
  t1=$(date +%s)
  echo "$bench $((t1-t0)) $grc $erc" >> "$OUT/.timings"
  echo "[$(date +%H:%M:%S)] DONE bench $bench codegen_rc=$grc eval_rc=$erc $((t1-t0))s" | tee -a "$LOG"
done

# ---- aggregate: compute pass@1 from the eval dict, write evalplus.json --------------
python3 - "$OUT" "$TAG" "$MODEL" "$MODEL_REAL" "$BASE" "$PORT" <<'PYEOF'
import json, os, sys
from datetime import datetime
out, tag, model, model_real, base_url, port = sys.argv[1:7]
out = os.path.abspath(out)

def tail(path, n=40):
    if not os.path.exists(path):
        return [f"(no log at {path})"]
    lines = open(path, errors="replace").read().splitlines()
    return lines[-n:]

benches = {}
errors = []
timings = {}
total = 0.0
for line in open(os.path.join(out, ".timings")):
    parts = line.split()
    if len(parts) != 4:
        continue
    bench, secs, grc, erc = parts[0], int(parts[1]), int(parts[2]), int(parts[3])
    timings[bench] = secs
    total += secs
    samples = os.path.join(out, "codegen", bench, f"{tag}_openai_temp_0.0.jsonl")
    ev_json = os.path.join(out, "codegen", bench, f"{tag}_openai_temp_0.0_eval_results.json")
    blog = os.path.join(out, f"code_{bench}.log")
    entry = {"base": None, "plus": None, "n": None, "base_pass": None,
             "plus_pass": None, "bad_rate": None}
    # bad_rate: fraction of generated samples with an empty (sanitised) solution.
    try:
        tot = bad = 0
        for ln in open(samples):
            ln = ln.strip()
            if not ln:
                continue
            tot += 1
            if not (json.loads(ln).get("solution") or "").strip():
                bad += 1
        if tot:
            entry["bad_rate"] = bad / tot
    except Exception:
        pass
    ok = False
    if os.path.exists(ev_json):
        try:
            doc = json.load(open(ev_json))
            ev = doc.get("eval") or {}
            n = len(ev)
            base_pass = sum(1 for r in ev.values() if r and r[0].get("base_status") == "pass")
            plus_pass = sum(1 for r in ev.values()
                            if r and r[0].get("base_status") == "pass"
                            and r[0].get("plus_status") == "pass")
            if n:
                entry.update({"n": n, "base_pass": base_pass, "plus_pass": plus_pass,
                              "base": base_pass / n, "plus": plus_pass / n})
                ok = True
        except Exception as exc:  # noqa: BLE001
            errors.append({"bench": bench, "stage": "parse",
                           "returncode": erc, "error": repr(exc),
                           "output_json": ev_json, "stderr_tail": tail(blog)})
    if not ok:
        if not any(e["bench"] == bench for e in errors):
            errors.append({"bench": bench, "stage": "evaluate",
                           "returncode": erc, "output_json": ev_json,
                           "stderr_tail": tail(blog)})
    benches[bench] = entry

panel = {
    "tag": tag,
    "model": model_real,
    "model_arg": model,
    "protocol": {"backend": "openai-chat", "temperature": 0.0, "greedy": True,
                 "max_new_tokens": 768, "ctx": 8192, "np": 1, "ngl": 99,
                 "jinja": True, "reasoning": "off"},
    "benches": benches,
    "errors": errors,
    "timings_s": {**timings, "total": total},
    "server": {"binary": "llama-server", "port": int(port), "base_url": base_url},
    "evalplus": "0.3.1",
    "date": datetime.now().isoformat(timespec="seconds"),
}
with open(os.path.join(out, "evalplus.json"), "w") as fh:
    fh.write(json.dumps(panel, indent=2) + "\n")

real = [b for b in benches if benches[b]["base"] is not None]
print("REAL_BENCHES", real)
for b in benches:
    e = benches[b]
    print(f"  {b}: base={e['base']} plus={e['plus']} n={e['n']} "
          f"base_pass={e['base_pass']} plus_pass={e['plus_pass']} bad_rate={e['bad_rate']}")
sys.exit(0 if real else 1)
PYEOF
agg=$?

if [ "$agg" -eq 0 ]; then
  echo "$TAG $(date -Is)" > "$OUT/code.DONE"
  echo "=== codepanel done tag=$TAG $(date -Is)" | tee -a "$LOG"
else
  echo "=== codepanel NO REAL BENCH NUMBER tag=$TAG rc=$agg (no code.DONE; see evalplus.json errors) $(date -Is)" | tee -a "$LOG"
fi
exit "$agg"
