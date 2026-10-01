#!/bin/bash
cd /home/z/hf/research/.wrapup
while ! grep -q "M14 end" m14.log 2>/dev/null; do sleep 30; done
echo "[chain5] starting M15 $(date)" >> chain5.log
bash run_m15.sh
echo "[chain5] M15 done $(date)" >> chain5.log
