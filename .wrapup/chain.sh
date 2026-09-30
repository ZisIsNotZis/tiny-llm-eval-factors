#!/bin/bash
cd /home/z/hf/research/.wrapup
echo "[chain] waiting for M7 $(date)" >> chain.log
while pgrep -f '^bash run_m7.sh' >/dev/null 2>&1; do sleep 30; done
echo "[chain] M7 done, waiting for downloads $(date)" >> chain.log
while pgrep -f 'dl_fam2.sh' >/dev/null 2>&1; do sleep 30; done
echo "[chain] starting M6 $(date)" >> chain.log
bash run_m6.sh
echo "[chain] M6 done $(date)" >> chain.log
