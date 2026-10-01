#!/bin/bash
cd /home/z/hf/research/.wrapup
echo "[chain2] waiting for M11 $(date)" >> chain2.log
while ! grep -q "M11 end" m11.log 2>/dev/null; do sleep 30; done
echo "[chain2] M11 done, starting M12 $(date)" >> chain2.log
bash run_m12.sh
echo "[chain2] M12 done $(date)" >> chain2.log
