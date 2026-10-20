#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# One lm-evaluation-harness panel, serialised on the GPU.
# Usage: .wrapup/lmeval_panel.sh <MODEL_PATH> <TAG> [limit]
#   limit omitted or 0 == full/complete suite (no --limit passed to lm_eval)
#
# NEVER blocks on the GPU lock: flock -n, and if another panel holds it we report and
# stop instead of hanging (SSOT 6b.5 / delegation protocol).  We never kill a
# llama-server we did not start; the runner only binds a port that `ss` proves free.
set -u
cd ${REPO_ROOT} || exit 2

MODEL="${1:?usage: lmeval_panel.sh <MODEL_PATH> <TAG> [limit]}"
TAG="${2:?usage: lmeval_panel.sh <MODEL_PATH> <TAG> [limit]}"
LIMIT="${3:-0}"

PY=${REPO_ROOT}/.wrapup/lmenv/bin/python
RUNNER=${REPO_ROOT}/.wrapup/lmeval_run.py
LLAMA_SERVER="${LLAMA_SERVER:-$(command -v llama-server || echo /home/z/.local/bin/llama-server)}"
OUT=${REPO_ROOT}/.wrapup/mres/$TAG
mkdir -p "$OUT" || exit 2

# Hold the flock on fd 9 for the whole run (same lock file as gpu_locked.sh).
exec 9>/tmp/llama_gpu.lock
if ! flock -n 9; then
  echo "ABORT $TAG: /tmp/llama_gpu.lock is held by another panel; not waiting." | tee -a "$OUT/panel.log"
  exit 3
fi

ARGS=(--model "$MODEL" --tag "$TAG" --llama-bin "$LLAMA_SERVER" --reasoning "${REASONING:-off}")
[ "$LIMIT" != "0" ] && ARGS+=(--limit "$LIMIT")
[ -n "${MMLU_LIMIT:-}" ] && ARGS+=(--mmlu-limit "$MMLU_LIMIT")
# TASKS lets a follow-up run touch only the tasks a variable can actually affect (e.g. the
# thinking-on comparison only needs the two generative tasks).
if [ -n "${TASKS:-}" ]; then
  # shellcheck disable=SC2206
  read -r -a _taskarr <<< "${TASKS//,/ }"
  ARGS+=(--tasks "${_taskarr[@]}")
fi

echo "=== lmeval_panel start tag=$TAG model=$MODEL limit=$LIMIT llama=$LLAMA_SERVER $(date -Is)" | tee -a "$OUT/panel.log"
"$PY" "$RUNNER" "${ARGS[@]}"
rc=$?
if [ $rc -ne 0 ]; then
  echo "=== lmeval_panel FAILED tag=$TAG rc=$rc $(date -Is)" | tee -a "$OUT/panel.log"
fi
exit $rc
