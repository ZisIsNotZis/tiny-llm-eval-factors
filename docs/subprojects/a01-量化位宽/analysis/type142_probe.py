#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a01 WP4 的加载试验：三元/极低位宽文件能不能被当前 llama.cpp 加载（ggml type 142 等）。

`plan.yaml::plan2`（原始文字）要查两件事：`Q2_0` 的加载失败、`PQ2_0`（= ggml type 142）是否需要更新的
llama.cpp。这两件事是**加载器的性质**，不是模型质量，所以用一个极小的生成探针就够：起服 → 等 health →
发一条 8 token 的补全 → 关服；起不来就把 stderr 尾部原文记下来（那才是证据）。

并发例外：需求 ≤4 GB、≤3 分钟。所以只有小文件（1.7B 三元 ≈ 0.5 GB）能现在跑；27B 的 `PQ2_0`
（≈7–9 GB）必须等大段落锁结束。

    python3 "docs/subprojects/a01-量化位宽/analysis/type142_probe.py" /home/z/hf/Ternary-Bonsai-1.7B-Q2_0_g64.gguf
    python3 ".../type142_probe.py"            # 默认跑 1.7B Q2_0

结果追加进 `analysis/type142_probe.json`（同一文件多次调用会累加，按 gguf 去重）。
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
SERVER = "/home/z/.local/bin/llama-server"
OUT = os.path.join(HERE, "type142_probe.json")
DEFAULT = "/home/z/hf/Ternary-Bonsai-1.7B-Q2_0_g64.gguf"
NEED_MIB = 2048
BUDGET_S = 170


def free_mib():
    return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True).stdout.split()[0])


def peak_vram(pid):
    for line in subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                                "--format=csv,noheader,nounits"],
                               capture_output=True, text=True).stdout.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[0] == str(pid) and parts[1].isdigit():
            return int(parts[1])
    return 0


def main(argv):
    gguf = argv[0] if argv else DEFAULT
    rec = {"gguf": gguf, "exists": os.path.isfile(gguf),
           "size_bytes": os.path.getsize(gguf) if os.path.isfile(gguf) else None,
           "free_mib_before": free_mib(), "need_mib": NEED_MIB}
    if not rec["exists"]:
        rec.update(verdict="BLOCKED：文件不存在")
        return _save(rec, 4)
    if rec["free_mib_before"] < NEED_MIB + 2048:
        rec.update(verdict=f"BLOCKED：空闲显存 {rec['free_mib_before']} < 需求 {NEED_MIB}+2048")
        return _save(rec, 4)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    flags = [SERVER, "-m", gguf, "--port", str(port), "--host", "127.0.0.1",
             "-c", "512", "-np", "1", "-ngl", "99"]
    rec["server_flags"] = " ".join(flags[1:])
    t0 = time.time()
    logp = os.path.join(REPO, ".wrapup", f"a01_type_probe_{os.path.basename(gguf)}.log")
    with open(logp, "w") as fh:
        proc = subprocess.Popen(flags, stdout=fh, stderr=fh)
        ok = False
        while time.time() - t0 < BUDGET_S:
            if proc.poll() is not None:
                break
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read()
                ok = True
                break
            except Exception:
                time.sleep(2)
        rec["elapsed_s"] = round(time.time() - t0, 1)
        rec["peak_vram_mib"] = peak_vram(proc.pid)
        if ok:
            try:
                body = json.dumps({"prompt": "The number after 41 is", "max_tokens": 8, "temperature": 0}).encode()
                req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/completions", data=body,
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    d = json.loads(r.read())
                rec["generated"] = d["choices"][0]["text"]
                rec["verdict"] = "加载并生成：当前 llama.cpp 能读这个文件"
            except Exception as exc:
                rec["verdict"] = f"加载成功但生成失败：{exc}"
        else:
            tail = subprocess.run(["tail", "-25", logp], capture_output=True, text=True).stdout.split("\n")
            rec["stderr_tail"] = [l for l in tail if l.strip()][-12:]
            rec["verdict"] = ("加载失败：见 stderr_tail（原文）" if proc.poll() is not None
                              else f"{BUDGET_S}s 内没起来：见 stderr_tail")
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
    rec["free_mib_after"] = free_mib()
    rec["log"] = os.path.relpath(logp, REPO)
    return _save(rec, 0 if ok else 1)


def _save(rec, code):
    data = {"results": []}
    if os.path.isfile(OUT):
        try:
            data = json.load(open(OUT, encoding="utf-8"))
        except ValueError:
            pass
    data.setdefault("results", [])
    data["results"] = [r for r in data["results"] if r.get("gguf") != rec["gguf"]] + [rec]
    data["_note"] = ("加载器性质测试：Q2_0 / PQ2_0(ggml type 142) 能不能被当前 llama.cpp 读。"
                     "小文件按并发例外（≤4 GB / ≤3 分钟）跑，27B 的 PQ2_0 要等大段落锁。")
    json.dump(data, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: rec.get(k) for k in ("gguf", "size_bytes", "elapsed_s", "peak_vram_mib",
                                              "free_mib_before", "verdict")}, ensure_ascii=False, indent=1))
    if rec.get("stderr_tail"):
        print("\n".join(rec["stderr_tail"]))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
