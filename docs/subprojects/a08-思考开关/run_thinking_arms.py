#!/usr/bin/env python3
"""a08 思考开关：同一模型上「只改 --reasoning」的受控臂。

轴的判据是「同一格、同一预算下，只切换 server 的 --reasoning」。历史格全都把思考关掉，
唯一的 on 格（13 个 gsm8k）跑在 max_gen_toks=4096 而对应的 off 格是 1024，所以那 13 对
**预算混淆**，不能直接读成思考效应。本脚本补上预算对齐的一侧，并把 ifeval（抽取类）和
mmlu（对数似然类）也各跑一对，使每一类基准都有自己的开/关对照。

一条臂 = (task, limit, reasoning, max_gen_toks, ctx)。同一 task 的两条臂除 reasoning 外
逐字相同，所以是「一格换一个开关」，不是「某次重跑」。

复用 `.wrapup/lmeval_run.py`（i02 的量测基础设施）：它负责起服、断言端口、EchoShim、
离线环境变量、panel json 与 timings_s 的写法。本脚本只做两件它做不到的事：
  1. 把 per-task profile 钉成「预算对齐」的那一组（它的 DEFAULT_PROFILE 是 1024/8192，
     且 run_panel 会用 profile 覆盖 --ctx/--max-gen-toks，所以只能从 TASK_PROFILE 给）；
  2. 开跑前先对两个端点各发一次真实请求，把 `--reasoning on/off` 到底改了什么落盘成证据
     （`fixtures/endpoint_probe/*.json`），否则「开关生效」只是推断。

用法（必须在 GPU 锁下）：
    bash .wrapup/gpu_locked.sh python3 "docs/subprojects/a08-思考开关/run_thinking_arms.py"

每一步都追加一行到 `fixtures/arm_runs.tsv`（tag、臂参数、退出码、时间戳）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WR = REPO / ".wrapup"
MRES = WR / "mres"

MODEL = os.environ.get(
    "A08_MODEL", "/home/z/hf/mscache/unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-UD-Q4_K_XL.gguf")
LLAMA = os.environ.get("LLAMA_SERVER", "/home/z/.local/bin/llama-server")
LLAMA_PORT = int(os.environ.get("A08_LLAMA_PORT", "8910"))
SHIM_PORT = int(os.environ.get("A08_SHIM_PORT", "8911"))

# (tag, task, limit, reasoning, max_gen_toks, ctx)
# 顺序 = 价值顺序：先把便宜的、判据最强的一侧落地，最贵的复现臂放最后。
ARMS: list[tuple[str, str, int, str, int, int]] = [
    ("a08-gsm8k-off-4096", "gsm8k", 100, "off", 4096, 16384),
    ("a08-ifeval-off-50", "ifeval", 50, "off", 4096, 8192),
    ("a08-mmlu-off-16", "mmlu", 16, "off", 1024, 8192),
    ("a08-mmlu-on-16", "mmlu", 16, "on", 1024, 8192),
    ("a08-ifeval-on-50", "ifeval", 50, "on", 4096, 8192),
    ("a08-gsm8k-on-4096", "gsm8k", 100, "on", 4096, 16384),
]


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


def assert_single_slot(tag: str) -> None:
    """起服后断言 server 自报的 n_slots 与 -np 1 相符；不符即作废该次测量。"""
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
    sys.argv = argv
    rc = lr.main()
    if (MRES / tag / "server.log").exists():
        assert_single_slot(tag)
    note({"tag": tag, "task": task, "limit": limit, "reasoning": reasoning,
          "max_gen_toks": mgt, "ctx": ctx, "rc": rc, "started": started,
          "finished": f"{time.time():.0f}"})
    print(f"[a08] arm {tag}: rc={rc}", flush=True)
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
    for reasoning in ("off", "on"):
        lr.CTX_SIZE = 8192
        proc = lr.start_llama(LLAMA, MODEL, LLAMA_PORT, log, reasoning)
        try:
            text = log.read_text(errors="replace")
            if "n_slots = 1," not in text:
                raise SystemExit("probe: server 未自报 n_slots = 1，作废该次探针")
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
            print(f"[a08] probe reasoning={reasoning} done", flush=True)
        finally:
            lr.stop_llama(proc, log)
    # /props 是 server 的默认参数，不证明单次请求生效；记下来只作环境快照
    (out / "README.txt").write_text(
        "每个文件 = 一次真实请求的原始 JSON。chat_* 走生成类基准的端点，completions_* 走\n"
        "对数似然类的端点（EchoShim 从 top_logprobs 读真 logprob）。差分判据见 RESULT.md。\n"
        "两次请求都只改 server 启动参数 `--reasoning off|on`，提示词逐字相同。\n")


def main() -> int:
    if not Path(MODEL).exists():
        raise SystemExit(f"模型不存在：{MODEL}")
    if "--probe-only" not in sys.argv:
        endpoint_probe()
    for arm in ARMS:
        rc = run_arm(*arm)
        if rc != 0:
            print(f"[a08] arm {arm[0]} 退出码 {rc}，继续跑后续臂（失败的臂在 RESULT 里记未得数）",
                  flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
