#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a01 WP3::T4 —— 「分数低的那一格」的复现负控（GPU，≤3 分钟，按 registry 的并发例外跑）。

问题：Qwen3.5-2B 的 `UD-Q2_K_XL` 在 HumanEval+ 上比 `UD-IQ3_XXS` 低 22 题（`RESULT.md::b1-heplus-only`）。
T4 只回答一件事：**这 22 题（IQ3 判过、Q2 判不过的那批）的生成是不是可复现的？**
可复现 ⇒ 那个差不可能是「同配置跑两次的随机噪声」；不可复现 ⇒ 该格的值本身不稳定，`b1-heplus-only` 必须降级。

设计（不需要重跑 164 题，也不需要谁的口径与我一致）：

  1. 取「争议题」= IQ3 的 plus_status 为 pass 且 Q2 为 fail 的题（现算，不写死），再加一组对照组
     （两格都 pass 的题）——对照组证明这条路线在该文件上能生成正常完成物，不是全线崩坏。
  2. 同一台 server、同一套历史旗标（`-c 8192 -np 1 -ngl 99 --jinja --reasoning off`）、同一提示构造
     （evalplus 自己的 `task["prompt"].strip() + "\\n"` + `OpenAIChatDecoder`）、贪心，把这批题**跑两遍**。
  3. 判据先写死：两遍逐字节相同 ⇒ 可复现；不同 ⇒ 不可复现，并记下翻转的题。
  4. 附带的旁证：两遍的完成物与 `.wrapup/mres/m64.../humaneval/*.raw.jsonl` 里的历史完成物逐字节比。

并发例外（`docs/plan/subprojects.md` 的「GPU 并发例外」）：需求 ≈2 GB、预算 ≤3 分钟、空闲显存 ≥ 需求 + 2 GB、
起服后断言 `n_slots`、把「并行于谁、实测占用」写进记录。不满足就以 exit 4 退出（那不是测量）。

用法：
    setsid nohup python3 "docs/subprojects/a01-量化位宽/analysis/gpu_t4.py" > .wrapup/a01_t4.out 2>&1 &
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))
SERVER = "/home/z/.local/bin/llama-server"
EVALPY = os.path.join(REPO, ".wrapup", "evalpy", "bin", "python")
OUTDIR = os.path.join(REPO, ".wrapup", "mres", "a01-t4")
RESULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "t4_result.json")


def free_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.split()
    return int(out[0])


def server_vram(pid):
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    for line in out.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[0] == str(pid):
            return int(parts[1])
    return 0


def wait_ready(port, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read()
            return True
        except Exception:
            time.sleep(1)
    return False


def disputed_ids():
    """IQ3 判过、Q2 判不过的题号（现算）。"""
    def st(tag):
        f = glob.glob(os.path.join(REPO, ".wrapup", "mres", tag, "codegen", "humaneval",
                                   "*_eval_results.json"))[0]
        E = json.load(open(f, encoding="utf-8"))["eval"]
        return {k: v[0]["plus_status"] for k, v in E.items()}

    a = st("m63-qwen-2b-iq3xxs")
    b = st("m64-qwen-2b-q2kxl")
    bad = sorted(int(k.split("/")[1]) for k in a if a[k] == "pass" and b.get(k) == "fail")
    good = sorted(int(k.split("/")[1]) for k in a if a[k] == "pass" and b.get(k) == "pass")
    return bad, good


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", default="/home/z/hf/Qwen3.5-2B-UD-Q2_K_XL.gguf")
    ap.add_argument("--port", type=int, default=8917)
    ap.add_argument("--controls", type=int, default=8)
    ap.add_argument("--need-mib", type=int, default=2048)
    a = ap.parse_args(argv)

    os.makedirs(OUTDIR, exist_ok=True)
    bad, good = disputed_ids()
    # 对照组：取争议题里最小的 8 个「两格都过」的题，按题号排序，位置固定
    ctrl = good[: a.controls]
    ids = sorted(set(bad) | set(ctrl))
    log = {"gguf": a.gguf, "port": a.port, "disputed": bad, "controls": ctrl,
           "free_mib_before": free_mib(), "need_mib": a.need_mib, "parallel_with": None,
           "server_flags": None, "n_slots": None, "n_ctx": None, "peak_vram_mib": None,
           "passes": [], "verdict": None}
    others = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader"],
                            capture_output=True, text=True).stdout.strip()
    log["parallel_with"] = others

    if log["free_mib_before"] < a.need_mib + 2048:
        log["verdict"] = f"BLOCKED：空闲显存 {log['free_mib_before']} MiB < 需求 {a.need_mib} + 2048，不是测量"
        json.dump(log, open(RESULT, "w"), ensure_ascii=False, indent=1)
        print(log["verdict"])
        return 4

    flags = [SERVER, "-m", a.gguf, "--port", str(a.port), "--host", "127.0.0.1",
             "-c", "8192", "-np", "1", "-ngl", "99", "--jinja", "--reasoning", "off"]
    log["server_flags"] = " ".join(flags[1:])
    slog = open(os.path.join(OUTDIR, f"server-{a.port}.log"), "w")
    proc = subprocess.Popen(flags, stdout=slog, stderr=slog)
    peak = 0
    try:
        if not wait_ready(a.port):
            log["verdict"] = "server 没起来；见日志"
            json.dump(log, open(RESULT, "w"), ensure_ascii=False, indent=1)
            return 3
        props = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{a.port}/props").read())
        d = props.get("default_generation_settings", {})
        log["n_slots"] = props.get("total_slots")
        log["n_ctx"] = d.get("n_ctx")
        if log["n_slots"] != 1 or log["n_ctx"] != 8192:
            log["verdict"] = f"配置不符（n_slots={log['n_slots']}, n_ctx={log['n_ctx']}），不是测量"
            json.dump(log, open(RESULT, "w"), ensure_ascii=False, indent=1)
            return 5

        t0 = time.time()
        for p in (1, 2):
            target = os.path.join(OUTDIR, f"t4-p{p}.jsonl")
            for f in (target, target.replace(".jsonl", ".raw.jsonl")):
                if os.path.exists(f):
                    os.remove(f)
            code = f'''
import json, sys
from evalplus.data import get_human_eval_plus
from evalplus.provider import make_model
from evalplus.codegen import codegen
tasks = get_human_eval_plus()
ids = {ids!r}
import evalplus.codegen as C
orig = C.get_human_eval_plus
C.get_human_eval_plus = lambda version="default": {{k: v for k, v in orig(version).items()
                                                   if int(k.split("/")[1]) in ids}}
dec = make_model(model={os.path.basename(a.gguf)!r}, backend="openai", dataset="humaneval",
                 temperature=0.0, base_url="http://127.0.0.1:{a.port}/v1",
                 instruction_prefix="Please provide a self-contained Python script that solves the following problem in a markdown code block:",
                 response_prefix="Below is a Python script with a self-contained function that solves the problem and passes corresponding tests:")
codegen({target!r}, dec, "humaneval", greedy=True)
'''
            script = os.path.join(OUTDIR, f"pass{p}.py")
            open(script, "w").write(code)
            r = subprocess.run([EVALPY, script], capture_output=True, text=True, timeout=150)
            print(f"pass{p} rc={r.returncode} {r.stdout[-300:]} {r.stderr[-500:]}")
            log["passes"].append({"pass": p, "rc": r.returncode,
                                  "items": sum(1 for _ in open(target.replace(".jsonl", ".raw.jsonl")))
                                  if os.path.exists(target.replace(".jsonl", ".raw.jsonl")) else 0})
        elapsed = time.time() - t0
        peak = max(peak, server_vram(proc.pid))

        def load(path):
            out = {}
            if os.path.exists(path):
                for line in open(path, encoding="utf-8"):
                    if line.strip():
                        j = json.loads(line)
                        out[j["task_id"]] = j["solution"]
            return out
        p1 = load(os.path.join(OUTDIR, "t4-p1.raw.jsonl"))
        p2 = load(os.path.join(OUTDIR, "t4-p2.raw.jsonl"))
        hist = load(glob.glob(os.path.join(REPO, ".wrapup", "mres", "m64-qwen-2b-q2kxl", "codegen",
                                          "humaneval", "*temp_0.0.raw.jsonl"))[0])
        common = sorted(set(p1) & set(p2))
        same12 = [t for t in common if p1[t] == p2[t]]
        same_hist = [t for t in common if t in hist and p1[t] == hist[t]]
        log.update({
            "elapsed_s": round(elapsed, 1), "n_common": len(common),
            "identical_p1_p2": len(same12),
            "differing": [t for t in common if p1[t] != p2[t]],
            "identical_to_history": len(same_hist),
            "disputed_covered": len([t for t in bad if f"HumanEval/{t}" in common]),
            "verdict": None,
        })
        if len(same12) == len(common) and len(common) == len(ids):
            log["verdict"] = ("可复现：同一文件、同一旗标、同一提示，两遍逐字节相同于全部 "
                              f"{len(common)} 题（其中争议题 {log['disputed_covered']} 道）⇒ 那 22 题的差不是跑两次的随机噪声")
        else:
            log["verdict"] = (f"不可复现或覆盖不全：{len(common)} 题里 {len(same12)} 题逐字节相同，"
                              f"翻转 {log['differing']}")
        json.dump(log, open(RESULT, "w"), ensure_ascii=False, indent=1)
        print(json.dumps({k: log[k] for k in ("elapsed_s", "n_common", "identical_p1_p2",
                                              "disputed_covered", "identical_to_history", "verdict")},
                         ensure_ascii=False, indent=1))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
        slog.close()
        print(f"peak_vram_mib={peak} free_after={free_mib()}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
