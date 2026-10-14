#!/bin/bash
# One-shot retry daemon for the AXES campaign (guidance step 3).
# Waits for the CURRENT campaign.sh (pid arg) to finish, then re-arms campaign.sh exactly
# ONCE (idempotent: DONE-banner models are skipped).  Used so the single allowed retry pass
# for the VRAM-blocked tags (m142/m143/m145) fires reliably in case the foreign :8834
# server has exited.  Writes /tmp/axes_retry_done when finished.
set -u
cd /home/z/hf/research || exit 2
DRIVER_PID="${1:-3850304}"
LOG=.wrapup/axes_retry.log
ended() { awk '/=== campaign start/{s=0} /=== campaign end/{s=1} END{exit !s}' .wrapup/campaign.log; }
echo "[$(date -Is)] retry-daemon armed; waiting for driver pid $DRIVER_PID + campaign end" >> "$LOG"
while ! ended; do sleep 30; done
while kill -0 "$DRIVER_PID" 2>/dev/null; do sleep 10; done
sleep 10
echo "[$(date -Is)] campaign ended, driver gone -> re-arming campaign.sh (retry pass)" >> "$LOG"
CAMPAIGN_FILE=.wrapup/AXES_CAMPAIGN.txt LOCK_SLEEP=30 MAX_LOCK_TRIES=4 \
  bash .wrapup/campaign.sh >> .wrapup/axes_retry.out 2>&1
echo "[$(date -Is)] retry pass finished rc=$?" >> "$LOG"
touch /tmp/axes_retry_done
