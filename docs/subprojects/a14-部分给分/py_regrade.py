#!/usr/bin/env python3
"""a14 — 用钉住的语料把历史 py 格重新判分，给出「旧值 → 新值」与它移动了哪些结论边界。

背景（RESULT res16/res19）：历史 py 产物是 2026-09-30 用当时的 `/tmp/MultiPL-E/prompts` 算的；
语料在 2026-10-14 重建、2026-10-19 才钉进 `.wrapup/prompts`。两代 `tests` 文本不同，
所以历史 py 分数不是今天的测量。

本脚本的两个模式：

  --rescore   用 `.wrapup/prompts`（先校验 `SHA256SUMS`）调 `.wrapup/mpl_run.py eval` 重打所有
              历史 py 格，写 `evidence/py_regrade.json`。需要 gitignored 完成物；缺了就 exit 2。
  默认         读 `evidence/py_regrade.json` 复算并核对：语料 sha 必须与记录一致、每个格的旧值
              必须仍与入库 `_eval.json` 吻合。核对失败 exit 1（数字要重写），输入缺失 exit 2。

  python3 "docs/subprojects/a14-部分给分/py_regrade.py"
  python3 "docs/subprojects/a14-部分给分/py_regrade.py" --rescore
"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WRAPUP = os.path.join(REPO, ".wrapup")
MRES = os.path.join(WRAPUP, "mres")
PROMPTS = os.path.join(WRAPUP, "prompts")
DB = os.path.join(REPO, "experiments.sqlite")
EVIDENCE = os.path.join(HERE, "evidence", "py_regrade.json")
LANG = "py"


class Missing(Exception):
    pass


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def verify_corpus():
    """SHA256SUMS 必须全过；不过就说明钉住的语料本身被换过。"""
    sums = os.path.join(PROMPTS, "SHA256SUMS")
    if not os.path.exists(sums):
        raise Missing(f"缺 {sums}：语料没有被钉住，无法谈代次")
    r = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=PROMPTS,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise Missing(f"SHA256SUMS 校验失败，钉住的语料已变：\n{r.stdout}{r.stderr}")
    return sha256(os.path.join(PROMPTS, f"humaneval-{LANG}.jsonl"))


def py_cells():
    """所有既有入库 `_eval.json`、又有落盘完成物的历史 py 格。"""
    out = []
    for p in sorted(glob.glob(os.path.join(MRES, "*-py_eval.json"))):
        tag = os.path.basename(p)[: -len("_eval.json")]
        if os.path.exists(os.path.join(MRES, tag + ".jsonl")):
            out.append(tag)
    if not out:
        raise Missing("一个「既有 _eval.json 又有完成物」的 py 格都没有")
    return out


def rescore():
    corpus_sha = verify_corpus()
    cells = py_cells()
    print(f"重打分 {len(cells)} 个历史 py 格，语料 sha256={corpus_sha}")
    recs = []
    for tag in cells:
        out = os.path.join("/tmp", "a14", "pyall", tag + ".json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if not (os.path.exists(out) and os.path.getsize(out)):
            r = subprocess.run([sys.executable, os.path.join(WRAPUP, "mpl_run.py"), "eval",
                                "--lang", LANG, "--samples", os.path.join(MRES, tag + ".jsonl"),
                                "--out", out], capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                raise Missing(f"重打分 {tag} 失败：{r.stderr[-300:]}")
        new = {x["name"]: bool(x["pass"]) for x in json.load(open(out))["details"]}
        old = {x["name"]: bool(x["pass"]) for x in
               json.load(open(os.path.join(MRES, tag + "_eval.json")))["details"]}
        common = set(new) & set(old)
        recs.append({
            "tag": tag,
            "n": len(common),
            "pass_old": sum(1 for v in old.values() if v),
            "pass_new": sum(1 for v in new.values() if v),
            "flipped": sorted(x for x in common if new[x] != old[x]),
            "dropped": sorted(set(old) - set(new)),
        })
        print(f"  {tag}: {recs[-1]['pass_old']} -> {recs[-1]['pass_new']} "
              f"({len(recs[-1]['flipped'])} 题翻转)")
    doc = {"what": "历史 py 格用钉住语料重打分的旧值/新值",
           "corpus_sha256": corpus_sha,
           "scoring_identity": f"mpl-raw-greedy-768;corpus={corpus_sha[:12]}",
           "scorer": ".wrapup/mpl_run.py eval",
           "cells": recs}
    os.makedirs(os.path.dirname(EVIDENCE), exist_ok=True)
    json.dump(doc, open(EVIDENCE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"写入 {EVIDENCE}（{len(recs)} 格）")
    return 0


def load_evidence():
    if not os.path.exists(EVIDENCE):
        raise Missing(f"缺重打分摘要 {EVIDENCE}（先跑 --rescore）")
    doc = json.load(open(EVIDENCE, encoding="utf-8"))
    if not doc.get("cells"):
        raise Missing("重打分摘要里没有格")
    if not doc.get("corpus_sha256"):
        raise Missing("重打分摘要没记语料 sha256，无法谈代次")
    return doc


def db_rows():
    """``(model, protocol, score, source_file)``，只看 py 列的 MultiPL-E 行。"""
    import sqlite3
    if not os.path.exists(DB):
        raise Missing(f"缺库 {DB}")
    con = sqlite3.connect(DB)
    return con.execute(
        "SELECT model, protocol, _score, source_file FROM experiments "
        "WHERE bench_family='humaneval-multipl-e' AND language=? AND _score IS NOT NULL",
        (LANG,)).fetchall()


def analyse(doc):
    cells = doc["cells"]
    changed = [c for c in cells if c["pass_new"] != c["pass_old"]]
    flips = sum(len(c["flipped"]) for c in cells)
    total = sum(c["n"] for c in cells)
    print(f"格 {len(cells)}（{total} 道题）：{len(changed)} 格改变分数，{flips} 题翻转 "
          f"（{flips / total:.3%}）")
    print(f"\n{'tag':28} {'n':>4} {'旧':>5} {'新':>5} {'Δ题':>4} {'翻转':>4}")
    for c in sorted(cells, key=lambda c: -(c["pass_new"] - c["pass_old"])):
        d = c["pass_new"] - c["pass_old"]
        if d or c["flipped"]:
            print(f"{c['tag']:28} {c['n']:>4} {c['pass_old']:>5} {c['pass_new']:>5} "
                  f"{d:>+4} {len(c['flipped']):>4}")

    # 结论边界：同语言、tag 只差一个字段的 py 格对，语料代次是否把符号改掉
    by_tag = {c["tag"]: c for c in cells}
    rev = []
    for a in sorted(by_tag):
        for b in sorted(by_tag):
            if a >= b:
                continue
            pa, pb = a.split("-"), b.split("-")
            if len(pa) != len(pb) or sum(1 for x, y in zip(pa, pb) if x != y) != 1:
                continue
            ca, cb = by_tag[a], by_tag[b]
            if ca["n"] != cb["n"]:
                continue
            dold = cb["pass_old"] - ca["pass_old"]
            dnew = cb["pass_new"] - ca["pass_new"]
            if dold * dnew < 0 or (dold == 0) != (dnew == 0):
                rev.append((a, b, dold, dnew))
    print(f"\n语料代次改掉符号的 py 格对（同语言、tag 只差一个字段、同题数）：{len(rev)} 对")
    for a, b, dold, dnew in rev:
        print(f"  {a} vs {b}: 旧 {dold:+d} 题 → 新 {dnew:+d} 题")
    near = [(a, b, dold, dnew) for a, b, dold, dnew in rev if abs(dold) <= 2 or abs(dnew) <= 2]
    print(f"  其中至少一侧落在 1–2 题的近差区：{len(near)} 对")

    # §13 影响面：按 (py, 旧分数) 在库里找行
    rows = db_rows()
    hits, ambiguous, nomatch = [], [], []
    for c in changed:
        old = c["pass_old"] / c["n"]
        cand = [r for r in rows if abs(r[2] - old) < 5e-5]
        prefix = c["tag"].split("-")[0] + "_"
        pref = [r for r in cand if (r[3] or "").startswith(prefix)]
        if len(pref) == 1:
            hits.append((c["tag"], pref[0][0], c["pass_old"], c["pass_new"]))
        elif len(cand) == 1:
            hits.append((c["tag"], cand[0][0], c["pass_old"], c["pass_new"]))
        elif cand:
            ambiguous.append((c["tag"], len(cand)))
        else:
            nomatch.append(c["tag"])
    print(f"\n§13（逐语言表）里会因为这次取代而动的 py 格：唯一配对 {len(hits)}，"
          f"多重配对 {len(ambiguous)}，库里没有对应行 {len(nomatch)}")
    for tag, model, o, n in hits:
        print(f"  {tag:28} {model[:34]:34} {o:>3} → {n:>3}  ({o / 161:.4f} → {n / 161:.4f})")
    if ambiguous:
        print(f"  多重配对（不能猜，交 i02 按 source_file 逐条对）：{ambiguous}")
    if nomatch:
        print(f"  库里没有对应行（该格不在 §13 里）：{nomatch}")
    return {"cells": len(cells), "changed": len(changed), "flips": flips,
            "total": total, "reversals": len(rev), "near": len(near),
            "report_cells": len(hits), "hits": hits}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rescore", action="store_true")
    args = ap.parse_args()
    try:
        if args.rescore:
            return rescore()
        doc = load_evidence()
        corpus = verify_corpus()
        if corpus != doc["corpus_sha256"]:
            print(f"FAIL  钉住的语料 sha256 现在是 {corpus}，摘要记的是 {doc['corpus_sha256']}")
            return 1
        bad = []
        for c in doc["cells"]:
            p = os.path.join(MRES, c["tag"] + "_eval.json")
            if not os.path.exists(p):
                bad.append(f"{c['tag']}: 入库产物已不在")
                continue
            old = sum(1 for x in json.load(open(p, encoding="utf-8"))["details"] if x["pass"])
            if old != c["pass_old"]:
                bad.append(f"{c['tag']}: 旧值现在是 {old}，摘要记的是 {c['pass_old']}")
        for line in bad:
            print(f"  FAIL  {line}")
        if bad:
            return 1
        print(f"语料代次：sha256={corpus}（SHA256SUMS 全过），判分身份串 "
              f"{doc.get('scoring_identity')}")
        analyse(doc)
        print("RESULT PASS")
        return 0
    except Missing as e:
        print(f"UNMEASURED  {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
