#!/bin/bash
cd /home/z/hf/research/.wrapup
echo "[chain4] waiting for M12+M13 $(date)" >> chain4.log
while ! grep -q "M13 end" m13.log 2>/dev/null; do sleep 30; done
echo "[chain4] starting M14 $(date)" >> chain4.log
bash run_m14.sh
echo "[chain4] M14 done $(date)" >> chain4.log
