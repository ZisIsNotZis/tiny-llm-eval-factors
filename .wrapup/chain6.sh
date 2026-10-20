#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
cd ${REPO_ROOT}/.wrapup
while ! grep -q "M16 end" m16.log 2>/dev/null; do sleep 30; done
echo "[chain6] starting M17 $(date)" >> chain6.log
bash run_m17.sh
echo "[chain6] M17 done $(date)" >> chain6.log
