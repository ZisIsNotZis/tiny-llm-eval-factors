#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# KV then sampling on the two 2B quants, under the GPU lock.
set -u
cd ${REPO_ROOT} || exit 2
WR=${REPO_ROOT}/.wrapup
PY="$WR/lmenv/bin/python"
LOG="$WR/variant_campaign.log"
exec 7>/tmp/variant_driver.lock
flock -n 7 || { echo "another variant driver holds the lock"; exit 0; }
run() {  # tag axis model
  local tag="$1" axis="$2" model="$3"
  [ -f "$WR/mres/$tag/DONE" ] && { echo "[$(date -Is)] SKIP $tag" >> "$LOG"; return; }
  echo "[$(date -Is)] START $tag $axis" >> "$LOG"
  "$PY" "$WR/variant_panel.py" --model "$model" --tag "$tag" --axis "$axis" --limit 50 \
      >> "$WR/variant_campaign.out" 2>&1
  [ -f "$WR/mres/$tag/DONE" ] && echo "[$(date -Is)] DONE $tag" >> "$LOG" \
                              || echo "[$(date -Is)] FAIL $tag" >> "$LOG"
}
run m130-kv       kv       /home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf
run m131-sampling sampling /home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf
echo "[$(date -Is)] === variant campaign end ===" >> "$LOG"
