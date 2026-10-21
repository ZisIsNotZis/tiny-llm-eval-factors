#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""差分负控：证明「读不到输入就不删」这条 guard **在承重**，不是恰好通过。

做法是在一份**干净 clone** 里跑两次完整 refresh——那里的 `.wrapup/mres` 没有随仓库分发的面板
（只有 `*_eval.json` 与几个来源清单），正是历史上丢行的环境：

  A. 带 guard（默认）：campaign / spec / variant 都读不到面板 → 保留现状、`migrate_db.py` exit 2；
     `mres/%` 行**一行不丢**。
  B. 去掉 guard（`MIGRATE_WIDE_DELETE=1` 把删除范围换回旧写法 `source_file LIKE 'mres/%'`）：
     同一轮里那些读不回来的行被删掉、只有能重建的少数行回来 → 净丢几百行。

两次的行数差就是这条 guard 的价值。判据三条：
  1. A 的 `mres/%` 行数前后相等（丢 0 行）；
  2. B 丢掉的 `mres/%` 行数 > 0（否则这条 guard 是装饰，负控不成立）；
  3. A 与 B 的差 > 0 且方向正确（guard 让损失从正数变成 0）。
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def mres_rows(db: Path) -> int:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(
            "SELECT count(*) FROM experiments WHERE source_file LIKE 'mres/%'").fetchone()[0]
    finally:
        con.close()


def total_rows(db: Path) -> int:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute("SELECT count(*) FROM experiments").fetchone()[0]
    finally:
        con.close()


def run_migrate(workdir: Path, wide_delete: bool):
    """跑**工作树里**那份 `migrate_db.py`，输入与库用 clone 的（cwd=clone）。

    不能跑 clone 里的那份：clone 是 HEAD，`MIGRATE_WIDE_DELETE` 这个差分用的开关就在工作树里
    还没提交——跑 clone 的那份等于两次都跑「带 guard 的新代码」，差分自然为 0（本控制第一版
    就踩了这个坑，B 腿一行没丢）。
    """
    env = dict(os.environ)
    env.pop("MIGRATE_WIDE_DELETE", None)
    if wide_delete:
        env["MIGRATE_WIDE_DELETE"] = "1"
    r = subprocess.run([sys.executable, str(REPO / "migrate_db.py")], cwd=str(workdir), env=env,
                       capture_output=True, text=True)
    if r.returncode not in (0, 2):
        print(f"FAIL: migrate_db.py 退出 {r.returncode}：{(r.stdout + r.stderr)[-500:]}")
        sys.exit(1)
    return r


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="refresh-guard-diff-"))
    clone = tmp / "clone"
    try:
        r = subprocess.run(["git", "clone", "--quiet", str(REPO), str(clone)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"FAIL: 建不出干净 clone：{r.stderr.strip()[:300]}")
            return 1
        db = clone / "experiments.sqlite"
        head = subprocess.run(["git", "-C", str(clone), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        before = mres_rows(db)
        before_total = total_rows(db)
        panels = sum(len(list((clone / ".wrapup" / "mres").glob(p)))
                     for p in ("*/lmeval_panel.json", "*/evalplus.json",
                               "*-spec-*/spec_panel.json", "*/variant_panel.json"))

        # A. 带 guard
        ra = run_migrate(clone, wide_delete=False)
        after_a, after_a_total = mres_rows(db), total_rows(db)
        loss_a = before - after_a

        # 复原 DB，再跑 B（去掉 guard）
        subprocess.run(["git", "-C", str(clone), "checkout", "--", "experiments.sqlite"],
                       capture_output=True, text=True)
        if mres_rows(db) != before:
            print("FAIL: 复原后 mres 行数与跑前不一致，B 腿不可比")
            return 1
        rb = run_migrate(clone, wide_delete=True)
        after_b = mres_rows(db)
        loss_b = before - after_b

        print(f"0) 环境                : clone {head}，.wrapup/mres 下面板文件 {panels} 个；"
              f"跑前 mres/% 行 {before}（全库 {before_total}）")
        print(f"1) 带 guard（默认）    : exit {ra.returncode}；mres/% 行 {before} → {after_a}"
              f"（丢 {loss_a}，要 0）；全库 {before_total} → {after_a_total}")
        print(f"2) 去掉 guard（旧写法）: exit {rb.returncode}；mres/% 行 {before} → {after_b}"
              f"（丢 {loss_b}，要 >0）")

        problems = []
        if loss_a != 0:
            problems.append(f"带 guard 还丢了 {loss_a} 行——guard 不生效")
        if loss_b <= 0:
            problems.append("去掉 guard 一行没丢——这条 guard 不是在承重（或 clone 里本来就没有可丢的行）")
        if not (loss_b > loss_a):
            problems.append(f"方向不对：guard 前丢 {loss_b}、guard 后丢 {loss_a}")
        if problems:
            print("FAIL:")
            for p in problems:
                print("  -", p)
            return 1
        print(f"3) 差分                : guard 把丢失从 {loss_b} 行变成 {loss_a} 行")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
