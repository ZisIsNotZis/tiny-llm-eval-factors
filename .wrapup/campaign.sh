#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# Campaign driver: drain .wrapup/CAMPAIGN.txt, one model at a time.
#
# For every not-yet-done line `<abs_gguf_path> <tag> <limit>` it runs
#   .wrapup/lmeval_panel.sh <model> <tag> <limit>     (5 standard benchmarks)
#   .wrapup/codepanel.sh   <model> <tag> <limit>     (EvalPlus HumanEval+ / MBPP+)
# and records a one-line status in .wrapup/campaign.log after each stage.
#
# A model counts as done only when BOTH `.wrapup/mres/<tag>/DONE` (lmeval panel) and
# `.wrapup/mres/<tag>/code.DONE` (code panel) exist.  Re-running the driver is safe:
# completed stages are skipped from their DONE banner.
#
# The GPU lock (/tmp/llama_gpu.lock) is never waited on indefinitely: the driver first
# checks the lock with `flock -n`; while it is held it sleeps LOCK_SLEEP seconds and
# retries, up to MAX_LOCK_TRIES times, then logs the give-up and moves on to the next
# line (the panels themselves also take the lock with `flock -n` and exit 3 if held).
#
# Env overrides (for testing): CAMPAIGN_FILE, LOCK_SLEEP, MAX_LOCK_TRIES.
set -u
cd ${REPO_ROOT} || exit 2

WR=${REPO_ROOT}/.wrapup
CAMP="${CAMPAIGN_FILE:-$WR/CAMPAIGN.txt}"
LOG="$WR/campaign.log"
LMEVAL="$WR/lmeval_panel.sh"
CODE="$WR/codepanel.sh"
LOCK=/tmp/llama_gpu.lock
LOCK_SLEEP="${LOCK_SLEEP:-30}"
MAX_LOCK_TRIES="${MAX_LOCK_TRIES:-10}"

[ -f "$CAMP" ] || { echo "campaign: missing $CAMP" >&2; exit 2; }

# The driver holds its own lock for its whole lifetime.  This is the ONLY legitimate
# liveness proof (SSOT 6b rule 5) and it makes pausing safe: kill the driver, wait for
# the in-flight panel to finish, edit the queue, and the keeper will relaunch it.
exec 7>/tmp/campaign_driver.lock
if ! flock -n 7; then
  echo "campaign: another driver already holds /tmp/campaign_driver.lock; exiting" >&2
  exit 0
fi

log() { echo "[$(date -Is)] $*" >> "$LOG"; }
lock_free() { flock -n "$LOCK" true 2>/dev/null; }

# run one panel stage, retrying only while the lock is held.  Returns the panel rc, or 4
# if the lock stayed held through MAX_LOCK_TRIES attempts (caller then moves on).
run_stage() {  # <stage> <script> <model> <tag> <limit> [mmlu_limit] [reasoning] [tasks]
  local name="$1" script="$2" model="$3" tag="$4" limit="$5"
  local mmlu="${6:-}" reason="${7:-off}" tasks="${8:-}"
  local tries=0 rc t0 t1
  while :; do
    if ! lock_free; then
      tries=$((tries + 1))
      if [ "$tries" -gt "$MAX_LOCK_TRIES" ]; then
        log "GIVEUP $name $tag: lock held after $MAX_LOCK_TRIES tries; moving on"
        return 4
      fi
      log "WAIT $name $tag: lock held (try $tries/$MAX_LOCK_TRIES); sleeping ${LOCK_SLEEP}s"
      sleep "$LOCK_SLEEP"
      continue
    fi
    t0=$(date +%s)
    # 7>&- : panels must NOT inherit the driver's lifetime lock, otherwise killing the driver
    # leaves the lock held by an orphaned panel and the keeper can never restart the queue.
    MMLU_LIMIT="$mmlu" REASONING="$reason" TASKS="$tasks" "$script" "$model" "$tag" "$limit" 7>&-
    rc=$?
    t1=$(date +%s)
    if [ "$rc" -eq 3 ]; then
      tries=$((tries + 1))
      if [ "$tries" -gt "$MAX_LOCK_TRIES" ]; then
        log "GIVEUP $name $tag: panel reported lock held after $MAX_LOCK_TRIES tries; moving on"
        return 4
      fi
      log "WAIT $name $tag: panel reported lock held (try $tries/$MAX_LOCK_TRIES); sleeping ${LOCK_SLEEP}s"
      sleep "$LOCK_SLEEP"
      continue
    fi
    log "STAGE $name $tag rc=$rc wall=$((t1 - t0))s"
    return "$rc"
  done
}

n_done=0; n_skip=0; n_fail=0
log "=== campaign start file=$CAMP $(date -Is) ==="
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%%#*}"
  # shellcheck disable=SC2086
  set -- $line
  [ "$#" -lt 2 ] && continue
  model="$1"; tag="$2"; limit="${3:-20}"; mmlu="${4:-}"; reason="${5:-off}"; tasks="${6:-}"
  out="$WR/mres/$tag"

  if [ -f "$out/DONE" ] && [ -f "$out/code.DONE" ]; then
    n_skip=$((n_skip + 1))
    log "SKIP $tag (both DONE banners present)"
    continue
  fi
  # A task-restricted entry is a partial re-run of a variable probe (e.g. the thinking-on
  # comparison only touches the generative tasks); it has no code half to run.
  partial=0
  [ -n "$tasks" ] && partial=1
  if [ "$partial" -eq 1 ] && [ -f "$out/DONE" ]; then
    n_skip=$((n_skip + 1))
    log "SKIP $tag (partial re-run, DONE present)"
    continue
  fi
  mkdir -p "$out"

  if [ -f "$out/DONE" ]; then
    log "SKIP lmeval $tag (DONE present)"
  else
    run_stage lmeval "$LMEVAL" "$model" "$tag" "$limit" "$mmlu" "$reason" "$tasks"; rc=$?
    if [ "$rc" -eq 4 ]; then log "GIVEUP lmeval $tag (lock held); next model"; continue; fi
    if [ -f "$out/DONE" ]; then log "OK lmeval $tag (rc=$rc)"; else n_fail=$((n_fail + 1)); log "FAIL lmeval $tag (rc=$rc, no DONE)"; fi
  fi

  if [ "$partial" -eq 1 ]; then
    log "PARTIAL $tag (tasks=$tasks); code stage not applicable"
  elif [ -f "$out/code.DONE" ]; then
    log "SKIP code $tag (code.DONE present)"
  else
    run_stage code "$CODE" "$model" "$tag" "$limit"; rc=$?
    if [ "$rc" -eq 4 ]; then log "GIVEUP code $tag (lock held); next model"; continue; fi
    if [ -f "$out/code.DONE" ]; then log "OK code $tag (rc=$rc)"; else n_fail=$((n_fail + 1)); log "FAIL code $tag (rc=$rc, no code.DONE)"; fi
  fi

  if [ "$partial" -eq 1 ]; then
    if [ -f "$out/DONE" ]; then n_done=$((n_done + 1)); log "MODEL DONE $tag (partial)"; else log "MODEL INCOMPLETE $tag (partial)"; fi
  elif [ -f "$out/DONE" ] && [ -f "$out/code.DONE" ]; then
    n_done=$((n_done + 1))
    log "MODEL DONE $tag"
  else
    log "MODEL INCOMPLETE $tag (lmeval=$([ -f "$out/DONE" ] && echo done || echo no) code=$([ -f "$out/code.DONE" ] && echo done || echo no))"
  fi
done < "$CAMP"
log "=== campaign end done=$n_done skipped_complete=$n_skip failed_stages=$n_fail $(date -Is) ==="
