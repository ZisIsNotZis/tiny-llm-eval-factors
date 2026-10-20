#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：venv 入口点指向不存在解释器时必须 FAIL 并点名，指向 `env` 的不得误报。"""
from __future__ import annotations
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
CHECK = REPO / "checks" / "venv_shebang.py"

def main():
    tmp = Path(tempfile.mkdtemp(prefix="venv-shebang-negative-control-"))
    try:
        b = tmp / "busted" / "bin"; b.mkdir(parents=True)
        (b / "lm_eval").write_text("#!/nonexistent/python3\nprint(1)\n")
        (b / "envtool").write_text("#!/usr/bin/env python3\nprint(2)\n")
        r = subprocess.run([sys.executable, str(CHECK), str(tmp / "busted")],
                           capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        ok = r.returncode == 1 and "lm_eval" in out and "envtool" not in out
        print(f"1) bogus shebang          : exit {r.returncode}, names lm_eval, ignores env: {ok}")
        if not ok:
            print(out); return 1
        good = tmp / "good" / "bin"; good.mkdir(parents=True)
        (good / "envtool").write_text("#!/usr/bin/env python3\nprint(2)\n")
        r2 = subprocess.run([sys.executable, str(CHECK), str(tmp / "good")],
                            capture_output=True, text=True)
        ok2 = r2.returncode == 0
        print(f"2) only env-based entries : exit {r2.returncode} (expect 0): {ok2}")
        if not ok2:
            print(r2.stdout); return 1
        print("PASS: 指向不存在解释器 → FAIL 并点名；只含 env 入口 → PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
