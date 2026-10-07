#!/bin/bash
# m55_prebuild.sh — CPU/network preparation for the Tier-1A expert-wise / mixed-
# precision quantisation panel (m55) plus the two fetch-gated architecture-family
# panels (m58 Llama-3.2-3B, m59 Phi-4-mini).
#
# It touches NO GPU: it only downloads GGUFs (ModelScope), runs llama-quantize on
# the CPU, and load-gates every resulting GGUF with ONE real CPU completion
# (.wrapup/loadgate.jsonl). It therefore needs no /tmp/llama_gpu.lock and runs in
# parallel with the GPU queue (SSOT: a worker must not block on the lock).
#
# Outputs:
#   .wrapup/loadgate.jsonl   {"tag","file","load"} per verified GGUF
#   .wrapup/m55_recipes.json [{tag,file,recipe,base,expert_type,size_bytes,load}]
#   .wrapup/m55_prebuild.log
#
# Launch detached:
#   setsid nohup bash .wrapup/m55_prebuild.sh >>.wrapup/m55_prebuild.log 2>&1 &
set -u
W=/home/z/hf/research/.wrapup
LOG=$W/m55_prebuild.log
cd "$W"
echo "=== m55_prebuild start $(date) pid=$$ ===" >> "$LOG"

lg() { bash "$W/loadgate_cpu.sh" "$1" "${2:-$1}" >> "$LOG" 2>&1; }

# ---------------------------------------------------------------- phase A: gate
# the on-disk anchors of the cheap power panels (m56 LFM, m57 Nemotron, m60 Ornith)
# BEFORE the long downloads, so the runners can check the gate early.
for f in LFM2.5-8B-A1B-UD-Q2_K_XL.gguf LFM2.5-8B-A1B-UD-Q3_K_XL.gguf \
         NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL.gguf NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL.gguf \
         Ornith-1.5-9B-Q4_K_M.gguf Ornith-1.5-9B-Q5_K_M.gguf; do
  lg "$f"
done

# -------------------------------------------------- phase B: fetch new families
for spec in \
  "unsloth/Llama-3.2-3B-Instruct-GGUF:Llama-3.2-3B-Instruct-Q2_K.gguf" \
  "unsloth/Llama-3.2-3B-Instruct-GGUF:Llama-3.2-3B-Instruct-Q3_K_M.gguf" \
  "unsloth/Phi-4-mini-instruct-GGUF:Phi-4-mini-instruct-Q2_K.gguf" \
  "unsloth/Phi-4-mini-instruct-GGUF:Phi-4-mini-instruct-Q3_K_M.gguf"; do
  repo="${spec%%:*}"; file="${spec##*:}"
  bash "$W/resolve_model.sh" "$repo" "$file" >> "$LOG" 2>&1 || echo "[prebuild] SKIP $repo/$file" >> "$LOG"
  lg "$file"
done

# ------------------------------------------------- phase C: fetch the BF16 source
# LFM2.5-8B-A1B BF16 = 16.9 GB (8B total / 1B active MoE). This is the small MoE
# whose F16 source is affordable; 26B/35B F16 would be 50-70 GB and is SKIPped.
BF=/home/z/hf/LFM2.5-8B-A1B-BF16.gguf
if [ ! -e "$BF" ]; then
  bash "$W/resolve_model.sh" unsloth/LFM2.5-8B-A1B-GGUF LFM2.5-8B-A1B-BF16.gguf >> "$LOG" 2>&1 \
    || echo "[prebuild] SKIP LFM2.5-8B-A1B-BF16.gguf (unavailable)" >> "$LOG"
fi
if [ ! -e "$BF" ]; then
  echo "[prebuild] aborting m55 recipes: BF16 source unavailable $(date)" >> "$LOG"
  echo "=== m55_prebuild end (no BF16) $(date) ===" >> "$LOG"
  exit 0
fi
lg LFM2.5-8B-A1B-BF16.gguf lfm25-8a1b-bf16

# ------------------------------------------------ phase D: expert-wise recipes
# Experts live in blk.N.ffn_{gate,up,down}_exps.weight (verified from the shipped
# Q2 file: 66 expert tensors over 22 MoE layers). --tensor-type takes a REGEX
# (quantize.cpp -> std::regex_search on the tensor name), so one pattern covers all
# expert tensors while ffn_gate_inp (router) / attn / shortconv keep the base type.
EXRE='ffn_(gate|up|down)_exps'

dry() { # base [expert_type] -> quant size in MiB (empty on failure)
  local base="$1" et="${2:-}"
  if [ -n "$et" ]; then
    llama-quantize --dry-run --tensor-type "$EXRE=$et" "$BF" "$base" 2>&1
  else
    llama-quantize --dry-run "$BF" "$base" 2>&1
  fi | awk '/quant size/{print $5}' | tail -1
}

T=$(dry Q3_K_M); echo "[prebuild] uniform Q3_K_M target = ${T:-?} MiB" >> "$LOG"

best() { # side("ec"/"ed") candidates "base:et" ... ; echo "base:et:size" of closest to T
  local side="$1"; shift; local best="" bestd="" spec base et s d
  for spec in "$@"; do
    base="${spec%%:*}"; et="${spec##*:}"; [ "$et" = "$base" ] && et=""
    s=$(dry "$base" "$et"); [ -z "$s" ] && continue
    d=$(python3 -c "print(abs(float('$s')-float('$T')))" 2>/dev/null) || continue
    if [ -z "$bestd" ] || python3 -c "exit(0 if float('$d')<float('$bestd') else 1)"; then best="$base:$et"; bestd="$d"; fi
    echo "[prebuild]   cand $side base=$base et=${et:-none} size=$s MiB" >> "$LOG"
  done
  echo "$best"
}

EC=$(best ec  "Q4_K_M:Q2_K" "Q4_K_S:Q2_K" "Q5_K_S:Q2_K" "Q5_K_M:Q2_K")
ED=$(best ed  "Q2_K:Q4_K" "Q2_K:Q5_K" "Q3_K_S:Q5_K" "Q3_K_S:Q6_K")
[ -z "$EC" ] && EC="Q4_K_M:Q2_K"
[ -z "$ED" ] && ED="Q2_K:Q4_K"
echo "[prebuild] chosen experts-cheap=$EC experts-dear=$ED (target ${T:-?} MiB)" >> "$LOG"

quant() { # out base expert_type(optional)
  local out="$1" base="$2" et="${3:-}"
  if [ -n "$et" ]; then
    llama-quantize --tensor-type "$EXRE=$et" "$BF" "$out" "$base" 2>&1 | tail -4
  else
    llama-quantize "$BF" "$out" "$base" 2>&1 | tail -4
  fi
}

mkdir -p "$W"
REC=$W/m55_recipes.json
: > "$REC"
python3 - "$REC" <<'PY'
import json, sys
open(sys.argv[1], "w").close()
PY

add_recipe() { # tag outfile recipe base et
  local tag="$1" out="$2" recipe="$3" base="$4" et="$5"
  echo "[prebuild] quantize $tag base=$base expert=${et:-none} -> $out $(date)" >> "$LOG"
  quant "$out" "$base" "$et" >> "$LOG" 2>&1 || { echo "[prebuild] quantize FAIL $tag" >> "$LOG"; return 1; }
  [ -s "$out" ] || { echo "[prebuild] empty output $tag" >> "$LOG"; return 1; }
  lg "$(basename "$out")" "$tag"
  python3 - "$tag" "$(basename "$out")" "$recipe" "$base" "$et" "$REC" <<'PY'
import json, os, sys
tag, f, recipe, base, et, dest = sys.argv[1:7]
row = {"tag": tag, "file": f, "recipe": recipe, "base": base, "expert_type": et or "-",
       "size_bytes": os.path.getsize("/home/z/hf/"+f),
       "load": "PASS" if os.path.exists("/home/z/hf/"+f) else "FAIL"}
# carry the load-gate verdict recorded by loadgate_cpu.sh
try:
    for ln in open(dest.replace("m55_recipes.json", "loadgate.jsonl")):
        d = json.loads(ln)
        if d.get("file") == f:
            row["load"] = d.get("load", row["load"])
except FileNotFoundError:
    pass
with open(dest, "a") as fh:
    fh.write(json.dumps(row) + "\n")
PY
  echo "[prebuild] recipe $tag $(stat -c%s "$out" 2>/dev/null) bytes" >> "$LOG"
}

add_recipe lfm25-8a1b-m55-q3base /home/z/hf/LFM2.5-8B-A1B-m55-Q3_K_M.gguf uniform-Q3_K_M        Q3_K_M ""
add_recipe lfm25-8a1b-m55-exq2   /home/z/hf/LFM2.5-8B-A1B-m55-exq2.gguf    experts-cheap-rest-dear "${EC%%:*}" "${EC##*:}"
add_recipe lfm25-8a1b-m55-exq4   /home/z/hf/LFM2.5-8B-A1B-m55-exq4.gguf    experts-dear-rest-cheap "${ED%%:*}" "${ED##*:}"

echo "=== m55_prebuild end $(date) ===" >> "$LOG"
