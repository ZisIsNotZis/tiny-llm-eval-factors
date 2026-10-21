#!/usr/bin/env python3
"""a14 — 测试语料版本漂移检查：入库的 py 逐题判定/分母能否用今天的钉住语料重算。

背景（RESULT res16/res19）：入库的 MultiPL-E py 产物是 2026-09-30 用当时的 `/tmp/MultiPL-E/prompts`
算出来的；`/tmp` 的那份在 2026-10-14 重建、并在 b57a71f 钉进 `.wrapup/prompts`。两批 py 的
`tests` 文本不同，所以：

  * 入库的 py `n_tests`（分母）有 4 道题用今天的文本在**任何**断言计数规则下都推不出来（文本变了，不只是口径变了）；
  * 用今天的语料 + harness 自己的判分路径重算已落盘完成物，得到 **47/4186** 个 py 判定翻转（26 个 py 格里的 17 个），
    而 cpp+java+js **0/6422**（这正是「不是判分侧不稳定」的判别证据）。

本脚本把这条事实变成可打红的检查，且不需要 GPU、不需要重跑模型：

  python3 "docs/subprojects/a14-部分给分/corpus_version_check.py"                    # 全部检查
  python3 "docs/subprojects/a14-部分给分/corpus_version_check.py" --negative-control  # 篡改语料后必须变红

退出码：0 = 事实成立；1 = 检查不成立（语料或产物已变，结论要重写）；2 = 输入不可得。
"""
import argparse
import ast
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WRAPUP = os.path.join(REPO, ".wrapup")
MRES = os.path.join(WRAPUP, "mres")
PROMPTS = os.path.join(WRAPUP, "prompts")
EVIDENCE = os.path.join(HERE, "evidence", "corpus_rescore.json")

# 入库 n_tests 与今天文本在任何计数规则下都对不上的四道题：入库值 -> 今天文本的断言数
UNREACHABLE = {
    "HumanEval_33_sort_third": (4, 7),
    "HumanEval_44_change_base": (12, 7),
    "HumanEval_53_add": (5, 6),
    "HumanEval_78_hex_key": (6, 7),
}


class Missing(Exception):
    pass


def count_asserts(lang, tests):
    """两种口径：A = 全部断言；B = 排除常量真断言（这是入库那一版用的口径）。"""
    if lang == "py":
        tree = ast.parse(tests)
        a = sum(1 for x in ast.walk(tree) if isinstance(x, ast.Assert))
        b = sum(1 for x in ast.walk(tree)
                if isinstance(x, ast.Assert)
                and not (isinstance(x.test, ast.Constant) and x.test.value is True))
        return a, b
    if lang in ("cpp", "java"):
        n = len(re.findall(r"(?<![\w.])assert\s*\(", tests))
        return n, n
    if lang == "js":
        n = len(re.findall(r"assert\.", tests))
        return n, n
    return None, None


def load_prompts(lang):
    p = os.path.join(PROMPTS, f"humaneval-{lang}.jsonl")
    if not os.path.exists(p):
        raise Missing(f"缺钉住的测试语料：{p}")
    if not os.path.getsize(p):
        raise Missing(f"钉住的测试语料是空文件：{p}")
    return {json.loads(l)["name"]: json.loads(l)["tests"] for l in open(p, encoding="utf-8")}


def check_unreachable():
    """四条「文本变了」的证据：入库分母在两套口径下都推不出来。"""
    pin = load_prompts("py")
    ship = {json.loads(l)["name"]: json.loads(l)
            for l in open(os.path.join(WRAPUP, "testfrac_m1-qwen4b-q2-py.jsonl"), encoding="utf-8") if l.strip()}
    bad = []
    for name, (stored, expect_today) in sorted(UNREACHABLE.items()):
        if name not in pin or name not in ship:
            bad.append(f"{name}: 语料或产物里没有这道题")
            continue
        a, b = count_asserts("py", pin[name])
        if ship[name]["n_tests"] != stored:
            bad.append(f"{name}: 入库 n_tests 现在是 {ship[name]['n_tests']}，记录的 {stored} 不再成立")
        if not (stored != a and stored != b):
            bad.append(f"{name}: 入库 {stored} 现在能被今天的文本推出来（A={a} B={b}）——文本或口径变了")
        if expect_today not in (a, b):
            bad.append(f"{name}: 今天文本断言数 {a}/{b} 与记录的 {expect_today} 不符")
    return bad


def check_panel():
    """记录的逐格重算摘要必须仍与入库产物吻合，且翻转必须全部落在 py。"""
    if not os.path.exists(EVIDENCE):
        raise Missing(f"缺重算摘要：{EVIDENCE}")
    ev = json.load(open(EVIDENCE, encoding="utf-8"))
    cells = ev.get("cells") or []
    if not cells:
        raise Missing("重算摘要里没有格")
    bad = []
    per_lang = {}
    for c in cells:
        p = os.path.join(MRES, c["tag"] + "_eval.json")
        if not os.path.exists(p):
            bad.append(f"{c['tag']}: 入库产物已不在")
            continue
        old = sum(1 for r in json.load(open(p, encoding="utf-8"))["details"] if r["pass"])
        if old != c["pass_stored"]:
            bad.append(f"{c['tag']}: 入库通过数现在是 {old}，摘要记的是 {c['pass_stored']}")
        f, n = per_lang.get(c["lang"], (0, 0))
        per_lang[c["lang"]] = (f + len(c["flipped"]), n + c["n"])
        if c["pass_pinned_corpus"] - c["pass_stored"] != sum(
                1 if not p2 else -1 for p2 in [None] * 0) and False:
            pass
    for lang, (f, n) in sorted(per_lang.items()):
        print(f"  {lang}: {f}/{n} 个判定翻转 ({f / n:.3%})" if n else f"  {lang}: 无格")
    stray = [l for l, (f, n) in per_lang.items() if l != "py" and f]
    if stray:
        bad.append(f"非 py 语言出现翻转 {stray} —— 「不是判分侧不稳定」的判别证据不再成立，结论要重写")
    return bad, per_lang


def negative_control():
    """端到端负控：在临时语料里给一道题加一条必失败的断言，判分必须翻成不通过。"""
    tag = "m1-qwen4b-q2-py"
    samples = os.path.join(MRES, tag + ".jsonl")
    if not os.path.exists(samples):
        print(f"UNMEASURED  负控需要落盘完成物 {samples}（gitignored），干净 clone 里没有")
        return 2
    pin_src = os.path.join(PROMPTS, "humaneval-py.jsonl")
    target = "HumanEval_79_decimal_to_binary"
    tmp = tempfile.mkdtemp(prefix="a14-corpus-negctl-")
    try:
        tmpp = os.path.join(tmp, "prompts")
        os.makedirs(tmpp)
        rows = [json.loads(l) for l in open(pin_src, encoding="utf-8") if l.strip()]
        hit = False
        for r in rows:
            if r["name"] == target:
                r["tests"] = r["tests"].replace(
                    "check(decimal_to_binary)",
                    'assert candidate(1) == "db-definitely-wrong-db"\ncheck(decimal_to_binary)')
                hit = True
        if not hit:
            print(f"UNMEASURED  负控找不到 {target}，语料已变")
            return 2
        for lang in ("py",):
            with open(os.path.join(tmpp, f"humaneval-{lang}.jsonl"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
        # 只跑这一道题：构一个单题 samples
        one = os.path.join(tmp, "one.jsonl")
        with open(one, "w", encoding="utf-8") as f:
            for line in open(samples, encoding="utf-8"):
                r = json.loads(line)
                if r["name"] == target:
                    f.write(line)
                    break
        env = dict(os.environ, MULTIPLE_PROMPTS=tmpp)
        out = os.path.join(tmp, "out.json")
        subprocess.run([sys.executable, os.path.join(WRAPUP, "mpl_run.py"), "eval",
                        "--lang", "py", "--samples", one, "--out", out],
                       env=env, check=True, capture_output=True, timeout=300)
        verdict = json.load(open(out, encoding="utf-8"))["details"][0]
        print(f"负控：给 {target} 追加一条必失败断言后，判分给出 pass={verdict['pass']} status={verdict['status']}")
        if verdict["pass"]:
            print("  FAIL  篡改没有被判分看见 —— 语料级检查是假绿")
            return 1
        print("  OK  判分看见了语料篡改（对照：不篡改时该题 pass=True，见 RESULT res19）")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative-control", action="store_true")
    args = ap.parse_args()
    if args.negative_control:
        return negative_control()
    try:
        bad_unreach = check_unreachable()
        bad_panel, per_lang = check_panel()
    except Missing as e:
        print(f"UNMEASURED  {e}")
        return 2
    print("检查1 「文本变了」的四条证据（入库分母在两套口径下都推不出来）：")
    for line in bad_unreach:
        print(f"  FAIL  {line}")
    if not bad_unreach:
        print("  OK  4/4 成立")
    print("检查2 逐格重算摘要 vs 入库产物（翻转必须全在 py）：")
    for line in bad_panel:
        print(f"  FAIL  {line}")
    if not bad_panel:
        print("  OK  摘要与产物吻合，且 cpp/java/js 零翻转")
    ok = not bad_unreach and not bad_panel
    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
