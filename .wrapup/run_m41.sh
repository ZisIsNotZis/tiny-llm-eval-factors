#!/bin/bash
# M41 (QUEUE #15) — T2 partial-credit metric for the ternary-vs-conventional
# comparison: does a ternary model fail FEWER tests or just DIFFERENT ones?
#
# The binary MultiPL-E pass@1 flattens "compiles but 1/7 asserts fail" and
# "does not compile" to the same 0. testfrac.py (the T2 instrumentation) scores
# each item by the fraction of its provided unit tests that pass, reusing the
# exact compile/run path of mpl_run.py. m29 showed the ternary cells can score
# the same pass@1 while differing in per-item behaviour; this quantifies it.
#
# CPU-only (compile + run per item; no llama-server, no GPU work). It runs over
# the completions already on disk, so it costs 0 GPU-hours. Re-running is
# idempotent per file (a completed testfrac_<base>_summary.jsonl is reused) and
# the aggregate m41_summary.jsonl is rebuilt from scratch each time.
#
# Rows: m41_summary.jsonl = one row per (completion file) scored.
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m41.log
SUM=$W/m41_summary.jsonl
PY=python3
mkdir -p tflogs
echo "=== M41 start $(date) ===" >> "$LOG"
: > "$SUM"

# Ternary (and 1-bit) arm samples, plus their in-family conventional references.
GLOBS=(
  mres/m21-bonsai-q2g64-*.jsonl
  mres/mt1-bonsai17b-g64-*.jsonl
  mres/mt1-bonsai8b-g64-*.jsonl
  mres/pan-bonsai27b-1bit-*.jsonl
  mres/pan-bonsai4b-ternary-*.jsonl
  mres/pan-qwen35-35a3b-iq1m-*.jsonl
  mres/pan-glm47flash-tq1-*.jsonl
  mres/pan-glm47flash-q2kxl-*.jsonl
  mres/pan-glm47flash-q3-*.jsonl
  mres/m3-q2-*.jsonl
  mres/m3-q3-*.jsonl
)
FILES=$(ls ${GLOBS[@]} 2>/dev/null | grep -E '\-(cpp|java|js|py)\.jsonl$' | grep -v _eval | sort -u)
[ -n "$FILES" ] || { echo "[M41] SKIP: no target completion files found" >> "$LOG"; exit 0; }

for f in $FILES; do
  base=$(basename "$f" .jsonl)
  lang=${base##*-}
  sum="testfrac_${base}_summary.jsonl"
  if [ ! -s "$sum" ]; then
    echo "[M41] score $base ($lang) $(date +%H:%M:%S)" >> "$LOG"
    timeout 3600 $PY testfrac.py --lang "$lang" --samples "$f" \
      --out "testfrac_${base}.jsonl" --workers 5 >> "$LOG" 2>&1 \
      || echo "[M41] testfrac FAILED $base" >> "$LOG"
  fi
  [ -s "$sum" ] || { echo "[M41] no summary for $base" >> "$LOG"; continue; }
  kind=conventional
  case "$base" in *tq1*|*ternary*|*bonsai*|*g64*|*1bit*|*iq1*) kind=ternary;; esac
  $PY - "$sum" "$base" "$kind" "$SUM" <<'PY' >> "$LOG" 2>&1
import json, sys
sm, base, kind, dest = sys.argv[1:5]
d = json.load(open(sm))
d.update({"file": base, "arm": kind})
with open(dest, "a") as fo:
    fo.write(json.dumps(d) + "\n")
print("recorded", base, kind, round(d.get("mean_frac", -1), 4))
PY
done

echo "=== M41 end $(date) rows=$(wc -l < "$SUM") ===" >> "$LOG"
