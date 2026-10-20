#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
cd ${REPO_ROOT}/.wrapup
echo "[chain3] waiting for M12 $(date)" >> chain3.log
while ! grep -q "M12 end" m12.log 2>/dev/null; do sleep 30; done
echo "[chain3] M12 done, starting M13 $(date)" >> chain3.log
bash run_m13.sh
echo "[chain3] M13 done $(date)" >> chain3.log
