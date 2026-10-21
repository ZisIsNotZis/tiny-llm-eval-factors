#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三条路（同模型换运行时）的取证：`transformers` 里有没有 diffusion-gemma 的解码回路。

`RESULT.md::res7(c)` 原先写「上游权重与仓库未知」，把两件不同的事混成一件：**代码在不在**、
**权重在不在**。代码就在本机的 venv 里（`transformers 5.17.0` 的 `models/diffusion_gemma/`，
含生成循环、`max_denoising_steps` 默认 48、`EntropyBoundSampler.accept_canvas`），缺的是权重与许可。
本脚本把「代码在」这一段变成可核对的记录（夹具 + 漂移检查），不让它只停在 grep 的输出里。

记录的四个标记（都在 `generation_diffusion_gemma.py` / `configuration_diffusion_gemma.py` 里）：
  * `DiffusionGemmaForBlockDiffusion`（模型类）——证明这个架构被实现，不是只有配置；
  * `"max_denoising_steps": 48`（生成配置默认值）——解码步数的默认口径；
  * `class EntropyBoundSampler` 与 `def accept_canvas(`——块内接受判据，块扩散的解码回路本体；
  * `block length in block diffusion`（`canvas_length` 的 docstring）——原文措辞。

    python3 transformers_code.py            # 打印
    python3 transformers_code.py --record   # 写 fixtures/transformers_code.json
    python3 transformers_code.py --check    # 重新取并与夹具比对；找不到 venv 则 exit 2
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
FIXTURE = HERE.parent / "fixtures" / "transformers_code.json"
GLOB = os.path.join(REPO, ".wrapup", "*", "lib", "python3*", "site-packages")
MARKERS = {
    "model_class": re.compile(r"^class DiffusionGemmaForBlockDiffusion\b", re.M),
    "denoise_steps_default": re.compile(r'"max_denoising_steps":\s*(\d+)'),
    "sampler_class": re.compile(r"^class EntropyBoundSampler\b", re.M),
    "accept_canvas": re.compile(r"^\s*def accept_canvas\(", re.M),
    "canvas_docstring": re.compile(r"block length in block diffusion"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_package():
    for site in sorted(glob.glob(GLOB)):
        pkg = Path(site) / "transformers" / "models" / "diffusion_gemma"
        if (pkg / "generation_diffusion_gemma.py").exists():
            dist = sorted(glob.glob(os.path.join(site, "transformers-*.dist-info")))
            return pkg, ([Path(d).name for d in dist] or [None])[0]
    return None, None


def probe():
    pkg, dist = find_package()
    if pkg is None:
        return None
    gen = pkg / "generation_diffusion_gemma.py"
    cfg = pkg / "configuration_diffusion_gemma.py"
    ml = pkg / "modeling_diffusion_gemma.py"
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in (gen, cfg, ml))
    found = {}
    for name, rx in MARKERS.items():
        m = rx.search(text)
        found[name] = bool(m)
        if m and name == "denoise_steps_default":
            found["denoise_steps_default_value"] = int(m.group(1))
    cfg_text = cfg.read_text(encoding="utf-8", errors="replace")
    line = next((i + 1 for i, l in enumerate(cfg_text.split("\n"))
                 if "block length in block diffusion" in l), None)
    return {
        "venv_site_packages": str(pkg.parents[3]),
        "transformers_dist": dist,
        "package_dir": str(pkg),
        "files": {p.name: sha256(p) for p in (gen, cfg, ml)},
        "markers": found,
        "canvas_docstring_line": f"configuration_diffusion_gemma.py:{line}" if line else None,
        "has_bf16_weights": None,   # 权重是否存在是另一件事，由 gate/run_all 的 F 段判
    }


def main(argv):
    rec = probe()
    if rec is None:
        print("本机没有装着 transformers 的 venv（或里面没有 diffusion_gemma）→ 未验证", file=sys.stderr)
        return 2
    if "--record" in argv:
        FIXTURE.parent.mkdir(exist_ok=True)
        FIXTURE.write_text(json.dumps(rec, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        print(f"已写入 {FIXTURE.name}: {rec['transformers_dist']} "
              f"{rec['markers']}")
        return 0
    if "--check" in argv:
        if not FIXTURE.exists():
            print(f"缺夹具 {FIXTURE.name}", file=sys.stderr)
            return 2
        fixed = json.loads(FIXTURE.read_text(encoding="utf-8"))
        drift = [k for k in ("transformers_dist", "markers", "canvas_docstring_line", "files")
                 if fixed.get(k) != rec.get(k)]
        print(f"transformers 的 diffusion_gemma 代码：{'与夹具一致' if not drift else '漂移 ' + str(drift)}")
        return 0 if not drift else 1
    print(json.dumps(rec, ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(tuple(sys.argv[1:])))
