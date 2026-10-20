#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
cd ${REPO_ROOT}/.wrapup
while ! grep -q "M17 end" m17.log 2>/dev/null; do sleep 30; done
echo "[chain7] starting M18 $(date)" >> chain7.log
bash run_m18.sh
echo "[chain7] M18 done $(date)" >> chain7.log
