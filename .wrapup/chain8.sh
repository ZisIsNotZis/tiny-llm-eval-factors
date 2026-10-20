#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
cd ${REPO_ROOT}/.wrapup
while ! grep -q "M18 end" m18.log 2>/dev/null; do sleep 30; done
echo "[chain8] starting M19 $(date)" >> chain8.log
bash run_m19.sh
echo "[chain8] M19 done $(date)" >> chain8.log
