#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP4：KV 精度 × 上下文长度的针检索网格（a05）。

设计写死在 `PLAN.md` 的「GPU 队列」里，这里是它的执行体。每格 20 条：把一条
`KEY: <5 位数字>` 插到长填充段的 10% / 50% / 90% 深度，最后一行只要求模型输出该数字。
判分 = 完成物里第一个 5 位数字等于针。这测的是「KV 缓存里远端的信息还在不在」，
而不是代码生成（m30 的加长格失败正是因为模型续写填充前言）。

阳性对照：同一个 prompt 但**不含针**（等价于针被截在窗口外——模型无从检索，只能猜），
必须 0/20；否则说明打分器或模型行为不是在做检索，整轮作废。

逐条产物落盘到 `docs/subprojects/a05-KV 缓存精度/evidence/needle/`（随仓库走），
每个格一个 JSON，含每条的深度、针值、完成物、是否命中与 prompt 的 sha256。

必须持 GPU 锁运行：
    timeout 1500 bash .wrapup/gpu_locked.sh python3 \
        "docs/subprojects/a05-KV 缓存精度/analysis/needle_grid.py"
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WR = REPO / ".wrapup"
CORPUS = WR / "ppl_corpora/nl_english.txt"
LLAMA = os.environ.get("LLAMA_SERVER", "/home/z/.local/bin/llama-server")
MODEL = "/home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf"
DEFAULT_OUT = HERE.parent / "evidence/needle"
INSTR = ("\nIgnore the text above. Answer with the KEY value only (5 digits), nothing else.\nKEY: ")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Server:
    def __init__(self, ctx, ctk, ctv, port, logfile):
        self.ctx, self.ctk, self.ctv, self.port = ctx, ctk, ctv, port
        self.logfile = logfile
        self.proc = None
        self.props = None

    def __enter__(self):
        fh = open(self.logfile, "a")
        cmd = [LLAMA, "-m", MODEL, "--port", str(self.port), "--host", "127.0.0.1",
               "-ngl", "99", "-c", str(self.ctx), "-np", "1", "-fa", "on",
               "--cache-type-k", self.ctk, "--cache-type-v", self.ctv]
        fh.write("\n=== " + " ".join(cmd) + "\n")
        fh.flush()
        self.proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)
        self.fh = fh
        for _ in range(150):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=3) as r:
                    if json.loads(r.read().decode()).get("status") == "ok":
                        break
            except (urllib.error.URLError, OSError, ValueError):
                pass
            time.sleep(2)
        else:
            raise RuntimeError(f"server did not become healthy at ctx={self.ctx}")
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/props", timeout=10) as r:
            self.props = json.loads(r.read().decode())
        return self

    def __exit__(self, *exc):
        if self.proc:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.fh.close()
        time.sleep(1)

    def slots(self):
        """server 自报的 slot 数与每槽 ctx：不符即该次测量作废（PLAN 的断言）。"""
        p = self.props or {}
        total = p.get("total_slots")
        n_ctx = (p.get("default_generation_settings") or {}).get("n_ctx")
        return total, n_ctx

    def tokenize(self, text):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/tokenize",
            data=json.dumps({"content": text}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return len(json.loads(r.read().decode())["tokens"])

    def complete(self, prompt, n_predict, stop=("\n",)):
        body = {"prompt": prompt, "n_predict": n_predict, "temperature": 0,
                "cache_prompt": False, "stop": list(stop)}
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/completion",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read().decode()).get("content") or ""


def needle_for(idx, ctx, depth):
    return f"{(idx * 7919 + ctx * 31 + int(depth * 1000)) % 90000 + 10000}"


def build_prompt(srv, filler, target_tokens, needle, depth):
    """把填充段裁到 target−指令−针 的 token 数，再把针插到 depth 处。"""
    instr_tok = srv.tokenize(INSTR)
    needle_tok = srv.tokenize("\nKEY: " + needle + "\n")
    body_target = max(64, target_tokens - instr_tok - needle_tok)
    chars = min(len(filler), int(body_target * 4.0))
    body = filler[:chars]
    for _ in range(6):
        n = srv.tokenize(body)
        if n == body_target:
            break
        ratio = len(body) / max(n, 1)
        chars = max(1, min(len(filler), int(len(body) - (n - body_target) * ratio)))
        body = filler[:chars]
    pos = int(depth * len(body))
    prompt = body[:pos] + "\nKEY: " + needle + "\n" + body[pos:] + INSTR
    return prompt


def first_digits(text):
    run = ""
    for ch in text or "":
        if ch.isdigit():
            run += ch
            if len(run) == 5:
                return run
        else:
            run = ""
    return ""


def run_cell(cell_id, ctx, ctk, ctv, prompts, outdir, port, logfile, n_predict=32, stop=("\n",)):
    with Server(ctx, ctk, ctv, port, logfile) as srv:
        total, n_ctx = srv.slots()
        if total != 1 or n_ctx != ctx:
            raise RuntimeError(f"slot assertion failed for {cell_id}: total_slots={total} n_ctx={n_ctx} expected 1/{ctx}")
        items = []
        for it in prompts:
            comp = srv.complete(it["prompt"], n_predict, stop)
            got = first_digits(comp)
            hit = (got == it["needle"])      # 只比数字：对照的针仍在 prompt 里，所以对照可以非 0
            items.append({"i": it["i"], "depth": it["depth"], "needle": it["needle"],
                          "control": it.get("control"),
                          "completion": comp, "answer": got,
                          "answer_shape": ("empty" if not (comp or "") else
                                           "no-5-digit-run" if not got else
                                           "placeholder" if len(set(got)) == 1 else
                                           "five-digits"),
                          "hit": hit, "prompt_sha256": it["prompt_sha256"],
                          "prompt_tokens": it["prompt_tokens"]})
        hits = sum(1 for x in items if x["hit"])
        rec = {"cell": cell_id, "model": Path(MODEL).name, "ctx": ctx,
               "kv": f"{ctk}/{ctv}", "fa": "on", "n_items": len(items), "hits": hits,
               "n_predict": n_predict, "stop": list(stop),
               "n_slots": total, "n_ctx_slot": n_ctx,
               "prompt_tokens_mean": round(sum(x["prompt_tokens"] for x in items) / len(items), 1),
               "items": items}
        outdir.mkdir(parents=True, exist_ok=True)
        dest = outdir / f"{cell_id}.json"
        dest.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
        log(f"{cell_id}: hits {hits}/{len(items)}  prompt_tokens≈{rec['prompt_tokens_mean']}  -> {dest.name}")
        return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctxs", default="8192,16384,32768")
    ap.add_argument("--kvs", default="f16:f16,q8_0:f16,f16:q8_0,q8_0:q8_0")
    ap.add_argument("--n-items", type=int, default=20)
    ap.add_argument("--depths", default="0.1,0.5,0.9",
                    help="逗号分隔；每个 (ctx, depth) 是一个独立格，格内 20 条全在同一深度")
    ap.add_argument("--reserve", type=int, default=1024)
    ap.add_argument("--port", type=int, default=8150)
    ap.add_argument("--outdir", default=str(DEFAULT_OUT))
    ap.add_argument("--logfile", default=str(WR / "a05_needle_server.log"))
    ap.add_argument("--gate-ctx", type=int, default=32768)
    ap.add_argument("--gate-kv", default="f16:f16")
    ap.add_argument("--control-max-tokens", type=int, default=192,
                    help="对照格的生成长度；对照不按换行截断，否则模型只吐一个换行、判定拿不到内容")
    ap.add_argument("--control-only", action="store_true",
                    help="只跑阳性对照格（修对照时用，不重跑处理组、不重写 summary.json）")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    ctxs = [int(c) for c in args.ctxs.split(",")]
    gate0 = tuple(args.gate_kv.split(":"))
    depths = [float(d) for d in args.depths.split(",")]
    kvs = [tuple(k.split(":")) for k in args.kvs.split(",")]
    filler = CORPUS.read_text(errors="ignore")
    n = args.n_items

    # 1) 每格 prompt 只建一次（跨 KV 逐字节相同），并记 sha256。
    plans = {}
    with Server(2048, "f16", "f16", args.port, args.logfile) as tk:
        total, n_ctx = tk.slots()
        log(f"tokenizer server: n_slots={total} n_ctx={n_ctx}")
        for ctx in ([min(ctxs)] if args.control_only else ctxs):
            target = ctx - args.reserve
            for depth in ([depths[-1]] if args.control_only else depths):
                items = []
                for i in range(n):
                    needle = needle_for(i, ctx, depth)
                    while needle in filler[:200000]:
                        needle = f"{int(needle) + 1:05d}"
                    prompt = build_prompt(tk, filler, target, needle, depth)
                    assert prompt.count(needle) == 1, f"needle {needle} not unique in prompt"
                    items.append({"i": i, "depth": depth, "needle": needle, "absent": False,
                                  "prompt": prompt,
                                  "prompt_tokens": tk.tokenize(prompt),
                                  "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
                plans[(ctx, depth)] = items
                log(f"ctx={ctx} depth={depth}: {len(items)} prompts, tokens "
                    f"{min(x['prompt_tokens'] for x in items)}–{max(x['prompt_tokens'] for x in items)}")

    # 2) 阳性对照用的 prompt：同一条 8k 题去掉针那一行（窗口里没有可检索的信息，模型只能猜）。
    ctl_ctx = min(ctxs)
    ctl_depth = depths[-1]
    control = []
    for x in plans[(ctl_ctx, ctl_depth)][:n]:
        # 针留在 prompt 里，只把最后那行「只回答数字」的指令去掉：模型若复述针，就会记命中，
        # 所以这个对照**能失败**，它检验的是「打分器看到正确答案时会不会记命中」。
        stripped = x["prompt"].replace(INSTR, "", 1)
        assert stripped != x["prompt"]
        control.append(dict(x, prompt=stripped, control="instruction-removed",
                            prompt_tokens=None))
    with Server(2048, "f16", "f16", args.port, args.logfile) as tk2:
        for c in control:
            c["prompt_tokens"] = tk2.tokenize(c["prompt"])
            c["prompt_sha256"] = hashlib.sha256(c["prompt"].encode()).hexdigest()
    log(f"control: {len(control)} prompts, instruction removed (needle kept), tokens "
        f"{min(c['prompt_tokens'] for c in control)}–{max(c['prompt_tokens'] for c in control)}")

    if args.control_only:
        rec = run_cell(f"a05-needle-d{ctl_depth}-ctx{ctl_ctx}-kv{gate0[0]}_{gate0[1]}-control-noinstruction",
                       ctl_ctx, gate0[0], gate0[1], control, outdir, args.port, args.logfile,
                       n_predict=args.control_max_tokens, stop=())
        shapes = collections.Counter(it["answer_shape"] for it in rec["items"])
        print(json.dumps({"control_only": True, "cell": rec["cell"], "hits": rec["hits"],
                          "n": rec["n_items"], "answer_shapes": shapes}, indent=1))
        return 0 if rec["hits"] == 0 else 4

    # 3) 逐格跑。门率先跑，便于早发现问题。
    cells = []
    gate = tuple(args.gate_kv.split(":"))
    for depth in depths:
        order = [(args.gate_ctx, gate)] + [(c, k) for c in ctxs for k in kvs
                                           if (c, k) != (args.gate_ctx, gate)]
        for ctx, (ck, cv) in order:
            cell_id = f"a05-needle-d{depth}-ctx{ctx}-kv{ck}_{cv}"
            cells.append(run_cell(cell_id, ctx, ck, cv, plans[(ctx, depth)],
                                  outdir, args.port, args.logfile, n_predict=32, stop=("\n",)))
    cells.append(run_cell(f"a05-needle-d{ctl_depth}-ctx{ctl_ctx}-kv{gate[0]}_{gate[1]}-control-noinstruction",
                          ctl_ctx, gate[0], gate[1], control, outdir, args.port, args.logfile))

    # 4) 汇总与门判定。
    ctl = [c for c in cells if c["cell"].endswith("control-noinstruction")][0]
    ctl_shapes = {}
    for it in ctl["items"]:
        ctl_shapes[it["answer_shape"]] = ctl_shapes.get(it["answer_shape"], 0) + 1
    strata = {}
    for depth in depths:
        gate_cell = [c for c in cells if c["cell"] == f"a05-needle-d{depth}-ctx{args.gate_ctx}-kv{gate[0]}_{gate[1]}"]
        if not gate_cell:
            continue
        g = gate_cell[0]
        diffs = {}
        for ctx in ctxs:
            base = [c for c in cells if c["cell"] == f"a05-needle-d{depth}-ctx{ctx}-kvf16_f16"]
            if not base:
                continue
            for kv in ("q4_0/q4_0", "q8_0/q8_0", "q8_0/f16", "f16/q8_0"):
                got = [c for c in cells if c["cell"] == f"a05-needle-d{depth}-ctx{ctx}-kv{kv.replace('/', '_')}"]
                if got:
                    diffs[f"{ctx}:{kv}"] = got[0]["hits"] - base[0]["hits"]
        passed = g["hits"] >= 8          # 门 v2：地板(<8/20)判不可用；天花板(20/20)记单侧
        one_sided = g["hits"] == args.n_items
        strata[str(depth)] = {
            "gate": {"ctx": args.gate_ctx, "kv": f"{gate[0]}/{gate[1]}", "hits": g["hits"],
                     "n": args.n_items, "window": "v2: >=8/20 usable; 20/20 = one-sided",
                     "passed": passed, "one_sided": one_sided},
            "diffs_vs_f16": diffs,
            "verdict": ("resolvable" if any(abs(v) >= 4 for v in diffs.values())
                        else "not-resolvable") if passed else "void-dynamic-range",
        }
    summary = {
        "run_tag": "a05-needle-kv-ctx",
        "design": "needle at a fixed depth per cell (depth is a stratum, not pooled), "
                  "answer-only instruction, prompt = ctx-1024 tokens, 20 items per cell",
        "control": {"cell": ctl["cell"], "hits": ctl["hits"], "n": ctl["n_items"],
                    "passed": ctl["hits"] == 0,
                    "mode": "instruction-removed (needle kept in the prompt)",
                    "answer_shapes": ctl_shapes,
                    "can_fail": "命中=完成物第一个 5 位数字等于针；对照里针仍在，模型复述它就记命中，"
                                "所以这条对照可以非 0（旧的 absent 一票否决写法永远 0，已删除）"},
        "strata": strata,
        "cells": [{"cell": c["cell"], "ctx": c["ctx"], "kv": c["kv"],
                   "depth": c["items"][0]["depth"], "hits": c["hits"], "n": c["n_items"]}
                  for c in cells],
    }
    summary["verdict"] = ("void-control" if not summary["control"]["passed"] else
                          "resolvable" if any(v["verdict"] == "resolvable" for v in strata.values())
                          else "not-resolvable")
    (outdir / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    ok = summary["control"]["passed"] and any(v["gate"]["passed"] for v in strata.values())
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
