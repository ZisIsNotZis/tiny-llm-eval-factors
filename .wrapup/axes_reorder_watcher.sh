#!/bin/bash
# One-shot reorder watcher (operator option B).
# Waits for the in-flight m146 model to reach a CLEAN boundary (the driver logs
# "MODEL DONE m146-..." only when both DONE and code.DONE exist), then:
#   1. stops the campaign driver's whole process group (no orphaned panel/server),
#   2. waits for the GPU lock to free,
#   3. backs up + rewrites .wrapup/AXES_CAMPAIGN.txt with the remaining lines reordered
#      (m141, m152, m150, m151, then E2B/E4B, m155; m142/m143/m145 stay BLOCKED/no-retry),
#   4. restarts campaign.sh (idempotent) detached.
set -u
cd /home/z/hf/research || exit 2
WR=.wrapup
LOG="$WR/axes_reorder.log"
DRV=3850304
echo "[$(date -Is)] reorder-watcher armed (driver pgid $DRV)" >> "$LOG"

# 1. wait for the clean m146 boundary
for i in $(seq 1 2400); do
  grep -qE "MODEL (DONE|INCOMPLETE) m146-qat-gemma-e2b-q2" "$WR/campaign.log" && break
  sleep 15
done
if ! grep -qE "MODEL (DONE|INCOMPLETE) m146-qat-gemma-e2b-q2" "$WR/campaign.log"; then
  echo "[$(date -Is)] GIVEUP: m146 boundary not seen in 10h" >> "$LOG"; exit 1
fi
if ! { [ -f "$WR/mres/m146-qat-gemma-e2b-q2/DONE" ] && [ -f "$WR/mres/m146-qat-gemma-e2b-q2/code.DONE" ]; }; then
  echo "[$(date -Is)] boundary line seen but DONE banners missing; proceeding anyway" >> "$LOG"
fi
echo "[$(date -Is)] m146 clean boundary -> stopping driver group" >> "$LOG"

# 2. stop the whole group (driver + panel + its llama-server)
kill -TERM -"$DRV" 2>/dev/null
sleep 8
kill -KILL -"$DRV" 2>/dev/null
sleep 3
# safety: anything from THIS campaign still holding the gemma E2B/E4B server
for p in $(pgrep -f 'llama-server .*gemma-4-(E2B|E4B|12b)-it' 2>/dev/null); do
  echo "[$(date -Is)] killing leftover llama-server $p" >> "$LOG"; kill -TERM "$p" 2>/dev/null
done
# wait for GPU lock to be free (no more than ~2 min)
for i in $(seq 1 40); do flock -n /tmp/llama_gpu.lock true 2>/dev/null && break; sleep 3; done
echo "[$(date -Is)] driver stopped; lock_free=$(flock -n /tmp/llama_gpu.lock true 2>/dev/null && echo yes || echo no)" >> "$LOG"

# 3. back up + rewrite the campaign order
if [ ! -f "$WR/AXES_CAMPAIGN.orig.txt" ]; then cp "$WR/AXES_CAMPAIGN.txt" "$WR/AXES_CAMPAIGN.orig.txt"; fi
cat > "$WR/AXES_CAMPAIGN.txt" <<'EOF'
# AXES_CAMPAIGN.txt -- REORDERED per operator option B (front-load fast complete-pair models).
# Format: <abs_gguf_path> <tag> <limit> <mmlu_limit>
# Already complete (not relisted): m140, m144, m146.
# BLOCKED-on-VRAM, no retry (operator option a): m142, m143, m145 -- see .wrapup/AXES_BLOCKED.md
# Axis 1.6 12B native control
/home/z/hf/gemma-4-12b-it-UD-Q4_K_XL.gguf          m141-native-gemma12b-q4     100 16
# Axis 1.5 GSQ-RCO control + 2 treatments
/home/z/hf/Qwen3.8-27B-UD-IQ4_XS.gguf              m152-qwen38-27b-iq4xs       100 16
/home/z/hf/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf    m150-qwen38-gsqrco-iq3xxs   100 16
/home/z/hf/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf      m151-qwen38-gsqrco-iq3s     100 16
# Axis 1.6 E2B Q4 pair
/home/z/hf/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf      m147-qat-gemma-e2b-q4       100 16
/home/z/hf/gemma-4-E2B-it-UD-Q4_K_XL.gguf          m148-native-gemma-e2b-q4    100 16
# Axis 1.6 E4B Q2 treatment + E4B Q4 pair
/home/z/hf/gemma-4-E4B-it-qat-UD-Q2_K_XL.gguf      m149-qat-gemma-e4b-q2       100 16
/home/z/hf/gemma-4-E4B-it-UD-Q4_K_XL.gguf          m156-native-gemma-e4b-q4    100 16
/home/z/hf/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf      m155-qat-gemma-e4b-q4       100 16
EOF
echo "[$(date -Is)] campaign file rewritten" >> "$LOG"

# 4. restart idempotent driver, detached (new session/group)
CAMPAIGN_FILE="$WR/AXES_CAMPAIGN.txt" setsid bash "$WR/campaign.sh" >/dev/null 2>&1 < /dev/null &
sleep 5
NEW=$(pgrep -f "$WR/campaign.sh" | head -1)
echo "[$(date -Is)] restarted campaign.sh pid=$NEW" >> "$LOG"
