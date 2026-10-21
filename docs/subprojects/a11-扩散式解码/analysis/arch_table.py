#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""llama.cpp 的架构名表：`diffusion-gemma` 在不在里面，是 a11 门槛的**源级**证据。

门槛的另一种说法是「运行时不认这个架构」。运行时不认，是因为它查的那张表里没有这个键，
而查表失败处抛的就是 `unknown model architecture: '<arch>'`。所以只要把那张表取下来存进仓库，
门槛就不再依赖 `.wrapup/` 里的一次性日志：干净 clone 里也能看到「表里有 gemma4 / gemma4-assistant /
dream / llada / rnd1，唯独没有 diffusion-gemma」，而 `gate.py` 现场重放的那句错话正是这张表
查不到时的固定输出。

一条记录 = 一棵源码树 + 两个文件的 sha256 + 取到的表。
  * `--record <label>` 写进 `fixtures/arch_tables.json`（同一 label 覆盖）；
  * 不带 `--record` 就打印，并与夹具里同名 label 比对（漂移检查，供 run_all 在有源码的机器上用）。

用法：
    python3 arch_table.py /home/z/llama.cpp --record local_4da6337
    python3 arch_table.py /tmp/lp2-src --record upstream_339f324
    python3 arch_table.py /home/z/llama.cpp --label local_4da6337   # 只对漂移
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
FIXTURE = HERE.parent / "fixtures" / "arch_tables.json"

NAME_RE = re.compile(r'^\s*\{\s*(LLM_ARCH_[A-Z0-9_]+)\s*,\s*"([^"]+)"\s*\}\s*,\s*$')
DIFFUSION_RE = re.compile(r"bool llm_arch_is_diffusion\(const llm_arch & arch\) \{(.*?)\n\}", re.S)
ENUM_RE = re.compile(r"case\s+(LLM_ARCH_[A-Z0-9_]+)\s*:")
THROW = "unknown model architecture: '"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(root):
    try:
        p = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=60)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    marker = Path(root) / "COMMIT"          # 从 git 仓库里 show 出来的源码树靠这个标明出处
    if marker.exists():
        return marker.read_text(encoding="utf-8").strip()
    return None


def read_table(root):
    root = Path(root)
    arch_cpp = root / "src" / "llama-arch.cpp"
    model_cpp = root / "src" / "llama-model.cpp"
    for p in (arch_cpp, model_cpp):
        if not p.exists():
            raise FileNotFoundError(f"{p} 不在：这棵树不是 llama.cpp 源码树")
    src = arch_cpp.read_text(encoding="utf-8", errors="replace")
    names = {}
    for line in src.splitlines():
        m = NAME_RE.match(line)
        if m:
            names[m.group(1)] = m.group(2)
    if not names:
        raise ValueError(f"{arch_cpp} 里没取到架构名表（格式变了？）")
    m = DIFFUSION_RE.search(src)
    diffusion_enums = sorted(set(ENUM_RE.findall(m.group(1)))) if m else []
    model_src = model_cpp.read_text(encoding="utf-8", errors="replace")
    if THROW not in model_src:
        raise ValueError(f"{model_cpp} 里没有 {THROW!r}：查表失败处的措辞变了，门槛文本要重取")
    return {
        "root": str(root),
        "git_head": git_head(root),
        "files": {"src/llama-arch.cpp": sha256(arch_cpp),
                  "src/llama-model.cpp": sha256(model_cpp)},
        "names": names,
        "diffusion_arch_enums": diffusion_enums,
        "diffusion_arch_names": sorted(names.get(e, e) for e in diffusion_enums),
        "throws_on_missing_arch": THROW,
        "has_diffusion_gemma": "diffusion-gemma" in names.values(),
    }


def load_fixture():
    if not FIXTURE.exists():
        return {}
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    root = argv[0]
    label = None
    if "--record" in argv:
        label = argv[argv.index("--record") + 1]
    elif "--label" in argv:
        label = argv[argv.index("--label") + 1]
    try:
        rec = read_table(root)
    except (OSError, ValueError) as e:
        print(f"取不到架构名表：{e}", file=sys.stderr)
        return 2
    if label is None:
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        return 0
    fx = load_fixture()
    if "--record" in argv:
        fx[label] = rec
        FIXTURE.parent.mkdir(exist_ok=True)
        FIXTURE.write_text(json.dumps(fx, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        print(f"已写入 {label}: {len(rec['names'])} 个架构名, "
              f"has_diffusion_gemma={rec['has_diffusion_gemma']}")
        return 0
    if label not in fx:
        print(f"夹具里没有 label {label!r}：先 --record", file=sys.stderr)
        return 2
    same = (fx[label]["names"] == rec["names"]
            and fx[label]["has_diffusion_gemma"] == rec["has_diffusion_gemma"])
    print(f"{label}: {'与夹具一致' if same else '与夹具**漂移**'}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main(tuple(sys.argv[1:])))
