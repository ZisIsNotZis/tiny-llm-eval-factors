#!/bin/bash
# T2 driver — run per-test-fraction instrumentation over all m1/m3 completion files.
set -u
cd /home/z/hf/research/.wrapup
mkdir -p tflogs
SUMMARY=/home/z/hf/research/.wrapup/testfrac_summary.jsonl
: > "$SUMMARY"
FILES=$(ls mres/m1-*.jsonl mres/m3-*.jsonl | grep -E '\-(cpp|java|js|py)\.jsonl$')
for f in $FILES; do
  base=$(basename "$f" .jsonl)
  lang=${base##*-}
  out="testfrac_${base}.jsonl"
  log="tflogs/${base}.log"
  if [ -s "$out" ]; then
    echo "skip $base (exists)" | tee -a "$log"
  else
    echo "=== $(date +%H:%M:%S) $base ($lang) ===" | tee -a "$log"
    python3 testfrac.py --lang "$lang" --samples "$f" --out "$out" --workers 5 >> "$log" 2>&1
  fi
  sum="testfrac_${base}_summary.jsonl"
  if [ -s "$sum" ]; then cat "$sum" >> "$SUMMARY"; fi
done
echo "ALL DONE $(date)" 
