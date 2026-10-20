#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# T1 PPL ladder sweep. Every GPU call goes through gpu_locked.sh (flock serialisation).
# Fixed flags across all points: -c 2048 --chunks 40 -ngl 99 -ctk q8_0 -ctv q8_0.
cd ${REPO_ROOT} || exit 1
PP=/home/z/llama.cpp/build/bin/llama-perplexity
OUT=.wrapup/ppl_summary.jsonl
LOGDIR=.wrapup/ppl_logs
mkdir -p "$LOGDIR"
: > "$OUT"

C=(code_python code_multi nl_english)

run() {  # model quant file
  local model="$1" quant="$2" file="$3" corpus="$4"
  local tag="${model}__${quant}__${corpus}"
  local log="$LOGDIR/${tag}.log"
  if [ ! -e "$file" ]; then
    echo "{\"model\":\"$model\",\"quant\":\"$quant\",\"corpus\":\"$corpus\",\"error\":\"file_missing\",\"file\":\"$file\"}" >> "$OUT"
    return
  fi
  local t0=$SECONDS
  timeout 1200 "$PP" -m "$file" -f ".wrapup/ppl_corpora/${corpus}.txt" \
      -c 2048 --chunks 40 -ngl 99 -ctk q8_0 -ctv q8_0 > "$log" 2>&1
  local rc=$?
  local dt=$((SECONDS - t0))
  local ppl nchunks
  ppl=$(grep -oE 'Final estimate: PPL = [0-9.]+' "$log" | tail -1 | grep -oE '[0-9.]+$')
  nchunks=$(grep -oE 'perplexity over [0-9]+ chunks' "$log" | head -1 | grep -oE '[0-9]+')
  if [ -n "$ppl" ]; then
    python3 -c "import json,sys; print(json.dumps({'model':'$model','quant':'$quant','corpus':'$corpus','ppl':float('$ppl'),'n_chunks':int('${nchunks:-0}'),'ctx':2048,'kv':'q8_0/q8_0','rc':$rc,'secs':$dt}))" >> "$OUT"
    echo "[$(date +%H:%M:%S)] OK  $tag ppl=$ppl chunks=$nchunks ${dt}s"
  else
    echo "{\"model\":\"$model\",\"quant\":\"$quant\",\"corpus\":\"$corpus\",\"error\":\"no_ppl_rc${rc}\",\"rc\":$rc,\"secs\":$dt}" >> "$OUT"
    echo "[$(date +%H:%M:%S)] FAIL $tag rc=$rc ${dt}s (see $log)"
  fi
}

sweep() {  # model  "quant:file" ...
  local model="$1"; shift
  for spec in "$@"; do
    local quant="${spec%%:*}" file="${spec##*:}"
    for c in "${C[@]}"; do run "$model" "$quant" "$file" "$c"; done
  done
}

echo "=== T1 PPL sweep start $(date) ==="
sweep Qwen3.5-2B \
  UD-IQ2_XXS:/home/z/hf/Qwen3.5-2B-UD-IQ2_XXS.gguf \
  UD-IQ2_M:/home/z/hf/Qwen3.5-2B-UD-IQ2_M.gguf \
  UD-Q2_K_XL:/home/z/hf/Qwen3.5-2B-UD-Q2_K_XL.gguf \
  UD-Q3_K_XL:/home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf \
  UD-Q4_K_XL:/home/z/hf/Qwen3.5-2B-UD-Q4_K_XL.gguf \
  UD-Q5_K_XL:/home/z/hf/Qwen3.5-2B-UD-Q5_K_XL.gguf
sweep Qwen3.5-0.8B \
  UD-Q2_K_XL:/home/z/hf/Qwen3.5-0.8B-UD-Q2_K_XL.gguf \
  UD-Q3_K_XL:/home/z/hf/Qwen3.5-0.8B-UD-Q3_K_XL.gguf \
  UD-Q4_K_XL:/home/z/hf/Qwen3.5-0.8B-UD-Q4_K_XL.gguf \
  UD-Q5_K_XL:/home/z/hf/Qwen3.5-0.8B-UD-Q5_K_XL.gguf
sweep Qwen3.5-4B \
  UD-Q2_K_XL:/home/z/hf/Qwen3.5-4B-UD-Q2_K_XL.gguf \
  UD-Q3_K_XL:/home/z/hf/Qwen3.5-4B-UD-Q3_K_XL.gguf \
  UD-Q4_K_XL:/home/z/hf/Qwen3.5-4B-UD-Q4_K_XL.gguf \
  UD-Q5_K_XL:/home/z/hf/Qwen3.5-4B-UD-Q5_K_XL.gguf
sweep gemma-4-E2B-it \
  UD-Q2_K_XL:/home/z/hf/gemma-4-E2B-it-UD-Q2_K_XL.gguf \
  UD-Q3_K_XL:/home/z/hf/gemma-4-E2B-it-UD-Q3_K_XL.gguf
sweep granite-4.1-3b \
  Q2_K:/home/z/hf/granite-4.1-3b-Q2_K.gguf \
  Q3_K_M:/home/z/hf/granite-4.1-3b-Q3_K_M.gguf \
  Q4_K_M:/home/z/hf/granite-4.1-3b-Q4_K_M.gguf
echo "=== T1 PPL sweep end $(date) ==="
echo "lines: $(wc -l < $OUT)"
