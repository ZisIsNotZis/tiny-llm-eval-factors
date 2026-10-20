#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M52 (NEXT_DRIVER N3) — Tier 4B: decode SPEED vs prompt type (prose vs code) and,
# if the MTP draft head loads, the spec-draft length curve. This is a different
# measurement type from the score panels: it records tokens/s (prefill + decode)
# rather than accuracy, so it does not touch the quant->score claims, but it answers
# (a) whether throughput depends on task type and (b) what draft length pays off —
# a question BRAINSTORM 4B raised and the queue has never measured.
#
# Base rows (always): 2 targets (gemma-4-12B Q3, Qwen3.5-9B Q3) x {code, prose} = 4.
# Extra rows (only if the draft head loads): gemma target x draft_n {2,4,6} x {code,prose}.
#
# Rows are {"model","prompt_type","draft_n","prompt_tps","decode_tps","n_decoded",...}.
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m52.log
SUM=$W/m52_summary.jsonl
PORT=${M52_PORT:-8160}
BASE=http://127.0.0.1:$PORT
DRAFT=mtp-gemma-4-12B-it.gguf
echo "=== M52 start $(date) ===" >> "$LOG"

srv=""
cleanup() { [ -n "$srv" ] && kill "$srv" 2>/dev/null; srv=""; }
trap cleanup EXIT

start_server() {  # basename [extra args...]
  local file="$1"; shift
  llama-server -m "/home/z/hf/$file" --port "$PORT" --host 127.0.0.1 -ngl 99 \
    -c 8192 -np 1 --cache-type-k q8_0 --cache-type-v q8_0 "$@" >> "$LOG" 2>&1 &
  srv=$!
  for i in $(seq 1 150); do
    curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && break
    kill -0 "$srv" 2>/dev/null || break
    sleep 2
  done
  curl -s --max-time 5 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"'
}

measure() {  # tag prompt_type draft_n
  python3 - "$BASE" "$1" "$2" "$3" "$SUM" <<'PY' >> "$LOG" 2>&1
import json, sys, urllib.request
base, tag, ptype, draft_n, dest = sys.argv[1:6]
code = ("def solve(xs):\n    # return the running maximum of a list of ints\n"
        "    best = xs[0]\n    out = []\n    for x in xs:\n        best = max(best, x)\n"
        "        out.append(best)\n    return out\n") * 6
prose = ("The measurement of quantisation effects on language models requires careful "
         "control of the decoding protocol, because the same weights can score very "
         "differently under raw completion and under a chat template. ") * 6
prompt = code if ptype == "code" else prose
body = {"prompt": prompt, "n_predict": 256, "temperature": 0, "top_p": 0.95,
        "top_k": 40, "min_p": 0.05}
req = urllib.request.Request(base + "/completion", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
r = json.loads(urllib.request.urlopen(req, timeout=900).read().decode())
t = r.get("timings", {})
row = {"model": tag, "prompt_type": ptype, "draft_n": int(draft_n),
       "prompt_tps": round(t.get("prompt_per_second", 0.0), 2),
       "decode_tps": round(t.get("predicted_per_second", 0.0), 2),
       "n_decoded": t.get("predicted_n"), "protocol": "speed-greedy-256-tps"}
print(json.dumps(row))
open(dest, "a").write(json.dumps(row) + "\n")
PY
}

for spec in "gemma-4-12b-it-UD-Q3_K_XL.gguf:gemma12b-q3" "Qwen3.5-9B-UD-Q3_K_XL.gguf:qwen9b-q3"; do
  file="${spec%%:*}"; tag="${spec##*:}"
  if [ ! -e "/home/z/hf/$file" ]; then echo "[M52] SKIP $tag: $file missing" >> "$LOG"; continue; fi
  if start_server "$file"; then
    for pt in code prose; do measure "$tag" "$pt" 0; done
    echo "[M52] baseline done $tag $(date +%H:%M:%S)" >> "$LOG"
  else
    echo "[M52] SERVER FAIL $tag; skipping" >> "$LOG"
  fi
  kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; sleep 3
done

# Optimal draft length for the gemma target (MTP head shares the tokenizer).
if [ -e "/home/z/hf/$DRAFT" ]; then
  for dn in 2 4 6; do
    if start_server "gemma-4-12b-it-UD-Q3_K_XL.gguf" -md "/home/z/hf/$DRAFT" -ngld 99 --spec-draft-n-max "$dn"; then
      for pt in code prose; do measure "gemma12b-q3-draft" "$pt" "$dn"; done
      echo "[M52] draft n=$dn done $(date +%H:%M:%S)" >> "$LOG"
    else
      echo "[M52] draft n=$dn: server fail (MTP head unsupported?); stopping sweep" >> "$LOG"
      break
    fi
    kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; sleep 3
  done
else
  echo "[M52] SKIP draft sweep: $DRAFT missing" >> "$LOG"
fi

echo "=== M52 end $(date) ===" >> "$LOG"
