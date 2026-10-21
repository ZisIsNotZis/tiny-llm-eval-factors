#!/usr/bin/env python3
"""a08 思考开关：同一模型上「只改 --reasoning」的受控臂，**一次调用只跑一条臂**。

为什么改成一条臂一次调用：一次 `flock` 串六条臂时，第一条失败就把整批吞掉，而排队等锁的进程
既没有输出也不释放位置——2026-10-21 就是这样白等了 27 分钟（`a06` 的厂商臂持锁），
`.tmp/a08_arms.out` 0 字节、`.wrapup/mres/` 下没有任何产物、GPU 侧没有我们的 server。
所以：**持锁时间 = 一条臂的时间**，起服前后各有一次可打红的 preflight。

一条臂 = (task, limit, reasoning, max_gen_toks, ctx)。同一 task 的两条臂除 reasoning 外逐字相同，
所以是「一格换一个开关」，不是「某次重跑」。

复用 `.wrapup/lmeval_run.py`（i02 的量测基础设施）：它负责起服、EchoShim、离线环境变量、
panel json 与 `timings_s` 的写法。本脚本只做它做不到的三件事：
  1. 把 per-task profile 钉成「预算对齐」的那一组（它的 `DEFAULT_PROFILE` 是 1024/8192，且
     `run_panel` 会用 profile 覆盖 CLI 的 `--ctx/--max-gen-toks`，所以只能从 `TASK_PROFILE` 给）；
  2. 起服**前**打一行 `[arm] starting server …`，起服**后** 30 秒内必须拿到 `/props`，
     失败就打印原因并 exit 1 —— 不允许静默持锁；
  3. 端点探针：`--reasoning on/off` 在两个端点上各改了什么，落盘成 `fixtures/endpoint_probe/*.json`
     （否则「开关生效」只是推断）。

用法（一次一条臂，锁等待有上限）：
    bash "docs/subprojects/a08-思考开关/run_arm.sh" a08-gsm8k-off-4096
    bash "docs/subprojects/a08-思考开关/run_arm.sh" --probe
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WR = REPO / ".wrapup"
MRES = WR / "mres"

# 历史 panel（m66gs 等）里记的是老布局的 `/home/z/hf/mscache/unsloth/...`，那个目录已经不在；
# 现在可用的是 `/home/z/hf/` 下的符号链接（指向 models--unsloth--Qwen3.5-2B-GGUF 的 snapshot）。
MODEL = os.environ.get("A08_MODEL", "/home/z/hf/Qwen3.5-2B-UD-Q4_K_XL.gguf")
LLAMA = os.environ.get("LLAMA_SERVER", "/home/z/.local/bin/llama-server")
LLAMA_PORT = int(os.environ.get("A08_LLAMA_PORT", "8910"))
SHIM_PORT = int(os.environ.get("A08_SHIM_PORT", "8911"))

# (tag, task, limit, reasoning, max_gen_toks, ctx)
# 每条臂的预估（2B Q4，加载 ≈20 s，生成 ≈300 token/s，prompt 侧 5-shot ≈1100 token/题）：
#   gsm8k off @4096   ≈ 3 min（关思考答案短）
#   mmlu  off/on @16  ≈ 3 min/臂（对数似然，不生成）
#   ifeval off @25    ≈ 3 min
#   ifeval on  @25    ≈ 8–10 min（思考串把 4096 预算吃掉，是这一轴唯一贵的臂）
#   gsm8k on @4096    ≈ 11 min（100 题 × ≈1990 token，已有 m66gs 同协议格，作复现臂）
ARMS: list[tuple[str, str, int, str, int, int]] = [
    ("a08-gsm8k-off-4096", "gsm8k", 100, "off", 4096, 16384),
    ("a08-mmlu-off-16", "mmlu", 16, "off", 1024, 8192),
    ("a08-mmlu-on-16", "mmlu", 16, "on", 1024, 8192),
    ("a08-ifeval-off-25", "ifeval", 25, "off", 4096, 8192),
    ("a08-ifeval-on-25", "ifeval", 25, "on", 4096, 8192),
    ("a08-gsm8k-on-4096", "gsm8k", 100, "on", 4096, 16384),
]
BY_TAG = {a[0]: a for a in ARMS}


def load_lmeval_run():
    spec = importlib.util.spec_from_file_location("lmeval_run_a08", str(WR / "lmeval_run.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def note(row: dict) -> None:
    path = HERE / "fixtures" / "arm_runs.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a") as fh:
        if new:
            fh.write("tag\ttask\tlimit\treasoning\tmax_gen_toks\tctx\trc\tstarted\tfinished\n")
        fh.write("\t".join(str(row[k]) for k in
                           ("tag", "task", "limit", "reasoning", "max_gen_toks", "ctx", "rc",
                            "started", "finished")) + "\n")


def preflight_server(tag: str, port: int, log: Path) -> None:
    """起服后的证明：30 秒内 `/props` 必须答 200，且 server 自报 `n_slots = 1`。

    两件事都做不到就打印原因并 exit 1：一个起不来的 server 不许把持锁的进程留在那里。
    """
    import requests

    why = []
    try:
        r = requests.get(f"http://127.0.0.1:{port}/props", timeout=30)
        ok = r.status_code == 200 and isinstance(r.json(), dict)
        if not ok:
            why.append(f"/props status={r.status_code}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        why.append(f"/props: {exc!r}")
    text = log.read_text(errors="replace") if log.exists() else ""
    if "n_slots = 1," not in text:
        ok = False
        why.append("server.log 里没有 `n_slots = 1,`（-np 1 未生效）")
    print(f"[arm {tag}] preflight: props_ok={ok} port={port}", flush=True)
    if not ok:
        tail = "\n".join(text.splitlines()[-20:])
        print(f"[arm {tag}] PREFLIGHT FAILED: {'; '.join(why)}\n--- server.log tail ---\n{tail}",
              flush=True)
        raise SystemExit(1)


def assert_single_slot(tag: str) -> None:
    """跑完再断言一次（起服与结束各一次，日志被轮换也能抓）。"""
    log = MRES / tag / "server.log"
    text = log.read_text(errors="replace") if log.exists() else ""
    if "n_slots = 1," not in text:
        raise SystemExit(f"{tag}: server.log 里没有 `n_slots = 1`，作废该次测量（{log}）")


def run_arm(tag: str, task: str, limit: int, reasoning: str, mgt: int, ctx: int) -> int:
    lr = load_lmeval_run()  # 每条臂一份新模块：TASK_PROFILE 与 globals 都从干净状态起
    lr.TASK_PROFILE[task] = {"reasoning": reasoning, "max_gen_toks": mgt, "ctx": ctx}
    lr.CTX_SIZE = ctx
    lr.MAX_GEN_TOKS = mgt
    argv = ["lmeval_run.py", "--model", MODEL, "--tag", tag, "--tasks", task,
            "--limit", str(limit), "--reasoning", reasoning,
            "--llama-bin", LLAMA,
            "--llama-port", str(LLAMA_PORT), "--shim-port", str(SHIM_PORT)]
    if task == "mmlu":
        argv += ["--mmlu-limit", str(limit)]
    started = f"{time.time():.0f}"
    print(f"[arm {tag}] starting server: model={Path(MODEL).name} task={task} limit={limit} "
          f"reasoning={reasoning} max_gen_toks={mgt} ctx={ctx} port={LLAMA_PORT}", flush=True)
    # 起服前先把端口前提说清楚：端口被占时 lmeval_run 会 SystemExit，这里给出同一事实
    preflight_ports_ok = True
    listening = subprocess.run(["ss", "-ltnH"], capture_output=True, text=True).stdout
    for p in (LLAMA_PORT, SHIM_PORT):
        if f":{p} " in listening:
            print(f"[arm {tag}] PREFLIGHT FAILED: 端口 {p} 已被占用（ss -ltnH）", flush=True)
            preflight_ports_ok = False
    if not preflight_ports_ok:
        note({"tag": tag, "task": task, "limit": limit, "reasoning": reasoning,
              "max_gen_toks": mgt, "ctx": ctx, "rc": "port-busy", "started": started,
              "finished": f"{time.time():.0f}"})
        return 1
    # 起服后的 preflight 挂在 run_panel 会调用的那个函数上：它起完服、还没开始跑基准时，
    # 我们在 30 秒内用 `/props` 证明这个 server 真的活着，并把 `n_slots = 1` 断言在日志里。
    orig_start = lr.start_llama

    def start_with_preflight(binary, model, port, logfile, reasoning="off"):
        proc = orig_start(binary, model, port, logfile, reasoning)
        preflight_server(tag, port, logfile)
        return proc

    lr.start_llama = start_with_preflight
    sys.argv = argv
    rc = lr.main()
    if (MRES / tag / "server.log").exists():
        assert_single_slot(tag)
    note({"tag": tag, "task": task, "limit": limit, "reasoning": reasoning,
          "max_gen_toks": mgt, "ctx": ctx, "rc": rc, "started": started,
          "finished": f"{time.time():.0f}"})
    print(f"[arm {tag}] rc={rc}", flush=True)
    return rc


def endpoint_probe() -> None:
    """`--reasoning on/off` 在两个端点上各改了什么：落盘原始响应，不作推断。

    chat/completions 是生成类基准（gsm8k、ifeval）走的路；completions 是对数似然类
    （mmlu/arc/truthfulqa）经 EchoShim 走的路。两处都取证，才能说「这一类的分数里
    有没有思考成分」。
    """
    import requests

    out = HERE / "fixtures" / "endpoint_probe"
    out.mkdir(parents=True, exist_ok=True)
    lr = load_lmeval_run()
    log = out / "probe_server.log"
    lr.CTX_SIZE = 8192
    for reasoning in ("off", "on"):
        print(f"[probe] starting server: reasoning={reasoning} ctx=8192 port={LLAMA_PORT}",
              flush=True)
        proc = lr.start_llama(LLAMA, MODEL, LLAMA_PORT, log, reasoning)
        try:
            preflight_server("probe-" + reasoning, LLAMA_PORT, log)
            chat = requests.post(
                f"http://127.0.0.1:{LLAMA_PORT}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Natalia sold 48 clips in April and half as many in May. How many clips did she sell in total? Answer with the number only."}],
                      "max_tokens": 512, "temperature": 0}, timeout=1800).json()
            comp = requests.post(
                f"http://127.0.0.1:{LLAMA_PORT}/v1/completions",
                json={"prompt": "The answer to 2+2 is", "max_tokens": 64,
                      "temperature": 0, "logprobs": 3}, timeout=1800).json()
            (out / f"chat_{reasoning}.json").write_text(json.dumps(chat, indent=1))
            (out / f"completions_{reasoning}.json").write_text(json.dumps(comp, indent=1))
            print(f"[probe] reasoning={reasoning} done", flush=True)
        finally:
            lr.stop_llama(proc, log)
    (out / "README.txt").write_text(
        "每个文件 = 一次真实请求的原始 JSON。chat_* 走生成类基准的端点，completions_* 走\n"
        "对数似然类的端点（EchoShim 从 top_logprobs 读真 logprob）。差分判据见 RESULT.md。\n"
        "两次请求都只改 server 启动参数 `--reasoning off|on`，提示词逐字相同。\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", default=[],
                    help="只跑这条臂（tag）；可重复。默认全部（不要在共享锁下这样用）")
    ap.add_argument("arms", nargs="*", default=[],
                    help="同上，位置写法（run_arm.sh 用这个）：a08-ifeval-on-25")
    ap.add_argument("--probe", action="store_true", help="先跑端点探针")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check-model", action="store_true",
                    help="只检查模型路径存在（不需要 GPU/锁）；run_arm.sh 在排锁之前调它")
    a = ap.parse_args()
    if a.check_model:
        ok = Path(MODEL).exists()
        print(f"{'ok' if ok else 'MISSING'}: {MODEL} -> {os.path.realpath(MODEL)}")
        return 0 if ok else 1
    if a.list:
        for tag, task, limit, reasoning, mgt, ctx in ARMS:
            print(f"{tag}\t{task}\tlimit={limit}\treasoning={reasoning}\t"
                  f"max_gen_toks={mgt}\tctx={ctx}")
        return 0
    if not Path(MODEL).exists():
        raise SystemExit(f"模型不存在：{MODEL}")
    if a.probe:
        endpoint_probe()
        if not (a.arm or a.arms):   # `--probe` 单独用 = 只跑探针；要跑臂必须显式点名
            return 0
    wanted = list(a.arm) + list(a.arms)
    if wanted:
        unknown = [t for t in wanted if t not in BY_TAG]
        if unknown:
            raise SystemExit(f"未知臂：{unknown}；可用：{sorted(BY_TAG)}")
        arms = [BY_TAG[t] for t in wanted]
    else:
        arms = ARMS
    rc = 0
    for arm in arms:
        rc = run_arm(*arm) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
