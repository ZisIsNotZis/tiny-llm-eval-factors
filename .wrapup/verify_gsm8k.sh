#!/bin/bash
# Decisive check on the gsm8k anomaly on the Qwen3.5-2B ladder.
#
# thinking-off gsm8k: IQ2_XXS 0.02, IQ2_M 0.01, IQ3_XXS 0.01, Q2_K_XL 0.36, while MMLU is
# 0.36 / 0.50 / 0.56 / 0.55 -- i.e. IQ3_XXS has the BEST knowledge and code of the four but
# sits on the gsm8k floor.  Before that is reported as a finding, look at the raw generations:
# a parsing/format artifact and a genuine reasoning collapse look identical in the score.
#
# This dumps lm_eval's per-sample prompt/response for a small limit, side by side.
set -u
cd /home/z/hf/research || exit 2
exec 9>/tmp/llama_gpu.lock
if ! flock -n 9; then echo "verify: GPU lock held; aborting"; exit 3; fi

PY=/home/z/hf/research/.wrapup/lmenv/bin/python
OUT=/home/z/hf/research/.wrapup/mres/verify-gsm8k
mkdir -p "$OUT"
LIM="${LIM:-30}"

run_one() {  # <model> <tag> <port>
  local model="$1" tag="$2" port="$3"
  echo "=== $tag  $model" | tee -a "$OUT/verify.log"
  nohup /home/z/.local/bin/llama-server -m "$model" --port "$port" --host 127.0.0.1 \
      -c 8192 -np 1 -ngl 99 --jinja --reasoning off > "$OUT/$tag.server.log" 2>&1 &
  local srv=$!
  for _ in $(seq 1 180); do curl -s -o /dev/null "http://127.0.0.1:$port/health" && break; sleep 2; done
  env HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    "$PY" -m lm_eval --model local-chat-completions \
      --model_args "base_url=http://127.0.0.1:$port/v1/chat/completions" \
      --tasks gsm8k --apply_chat_template --gen_kwargs temperature=0,max_gen_toks=1024 \
      --limit "$LIM" --log_samples --output_path "$OUT/$tag" > "$OUT/$tag.eval.log" 2>&1
  kill $srv 2>/dev/null; wait $srv 2>/dev/null
  echo "  rc=$? samples -> $(find "$OUT/$tag" -name 'samples_gsm8k*.jsonl' | head -1)" | tee -a "$OUT/verify.log"
}

run_one /home/z/hf/mscache/unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-UD-IQ3_XXS.gguf v-iq3xxs 8931
run_one /home/z/hf/mscache/unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-UD-Q2_K_XL.gguf  v-q2kxl  8932

# Summarise: how many responses contain the '####' answer marker, and a few raw samples.
"$PY" - "$OUT" <<'PYEOF'
import glob, json, os, sys
out = sys.argv[1]
for tag in ("v-iq3xxs", "v-q2kxl"):
    fs = glob.glob(os.path.join(out, tag, "**", "samples_gsm8k*.jsonl"), recursive=True)
    if not fs:
        print(f"{tag}: NO SAMPLES"); continue
    rows = [json.loads(l) for l in open(fs[0]) if l.strip()]
    n = len(rows)
    has_marker = sum(1 for r in rows if "####" in str(r.get("filtered_resps")))
    empty = sum(1 for r in rows if not str(r.get("filtered_resps") or "").strip())
    print(f"\n===== {tag}: n={n}  with-'####'={has_marker}  empty={empty}")
    for r in rows[:6]:
        tgt = str(r.get("target"))[-40:].replace("\n", "|")
        resp = str(r.get("filtered_resps"))[:300].replace("\n", "|")
        print(f"  target_tail={tgt!r}\n    resp={resp!r}")
PYEOF
echo "verify done"
