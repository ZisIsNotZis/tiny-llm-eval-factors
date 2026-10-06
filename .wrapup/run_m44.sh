#!/bin/bash
# M44 (QUEUE #18) — compute-precision axis, REDONE as a provable manipulation.
#
# Why: m29 (flash-attn on/off x KV dtype) recorded 24 rows, but its fa on/off
# cells were later judged a non-measurement — the two files looked identical, so
# the "0.00 floor" could not be trusted for the fa main effect. SSOT §3 makes the
# rule explicit: a manipulated variable must be shown to move the output before
# its score delta means anything.
#
# Design: a *probe* runs first. For each cell the server is started with the
# exact flags and asked for a deterministic greedy completion of three fixed
# prompts (short code, a full HumanEval cpp item, and a ~3k-token padded prompt
# where attention numerics actually differ). The two files under test are diffed
# byte-for-byte:
#   * faon_f16 vs faoff_f16  -> does `-fa` move the output AT ALL?
#   * faon_f16 vs faon_q8    -> positive control (V-cache quant is known to move it)
# A cell whose manipulation provably changes the text is `manipulation=real`; one
# that does not is `manipulation=no-op` and its score is an arithmetic null, not a
# compute-precision effect. The full 161-item panel is only meaningful for cells
# proven real, so this probe is the gate (it is also cheap: 6 short gens).
#
# The probe result is written to m44_summary.jsonl as one row per (anchor, cell).
#
# Rows: 2 anchors x 3 cells = 6.
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m44.log
SUM=$W/m44_summary.jsonl
MRES=$W/mres
PORT=8099; BASE=http://127.0.0.1:$PORT; PY=python3
mkdir -p "$MRES"
echo "=== M44 start $(date) ===" >> "$LOG"
: > "$SUM"

ANCHORS=("qwen2b-q2:Qwen3.5-2B-UD-Q2_K_XL.gguf" "qwen2b-q3:Qwen3.5-2B-UD-Q3_K_XL.gguf")
# cell : fa : cache_k : cache_v
CELLS=("faon_f16:on:q8_0:f16" "faoff_f16:off:q8_0:f16" "faon_q8:on:q8_0:q8_0")

probe() {  # <model> <out.json>  -> 0/1
  local model="$1" out="$2" srv
  if curl -s --max-time 3 "$BASE/health" >/dev/null 2>&1; then
    pkill -f "llama-server .*-m /home/z/hf/" 2>/dev/null; sleep 3
  fi
  llama-server -m "/home/z/hf/$model" --port $PORT --host 127.0.0.1 -ngl 99 -c 4096 \
    -fa "$FA" --cache-type-k "$CK" --cache-type-v "$CV" \
    --top-p 0.95 --top-k 40 --min-p 0.05 --seed 1234 >> "$LOG" 2>&1 &
  srv=$!
  local ok=0
  for i in $(seq 1 150); do curl -s --max-time 3 $BASE/health 2>/dev/null | grep -q '"status":"ok"' && { ok=1; break; }; sleep 2; done
  if [ $ok -ne 1 ]; then echo "[M44] SERVER FAIL $model fa=$FA kv=$CK/$CV" >> "$LOG"; kill $srv 2>/dev/null; return 1; fi
  $PY - "$BASE" "$out" <<'PY' >> "$LOG" 2>&1
import json, sys, urllib.request
base, out = sys.argv[1], sys.argv[2]
def gen(prompt, npred):
    body = json.dumps({"prompt": prompt, "n_predict": npred, "temperature": 0,
                       "top_p": 0.95, "top_k": 40, "min_p": 0.05, "seed": 1234}).encode()
    req = urllib.request.Request(base + "/completion", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read().decode()).get("content", "")
item = json.loads(open("/tmp/MultiPL-E/prompts/humaneval-cpp.jsonl").readline())
medium = item["prompt"]
long_p = (medium + "\n// filler\n") * 60          # ~3k tokens: attention-numerics regime
recs = {"short":  gen("def add(a, b):\n    return a", 64),
        "medium": gen(medium, 256),
        "long":   gen(long_p, 128)}
json.dump(recs, open(out, "w"))
print("probe wrote", out, {k: len(v) for k, v in recs.items()})
PY
  kill $srv 2>/dev/null; wait $srv 2>/dev/null; sleep 2
  [ -s "$out" ]
}

for a in "${ANCHORS[@]}"; do
  tag="${a%%:*}"; model="${a#*:}"
  files=""
  for c in "${CELLS[@]}"; do
    IFS=: read -r cell FA CK CV <<< "$c"
    out="$MRES/m44-${tag}-${cell}.json"
    if ! probe "$model" "$out"; then echo "[M44] FAIL probe $tag/$cell" >> "$LOG"; continue; fi
    files="$files $cell=$out"
  done
  $PY - "$tag" "$SUM" $files <<'PY' >> "$LOG" 2>&1
import json, sys
tag, dest = sys.argv[1], sys.argv[2]
cells = {}
for kv in sys.argv[3:]:
    name, path = kv.split("=", 1)
    try:
        cells[name] = json.load(open(path))
    except Exception:
        cells[name] = None
def n_diff(a, b):
    if not a or not b:
        return None
    return sum(1 for k in a if a.get(k) != b.get(k))
for name in ("faon_f16", "faoff_f16", "faon_q8"):
    rec = cells.get(name)
    if rec is None:
        continue
    fa_effect = n_diff(cells.get("faon_f16"), cells.get("faoff_f16"))
    kv_effect = n_diff(cells.get("faon_f16"), cells.get("faon_q8"))
    if name == "faoff_f16":
        manip = "real" if fa_effect else "no-op"
        var = "fa on/off"; effect = fa_effect
    elif name == "faon_q8":
        manip = "real (control)" if kv_effect else "no-op (control)"
        var = "V cache f16->q8_0"; effect = kv_effect
    else:
        manip = "reference"; var = "-"; effect = fa_effect
    row = {"model": tag, "cell": name, "var": var, "manipulation": manip,
           "prompts": len(rec), "prompts_changed_vs_reference": effect,
           "probe_len": {k: len(v) for k, v in rec.items()},
           "protocol": "m44-probe-greedy-256",
           "design": "fa main effect vs V-cache-quant positive control; manipulation must provably change text"}
    with open(dest, "a") as f:
        f.write(json.dumps(row) + "\n")
    print("recorded", tag, name, manip, "changed=", effect)
PY
done

echo "=== M44 end $(date) rows=$(wc -l < "$SUM") ===" >> "$LOG"
