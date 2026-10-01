#!/bin/bash
cd /home/z/hf/research/.wrapup
while ! grep -q "M16 end" m16.log 2>/dev/null; do sleep 30; done
echo "[chain6] starting M17 $(date)" >> chain6.log
bash run_m17.sh
echo "[chain6] M17 done $(date)" >> chain6.log
