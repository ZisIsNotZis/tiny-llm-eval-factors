#!/bin/bash
# Watches the campaign: relaunches campaign.sh whenever it is not running and there is
# still un-done work in CAMPAIGN.txt.
#
# Why this exists: pi's scheduled-subagent path is broken on this host (async children fail
# with "Background children require the host npm package ... pi-agent-core/node"), so the
# "cron job re-arms the queue" pattern from SSOT 6b cannot be used. A plain detached shell
# loop is the reliable substitute.
#
# Liveness is judged ONLY by a process test on the driver plus the DONE banners -- never by
# `pgrep -f "<script name>"` matching a stray shell (SSOT 6b rule 5). The pgrep pattern is
# anchored to the exact driver path and excludes this keeper's own PID.
set -u
cd /home/z/hf/research || exit 2

WR=/home/z/hf/research/.wrapup
CAMP="$WR/CAMPAIGN.txt"
DRIVER="$WR/campaign.sh"
LOG="$WR/keeper.log"

log() { echo "[$(date -Is)] $*" >> "$LOG"; }

pending() {  # count lines whose two DONE banners are not both present
  local n=0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"
    # shellcheck disable=SC2086
    set -- $line
    [ "$#" -lt 2 ] && continue
    if [ ! -f "$WR/mres/$2/DONE" ] || [ ! -f "$WR/mres/$2/code.DONE" ]; then
      n=$((n + 1))
    fi
  done < "$CAMP"
  echo "$n"
}

driver_running() {
  # exact-path match, own PID excluded
  local me=$$
  for p in $(pgrep -f -- "$DRIVER" 2>/dev/null); do
    [ "$p" = "$me" ] && continue
    return 0
  done
  # also catch a panel currently holding the GPU on the campaign's behalf
  if ! flock -n /tmp/llama_gpu.lock true 2>/dev/null; then
    return 0
  fi
  return 1
}

log "=== keeper start $(date -Is) ==="
idle=0
while :; do
  left=$(pending)
  if [ "$left" -eq 0 ]; then
    log "ALL DONE ($left pending); keeper exiting"
    break
  fi
  if driver_running; then
    idle=0
  else
    idle=$((idle + 1))
    log "driver not running, $left pending -> relaunch (idle streak $idle)"
    setsid nohup "$DRIVER" > "$WR/campaign.out" 2>&1 < /dev/null &
    sleep 60
  fi
  sleep 300
done
