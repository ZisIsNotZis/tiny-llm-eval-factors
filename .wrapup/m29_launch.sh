#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# Launcher: wait for m24 to finish, then run m29 under the GPU lock.
while pgrep -f "[r]un_m24.sh" >/dev/null 2>&1; do sleep 30; done
exec bash ${REPO_ROOT}/.wrapup/gpu_locked.sh bash ${REPO_ROOT}/.wrapup/run_m29.sh
