#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
cd ${REPO_ROOT}/.wrapup
uv venv --python 3.11 evalpy 2>&1
uv pip install --python evalpy/bin/python evalplus 2>&1
evalpy/bin/python -c "import evalplus; print('evalplus OK', evalplus.__file__)"
