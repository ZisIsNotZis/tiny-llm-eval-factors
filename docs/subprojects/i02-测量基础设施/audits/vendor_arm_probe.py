#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""厂商推荐采样臂的服务端负控：同 seed 重复 → 全同；只改一个参数 → 必须不同。

形状（a06 实测）：llama.cpp 每次请求按 seed 重置 RNG，所以 **temp>0 两次输出可以逐字相同**，
「两次不一样」不是判据。正确判据是：
  1. 同 seed、同五参数重复两次 → 输出逐字相同（说明 seed 真的生效）；
  2. 只把 presence_penalty 2.0 → 0.0 → 输出必须不同（说明这个参数真的进了采样）；
  3. `/props` 的服务端默认 temperature（a06 实测 0.8）与我们传的 1.0 不同，记下来作为负控的旁证。

用法（必须持全局 GPU 锁）：
    bash .wrapup/gpu_locked.sh python3 "docs/subprojects/i02-测量基础设施/audits/vendor_arm_probe.py"
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

MODEL = "/home/z/hf/Qwen3.5-2B-UD-Q2_K_XL.gguf"
SERVER = "/home/z/.local/bin/llama-server"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor_arm_probe.json")
VENDOR = {"temperature": 1.0, "top_p": 1.00, "top_k": 20, "min_p": 0.0, "presence_penalty": 2.0}
PROMPT = "List the first 40 positive integers, separated by commas. No other words."


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_ready(port, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read()
            return True
        except Exception:
            time.sleep(1)
    return False


def post(port, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def main():
    if not os.path.exists(MODEL):
        raise SystemExit(f"模型不存在：{MODEL}")
    port = free_port()
    log = open("/tmp/vendor_arm_probe_server.log", "w")
    proc = subprocess.Popen([SERVER, "-m", MODEL, "-c", "8192", "-np", "1", "--port", str(port),
                             "--host", "127.0.0.1", "-fa", "on"], stdout=log, stderr=log)
    try:
        if not wait_ready(port):
            raise SystemExit("server 没起来；见 /tmp/vendor_arm_probe_server.log")
        props = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/props").read())
        defaults = props.get("default_generation_settings", {})
        base = {"model": "x", "messages": [{"role": "user", "content": PROMPT}],
                "max_tokens": 64, "seed": 1234, **VENDOR}
        a = post(port, base)["choices"][0]["message"]["content"]
        b = post(port, base)["choices"][0]["message"]["content"]
        c = post(port, {**base, "presence_penalty": 0.0})["choices"][0]["message"]["content"]
        d = post(port, {**base, "top_k": 1})["choices"][0]["message"]["content"]
        e = post(port, {**base, "temperature": 0.0})["choices"][0]["message"]["content"]
        ev = {
            "model": MODEL,
            "server_defaults": {k: defaults.get(k) for k in
                                ("temperature", "top_p", "top_k", "min_p", "presence_penalty",
                                 "n_ctx", "n_predict") if k in defaults},
            "request": base,
            "same_seed_twice_identical": a == b,
            "presence_penalty_change_changes_output": a != c,
            "top_k_change_changes_output": a != d,
            "temperature_change_changes_output": a != e,
            "outputs": {"a": a, "b": b, "c": c, "d_top_k1": d, "e_temp0": e},
        }
        # 判据：同 seed 重复必须相同；且**至少一个**单参数改动必须改输出（证明参数进了采样）
        ok = ev["same_seed_twice_identical"] and (
            ev["presence_penalty_change_changes_output"] or ev["top_k_change_changes_output"])
        ev["verdict"] = "PASS" if ok else "FAIL"
        json.dump(ev, open(OUT, "w"), ensure_ascii=False, indent=1)
        print(json.dumps({k: ev[k] for k in ("server_defaults", "same_seed_twice_identical",
                                             "presence_penalty_change_changes_output",
                                             "top_k_change_changes_output",
                                             "temperature_change_changes_output", "verdict")},
                         ensure_ascii=False))
        print("evidence:", OUT)
        return 0 if ok else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
