#!/bin/bash
cd /home/z/hf/research/.wrapup
echo "[chain3] waiting for M12 $(date)" >> chain3.log
while ! grep -q "M12 end" m12.log 2>/dev/null; do sleep 30; done
echo "[chain3] M12 done, starting M13 $(date)" >> chain3.log
bash run_m13.sh
echo "[chain3] M13 done $(date)" >> chain3.log
