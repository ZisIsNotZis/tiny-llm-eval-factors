#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a03 的两份入库夹具：把「只有本机才有的源」变成随仓库走的证据。

`analysis/run_all.py` 的断言里有两条依赖仓库外的东西：

  * **来源（厂商/上传者）** 只能从 `.wrapup/mres/<run_tag>/{evalplus,lmeval_panel}.json` 的
    `model` 绝对路径读，而 `.gitignore` 把 `.wrapup/mres/*` 排除了（只放行 `*_eval.json`）；
  * **比特分配轮廓** 只能从 gguf 头读，而 `*.gguf` 同样不入库。

干净 clone 里这两样都不在，断言就**无法成立**——所以这里把它们各自冻结成一份小夹具，
连同「它是从哪条路径、哪个 run_tag 推出来的」一起入库。判据：承载断言的东西必须随仓库走。

    python3 "docs/subprojects/a03-量化方案与厂商/analysis/build_fixtures.py"           # 重写两份夹具
    python3 ".../build_fixtures.py" --check    # 用本机源重算并与夹具比对，有漂移退出 1

`--check` 只在源存在时才有意义（干净 clone 里源不在，它打印「无源可比」并退出 2），
而 `run_all.py` 只读夹具，所以它在任何 clone 里都能跑完。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE
for _ in range(6):                       # docs/subprojects/<id>/analysis/build_fixtures.py → 仓库根
    REPO = REPO.parent
    if (REPO / "experiments.sqlite").is_file():
        break
else:
    sys.exit("找不到仓库根（experiments.sqlite）")

sys.path.insert(0, str(HERE.parent))

import alloc  # noqa: E402
import pairs  # noqa: E402

FIX = HERE.parent / "fixtures"
VENDOR_MAP = FIX / "vendor_map.json"
ALLOC_MAP = FIX / "alloc_map.json"


def build_vendor_map():
    """{模型文件: {vendors: [...], paths: {run_tag: 路径}}}，来源 = 面板写入的模型路径。"""
    cc = pairs.con()
    tag_models = {}
    for tag, model in cc.execute(
            "SELECT DISTINCT run_tag, model FROM experiments WHERE run_tag IS NOT NULL"):
        tag_models.setdefault(tag, set()).add(model)
    models = {}
    for tag, ms in sorted(tag_models.items()):
        for f in sorted((REPO / ".wrapup" / "mres" / tag).glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:            # 面板 json 坏了不影响其它面板
                continue
            p = d.get("model") or d.get("model_arg")
            if not isinstance(p, str) or not p.startswith("/"):
                continue
            for m in ms:
                base = m if m.endswith(".gguf") else m + ".gguf"
                e = models.setdefault(base, {"vendors": set(), "paths": {}})
                e["vendors"].add(pairs.vendor_in_path(p))
                e["paths"][tag] = p
    return {"source": ".wrapup/mres/<run_tag>/{evalplus,lmeval_panel,*}.json 的 model 字段；"
                      "run_tag 与 experiments.run_tag 同键",
            "vendor_rule": "mscache/<vendor>/… → vendor；models--<vendor>--… → vendor；"
                           "/home/z/hf/<file>.gguf → local；其余 unknown",
            "generated_by": "docs/subprojects/a03-量化方案与厂商/analysis/build_fixtures.py",
            "models": {m: {"vendors": sorted(e["vendors"]),
                           "paths": dict(sorted(e["paths"].items()))}
                       for m, e in sorted(models.items())}}


def build_alloc_map():
    """{模型文件: 实测轮廓}，来源 = 该 gguf 的头（逐张量元素数 + offset 差给出字节数）。"""
    cells, _dups = pairs.load()
    models = {}
    for m in sorted(cells):
        p = alloc.find_path(m)
        if p is None:
            continue                     # 盘上没有就是没有，不编一个
        try:
            prof = alloc.profile(p)
        except Exception as e:           # noqa: BLE001  坏文件不要让整张表失败
            print(f"  WARN {m}: {e}")
            continue
        models[m] = {"source_path": p, "n_params": prof["n_params"],
                     "n_bytes": prof["n_bytes"], "bpw_file": round(prof["bpw_file"], 6),
                     "classes": {k: {"params": v["params"], "bytes": v["bytes"],
                                     "bits": round(v["bits"], 6)}
                                 for k, v in prof["classes"].items()}}
    return {"source": "每个 gguf 的张量信息段：元素数 = 维度连乘，字节数 = 相邻 offset 之差"
                      "（末张量到文件尾）；bits/参数 = 8×字节÷元素数，不查类型表",
            "tensor_class": "embed / attn / ffn-expert(_exps) / ffn-shexp(_shexp) / "
                            "router(ffn_gate_inp) / ffn-dense / norm / output / other",
            "generated_by": "docs/subprojects/a03-量化方案与厂商/analysis/build_fixtures.py",
            "models": models}


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path.relative_to(REPO)}  sha256={hashlib.sha256(text.encode()).hexdigest()[:16]}  "
          f"{len(obj.get('models', {}))} 个模型")


def live_sources() -> tuple[bool, bool]:
    """(面板元数据在不在, gguf 在不在)。"""
    panels = any((REPO / ".wrapup" / "mres").glob("*/*.json")) and \
        any((REPO / ".wrapup" / "mres").glob("*/evalplus.json"))
    gguf = any(True for _ in (REPO / ".wrapup" / "mres").glob("*"))  # 占位，下面按需算
    cells, _d = pairs.load()
    gguf = any(alloc.find_path(m) for m in list(cells)[:5])
    return panels, gguf


def main(argv=()):
    check = "--check" in argv
    panels, gguf = live_sources()
    vmap = build_vendor_map() if panels else None
    amap = build_alloc_map() if gguf else None
    if not check:
        if vmap is None:
            print("  ABORT 面板元数据不在本机，无法重建 vendor_map.json")
        else:
            dump(VENDOR_MAP, vmap)
        if amap is None:
            print("  ABORT gguf 不在本机，无法重建 alloc_map.json")
        else:
            dump(ALLOC_MAP, amap)
        return 0
    bad = 0
    for path, fresh, present in ((VENDOR_MAP, vmap, panels), (ALLOC_MAP, amap, gguf)):
        if not present or fresh is None:
            print(f"  [{ '无源可比' }] {path.name}：本机没有它的源，跳过漂移检查（不是通过）")
            bad += 2
            continue
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if old == fresh:
            print(f"  [ok] {path.name} 与源一致")
            continue
        oldm, newm = (old or {}).get("models", {}), fresh.get("models", {})
        diff = sorted({k for k in set(oldm) | set(newm) if oldm.get(k) != newm.get(k)})
        print(f"  [FAIL] {path.name} 与源漂移：{len(diff)} 个模型不同，例如 {diff[:3]}")
        bad += 1
    if bad:
        return 2 if bad % 2 == 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(tuple(sys.argv[1:])))
