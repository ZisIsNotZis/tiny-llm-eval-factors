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
"$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r "$REQ"
echo "== entry points =="
ls "$VENV/bin" | head -20
python3 checks/venv_shebang.py "$(dirname "$VENV")"
