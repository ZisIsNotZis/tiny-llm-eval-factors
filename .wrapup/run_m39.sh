#!/bin/bash
# M39 (NEW QUEUE entry) — a SECOND ternary family: GLM-4.7-Flash-UD-TQ1_0.
#
# Tier 1C needs any second ternary/sub-2-bit family to turn the single Bonsai
# observation (Finding 8) into a class. ModelScope search
# (HubApi.list_repos(search=...)) found `unsloth/GLM-4.7-Flash-GGUF` ships
# GLM-4.7-Flash-UD-TQ1_0.gguf — a TQ2_0-family ternary (ggml type 35, inside build
# 4399's table) built by a different vendor for a different architecture family
# (GLM MoE, not Qwen/Bonsai). It pairs with the in-family on-curve reference
# GLM-4.7-Flash-UD-Q2_K_XL.gguf so the ternary residual can be read at ~matched
# bits/weight (TQ1_0 8.33 GB vs Q2_K_XL 11.89 GB for the same weights).
#
# Both files are load-gated: if TQ1_0 is not runnable on this llama.cpp build the
# panel is logged SKIP, not scored.
#
# Rows: m39_summary.jsonl = 2 models x 2 langs = 4.
#
# Must run under the GPU flock (the driver does this).
set -u
W=/home/z/hf/research/.wrapup
cd "$W"
LOG=$W/m39.log
SUM=$W/m39_summary.jsonl
export LOG
echo "=== M39 start $(date) ===" >> "$LOG"

# repo : file : tag
PANELS=(
  "unsloth/GLM-4.7-Flash-GGUF:GLM-4.7-Flash-UD-TQ1_0.gguf:glm47flash-tq1"
  "unsloth/GLM-4.7-Flash-GGUF:GLM-4.7-Flash-UD-Q2_K_XL.gguf:glm47flash-q2kxl"
)
for spec in "${PANELS[@]}"; do
  repo="${spec%%:*}"; rest="${spec#*:}"; file="${rest%%:*}"; tag="${rest##*:}"
  if ! bash "$W/resolve_model.sh" "$repo" "$file"; then
    echo "[M39] SKIP $tag: $repo/$file unavailable on ModelScope" >> "$LOG"; continue
  fi
  bash "$W/panel_mpl.sh" "$tag" "$file" "$SUM" "cpp py" \
    || echo "[M39] FAIL $tag" >> "$LOG"
done

echo "=== M39 end $(date) ===" >> "$LOG"
