#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：`vendor-recommended` 臂的五个采样量必须真的进协议串，且不与 greedy 合并。

三例（都不需要模型，纯字符串与行键层面）：
  1. 协议串里五个量逐字出现（不是「vendorsampled」这种标签）；
  2. 与 greedy 的协议串不同；只差 `top_k` 的两条协议串也不同（测量身份含 protocol，不会被合并）；
  3. `mpl_protocol_label` 不会把厂商臂与 greedy 合成同一个显示标签。

服务端是否真的按这五个量采样，需要模型文件才能验证——本机没有 gguf，那一步**未验证**，
在输出里显式声明，并给出要跑的命令。
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / ".wrapup"))
import variant_panel as vp          # noqa: E402
import make_report                  # noqa: E402

VENDOR = {"temperature": 1.0, "top_p": 1.00, "top_k": 20, "min_p": 0.0, "presence_penalty": 2.0}


def main():
    spec = vp.sampling_spec(VENDOR)
    ok = True
    missing = [k for k, v in VENDOR.items() if f"{k}={v}" not in spec]
    print(f"1) spec = {spec}")
    print(f"   every one of the five appears verbatim: {not missing} {('missing ' + str(missing)) if missing else ''}")
    if missing:
        ok = False

    greedy = "variant-sampling-greedy-lmeval;sampling=temperature=0"
    vendor = f"variant-sampling-vendor-recommended-lmeval;{spec}"
    topk1 = "variant-sampling-greedy-topk1-lmeval;sampling=temperature=0,top_k=1"
    topk200 = "variant-sampling-greedy-topk200-lmeval;sampling=temperature=0,top_k=200"
    distinct = (vendor != greedy) and (topk1 != topk200)
    print(f"2) vendor != greedy, and top_k=1 != top_k=200: {distinct}")
    if not distinct:
        ok = False

    lab_vendor = make_report.mpl_protocol_label(vendor)
    lab_greedy = make_report.mpl_protocol_label(greedy)
    label_ok = lab_vendor != lab_greedy
    print(f"3) labels differ: {label_ok} ({lab_vendor!r} vs {lab_greedy!r})")
    if not label_ok:
        ok = False

    print("\nNOT VERIFIED: 服务端是否真的按这五个量采样，需要模型文件；本机没有 gguf。")
    print("  要跑的命令：")
    print('    python3 .wrapup/variant_panel.py --model <X.gguf> --tag a06-vendor-sampling \\')
    print('        --axis sampling            # 只跑 vendor-recommended 那一臂时删掉其它臂')
    print("  证据应包含：variant_panel.json 的 sampling_spec + server.log 的采样参数回显 + 五列分数")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
