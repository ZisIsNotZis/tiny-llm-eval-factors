#!/usr/bin/env python3
"""a08 思考开关：这一轴的全部数字与它们唯一的复算入口。

轴的问题是「开关思考会改变分数、生成 token 数与延迟吗」，所以每一项证据都必须带三类列：
分数（库里有）、生成 token 数与墙钟（`mres/<tag>/lmeval_panel.json` 的 `timings_s` 与
`server.log` 的逐请求计时），以及这一格所在的协议身份（`protocol` / `max_tokens` / `ctx`）。

    python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --write   # 重算并落 fixture
    python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --check   # 重算并与 fixture 逐字比
    python3 "docs/subprojects/a08-思考开关/analysis/thinking_pairs.py" --selftest # 负控：改坏一份副本必须变红

配对的硬规则（写在代码里，不靠记忆）：
  * 只要 `reasoning` 不同的两个格才是开关对；模型、基准、`n_items`、`limit_spec` 必须相同，
    否则不配对（`reasoning` 是协议的一部分，跨协议池化就是把两个测量当一个）。
  * `max_tokens` 不同的对被**标成 `budget_matched=0`** 并整体保留：它们仍然是有信息量的观测，
    但那 13 对历史格的差同时含「开关」与「预算」两个变量，不能读成思考效应。
  * 库里 `max_tokens` 为 NULL 的老格，其预算取自它自己的 panel json（`profiles[task]`），
    来源写进 `mt_source` 列；取不到就是 NULL，不填默认值。

退出码：0 一致；1 与 fixture 不符；2 输入缺失（库/脚本不在，或 --write 时读不到库）。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBPROJECT = HERE.parent
REPO = HERE.parents[3]
DB = Path(os.environ.get("A08_DB", REPO / "experiments.sqlite"))
MRES = Path(os.environ.get("A08_MRES", REPO / ".wrapup/mres"))
FIX = SUBPROJECT / "fixtures"
LOGDIR = FIX / "logs"          # 生成 token 数所依据的 server.log 的 gz 副本（随仓库走的证据）
CELLS = FIX / "thinking_cells.tsv"
PAIRS = FIX / "thinking_pairs.tsv"
CENSUS = FIX / "reasoning_census.tsv"

# 每一类基准在报告里代表什么；一次开关会让某一类改变方向，所以类别要显式带在每一行上
CLASS = {
    "gsm8k": "reasoning",
    "gsm8k-strict": "reasoning",
    "ifeval": "extraction",
    "mmlu": "knowledge-loglik",
    "arc_challenge": "knowledge-loglik",
    "truthfulqa_mc2": "knowledge-loglik",
    "humaneval": "code",
    "mbpp": "code",
    "humaneval-plus": "code",
    "humaneval-cpp": "code",
    "humaneval-py": "code",
    "mbpp-plus": "code",
}
HARNESS_TASK = {"gsm8k": "gsm8k", "gsm8k-strict": "gsm8k", "ifeval": "ifeval", "mmlu": "mmlu",
                "arc_challenge": "arc_challenge", "truthfulqa_mc2": "truthfulqa_mc2"}

GEN_RE = re.compile(r"^\S+ \S+ .*eval time =\s+([\d.]+) ms /\s+(\d+) tokens")
PROMPT_RE = re.compile(r"^\S+ \S+ .*prompt eval time =\s+([\d.]+) ms /\s+(\d+) tokens")


def f6(x):
    return "NA" if x is None else f"{x:.6g}"


def q(sql, args=()):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def panel(tag: str) -> dict | None:
    if tag in _PANEL_CACHE:
        return _PANEL_CACHE[tag]
    # 同样优先用随仓库走的副本，使 clone 里重算与工作树里逐字一致
    for p in (LOGDIR / f"{tag}.lmeval_panel.json", MRES / tag / "lmeval_panel.json"):
        if p.exists():
            _PANEL_CACHE[tag] = json.loads(p.read_text())
            return _PANEL_CACHE[tag]
    _PANEL_CACHE[tag] = None
    return None


_PANEL_CACHE: dict[str, dict | None] = {}
_COST_CACHE: dict[tuple, dict] = {}


def cost_from_log(tag: str, task: str, n_items: int | None, mgt: int | None) -> dict:
    key = (tag, task, n_items, mgt)
    if key not in _COST_CACHE:
        _COST_CACHE[key] = _cost_compute(tag, task, n_items, mgt)
    return dict(_COST_CACHE[key])


def _cost_compute(tag: str, task: str, n_items: int | None, mgt: int | None) -> dict:
    """一条测量自己的生成 token 数 / 墙钟。只在该 panel 只生成过这一个任务时给 token 数：
    多任务 panel 的 server.log 把所有任务混在一起，按 n_items 对不上就记 `shared-log`。"""
    out = {"wall_s": None, "requests": None, "gen_tokens": None, "prompt_tokens": None,
           "gen_ms": None, "cap_hits": None, "max_gen_item": None, "log_sha256": None,
           "cost_note": ""}
    p = panel(tag)
    if p is None:
        out["cost_note"] = "no-panel"
        return out
    out["wall_s"] = (p.get("timings_s") or {}).get(task)
    # 日志来源优先用随仓库走的那份（clone 里也有），否则用原始 `.wrapup/mres`。两份字节相同，
    # 所以 sha256 与由它算出的 token 数在两种环境里一致 —— 重算不是“在我的工作树里才能绿”。
    # 多任务 panel（历史标准面板）的 server.log 把所有任务混在一起，逐请求解析不可能归给某一格，
    # 所以不读它：直接记 `shared-log`，那一格的生成 token 数就是不可得。
    if len([t for t in (p.get("tasks") or {}) if t]) > 1:
        out["cost_note"] = "shared-log(multi-task panel)"
        return out
    log = LOGDIR / f"{tag}.server.log.gz"
    if log.exists():
        raw = gzip.open(log, "rb").read()
    else:
        log = MRES / tag / "server.log"
        raw = log.read_bytes() if log.exists() else None
    if raw is None:
        out["cost_note"] = "no-server-log"
        return out
    out["log_sha256"] = hashlib.sha256(raw).hexdigest()
    gen, prompt = [], []
    for line in raw.decode("utf-8", "replace").splitlines():
        if "prompt eval time" in line:
            m = PROMPT_RE.search(line)
            if m:
                prompt.append((float(m.group(1)), int(m.group(2))))
        elif "eval time" in line:
            m = GEN_RE.search(line)
            if m:
                gen.append((float(m.group(1)), int(m.group(2))))
    # run_panel 起服后会发一次 `1+1=` 的冒烟请求（max_tokens=1），它不是被测格的一部分
    if gen and prompt and gen[0][1] == 1 and prompt[0][1] <= 8:
        gen, prompt = gen[1:], prompt[1:]
    out["requests"] = len(prompt)
    if n_items is not None and abs(len(prompt) - n_items) <= 2:
        out["gen_tokens"] = sum(b for _, b in gen)
        out["prompt_tokens"] = sum(b for _, b in prompt)
        out["gen_ms"] = round(sum(a for a, _ in gen), 1)
        # 打满预算的题数：推理流把 max_gen_toks 吃光就从根上判不了对错，这是 on 臂掉分的机制候选，
        # 不能只看分数差就说“思考有害”。
        if mgt:
            out["cap_hits"] = sum(1 for _, b in gen if b >= mgt)
            out["max_gen_item"] = max(b for _, b in gen)
    else:
        out["cost_note"] = f"shared-log(requests={len(prompt)})"
    return out


def effective_mt(row: dict) -> tuple[int | None, str]:
    if row["max_tokens"] is not None:
        return int(row["max_tokens"]), "db"
    p = panel(row["run_tag"] or "")
    prof = ((p or {}).get("profiles") or {}).get(HARNESS_TASK.get(row["_bench"], ""), {})
    if prof.get("max_gen_toks") is not None:
        return int(prof["max_gen_toks"]), "panel-json:profiles"
    if (p or {}).get("max_gen_toks") is not None:
        return int(p["max_gen_toks"]), "panel-json"
    return None, "unknown"


BENCHES = ("gsm8k", "gsm8k-strict", "ifeval", "mmlu", "arc_challenge", "truthfulqa_mc2",
           "humaneval", "mbpp", "humaneval-plus", "humaneval-cpp", "humaneval-py", "mbpp-plus")


def cells() -> list[dict]:
    """逐格证据只收两类格：思考开的格，以及与它同模型/同基准/同题量的关思考格。

    其余 800 多行关思考格（代码类、多任务 panel）不属于开关对，它们的量在 census 里用聚合体现；
    把它们拉进逐格表只会让“这一轴有多少证据”读不出来。"""
    rows = q(f"""
        select model, _bench, _score, n_items, max_tokens, ctx_size, protocol, reasoning,
               run_tag, limit_spec, temp, seed, source_file
        from experiments
        where reasoning in ('on','off')
          and _bench in {BENCHES}
        """)
    ons = [r for r in rows if r["reasoning"] == "on" and r["_score"] is not None]
    keys = {(r["model"], r["_bench"], r["n_items"]) for r in ons}
    keep = [r for r in rows
            if r["_score"] is not None
            and (r["reasoning"] == "on" or (r["model"], r["_bench"], r["n_items"]) in keys)]
    out = []
    for r in keep:
        mt, mtsrc = effective_mt(r)
        c = cost_from_log(r["run_tag"] or "", HARNESS_TASK.get(r["_bench"], r["_bench"]),
                          r["n_items"], mt)
        out.append({
            "class": CLASS.get(r["_bench"], "?"), "bench": r["_bench"], "model": r["model"],
            "reasoning": r["reasoning"], "score": round(r["_score"], 6),
            "n_items": r["n_items"], "max_gen_toks": mt, "mt_source": mtsrc,
            "ctx": r["ctx_size"], "protocol": r["protocol"], "tag": r["run_tag"],
            "gen_per_item": (round(c["gen_tokens"] / r["n_items"], 1)
                             if c["gen_tokens"] and r["n_items"] else None),
            **c,
        })
    out.sort(key=lambda c: (c["class"], c["bench"], c["model"], c["reasoning"], c["tag"] or ""))
    return out


def census() -> list[dict]:
    """每一类基准在库里各有多少开/关格 —— “哪里不可测”本身是这一轴的一个结果。"""
    rows = q(f"""
        select _bench, reasoning, count(*) cells, count(distinct model) models
        from experiments
        where reasoning in ('on','off','auto')
          and _bench in {BENCHES}
        group by _bench, reasoning
        """)
    out = [{"class": CLASS.get(r["_bench"], "?"), "bench": r["_bench"],
            "reasoning": r["reasoning"], "cells": r["cells"], "models": r["models"]}
           for r in rows]
    out.sort(key=lambda a: (a["class"], a["bench"], a["reasoning"]))
    return out


def pairs(cs: list[dict]) -> list[dict]:
    ons = [c for c in cs if c["reasoning"] == "on"]
    offs = [c for c in cs if c["reasoning"] == "off"]
    out = []
    for on in ons:
        cand = [o for o in offs if o["model"] == on["model"] and o["bench"] == on["bench"]
                and o["n_items"] == on["n_items"]]
        if not cand:
            out.append({"class": on["class"], "bench": on["bench"], "model": on["model"],
                        "on_tag": on["tag"], "off_tag": "NO-OFF-CELL", "on_mt": on["max_gen_toks"],
                        "off_mt": None, "budget_matched": "n/a", "n_items": on["n_items"],
                        "score_on": f6(on["score"]), "score_off": "NA", "delta_items": "NA",
                        "off_wall_s": "NA", "on_wall_s": f6(on["wall_s"]), "wall_ratio": "NA",
                        "note": "库里没有同模型同题量的关思考格，基线率不可得"})
            continue
        best = sorted(cand, key=lambda o: (abs((o["max_gen_toks"] or 0) - (on["max_gen_toks"] or 0)),
                                           o["max_gen_toks"] or 0, o["tag"] or ""))[0]
        matched = best["max_gen_toks"] == on["max_gen_toks"]
        d = (on["score"] - best["score"]) * (on["n_items"] or 0)
        ratio = (on["wall_s"] / best["wall_s"]) if (on["wall_s"] and best["wall_s"]) else None
        out.append({"class": on["class"], "bench": on["bench"], "model": on["model"],
                    "on_tag": on["tag"], "off_tag": best["tag"],
                    "on_mt": on["max_gen_toks"], "off_mt": best["max_gen_toks"],
                    "budget_matched": int(matched), "n_items": on["n_items"],
                    "score_on": f6(on["score"]), "score_off": f6(best["score"]),
                    "delta_items": f6(round(d, 6)), "off_wall_s": f6(best["wall_s"]),
                    "on_wall_s": f6(on["wall_s"]), "wall_ratio": f6(ratio),
                    "note": "" if matched else "预算不同：差同时含开关与预算两个变量"})
    out.sort(key=lambda p: (p["class"], p["bench"], p["model"]))
    return out


def tsv(rows: list[dict], cols: list[str]) -> str:
    lines = ["\t".join(cols)]
    for r in rows:
        lines.append("\t".join("" if r.get(c) is None else str(r.get(c)) for c in cols))
    return "\n".join(lines) + "\n"


CELL_COLS = ["class", "bench", "model", "reasoning", "score", "n_items", "max_gen_toks",
             "mt_source", "ctx", "wall_s", "requests", "gen_tokens", "gen_per_item", "cap_hits",
             "prompt_tokens", "gen_ms", "tag", "protocol", "cost_note", "log_sha256"]
PAIR_COLS = ["class", "bench", "model", "off_tag", "on_tag", "off_mt", "on_mt", "budget_matched",
             "n_items", "score_off", "score_on", "delta_items", "off_wall_s", "on_wall_s",
             "wall_ratio", "note"]
CENSUS_COLS = ["class", "bench", "reasoning", "cells", "models"]


def persist_evidence(cs: list[dict]) -> list[str]:
    """把每个带 token 数的格所依据的 server.log 与 panel json 各压/拷一份到 fixtures/logs/。

    `.wrapup/mres` 在 git 里不存盘（大体量、可重建），但「延迟与生成 token 数」是这次测量的产物，
    不是能从代码重算的派生值，所以它作为证据物落盘：日志 gz 副本 + fixture 里的原文件 sha256。
    panel json 也一并落盘，否则 clone 里读不到该格的 `timings_s` 与 `max_gen_toks`。
    """
    LOGDIR.mkdir(parents=True, exist_ok=True)
    written = []
    for tag in sorted({c["tag"] for c in cs if c.get("tag")}):
        src_panel = MRES / tag / "lmeval_panel.json"
        dst_panel = LOGDIR / f"{tag}.lmeval_panel.json"
        if src_panel.exists() and (not dst_panel.exists()
                                  or dst_panel.read_text() != src_panel.read_text()):
            dst_panel.write_text(src_panel.read_text())
            written.append(dst_panel.name)
        elif not dst_panel.exists() and not src_panel.exists():
            raise SystemExit(f"{tag}: panel json 既不在 mres 也不在 fixtures/logs")
        if not any(c.get("log_sha256") for c in cs if c["tag"] == tag):
            continue
        dst = LOGDIR / f"{tag}.server.log.gz"
        src = MRES / tag / "server.log"
        if not src.exists():
            raise SystemExit(f"{tag}: mres 里没有 server.log，且 fixtures/logs 也没有副本")
        if dst.exists() and gzip.open(dst, "rb").read() == src.read_bytes():
            continue
        with gzip.GzipFile(dst, "wb", mtime=0) as fh:
            fh.write(src.read_bytes())
        written.append(dst.name)
    return written


def render() -> dict[str, str]:
    cs = cells()
    return {CELLS.name: tsv(cs, CELL_COLS), PAIRS.name: tsv(pairs(cs), PAIR_COLS),
            CENSUS.name: tsv(census(), CENSUS_COLS)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not DB.exists():
        print(f"MISSING: 库不存在 {DB}", file=sys.stderr)
        return 2
    texts = render()
    if a.write:
        FIX.mkdir(parents=True, exist_ok=True)
        for name, text in texts.items():
            (FIX / name).write_text(text)
        logs = persist_evidence(cells())
        print(f"wrote {len(texts)} fixtures into {FIX}"
              + (f"; persisted {len(logs)} evidence copies: {', '.join(logs)}" if logs else ""))
        return 0
    if a.check:
        bad = []
        for name, text in texts.items():
            p = FIX / name
            if not p.exists():
                print(f"MISSING: {p}", file=sys.stderr)
                return 2
            if p.read_text() != text:
                bad.append(name)
        if bad:
            print("FAIL: fixture 与重算不符：" + ", ".join(bad), file=sys.stderr)
            for name in bad:
                old = (FIX / name).read_text().splitlines()
                new = texts[name].splitlines()
                for i, (x, y) in enumerate(zip(old, new), 1):
                    if x != y:
                        print(f"  {name}:{i}\n    fixture: {x}\n    recompute: {y}", file=sys.stderr)
                        break
            return 1
        n_cost = sum(1 for line in texts[CELLS.name].splitlines()[1:]
                     if line.split("\t")[11] not in ("None", ""))
        print(f"PASS thinking_pairs: {len(texts[PAIRS.name].splitlines()) - 1} 对逐字一致；"
              f"{n_cost} 个格带可复算的生成 token 数")
        return 0
    if a.selftest:
        # 负控：改坏一份副本，检查必须变红（否则这道判据看不见错误）
        tmp = Path(tempfile.mkdtemp(prefix="a08-selftest-"))
        try:
            for name, text in texts.items():
                (tmp / name).write_text(text)
            clean = check_into(tmp, texts)
            lines = (tmp / PAIRS.name).read_text().splitlines()
            parts = lines[1].split("\t")
            parts[10] = "0.123456" if parts[10] != "0.123456" else "0.654321"
            lines[1] = "\t".join(parts)
            (tmp / PAIRS.name).write_text("\n".join(lines) + "\n")
            mutated = check_into(tmp, texts)
            ok = clean and not mutated
            print(("PASS negative control: 副本未改时绿、改坏一行后变红" if ok else
                   f"FAIL negative control: clean={clean} mutated_still_green={mutated}"))
            return 0 if ok else 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("nothing to do: pass --write, --check or --selftest", file=sys.stderr)
    return 2


def check_into(dirpath: Path, fresh: dict[str, str]) -> bool:
    """fixture 目录 dirpath 是否与重算一致（True = 一致）。"""
    for name, text in fresh.items():
        p = dirpath / name
        if not p.exists() or p.read_text() != text:
            return False
    return True


if __name__ == "__main__":
    sys.exit(main())
