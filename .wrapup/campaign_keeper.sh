#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
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
cd ${REPO_ROOT} || exit 2

WR=${REPO_ROOT}/.wrapup
CAMP="$WR/CAMPAIGN.txt"
DRIVER="$WR/campaign.sh"
LOG="$WR/keeper.log"

log() { echo "[$(date -Is)] $*" >> "$LOG"; }

# single instance: a second keeper would race the first into launching two drivers, and
# although panels are serialised by the GPU lock that only wastes hours of GPU time.
exec 8>"$WR/.keeper.lock"
if ! flock -n 8; then
  log "another keeper already holds the lock; exiting"
  exit 0
fi

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
  # SSOT 6b rule 5: liveness is proved by a lock, never by matching a process name.
  # The driver holds /tmp/campaign_driver.lock for its whole lifetime; a panel holding the
  # GPU lock is the second, independent proof that work is in flight.
  if ! flock -n /tmp/campaign_driver.lock true 2>/dev/null; then
    return 0
  fi
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
    # 8>&- so the driver does NOT inherit the keeper's single-instance lock: otherwise
    # killing the keeper would leave the lock held by a surviving driver process.
    setsid nohup "$DRIVER" > "$WR/campaign.out" 2>&1 < /dev/null 8>&- &
    sleep 60
  fi
  sleep 300
done
