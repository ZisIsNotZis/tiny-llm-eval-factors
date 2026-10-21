#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a11 的门槛（gate）：把一个 `diffusion-gemma` GGUF 交给本机运行时，记录它死在哪一步。

为什么要有这个装置：登记表给 a11 的 AC 是「要么测出对照，要么 GATE-FAIL 且门槛可复现」。
一条「加载不了」的日志放在 `.wrapup/` 里不算可复现——它没进仓库、没有负控、也不知道
是文件坏了、显存不够、还是运行时根本不认这个架构。本脚本把三者分开：

  * 架构：运行时自报 `unknown model architecture: '<arch>'`，且该 arch 名不在运行时的
    arch 名表里（`llama-model.cpp` 在查表失败处抛的就是这一句，见 fixtures 里的行号）；
  * 文件：头部能解析、架构名与 GGUF 元数据一致（不是 truncated 文件）；
  * 负控：同一个加载器换一个**本机支持**的模型必须真的加载起来并出 token——
    否则「加载失败」不构成证据，它只是这段代码永远失败。

退出码即结论：
  0 = 门槛成立（GATE-FAIL：本机运行时拒绝该架构，而负控加载成功）；
  1 = 门槛被推翻或负控不成立（有运行时装上了 / 加载器无区分力）→ 必须重新计划；
  2 = 看不到输入（模型或二进制不在）→ 未验证，不是通过。

GPU：本脚本全程 `-ngl 0`，不建 CUDA 上下文、不碰 `/tmp/llama_gpu.lock`
（与 `.wrapup/loadgate_cpu.sh` 同一约定：架构/类型这一类失败在 CPU 侧就该被抓住）。

用法：
    python3 gate.py                 # 本机现场重放，打印门槛与价格
    python3 gate.py --record        # 同上，并把这一天的观察写进 fixtures/diffusion_gate.json
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import gguf_header  # noqa: E402

MODEL = os.environ.get("A11_DIFFUSION_GGUF",
                       "/home/z/hf/diffusiongemma-26B-A4B-it-Q4_K_M.gguf")
CONTROL = os.environ.get("A11_CONTROL_GGUF", "/home/z/hf/gemma-4-E2B-it-UD-Q4_K_XL.gguf")
RUNNERS = ("llama-diffusion-cli", "llama-server", "llama-cli")
SERVER_PORT = 8199                     # .wrapup/loadgate_cpu.sh 用 8188，别撞
ARCH_ERR = re.compile(r"unknown model architecture: '([^']+)'")
FIXTURE = HERE.parent / "fixtures" / "diffusion_gate.json"


def run(cmd, timeout):
    """跑一次，返回 rc / 合并输出（截尾 4000 字）。超时记 rc=None。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out[-4000:]
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes)
               else (e.stdout or "")) + ((e.stderr or b"").decode("utf-8", "replace")
                                         if isinstance(e.stderr, bytes) else (e.stderr or ""))
        return None, out[-4000:]


def version_of(binary):
    if not shutil.which(binary):
        return None
    _rc, out = run([binary, "--version"], 60)
    for line in out.splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return out.strip()[:200] or None


def load_attempt(binary, model, extra, timeout):
    """一次加载尝试。返回 {cmd, rc, arch_error, out_tail}。"""
    cmd = [binary, "-m", model, "-ngl", "0"] + extra
    rc, out = run(cmd, timeout)
    m = ARCH_ERR.search(out)
    return {"cmd": " ".join(cmd), "rc": rc,
            "arch_error": m.group(1) if m else None,
            "tail": "\n".join(out.strip().splitlines()[-3:])}


def control_load(model, port, wait_s=300):
    """负控：同一个 llama-server 换一个**支持**的模型，必须走完 /health 并真出一个 completion。

    这是本仓库既有的加载闸门做法（`.wrapup/loadgate_cpu.sh`）：llama-cli 会进交互循环，
    而 server 的 `/health` + `/completion` 有明确的「起来了」与「出了 token」两个判据。
    """
    cmd = ["llama-server", "-m", model, "-ngl", "0", "-c", "2048", "-t", "8",
           "--port", str(port), "--host", "127.0.0.1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log, health_ok, token = [], False, False
    deadline = time.time() + wait_s
    try:
        while time.time() < deadline and proc.poll() is None:
            time.sleep(1)
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/health", timeout=3) as r:
                    if b'"ok"' in r.read():
                        health_ok = True
                        break
            except OSError:
                continue
        if health_ok:
            body = json.dumps({"prompt": "def add(a, b):\n    return a",
                               "n_predict": 4, "temperature": 0}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/completion", data=body,
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    token = b'"content"' in r.read()
            except OSError as e:
                log.append(f"completion 失败：{e}")
    finally:
        proc.terminate()
        try:
            out = proc.communicate(timeout=30)[0] or ""
        except subprocess.TimeoutExpired:
            proc.kill()
            out = ""
    tail = "\n".join(((out or "") + "\n" + "\n".join(log)).strip().splitlines()[-3:])
    m = ARCH_ERR.search(out or "")
    return {"cmd": " ".join(cmd), "health_ok": health_ok, "token": token,
            "arch_error": m.group(1) if m else None, "tail": tail,
            "ok": bool(health_ok and token)}


def gpu_state():
    """当前卡的占用（不占卡，只问驱动）。没有 nvidia-smi 就记 None。"""
    if not shutil.which("nvidia-smi"):
        return None
    rc, out = run(["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
                   "--format=csv,noheader,nounits"], 60)
    rc2, apps = run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                     "--format=csv,noheader,nounits"], 60)
    if rc != 0:
        return None
    total, used, free = (int(x) for x in out.strip().splitlines()[0].split(", "))
    others = 0
    for line in apps.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[1].isdigit():
            others += int(parts[1])
    return {"total_mib": total, "used_mib": used, "free_mib": free,
            "compute_apps_mib": others}


def main(argv):
    record = "--record" in argv
    print("a11 门槛：diffusion-gemma 在本机运行时到底是什么状态")
    missing = [p for p in (MODEL, CONTROL) if not os.path.exists(p)]
    for p in (MODEL, CONTROL):
        print(f"  {'[有]' if os.path.exists(p) else '[缺]'} {p}")
    if missing:
        print("  → 看不到输入，门槛**未验证**（不是通过）。缺：" + "、".join(missing),
              file=sys.stderr)
        return 2
    bins = {b: version_of(b) for b in RUNNERS}
    for b, v in bins.items():
        print(f"  {'[有]' if v else '[缺]'} {b}: {v}")
    if not bins["llama-diffusion-cli"] and not bins["llama-server"]:
        print("  → 没有可用的运行时二进制，门槛**未验证**（不是通过）", file=sys.stderr)
        return 2

    hdr = gguf_header.read_header(MODEL, shapes=False)
    ctl = gguf_header.read_header(CONTROL, shapes=False)
    kv_b = gguf_header.kv_upper_bound(hdr["meta"])
    print(f"\n  模型头部：arch={hdr['arch']}  n_params={hdr['n_params']:,}  "
          f"file={hdr['file_bytes']:,} B  bpw={hdr['bpw_file']:.4f}  "
          f"canvas={hdr['meta'].get('diffusion.canvas_length')}  "
          f"causal={hdr['meta'].get('attention.causal')}")
    print(f"  负控模型：arch={ctl['arch']}  n_params={ctl['n_params']:,}  "
          f"file={ctl['file_bytes']:,} B")

    print("\n  加载尝试（全部 -ngl 0，不碰 GPU 显存、不持锁）：")
    attempts = []
    if bins["llama-diffusion-cli"]:
        attempts.append(("llama-diffusion-cli",
                         load_attempt("llama-diffusion-cli", MODEL,
                                      ["-n", "4", "-p", "def add(a, b):"], 180)))
    if bins["llama-server"]:
        attempts.append(("llama-server",
                         load_attempt("llama-server", MODEL,
                                      ["-c", "512", "--port", str(SERVER_PORT),
                                       "--host", "127.0.0.1"], 180)))
    for name, a in attempts:
        print(f"    {name}: rc={a['rc']} arch_error={a['arch_error']!r}")
        print(f"      {a['tail'].splitlines()[-1] if a['tail'] else ''}")
    control = control_load(CONTROL, SERVER_PORT + 1) if bins["llama-server"] else {
        "ok": False, "tail": "没有 llama-server，负控无从谈起", "arch_error": None}
    control_ok = bool(control.get("ok"))
    print(f"    负控 llama-server: health={control.get('health_ok')} "
          f"token={control.get('token')} → {'加载成功' if control_ok else '没加载起来'}")
    if not control_ok:
        print(f"      {control.get('tail', '')}")

    gpu = gpu_state()
    kv_true = gguf_header.kv_true_bytes(hdr["meta"], 4096)
    weights_gib = round(hdr["data_bytes"] / 2**30, 3)
    kv_true_gib = round(kv_true / 2**30, 3) if kv_true else None
    price = {
        "weights_bytes": hdr["data_bytes"],
        "weights_gib": weights_gib,
        # 上界口径：不认滑窗、不认 *_swa 小头维，只当「头部自洽」的参照，不是需求
        "kv_bound_bytes_per_token": kv_b,
        "kv_bound_gib_at_4096": round(kv_b * 4096 / 2**30, 3) if kv_b else None,
        # 真值口径：按层记账（滑窗层只留 min(ctx, window) 个 token、用 *_swa 头维）
        "kv_true_bytes_at_4096": kv_true,
        "kv_true_gib_at_4096": kv_true_gib,
        "bound_over_true": round(kv_b * 4096 / kv_true, 2) if (kv_b and kv_true) else None,
        "weights_plus_true_kv_gib": (round(weights_gib + kv_true_gib, 3)
                                     if kv_true_gib is not None else None),
        "fits_given_true_kv": (bool((weights_gib + kv_true_gib) * 1024 <= gpu["free_mib"])
                               if (kv_true_gib is not None and gpu) else None),
        "bf16_weights_bytes": hdr["n_params"] * 2,
        "bf16_weights_gib": round(hdr["n_params"] * 2 / 2**30, 2),
        "gpu": gpu,
    }
    print("\n  价格（装不装得下）：两个口径并列，别把上界当需求")
    print(f"    权重 {price['weights_gib']:.3f} GiB")
    print(f"    KV 上界（不认滑窗）{price['kv_bound_gib_at_4096']} GiB @4096 ctx；"
          f"KV 真值（按层，滑窗 1024 + *_swa 头维）{kv_true_gib} GiB @4096 ctx"
          f"（上界/真值 = {price['bound_over_true']} 倍）")
    if gpu:
        print(f"    权重 + KV 真值 = {price['weights_plus_true_kv_gib']} GiB vs 当时空闲 "
              f"{gpu['free_mib'] / 1024:.2f} GiB → "
              f"{'当时可容纳' if price['fits_given_true_kv'] else '塞不下'}；"
              "llama.cpp 的 compute buffer 没算，加它之后是否仍可容纳**未测**")
        print(f"    卡：总 {gpu['total_mib']} MiB / 已用 {gpu['used_mib']} MiB / "
              f"空闲 {gpu['free_mib']} MiB；别的进程占 {gpu['compute_apps_mib']} MiB")
    print(f"    bf16 权重（另一个运行时要的量）= n_params×2 = {price['bf16_weights_gib']} GiB"
          f" > 整张卡 {gpu['total_mib'] / 1024:.1f} GiB" if gpu else
          f"    bf16 权重 = {price['bf16_weights_gib']} GiB")

    gate_failed = all(a["arch_error"] == hdr["arch"] for _n, a in attempts)
    if control_ok and gate_failed:
        verdict, code = "GATE-FAIL", 0
    elif control_ok and not gate_failed:
        verdict, code = "GATE-OPEN", 1
    else:
        verdict, code = "GATE-UNINFORMATIVE", 1
    print(f"\n  结论：{verdict}")
    if verdict == "GATE-FAIL":
        print("    运行时在架构查表处拒绝该文件，且负控能加载 → 这是非测量，不是低分。")
    elif verdict == "GATE-OPEN":
        print("    有运行时接受了这个架构 → 对照可能已可做，本子项目的结论必须重判。")
    else:
        print("    负控没加载起来 → 加载器没有区分力，本次「加载失败」不构成证据。")

    if record:
        facts = {
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "writer": "python3 gate.py --record",
            "model": MODEL, "control": CONTROL,
            "runners": bins,
            "header": {k: hdr[k] for k in ("arch", "n_params", "file_bytes", "data_bytes",
                                          "data_offset", "n_tensors", "bpw_file",
                                          "bpw_tensors", "gguf_version", "alignment")},
            "header_meta": {k: hdr["meta"].get(k) for k in
                            ("block_count", "embedding_length", "expert_count",
                             "expert_used_count", "context_length", "attention.causal",
                             "attention.sliding_window", "attention.shared_kv_layers",
                             "attention.key_length", "attention.value_length",
                             "diffusion.canvas_length")},
            "control_header": {k: ctl[k] for k in ("arch", "n_params", "file_bytes")},
            "attempts": [a for _n, a in attempts],
            "control_attempt": control, "control_ok": control_ok,
            "price": price, "verdict": verdict,
        }
        FIXTURE.parent.mkdir(exist_ok=True)
        FIXTURE.write_text(json.dumps(facts, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        print(f"  → 已写入 {FIXTURE.relative_to(HERE.parent.parent.parent.parent)}")
    return code


if __name__ == "__main__":
    sys.exit(main(tuple(sys.argv[1:])))
