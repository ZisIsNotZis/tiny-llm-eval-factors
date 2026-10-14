#!/bin/bash
# axes_finisher.sh -- detached watcher that, after every campaign milestone, ingests the
# new AXES rows and recomputes the three-axis readout into .wrapup/AXES_RESULTS.md.
# Needed because the long GPU campaign outlives any single subagent session.
set -u
cd /home/z/hf/research || exit 2
WR=.wrapup
OUT="$WR/AXES_RESULTS.md"
LOG="$WR/axes_finisher.log"
TAGS="m140-qat-gemma12b-q4 m141-native-gemma12b-q4 m144-qat-gemma26b-a4b-q4 m146-qat-gemma-e2b-q2 m147-qat-gemma-e2b-q4 m148-native-gemma-e2b-q4 m149-qat-gemma-e4b-q2 m155-qat-gemma-e4b-q4 m156-native-gemma-e4b-q4 m150-qwen38-gsqrco-iq3xxs m151-qwen38-gsqrco-iq3s m152-qwen38-27b-iq4xs"
log(){ echo "[$(date -Is)] $*" >> "$LOG"; }
done_count(){ n=0; for t in $TAGS; do [ -f "$WR/mres/$t/DONE" ] && [ -f "$WR/mres/$t/code.DONE" ] && n=$((n+1)); done; echo $n; }
log "finisher start (12 target tags)"
while :; do
  python3 migrate_db.py >>"$LOG" 2>&1
  {
    echo "# AXES results (auto-updated $(date -Is))"
    echo
    echo "complete tags: $(done_count)/12"
    echo
    echo "## axes_findings.py"
    python3 "$WR/axes_findings.py" 2>&1
    echo
    echo "## axes_analysis.py"
    python3 "$WR/axes_analysis.py" 2>&1
  } > "$OUT" 2>>"$LOG"
  c=$(done_count)
  log "results updated complete=$c/12"
  [ "$c" -ge 12 ] && { log "all 12 complete -> finisher exit"; break; }
  sleep 600
done
