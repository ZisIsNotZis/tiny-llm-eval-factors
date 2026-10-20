#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M53 (NEXT_DRIVER N4) — BRAINSTORM 1C / task hint: hunt more ternary / sub-2-bit
# families that are NOT already on disk, then load-gate and measure the ones that
# resolve. Two stages, never stops:
#   (1) SEARCH: best-effort ModelScope query for ternary / TQ1_0 / Q2_0 / IQ1 / 1-bit
#       GGUFs; the candidate list is logged to m53_search.log (evidence of the sweep).
#   (2) PROBE: for up to 2 candidates not already symlinked into /home/z/hf, resolve
#       (download-gated via resolve_model.sh) and run the frozen MultiPL-E panel; a
#       candidate that 404s, will not download, or fails the load gate is logged SKIP.
# Rows: m53_summary.jsonl = 2 langs per probed model (0 rows if nothing new resolves).
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m53.log
SUM=$W/m53_summary.jsonl
SEARCH=$W/m53_search.log
MS=${REPO_ROOT}/.wrapup/msenv/bin/python
echo "=== M53 start $(date) ===" >> "$LOG"
: > "$SUM"; : > "$SEARCH"

# --- (1) best-effort ModelScope search -------------------------------------------
for q in ternary TQ1_0 Q2_0 IQ1 ; do
  curl -s --max-time 25 \
    "https://modelscope.cn/api/v1/dolphin/models?PageSize=30&PageNumber=1&Query=$q" 2>/dev/null \
    | "$MS" -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
models=(((d.get('Data') or {}).get('Model') or {}).get('Models') or [])
for m in models:
    p=(m.get('Path') or '')+'/'+(m.get('Name') or '')
    if p.strip('/'): print('$q', p)
" >> "$SEARCH" 2>>"$LOG" || true
done
echo "[M53] search hits: $(wc -l < "$SEARCH")" >> "$LOG"

# --- (2) probe curated candidates (repo:file:tag), load-gated --------------------
CANDS=(
  "dealignai/Ternary-Bonsai-27B-CRACK-GGUF:Ternary-Bonsai-27B-CRACK-Q2_0.gguf:bonsai27b-crack"
  "dealignai/Ternary-Bonsai-2-27B-CRACK-GGUF:Ternary-Bonsai-2-27B-CRACK-PQ2_0.gguf:bonsai2-27b-crack"
)
probed=0
for spec in "${CANDS[@]}"; do
  [ "$probed" -ge 2 ] && break
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if [ -e "/home/z/hf/$file" ]; then
    echo "[M53] $tag already present, probing" >> "$LOG"
  elif ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M53] SKIP $tag: $repo/$file not resolvable" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" \
    "mpl-raw-greedy-768-third-party-ternary" \
    || echo "[M53] FAIL $tag (load gate / panel)" >> "$LOG"
  probed=$((probed+1))
done
[ "$probed" -eq 0 ] && echo "[M53] SKIP: no new ternary/1-bit family resolved" >> "$LOG"
echo "=== M53 end $(date) ===" >> "$LOG"
