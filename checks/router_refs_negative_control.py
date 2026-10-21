#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：证明 `checks/router_refs.py` 真的会红，而不是一个只会打印 PASS 的形状。

六个必须成立的期望，各跑一棵临时树（`tempfile.mkdtemp`，结束即删；仓库一个字节都不动）：

  1. 未改动的合成树                     → exit 0（基线，排除「临时目录本身有问题」这个解释）；
  2. 引用一个不存在的路径               → exit 1 且点名 missing-file；
  3. 引用的文件存在、id 不在里面        → exit 1 且点名 missing-id；
  4. 路由是空的（degenerate）           → exit 1 且说明扫描为空（空扫描不是通过）。

外加两条验证新的 token 边界（反引号 span 是 token，空格算在内）：

  5. 反引号里引一个带空格的路径且 id 在  → exit 0（分母里真的算上了它，自检行两边相等）；
  6. 同上但 id 不在里面                  → exit 1 且点名 missing-id，**不是** missing-file。

外加一条边界代价的负控：同一条带空格引用写成**裸文本**（不加反引号）→ 按空白截断后是一条
一条可见的 `missing-file` 红行（截断的本义就印在输出里），而不是静默消失。

外加：删掉一个路由文件 → exit 2 且打出 `BLOCKED:`（缺失是外部阻断，不是通过也不是失败）。

合成树里 STATUS.md / FINDINGS.md / README.md 三种输入都用到，因为主脚本要求它至少扫到一条
STATUS 引用、一条 FINDINGS 引用、一个路径 token——否则它自己就会判「看不见输入」。

    python3 checks/router_refs_negative_control.py
    python3 checks/router_refs_negative_control.py --keep   # 留着临时树看现场
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "checks" / "router_refs.py"

STATUS = """# STATUS

当前状态在 `docs/plan/plan.yaml::plan1`，结论在 `docs/subprojects/7-demo/RESULT.md::res9`。
事实落在哪：`docs/plan/plan.yaml`、`docs/product/`。
"""

FINDINGS = """# FINDINGS

| 结论 | 事实所在 | 状态 |
| --- | --- | --- |
| 演示结论 | `docs/subprojects/7-demo/RESULT.md::res9` | 成立 |
"""

README = """# README

- `docs/plan/plan.yaml` owns the plan layer.
"""

PLAN_YAML = """plan1:
  status: current
  _text: 一条顶层键事实。
plan2:
  status: current
"""

RESULT_MD = """# 7 演示 —— 结果

## res9 :: 演示节点，标题的第一个 token 就是 id。

- status: current

### res10 :: 更深一级的标题也算。

## 一节说明文字（没有 id）
"""

PRODUCT_YAML = """product1:
  status: current
"""

# 目录名带空格：本仓库真的这么叫（a04-MoE 各层比特分配 / a09-量化感知训练 QAT ...）。
SPACED_MD = """# a-long name —— 结果

## res1 :: 空格目录里的节点，标题第一个 token 就是 id。

- status: current
"""

# 每次期望都从这份「未改动」内容起步，所以失败只可能来自这一处注入。
BASE = {
    "STATUS.md": STATUS,
    "FINDINGS.md": FINDINGS,
    "README.md": README,
    "docs/plan/plan.yaml": PLAN_YAML,
    "docs/product/product.yaml": PRODUCT_YAML,
    "docs/subprojects/7-demo/RESULT.md": RESULT_MD,
    "docs/subprojects/a-long name/RESULT.md": SPACED_MD,
}

SPACED_ROW = "| 空格目录引用 | `docs/subprojects/a-long name/RESULT.md::res1` | 成立 |\n"
SPACED_ROW_BAD_ID = "| 空格目录引用 | `docs/subprojects/a-long name/RESULT.md::res404` | 成立 |\n"
SPACED_ROW_BARE = "| 空格目录引用 | docs/subprojects/a-long name/RESULT.md::res1 | 成立 |\n"


def build(root, drop=()):
    """把 BASE 写进 root（先清空），drop 里的路径不写。"""
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    for rel, text in BASE.items():
        if rel in drop:
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def run(root):
    r = subprocess.run([sys.executable, str(CHECKER), "--root", str(root)],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main(argv):
    ap = argparse.ArgumentParser(add_help=True, description=__doc__)
    ap.add_argument("--keep", action="store_true", help="保留临时树（调试用）")
    args = ap.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix="router-refs-negative-control-"))
    if tmp.resolve() == REPO.resolve():
        print("FAIL: 临时树就是仓库本身，负控会改坏仓库")
        return 1
    failures = 0

    def expect(label, ok, detail=""):
        nonlocal failures
        print(f"{label:<58}: {'ok' if ok else 'FAIL'}{('  ' + detail) if detail and not ok else ''}")
        if not ok:
            failures += 1

    try:
        # 1) 基线：未改动的合成树必须通过
        build(tmp)
        rc, out = run(tmp)
        expect("baseline (unmodified synthetic tree) exit 0",
               rc == 0 and "citations resolved" in out, f"exit {rc}\n{out}")

        # 2) 路径不存在 → missing-file
        build(tmp)
        (tmp / "FINDINGS.md").write_text(
            FINDINGS.replace("docs/subprojects/7-demo/RESULT.md::res9",
                             "docs/subprojects/7-demo/GONE.md::res9"), encoding="utf-8")
        rc, out = run(tmp)
        expect("citation to a path that does not exist -> 1 + missing-file",
               rc == 1 and "missing-file" in out and "GONE.md" in out, f"exit {rc}\n{out}")

        # 3) 文件在、id 不在里面 → missing-id
        build(tmp)
        (tmp / "FINDINGS.md").write_text(
            FINDINGS.replace("RESULT.md::res9", "RESULT.md::res404"), encoding="utf-8")
        rc, out = run(tmp)
        expect("existing file, id not in it -> 1 + missing-id",
               rc == 1 and "missing-id" in out and "res404" in out
               and "missing-file" not in out, f"exit {rc}\n{out}")

        # 3b) 反方向：id 在标题里、标题在文件里，但引用搬到 .yaml 那种形状上也要判得动
        build(tmp)
        (tmp / "STATUS.md").write_text(
            STATUS.replace("docs/plan/plan.yaml::plan1", "docs/plan/plan.yaml::res9"),
            encoding="utf-8")
        rc, out = run(tmp)
        expect("yaml citation to an id that only a .md heading has -> 1",
               rc == 1 and "missing-id" in out, f"exit {rc}\n{out}")

        # 3c) 反引号里的带空格路径：文件在、id 在 → 必须进分母且解析成功（exit 0）
        build(tmp)
        (tmp / "FINDINGS.md").write_text(FINDINGS + SPACED_ROW, encoding="utf-8")
        rc, out = run(tmp)
        expect("backticked spaced path, file+id exist -> 0",
               rc == 0 and "citation tokens seen:" in out and "missing" not in out
               and "citations resolved" in out, f"exit {rc}\n{out}")

        # 3d) 同一条引用，文件在、id 不在 → missing-id（不是 missing-file：路径没被截断）
        build(tmp)
        (tmp / "FINDINGS.md").write_text(FINDINGS + SPACED_ROW_BAD_ID, encoding="utf-8")
        rc, out = run(tmp)
        expect("backticked spaced path, id absent -> 1 + missing-id",
               rc == 1 and "missing-id" in out and "res404" in out
               and "a-long name/RESULT.md::res404" in out
               and "missing-file" not in out, f"exit {rc}\n{out}")

        # 3e) 不做边界判定的代价写成可见的一条：裸文本的带空格路径按空白截断 → missing-file 红行，
        #     截断后的 token 原样印出，读的人看见的是「边界或路径错了」，不是静默吞掉。
        build(tmp)
        (tmp / "FINDINGS.md").write_text(FINDINGS + SPACED_ROW_BARE, encoding="utf-8")
        rc, out = run(tmp)
        expect("bare (not backticked) spaced path -> 1 + visible missing-file",
               rc == 1 and "docs/subprojects/a-long  missing-file" in out
               and "a-long name" not in out.split("citation tokens seen:")[0],
               f"exit {rc}\n{out}")

        # 4) 空扫描不是通过：两个路由一条引用都没有（只剩 README 的一个路径 token）
        build(tmp)
        (tmp / "STATUS.md").write_text("# STATUS\n\n没有引用的路由。\n", encoding="utf-8")
        (tmp / "FINDINGS.md").write_text("# FINDINGS\n\n（本文件暂无内容）\n", encoding="utf-8")
        rc, out = run(tmp)
        expect("degenerate routers (no citations) -> 1 + VACUOUS",
               rc == 1 and "VACUOUS" in out and "0/0 citations resolved" in out
               and "STATUS.md" in out and "FINDINGS.md" in out,
               f"exit {rc}\n{out}")

        # 5) 路由文件缺失是阻断，不是通过也不是失败
        build(tmp, drop=("STATUS.md",))
        rc, out = run(tmp)
        expect("missing router file -> 2 + BLOCKED:",
               rc == 2 and "BLOCKED:" in out, f"exit {rc}\n{out}")
    finally:
        if args.keep:
            print(f"temp tree kept at {tmp}")
        else:
            for path in sorted(tmp.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            tmp.rmdir()

    if failures:
        print(f"FAIL: {failures} expectation(s) did not hold — 负控不成立，检查无法被证明会红")
        return 1
    print("PASS: router_refs.py 在未改动的树上绿，在六种故意破坏的树上红，"
          "反引号里的带空格引用进分母且按 missing-id 判，裸文本的带空格路径报成可见的 missing-file，"
          "缺路由文件时阻断；仓库未被改动")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
