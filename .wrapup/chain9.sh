#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# Chain M20 after M19 (M19 chain already finished -> starts immediately).
cd ${REPO_ROOT}/.wrapup
while ! grep -q "M19 end" m19.log 2>/dev/null; do sleep 30; done
echo "[chain9] starting M20 $(date)" >> chain9.log
bash run_m20.sh
echo "[chain9] M20 done $(date)" >> chain9.log
