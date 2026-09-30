#!/usr/bin/env python3
"""Build the T1 PPL corpora from local data (no network).

Outputs (in .wrapup/ppl_corpora/):
  code_python.txt  HumanEval+ / MBPP+ canonical solutions + tests (+ MultiPL-E py)
  code_multi.txt   MultiPL-E cpp/java/js/rs prompts + tests
  nl_english.txt   BFCL v4 question text (all categories present locally)
Corpora are repeated to >= MIN_CHARS so each holds >= ~200k tokens.
"""
import json, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ppl_corpora")
os.makedirs(OUT, exist_ok=True)
MIN_CHARS = 1_000_000  # ~250k tokens; -c2048 x 40 chunks needs ~80k tokens

def evalplus_py():
    parts = []
    for f in ["HumanEvalPlus-v0.1.10.jsonl", "MbppPlus-v0.2.0.jsonl"]:
        p = os.path.expanduser("~/.cache/evalplus/" + f)
        with open(p) as fh:
            for line in fh:
                d = json.loads(line)
                parts.append("# ==== %s ====\n%s%s%s\n" % (
                    d.get("task_id", "?"),
                    d.get("prompt", ""),
                    d.get("canonical_solution", ""),
                    d.get("test", "")))
    return "\n".join(parts)

def multipl_e(langs, include_py_mirror=False):
    parts = []
    for lang in langs:
        p = "/tmp/MultiPL-E/prompts/humaneval-%s.jsonl" % lang
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            for line in fh:
                d = json.loads(line)
                parts.append("// ==== %s [%s] ====\n%s%s\n" % (
                    d.get("name", "?"), lang, d.get("prompt", ""), d.get("tests", "")))
    return "\n".join(parts)

def bfcl_questions():
    d = os.path.join(HERE, "bfclenv/lib/python3.11/site-packages/bfcl_eval/data")
    parts = []
    for f in sorted(glob.glob(os.path.join(d, "BFCL_v4_*.json"))):
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if not isinstance(item, dict):
                    continue
                for turn in item.get("question") or []:
                    if isinstance(turn, list):
                        for msg in turn:
                            if isinstance(msg, dict) and msg.get("content"):
                                parts.append(str(msg["content"]))
                    elif isinstance(turn, str):
                        parts.append(turn)
    return "\n".join(parts)

def repeat_to(text, min_chars=MIN_CHARS):
    if not text.strip():
        raise SystemExit("empty corpus text")
    out, n = [], 0
    while n < min_chars:
        out.append(text)
        n += len(text)
    return "\n".join(out)

def main():
    corpora = {
        "code_python": evalplus_py() + "\n" + multipl_e(["py"]),
        "code_multi": multipl_e(["cpp", "java", "js", "rs"]),
        "nl_english": bfcl_questions(),
    }
    for name, text in corpora.items():
        body = repeat_to(text)
        path = os.path.join(OUT, name + ".txt")
        with open(path, "w") as fh:
            fh.write(body)
        print("%s: raw=%d chars, final=%d chars, ~%d tokens" % (
            name, len(text), len(body), len(body) // 4))

if __name__ == "__main__":
    main()
