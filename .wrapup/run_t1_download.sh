#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
cd ${REPO_ROOT}
LOG=.wrapup/t1_download.log
: > $LOG
echo "=== download start $(date) ===" >> $LOG
.wrapup/msenv/bin/modelscope download --model ibm-granite/granite-4.1-3b-GGUF granite-4.1-3b-Q4_K_M.gguf --local_dir /home/z/hf/mscache/ibm-granite/granite-4.1-3b-GGUF >> $LOG 2>&1
echo "exit=$? end $(date)" >> $LOG
ls -la /home/z/hf/mscache/ibm-granite/granite-4.1-3b-GGUF/ >> $LOG 2>&1
