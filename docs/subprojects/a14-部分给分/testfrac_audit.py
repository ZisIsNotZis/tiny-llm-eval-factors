#!/usr/bin/env python3
"""a14 部分给分 — 可得性矩阵与二元一致性自检。

只读已入库的产物（`.wrapup/mres/*_eval.json`、`.wrapup/testfrac_*.jsonl`），所以干净 clone 里
应该 `exit 0`。缺输入时 `exit 2`，绝不因为读不到东西就打印成功。

  python3 "docs/subprojects/a14-部分给分/testfrac_audit.py"                  # 全部检查 + 矩阵
  python3 "docs/subprojects/a14-部分给分/testfrac_audit.py" --matrix         # 只打印可得性矩阵
  python3 "docs/subprojects/a14-部分给分/testfrac_audit.py" --negative-control
                                                            # 在临时副本上把一道通过题改成不通过，
                                                            # 一致性检查必须变红（exit 1）

退出码：0 = 全部成立；1 = 有检查不成立；2 = 输入不可得（缺文件/结构不认识）。
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
MRES = os.path.join(REPO, ".wrapup", "mres")
WRAPUP = os.path.join(REPO, ".wrapup")


class Missing(Exception):
    """输入不可得：退出码 2，与「检查不成立」（1）区分。"""


def tracked_mres():
    try:
        out = subprocess.run(["git", "-C", REPO, "ls-files", ".wrapup/mres"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        raise Missing(f"git ls-files 失败：{e}")
    paths = [os.path.join(REPO, p) for p in out.split()]
    if not paths:
        raise Missing("`.wrapup/mres` 里没有已跟踪的 *eval.json —— 本检查拿不到输入")
    return sorted(paths)


def classify(paths):
    """把逐题 eval 产物按结构分类；不认识的结构就是缺陷。"""
    kinds = {"multip_e": [], "evalplus": [], "bfcl": []}
    unknown = []
    for p in paths:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError) as e:
            unknown.append((p, f"读不出 JSON：{e}"))
            continue
        if isinstance(d, dict) and "details" in d:
            recs = d["details"]
            if not recs or not {"name", "pass"} <= set(recs[0]):
                unknown.append((p, "details 缺 name/pass"))
            else:
                kinds["multip_e"].append(p)
        elif isinstance(d, dict) and "eval" in d:
            kinds["evalplus"].append(p)
        elif isinstance(d, dict) and "per_category" in d:
            kinds["bfcl"].append(p)
        else:
            unknown.append((p, f"结构不认识：{sorted(d) if isinstance(d, dict) else type(d).__name__}"))
    return kinds, unknown


def testfrac_items():
    its = sorted(f for f in glob.glob(os.path.join(WRAPUP, "testfrac_*.jsonl"))
                 if not f.endswith("_summary.jsonl"))
    if not its:
        raise Missing("`.wrapup/testfrac_*.jsonl` 逐题文件一个都没有 —— 比例口径不可得")
    return its


def load_items(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        out[r["name"]] = r
    return out


def agreement(items, mres_paths):
    """逐题比较 testfrac 的 binary_pass 与 harness 的 pass。

    返回 (pairs, items_compared, disagreements, unmatched)。
    未配上的格不算缺陷（可能是该格 _eval.json 未入库），但要报出来。
    """
    by_tag = {os.path.basename(p)[: -len("_eval.json")]: p
              for p in mres_paths if p.endswith("_eval.json")}
    pairs, compared, dis, unmatched = 0, 0, [], []
    for f in items:
        tag = os.path.basename(f)[len("testfrac_"): -len(".jsonl")]
        ev = by_tag.get(tag)
        if ev is None:
            unmatched.append(tag)
            continue
        pairs += 1
        evp = {r["name"]: bool(r["pass"]) for r in json.load(open(ev, encoding="utf-8"))["details"]}
        tf = load_items(f)
        common = set(evp) & set(tf)
        compared += len(common)
        if len(common) != len(evp) or len(common) != len(tf):
            dis.append(f"{tag}: 题集不同（eval {len(evp)} / testfrac {len(tf)} / 交集 {len(common)}）")
        bad = sorted(n for n in common if evp[n] != bool(tf[n]["binary_pass"]))
        if bad:
            dis.append(f"{tag}: {len(bad)} 道题二元判定不一致，例如 {bad[:3]}")
    return pairs, compared, dis, unmatched


def matrix(kinds, items):
    """每族一行：比例能不能从仓里推出来、缺什么、代价。"""
    langs = {}
    for f in items:
        lang = os.path.basename(f)[len("testfrac_"): -len(".jsonl")].rsplit("-", 1)[-1]
        langs[lang] = langs.get(lang, 0) + 1
    rows = [
        ("MultiPL-E (cpp/py/java)",
         f"可得：{len(items)} 格逐题文件已入库（{', '.join(f'{k} {v}' for k, v in sorted(langs.items()))}）",
         "无缺口", "0",
         "`python3 docs/subprojects/a14-部分给分/rank_compare.py`"),
        ("MultiPL-E (rs/rb/pl)",
         "不可得：`.wrapup/testfrac.py::RUNNERS` 只有 cpp/py/java/js，没有这三门语言的断言计数注入",
         "每门语言一套探针 + 重复二元一致性检查（res7 同一装置）",
         "CPU：每门语言 ≤60 分钟；GPU 0",
         "写好探针后：`testfrac.py --lang <新语言>` 跑一格，再用 `testfrac_audit.py` 的二元一致性检查看它是否与 harness 判分逐题一致"),
        ("EvalPlus (HumanEval+/MBPP+)",
         "部分：每题失败测试名在 artefact 里，但分母（该题测试数）在数据集侧，不在 artefact 里",
         "EvalPlus 数据集每题测试数（已在 `.wrapup/evalpy` venv 内，gitignored）",
         "CPU ≤30 分钟，GPU 0（不需重跑模型，fail_tests 已落盘）",
         "拿到分母后：对四个 `*-evalplus_eval.json` 算 `(总数-失败数)/总数`，并用 `base_status=='pass'` 逐题校对二元结论必须等价于「失败数==0」"),
        ("lm-eval ifeval",
         "可得且已得：`inst_level_strict_acc` 就是指令级比例，`prompt_level_strict_acc` 是题级；两者同在一个 json 里",
         "无缺口", "0",
         "`python3 docs/subprojects/a14-部分给分/testfrac_audit.py` 的检查3"),
        ("lm-eval gsm8k/mmlu/arc_challenge",
         "不可得：587 份 lmeval_*.json 里 0 份含逐题 samples（历史运行从不传 --log_samples）",
         "该格带 --log_samples 重跑",
         "GPU：`m100` gsm8k 单格 11 分钟量级，每族 ≥1 格",
         "重跑后：读 `results.samples[].exact_match`（或 `acc`），与聚合值对账；同题内部仍是二元，所以这族只能得到「逐题对不对」，得不到「题内部分分」"),
        ("BFCL",
         "不可得：已入库 15 份只有 n/correct/per_category，`.wrapup/bfcl_out` 为空；且 BFCL 一条用例就是一条测试，题内没有更细的官方粒度",
         "重新落盘逐用例原始输出",
         "本次不做：那是新指标（每轮/每参数通过率），不是现有 Y 的细化",
         "—（不做，所以不欠验证）"),
        ("新增一个 MultiPL-E 格的比例（单价）",
         "可得：只要完成物已落盘，重算比例 ~12 s CPU / 格（res15 实测 11.6 s，161 题，5 并发），0 GPU",
         "完成物 `.wrapup/mres/<tag>-<lang>.jsonl`（gitignored）+ 已钉住的测试语料",
         "CPU ~12 s/格；GPU 0。语料不钉住时得到的是另一组数（res16）",
         "`cd .wrapup && python3 testfrac.py --lang <lang> --samples mres/<tag>-<lang>.jsonl --out /tmp/x.jsonl`，再与 `<tag>_eval.json` 比逐题二元结论"),
    ]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", action="store_true", help="只打印可得性矩阵")
    ap.add_argument("--negative-control", action="store_true",
                    help="在临时副本上把一道通过题改成不通过，一致性检查必须变红")
    args = ap.parse_args()

    try:
        paths = tracked_mres()
        kinds, unknown = classify(paths)
        if unknown:
            for p, why in unknown:
                print(f"UNRECOGNISED  {os.path.relpath(p, REPO)}  {why}")
            raise Missing(f"{len(unknown)} 份产物结构不认识")
        if not kinds["multip_e"]:
            raise Missing("没有 MultiPL-E 结构的逐题产物")
        items = testfrac_items()
    except Missing as e:
        print(f"UNMEASURED  {e}")
        return 2

    if args.matrix:
        for fam, ok, need, cost, verify in matrix(kinds, items):
            print(f"\n[{fam}]")
            print(f"  {ok}")
            print(f"  缺：{need}")
            print(f"  代价：{cost}")
            print(f"  验证：{verify}")
        return 0

    if args.negative_control:
        return negative_control(items, kinds["multip_e"])

    n_items = sum(len(load_items(f)) for f in items)
    print(f"产物：MultiPL-E {len(kinds['multip_e'])} 份 / EvalPlus {len(kinds['evalplus'])} 份 / "
          f"BFCL {len(kinds['bfcl'])} 份；逐测试比例逐题文件 {len(items)} 格 {n_items} 道题")

    pairs, compared, dis, unmatched = agreement(items, kinds["multip_e"])
    print(f"检查1 二元一致性：配上的格 {pairs}，逐题比较 {compared} 道，不一致 {len(dis)} 项；"
          f"未配上（该格 _eval.json 未入库）{len(unmatched)} 格 {unmatched}")
    for d in dis:
        print(f"  FAIL  {d}")

    # 检查2：逐题文件必须带分母，否则比例不可复现
    no_den = []
    for f in items:
        for name, r in load_items(f).items():
            if not isinstance(r.get("n_tests"), int) or r["n_tests"] <= 0:
                no_den.append(f"{os.path.basename(f)}::{name}")
    print(f"检查2 分母在场：缺 n_tests 的逐题记录 {len(no_den)} 条")
    if no_den:
        print(f"  FAIL  {no_den[:5]}")

    # 检查3：ifeval 的指令级指标在 artifact 里（细粒度 Y 的零成本那一族）
    ifeval = glob.glob(os.path.join(MRES, "*/lmeval_ifeval_*.json"))
    if not ifeval:
        print("检查3 ifeval 指令级指标：UNMEASURED（没有 lmeval_ifeval_*.json）")
        return 2
    with_inst = 0
    for p in ifeval:
        for task in json.load(open(p, encoding="utf-8")).get("results", {}).values():
            if any(k.startswith("inst_level_strict_acc") for k in task):
                with_inst += 1
    print(f"检查3 ifeval 指令级指标：{len(ifeval)} 份产物中 {with_inst} 份含 inst_level_strict_acc")

    ok = not dis and not no_den
    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def negative_control(items, mres_paths):
    """把一份 testfrac 逐题文件里的一道通过题改成不通过，一致性检查必须报不一致。"""
    src = items[0]
    tmp = tempfile.mkdtemp(prefix="a14-negctl-")
    try:
        dst = os.path.join(tmp, os.path.basename(src))
        rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
        target = next((r for r in rows if r["binary_pass"] and r["n_pass"] > 0), None)
        if target is None:
            print("UNMEASURED  负控找不到可翻转的通过题（该格没有通过题），换一格再试")
            return 2
        target["n_pass"] -= 1
        target["frac"] = round(target["n_pass"] / target["n_tests"], 6)
        target["binary_pass"] = False
        with open(dst, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        _, compared, dis, _ = agreement([dst], mres_paths)
        print(f"负控：翻转 {os.path.basename(src)}::{target['name']} 后，"
              f"逐题比较 {compared} 道，报出不一致 {len(dis)} 项")
        if dis:
            print(f"  OK  检查看见了这次篡改：{dis[0]}")
            return 0
        print("  FAIL  篡改没有被检查看见 —— 一致性检查是假绿")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
