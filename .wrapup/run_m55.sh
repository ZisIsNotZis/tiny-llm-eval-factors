#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M55 (Tier 1A) — expert-wise / mixed-precision quantisation, the one big untested
# axis (BRAINSTORM 1A). The quantisation itself is done CPU-side by
# m55_prebuild.sh (llama-quantize --tensor-type overrides on the 16.9 GB BF16
# LFM2.5-8B-A1B MoE); this runner only spends GPU time on recipes that already
# passed a CPU load gate (one real completion), then runs the standard panel.
#
# Recipes (all ~the same total byte budget as uniform Q3_K_M):
#   uniform-Q3_K_M        baseline built with the SAME toolchain as the mixes
#   experts-cheap         base ~Q4_K + blk.N.ffn_{gate,up,down}_exps=Q2_K
#   experts-dear          base ~Q2_K + blk.N.ffn_{gate,up,down}_exps=Q4_K
# Comparing these three at matched size isolates WHERE the bits are spent
# (expert tensors vs attention/shortconv/dense) from HOW MANY bits there are.
#
# Rows: m55_summary.jsonl = up to 3 recipes x {cpp, py} = 6.
# Protocol mpl-raw-greedy-768-expertwise (raw completion, greedy, ctx 4096).
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m55.log
SUM=$W/m55_summary.jsonl
REC=$W/m55_recipes.json
export LOG
echo "=== M55 start $(date) ===" >> "$LOG"
: > "$SUM"

if [ ! -s "$REC" ]; then
  echo "[M55] SKIP: $REC not built yet (m55_prebuild.sh still running)" >> "$LOG"
  echo "=== M55 end $(date) ===" >> "$LOG"
  exit 0
fi

JOBS=$W/m55_jobs.txt
python3 - "$REC" "$JOBS" <<'PY'
import json, sys
rec, out = sys.argv[1], sys.argv[2]
n = 0
with open(out, "w") as fh:
    for ln in open(rec):
        ln = ln.strip()
        if not ln:
            continue
        d = json.loads(ln)
        if d.get("load") == "PASS":
            fh.write("%s\t%s\t%s\n" % (d["tag"], d["file"], d["recipe"])); n += 1
print("jobs", n)
PY
if [ ! -s "$JOBS" ]; then
  echo "[M55] SKIP: no recipe passed the load gate" >> "$LOG"
  echo "=== M55 end $(date) ===" >> "$LOG"
  exit 0
fi

while IFS=$'\t' read -r tag file recipe; do
  [ -e "/home/z/hf/$file" ] || { echo "[M55] SKIP $tag: $file missing" >> "$LOG"; continue; }
  echo "[M55] recipe $tag ($recipe)" >> "$LOG"
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" "mpl-raw-greedy-768-expertwise" \
    || echo "[M55] FAIL $tag" >> "$LOG"
done < "$JOBS"
echo "=== M55 end $(date) ===" >> "$LOG"
