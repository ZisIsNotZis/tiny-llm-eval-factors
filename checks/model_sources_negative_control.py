#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：模型来源索引在场时，它才是来源列的唯一决定者；缺了、坏了、缺条目，构建必须变红。

四个用例，缺一个都不算证明过（全部就地注入，`finally` 里按原字节写回并按 sha256 复核）：

    baseline  未改动 → `checks/model_sources.py` exit 0，且它数出的条目数与文件一致
    tamper    改坏一条条目的 repo（合法 JSON）→ 检查非零退出并点名那个模型
    remove    删掉一条条目 → **真的** `python3 make_report.py` 非零退出并点名那个模型
    corrupt   索引整体写成非法 JSON → 真的构建非零退出并点名索引文件
    absent    索引文件不在场 → 真的构建非零退出并点名路径（「缺索引不许静默变未知」）

为什么 `remove` 这么快：`make_report.py` 在画第一张图之前先跑 `require_sources()`（正文表格是各节
表格的超集），缺条目在那里一次点名，所以失败发生在几秒内，不是三分钟。

顺手守一条不变量：这些失败都发生在写盘之前，`report.html` 的 sha256 全程不变——构建失败不许留下
半份报告。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SOURCES = os.path.join(REPO, "report_inputs", "model_sources.json")
REPORT = os.path.join(REPO, "report.html")
CHECK = os.path.join(HERE, "model_sources.py")
BACKUP = SOURCES + ".model-sources-nc.bak"

# 两个被拿来做文章的模型：一个删条目、一个改仓库名。都是报告附录里真有的行。
REMOVE_MODEL = "Qwen3.5-2B-UD-Q2_K_XL.gguf"
TAMPER_MODEL = "gemma-4-E2B-it-UD-Q2_K_XL.gguf"
TAMPER_REPO = "改坏的仓库名-GGUF"


def sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          env=dict(os.environ, A10_NO_GGUF="1"))
    return proc.returncode, proc.stdout + proc.stderr


def fail(message: str) -> int:
    print(f"FAIL {message}")
    return 1


def main() -> int:
    if not os.path.exists(SOURCES):
        return fail(f"模型来源索引不在场：{os.path.relpath(SOURCES, REPO)}")
    original = open(SOURCES, "rb").read()
    original_sha = sha256(SOURCES)
    report_sha = sha256(REPORT) if os.path.exists(REPORT) else None
    doc = json.loads(original)
    entries = doc["sources"]
    by_file = {e["file"]: e for e in entries}
    for name in (REMOVE_MODEL, TAMPER_MODEL):
        if name not in by_file:
            return fail(f"负控要动的模型 {name} 不在索引里——这个负控与索引脱钩了")

    def write(doc_obj) -> None:
        with open(SOURCES, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(doc_obj, ensure_ascii=False, indent=2) + "\n")

    # baseline：不改任何东西时必须绿，否则下面那次红说明不了任何事
    rc, out = run([sys.executable, CHECK])
    if rc != 0:
        return fail(f"baseline 未改动却 exit {rc}：\n{out}")
    if f"索引 {len(entries)} 条" not in out:
        return fail(f"baseline 数出的条目数与文件不一致（应为 {len(entries)}）：\n{out}")

    shutil.copyfile(SOURCES, BACKUP)
    try:
        # tamper：改坏一条条目的 repo，报告没重建 → 检查必须红并点名
        for ent in entries:
            if ent["file"] == TAMPER_MODEL:
                ent["repo"] = TAMPER_REPO
        write(doc)
        rc, out = run([sys.executable, CHECK])
        if rc == 0:
            return fail(f"把 {TAMPER_MODEL} 的仓库改成 {TAMPER_REPO} 后检查仍 exit 0 —— 来源列没有守卫")
        if TAMPER_MODEL not in out or TAMPER_REPO not in out:
            return fail(f"改坏仓库名后非零退出（{rc}）但没有点名该模型：\n{out}")
        print(f"tamper: 改坏 {TAMPER_MODEL} 的仓库 → 检查红并点名: True")
        write(json.loads(original))          # 复原内容，下面的用例从干净索引出发

        # remove：删掉一条条目 → 真的构建必须非零退出并点名
        doc2 = json.loads(original)
        doc2["sources"] = [e for e in doc2["sources"] if e["file"] != REMOVE_MODEL]
        write(doc2)
        rc, out = run([sys.executable, "make_report.py"])
        if rc == 0:
            return fail(f"删掉 {REMOVE_MODEL} 的条目后 make_report.py 仍 exit 0 —— 构建会静默退回「未知」")
        if REMOVE_MODEL not in out or "没有来源条目" not in out:
            return fail(f"缺条目时构建非零退出（{rc}）但没有点名该模型：\n{out}")
        print(f"remove: 删掉 {REMOVE_MODEL} 的条目 → make_report.py exit {rc} 并点名: True")

        # corrupt：索引整体写成非法 JSON → 构建必须失败并点名文件
        with open(SOURCES, "w", encoding="utf-8") as fh:
            fh.write("{ 这不是 JSON")
        rc, out = run([sys.executable, "make_report.py"])
        if rc == 0 or "model_sources.json" not in out:
            return fail(f"索引写成非法 JSON 后构建没有点名失败（rc={rc}）：\n{out}")
        print(f"corrupt: 索引写成非法 JSON → make_report.py exit {rc} 并点名 model_sources.json: True")

        # absent：索引不在场 → 构建必须失败并点名路径
        os.remove(SOURCES)
        rc, out = run([sys.executable, "make_report.py"])
        if rc == 0 or "模型来源索引缺失" not in out:
            return fail(f"索引不在场时构建没有失败并点名（rc={rc}）：\n{out}")
        print(f"absent: 索引不在场 → make_report.py exit {rc} 并点名路径: True")
    finally:
        with open(SOURCES, "wb") as fh:
            fh.write(original)
        if os.path.exists(BACKUP):
            os.remove(BACKUP)

    if not os.path.exists(SOURCES) or sha256(SOURCES) != original_sha:
        return fail("负控结束后 model_sources.json 没有按原字节写回")
    if report_sha is not None and (not os.path.exists(REPORT) or sha256(REPORT) != report_sha):
        return fail("负控里的失败构建动了 report.html —— 构建失败不许留下半份报告")
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "report_inputs", "report.html"],
                           cwd=REPO, capture_output=True, text=True, check=False)
    unexpected = [ln for ln in dirty.stdout.splitlines() if BACKUP.split("/")[-1] in ln]
    if unexpected:
        return fail(f"负控留下备份文件：\n{dirty.stdout}")
    print("PASS baseline 绿；改仓库名→检查红并点名；删条目/坏 JSON/缺索引→构建红并点名；原字节写回、report.html 未动")
    return 0


if __name__ == "__main__":
    sys.exit(main())
