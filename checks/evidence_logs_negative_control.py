#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：证明 `checks/evidence_logs.py` 真的会红，而不是一个只会打印绿行的形状（p-entry3 的门 4）。

基线在**真树**上跑（exit 0）；三个注入面各跑在**本仓库的临时 clone** 上（`git clone --shared`，
结束即删，真树一个字节都不动），每例的判据是差分的：注入之后多出来的失败行**恰好一条**，且点名
被注入的那个路径。一行一条、末尾 `PASS` 才算过：

  0. baseline（真树）        exit 0，结论行是「无处置 0」（否则下面的红说明不了任何事）；
  1. 字节数不符             把登记表里 `.wrapup/axes_diffusion_gate.log.gz` 换成解压后字节数不同的
                            副本 → 多一条失败行，点名该 `.log`（`.gz` 里装的必须是登记的那一份）；
  2. 从索引里拿掉           把已入库、被点名的 `.wrapup/mres/m63-qwen-2b-iq3xxs/evalplus.json` 从索引
                            里拿掉（文件仍在盘上、`.gitignore` 里那行 `!` 放行仍在）→ 多一条失败行，
                            判「无处置」并点名该路径。旧版检查在这里是绿的：`glob(path+"*")` 把它
                            匹配成它自己，于是「被 ignore」冒充「有处置」；
  3. 未声明类               给一条精确点名的路径（`.wrapup/mres/m1-qwen4b-q2-py.jsonl`，clone 基线里
                            它按 `.wrapup/mres/*` 的 `.jsonl` 形状算「按类忽略」）加一条**未声明**的
                            ignore 规则 → 多一条失败行，判「无处置」并点名那条规则。这是用例 2 的
                            另一半：光「被忽略」不算处置，必须是被声明为可重建缓存的那一类。

clone 为什么不能当基线：`dir` 与 `glob` 两档要读盘上真实存在的目录与展开结果，而 clone 里只有
跟踪文件（818 个 `.wrapup/mres/` 运行目录、`.gz` 之外的落盘产物都不在），所以 clone 上本来就有一批
「无处置」。因此 clone 只当**差分**用：预先记下它的失败行集合，再要求注入后恰好只多一条。
clone 之后把**工作树**的 `.gitignore`、`docs/` 与本次新入库的证据文件叠上去——本控制判的是本次
改动，不是 HEAD（`refresh_guard_differential_control` 里记过同一条教训：跑 clone 自带的那份等于在测
上一个人的代码）。

    python3 checks/evidence_logs_negative_control.py
    python3 checks/evidence_logs_negative_control.py --keep   # 留着临时 clone 看现场
"""
from __future__ import annotations

import argparse
import gzip
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "checks" / "evidence_logs.py"

# 用例 1/2/3 的注入面：都是 p-entry3 的承重文件（登记过的 `.log`、被点名的聚合产物、按类忽略的逐题样本）
GZ_LOG = ".wrapup/axes_diffusion_gate.log.gz"
TRACKED_AGGREGATE = ".wrapup/mres/m63-qwen-2b-iq3xxs/evalplus.json"
CLASS_IGNORED = ".wrapup/mres/m1-qwen4b-q2-py.jsonl"

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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", action="store_true", help="留着临时 clone（默认结束即删）")
    args = ap.parse_args()

    before = sh("git", "status", "--porcelain").stdout
    all_ok = True

    # 0) baseline：真树未改动时必须绿
    rc, out = run_check(REPO)
    all_ok &= check("0 baseline（真树）", rc == 0 and "无处置 0" in out,
                    f"exit {rc}；{summary_line(out)}")

    tmp = Path(tempfile.mkdtemp(prefix="evidence-logs-nc."))
    try:
        clone = prepare(tmp)
        pristine_index = (clone / ".git" / "index").read_bytes()

        def fresh() -> None:
            """每个用例前把索引、`.gitignore` 与登记的 `.gz` 复原，让每次红的差分只有一条。"""
            (clone / ".git" / "index").write_bytes(pristine_index)
            shutil.copyfile(REPO / ".gitignore", clone / ".gitignore")
            shutil.copyfile(REPO / GZ_LOG, clone / GZ_LOG)

        # clone 基线：只记失败行集合，不当绿基线（理由见模块说明）
        fresh()
        rc0, out0 = run_check(clone)
        base = failures(out0)
        all_ok &= check("  clone 基线", rc0 in (0, 1), f"exit {rc0}；预存失败行 {len(base)} 条")

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

        # 1) 登记的 `.gz` 换成解压字节数不同的副本
        def swap_gz() -> None:
            gz_path = clone / GZ_LOG
            gz_path.write_bytes(gzip.compress(b"negative-control: not the registered bytes\n"))

        each("1 字节数不符", GZ_LOG[: -len(".gz")], "点名该 .log", swap_gz)

        # 2) 已入库的被点名路径从索引里拿掉（文件仍在盘上、`!` 放行仍在）
        def untrack() -> None:
            sh("git", "rm", "--cached", "--quiet", "--", TRACKED_AGGREGATE, cwd=clone)

        each("2 从索引里拿掉", TRACKED_AGGREGATE, "判「无处置」", untrack)

        # 3) 精确点名的路径落在一条**未声明**的 ignore 规则下
        def undeclared_rule() -> None:
            with open(clone / ".gitignore", "a", encoding="utf-8") as fh:
                fh.write(f"\n# negative control: 未声明的类（不在 REBUILDABLE_CLASSES 里）\n{CLASS_IGNORED}\n")

        each("3 未声明的类", f"`{CLASS_IGNORED}`", "判「无处置」并点名那条规则", undeclared_rule)
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
    print("PASS 换字节→多一条并点名 `.log`；从索引拿掉→无处置；未声明类→无处置；真树前后相同")
    return 0


if __name__ == "__main__":
    sys.exit(main())
