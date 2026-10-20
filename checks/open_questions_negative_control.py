#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：`build_open_questions.py` 不会把不该算的标题当成「未解问题」一节。

复核发现过两种误判：`## wp98 :: 未解决的 top_k 处置`（工作包标题里带了关键词）与代码围栏
里的 `# 未解问题`。这个负控用一份故意写成那样的 `PLAN.md` 证明它们都被跳过、只取真正的
二级标题，并且在真实仓库上跑同样规则时条目数与索引一致。

    python3 checks/open_questions_negative_control.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "report_inputs"))
import build_open_questions as boq  # noqa: E402

FAKE = textwrap.dedent('''\
    # 研究计划

    ## wp98 :: 未解决的 top_k 处置

    - 这条属于工作包标题，不是「未解问题」一节。

    ## 已记录

    ```
    # 未解问题
    - 围栏里的这一行不是一节
    ```

    ## 未解问题

    - 真正的第一条未解问题。
    - 真正的第二条未解问题。
    ''')


def main():
    tmp = tempfile.mkdtemp(prefix="open-questions-negative-control-")
    try:
        sub = Path(tmp) / "subprojects" / "zz-fake"
        sub.mkdir(parents=True)
        (sub / "PLAN.md").write_text(FAKE, encoding="utf-8")
        saved = boq.SOURCE_GLOB
        boq.SOURCE_GLOB = os.path.join(tmp, "subprojects", "*", "PLAN.md")
        try:
            sections, skipped = boq.scan()
        finally:
            boq.SOURCE_GLOB = saved
        got = [(s[1], s[2], s[3]) for s in sections]
        print(f"fixture sections: {got}")
        if len(sections) != 1 or sections[0][2] != "未解问题":
            print("FAIL: 工作包标题或被围栏的行被当成了「未解问题」一节")
            return 1
        if sections[0][3] != ["真正的第一条未解问题。", "真正的第二条未解问题。"]:
            print(f"FAIL: 取到的条目不对：{sections[0][3]}")
            return 1

        real_sections, real_skipped = boq.scan()
        print(f"repository sections: {[(s[0], s[2], len(s[3])) for s in real_sections]}, "
              f"skipped: {len(real_skipped)}")
        print("PASS: the fixture's wp98 heading and fenced heading are ignored; "
              "the real tree still yields exactly its own 未解问题 section")
        return 0
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
