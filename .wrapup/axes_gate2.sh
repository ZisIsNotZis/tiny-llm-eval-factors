#!/bin/bash
# axes_gate2.sh -- idempotent CPU load gate for the AXES campaign, diffusion first.
#
# Same contract as axes_gate.sh but (a) gates DiffusionGemma immediately (it is the file
# most likely to GATE-FAIL and the axis-7 decision needs it early), and (b) skips any tag
# already present in .wrapup/loadgate.jsonl so a restart cannot double-record.
set -u
cd /home/z/hf/research || exit 2
W=/home/z/hf/research/.wrapup
LG=$W/loadgate.jsonl
H=/home/z/hf
touch "$LG"

already() { grep -q "\"tag\": \"$1\"" "$LG" 2>/dev/null; }

gate() {  # <tag> <basename>
  local tag="$1" f="$2"
  if already "$tag"; then echo "[axes_gate] $(date +%H:%M:%S) SKIP $tag (gate row exists)" >> "$W/loadgate.log"; return 0; fi
  if [ ! -e "$H/$f" ]; then echo "[axes_gate] $(date +%H:%M:%S) SKIP $tag $f (missing)" >> "$W/loadgate.log"; return 1; fi
  bash "$W/loadgate_cpu.sh" "$f" "$tag"
}

# --- DiffusionGemma FIRST: dedicated diffusion runtime, not llama-server ---
DIFF=$H/diffusiongemma-26B-A4B-it-Q4_K_M.gguf
DTAG=m154-diffusiongemma-26b-a4b-q4km
if already "$DTAG"; then
  echo "[axes_gate] $(date +%H:%M:%S) SKIP $DTAG (gate row exists)" >> "$W/loadgate.log"
elif [ -e "$DIFF" ]; then
  echo "[axes_gate] $(date +%H:%M:%S) DIFF START $DTAG" >> "$W/loadgate.log"
  timeout 2400 llama-diffusion-cli -m "$DIFF" -ngl 0 -t 8 -c 1024 -n 16 --diffusion-steps 32 \
      -p "The capital of France is" > "$W/axes_diffusion_gate.log" 2>&1
  rc=$?
  res=FAIL
  if [ "$rc" -eq 0 ] && ! grep -qiE 'error|failed to|unknown model|unsupported|abort|assert' "$W/axes_diffusion_gate.log"; then
    res=PASS
  fi
  echo "[axes_gate] $(date +%H:%M:%S) $DTAG diffusion-cli rc=$rc -> $res" >> "$W/loadgate.log"
  python3 - "$DTAG" "diffusiongemma-26B-A4B-it-Q4_K_M.gguf" "$res" "$LG" <<'PY'
import json, sys
tag, f, res, dest = sys.argv[1:5]
with open(dest, "a") as fh:
    fh.write(json.dumps({"tag": tag, "file": f, "load": res,
                         "runtime": "llama-diffusion-cli"}) + "\n")
PY
else
  echo "[axes_gate] $(date +%H:%M:%S) SKIP $DTAG (missing)" >> "$W/loadgate.log"
fi

# --- native UD-Q4_K_XL controls: wait (bounded) for each download, then gate ---
wait_gate() {  # <tag> <basename> <timeout_s>
  local tag="$1" f="$2" tmo="$3" waited=0
  already "$tag" && return 0
  while [ ! -e "$H/$f" ] && [ "$waited" -lt "$tmo" ]; do sleep 30; waited=$((waited + 30)); done
  gate "$tag" "$f"
}
wait_gate m148-native-gemma-e2b-q4     gemma-4-E2B-it-UD-Q4_K_XL.gguf      5400
wait_gate m156-native-gemma-e4b-q4     gemma-4-E4B-it-UD-Q4_K_XL.gguf      5400
wait_gate m141-native-gemma12b-q4      gemma-4-12b-it-UD-Q4_K_XL.gguf      5400
wait_gate m145-native-gemma26b-a4b-q4  gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf  5400
wait_gate m143-native-gemma31b-q4      gemma-4-31B-it-UD-Q4_K_XL.gguf      5400

echo "[axes_gate] $(date +%H:%M:%S) DONE" >> "$W/loadgate.log"
