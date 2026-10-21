#!/usr/bin/env python3
"""a07 WP2/WP3：本装置内的字节负控 + 草稿的运行期显存成本。

一个 server 会话一个臂，旗标与历史 spec panel 完全一致（`-c 8192 -np 1 -ngl 99 --jinja
--reasoning off`），只有 `--spec-type`/`--spec-draft-n-max` 变。每个臂跑同一批 humanEval 164 题
（evalplus codegen + evaluate，greedy），并把完成物原文落到 `<out>/codegen/<arm>/`。

回答两件事：

  * 字节负控（WP2）：`none` 两次 → 两份完成物逐字节相同吗？相同则「本装置在不开投机时字节地板 = 0」，
    `RESULT.md::byte-identity-fails` 的差异可以归因到投机这条路径；不同则字节地板未知，那一条只能依赖 i01。
  * 运行期显存（WP3）：起服前后 `nvidia-smi` 的数值差 + llama-server 自己的 pid 占用，n0 与 n2 并列，
    与「MTP 头的权重字节差」分开记（权重是文件口径，这是运行期口径）。

必须在锁下跑：`A07_GPU_LOCKED=1 bash .wrapup/gpu_locked.sh python3 <本脚本> …`；
没设这个变量就退出 2（防止有人直接前台起服抢显存）。

用法：
    A07_GPU_LOCKED=1 bash .wrapup/gpu_locked.sh python3 \
        "docs/subprojects/a07-投机解码/run_ident_control.py" \
        --model /home/z/hf/Qwen3.5-9B-UD-Q4_K_XL.gguf --tag m166-spec-ident \
        --arms none,none,draft-mtp:2
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
WR = REPO / ".wrapup"
EVALPLUS = WR / "evalpy/bin/evalplus.codegen"
EVALPLUS_EV = WR / "evalpy/bin/evalplus.evaluate"
RUNS_JSONL = HERE / "evidence" / "spec-runs.jsonl"   # 逐臂追加的进度账本（随仓库走）
PIDFILE = WR / "a07_ident.pid"
LLAMA = os.environ.get("LLAMA_SERVER", "/home/z/.local/bin/llama-server")
PANEL_T0 = time.time()
OFFLINE = dict(os.environ, HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1", TRANSFORMERS_OFFLINE="1")


def log(msg, path):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(path, "a") as fh:
        fh.write(line + "\n")


def free_port(start=8900, span=100):
    listening = subprocess.run(["ss", "-ltnH"], capture_output=True, text=True).stdout
    for port in range(start, start + span):
        if f":{port} " in listening:
            continue
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit("no free port")


def smi(fields):
    out = subprocess.run(["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip()
    return [x.strip() for x in out.splitlines()]


def smi_procs():
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                          "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
    procs = {}
    for line in out.strip().splitlines():
        if "," in line:
            pid, mib = line.split(",")
            procs[int(pid.strip())] = int(mib.strip())
    return procs


def start_server(model, port, arm, logfile):
    if arm == "none":
        spec = ["--spec-type", "none"]
    else:
        kind, depth = arm.split(":")
        spec = ["--spec-type", kind, "--spec-draft-n-max", depth]
    cmd = [LLAMA, "-m", model, "--port", str(port), "--host", "127.0.0.1",
           "-c", "8192", "-np", "1", "-ngl", "99", "--jinja", "--reasoning", "off", *spec]
    log("llama-server: " + " ".join(cmd), logfile)
    fh = open(logfile, "a")
    proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True,
                            env=OFFLINE, preexec_fn=_die_with_parent)
    PIDFILE.write_text(f"{proc.pid}\n")
    t0 = time.time()
    while time.time() - t0 < 300:
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3).read().decode().find('"ok"') >= 0:
                # 客户端活着必须被看见：health 之后再验一次 /props，30 秒内拿不到就算这个臂失败。
                props = urllib.request.urlopen(f"http://127.0.0.1:{port}/props", timeout=10).read()
                if not props:
                    raise SystemExit("server: /props 空响应")
                return proc
        except SystemExit:
            raise
        except Exception:
            pass
        if proc.poll() is not None:
            raise SystemExit(f"server died rc={proc.returncode}")
        time.sleep(1)
    raise SystemExit("server never healthy（300 s 内 /health 未 ok）")


def _die_with_parent():
    """子进程（llama-server）在父进程死掉时被内核杀掉：孤儿 server 吃显存的根治手段。"""
    import ctypes
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    PR_SET_PDEATHSIG = 1
    libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)


def arm_artifacts(arm_dir):
    """一个臂的产物是否真的落盘：raw 完成物行数 + 判决文件。返回 (ok, 原因)。"""
    raws = list((arm_dir / "humaneval").glob("*_openai_temp_0.0.raw.jsonl"))
    evs = list((arm_dir / "humaneval").glob("*_eval_results.json"))
    if not raws:
        return False, "没有 raw 完成物"
    n = sum(1 for _ in open(raws[0], encoding="utf-8"))
    if n == 0:
        return False, f"raw 完成物 0 行（{raws[0].name}）"
    if not evs:
        return False, f"有 {n} 条完成物但没有 *_eval_results.json"
    return True, f"{n} 条完成物 + 判决"


def append_run_row(row):
    """逐臂追加一行到仓库内的进度账本；被中断时它写着跑到了哪一格。"""
    if str(row.get("tag", "")).endswith("-test"):
        return                    # 守则演练（guard test）不进测量账本，它的记录在 PLAN 里
    RUNS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNS_JSONL, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def stop_server(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


def run(cmd, logfile, timeout=900):
    """跑一个子进程；超时杀**整个进程组**（subprocess 的 timeout 只杀父进程，孙进程会活下来）。"""
    with open(logfile, "a") as fh:
        fh.write("# " + " ".join(cmd) + "\n")
        fh.flush()
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                start_new_session=True, env=OFFLINE)
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            fh.write(f"# TIMEOUT after {timeout}s, process group {proc.pid} killed\n")
            return 124


def one_arm(model, port, arm, tag, arm_dir, logfile, vram_only=False, hold_seconds=0.0):
    """起服 → 量显存 → （可选）跑 humanEval → 收完成物与判决。返回一行记录。"""
    row = {"arm": arm}
    try:
        proc = start_server(model, port, arm, logfile)
    except SystemExit as exc:      # 起服失败（例如普通 gguf 没有 MTP 层）是这个臂的结论，不是整批的失败
        row["error"] = str(exc)
        return row
    try:
        used = smi("memory.used,memory.free")
        procs = smi_procs()
        row["gpu_used_mib"] = int(used[0].split(",")[0]) if used else None
        row["gpu_free_mib"] = int(used[0].split(",")[1]) if used else None
        row["server_mib"] = procs.get(proc.pid)
        # 起服后断言 n_slots：spec panel 的历史规矩，不符即作废该臂。
        txt = Path(logfile).read_text(errors="replace")
        m = re.findall(r"load_model: initializing, n_slots = (\d+), n_ctx_slot = (\d+)", txt)
        row["n_slots"] = int(m[-1][0]) if m else None
        row["n_ctx_slot"] = int(m[-1][1]) if m else None

        if hold_seconds:
            log(f"arm {arm}: hold {hold_seconds}s（守则演练）", logfile)
            time.sleep(hold_seconds)
        if vram_only:
            return row
        arm_dir.mkdir(parents=True, exist_ok=True)
        row["gpu_minutes_at_start"] = round((time.time() - PANEL_T0) / 60.0, 2)
        rc = run([str(EVALPLUS), f"{tag}-{arm.replace(':', '')}", "humaneval", "--backend", "openai",
                  "--base_url", f"http://127.0.0.1:{port}/v1", "--temperature", "0.0",
                  "--greedy", "True", "--root", str(arm_dir)], str(arm_dir / "code.log"))
        row["codegen_rc"] = rc
        cands = [p for p in arm_dir.rglob("*_openai_temp_0.0.jsonl") if ".raw." not in p.name]
        if rc == 0 and cands:
            samples = sorted(cands)[0]
            rc2 = run([str(EVALPLUS_EV), "humaneval", "--samples", str(samples)], str(arm_dir / "code.log"))
            row["evaluate_rc"] = rc2
            ev = next(iter(arm_dir.rglob("*_eval_results.json")), None)
            if rc2 == 0 and ev:
                evd = json.load(open(ev))["eval"]
                npass = sum(1 for v in evd.values() for x in (v if isinstance(v, list) else [v])
                            if isinstance(x, dict) and x.get("base_status") == "pass")
                row["humaneval"] = npass / len(evd)
                row["humaneval_n"] = len(evd)
    finally:
        stop_server(proc)
    return row


def identity_report(out, arms, dirs=None):
    """同一 tag 内，第一臂与其余每一臂的逐题完成物逐字节比。

    `dirs` 是每臂的**目录名**（同名臂会拿到 `-r<k>` 后缀）：按臂名取目录会把两次 `none`
    指到同一处，得到「164/164 相同」的假地板（踩过一次）。
    """
    dirs = dirs or [a.replace(":", "") for a in arms]
    base_dir = out / "codegen" / dirs[0]
    base = {}
    for f in glob.glob(str(base_dir / "humaneval" / "*_openai_temp_0.0.raw.jsonl")):
        base = {json.loads(l)["task_id"]: json.loads(l)["solution"] for l in open(f, encoding="utf-8")}
    if not base:
        return []
    rows = []
    for arm, dirname in zip(arms[1:], dirs[1:]):
        d = out / "codegen" / dirname
        cur = {}
        for f in glob.glob(str(d / "humaneval" / "*_openai_temp_0.0.raw.jsonl")):
            cur = {json.loads(l)["task_id"]: json.loads(l)["solution"] for l in open(f, encoding="utf-8")}
        common = [t for t in base if t in cur]
        differ = [t for t in common if base[t] != cur[t]]
        rows.append({"base": arms[0], "arm": arm, "n": len(common),
                     "identical": len(common) - len(differ), "differing": len(differ)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--arms", default="none,none,draft-mtp:2")
    ap.add_argument("--hold-seconds", type=float, default=0.0,
                    help="起服量完显存后停这么多秒再收尾——用来演练「客户端被杀，server 必须跟着死」")
    ap.add_argument("--vram-only", action="store_true",
                    help="只起服量显存，不跑 benchmark（WP3 用它把运行期成本与权重字节分开）")
    args = ap.parse_args()
    if os.environ.get("A07_GPU_LOCKED") != "1":
        print("REFUSED: 必须在 bash .wrapup/gpu_locked.sh 下跑，并设 A07_GPU_LOCKED=1")
        return 2

    out = WR / "mres" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "client.pid").write_text(f"{os.getpid()}\n")   # 客户端自己的 pid：守则演练与排障用
    logfile = str(out / "server.log")
    model = os.path.realpath(args.model)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    port = free_port()
    panel = {"tag": args.tag, "model": model, "arms": arms, "rows": [],
             "gpu_before": smi("memory.used,memory.free"), "errors": [],
             "pid": os.getpid(), "started_at": datetime.now().isoformat(timespec="seconds")}
    global PANEL_T0
    PANEL_T0 = time.time()
    log(f"=== ident control tag={args.tag} model={model} arms={arms} gpu_before={panel['gpu_before']}", logfile)
    dry = 0                       # 连续「没有产物」的臂数
    seen = {}
    for arm in arms:
        # 同名臂必须各有目录：evalplus.codegen 会「接续」已有输出，共用目录的第二次运行会
        # 5 秒跑完并复用上一次的完成物（实测：`none` 的第二臂只花 0.09 分钟、164/164 逐字节相同）。
        k = arm.replace(":", "")
        seen[k] = seen.get(k, 0) + 1
        dirname = k if seen[k] == 1 else f"{k}-r{seen[k]}"
        arm_dir = out / "codegen" / dirname
        t_arm = time.time()
        try:
            row = one_arm(model, port, arm, args.tag, arm_dir, logfile, args.vram_only,
                          args.hold_seconds)
        except Exception as exc:  # noqa: BLE001
            row = {"arm": arm, "error": repr(exc)}
            panel["errors"].append(row)
        row["gpu_minutes"] = round((time.time() - t_arm) / 60.0, 2)
        row["dir"] = dirname
        if not args.vram_only and not row.get("error"):
            ok, why = arm_artifacts(arm_dir)
            row["artifacts"] = why
            row["artifacts_ok"] = ok
            dry = 0 if ok else dry + 1
        panel["rows"].append(row)
        log(f"arm {arm}: {json.dumps(row, ensure_ascii=False)}", logfile)
        append_run_row({"tag": args.tag, "arm": arm, **{k: row.get(k) for k in
                        ("humaneval", "humaneval_n", "n_slots", "artifacts", "artifacts_ok",
                         "gpu_minutes", "error")},
                        "at": datetime.now().isoformat(timespec="seconds")})
        # 每臂落一次盘：被中断时前面跑完的臂仍然可用，不必整批重跑。
        (out / "ident_control.json").write_text(
            json.dumps(panel, indent=2, ensure_ascii=False) + "\n")
        if dry >= 2:
            msg = f"ABORT: 连续 {dry} 个臂没有产物（最后一个原因：{row.get('artifacts')}）——客户端或判分器没在干活"
            log(msg, logfile)
            print(msg)
            append_run_row({"tag": args.tag, "abort": msg,
                            "at": datetime.now().isoformat(timespec="seconds")})
            return 1
    panel["identity"] = [] if args.vram_only else identity_report(
        out, arms, [r.get("dir") for r in panel["rows"]])
    (out / "ident_control.json").write_text(json.dumps(panel, indent=2, ensure_ascii=False) + "\n")
    (out / "DONE").write_text(f"{args.tag} {datetime.now().isoformat(timespec='seconds')}\n")
    print(json.dumps(panel, indent=2, ensure_ascii=False))
    return 0 if not panel["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
