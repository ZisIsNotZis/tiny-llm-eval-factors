#!/bin/bash
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
cd /home/z/hf/research/.wrapup
uv venv --python 3.11 evalpy 2>&1
uv pip install --python evalpy/bin/python evalplus 2>&1
evalpy/bin/python -c "import evalplus; print('evalplus OK', evalplus.__file__)"
