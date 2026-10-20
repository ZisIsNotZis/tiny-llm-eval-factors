#!/bin/bash
# a03 复现负控：等 /tmp/llama_gpu.lock 空出来再跑两条 2B 代码面板（每条约 10 分钟，实测 m63/m64 = 638/573 s）。
# 队列语义：最多等 12 次 × 60 s，超时即放弃并把「未跑」原因写进日志，绝不抢锁、绝不等住回合。
cd /home/z/vibe/local_lm_research || exit 2
LOG=.wrapup/a03_repro.log
for i in $(seq 1 12); do
  if ! flock -n /tmp/llama_gpu.lock true; then
    echo "[$(date -Is)] attempt $i: lock held, wait 60s" >> $LOG
    sleep 60; continue
  fi
  echo "[$(date -Is)] attempt $i: lock free, running arms" >> $LOG
  bash .wrapup/codepanel.sh /home/z/hf/mscache/unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-UD-IQ3_XXS.gguf a03-repro-iq3xxs >> $LOG 2>&1
  sleep 5
  bash .wrapup/codepanel.sh /home/z/hf/mscache/unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-UD-Q2_K_XL.gguf a03-repro-q2kxl >> $LOG 2>&1
  echo "[$(date -Is)] arms done" >> $LOG
  exit 0
done
echo "[$(date -Is)] GAVE UP: lock held for 12 minutes; arms NOT run (未测)" >> $LOG
exit 3
