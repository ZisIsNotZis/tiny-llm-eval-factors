#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
cd ${REPO_ROOT}
setsid nohup bash .wrapup/gpu_locked.sh bash .wrapup/run_t1_ppl.sh > .wrapup/t1_sweep.log 2>&1 &
echo "t1 sweep launcher pid $!"
