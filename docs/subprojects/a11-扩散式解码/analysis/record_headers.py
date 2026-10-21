#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重取 `fixtures/headers.json`（两份 GGUF 的头部）。权重不在仓库里，头部在。

    python3 record_headers.py [--check]

`--check` 在有 live 文件的机器上重取并与夹具逐字段比对（漂移检查）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import gguf_header  # noqa: E402

DEST = HERE.parent / "fixtures" / "headers.json"
FILES = {
    "diffusiongemma-26B-A4B-it-Q4_K_M.gguf":
        "/home/z/hf/diffusiongemma-26B-A4B-it-Q4_K_M.gguf",
    "gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf":
        "/home/z/hf/gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf",
}
NOTE = ("两份 GGUF 的头部（元数据 + 每张量形状/类型/偏移/字节），不含权重；"
        "用来在干净 clone 里复算参数量与位宽")


def build(missing_ok=False):
    out = {"producer": "python3 record_headers.py",
           "producer_module": "analysis/gguf_header.py",
           "what": NOTE, "models": {}, "missing": []}
    for name, path in FILES.items():
        if not Path(path).exists():
            if not missing_ok:
                raise FileNotFoundError(path)
            out["missing"].append(path)
            continue
        h = gguf_header.read_header(path, shapes=True)
        h.pop("path", None)
        out["models"][name] = h
    return out


def main(argv):
    if "--check" in argv:
        try:
            live = build()
        except FileNotFoundError as e:
            print(f"缺 {e}：漂移检查**未验证**", file=sys.stderr)
            return 2
        fixed = json.loads(DEST.read_text(encoding="utf-8"))
        drift = [n for n in live["models"] if live["models"][n] != fixed["models"].get(n)]
        print(f"夹具与盘上头部：{'一致' if not drift else '漂移 ' + str(drift)}")
        return 0 if not drift else 1
    try:
        data = build()
    except FileNotFoundError as e:
        print(f"缺 {e}：无法重取夹具", file=sys.stderr)
        return 2
    DEST.parent.mkdir(exist_ok=True)
    DEST.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(f"已写入 {DEST.name}：{len(data['models'])} 份头部")
    return 0


if __name__ == "__main__":
    sys.exit(main(tuple(sys.argv[1:])))
