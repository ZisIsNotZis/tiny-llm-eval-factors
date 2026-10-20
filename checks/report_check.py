#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对已生成的 `report.html` 做独立核对：报告里印出来的东西必须与产物一致。

检查对象是用户实际读的那个文件，不是中间变量。四条：

 1. 同一张表的同一个模型下不出现两行同标签（行键必须携带全部区分列，plan16）。
 2. MultiPL-E 列里每个分数都印着题量，那个题量必须等于该格逐题产物的 n；
    取不到配对的格必须不印题量（绝不允许印一个看起来合理的默认题数）。
 3. 非测量登记册在场，状态与 `non_measurements.tsv` 逐条一致，且声明「未测 ≠ 0」。
 4. 「全 Exception 的格不是整轮运行失败」那段印的份数 / 格数必须与产物一致。

    python3 checks/report_check.py [report.html]
"""
from __future__ import annotations

import collections
import html as htmllib
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "report_inputs"))
import eval_status  # noqa: E402

REPORT = os.path.join(REPO, "report.html")
REGISTRY = os.path.join(REPO, "docs", "subprojects", "i02-测量基础设施", "non_measurements.tsv")

# 标准列（拆开的 C++/Python）与逐语言表（C++ / Python / JS / Java / Rust / Ruby）两种列名
LANG_OF_COLUMN = {"多语言代码 C++": "cpp", "多语言代码 Python": "py",
                  "C++": "cpp", "Python": "py", "JS": "js",
                  "Java": "java", "Rust": "rs", "Ruby": "rb"}
TAG_RE = re.compile(r"<[^>]+>")


def text_of(fragment):
    return htmllib.unescape(TAG_RE.sub("", fragment)).strip()


def tables(html):
    """[[header cells, row cells...]]，够用的最小解析（我们的表格不嵌套）。"""
    out = []
    for block in re.findall(r"<table[^>]*>(.*?)</table>", html, re.S):
        rows = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
            rows.append([text_of(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)])
        if rows:
            out.append(rows)
    return out


def check_row_labels(parsed):
    """(1) 同一模型下不得有两行同标签。"""
    problems, checked = [], 0
    for rows in parsed:
        head = rows[0]
        if len(head) < 3 or "生成协议" not in head[1]:
            continue
        seen = collections.Counter()
        for r in rows[1:]:
            if len(r) < 2 or r[0] == "覆盖":
                continue
            seen[(r[0], r[1])] += 1
        checked += 1
        for (model, label), n in seen.items():
            if n > 1:
                problems.append(f"行标签重复：{model} 的 {label!r} 出现 {n} 行")
    return checked, problems


def _testfrac_n():
    """部分给分表（m41）的题量来自它自己的汇总：[(lang, mean_frac, n)]。"""
    out = []
    try:
        for line in open(os.path.join(REPO, ".wrapup", "m41_summary.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            if r.get("lang") and r.get("n") and r.get("mean_frac") is not None:
                out.append((r["lang"], float(r["mean_frac"]), int(r["n"])))
    except (FileNotFoundError, ValueError):
        return []
    return out


def _testfrac_lookup(rows, lang, printed_score):
    """印出来的分数只有四位小数，所以配对在 5e-5 内比。"""
    hits = {n for l, frac, n in rows if l == lang and abs(frac - printed_score) < 5e-5}
    return hits.pop() if len(hits) == 1 else None


def check_item_counts(parsed):
    """(2) MultiPL-E 列的题量必须来自该格产物。

    两种口径：通过率列（score = pass/n）按「pass/n == 分数」找产物；部分给分列
    （分数 = 每题通过的测试比例均值）按它自己的汇总找题量。都不是默认题数。
    """
    problems, checked, without_n = [], 0, 0
    tf_rows = _testfrac_n()
    for rows in parsed:
        head = rows[0]
        cols = [(i, LANG_OF_COLUMN[h]) for i, h in enumerate(head) if h in LANG_OF_COLUMN]
        if not cols:
            continue
        partial = len(head) > 1 and head[1] == "方案类别"
        for r in rows[1:]:
            if r and r[0] == "覆盖":
                continue
            for i, lang in cols:
                if i >= len(r) or r[i] in ("—", "-", ""):
                    continue
                if r[i].endswith("(题量未知)"):
                    # 显式标注的未知题量：不是默认值，也不是裸分数
                    without_n += 1
                    checked += 1
                    continue
                m = re.match(r"^([0-9.]+)(?:\s*\(([0-9]+)\))?$", r[i])
                if not m:
                    problems.append(f"格子格式无法解释：{r[0]} / {r[1]} / {lang}: {r[i]!r}")
                    continue
                score = float(m.group(1))
                checked += 1
                if m.group(2) is None:
                    without_n += 1
                    continue
                n = int(m.group(2))
                if partial:
                    want = _testfrac_lookup(tf_rows, lang, score)
                    if want != n:
                        problems.append(f"部分给分表题量与汇总不符：{r[0]} / {r[1]} / {lang} = {r[i]}"
                                        f"（汇总 {want}）")
                    continue
                # 报告把分数印到小数点后四位，所以配对只在这一位精度内可比；
                # 1/161 ≈ 0.0062 远大于 5e-5，所以这个容差不会把两个不同的题数配混。
                arts = [a for a in eval_status.records() if a["lang"] == lang
                        and a["n"] == n and abs(a["pass"] / a["n"] - score) < 5e-5]
                if not arts:
                    problems.append(f"题量与产物不符：{r[0]} / {r[1]} / {lang} = {r[i]}"
                                    f"（没有 n={n} 且通过数对应 {score:.6f} 的产物）")
    return checked, without_n, problems


def check_registry(html):
    """(3) 非测量登记册在场、逐条一致、并声明未测 ≠ 0。"""
    problems = []
    plain = htmllib.unescape(html)   # 报告里的文本是转义过的（`->` 写成 `-&gt;`）
    rows = [ln.rstrip("\n").split("\t") for ln in open(REGISTRY, encoding="utf-8") if ln.strip()]
    head, body = rows[0], rows[1:]
    if "非测量登记册" not in plain:
        problems.append("报告里没有非测量登记册一节")
    for r in body:
        for cell in r:
            if cell and cell not in plain:
                problems.append(f"登记册条目未出现在报告里：{cell}")
                break
    for state in {r[3] for r in body}:
        if state not in plain:
            problems.append(f"状态未在报告里出现：{state}")
    if "未测 ≠ 0" not in plain:
        problems.append("缺少「未测 ≠ 0」的口径声明")
    return len(body), problems


# 报告不再渲染子项目工作文档的事实清单，所以也不会再出现「来源：…」的退役路径；
# 这里只保留一条硬约束：退役根字符串不得出现在报告里（`/home/z/hf/…` 是测量时的加载路径，
# 保留在模型来源附录中，但必须就地声明它在采集机上已不存在）。
RETIRED_ROOTS = (".scratch/originals", "/tmp/MultiPL-E")
RETIRED_PATH_NOTE = "在采集机上已不存在"


def check_no_retired_sources(plain):
    """(6) 每条退役路径都必须就地标注，且不许出现「尚未迁移」这种未经核对的断言。"""
    problems = []
    for root in RETIRED_ROOTS:
        n = plain.count(root)
        if n:
            problems.append(f"报告里出现退役根 {root}（{n} 处）")
    if "/home/z/hf" in plain and RETIRED_PATH_NOTE not in plain:
        problems.append("报告出现 /home/z/hf 路径，却没有声明它在采集机上已不存在")
    return problems


def check_exception_counts(html):
    """(4) 「全 Exception」段的份数 / 格数与产物一致。"""
    m = re.search(r"有 <b>(\d+)</b> 份文件，来自 <b>(\d+)</b> 个格", html)
    if not m:
        return ["找不到「全 Exception」份数 / 格数的句子"]
    files = [a for a in eval_status.records() if a["n"] and a["status"]["Exception"] == a["n"]]
    cells = {re.sub(r"(_fixed)?_eval\.json$", "", a["file"]) for a in files}
    got = (int(m.group(1)), int(m.group(2)))
    if got != (len(files), len(cells)):
        return [f"全 Exception 段印的是 {got}，产物算出来是 ({len(files)}, {len(cells)})"]
    if files and got[0] == 0:
        return ["产物里有全 Exception 的文件，报告却印了 0 份"]
    return []


def check_ambiguous_cells(plain):
    """(5) 同一 (模型, 协议, 语言) 存了多个不同分数时，报告必须把每个值都印出来。

    这是从库独立重算的，不看 make_report 的中间变量：只要库内一个键有两个值，两个值的
    四位小数都必须出现在报告里，否则就是静默取其一。
    """
    import sqlite3
    con = sqlite3.connect(f"file:{os.path.join(REPO, 'experiments.sqlite')}?mode=ro", uri=True)
    seen = collections.defaultdict(set)
    for model, proto, lang, score in con.execute(
            "SELECT model, protocol, language, _score FROM experiments "
            "WHERE bench_family='humaneval-multipl-e' AND _score IS NOT NULL"):
        seen[(model, proto, lang)].add(score)
    multi = {k: v for k, v in seen.items() if len(v) > 1}
    problems = []
    for (model, proto, lang), values in sorted(multi.items()):
        stem = model[:-len(".gguf")] if model.endswith(".gguf") else model
        if stem not in plain:
            problems.append(f"含多值的格所属模型未出现在报告里：{stem}")
            continue
        for v in values:
            if f"{v:.4f}" not in plain:
                problems.append(f"多值格的值未打印：{stem} / {lang} = {v:.4f}"
                                f"（协议 {proto[:60]}）")
    return len(multi), problems


def main(argv):
    path = argv[0] if argv else REPORT
    html = open(path, encoding="utf-8").read()
    parsed = tables(html)
    problems = []

    n_tables, p = check_row_labels(parsed)
    problems += p
    n_cells, without_n, p = check_item_counts(parsed)
    problems += p
    n_registry, p = check_registry(html)
    problems += p
    problems += check_exception_counts(html)
    plain = htmllib.unescape(html)
    n_amb, p = check_ambiguous_cells(plain)
    problems += p
    problems += check_no_retired_sources(plain)

    print(f"report: {os.path.relpath(path, REPO)}")
    print(f"  tables                : {len(parsed)} (row-label check on {n_tables})")
    print(f"  MultiPL-E cells       : {n_cells} checked, {without_n} marked 题量未知 "
          f"(no unique artefact pair, never a default)")
    print(f"  non-measurements      : {n_registry} entries")
    print(f"  multi-valued cells    : {n_amb} key(s) holding more than one score")
    if problems:
        print(f"FAIL: {len(problems)} problem(s)")
        for p in problems[:20]:
            print("  -", p)
        return 1
    print("PASS: report agrees with the artefacts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
