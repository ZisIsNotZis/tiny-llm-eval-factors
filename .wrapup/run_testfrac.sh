#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# T2 driver — run per-test-fraction instrumentation over all m1/m3 completion files.
set -u
cd ${REPO_ROOT}/.wrapup
mkdir -p tflogs
SUMMARY=${REPO_ROOT}/.wrapup/testfrac_summary.jsonl
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
