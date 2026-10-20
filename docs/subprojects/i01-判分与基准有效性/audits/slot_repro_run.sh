#!/bin/bash
# i01 WP6 — slot-reproducibility adjudication for plan15's cell.
#
# Question: the same cell (`q38-27b-q3 py chat`, protocol mpl-chat-nothink-greedy-768)
# is recorded at 131/161 (m26, old postprocess), 139/161 (re-score of m26 samples
# with the fixed postprocess, RESULT.md::res20) and 145/161 (m161, fresh
# generation).  131->139 is explained by the scoring defect; the remaining
# 139->145 = 6 problems can only come from the generation side, with two candidate
# causes: (a) m161 used the rebuilt prompt set in .wrapup/prompts, m26 used the
# deleted /tmp/MultiPL-E/prompts; (b) both runs were 4-slot servers and greedy
# decoding across a batch is not guaranteed bit-reproducible.
#
# The deleted prompt set cannot be recovered, so this run separates the variable
# that is still controllable -- the number of server slots -- and leaves (a)
# recorded as unmeasurable unless every arm here is identical.
#
# Arms (all on the pinned prompt set, chat, thinking off, greedy, 768 tokens,
# ctx 2048, exactly as the recorded cells):
#   np1  : one server started with -np 1, two independent generation passes
#   np4  : one server started with -np 4, two independent generation passes
#   np4b : a SECOND server started with -np 4, one pass (cross-instance check)
#
# The recorded cells ran without an explicit -np: this llama-server build defaults
# to -np auto and reported `n_slots = 4`, which is why np4 is the production arm.
# Each arm writes its own meta json (n_slots, n_ctx_slot, prompt hash, version)
# so a slot-count change can never be a silent input change again.
#
# Run under the GPU flock:
#   bash .wrapup/gpu_locked.sh bash "docs/subprojects/i01-判分与基准有效性/audits/slot_repro_run.sh"
# Then adjudicate:
#   python3 "docs/subprojects/i01-判分与基准有效性/audits/slot_repro_compare.py"
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
cd "$REPO" || exit 1

TAG=i01-slot
LOG=$REPO/.wrapup/i01_slot_repro.log
MRES=$REPO/.wrapup/mres
PROMPTS=$REPO/.wrapup/prompts
PORT=${PORT:-8087}
BASE=http://127.0.0.1:$PORT
CTX=${CTX:-2048}
MODEL=${MODEL:-/home/z/hf/Qwen3.8-27B-UD-Q3_K_XL.gguf}
LANG_=py
CHAT_KW='{"enable_thinking": false}'
PY=python3
mkdir -p "$MRES"

say() { echo "[$TAG] $*" | tee -a "$LOG"; }

# --- preflight: the prompt set is an input of this experiment, so its hash goes
# --- into the log and is checked against SHA256SUMS before GPU time is spent.
preflight() {
  local f missing=0
  for f in "$PROMPTS"/humaneval-*.jsonl; do
    [ -s "$f" ] || { say "ABORT: prompt set missing $f"; missing=1; }
  done
  [ "$missing" = 0 ] || return 1
  ( cd "$PROMPTS" && sha256sum -c SHA256SUMS --quiet ) >/dev/null 2>&1 || {
    say "ABORT: prompt set does not match $PROMPTS/SHA256SUMS"; return 1; }
  say "preflight ok: prompt set matches SHA256SUMS"
  say "prompt humaneval-$LANG_.jsonl sha256=$(sha256sum "$PROMPTS/humaneval-$LANG_.jsonl" | cut -d' ' -f1)"
}
preflight || exit 2

say "start $(date)"
say "llama-server: $(llama-server --version 2>&1 | tr '\n' ' ')"
say "model: $MODEL size=$(stat -Lc %s "$MODEL") mtime=$(date -r "$MODEL" -Iseconds)"
[ -f "$MODEL" ] || { say "ABORT: model missing $MODEL"; exit 2; }

# a previous run that died before its kill would answer on this port from the
# wrong model, so reap only a server we can attribute to this experiment
if ss -ltnp 2>/dev/null | grep -q ":$PORT "; then
  pid=$(ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1)
  if [ -n "${pid:-}" ] && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q "llama-server"; then
    say "reaping stale llama-server pid=$pid on port $PORT"
    kill "$pid"; sleep 3
  else
    say "ABORT: port $PORT held by a non-llama process pid=${pid:-unknown}"; exit 2
  fi
fi

srv=""
stop_server() { [ -n "$srv" ] && { kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; }; }
trap stop_server EXIT INT TERM

# start_server <np> <arm>: -np is explicit in both arms so the value is recorded
start_server() {
  local np=$1 arm=$2
  llama-server -m "$MODEL" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$CTX" \
    -np "$np" --cache-type-k q8_0 --cache-type-v q8_0 --jinja \
    --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
  srv=$!
  local i
  for i in $(seq 1 180); do
    kill -0 "$srv" 2>/dev/null || { say "server DIED arm=$arm"; return 1; }
    curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && break
    sleep 2
  done
  curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' || {
    say "server TIMEOUT arm=$arm"; kill "$srv" 2>/dev/null; return 1; }
  local slots
  slots=$(grep -o "n_slots = [0-9]*, n_ctx_slot = [0-9]*" "$LOG" | tail -1)
  "$PY" - "$MRES/i01-slot-$arm-meta.json" "$np" "$slots" "$CTX" "$MODEL" "$PROMPTS/humaneval-$LANG_.jsonl" <<'PY'
import json, sys, hashlib, subprocess
dest, np, slots, ctx, model, prompt = sys.argv[1:7]
meta = {"arm_np_flag": int(np), "llama_reports": slots, "ctx_flag": int(ctx),
        "model": model, "lang": "py", "mode": "chat", "greedy": True,
        "max_tokens": 768, "chat_kwargs": {"enable_thinking": False},
        "strip_thought": True,
        "prompt_sha256": hashlib.sha256(open(prompt, "rb").read()).hexdigest(),
        "server_version": subprocess.run(["llama-server", "--version"],
                                          capture_output=True, text=True).stdout.strip()}
json.dump(meta, open(dest, "w"), indent=1, ensure_ascii=False)
print(json.dumps(meta, ensure_ascii=False))
PY
  say "arm=$arm server up: $slots"
}

# gen_eval <arm> <pass>: one generation pass + its scoring
gen_eval() {
  local arm=$1 pass=$2
  local samples="$MRES/i01-slot-$arm-$pass-$LANG_-chat.jsonl"
  say "gen arm=$arm pass=$pass start=$(date +%H:%M:%S)"
  timeout 1800 "$PY" .wrapup/mpl_run.py gen --lang "$LANG_" --mode chat --greedy \
    --max_tokens 768 --strip-thought --chat-kwargs "$CHAT_KW" \
    --samples "$samples" --base_url "$BASE" >> "$LOG" 2>&1
  local rc=$?
  say "gen arm=$arm pass=$pass end=$(date +%H:%M:%S) rc=$rc"
  [ "$rc" = 0 ] || { say "GEN-FAILED arm=$arm pass=$pass rc=$rc"; return 1; }
  timeout 2400 "$PY" .wrapup/mpl_run.py eval --lang "$LANG_" --samples "$samples" >> "$LOG" 2>&1
  local rc2=$?
  say "eval arm=$arm pass=$pass rc=$rc2 $(jq -c '{n,pass,score}' "${samples%.jsonl}_eval.json" 2>/dev/null)"
  [ "$rc2" = 0 ] || return 1
}

# --- arm np1: no batching at all
start_server 1 np1 || exit 3
gen_eval np1 p1 || { stop_server; exit 3; }
gen_eval np1 p2 || { stop_server; exit 3; }
stop_server; sleep 3

# --- arm np4: the production slot count, same server, two passes
start_server 4 np4 || exit 3
gen_eval np4 p1 || { stop_server; exit 3; }
gen_eval np4 p2 || { stop_server; exit 3; }
stop_server; sleep 3

# --- arm np4b: a second server instance at np4, one pass (cross-instance)
start_server 4 np4b || exit 3
gen_eval np4b p1 || { stop_server; exit 3; }
stop_server

say "done $(date)"
say "adjudicate with: python3 \"docs/subprojects/i01-判分与基准有效性/audits/slot_repro_compare.py\""
