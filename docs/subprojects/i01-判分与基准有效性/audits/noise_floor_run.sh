#!/bin/bash
# i01 WP7 — chat single-run noise floor: repeat ONE cell twice under identical
# configuration and count per-problem verdict flips.
#
# What this measures, and what it does not:
#   * it measures the floor for a cell whose INPUTS are pinned (same prompt set, same
#     postprocess, same model file, same server flags, greedy) -- that is pure
#     run-to-run noise of the harness;
#   * it does NOT measure plan15's +/-16/161 class, which came from an input change
#     (different prompt set / postprocess version).  The two must never be added
#     together; RESULT.md::res29 is the input-difference number and this is the
#     repeatability number.
#
# Two families are exercised here because the other two already have repeats on disk:
#   * lm-eval gsm8k (chat, reasoning off, --limit 100) x2, with --log_samples so the
#     flips can be counted per problem (the production runner does not log samples,
#     which is itself one of the audit findings in audits/lmeval.md);
#   * BFCL single-turn simple_python (native tools, --limit 40) x2, comparing the
#     predicted calls per item.
# MultiPL-E is covered by i01-slot-np1-p{1,2} and i01-slot-npauto-p{1,2} (4 passes,
# byte-identical) and EvalPlus by the stored temp=0 repeats (w1-repeat).
#
# VRAM gate: this cell uses the 2B model, not the 27B one.  Weights are 1,106 MiB
# (measured file size) and the KV/compute overhead is the same shape as the 27B
# config (3,084 MiB at 4 slots x 2048 ctx, measured), so the requirement is about
# 1,106 + ~1,500 + 1,536 = ~4.1 GiB; the gate below is 6,144 MiB.
#
# Run:  bash .wrapup/gpu_locked.sh bash "docs/subprojects/i01-判分与基准有效性/audits/noise_floor_run.sh"
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
cd "$REPO" || exit 1

MODEL=${MODEL:-/home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf}
PORT=${PORT:-8089}
BASE=http://127.0.0.1:$PORT
CTX=${CTX:-8192}
MIN_FREE_MIB=${MIN_FREE_MIB:-6144}
LOG=$REPO/.wrapup/i01_noise_floor.log
OUT=$REPO/.wrapup/mres/i01-floor
# `.wrapup/lmenv/bin/lm_eval` has a shebang pointing at the retired root
# /home/z/hf/research (i02 plan10 class), so it exits 127; go through the venv
# interpreter and `-m lm_eval` instead of repairing a shared console script here.
LMENV_PY=$REPO/.wrapup/lmenv/bin/python
say() { echo "[i01-floor] $*" | tee -a "$LOG"; }
mkdir -p "$OUT"

free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
say "start $(date +%H:%M:%S) model=$MODEL free=${free}MiB gate=${MIN_FREE_MIB}MiB ctx=$CTX"
[ "${free:-0}" -ge "$MIN_FREE_MIB" ] || { say "ABORT: free VRAM ${free}MiB < ${MIN_FREE_MIB}MiB"; exit 4; }

srv=""
stop_server() { [ -n "$srv" ] && { kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""; }; }
trap stop_server EXIT INT TERM

# The same server flags the panel runner uses for a chat task (`--reasoning off`).
# Without it an instruct model spends the generation budget inside reasoning_content and
# the scored `content` comes back empty: the first i01 run omitted the flag and every
# gsm8k response was ``[invalid]`` -- repeatable, but not the production cell.
llama-server -m "$MODEL" --port "$PORT" --host 127.0.0.1 -ngl 99 -c "$CTX" \
  --cache-type-k q8_0 --cache-type-v q8_0 --jinja --reasoning off \
  --top-p 0.95 --top-k 40 --min-p 0.05 >> "$LOG" 2>&1 &
srv=$!
for _ in $(seq 1 120); do
  kill -0 "$srv" 2>/dev/null || { say "ABORT: server died"; exit 3; }
  curl -s --max-time 3 "$BASE/health" 2>/dev/null | grep -q '"status":"ok"' && break
  sleep 2
done
say "server up: $(grep -o 'n_slots = [0-9]*, n_ctx_slot = [0-9]*' "$LOG" | tail -1)"

ONLY=${ONLY:-gsm8k,bfcl}
for rep in 1 2; do
  case ",$ONLY," in *,gsm8k,*) ;; *) continue ;; esac
  d=$OUT/gsm8k-r$rep
  mkdir -p "$d"
  say "lm-eval gsm8k rep=$rep start $(date +%H:%M:%S)"
  timeout 1800 "$LMENV_PY" -m lm_eval --model local-chat-completions \
    --model_args "base_url=$BASE/v1/chat/completions" \
    --tasks gsm8k --apply_chat_template \
    --gen_kwargs "temperature=0,max_gen_toks=1024" \
    --limit 100 --log_samples --output_path "$d/lmeval_gsm8k.json" >> "$LOG" 2>&1
  say "lm-eval gsm8k rep=$rep rc=$? end $(date +%H:%M:%S)"
done

for rep in 1 2; do
  case ",$ONLY," in *,bfcl,*) ;; *) continue ;; esac
  say "bfcl simple_python rep=$rep start $(date +%H:%M:%S)"
  timeout 1200 python3 .wrapup/bfcl_run.py gen --categories simple_python --mode tools \
    --limit 40 --samples "$OUT/bfcl-r$rep.jsonl" --base_url "$BASE" \
    --max_tokens 512 >> "$LOG" 2>&1
  rc=$?
  timeout 600 python3 .wrapup/bfcl_run.py eval --samples "$OUT/bfcl-r$rep.jsonl" \
    --out "$OUT/bfcl-r$rep-eval.json" >> "$LOG" 2>&1
  say "bfcl simple_python rep=$rep gen_rc=$rc eval_rc=$? end $(date +%H:%M:%S)"
done

stop_server
say "done $(date +%H:%M:%S)"
say "compare: python3 \"docs/subprojects/i01-判分与基准有效性/audits/noise_floor_compare.py\""
