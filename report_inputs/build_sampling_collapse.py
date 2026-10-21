#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `a06` 的厂商臂塌陷事实抽成派生索引，供报告第六节生成文字。"""
from __future__ import annotations
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "sampling_collapse.json")
SRC = os.path.join(REPO, "docs", "subprojects", "a06-采样与解码参数", "RESULT.md")

def build():
    s = open(SRC, encoding="utf-8").read()
    m = re.search(r"q2-cpp (\d+)→(\d+)（−(\d+)）.*?q4-py (\d+)→(\d+)（−(\d+)）.*?"
                  r"94/164→\*\*(\d+)/164\*\*（−(\d+)）", s, re.S)
    if not m: raise SystemExit("a06 的 RESULT.md 里找不到丢题清单")
    cells = re.findall(r"(q[234]-(?:cpp|py)) (\d+)→(\d+)（−(\d+)）", m.group(0))
    floor = re.search(r"`SyntaxError=(\d+), Exception=(\d+), OK=(\d+)`", s)
    m2 = re.search(r"M1 \| 1\.0 \| 1\.00 \| 0\.00 \| 0\.0 \| (\d+)/(\d+)", s)
    return {"source": os.path.relpath(SRC, REPO),
            "mpl_losses": [{"cell": c, "from": int(a), "to": int(b), "lost": int(d)}
                           for c, a, b, d in cells],
            "evalplus": {"from": 94, "to": int(m.group(7)), "lost": int(m.group(8))},
            "floor_cpp": ({"syntax": int(floor.group(1)), "exception": int(floor.group(2)),
                           "ok": int(floor.group(3))} if floor else None),
            "m2_probe": ({"pass": int(m2.group(1)), "n": int(m2.group(2))} if m2 else None),
            "not_temperature": True}

def dump(d): return json.dumps(d, ensure_ascii=False, indent=1) + "\n"

def main(argv):
    doc = build(); txt = dump(doc)
    if "--check" in argv:
        try: have = open(OUT, encoding="utf-8").read()
        except FileNotFoundError: print("missing", file=sys.stderr); return 1
        if have != txt: print("stale; rerun without --check", file=sys.stderr); return 1
        print("sampling_collapse.json: up to date"); return 0
    open(OUT, "w", encoding="utf-8").write(txt)
    print(f"wrote {os.path.relpath(OUT, REPO)}: {len(doc['mpl_losses'])} MPL cells + EvalPlus")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
