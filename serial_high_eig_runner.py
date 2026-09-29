#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import random
import re
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "experiments.sqlite"
HF_DIR = ROOT.parent
STATE_PATH = ROOT / ".serial_high_eig_runner.state.json"
LOG_PATH = ROOT / ".serial_high_eig_runner.log"
EVALPLUS_ROOT = ROOT / "evalplus_results"

BENCHES = ("mbpp", "humaneval")
CACHE_TYPES = ("f16", "q8_0", "q5_1", "q5_0")
KV_RATIO = {"f16": 1.0, "fp16": 1.0, "q8_0": 0.53125, "q5_1": 0.375, "q5_0": 0.34375}

MAX_TOP_K = 2048
MAX_DRAFT = 32
RUN_TIMEOUT_SECONDS = 7200
READINESS_TIMEOUT_SECONDS = 180
SLEEP_NO_MODEL_SECONDS = 60
CANDIDATES_PER_MODEL_BENCH = 64

MIN_TEMP = 0.0
MAX_TEMP = 2.0
MIN_TOP_P = 0.0
MAX_TOP_P = 1.0
MIN_MIN_P = 0.0
MAX_MIN_P = 1.0
MIN_PRESENCE_PENALTY = 0.0
MAX_PRESENCE_PENALTY = 2.0

BASE_URL = "http://127.0.0.1:8080/v1"

QUANT_RE = re.compile(r"-((UD-)?I?Q[1-8]+[_A-Z]*)\b", re.IGNORECASE)
SIZE_RE = re.compile(r"-E?([0-9.]+)[MB]\b", re.IGNORECASE)
ACTIVATION_RE = re.compile(r"-A([0-9.]+)[MB]\b", re.IGNORECASE)
MTP_RE = re.compile(r"-MTP\b", re.IGNORECASE)
QAT_RE = re.compile(r"-QAT\b", re.IGNORECASE)
INSTRUCT_RE = re.compile(r"-IT\b", re.IGNORECASE)
OMNI_RE = re.compile(r"-(OMNI|ANY)\b", re.IGNORECASE)
THINK_RE = re.compile(r"-(THINK|REASON)(ING)?\b", re.IGNORECASE)
FLASH_RE = re.compile(r"-FLASH(-REAP)?\b", re.IGNORECASE)
CODE_RE = re.compile(r"-CODER?\b", re.IGNORECASE)
WORD_RE = re.compile(r"-(NANO|MINI|TINY|SMALL|MEDIUM|LARGE|ULTRA)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Candidate:
    model: str
    bench: str
    cache_type_k: str
    cache_type_v: str
    reasoning: str
    spec_type: str
    spec_draft_n_max: int
    temp: float
    top_p: float
    top_k: int
    min_p: float
    presence_penalty: float


@dataclass(frozen=True)
class Observation:
    model: str
    bench: str
    cache_type_k: str
    cache_type_v: str
    reasoning: str
    spec_type: str
    spec_draft_n_max: int
    temp: float
    top_p: float
    top_k: int
    min_p: float
    presence_penalty: float
    score: float


def ts_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def log(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{ts_now()}] {msg}\n")


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def check_db_health() -> None:
    con = sqlite3.connect(DB_PATH)
    try:
        ok = con.execute("PRAGMA integrity_check").fetchone()
        if not ok or str(ok[0]).lower() != "ok":
            raise RuntimeError(f"integrity_check failed: {ok}")
    finally:
        con.close()


def with_db_mutation(fn: callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    out = fn(*args, **kwargs)
    check_db_health()
    return out


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"seq": 0, "seed": int(time.time())}
    try:
        obj = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault("seq", 0)
    obj.setdefault("seed", int(time.time()))
    return obj


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def discover_models() -> list[str]:
    unsupported_prefixes = ("diffusiongemma",)
    models = sorted(p.name for p in HF_DIR.glob("*.gguf"))
    return [m for m in models if not m.lower().startswith(unsupported_prefixes)]


def is_qwen_model(model: str) -> bool:
    return model.lower().startswith("qwen")


def has_mtp_layers(model: str) -> bool:
    return "-mtp" in model.lower()


def sanitize_candidate(c: Candidate) -> Candidate:
    return Candidate(
        model=c.model,
        bench=c.bench,
        cache_type_k=c.cache_type_k,
        cache_type_v=c.cache_type_v,
        reasoning=c.reasoning,
        spec_type=c.spec_type,
        spec_draft_n_max=max(0, min(MAX_DRAFT, c.spec_draft_n_max)),
        temp=clamp(c.temp, MIN_TEMP, MAX_TEMP),
        top_p=clamp(c.top_p, MIN_TOP_P, MAX_TOP_P),
        top_k=max(1, min(MAX_TOP_K, int(c.top_k))),
        min_p=clamp(c.min_p, MIN_MIN_P, MAX_MIN_P),
        presence_penalty=clamp(c.presence_penalty, MIN_PRESENCE_PENALTY, MAX_PRESENCE_PENALTY),
    )


def signature_for_candidate(c: Candidate) -> tuple[str, ...]:
    return (
        c.bench,
        c.model,
        c.cache_type_k,
        c.cache_type_k,
        c.cache_type_v,
        c.cache_type_v,
        c.reasoning,
        c.spec_type,
        str(c.spec_draft_n_max),
        f"{c.temp:.6f}",
        f"{c.top_p:.6f}",
        str(c.top_k),
        f"{c.min_p:.6f}",
        f"{c.presence_penalty:.6f}",
    )


def vec_from_candidate(c: Candidate) -> list[float]:
    return [
        c.temp / MAX_TEMP,
        c.top_p,
        c.top_k / MAX_TOP_K,
        c.min_p,
        c.presence_penalty / MAX_PRESENCE_PENALTY,
        1.0 if c.reasoning == "auto" else 0.0,
        c.spec_draft_n_max / MAX_DRAFT,
        KV_RATIO.get(c.cache_type_k, 1.0),
        KV_RATIO.get(c.cache_type_v, 1.0),
    ]


def dist2(a: list[float], b: list[float]) -> float:
    return sum((x - y) * (x - y) for x, y in zip(a, b))


def load_existing_signatures() -> set[tuple[str, ...]]:
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(
            """
            SELECT _bench, model, cache_type_k, cache_type_k_draft, cache_type_v, cache_type_v_draft,
                   reasoning, spec_type, spec_draft_n_max, temp, top_p, top_k, min_p, presence_penalty
            FROM experiments
            WHERE _bench IN ('mbpp','humaneval')
            """
        ).fetchall()
    finally:
        con.close()
    return {tuple("" if v is None else str(v) for v in r) for r in rows}


def load_observations() -> list[Observation]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT model, _bench, cache_type_k, cache_type_v, reasoning, spec_type, spec_draft_n_max,
                   temp, top_p, top_k, min_p, presence_penalty, _score
            FROM experiments
            WHERE _bench IN ('mbpp','humaneval') AND _score IS NOT NULL
            """
        ).fetchall()
    finally:
        con.close()
    out: list[Observation] = []
    for r in rows:
        out.append(
            Observation(
                model=str(r["model"]),
                bench=str(r["_bench"]),
                cache_type_k=str(r["cache_type_k"]),
                cache_type_v=str(r["cache_type_v"]),
                reasoning=str(r["reasoning"]),
                spec_type=str(r["spec_type"]),
                spec_draft_n_max=int(float(r["spec_draft_n_max"] or 0)),
                temp=clamp(float(r["temp"]), MIN_TEMP, MAX_TEMP),
                top_p=clamp(float(r["top_p"]), MIN_TOP_P, MAX_TOP_P),
                top_k=max(1, min(MAX_TOP_K, int(float(r["top_k"])))),
                min_p=clamp(float(r["min_p"]), MIN_MIN_P, MAX_MIN_P),
                presence_penalty=clamp(float(r["presence_penalty"]), MIN_PRESENCE_PENALTY, MAX_PRESENCE_PENALTY),
                score=float(r["_score"]),
            )
        )
    return out


def generate_random_candidate(rng: random.Random, model: str, bench: str) -> Candidate:
    cache_k = rng.choice(CACHE_TYPES)
    cache_v = rng.choice(CACHE_TYPES)
    reasoning = rng.choice(("auto", "off"))
    if is_qwen_model(model) and has_mtp_layers(model):
        spec_type = "draft-mtp"
        spec_draft_n_max = rng.randint(1, MAX_DRAFT)
    else:
        spec_type = "none"
        spec_draft_n_max = 0
    # random() for float domains; randint() for integer domains; choice() for categorical domains.
    return sanitize_candidate(Candidate(
        model=model,
        bench=bench,
        cache_type_k=cache_k,
        cache_type_v=cache_v,
        reasoning=reasoning,
        spec_type=spec_type,
        spec_draft_n_max=spec_draft_n_max,
        temp=(rng.random() ** 1.6) * 1.2,
        top_p=0.50 + 0.499 * rng.random(),
        top_k=rng.randint(1, MAX_TOP_K),
        min_p=(rng.random() ** 2.0) * 0.20,
        presence_penalty=2.0 * rng.random(),
    ))


def acquisition(c: Candidate, observations: list[Observation]) -> float:
    rel = [o for o in observations if o.model == c.model and o.bench == c.bench]
    if not rel:
        model_total = sum(1 for o in observations if o.model == c.model)
        bench_total = sum(1 for o in observations if o.bench == c.bench)
        return 2.0 + 0.40 / math.sqrt(1.0 + model_total) + 0.10 / math.sqrt(1.0 + bench_total)
    xv = vec_from_candidate(c)
    dscore: list[tuple[float, float]] = []
    for o in rel:
        ov = vec_from_candidate(Candidate(
            model=o.model,
            bench=o.bench,
            cache_type_k=o.cache_type_k,
            cache_type_v=o.cache_type_v,
            reasoning=o.reasoning,
            spec_type=o.spec_type,
            spec_draft_n_max=o.spec_draft_n_max,
            temp=o.temp,
            top_p=o.top_p,
            top_k=o.top_k,
            min_p=o.min_p,
            presence_penalty=o.presence_penalty,
        ))
        dscore.append((dist2(xv, ov), o.score))
    dscore.sort(key=lambda t: t[0])
    nearest = dscore[:min(10, len(dscore))]
    weights = [1.0 / (1e-6 + math.sqrt(d)) for d, _ in nearest]
    wsum = sum(weights)
    mu = sum(w * s for w, (_, s) in zip(weights, nearest)) / wsum
    var = sum(w * ((s - mu) ** 2) for w, (_, s) in zip(weights, nearest)) / wsum
    sigma = math.sqrt(max(0.0, var))
    novelty = min(1.0, math.sqrt(nearest[0][0]) / 1.5)
    info_gain = sigma * (0.4 + 0.6 * novelty)
    model_total = sum(1 for o in observations if o.model == c.model)
    bench_total = sum(1 for o in observations if o.bench == c.bench)
    explore_bias = 0.15 / math.sqrt(1.0 + model_total) + 0.10 / math.sqrt(1.0 + bench_total)
    return info_gain + explore_bias + 0.05 * mu


def suggest_candidates(
    rng: random.Random,
    models: list[str],
    observations: list[Observation],
    existing_signatures: set[tuple[str, ...]],
) -> list[tuple[Candidate, float]]:
    ranked: list[tuple[Candidate, float]] = []
    local_seen: set[tuple[str, ...]] = set(existing_signatures)
    for model in models:
        for bench in BENCHES:
            made = 0
            tries = 0
            while made < CANDIDATES_PER_MODEL_BENCH and tries < CANDIDATES_PER_MODEL_BENCH * 20:
                tries += 1
                c = generate_random_candidate(rng, model, bench)
                sig = signature_for_candidate(c)
                if sig in local_seen:
                    continue
                local_seen.add(sig)
                ranked.append((c, acquisition(c, observations)))
                made += 1
    ranked.sort(key=lambda t: t[1], reverse=True)
    return ranked


def print_ranked_candidates(ranked: list[tuple[Candidate, float]], top_n: int = 10) -> None:
    top_n = max(1, int(top_n))
    print(f"candidate_count={len(ranked)} showing_top={min(top_n, len(ranked))}")
    for i, (c, score) in enumerate(ranked[:top_n], start=1):
        print(
            f"rank={i} acq={score:.6f} bench={c.bench} model={c.model} "
            f"k={c.cache_type_k} v={c.cache_type_v} reasoning={c.reasoning} "
            f"spec={c.spec_type}:{c.spec_draft_n_max} temp={c.temp:.6f} top_p={c.top_p:.6f} "
            f"top_k={c.top_k} min_p={c.min_p:.6f} presence_penalty={c.presence_penalty:.6f}",
            flush=True,
        )


class ProcessTracker:
    def __init__(self) -> None:
        self._procs: set[subprocess.Popen[str]] = set()

    def add(self, proc: subprocess.Popen[str]) -> subprocess.Popen[str]:
        self._procs.add(proc)
        return proc

    def remove(self, proc: subprocess.Popen[str]) -> None:
        self._procs.discard(proc)

    def terminate_all(self) -> None:
        for p in list(self._procs):
            if p.poll() is not None:
                self._procs.discard(p)
                continue
            try:
                p.terminate()
            except Exception:
                pass
        deadline = time.time() + 15
        while time.time() < deadline and any(p.poll() is None for p in self._procs):
            time.sleep(0.2)
        for p in list(self._procs):
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass
            self._procs.discard(p)

    def __enter__(self) -> ProcessTracker:
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.terminate_all()


def cleanup_stale_default_port_server() -> None:
    try:
        out = subprocess.check_output(["ss", "-ltnp"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return
    pids: set[int] = set()
    for line in out.splitlines():
        if "127.0.0.1:8080" not in line or "llama-server" not in line:
            continue
        for m in re.finditer(r"pid=(\d+)", line):
            pids.add(int(m.group(1)))
    for pid in sorted(pids):
        try:
            os.kill(pid, signal.SIGTERM)
            log(f"killed stale llama-server pid={pid}")
        except Exception as e:
            log(f"failed kill stale pid={pid} err={e!r}")


def wait_server_ready(server: subprocess.Popen[str], timeout_s: float) -> None:
    url = BASE_URL.rstrip("/") + "/models"
    deadline = time.time() + timeout_s
    last_err = ""
    while time.time() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"llama-server exited before ready rc={server.returncode}")
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if 200 <= int(resp.status) < 500:
                    print(f"llama-server ready: {url}", flush=True)
                    return
        except Exception as e:
            last_err = str(e)
        time.sleep(0.5)
    raise RuntimeError(f"llama-server not ready in {timeout_s:.0f}s ({last_err})")


def build_server_args(c: Candidate) -> list[str]:
    model_path = HF_DIR / c.model
    return [
        "--model", str(model_path),
        "--cache-type-k", c.cache_type_k,
        "--cache-type-k-draft", c.cache_type_k,
        "--cache-type-v", c.cache_type_v,
        "--cache-type-v-draft", c.cache_type_v,
        "--reasoning", c.reasoning,
        "--spec-type", c.spec_type,
        "--spec-draft-n-max", str(c.spec_draft_n_max),
        "--temp", f"{c.temp:.6f}",
        "--top-p", f"{c.top_p:.6f}",
        "--top-k", str(c.top_k),
        "--min-p", f"{c.min_p:.6f}",
        "--presence-penalty", f"{c.presence_penalty:.6f}",
    ]


def build_evalplus_cmd(c: Candidate, alias: str) -> list[str]:
    run_temp = f"{c.temp:.6f}"
    cmd = [
        "evalplus.evaluate",
        c.bench,
        "--model", alias,
        "--backend", "openai",
        "--base_url", BASE_URL,
        "--temperature", run_temp,
        "--root", str(EVALPLUS_ROOT),
        "--i_just_wanna_run",
    ]
    if float(run_temp) == 0.0:
        cmd.extend(["--greedy", "True"])
    return cmd


def monitor_pair_and_join(
    server: subprocess.Popen[str],
    benchmark: subprocess.Popen[str],
    tracker: ProcessTracker,
    timeout_s: float,
) -> None:
    deadline = time.time() + timeout_s
    while True:
        server_rc = server.poll()
        bench_rc = benchmark.poll()
        if bench_rc is not None:
            if server.poll() is None:
                server.terminate()
            tracker.remove(benchmark)
            if bench_rc != 0:
                raise RuntimeError(f"benchmarker failed rc={bench_rc}")
            return
        if server_rc is not None:
            if benchmark.poll() is None:
                benchmark.terminate()
            tracker.remove(server)
            raise RuntimeError(f"llama-server exited during benchmark rc={server_rc}")
        if time.time() > deadline:
            server.terminate()
            benchmark.terminate()
            raise TimeoutError(f"run timed out after {timeout_s}s")
        time.sleep(0.5)


def parse_evalplus_result(bench: str, out_eval: Path, out_jsonl: Path) -> tuple[float, float]:
    if bench not in {"mbpp", "humaneval"}:
        raise RuntimeError(f"unsupported bench parse: {bench}")
    if not out_eval.exists():
        raise RuntimeError(f"missing eval result file: {out_eval}")
    score = float(json.loads(out_eval.read_text(encoding="utf-8"))["pass_at_k"]["plus"]["pass@1"])
    if not out_jsonl.exists():
        raise RuntimeError(f"missing completion file: {out_jsonl}")
    total = 0
    bad = 0
    with out_jsonl.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            total += 1
            obj = json.loads(line)
            completion = obj.get("completion") or obj.get("output") or obj.get("solution")
            if completion is None or not str(completion).strip():
                bad += 1
    bad_rate = (bad / total) if total else 0.0
    return score, bad_rate


def db_insert_row(row: dict[str, Any]) -> int:
    def _insert() -> int:
        con = sqlite3.connect(DB_PATH)
        try:
            cur = con.execute(
                f"INSERT INTO experiments ({','.join(row.keys())}) VALUES ({','.join('?' for _ in row)})",
                tuple(row.values()),
            )
            con.commit()
            rid = cur.lastrowid
            if rid is None:
                raise RuntimeError("insert rowid missing")
            return int(rid)
        finally:
            con.close()
    return int(with_db_mutation(_insert))


def db_patch_row(row_id: int, row: dict[str, Any]) -> None:
    if not row:
        return
    def _patch() -> None:
        con = sqlite3.connect(DB_PATH)
        try:
            con.execute(
                f"UPDATE experiments SET {','.join(f'{k}=?' for k in row)} WHERE rowid = ?",
                (*row.values(), row_id),
            )
            con.commit()
        finally:
            con.close()
    with_db_mutation(_patch)


def db_get_row(row_id: int) -> sqlite3.Row:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT rowid, * FROM experiments WHERE rowid = ?", (row_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        raise RuntimeError(f"missing row id={row_id}")
    return row


def double_underscore_fields(row: sqlite3.Row) -> dict[str, object]:
    model_name = pathlib.Path(str(row["model"])).name
    stem = model_name[:-5] if model_name.lower().endswith(".gguf") else model_name
    filesize = float(row["_file_size"] or 0.0)
    score = float(row["_score"] or 0.0)
    bad_rate = float(row["_bad_rate"] or 0.0)

    quant_match = QUANT_RE.search(stem)
    quant = quant_match.group(1) if quant_match else ""
    stem = QUANT_RE.sub("", stem)
    size = float((SIZE_RE.findall(stem) or ["0"])[0])
    stem = SIZE_RE.sub("", stem)
    activation = float((ACTIVATION_RE.findall(stem) or ["0"])[0])
    stem = ACTIVATION_RE.sub("", stem)
    mtp = stem != (stem := MTP_RE.sub("", stem))
    qat = stem != (stem := QAT_RE.sub("", stem))
    instruct = stem != (stem := INSTRUCT_RE.sub("", stem))
    omni = stem != (stem := OMNI_RE.sub("", stem))
    think = stem != (stem := THINK_RE.sub("", stem))
    flash = stem != (stem := FLASH_RE.sub("", stem))
    code = stem != (stem := CODE_RE.sub("", stem))
    stem = WORD_RE.sub("", stem)

    if size > 0:
        if filesize > 0 and size < filesize:
            size = filesize
    elif filesize > 0:
        size = filesize / 0.5
        if size < filesize:
            size = filesize
    else:
        size = None

    if size is None:
        activation_size = None
        quant_ratio = None
    else:
        activation_size = activation if activation > 0 else size
        if activation_size > size:
            activation_size = size
        quant_ratio = filesize / size if size > 0 else 0.0

    score_fix = score / (1.0 - bad_rate) if bad_rate < 1.0 else score
    return {
        "__size": size,
        "__activation_size": activation_size,
        "__quant": quant if quant else "UNKNOWN",
        "__quant_ratio": quant_ratio,
        "__mtp": mtp,
        "__qat": qat,
        "__instruct": instruct,
        "__omni": omni,
        "__think": think,
        "__flash": flash,
        "__code": code,
        "__model": stem,
        "__k_ratio": KV_RATIO.get(str(row["cache_type_k"] or "f16").lower(), 1.0),
        "__v_ratio": KV_RATIO.get(str(row["cache_type_v"] or "f16").lower(), 1.0),
        "__score_fix": max(0.0, min(1.0, score_fix)),
    }


def initial_row_from_candidate(c: Candidate) -> dict[str, Any]:
    model_path = HF_DIR / c.model
    if not model_path.exists():
        raise RuntimeError(f"model file missing: {model_path}")
    return {
        "_bench": c.bench,
        "model": c.model,
        "cache_type_k": c.cache_type_k,
        "cache_type_k_draft": c.cache_type_k,
        "cache_type_v": c.cache_type_v,
        "cache_type_v_draft": c.cache_type_v,
        "reasoning": c.reasoning,
        "spec_type": c.spec_type,
        "spec_draft_n_max": c.spec_draft_n_max,
        "temp": f"{c.temp:.6f}",
        "top_p": f"{c.top_p:.6f}",
        "top_k": c.top_k,
        "min_p": f"{c.min_p:.6f}",
        "presence_penalty": f"{c.presence_penalty:.6f}",
        "_file_size": model_path.stat().st_size / 1e9,
    }


def run_one_candidate(c: Candidate, tracker: ProcessTracker) -> tuple[float, float, float]:
    cleanup_stale_default_port_server()
    row_id = db_insert_row(initial_row_from_candidate(c))
    log(f"inserted row_id={row_id} bench={c.bench} model={c.model}")

    alias = f"exp-{int(time.time())}-{c.bench}"
    run_temp = f"{c.temp:.6f}"
    out_jsonl = EVALPLUS_ROOT / c.bench / f"{alias}_openai_temp_{run_temp}.jsonl"
    out_eval = EVALPLUS_ROOT / c.bench / f"{alias}_openai_temp_{run_temp}_eval_results.json"
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    server = tracker.add(subprocess.Popen(["llama-server", *build_server_args(c)]))
    t0 = time.time()
    try:
        wait_server_ready(server, timeout_s=READINESS_TIMEOUT_SECONDS)
        env = {**os.environ, "OPENAI_API_BASE": BASE_URL, "OPENAI_API_KEY": "dummy"}
        bench_cmd = build_evalplus_cmd(c, alias=alias)
        benchmark = tracker.add(subprocess.Popen(bench_cmd, cwd=str(ROOT), env=env))
        monitor_pair_and_join(server, benchmark, tracker, timeout_s=RUN_TIMEOUT_SECONDS)
        score, bad_rate = parse_evalplus_result(c.bench, out_eval=out_eval, out_jsonl=out_jsonl)
        wall = time.time() - t0
        print(f"result row_id={row_id} score={score:.6f} bad_rate={bad_rate:.6f} wall={wall:.2f}s", flush=True)
        db_patch_row(row_id, {"_score": score, "_bad_rate": bad_rate, "_wall_time": wall})
        db_patch_row(row_id, double_underscore_fields(db_get_row(row_id)))
        return score, bad_rate, wall
    except Exception as e:
        wall = time.time() - t0
        db_patch_row(row_id, {"_wall_time": wall})
        raise RuntimeError(f"run failed row_id={row_id}: {e}") from e
    finally:
        tracker.terminate_all()


def main() -> None:
    ap = argparse.ArgumentParser(prog="serial_high_eig_runner.py")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--print-top", type=int, default=10)
    args = ap.parse_args()

    state = load_state()
    seq = int(state["seq"])
    seed = int(state["seed"])
    rng = random.Random(seed)
    log(f"runner start seq={seq} seed={seed}")

    with ProcessTracker() as tracker:
        stop_requested = False

        def _on_signal(signum: int, _frame: Any) -> None:
            nonlocal stop_requested
            stop_requested = True
            log(f"signal received signum={signum}, terminating children")
            tracker.terminate_all()

        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)

        while not stop_requested:
            models = discover_models()
            if not models:
                log(f"no gguf models, sleeping {SLEEP_NO_MODEL_SECONDS}s")
                time.sleep(SLEEP_NO_MODEL_SECONDS)
                continue

            observations = load_observations()
            existing = load_existing_signatures()
            ranked = suggest_candidates(rng, models, observations, existing)
            if not ranked:
                log("no new candidate generated; sleeping 2s")
                time.sleep(2)
                continue

            print_ranked_candidates(ranked, top_n=args.print_top)
            best, best_acq = ranked[0]
            seq += 1
            print(
                f"picked seq={seq} acq={best_acq:.6f} bench={best.bench} model={best.model} "
                f"k={best.cache_type_k} v={best.cache_type_v} reasoning={best.reasoning} "
                f"spec={best.spec_type}:{best.spec_draft_n_max} temp={best.temp:.6f} top_p={best.top_p:.6f} "
                f"top_k={best.top_k} min_p={best.min_p:.6f} presence_penalty={best.presence_penalty:.6f}",
                flush=True,
            )
            log(
                f"picked seq={seq} acq={best_acq:.6f} bench={best.bench} model={best.model} "
                f"k={best.cache_type_k} v={best.cache_type_v}"
            )

            state["seq"] = seq
            state["seed"] = rng.randint(1, 2**31 - 1)
            save_state(state)

            if args.dry_run:
                if args.once:
                    return
                continue

            try:
                run_one_candidate(best, tracker)
            except Exception as e:
                log(f"fail seq={seq} err={e!r}")
                print(f"run_failed seq={seq} err={e}", file=sys.stderr, flush=True)
                time.sleep(2)

            if args.once:
                return


if __name__ == "__main__":
    main()
