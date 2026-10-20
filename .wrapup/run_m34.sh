#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M34 (QUEUE #8) — a third-party ternary / 1-bit family: does the off-curve ternary
# result generalise beyond the original Ternary-Bonsai-27B (Finding 8)?
#
# QUEUE #8 named "TernaryQuench-Qwen3.8-27B". A ModelScope repo search
# (HubApi.list_repos(search=...)) found NO repo matching "TernaryQuench" or "quench"
# on 2026-10-06, so the exact named checkpoint is unavailable; per the queue rule
# ("if a whole family is unavailable, log SKIP and continue") the script first
# probes the named repo ids and then falls back to the closest available
# third-party ternary/1-bit family it can actually resolve:
#   * Ternary-Bonsai-2-27B (prism-ml, gen-2, Qwen3.8 core) PTQ1_0 (1-bit) or PQ2_0
#   * the original Ternary-Bonsai-27B family is excluded here — it is already in the DB
# Every candidate is behind the real-completion load gate: PTQ1_0/PQ2_0 use newer ggml
# tensor types (BACKLOG B1a: type 142 is beyond build 4399's table), so an unsupported
# file fails the gate and is logged SKIP rather than silently scored.
#
# Rows: m34_summary.jsonl = 1 model x 2 langs = 2 (whichever candidate loads).
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m34.log
SUM=$W/m34_summary.jsonl
export LOG
echo "=== M34 start $(date) ===" >> "$LOG"

# repo : file : tag  (first candidate that resolves AND loads wins)
CANDS=(
  "TernaryQuench/TernaryQuench-Qwen3.8-27B-GGUF:TernaryQuench-Qwen3.8-27B-PQ2_0.gguf:ternaryq-38-27b"
  "TernaryQuench/TernaryQuench-Qwen3.8-27B:TernaryQuench-Qwen3.8-27B-Q2_0.gguf:ternaryq-38-27b"
  "prism-ml/Ternary-Bonsai-2-27B-gguf:Ternary-Bonsai-2-27B-PTQ1_0.gguf:bonsai2-27b-1bit"
  "prism-ml/Ternary-Bonsai-2-27B-gguf:Ternary-Bonsai-2-27B-PQ2_0.gguf:bonsai2-27b-ternary"
)
done_any=0
for spec in "${CANDS[@]}"; do
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M34] SKIP $file: unavailable on ModelScope" >> "$LOG"; continue
  fi
  if bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py"; then
    done_any=1
    echo "[M34] used $repo/$file as tag=$tag" >> "$LOG"
    break
  fi
  echo "[M34] $file resolved but failed the load gate -> trying next candidate" >> "$LOG"
done
[ "$done_any" -eq 1 ] || echo "[M34] SKIP: no third-party ternary/1-bit candidate loaded" >> "$LOG"

echo "=== M34 end $(date) ===" >> "$LOG"
