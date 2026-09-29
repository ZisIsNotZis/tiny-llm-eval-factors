#!/bin/env python
import re
import os
import sys
import functools
import sqlite3
import subprocess
import json
import time
import typing
import pathlib
import urllib.request

### DB helper: DB logic is unacceptable elsewhere ###


_DB = sqlite3.connect('experiments.sqlite')
_DB.row_factory = sqlite3.Row


def get_row(row: dict[str, object]) -> int:
    row_id = _DB.execute(f"INSERT INTO experiments ({','.join(row)}) VALUES ({','.join('?'*len(row))})", tuple(row.values())).lastrowid
    assert row_id is not None
    _DB.commit()
    return int(row_id)


def patch_row(id: int, row: dict[str, object]):
    _DB.execute(f"UPDATE experiments SET {','.join(f'{k}=?' for k in row)} WHERE rowid = ?", (*row.values(), id))
    _DB.commit()

### Main program ###


HF_ROOT = pathlib.Path("..")
KV_RATIO = {"f16": 1.0, "fp16": 1.0, "q8_0": 0.53125, "q5_1": 0.375, "q5_0": 0.34375}
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


def double_underscore_fields(row: sqlite3.Row) -> dict[str, object]:
    model_name = pathlib.Path(str(row["model"])).name
    stem = model_name[:-5] if model_name.lower().endswith('.gguf') else model_name
    filesize = float(row["_file_size"] or 0.0)
    score = float(row["_score"] or 0.0)
    bad_rate = float(row["_bad_rate"] or 0.0)

    quant_match = QUANT_RE.search(stem)
    quant = quant_match.group(1) if quant_match else ''
    stem = QUANT_RE.sub("", stem)
    size = float((SIZE_RE.findall(stem) or ['0'])[0])
    stem = SIZE_RE.sub("", stem)
    activation = float((ACTIVATION_RE.findall(stem) or ['0'])[0])
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


def build_server_args(args: dict[str, str]) -> list[str]:
    server_args = []
    for key, value in args.items():
        if key.startswith("_"):
            continue
        if key == "model":
            value = str(HF_ROOT / value)
        server_args.extend([f"--{key.replace('_', '-')}", str(value)])
    return server_args


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=15)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


def wait_server_ready(server: subprocess.Popen[str], base_url: str, timeout_s: float = 120.0) -> None:
    deadline = time.time() + timeout_s
    url = base_url.rstrip("/") + "/models"
    last_err = ""
    while time.time() < deadline:
        rc = server.poll()
        if rc is not None:
            raise RuntimeError(f"llama-server exited before ready (code={rc})")
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if 200 <= int(resp.status) < 500:
                    return
        except Exception as e:
            last_err = str(e)
        time.sleep(0.5)
    raise RuntimeError(f"llama-server did not become ready within {timeout_s:.0f}s ({last_err})")


def run_checked_with_server(
    cmd: list[str],
    server: subprocess.Popen[str],
    *,
    env: dict[str, str] | None = None,
    cwd: pathlib.Path | None = None,
) -> None:
    proc = subprocess.Popen(
        cmd,
        stdout=sys.stderr,
        stderr=sys.stderr,
        text=True,
        env=env,
        cwd=str(cwd) if cwd is not None else None,
    )
    try:
        while True:
            run_rc = proc.poll()
            server_rc = server.poll()

            if run_rc is not None:
                if run_rc != 0:
                    raise subprocess.CalledProcessError(run_rc, cmd)
                return

            if server_rc is not None:
                stop_process(proc)
                raise RuntimeError(f"llama-server exited during benchmark (code={server_rc})")

            time.sleep(1.0)
    finally:
        stop_process(proc)


BENCHMARKS: dict[str, typing.Callable[[dict[str, str], int, list[str]], None]] = {}


@functools.partial(BENCHMARKS.setdefault, "terminal-bench-2")
def _(_args: dict[str, str], row_id: int, server_args: list[str]):
    def parse_terminal_bench_score(output: str) -> float:
        for line in reversed([line.strip() for line in output.splitlines() if line.strip()]):
            try:
                obj = json.loads(line)
            except Exception:
                continue
            for key in ("score", "acc", "accuracy", "success_rate", "pass_rate"):
                if key in obj:
                    val = float(obj[key])
                    return val / 100.0 if val > 1.0 else val

        matches = re.findall(
            r"(?:score|acc(?:uracy)?|success(?:[_ -]?rate)?|pass(?:[_ -]?rate)?)\s*[:=]\s*([0-9]*\.?[0-9]+)\s*%?",
            output,
            flags=re.IGNORECASE,
        )
        if matches:
            val = float(matches[-1])
            return val / 100.0 if val > 1.0 else val
        raise RuntimeError("could not parse terminal-bench-2 score from harbor output")

    base_url = "http://localhost:8080/v1"

    t0 = time.time()
    server = subprocess.Popen(["llama-server", *server_args], stdout=sys.stderr, stderr=sys.stderr, text=True)
    try:
        wait_server_ready(server, base_url)
        run_cmd = [
            "harbor",
            "run",
            "-d",
            "terminal-bench/terminal-bench-2",
            "-a",
            "terminus-2",
            "-m",
            "openai/local-llama-server",
            "-n",
            "1",
        ]
        out = subprocess.run(
            run_cmd,
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "OPENAI_API_BASE": base_url, "OPENAI_API_KEY": "dummy"},
        )
        score = parse_terminal_bench_score((out.stdout or "") + "\n" + (out.stderr or ""))
        wall_time = time.time() - t0
        patch_row(row_id, {
            "_score": score,
            "_bad_rate": 0.0,
            "_wall_time": wall_time,
        })
    finally:
        stop_process(server)
    row = _DB.execute("SELECT rowid, * FROM experiments WHERE rowid = ?", (row_id,)).fetchone()
    assert row is not None, row_id
    patch_row(row_id, double_underscore_fields(row))


@functools.partial(BENCHMARKS.setdefault, "dummybench")
def _(args: dict[str, str], row_id: int, _server_args: list[str]):
    def parse_dummy_score(output: str) -> float:
        return float(json.loads(output)["acc"]) / 100.0

    t0 = time.time()
    out = subprocess.run(["python3", str(pathlib.Path.home() / "dummybench.py")], check=True, capture_output=True, text=True)
    patch_row(row_id, {
        "_score": parse_dummy_score(out.stdout),
        "_bad_rate": 0.0,
        "_wall_time": time.time() - t0,
    })
    row = _DB.execute("SELECT rowid, * FROM experiments WHERE rowid = ?", (row_id,)).fetchone()
    assert row is not None, row_id
    patch_row(row_id, double_underscore_fields(row))


@functools.partial(BENCHMARKS.setdefault, "mbpp")
@functools.partial(BENCHMARKS.setdefault, "humaneval")
def _(args: dict[str, str], row_id: int, server_args: list[str]):
    def parse_score(eval_json: pathlib.Path) -> float:
        return float(json.loads(eval_json.read_text())["pass_at_k"]["plus"]["pass@1"])

    def compute_bad_rate_from_jsonl(jsonl_path: pathlib.Path) -> float:
        total = 0
        bad = 0
        with jsonl_path.open() as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                total += 1
                obj = json.loads(line)
                completion = obj.get("completion") or obj.get("output") or obj.get("solution")
                if completion is None or not str(completion).strip():
                    bad += 1
        return (bad / total) if total else 0.0

    evalplus_dir = pathlib.Path("../../evalplus").resolve()
    evalplus_root = evalplus_dir / "evalplus_results"
    bench = args["_bench"]
    base_url = "http://localhost:8080/v1"

    server = subprocess.Popen(["llama-server", *server_args], stdout=sys.stderr, stderr=sys.stderr, text=True)

    alias = f"exp-{int(time.time())}-{bench}"
    run_temp = str(args.get("temp", "0.0") or "0.0")
    out_jsonl = evalplus_root / bench / f"{alias}_openai_temp_{run_temp}.jsonl"
    out_eval = evalplus_root / bench / f"{alias}_openai_temp_{run_temp}_eval_results.json"
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    try:
        wait_server_ready(server, base_url)
        eval_cmd = [
            str((evalplus_dir / ".venv/bin/evalplus.evaluate").resolve()),
            bench,
            "--model",
            alias,
            "--backend",
            "openai",
            "--base_url",
            base_url,
            "--temperature",
            run_temp,
            "--root",
            str(evalplus_root),
            "--i_just_wanna_run",
        ]
        if float(run_temp) == 0.0:
            eval_cmd.extend(["--greedy", "True"])

        run_checked_with_server(eval_cmd, server, cwd=evalplus_dir)
        score = parse_score(out_eval)
        bad_rate = compute_bad_rate_from_jsonl(out_jsonl)
        wall_time = time.time() - t0
        patch_row(row_id, {
            "_score": score,
            "_bad_rate": bad_rate,
            "_wall_time": wall_time,
        })
    finally:
        stop_process(server)
    row = _DB.execute("SELECT rowid, * FROM experiments WHERE rowid = ?", (row_id,)).fetchone()
    assert row is not None, row_id
    patch_row(row_id, double_underscore_fields(row))


def main(argv: list[str]):
    assert len(argv) >= 2 and argv[1] in {"run", "check"}, "usage: exp.py <run|check> [--<arg> <value>...]"
    if argv[1] == "check":
        for row in _DB.execute("SELECT rowid, * FROM experiments"):
            patch_row(int(row["rowid"]), double_underscore_fields(row))
    else:
        args: dict[str, typing.Any] = {}
        i = 2
        while i < len(argv):
            key = argv[i]
            assert key.startswith("--"), key
            args[key[2:].replace("-", "_")] = argv[i + 1]
            i += 2

        assert "model" in args, "--model is required"
        args["model"] = pathlib.Path(args["model"]).name
        args["_file_size"] = (HF_ROOT / args["model"]).stat().st_size / 1e9
        bench = args["_bench"]

        row_id = get_row(args)
        server_args = build_server_args(args)
        BENCHMARKS[bench](args, row_id, server_args)


if __name__ == "__main__":
    main(sys.argv)
