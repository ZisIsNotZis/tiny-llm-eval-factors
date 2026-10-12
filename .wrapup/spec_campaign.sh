#!/bin/bash
# Drain SPECCAMPAIGN.txt: one MTP model at a time, drafts 0,1,2,4, under the GPU lock.
set -u
cd /home/z/hf/research || exit 2
WR=/home/z/hf/research/.wrapup
LMEVAL_PY="$WR/lmenv/bin/python"
LOG="$WR/spec_campaign.log"
exec 7>/tmp/spec_campaign_driver.lock
flock -n 7 || { echo "another spec driver holds the lock"; exit 0; }
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|\#*) continue;; esac
  set -- $line
  model="$1"; tag="$2"
  # the manifest uses a glob for the snapshot dir; expand it
  model=$(ls $model 2>/dev/null | head -1)
  [ -n "$model" ] || { echo "[$(date -Is)] SKIP $tag (no model)" >> "$LOG"; continue; }
  [ -f "$WR/mres/$tag/DONE" ] && { echo "[$(date -Is)] SKIP $tag (DONE)" >> "$LOG"; continue; }
  echo "[$(date -Is)] START $tag $model" >> "$LOG"
  "$LMEVAL_PY" "$WR/spec_panel.py" --model "$model" --tag "$tag" \
      --drafts 0,1,2,4 --limit 50 --tasks mmlu,gsm8k,ifeval >> "$WR/spec_campaign.out" 2>&1
  rc=$?
  [ -f "$WR/mres/$tag/DONE" ] && echo "[$(date -Is)] DONE $tag rc=$rc" >> "$LOG" \
                              || echo "[$(date -Is)] FAIL $tag rc=$rc" >> "$LOG"
done < "$WR/SPECCAMPAIGN.txt"
echo "[$(date -Is)] === spec campaign end ===" >> "$LOG"
