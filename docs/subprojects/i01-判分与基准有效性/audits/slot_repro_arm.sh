#!/bin/bash
# i01 WP6 — one arm of the slot-reproducibility adjudication. Lock scope.
#
# The GPU is globally serialised and other subprojects queue on the same flock, so
# each arm is its own flock rather than one long hold: `slot_repro_run.sh` calls
# this once per arm through `gpu_locked.sh`, which lets a queued panel start in the
# gap between two arms instead of waiting out the whole experiment.
#
# Usage: slot_repro_arm.sh np1|npauto|npauto-b
#   np1      - server with `-np 1 -c 2048`: one slot, 2048 ctx (no batching at all)
#   npauto   - server with `-c 2048` and NO `-np`: the harness default, which on this
#              build/hardware reports `n_slots = 4, n_ctx_slot = 2048` -- i.e. exactly
#              the configuration m26/m160/m161 ran (see PLAN.md), two passes
#   npauto-b - a SECOND server with the same flags, one pass (cross-instance check)
#
# Why `-c 2048` without `-np`, and not `-np 4 -c 8192`: with an explicit `-np`, `-c`
# is the TOTAL context and is divided by the slot count, so `-np 4 -c 2048` gives
# 512 ctx per slot, while the historical panels got 2048 per slot from `-c 2048`
# with `-np` left at its default.  Reproducing the recorded configuration verbatim
# is the point of this arm, so the flag that produced it is the flag that is used,
# and the server's own report is asserted instead of assumed.
#
# VRAM: the model needs an 11.7 GiB weights buffer (measured: the failed allocation
# in PLAN.md reads 11671.15 MiB).  A previous holder that is still tearing down can
# therefore fail this load even though the flock was released; that is what killed
# the first np4 attempt.  So an arm waits for free VRAM and retries the load once
# after an out-of-memory death, and a death with any other cause is not retried.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
cd "$REPO" || exit 1

ARM=${1:?usage: slot_repro_arm.sh np1|npauto|npauto-b}
case "$ARM" in
  np1)      NP_FLAG="-np 1"; CTX=2048; PASSES="p1 p2"; WANT_SLOTS=1 ;;
  npauto)   NP_FLAG="";      CTX=2048; PASSES="p1 p2"; WANT_SLOTS=4 ;;
  npauto-b) NP_FLAG="";      CTX=2048; PASSES="p1";    WANT_SLOTS=4 ;;
  *) echo "unknown arm $ARM" >&2; exit 2 ;;
esac

TAG=i01-slot
LOG=$REPO/.wrapup/i01_slot_repro.log
MRES=$REPO/.wrapup/mres
PROMPTS=$REPO/.wrapup/prompts
PORT=${PORT:-8087}
BASE=http://127.0.0.1:$PORT
MODEL=${MODEL:-/home/z/hf/Qwen3.8-27B-UD-Q3_K_XL.gguf}
LANG_=py
CHAT_KW='{"enable_thinking": false}'
# Derived, not guessed: weights buffer 11,671 MiB (measured OOM line) + KV/compute
# 3,084 MiB (measured: 22,627 free before load, 7,872 free while generating at 4 slots x
# 2048 ctx) + 1,536 MiB headroom = 16,291 MiB -> 16 GiB.
MIN_FREE_MIB=${MIN_FREE_MIB:-16384}
PY=python3
mkdir -p "$MRES"

say() { echo "[$TAG] $*" | tee -a "$LOG"; }

for f in "$PROMPTS"/humaneval-*.jsonl; do
  [ -s "$f" ] || { say "ABORT arm=$ARM: prompt set missing $f"; exit 2; }
done
( cd "$PROMPTS" && sha256sum -c SHA256SUMS --quiet ) >/dev/null 2>&1 || {
  say "ABORT arm=$ARM: prompt set does not match $PROMPTS/SHA256SUMS"; exit 2; }
say "arm=$ARM start $(date +%H:%M:%S) np_flag=[$NP_FLAG] ctx=$CTX passes=[$PASSES] want_slots=$WANT_SLOTS"

if ss -ltnp 2>/dev/null | grep -q ":$PORT "; then
  pid=$(ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1)
  if [ -n "${pid:-}" ] && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q "llama-server"; then
    say "arm=$ARM reaping stale llama-server pid=$pid"
    kill "$pid"; sleep 3
  else
    say "ABORT arm=$ARM: port $PORT held by a non-llama process pid=${pid:-unknown}"; exit 2
  fi
fi

# --- wait for the previous holder's VRAM to actually be released.  The flock is
# --- released by the shell, not by the dying process's cudaFree, so a handover can
# --- hand us a locked-but-full GPU.
wait_vram() {
  local i free
  for i in $(seq 1 60); do
    free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
    if [ "${free:-0}" -ge "$MIN_FREE_MIB" ]; then
      say "arm=$ARM vram free=${free}MiB (>= ${MIN_FREE_MIB}MiB)"
      return 0
    fi
    [ "$i" = 1 ] && say "arm=$ARM waiting for vram: free=${free}MiB < ${MIN_FREE_MIB}MiB"
    sleep 5
  done
  say "ABORT arm=$ARM: free VRAM ${free:-?}MiB stayed below ${MIN_FREE_MIB}MiB for 300s (another holder)"
  return 1
}
wait_vram || exit 4

srv=""
stop_server() { [ -n "$srv" ] && { kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; }; }
trap stop_server EXIT INT TERM

start_server() {
  # shellcheck disable=SC2086
  llama-server -m "$MODEL" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$CTX" \
    $NP_FLAG --cache-type-k q8_0 --cache-type-v q8_0 --jinja \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  srv=$!
  for _ in $(seq 1 180); do
    kill -0 "$srv" 2>/dev/null || return 1
    curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && return 0
    sleep 2
  done
  return 1
}

died_of_oom() { tail -40 "$LOG" | grep -q "cudaMalloc failed: out of memory"; }

if ! start_server; then
  if died_of_oom; then
    say "arm=$ARM first load died with cudaMalloc OOM (previous holder still freeing); retrying once in 30s"
    sleep 30
    wait_vram || exit 4
    start_server || { say "arm=$ARM server DIED on the retry; see the OOM lines above"; exit 3; }
  else
    say "arm=$ARM server DIED (not OOM; see the last lines of this log)"; exit 3
  fi
fi
slots=$(grep -o "n_slots = [0-9]*, n_ctx_slot = [0-9]*" "$LOG" | tail -1)
if ! echo "$slots" | grep -q "n_slots = $WANT_SLOTS,"; then
  say "ABORT arm=$ARM: server reports [${slots}] but this arm must run with n_slots = $WANT_SLOTS (config mismatch is not a measurement)"
  stop_server
  exit 5
fi
"$PY" - "$MRES/i01-slot-$ARM-meta.json" "$NP_FLAG" "$slots" "$CTX" "$MODEL" "$PROMPTS/humaneval-$LANG_.jsonl" <<'PY'
import json, sys, hashlib, subprocess
dest, npflag, slots, ctx, model, prompt = sys.argv[1:7]
meta = {"arm_np_flag": npflag or "(none: server default)",
        "llama_reports": slots, "ctx_flag_total_or_default": int(ctx),
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
