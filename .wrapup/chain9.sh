#!/bin/bash
# Chain M20 after M19 (M19 chain already finished -> starts immediately).
cd /home/z/hf/research/.wrapup
while ! grep -q "M19 end" m19.log 2>/dev/null; do sleep 30; done
echo "[chain9] starting M20 $(date)" >> chain9.log
bash run_m20.sh
echo "[chain9] M20 done $(date)" >> chain9.log
