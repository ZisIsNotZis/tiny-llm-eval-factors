#!/bin/bash
# i01 WP6 — one arm of the slot-reproducibility adjudication. Lock scope.
#
# The GPU is globally serialised and other subprojects queue on the same flock, so
# each arm is its own flock rather than one long hold: `slot_repro_run.sh` calls
# this once per arm through `gpu_locked.sh`, which lets a queued panel start in the
# gap between two arms instead of waiting out the whole experiment.
#
# Usage: slot_repro_arm.sh np1|np4|np4b
#   np1  - server with -np 1, two generation passes (no batching at all)
#   np4  - server with -np 4, two generation passes (the production slot count)
#   np4b - a SECOND -np 4 server, one pass (cross-instance check)
#
# Everything else -- pinned prompt set, chat, thinking off, greedy, 768 tokens,
# ctx 2048 -- is the recorded cell's protocol (see slot_repro_run.sh for why).
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
cd "$REPO" || exit 1

ARM=${1:?usage: slot_repro_arm.sh np1|np4|np4b}
case "$ARM" in
  np1)  NP=1; PASSES="p1 p2" ;;
  np4)  NP=4; PASSES="p1 p2" ;;
  np4b) NP=4; PASSES="p1" ;;
  *) echo "unknown arm $ARM" >&2; exit 2 ;;
esac

TAG=i01-slot
LOG=$REPO/.wrapup/i01_slot_repro.log
MRES=$REPO/.wrapup/mres
PROMPTS=$REPO/.wrapup/prompts
PORT=${PORT:-8087}
BASE=http://127.0.0.1:$PORT
CTX_PER_SLOT=${CTX:-2048}
CTX_TOTAL=$((CTX_PER_SLOT * NP))
MODEL=${MODEL:-/home/z/hf/Qwen3.8-27B-UD-Q3_K_XL.gguf}
LANG_=py
CHAT_KW='{"enable_thinking": false}'
PY=python3
mkdir -p "$MRES"

say() { echo "[$TAG] $*" | tee -a "$LOG"; }

for f in "$PROMPTS"/humaneval-*.jsonl; do
  [ -s "$f" ] || { say "ABORT arm=$ARM: prompt set missing $f"; exit 2; }
done
( cd "$PROMPTS" && sha256sum -c SHA256SUMS --quiet ) >/dev/null 2>&1 || {
  say "ABORT arm=$ARM: prompt set does not match $PROMPTS/SHA256SUMS"; exit 2; }
say "arm=$ARM start $(date +%H:%M:%S) np=$NP passes=[$PASSES]"

if ss -ltnp 2>/dev/null | grep -q ":$PORT "; then
  pid=$(ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1)
  if [ -n "${pid:-}" ] && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q "llama-server"; then
    say "arm=$ARM reaping stale llama-server pid=$pid"
    kill "$pid"; sleep 3
  else
    say "ABORT arm=$ARM: port $PORT held by a non-llama process pid=${pid:-unknown}"; exit 2
  fi
fi

srv=""
stop_server() { [ -n "$srv" ] && { kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; }; }
trap stop_server EXIT INT TERM

# -c is TOTAL with an explicit -np and PER-SLOT when -np is auto, so the arms are
# held equal on the quantity that actually matters (ctx per slot = 2048, the value
# every recorded chat cell ran with) and differ only in the slot count.
llama-server -m "$MODEL" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$CTX_TOTAL" \
  -np "$NP" --cache-type-k q8_0 --cache-type-v q8_0 --jinja \
  --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
srv=$!
for _ in $(seq 1 180); do
  kill -0 "$srv" 2>/dev/null || { say "arm=$ARM server DIED"; exit 3; }
  curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && break
  sleep 2
done
curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' || {
  say "arm=$ARM server TIMEOUT"; exit 3; }
slots=$(grep -o "n_slots = [0-9]*, n_ctx_slot = [0-9]*" "$LOG" | tail -1)
"$PY" - "$MRES/i01-slot-$ARM-meta.json" "$NP" "$slots" "$CTX_TOTAL" "$CTX_PER_SLOT" "$MODEL" "$PROMPTS/humaneval-$LANG_.jsonl" <<'PY'
import json, sys, hashlib, subprocess
dest, np, slots, ctx, ctx_slot, model, prompt = sys.argv[1:8]
meta = {"arm_np_flag": int(np), "llama_reports": slots,
        "ctx_flag_total": int(ctx), "ctx_per_slot_intended": int(ctx_slot),
        "model": model, "lang": "py", "mode": "chat", "greedy": True,
        "max_tokens": 768, "chat_kwargs": {"enable_thinking": False},
        "strip_thought": True,
        "prompt_sha256": hashlib.sha256(open(prompt, "rb").read()).hexdigest(),
        "server_version": subprocess.run(["llama-server", "--version"],
                                          capture_output=True, text=True).stdout.strip()}
json.dump(meta, open(dest, "w"), indent=1, ensure_ascii=False)
print(json.dumps(meta, ensure_ascii=False))
PY
say "arm=$ARM server up: $slots"

for pass in $PASSES; do
  samples="$MRES/i01-slot-$ARM-$pass-$LANG_-chat.jsonl"
  say "gen arm=$ARM pass=$pass start=$(date +%H:%M:%S)"
  timeout 1800 "$PY" .wrapup/mpl_run.py gen --lang "$LANG_" --mode chat --greedy \
    --max_tokens 768 --strip-thought --chat-kwargs "$CHAT_KW" \
    --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  rc=$?
  say "gen arm=$ARM pass=$pass end=$(date +%H:%M:%S) rc=$rc"
  [ "$rc" = 0 ] || { say "GEN-FAILED arm=$ARM pass=$pass rc=$rc"; stop_server; exit 3; }
  timeout 2400 "$PY" .wrapup/mpl_run.py eval --lang "$LANG_" --samples "$samples" >> "$LOG" 2>&1
  rc2=$?
  say "eval arm=$ARM pass=$pass rc=$rc2 $(jq -c '{n,pass,score}' "${samples%.jsonl}_eval.json" 2>/dev/null)"
  [ "$rc2" = 0 ] || { stop_server; exit 3; }
done

stop_server
say "arm=$ARM done $(date +%H:%M:%S) (GPU lock released)"
