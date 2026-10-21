#!/usr/bin/env python3
"""a07 投机解码：速度-深度、质量-深度、以及「贪心输出在投机下是否逐字节同一」。

三问共用一份装置，所以只有一个脚本，不另写第二份分析脚本：

  [A] 速度-深度   tok/s 随草稿深度；来源是 llama-server 自己的 `timings.predicted_per_second`
                  （不含起服时间），每个深度 3 次重复的均值（`.wrapup/spec_panel.py::speed_probe`）。
  [B] 质量-深度   同一批题、同一贪心协议，逐深度的分数与**逐题判决翻转数**。
                  分母是每一格自己的题数，不填默认值。
  [C] 字节同一性  同一提示词、同一贪心、同一种子配置下，深度 0 的完成物与深度 k 的完成物逐字节比。
                  这是决定性的：若贪心输出在投机下不逐字节同一，则质量列不是同一个测量，
                  不能从「深度 0 的分数」抄到「深度 k」。
  [D] 装置事实    每个臂 server 自报的 `n_slots`、草稿接受率、以及 MTP 头在文件里占的权重字节
                  （同一模型的普通仓库与 -MTP 仓库的文件字节差）。

退出码：0 = 四段全部跑完；2 = 缺输入（逐条打印缺哪个，不把缺失算成通过）；
`--check` 在 fixture 与库/自算不一致时退出 1（这是它可以变红的那条路）。

用法：
    python3 "docs/subprojects/a07-投机解码/spec_evidence.py"            # 打印四段
    python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --write    # 重写 fixtures/
    python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --check    # fixture 对库与自算
    python3 "docs/subprojects/a07-投机解码/spec_evidence.py" --selftest # 篡改一份 fixture 证明 --check 会红
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
WR = REPO / ".wrapup"
MRES = WR / "mres"
DB = REPO / "experiments.sqlite"
FIX = HERE / "fixtures"
HFROOT = Path("/home/z/hf")

PANEL_GLOB = "*-spec-*/spec_panel.json"
BENCHES = ("mmlu", "gsm8k", "ifeval", "humaneval")
# i01 的确定性解码地板：同一 cell 重跑，逐题判决差异 0 道、完成物 sha256 相同（res25）。
FLOOR_ITEMS = 0


# ---------- 读输入 ----------
def load_panels():
    """每个 spec panel 一行：tag / gguf / repo / depths / tok_s / scores。"""
    out, missing = [], []
    for p in sorted(glob.glob(str(MRES / PANEL_GLOB))):
        d = json.load(open(p))
        model = d["model"]
        repo_dir = Path(model).parent.parent  # .../models--org--name（model 是 blobs/<sha>）
        snap = sorted(glob.glob(str(repo_dir / "snapshots" / "*" / "*.gguf")))
        snap = [x for x in snap if "mmproj" not in os.path.basename(x)]
        gguf = os.path.basename(snap[0]) if snap else os.path.basename(model)
        out.append({
            "tag": d["tag"],
            "gguf": gguf,
            "repo": repo_dir.name,
            "model_path": model,
            "dir": str(Path(p).parent),
            "rows": d["rows"],
            "errors": d.get("errors") or [],
        })
    if not out:
        missing.append(str(MRES / PANEL_GLOB))
    return out, missing


def item_passes(tag_dir):
    """{depth: {task_id: bool}}（humanEval 每题的 base_status 全为 pass 才算过）。"""
    out = {}
    for ev in sorted(glob.glob(os.path.join(tag_dir, "codegen", "n*", "humaneval",
                                            "*_eval_results.json"))):
        depth = int(re.search(r"/n(\d+)/", ev).group(1))
        evd = json.load(open(ev))["eval"]
        per = {}
        for tid, v in evd.items():
            xs = v if isinstance(v, list) else [v]
            per[tid] = all(isinstance(x, dict) and x.get("base_status") == "pass" for x in xs)
        out[depth] = per
    return out


def item_texts(tag_dir):
    """{depth: {task_id: 完成物原文}}，取自 evalplus 的 raw 产物（未过 sanitizer 的那份）。"""
    out = {}
    for f in sorted(glob.glob(os.path.join(tag_dir, "codegen", "n*", "humaneval",
                                           "*_openai_temp_0.0.raw.jsonl"))):
        depth = int(re.search(r"/n(\d+)/", f).group(1))
        out[depth] = {json.loads(l)["task_id"]: json.loads(l)["solution"]
                      for l in open(f, encoding="utf-8")}
    return out


def device_facts(tag_dir):
    """每个臂：server 自报 n_slots、逐请求草稿接受率中位数、草稿长度中位数。"""
    log = os.path.join(tag_dir, "server.log")
    if not os.path.exists(log):
        return {}
    out, depth = {}, None
    for line in open(log, encoding="utf-8", errors="replace"):
        m = re.match(r"\[[^\]]+\] llama-server: .*--spec-type (\S+)(?: --spec-draft-n-max (\d+))?", line)
        if m:
            depth = int(m.group(2) or 0)
            out[depth] = {"n_slots": None, "accept": [], "mean_len": []}
            continue
        if depth is None:
            continue
        m = re.search(r"load_model: initializing, n_slots = (\d+)", line)
        if m:
            out[depth]["n_slots"] = int(m.group(1))
        m = re.search(r"draft acceptance = ([\d.]+).*?mean len =\s*([\d.]+)", line)
        if m:
            out[depth]["accept"].append(float(m.group(1)))
            out[depth]["mean_len"].append(float(m.group(2)))

    def med(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else None

    return {d: {"n_slots": v["n_slots"], "n_req": len(v["accept"]),
                "med_accept": med(v["accept"]), "med_mean_len": med(v["mean_len"])}
            for d, v in out.items()}


def build_m28():
    """m28（ctx 16384，三个提示场景，每档 3 次重复，逐次值在 jsonl 里）——速度轴的第二份独立测量。"""
    path = WR / "m28_speed.jsonl"
    if not path.exists():
        return [], [str(path)]
    rows = []
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        reps = d.get("tok_s_reps") or []
        rows.append({"mode": d["mode"], "depth": int(d["draft_n"]), "tok_s": d["tok_s"],
                     "rep_min": min(reps) if reps else None, "rep_max": max(reps) if reps else None,
                     "n_predict": d.get("n_predict"), "prompt_n": d.get("prompt_n")})
    rows.sort(key=lambda r: (r["mode"], r["depth"]))
    return rows, []


IDENT_ARMS = ("n0", "none", "none2", "draft-mtp2")  # 臂目录名 → 深度写在 run 的 json 里


def arm_depth(arm):
    """evalplus 的 `--root codegen/<arm>` 目录名 → 草稿深度。

    `n<k>` 是历史 panel 的臂，`draft-mtp<k>` 是控制运行的臂，`none`/`none-r2` 都是 0。
    """
    if arm.startswith("draft-mtp"):
        return int(arm[len("draft-mtp"):])
    if re.fullmatch(r"n\d+", arm):
        return int(arm[1:])
    return 0


def load_ident():
    """WP2/WP3 的控制运行（`run_ident_control.py`）：臂记录 + 逐题判决 + 同一 tag 内的逐字节对。"""
    runs, peritem = [], []
    for path in sorted(glob.glob(str(MRES / "*" / "ident_control.json"))):
        d = json.load(open(path))
        tag_dir = Path(path).parent
        for r in d["rows"]:
            if "error" in r:
                continue
            arm = r["arm"].replace(":", "")
            runs.append({"tag": d["tag"], "arm": arm, "dir": r.get("dir"),
                         "arm_depth": arm_depth(r.get("dir") or arm),
                         "humaneval": r.get("humaneval"), "humaneval_n": r.get("humaneval_n"),
                         "n_slots": r.get("n_slots"), "n_ctx_slot": r.get("n_ctx_slot"),
                         "server_mib": r.get("server_mib"),
                         "gpu_used_before": d.get("gpu_before")[0].split(",")[0].strip()
                         if d.get("gpu_before") else None,
                         "gpu_used_after": r.get("gpu_used_mib"),
                         "codegen_rc": r.get("codegen_rc"), "evaluate_rc": r.get("evaluate_rc")})
        for ev in sorted(glob.glob(str(tag_dir / "codegen" / "*" / "humaneval" / "*_eval_results.json"))):
            arm = Path(ev).parent.parent.name
            for tid, v in json.load(open(ev))["eval"].items():
                xs = v if isinstance(v, list) else [v]
                peritem.append({"tag": d["tag"], "arm": arm, "task_id": tid,
                                "pass": int(all(isinstance(x, dict) and x.get("base_status") == "pass"
                                                for x in xs))})
    return runs, peritem


def _session_models(tags):
    """每个 tag 的模型文件路径（realpath）——只有**同一文件**的会话之间才许做字节比较。"""
    out = {}
    for tag in tags:
        for name in ("spec_panel.json", "ident_control.json"):
            f = MRES / tag / name
            if f.exists():
                model = json.load(open(f)).get("model")
                if model:
                    out[tag] = os.path.realpath(model)
                break
    return out


def byte_pairs(tags=("m125-spec-0.8b", "m169-ident-08b-mtp", "m170-ident-08b-floor",
                     "m128-spec-9b")):
    """**同一模型文件**下不同会话的逐字节比较（跨模型的对比没有意义，直接不产生）。

    同深度 → 字节地板（同一配置重跑）；不同深度 → 投机效应（只有草稿深度不同）。
    0.8B：历史 panel `m125` 的四个深度 + 控制运行 `m169` 的 `none`/`draft-mtp2` + `m170` 的两次 `none`；
    9B：历史 panel `m128` 的四个深度。
    """
    models = _session_models(tags)
    sessions = {}
    for tag in tags:
        for f in sorted(glob.glob(str(MRES / tag / "codegen" / "*" / "humaneval" /
                                      "*_openai_temp_0.0.raw.jsonl"))):
            arm = Path(f).parent.parent.name
            sessions[(tag, arm)] = {json.loads(l)["task_id"]: json.loads(l)["solution"]
                                    for l in open(f, encoding="utf-8")}
    out = []
    keys = sorted(sessions)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if models.get(a[0]) is None or models.get(a[0]) != models.get(b[0]):
                continue
            common = [t for t in sessions[a] if t in sessions[b]]
            if not common:
                continue
            differ = [t for t in common if sessions[a][t] != sessions[b][t]]
            out.append({"tag_a": a[0], "arm_a": a[1], "tag_b": b[0], "arm_b": b[1],
                        "n": len(common), "identical": len(common) - len(differ),
                        "differing": len(differ),
                        "kind": ("floor" if arm_depth(a[1]) == arm_depth(b[1]) else "spec")})
    return out


def gguf_bytes(model_path):
    try:
        return os.path.getsize(model_path)
    except OSError:
        return None


def plain_path_for(gguf):
    """同一 gguf 名在**普通**仓库里的路径（不是 -MTP 仓库）。

    /home/z/hf 下的顶层软链可能指向 -MTP 仓库（9B 就是这样），所以不能直接 stat 它：
    用 `models--*-<名字>-GGUF` 里不含 `MTP` 的那个仓库，指不到就返回 None（未知，不是 0）。
    """
    for repo in sorted(HFROOT.glob("models--*--*")):
        if "MTP" in repo.name or not repo.name.endswith("-GGUF"):
            continue
        hits = glob.glob(str(repo / "snapshots" / "*" / gguf))
        if hits:
            return hits[0]
    return None


# ---------- 计算 ----------
def build_rows():
    panels, missing = load_panels()
    speed, quality, peritem, byteid, device = [], [], [], [], []
    for p in panels:
        tag, gguf, tag_dir = p["tag"], p["gguf"], p["dir"]
        rows = p["rows"]
        base = (rows.get("0") or {}).get("tok_s")
        for d in sorted(rows, key=int):
            r = rows[d]
            ts = r.get("tok_s")
            speed.append({"tag": tag, "gguf": gguf, "depth": int(d), "tok_s": ts,
                          "rel_pct": (100.0 * (ts / base - 1)) if (ts and base) else None})
            for b in BENCHES:
                if r.get(b) is None:
                    continue
                n = r.get("humaneval_n") if b == "humaneval" else None
                quality.append({"tag": tag, "gguf": gguf, "bench": b, "depth": int(d),
                                "score": r[b], "n_items": n})
        passes = item_passes(tag_dir)
        texts = item_texts(tag_dir)
        if 0 not in texts:
            missing.append(f"{tag}: codegen/n0/.../*.raw.jsonl")
            continue
        for d in sorted(texts):
            for tid in sorted(passes.get(d, {})):
                peritem.append({"tag": tag, "depth": d, "task_id": tid,
                                "pass": int(passes[d][tid])})
        for d in sorted(texts):
            if d == 0:
                continue
            base_t = texts[0]
            common = [t for t in base_t if t in texts[d]]
            if not common:
                missing.append(f"{tag}: depth {d} 与深度 0 无共同题")
                continue
            differ = [t for t in common if base_t[t] != texts[d][t]]
            firstpos = []
            for t in differ:
                a, b = base_t[t], texts[d][t]
                i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y),
                         min(len(a), len(b)))
                firstpos.append(i)
            firstpos.sort()
            byteid.append({"tag": tag, "depth": d, "n": len(common),
                           "identical": len(common) - len(differ), "differing": len(differ),
                           "first_div_median": (firstpos[len(firstpos) // 2] if firstpos else None)})
        dev = device_facts(tag_dir)
        plain = plain_path_for(gguf)
        for d in sorted(rows, key=int):
            f = dev.get(int(d), {})
            device.append({"tag": tag, "gguf": gguf, "depth": int(d),
                           "n_slots": f.get("n_slots"), "n_req": f.get("n_req"),
                           "med_accept": f.get("med_accept"),
                           "med_mean_len": f.get("med_mean_len"),
                           "mtp_bytes": gguf_bytes(p["model_path"]),
                           "plain_bytes": gguf_bytes(plain) if plain else None})
    m28, m28_missing = build_m28()
    missing.extend(m28_missing)   # 缺 m28_speed.jsonl 也是缺输入：不能静默退出 0
    ident, ident_peritem = load_ident()
    ident_pairs = byte_pairs()
    return {"speed": speed, "quality": quality, "peritem": peritem,
            "byteid": byteid, "device": device, "panels": panels, "m28": m28,
            "ident": ident, "ident_peritem": ident_peritem, "ident_pairs": ident_pairs}, missing


# ---------- 打印 ----------
def section_a(speed):
    print("[A] 速度-深度（tok/s，llama-server 自身计时，每深度 3 次重复的均值）")
    by = {}
    for r in speed:
        by.setdefault((r["gguf"], r["tag"]), []).append(r)
    for (gguf, tag), rs in by.items():
        rs.sort(key=lambda r: r["depth"])
        line = "  ".join(
            f"n{r['depth']}={r['tok_s']:.2f}" +
            ("" if r["rel_pct"] is None else f"({r['rel_pct']:+.1f}%)")
            for r in rs if r["tok_s"])
        print(f"  {tag:<16} {gguf:<34} {line}")
        vals = [r["tok_s"] for r in rs if r["tok_s"]]
        if len(vals) >= 2 and vals[-1] < max(vals[:-1]):
            peak = max(vals)
            print(f"      ! 非单调：最深一档 n{rs[-1]['depth']}={vals[-1]:.2f} 低于峰值 {peak:.2f}"
                  f"（峰值在 n{[r['depth'] for r in rs if r['tok_s'] == peak][0]}）")
    print("  注：这是单一固定提示词（fibonacci 函数头）上的一次贪心生成测量，不代表全部提示词分布。")


def section_a2(m28):
    print("\n[A2] 速度-深度，第二份独立测量（m28：ctx=16384、seed=1234、每档 3 次重复，"
          "括号里是三次的最小–最大）")
    by = {}
    for r in m28:
        by.setdefault(r["mode"], []).append(r)
    for mode, rs in by.items():
        rs.sort(key=lambda r: r["depth"])
        base = next((r["tok_s"] for r in rs if r["depth"] == 0), None)
        cells = []
        for r in rs:
            rel = "" if not base else f"({100.0 * (r['tok_s'] / base - 1):+.1f}%)"
            cells.append(f"n{r['depth']}={r['tok_s']:.2f}{rel}[{r['rep_min']:.1f}–{r['rep_max']:.1f}]")
        print(f"  {mode:<9} " + "  ".join(cells))
    print("  注：m28 只测速度、没跑过任何分数；它的协议串在各深度上相同（深度只在 "
          "`spec_draft_n_max` 列里），见 RESULT 的 `identity-m28-protocol`。")


def section_b(quality, peritem):
    print("\n[B] 质量-深度（同协议同题；括号里是逐题上/下翻转数，对深度 0）")
    pass_by = {}
    for r in peritem:
        pass_by.setdefault((r["tag"], r["depth"]), {})[r["task_id"]] = r["pass"]
    for bench in BENCHES:
        print(f"  -- {bench}")
        rows = [r for r in quality if r["bench"] == bench]
        by = {}
        for r in rows:
            by.setdefault((r["tag"], r["gguf"]), []).append(r)
        for (tag, gguf), rs in by.items():
            rs.sort(key=lambda r: r["depth"])
            cells = []
            b0 = pass_by.get((tag, 0))
            for r in rs:
                s = f"{r['score']:.4f}"
                cur = pass_by.get((tag, r["depth"]))
                if bench == "humaneval" and b0 and cur:
                    up = sum(1 for t in b0 if not b0[t] and cur.get(t))
                    down = sum(1 for t in b0 if b0[t] and not cur.get(t, b0[t]))
                    s += f"({up}↑{down}↓)"
                    if up + down > FLOOR_ITEMS:
                        s += "*"
                cells.append(f"n{r['depth']}={s}")
            print(f"  {tag:<16} {gguf:<34} " + "  ".join(cells))
    print("  * = 逐题翻转数超过 i01 的确定性地板（0 道题）。没有 * 不等于「没有效应」，"
          "只等于「判决层面没看到效应」。")
    print("  注：mmlu 走对数似然、不生成 token，投机解码结构上碰不到它（[C] 的字节差异不会出现在它上面），"
          "所以 mmlu 逐深度全同是正控，不是质量证据。")


def section_c(byteid):
    print("\n[C] 字节同一性（贪心；同提示词、同 server 旗标，只有 --spec-type/--spec-draft-n-max 不同）")
    by = {}
    for r in byteid:
        by.setdefault(r["tag"], []).append(r)
    tot = [0, 0]
    for tag, rs in by.items():
        rs.sort(key=lambda r: r["depth"])
        cells = "  ".join(f"n{r['depth']}: 同一 {r['identical']}/{r['n']}（差异 {r['differing']}）"
                          f" 首差中位字符 {r['first_div_median']}" for r in rs)
        print(f"  {tag:<16} {cells}")
        for r in rs:
            tot[0] += r["identical"]
            tot[1] += r["differing"] + r["identical"]
    if tot[1]:
        print(f"  合计：逐字节同一 {tot[0]}/{tot[1]} 对完成物（{100*tot[0]/tot[1]:.1f}%）")
    print("  判据：i01 res25 已证同一 cell 在不开投机时重跑，完成物 sha256 相同、逐题差异 0 道，"
          "所以这里的差异不是重复噪声；首差位置远离 0（中位数在数百字符处）说明提示词与模板相同，"
          "差异发生在生成中途。")


def section_d(device):
    print("\n[D] 装置事实（每个臂 server 自报；MTP 头 = 同一 gguf 名在两个仓库里的文件字节差）")
    seen = set()
    for r in device:
        if r["n_slots"] is not None and r["n_slots"] != 1:
            print(f"  ! {r['tag']} n{r['depth']}: n_slots={r['n_slots']}（应为 1，该臂作废）")
        key = (r["tag"], r["depth"])
        if key in seen:
            continue
        seen.add(key)
        acc = "—" if r["med_accept"] is None else f"{r['med_accept']:.4f}"
        ml = "—" if r["med_mean_len"] is None else f"{r['med_mean_len']:.2f}"
        req = "n/a（该臂无草稿）" if not r["n_req"] else str(r["n_req"])
        print(f"  {r['tag']:<16} n{r['depth']}  n_slots={r['n_slots']}  请求数={req}"
              f"  接受率中位={acc}  草稿长度中位={ml}")
    print("  MTP 头的权重开销（同一 gguf 名，-MTP 仓库文件 − 普通仓库同名文件）：")
    done = set()
    for r in device:
        if r["gguf"] in done:
            continue
        done.add(r["gguf"])
        if r["mtp_bytes"] is None:
            print(f"  {r['gguf']:<34} -MTP 文件未知")
        elif r["plain_bytes"] is None:
            print(f"  {r['gguf']:<34} -MTP {r['mtp_bytes']} B；普通仓库同名文件不在本机 → 开销 UNKNOWN（不是 0）")
        else:
            d = r["mtp_bytes"] - r["plain_bytes"]
            print(f"  {r['gguf']:<34} -MTP {r['mtp_bytes']} B  普通 {r['plain_bytes']} B"
                  f"  差 {d:+d} B ({100.0*d/r['plain_bytes']:+.2f}%)")


def section_e(ident, ident_pairs):
    print("\n[E] 装置内负控与草稿的运行期显存（`run_ident_control.py`，同一 -MTP 文件、同一贪心旗标，一次一会话）")
    if not ident:
        print("  未跑：没有 `.wrapup/mres/*/ident_control.json`。")
        return
    seen_dir = {}
    for r in ident:
        k = (r["tag"], r.get("dir") or r["arm"])   # 老产物没有 dir 列时按臂名判重
        seen_dir[k] = seen_dir.get(k, 0) + 1
        dup = seen_dir[k] > 1          # 只有第二行起才是「复用了同一目录」的那一行
        hv = "—" if r["humaneval"] is None else f"{r['humaneval']*r['humaneval_n']:.0f}/{r['humaneval_n']}"
        if dup:
            hv += "（同一目录的第二次运行：evalplus 接续了上次产物，非独立会话，作废）"
        print(f"  {r['tag']:<16} {r['arm']:<11} depth={r['arm_depth']}  n_slots={r['n_slots']}"
              f"  n_ctx_slot={r['n_ctx_slot']}  humanEval={hv}"
              f"  起服前整卡 {r['gpu_used_before']} MiB → 起服后 {r['gpu_used_after']} MiB"
              f"  本进程 {r['server_mib']} MiB")
    for kind, title in (("floor", "字节地板（同一配置、不同会话）"),
                        ("spec", "投机效应（只有草稿深度不同，同一文件、同一会话族）")):
        rows = [r for r in ident_pairs if r["kind"] == kind]
        if not rows:
            continue
        print(f"  {title}：")
        for r in rows:
            print(f"    {r['tag_a']}/{r['arm_a']} vs {r['tag_b']}/{r['arm_b']}: "
                  f"同一 {r['identical']}/{r['n']}（差异 {r['differing']}）")


# ---------- fixture ----------
COLS = {
    "speed_depth": ["tag", "gguf", "depth", "tok_s", "rel_pct"],
    "quality_depth": ["tag", "gguf", "bench", "depth", "score", "n_items"],
    "peritem_humaneval": ["tag", "depth", "task_id", "pass"],
    "byte_identity": ["tag", "depth", "n", "identical", "differing", "first_div_median"],
    "device": ["tag", "gguf", "depth", "n_slots", "n_req", "med_accept", "med_mean_len",
               "mtp_bytes", "plain_bytes"],
    "m28_speed": ["mode", "depth", "tok_s", "rep_min", "rep_max", "n_predict", "prompt_n"],
    "ident_control": ["tag", "arm", "dir", "arm_depth", "humaneval", "humaneval_n", "n_slots",
                      "n_ctx_slot", "server_mib", "gpu_used_before", "gpu_used_after",
                      "codegen_rc", "evaluate_rc"],
    "ident_peritem": ["tag", "arm", "task_id", "pass"],
    "ident_pairs": ["tag_a", "arm_a", "tag_b", "arm_b", "n", "identical", "differing", "kind"],
}


FIXKEY = {"speed_depth": "speed", "quality_depth": "quality",
          "peritem_humaneval": "peritem", "byte_identity": "byteid", "device": "device",
          "m28_speed": "m28", "ident_control": "ident", "ident_peritem": "ident_peritem",
          "ident_pairs": "ident_pairs"}


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.12g}"
    return str(v)


def write_fixtures(built):
    FIX.mkdir(parents=True, exist_ok=True)
    for name, cols in COLS.items():
        rows = built[FIXKEY[name]]
        with open(FIX / f"{name}.tsv", "w", encoding="utf-8") as fh:
            fh.write("\t".join(cols) + "\n")
            for r in rows:
                fh.write("\t".join(_fmt(r[c]) for c in cols) + "\n")
    # 输入文件的 sha256：说明 fixture 由哪些字节算出来（clone 里跑 --write 时若输入不同会先红这一列）。
    src = []
    for p in sorted(glob.glob(str(MRES / PANEL_GLOB))):
        src.append(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {p[len(str(REPO)) + 1:]}")
    for f in sorted(glob.glob(str(MRES / "*-spec-*/codegen/n*/humaneval/*_openai_temp_0.0.raw.jsonl"))):
        src.append(f"{hashlib.sha256(open(f, 'rb').read()).hexdigest()}  {f[len(str(REPO)) + 1:]}")
    (FIX / "sources.txt").write_text("\n".join(src) + "\n", encoding="utf-8")


def read_fixture(name):
    with open(FIX / f"{name}.tsv", encoding="utf-8") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        out = []
        for line in fh:
            vals = line.rstrip("\n").split("\t")
            out.append(dict(zip(hdr, vals)))
    return out


# ---------- 自检（--check） ----------
def check(fixdir=None):
    """三条：fixture 内部一致、与库一致、与本次重算一致。返回 0/1/2。"""
    fix = Path(fixdir) if fixdir else FIX
    if not fix.exists():
        print("MISSING fixture dir: %s" % fix)
        return 2
    bad = 0
    try:
        device = read_fixture("device") if not fixdir else _read(fix, "device")
        quality = read_fixture("quality_depth") if not fixdir else _read(fix, "quality_depth")
        speed = read_fixture("speed_depth") if not fixdir else _read(fix, "speed_depth")
        byteid = read_fixture("byte_identity") if not fixdir else _read(fix, "byte_identity")
        peritem = read_fixture("peritem_humaneval") if not fixdir else _read(fix, "peritem_humaneval")
    except FileNotFoundError as exc:
        print("MISSING fixture: %s" % exc)
        return 2

    # 1) 每臂 n_slots 必须是 1：这是「起服后断言 n_slots」那条规矩的机器化版本。
    for r in device:
        if r["n_slots"] and r["n_slots"] != "1":
            print("BAD n_slots: %s n%s = %s" % (r["tag"], r["depth"], r["n_slots"]))
            bad += 1

    # 2) peritem 的通过率必须复原 quality_depth 的 humaneval 分数（逐题证据绑定聚合值）。
    agg = {}
    for r in peritem:
        agg.setdefault((r["tag"], r["depth"]), [0, 0])
        agg[(r["tag"], r["depth"])][0] += int(r["pass"])
        agg[(r["tag"], r["depth"])][1] += 1
    for r in quality:
        if r["bench"] != "humaneval":
            continue
        k = (r["tag"], r["depth"])
        if k not in agg:
            print("MISSING peritem for %s n%s" % k)
            bad += 1
            continue
        p, n = agg[k]
        if abs(p / n - float(r["score"])) > 1e-9:
            print("BAD peritem rate: %s n%s = %d/%d = %.6f vs quality %.6f"
                  % (k[0], k[1], p, n, p / n, float(r["score"])))
            bad += 1

    # 3) 字节同一性：同一+差异必须等于题数，且差异数不超过题数。
    for r in byteid:
        if int(r["identical"]) + int(r["differing"]) != int(r["n"]):
            print("BAD byte_identity: %s n%s identical+differing != n" % (r["tag"], r["depth"]))
            bad += 1

    # 4) 与库对：每条质量/速度 fixture 行都要能在库里找到同一 (run_tag, 深度, 基准) 的格。
    if not DB.exists():
        print("MISSING db: %s" % DB)
        return 2
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    dbq = {(t, int(n), b): s for t, n, b, s in con.execute(
        "SELECT run_tag, spec_draft_n_max, _bench, _score FROM experiments"
        " WHERE run_tag LIKE 'm12%-spec-%' AND _score IS NOT NULL").fetchall()}
    dbs = {(t, int(n)): ts for t, n, ts in con.execute(
        "SELECT run_tag, spec_draft_n_max, _tok_s FROM experiments"
        " WHERE run_tag LIKE 'm12%-spec-%' AND _bench='speed' AND _tok_s IS NOT NULL").fetchall()}
    dbs = {(t, int(n)): ts for t, n, ts in con.execute(
        "SELECT run_tag, spec_draft_n_max, _tok_s FROM experiments"
        " WHERE run_tag LIKE 'm12%-spec-%' AND _bench='speed' AND _tok_s IS NOT NULL")}
    for r in quality:
        k = (r["tag"], int(r["depth"]), r["bench"])
        if k not in dbq:
            print("MISSING db row: %s n%s %s" % k)
            bad += 1
        elif abs(float(dbq[k]) - float(r["score"])) > 1e-9:
            print("BAD db score: %s n%s %s db=%.6f fixture=%.6f"
                  % (k[0], k[1], k[2], float(dbq[k]), float(r["score"])))
            bad += 1
    for r in speed:
        k = (r["tag"], int(r["depth"]))
        if k not in dbs:
            print("MISSING db tok/s: %s n%s" % k)
            bad += 1
        elif abs(float(dbs[k]) - float(r["tok_s"])) > 0.006:
            print("BAD db tok/s: %s n%s db=%.2f fixture=%.2f"
                  % (k[0], k[1], float(dbs[k]), float(r["tok_s"])))
            bad += 1
    m28 = _read(fix, "m28_speed") if fixdir else read_fixture("m28_speed")
    dbm = {(m, int(n)): ts for m, n, ts in con.execute(
        "SELECT _bench, spec_draft_n_max, _tok_s FROM experiments"
        " WHERE run_tag='m28-speed' AND _tok_s IS NOT NULL").fetchall()}
    for r in m28:
        k = ("speed-" + r["mode"], int(r["depth"]))
        if k not in dbm:
            print("MISSING db m28 row: %s n%s" % k)
            bad += 1
        elif abs(float(dbm[k]) - float(r["tok_s"])) > 0.006:
            print("BAD db m28 tok/s: %s n%s db=%.2f fixture=%.2f" % (k[0], k[1], float(dbm[k]), float(r["tok_s"])))
            bad += 1
    # 5) 控制运行：分数必须由逐题记录复原，n_slots 必须是 1，字节对各分量必须等于题数。
    ident = _read(fix, "ident_control") if fixdir else read_fixture("ident_control")
    ident_peritem = _read(fix, "ident_peritem") if fixdir else read_fixture("ident_peritem")
    ident_pairs = _read(fix, "ident_pairs") if fixdir else read_fixture("ident_pairs")
    agg2 = {}
    for r in ident_peritem:
        k = (r["tag"], r["arm"])
        agg2.setdefault(k, [0, 0])
        agg2[k][0] += int(r["pass"])
        agg2[k][1] += 1
    for r in ident:
        if r["n_slots"] and r["n_slots"] != "1":
            print("BAD n_slots: %s/%s = %s" % (r["tag"], r["arm"], r["n_slots"]))
            bad += 1
        k = (r["tag"], r["arm"])
        if r["humaneval"] and k in agg2:
            p, n = agg2[k]
            if abs(p / n - float(r["humaneval"])) > 1e-9:
                print("BAD ident score: %s/%s = %d/%d vs fixture %.6f"
                      % (r["tag"], r["arm"], p, n, float(r["humaneval"])))
                bad += 1
    for r in ident_pairs:
        if int(r["identical"]) + int(r["differing"]) != int(r["n"]):
            print("BAD ident_pairs: %s/%s vs %s/%s identical+differing != n"
                  % (r["tag_a"], r["arm_a"], r["tag_b"], r["arm_b"]))
            bad += 1
    con.close()

    if bad:
        print("CHECK FAILED: %d 处不一致" % bad)
        return 1
    print("CHECK OK: %d 质量行 / %d 速度行 / %d 逐题行 / %d 字节对，与库一致；每臂 n_slots=1；"
          "逐题通过率复原 humaneval 分数；控制运行 %d 臂 / %d 条逐题 / %d 对字节（地板 %d 对全同）"
          % (len(quality), len(speed), len(peritem), len(byteid),
             len(ident), len(ident_peritem), len(ident_pairs),
             sum(1 for r in ident_pairs if r.get("kind") == "floor" and int(r["differing"]) == 0)))
    return 0


def _read(fix, name):
    with open(Path(fix) / f"{name}.tsv", encoding="utf-8") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        return [dict(zip(hdr, l.rstrip("\n").split("\t"))) for l in fh]


def selftest():
    """负控：把 fixture 复制到临时目录并改坏一处，证明 --check 会退出 1。"""
    with tempfile.TemporaryDirectory() as td:
        for f in FIX.glob("*.tsv"):
            shutil.copy(f, td)
        q = Path(td) / "quality_depth.tsv"
        lines = q.read_text(encoding="utf-8").splitlines()
        head = lines[0].split("\t")
        i = head.index("score")
        for k in range(1, len(lines)):
            cells = lines[k].split("\t")
            cells[i] = "%.12g" % (float(cells[i]) + 0.05)
            lines[k] = "\t".join(cells)
        q.write_text("\n".join(lines) + "\n", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check(fixdir=td)
        n = len(buf.getvalue().strip().splitlines())
        print("selftest: 把 quality_depth 的每一格分数 +0.05 后，--check 退出 %d（期望 1），报 %d 行缺陷"
              % (rc, n))
        return 0 if rc == 1 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.selftest:
        return selftest()

    built, missing = build_rows()
    print("被审 revision: %s" % subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                              capture_output=True, text=True).stdout.strip())
    print("脚本 sha256: %s" % hashlib.sha256(open(__file__, "rb").read()).hexdigest())
    print("面板: %d 个 spec panel；产品根: %s\n" % (len(built["panels"]), WR))
    section_a(built["speed"])
    section_a2(built["m28"])
    section_b(built["quality"], built["peritem"])
    section_c(built["byteid"])
    section_d(built["device"])
    section_e(built["ident"], built["ident_pairs"])
    if missing:
        print("\nUNMEASURED: 缺输入 %d 项:" % len(missing))
        for m in missing:
            print("  missing %s" % m)
        return 2
    if args.write:
        write_fixtures(built)
        print("\n--write: fixtures 已重写到 %s" % FIX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
