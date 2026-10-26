#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""负控：证明 `checks/evidence_logs.py` 真的会红，而不是一个只会打印绿行的形状（p-entry3 的门 4）。

基线跑两处，两处的退出码**不同且都正确**：

  * 真树（`.wrapup` 在盘）exit 0；
  * 干净 clone（`.wrapup` 不在场）**exit 2**（不可得，不是通过）——判据只能按声明/索引，看不到盘上
    文件，所以脚本在结论行打出「本次 N 条只能按声明判」并以 2 退出。这一条是本包要修的正面证据：
    修前 clone 基线是 exit 1、预存失败 13 条。

注入面（用例 2 起）各跑在本仓库的临时 clone 上（结束即删，真树一个字节都不动），每例的判据是差分的：
注入之后多出来的失败行**恰好一条**，且点名被注入的那个路径。一行一条、末尾 `PASS` 才算过：

  0. baseline（真树）        exit 0，结论行是「无处置 0」；
  1. clone 基线              干净 clone 里 exit 2、失败 0 条、打出 BLOCKED 行；
  2. 字节数不符             把登记表里 `.wrapup/axes_diffusion_gate.log.gz` 换成解压后字节数不同的
                            副本 → 多一条失败行，点名该 `.log`（`.gz` 里装的必须是登记的那一份）；
  3. 从索引里拿掉           把已入库、被点名的 `.wrapup/mres/m164-a04-uni45/evalplus.json` 从索引
                            里拿掉（文件仍在盘上、`.gitignore` 里那行 `!` 放行仍在）→ 多一条失败行，
                            判「无处置」并点名该路径；
  4. 聚合产物未入库         同上，换成另一份聚合产物 `.wrapup/mres/m140-qat-gemma12b-q4/lmeval_panel.json`：
                            被点名、没入库、`!` 放行仍在 → 「无处置」。它与用例 3 共用同一条守卫：
                             未入库又没有声明规则 → 不是类。
  4b. 面板的形状表         精确点名盘上一份未入库的 `.wrapup/mres/m58-fake-panel/lmeval_panel.json`
                            （**不带 `!` 放行**，落在 `mres` catch-all）→ 多一条。这一例才真正问到
                            形状表里 `lmeval_(?!panel\.json$)` 那条排除；用例 4 的面板被 `!` 放行，
                            没有 ignore 规则可问，测不到形状表（删掉负向前瞻，用例 4 照样红）。
  5. 聚合产物落到未声明类   给一份精确点名的聚合产物 `.wrapup/mres/m164-a04-uni45/lmeval_panel.json`
                            加一条**未声明**的 ignore 规则 → 多一条失败行，判「无处置」并点名那条规则。
                            这是用例 4 的另一半：光「被忽略」不算处置，必须是被声明为可重建缓存的那一类。
  6. 逐题样本落到未声明类   给一份精确点名的逐题样本 `.wrapup/mres/m1-qwen4b-q2-py.jsonl`（它按
                            `.wrapup/mres/*` 的 `.jsonl` 形状算「按类忽略」）加一条**未声明**的
                            ignore 规则 → 多一条失败行，判「无处置」并点名那条规则。
  7. 逐题评测产物未入库     在一份 `RESULT.md` 里点名一个不在索引里、落在 `mres/` catch-all 下的
                            `*_eval.json` → 多一条失败行，判「无处置」。它测的是「被点名却没入库的
                            逐题评测产物 → 无处置」——`README` 的 Ships 一栏说逐题评测产物入库。
                            它**不**测形状表：`.gitignore` 的 `!.wrapup/mres/*/*_eval.json` 让该路径根本
                            不被 ignore（`git check-ignore` 不给规则），形状表从未被问到；把
                            `_eval\.json$` 加回形状表，这一例照样红。形状表那一面由用例 4b / 7b / 8 覆盖。
  7b. 模式里的聚合产物     在一份 `RESULT.md` 里写 `.wrapup/mres/m58-*/evalplus.json`，盘上放好一份
                            未入库的 `.wrapup/mres/m58-fake-run/evalplus.json` → 多一条并点名该文件。
                            这就是「同一个未入库文件，写成 exact 红、写成模式绿」的那个洞。
  8. 目录里的聚合产物      同上那份假运行目录，文档 token 写成 `.wrapup/mres/m58-fake-run/` → 走进目录，
                            看见里面只有未入库的 `evalplus.json` → 多一条并点名该文件。
  9. 空扫描                 临时 clone 里删掉所有 `RESULT.md` 正文里的 `.wrapup/…` token → 断言**只有
                            这条守卫会打的** `BLOCKED 空扫描：…` 行。只断言 exit 2 不够：末尾「盘上扫不到
                            未入库 run 文件」那条守卫也 exit 2（上一轮第 9 例就是因此不隔离任何守卫）。

**每一例都做过「删掉它守着的那段代码 → 该例必须变红」的反证**（临时 clone 里改
`checks/evidence_logs.py`，跑本控制，读逐例 `ok/FAIL`）。删哪几行 → 哪些例变红：

| 删掉的守卫（在 `checks/evidence_logs.py`） | 变红的例 |
|---|---|
| `main()` 里 `if _DISK_UNTRACKED == 0: … return 2` 整块 | 1 |
| `main()` 里 `if got != raw_bytes: failures.append(…)` | 2 |
| `main()` 里 `if not kind:` 改成 `if not kind and ignored_rule(token):`（无声明规则的未入库文件不再算无处置） | 3、4、7 |
| `class_label()` 里 `if rule not in rules: continue`（规则是否已声明不再问） | 4b、5、6、7b |
| `pattern_disposition()` 里文件候选的 `class_label(rep)` 改成 `declared_rule(rule)` | 7b |
| `class_label()` 里 `if not rule: return ""` | 无（与上一行的成员检查重合：空规则过不了成员检查，这行是冗余短路，不是洞） |
| `dir_disposition()` 里 `isdir` 分支在 `os.walk` 前直接 `return "dir", ""` | 8 |
| `main()` 里 `if not named:` 空扫描专用守卫整块 | 9（断言的行消失；末尾守卫仍给 exit 2，正说明旧断言无效） |
| （额外）per-run 形状里加入 `/evalplus\.json$` | 7b、8（证明这两例真的在问形状表） |
| （额外）删掉形状表 `lmeval_(?!panel\.json$)` 的负向前瞻 | 4b |

用例 0 是正基线，没有「守着它的代码」可删；上面任何一条改动都没有让它变红（它只判「真树 exit 0 且无失败行」）。


"聚合产物为什么必须入库"写在 `checks/evidence_logs.py` 的模块说明里：它们的断言无法从随仓库分发
的东西重算，所以 `mres/` 的 catch-all 只按**形状**认领逐题样本 / codegen / props / per-run 结果，
不认领这四类聚合产物。

clone 之后把**工作树**的 `.gitignore`、`docs/` 与本次新入库的证据文件叠上去——本控制判的是本次
改动，不是 HEAD（`refresh_guard_differential_control` 里记过同一条教训：跑 clone 自带的那份等于在测
上一个人的代码）。

    python3 checks/evidence_logs_negative_control.py
    python3 checks/evidence_logs_negative_control.py --keep   # 留着临时 clone 看现场
"""
from __future__ import annotations

import argparse
import gzip
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "checks" / "evidence_logs.py"

# 各用例的注入面：都是 p-entry3 的承重文件（登记过的 `.log`、被点名的聚合产物、按类忽略的逐题样本）
GZ_LOG = ".wrapup/axes_diffusion_gate.log.gz"
TRACKED_AGGREGATE = ".wrapup/mres/m164-a04-uni45/evalplus.json"
UNTRACKED_AGGREGATE = ".wrapup/mres/m140-qat-gemma12b-q4/lmeval_panel.json"
UNDECLARED_AGGREGATE = ".wrapup/mres/m164-a04-uni45/lmeval_panel.json"
CLASS_IGNORED = ".wrapup/mres/m1-qwen4b-q2-py.jsonl"
UNTRACKED_ITEM_EVAL = ".wrapup/mres/m63-qwen-2b-iq3xxs/code_eval.json"  # 不存在于索引、也不在盘上
NAMED_IN = "docs/subprojects/a01-量化位宽/RESULT.md"

# 假运行目录（用例 7b / 8）：盘上有一份未入库的聚合产物，文档 token 分别写成模式与目录
FAKE_DIR = ".wrapup/mres/m58-fake-run"
FAKE_FILE = FAKE_DIR + "/evalplus.json"

# 另一个假运行目录（用例 4b）：精确点名的未入库 lmeval_panel.json，不带 `!` 放行，故落在 mres catch-all
# 下——这一例才真正问到形状表里 `lmeval_(?!panel)…` 那条排除（用例 4 的 m140 面板被 `!` 放行，
# 没有 ignore 规则可问，测不到形状表）。
FAKE_PANEL_DIR = ".wrapup/mres/m58-fake-panel"
FAKE_PANEL = FAKE_PANEL_DIR + "/lmeval_panel.json"

# 本次新入库的证据文件：clone 是 HEAD，工作树里还没提交时它们不在 clone 里，要叠上去
NEW_EVIDENCE = (
    ".wrapup/mres/i01-shim-probe/probe-output.txt",
    ".wrapup/mres/i01-slot-np1-meta.json",
    ".wrapup/mres/m63-qwen-2b-iq3xxs/evalplus.json",
    ".wrapup/mres/m64-qwen-2b-q2kxl/evalplus.json",
    ".wrapup/mres/m115-phi4mini-q2k/evalplus.json",
    ".wrapup/mres/m140-qat-gemma12b-q4/lmeval_panel.json",
    ".wrapup/mres/m144-qat-gemma26b-a4b-q4/evalplus.json",
    ".wrapup/mres/m144-qat-gemma26b-a4b-q4/lmeval_panel.json",
    ".wrapup/mres/m164-a04-uni45/evalplus.json",
    ".wrapup/mres/m164-a04-uni45/lmeval_panel.json",
    ".wrapup/mres/m169-vram-08b-mtp/ident_control.json",
    ".wrapup/mres/m169-vram-9b/ident_control.json",
    # 第二轮复核补入库的 19 份聚合产物
    ".wrapup/mres/m61-qwen-2b-iq2xxs/evalplus.json",
    ".wrapup/mres/m62-qwen-2b-iq2m/evalplus.json",
    ".wrapup/mres/m65-qwen-2b-q3kxl/evalplus.json",
    ".wrapup/mres/m66-qwen-2b-q4kxl/evalplus.json",
    ".wrapup/mres/m67-qwen-2b-q5kxl/evalplus.json",
    ".wrapup/mres/m91-qwen38-27b-q2kxl/cmd.txt",
    ".wrapup/mres/m91-qwen38-27b-q2kxl/evalplus.json",
    ".wrapup/mres/m100-qwen38-27b-q3kxl/cmd.txt",
    ".wrapup/mres/m100-qwen38-27b-q3kxl/evalplus.json",
    ".wrapup/mres/m150-qwen38-gsqrco-iq3xxs/cmd.txt",
    ".wrapup/mres/m150-qwen38-gsqrco-iq3xxs/evalplus.json",
    ".wrapup/mres/m151-qwen38-gsqrco-iq3s/cmd.txt",
    ".wrapup/mres/m151-qwen38-gsqrco-iq3s/evalplus.json",
    ".wrapup/mres/m152-qwen38-27b-iq4xs/cmd.txt",
    ".wrapup/mres/m152-qwen38-27b-iq4xs/evalplus.json",
    ".wrapup/mres/m101-qwen36-35b-a3b-q3km/cmd.txt",
    ".wrapup/mres/m101-qwen36-35b-a3b-q3km/evalplus.json",
    ".wrapup/mres/m103-qwen36-35b-a3b-q3kxl/cmd.txt",
    ".wrapup/mres/m103-qwen36-35b-a3b-q3kxl/evalplus.json",
)


def sh(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=str(cwd or REPO), capture_output=True, text=True)


def prepare(tmp: Path) -> Path:
    """HEAD 的 clone + 工作树叠加层（`.gitignore`、`docs/`、本次新入库的证据文件）。"""
    clone = tmp / "clone"
    proc = sh("git", "clone", "--shared", "--quiet", str(REPO), str(clone))
    if proc.returncode != 0:
        raise SystemExit(f"FAIL 无法建立临时 clone：{proc.stderr.strip()}")
    shutil.copyfile(REPO / ".gitignore", clone / ".gitignore")
    shutil.copytree(REPO / "docs", clone / "docs", dirs_exist_ok=True)
    shutil.copytree(clone / "docs", tmp / "docs_pristine")
    for rel in NEW_EVIDENCE:
        src = REPO / rel
        if not src.exists():
            raise SystemExit(f"FAIL 工作树里没有 {rel}——证据文件不在了，本控制无从谈起")
        dst = clone / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if sh("git", "add", "--", rel, cwd=clone).returncode != 0:
            raise SystemExit(f"FAIL 临时 clone 里放不进 {rel}")
    return clone


def run_check(root: Path) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(CHECKER), "--root", str(root)],
                          cwd=str(root), capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def summary_line(out: str) -> str:
    return out.splitlines()[0] if out.splitlines() else ""


def failures(out: str) -> set[str]:
    return {line for line in out.splitlines() if line.startswith("FAIL")}


def check(name: str, ok: bool, detail: str) -> bool:
    print(f"{'ok  ' if ok else 'FAIL'}  {name}：{detail}")
    return ok


def write_fake_dir(clone: Path) -> None:
    dst = clone / FAKE_FILE
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("{}\n", encoding="utf-8")  # 未入库：不 add


def write_fake_panel(clone: Path) -> None:
    dst = clone / FAKE_PANEL
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("{}\n", encoding="utf-8")  # 未入库：不 add


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", action="store_true", help="留着临时 clone（默认结束即删）")
    args = ap.parse_args()

    before = sh("git", "status", "--porcelain").stdout
    all_ok = True

    # 0) baseline：本次工作树未改动时必须无失败行。本机（有未入库 run 文件）exit 0；
    #    在干净 clone 里跑本控制时，当前工作树也没有未入库文件 → exit 2（不可得），同样算无失败。
    rc, out = run_check(REPO)
    all_ok &= check("0 baseline（本次工作树）", rc in (0, 2) and not failures(out) and "无处置 0" in out,
                    f"exit {rc}；{summary_line(out)}")

    tmp = Path(tempfile.mkdtemp(prefix="evidence-logs-nc."))
    try:
        clone = prepare(tmp)
        pristine_index = (clone / ".git" / "index").read_bytes()

        def fresh() -> None:
            """每个用例前把索引、`.gitignore`、`docs/`、登记的 `.gz` 与假运行目录复原，让每次红的差分只有一条。"""
            (clone / ".git" / "index").write_bytes(pristine_index)
            shutil.copyfile(REPO / ".gitignore", clone / ".gitignore")
            shutil.rmtree(clone / "docs", ignore_errors=True)
            shutil.copytree(tmp / "docs_pristine", clone / "docs")
            shutil.copyfile(REPO / GZ_LOG, clone / GZ_LOG)
            shutil.rmtree(clone / FAKE_DIR, ignore_errors=True)
            shutil.rmtree(clone / FAKE_PANEL_DIR, ignore_errors=True)

        # 1) clone 基线：干净 clone 里没有 `.wrapup` → exit 2（不可得），失败 0 条
        fresh()
        rc0, out0 = run_check(clone)
        base = failures(out0)
        blocked = [l for l in out0.splitlines() if l.startswith("BLOCKED:")]
        all_ok &= check("1 clone 基线（不可得）", rc0 == 2 and not base and bool(blocked),
                        f"exit {rc0}；预存失败行 {len(base)} 条；{summary_line(out0)}；"
                        f"{blocked[0] if blocked else '（没有 BLOCKED 行）'}")

        def each(name: str, want: str, describe: str, mutate) -> None:
            """复原 → 注入 → 跑检查：注入后多出来的失败行必须恰好一条，且点名 want。"""
            nonlocal all_ok
            fresh()
            mutate()
            rc1, out1 = run_check(clone)
            delta = failures(out1) - base
            hit = [l for l in delta if want in l]
            ok = rc1 == 1 and len(delta) == 1 and len(hit) == 1
            all_ok &= check(name, ok, f"exit {rc1}；多出来的失败行 {len(delta)} 条"
                                      f"；{describe}：{hit[0] if hit else '（没有）'}")

        # 2) 登记的 `.gz` 换成解压字节数不同的副本
        def swap_gz() -> None:
            gz_path = clone / GZ_LOG
            gz_path.write_bytes(gzip.compress(b"negative-control: not the registered bytes\n"))

        each("2 字节数不符", GZ_LOG[: -len(".gz")], "点名该 .log", swap_gz)

        # 3) 已入库的被点名路径从索引里拿掉（文件仍在盘上、`!` 放行仍在）
        def untrack() -> None:
            sh("git", "rm", "--cached", "--quiet", "--", TRACKED_AGGREGATE, cwd=clone)

        each("3 从索引里拿掉", TRACKED_AGGREGATE, "判「无处置」", untrack)

        # 4) 另一份聚合产物从索引里拿掉：exact 档的严格度不许被本包换掉
        def untrack_aggregate() -> None:
            sh("git", "rm", "--cached", "--quiet", "--", UNTRACKED_AGGREGATE, cwd=clone)

        each("4 聚合产物未入库", UNTRACKED_AGGREGATE, "判「无处置」", untrack_aggregate)

        # 4b) 精确点名的未入库 lmeval_panel.json（盘上、落在 mres catch-all、没有 `!` 放行）→ 形状表必须
        #     把面板排除掉；删掉形状表里 `(?!panel\.json$)` 这条排除，本例就变绿。
        def name_fake_panel() -> None:
            write_fake_panel(clone)
            with open(clone / NAMED_IN, "a", encoding="utf-8") as fh:
                fh.write(f"\n- negative control：`{FAKE_PANEL}`\n")

        each("4b 精确点名的 lmeval_panel.json", FAKE_PANEL, "判「无处置」并点名该文件", name_fake_panel)

        # 5) 聚合产物落在一条**未声明**的 ignore 规则下（拿掉索引，否则 tracked 文件不被 check-ignore 问）
        def undeclared_aggregate_rule() -> None:
            sh("git", "rm", "--cached", "--quiet", "--", UNDECLARED_AGGREGATE, cwd=clone)
            with open(clone / ".gitignore", "a", encoding="utf-8") as fh:
                fh.write(f"\n# negative control: 未声明的类（不在 REBUILDABLE_CLASSES 里）\n"
                         f"{UNDECLARED_AGGREGATE}\n")

        each("5 聚合产物落到未声明类", f"`{UNDECLARED_AGGREGATE}`", "判「无处置」并点名那条规则",
             undeclared_aggregate_rule)

        # 6) 精确点名的逐题样本落在一条**未声明**的 ignore 规则下（既有用例）
        def undeclared_rule() -> None:
            with open(clone / ".gitignore", "a", encoding="utf-8") as fh:
                fh.write(f"\n# negative control: 未声明的类（不在 REBUILDABLE_CLASSES 里）\n{CLASS_IGNORED}\n")

        each("6 逐题样本落到未声明类", f"`{CLASS_IGNORED}`", "判「无处置」并点名那条规则", undeclared_rule)

        # 7) 被点名却没入库的 `*_eval.json`（测「无处置」；形状表那一面由 7b/8 覆盖）
        def name_untracked_item_eval() -> None:
            with open(clone / NAMED_IN, "a", encoding="utf-8") as fh:
                fh.write(f"\n- negative control：`{UNTRACKED_ITEM_EVAL}`\n")

        each("7 逐题评测产物未入库", UNTRACKED_ITEM_EVAL, "判「无处置」", name_untracked_item_eval)

        # 7b) 模式点名的聚合产物：盘上有假运行目录里的未入库 evalplus.json
        def name_fake_pattern() -> None:
            write_fake_dir(clone)
            with open(clone / NAMED_IN, "a", encoding="utf-8") as fh:
                fh.write(f"\n- negative control：`.wrapup/mres/m58-*/evalplus.json`\n")

        each("7b 模式里的聚合产物", FAKE_FILE, "判「无处置」并点名该文件", name_fake_pattern)

        # 8) 目录点名的聚合产物：走进假运行目录，看见里面只有未入库的 evalplus.json
        def name_fake_dir() -> None:
            write_fake_dir(clone)
            with open(clone / NAMED_IN, "a", encoding="utf-8") as fh:
                fh.write(f"\n- negative control：`{FAKE_DIR}/`\n")

        each("8 目录里的聚合产物", FAKE_FILE, "判「无处置」并点名该文件", name_fake_dir)

        # 9) 空扫描：删掉所有 RESULT.md 正文里的 `.wrapup/…` token → 只有空扫描守卫会打的
        #    `BLOCKED 空扫描` 那行必须出现（末尾那条 BLOCKED 也给 exit 2，所以不能只断言退出码）。
        fresh()
        for doc in (clone / "docs" / "subprojects").glob("*/RESULT.md"):
            text = doc.read_text(encoding="utf-8")
            doc.write_text(re.sub(r"\.wrapup/[^\s`）)]*", "", text), encoding="utf-8")
        rc9, out9 = run_check(clone)
        scan_line = [l for l in out9.splitlines() if l.startswith("BLOCKED 空扫描：")]
        all_ok &= check("9 空扫描", rc9 == 2 and len(scan_line) == 1,
                        f"exit {rc9}；只有空扫描守卫才会打的行：{scan_line[0] if scan_line else '（没有）'}")
    finally:
        if args.keep:
            print(f"--keep：临时 clone 留在 {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    after = sh("git", "status", "--porcelain").stdout
    all_ok &= check("真树未被本控制改动", after == before,
                    "git status --porcelain 前后相同" if after == before
                    else f"前后不同：\n{after[:300]}")
    if not all_ok:
        print("FAIL 有期望没有成立（缺一条都不算证明过这条检查会红）")
        return 1
    print("PASS 真树绿、干净 clone 报 BLOCKED（不可得）；换字节→点名 `.log`；聚合产物未入库/落未声明类"
          "→无处置；精确点名的未入库 lmeval_panel.json→过形状表判无处置；逐题样本落未声明类→无处置；"
          "逐题评测产物未入库→无处置；模式/目录点名的未入库 evalplus.json→无处置并点名；"
          "空扫描→只有该守卫会打的行；真树前后相同")
    return 0


if __name__ == "__main__":
    sys.exit(main())
