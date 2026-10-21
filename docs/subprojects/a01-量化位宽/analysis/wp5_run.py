#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a01 WP5 —— gemma-4-12B 原生档 MMLU 的 GPU 复测（同一 shim、同一协议、独立起服两次）。

问题（`PLAN.md` 的 plan7b）：`gemma-4-12b-it-UD-Q4_K_XL.gguf` 的 MMLU 记成 0.6436，而更低位宽的
`UD-Q3_K_XL` 是 0.4178、QAT 的 `UD-Q4_K_XL` 是 0.4463——涨 22.6 pp，同期其它基准几乎不动
（`RESULT.md::gemma12b-mmlu-uniform`）。这一格历史上只有**一次**测量，所以判据只能靠复测：

  * 两次都稳定在 0.6436 附近（±0.02）⇒ 这一格的性质，异常是「这个文件在这个指标上真的更好」
    或「MMLU 这条通道在两个文件上不一致」——后者仍需生成式对照，另行排队；
  * 任一次明显偏离（|Δ| > 0.05）⇒ 该格作废，报告里的 22.6 pp 必须撤。

复现的历史配置（`.wrapup/mres/m141-native-gemma12b-q4/cmd.txt` 与 `lmeval_mmlu.log` 首行）：
`--model gguf --model_args base_url=…,max_length=8192 --tasks mmlu --limit 16`，即 57 科目 × 16 = 912 题；
server 由 `.wrapup/lmeval_run.py` 起（`-c 8192 -np 1 -ngl 99 --jinja --reasoning off`）。

用法（必须持全局 GPU 锁，一次跑两次独立起服）：
    bash .wrapup/gpu_locked.sh python3 "docs/subprojects/a01-量化位宽/analysis/wp5_run.py"
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
GGUF = "/home/z/hf/mscache/unsloth/gemma-4-12B-it-GGUF/gemma-4-12b-it-UD-Q4_K_XL.gguf"
RUNNER = os.path.join(REPO, ".wrapup", "lmeval_run.py")
PY = os.path.join(REPO, ".wrapup", "lmenv", "bin", "python")
LLAMA = "/home/z/.local/bin/llama-server"
OUT = os.path.join(HERE, "wp5_result.json")
HIST = 0.643640350877193            # 库里 m141 当时的值
TOL = 0.05


def free_mib():
    return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True).stdout.split()[0])


class Sampler(threading.Thread):
    """每 3 s 记一次总占用与各进程占用，取最大值。"""

    def __init__(self):
        super().__init__(daemon=True)
        self.peak_total = 0
        self.peak_proc = 0
        self.stop = False

    def run(self):
        while not self.stop:
            try:
                used = int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                                           "--format=csv,noheader,nounits"],
                                          capture_output=True, text=True).stdout.split()[0])
                self.peak_total = max(self.peak_total, used)
                for line in subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                                            "--format=csv,noheader,nounits"],
                                           capture_output=True, text=True).stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) == 2 and parts[1].isdigit():
                        self.peak_proc = max(self.peak_proc, int(parts[1]))
            except Exception:
                pass
            time.sleep(3)


def read_score(tag):
    """从 lmeval_run.py 的产物里取 mmlu 的分数与题数。"""
    import glob
    for pat, key in ((os.path.join(REPO, ".wrapup", "mres", tag, "lmeval_panel.json"), "panel"),
                     (os.path.join(REPO, ".wrapup", "mres", tag, "lmeval_mmlu_*.json"), "lm_eval")):
        for p in sorted(glob.glob(pat)):
            d = json.load(open(p, encoding="utf-8"))
            if key == "panel":
                sc = (d.get("tasks") or {}).get("mmlu")
                if sc is not None:
                    return sc, (d.get("n") or {}).get("mmlu"), p
            else:
                r = d.get("results", {})
                root = r.get("mmlu") or {}
                if "acc,none" in root:
                    ns = d.get("n-samples", {})
                    n = sum(v.get("effective", 0) for v in ns.values()) if isinstance(ns, dict) else None
                    return root["acc,none"], n, p
    return None, None, None


def main():
    sampler = Sampler()
    log = {"gguf": GGUF, "runner": os.path.relpath(RUNNER, REPO),
           "historical_value": HIST, "tolerance": TOL,
           "free_mib_before": free_mib(), "runs": [], "peak_total_mib": None, "peak_proc_mib": None,
           "verdict": None}
    if not os.path.isfile(GGUF):
        log["verdict"] = f"BLOCKED：模型文件不存在 {GGUF}"
        json.dump(log, open(OUT, "w"), ensure_ascii=False, indent=1)
        print(log["verdict"])
        return 4
    sampler.start()
    try:
        for r in (1, 2):
            tag = f"a01-wp5-r{r}"
            t0 = time.time()
            out = os.path.join(REPO, ".wrapup", f"a01_wp5_r{r}.out")
            with open(out, "w") as fh:
                rc = subprocess.run([PY, RUNNER, "--model", GGUF, "--tag", tag, "--tasks", "mmlu",
                                     "--limit", "16", "--llama-bin", LLAMA],
                                    stdout=fh, stderr=subprocess.STDOUT, cwd=REPO).returncode
            score, n, src = read_score(tag)
            rec = {"run": r, "tag": tag, "rc": rc, "score": score, "n_items": n,
                   "elapsed_s": round(time.time() - t0, 1),
                   "source": os.path.relpath(src, REPO) if src else None,
                   "log": os.path.relpath(out, REPO)}
            log["runs"].append(rec)
            json.dump(log, open(OUT, "w"), ensure_ascii=False, indent=1)   # 每跑完一次就落盘
            print(f"run{r}: rc={rc} score={score} n={n} {rec['elapsed_s']}s")
    finally:
        sampler.stop = True
        sampler.join(timeout=10)
        log["peak_total_mib"] = sampler.peak_total
        log["peak_proc_mib"] = sampler.peak_proc
        scores = [x["score"] for x in log["runs"] if x["score"] is not None]
        if len(scores) == 2:
            dev = [round(s - HIST, 4) for s in scores]
            stable = all(abs(d) <= TOL for d in dev)
            log["deviations"] = dev
            log["verdict"] = ("稳定：两次都是 " + " / ".join(f"{s:.4f}" for s in scores) +
                              f"，与历史 {HIST:.4f} 差 {dev}（容差 ±{TOL}）⇒ 这一格是文件的性质，"
                              "22.6 pp 不是单次测量噪声；剩下未排除的是「MMLU 这条似然通道在这两个文件上是否同条件」，需生成式对照"
                              if stable else
                              "不稳定：" + " / ".join(f"{s:.4f}" for s in scores) +
                              f"，与历史 {HIST:.4f} 差 {dev} ⇒ 该格作废，报告里的 22.6 pp 必须撤")
        else:
            log["verdict"] = f"未完成：只有 {len(scores)}/2 次拿到分数，不是测量"
        json.dump(log, open(OUT, "w"), ensure_ascii=False, indent=1)
        print(json.dumps({k: log[k] for k in ("free_mib_before", "peak_total_mib", "peak_proc_mib",
                                              "deviations", "verdict")} if "deviations" in log
                         else {k: log[k] for k in ("free_mib_before", "peak_total_mib", "peak_proc_mib",
                                                   "verdict")}, ensure_ascii=False, indent=1))
    return 0 if len(log["runs"]) == 2 and all(x["score"] is not None for x in log["runs"]) else 1


if __name__ == "__main__":
    sys.exit(main())
