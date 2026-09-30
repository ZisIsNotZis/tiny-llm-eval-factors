#!/bin/bash
cd /home/z/hf/research
setsid nohup bash .wrapup/gpu_locked.sh bash .wrapup/run_t1_ppl.sh > .wrapup/t1_sweep.log 2>&1 &
echo "t1 sweep launcher pid $!"
