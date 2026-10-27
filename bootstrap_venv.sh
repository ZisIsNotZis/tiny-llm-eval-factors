#!/bin/bash
# 从锁定的依赖重建一个 venv，使入口点 shebang 由**创建时**的解释器决定，而不是继承旧机器的路径。
#
#   ./bootstrap_venv.sh .wrapup/lmenv requirements.txt
#
# venv 本身不入库（.gitignore），所以干净 clone 里跑这一条就够；重建后 `checks/venv_shebang.py`
# 会确认所有入口点指向存在的解释器。
set -eu
if [ $# -lt 2 ]; then
    echo "usage: $0 <venv-dir> <requirements-file>" >&2
    exit 2
fi
VENV="$1"
REQ="$2"
[ -f "$REQ" ] || { echo "requirements 不存在：$REQ" >&2; exit 2; }
PY="${PYTHON:-python3}"
echo "== recreate $VENV with $PY =="
rm -rf "$VENV"
if "$PY" -m venv "$VENV" 2>/dev/null; then
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet -r "$REQ"
else
    # Debian/Ubuntu 的 Python 可能没有 ensurepip（缺 python3.x-venv）。用 uv 建同一个
    # venv 并装同一份 requirements；这是工具链回退，不改变依赖清单。
    echo "== python -m venv failed (ensurepip unavailable); falling back to uv =="
    rm -rf "$VENV"
    command -v uv >/dev/null 2>&1 || { echo "uv 不可用：先装 python3-venv 或 uv" >&2; exit 2; }
    uv venv "$VENV" --python "$PY" || exit 2
    uv pip install --python "$VENV/bin/python" -r "$REQ" || exit 2
fi
echo "== entry points =="
ls "$VENV/bin" | head -20
python3 checks/venv_shebang.py "$(dirname "$VENV")"
