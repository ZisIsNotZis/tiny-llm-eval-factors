#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# M40 (QUEUE #14) — Ternary generalisation: third-party QUANTISERS of the ternary
# scheme, not just third-party models.
#
# Why: the off-curve ternary result currently rests on two observations — Bonsai
# (above its bits->score curve) and GLM-4.7-Flash TQ1_0 (below/half its own Q2
# reference). That is n=2, and both were built by unsloth/prism-ml. The most
# valuable open ternary question is whether the *residual* is a property of the
# ternary scheme or of one vendor's quantiser.
#
# ModelScope search (2026-10-06, HubApi.list_repos(repo_type='model', search=...))
# for "ternary"/"TQ1_0"/"TQ2_0" returns exactly one non-Bonsai cross-architecture
# ternary GGUF (unsloth GLM-4.7-Flash, already QUEUE #13) plus a family of
# Bonsai-derived builds from other vendors. The cleanest available manipulation is
# therefore the vendor quantiser on a fixed base model: dealignai's "CRACK" builds
# vs prism-ml's Q2_0/PQ2_0 for the same Bonsai weights. Both are load-gated: the
# gen-2 Prism layout uses ggml tensor type 142, which build 4399 rejects
# ("should be in [0, 43)", m34.log), so a SKIP here is itself a result.
#
# Rows: m40_summary.jsonl = (number of candidates that load) x 2 langs.
#
# Must run under the GPU flock (the driver does this).
set -u
W=${REPO_ROOT}/.wrapup
cd "$W"
LOG=$W/m40.log
SUM=$W/m40_summary.jsonl
export LOG
echo "=== M40 start $(date) ===" >> "$LOG"
: > "$SUM"   # rewrite from scratch (driver idempotency is row-count based)

# repo : file : tag
CANDS=(
  "dealignai/Bonsai-27b-Ternary-CRACK-GGUF:Bonsai-27b-Ternary-CRACK-Q2_0.gguf:crack-bonsai-27b-ternary"
  "dealignai/Bonsai-2-27B-Ternary-CRACK-GGUF:Bonsai-2-27B-PQ2_0-CRACK.gguf:crack-bonsai2-27b-pq2"
)
loaded=0
for spec in "${CANDS[@]}"; do
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M40] SKIP $tag: $repo/$file unavailable on ModelScope" >> "$LOG"; continue
  fi
  before=$(wc -l < "$SUM")
  if bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py"; then
    after=$(wc -l < "$SUM")
    if [ "$after" -gt "$before" ]; then
      loaded=$((loaded + 1))
      echo "[M40] used $repo/$file as tag=$tag (+$((after - before)) rows)" >> "$LOG"
      continue
    fi
  fi
  echo "[M40] $file resolved but failed the load gate -> next candidate" >> "$LOG"
done
echo "[M40] loadable ternary candidates: $loaded" >> "$LOG"

echo "=== M40 end $(date) ===" >> "$LOG"
