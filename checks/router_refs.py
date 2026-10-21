#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三个路由文件里印出的每一条引用，都必须在树里解析得到。

`docs/plan/plan.yaml` 与 `docs/result/result.yaml` 在文档迁移（021e6b8）后已搬进
`docs/subprojects/<dir>/{PLAN,RESULT}.md`，而 STATUS.md / FINDINGS.md / README.md 是**路由**：
它们只写「事实在哪个节点」，所以路径和节点 id 就是它们的全部内容。迁移后路由仍指旧路径、
旧 id 时，读者按路由找过去什么也读不到——这不是文字瑕疵，是路由失效，而它曾长期无人发现，
因为没有任何一步把「路由指得到」当成可核对的断言。

这个脚本只判**可解析**，不判正文真假（正文真假归各节点自己的证据与 `docs/check_docs.py`）：

  * token 的边界由反引号决定：`docs/...` 落在**同一行的反引号 span 里**时，整个 span（空格算在内）
    就是 token；落在裸文本里时，仍按空白与标点截断；
  * 引用 = 引用 token 里的 `docs/<path>.md::<id>` 或 `docs/<path>.yaml::<id>`；
  * 路径 token = 路径 token 里不带 `::` 的 `docs/...`（`docs/check_docs.py`、`docs/need/` 都算）；
  * 引用要两半都成立才算解析：路径是存在的**文件**，且 id 在那个文件里——`.md` 看二级及更深的
    ATX 标题，取其第一个空白分隔的 token 恰好等于 id（`### res25 ...`、`## res3 :: ...`）；
    `.yaml` 看第 0 列的顶层键 `<id>:`；
  * 路径 token 只要求那个路径存在（文件或目录）。
  * 围栏代码块（` ``` ` / `~~~`）与 HTML 注释（`<!-- … -->`）不算正文，判 id 与判引用都在把它们
    遮蔽之后的文本上做：写在围栏或注释里的 `## id` 不是 id，写在那里的 `docs/…::id` 不是路由。
    否则在 RESULT.md 末尾贴一段示例代码就能凭空造出一个「解析得到」的 id，或在路由器里贴一段
    注释掉的引用就能让它自己绿。
  * 行内反引号 span 里的 `<!--`（例如 `` `<!--` ``）**不是**注释开标记：那是行内代码。把它当注释，
    它后面同一行直到文件尾的每条引用都会同时掉出分母与抽取，绿的只是「什么都没看见」。
  * 路由器（三个文件）里遮蔽不许跑到文件尾：未闭合的围栏或 `<!--` 会把后面每条引用一起吞掉，
    同样只留下一个自洽的绿。`mask_non_route` 因此报出遮蔽起点行，`scan` 判一条 `unterminated-mask`
    红行。文档一侧不需要这条：那里遮蔽过头只会让 id 少算，于是引用判 `missing-id`，本来就红。

分母独立于抽取器，这是这条检查的第二半。`docs/…::` 形状按一条不看 id 的规则数：同一行内 `::` 前面
最近的 `docs/` 与它之间没有反引号（反引号是 token 边界），就进分母——`::` 前有没有空白不影响计数。
抽取器接受 `::` 前的可选空白，所以 `docs/X.md ::ghost` 会被读成一条引用、按 id 判 `missing-id`；
它读不成的形状（`…/RESULT.md::` 换行接 id、`…:: resdead`）则在该行印一条 `unparsed-citation`
红行，自检行 `seen != matched` 随之 `MISMATCH`。两条路都只通向红，不会出现 `seen == matched` 而
某条引用已经悄悄掉出分母的自洽绿。

不解析的两类，各自有理由：token 里带 `<` 或 `>` 的是模板（`docs/<layer>/<layer>.yaml`），它写的是
形状不是文件，判它「不存在」等于判散文；`::` 前的路径不存在时只报 `missing-file`，不猜那个 id 本来
该落在哪。

反引号边界是有意的取舍：本仓库的目录名本身带空格（`docs/subprojects/a04-MoE 各层比特分配` 等），
裸文本里的空白边界会把 `docs/subprojects/a09-量化感知训练 QAT/RESULT.md::an6` 截断成
`docs/subprojects/a09-量化感知训练` 而误报 `missing-file`，引用一侧更会整条消失、连分母都不算它。
背面同样有代价，且同样可见：裸文本（没加反引号）里的带空格路径仍按空白截断，于是报成一条
`missing-file` 红行——它不会静默消失，读的人看到的是「这条要么写错了边界，要么路径不存在」。
同一条道理推到分母上：裸文本里把 `docs/…::` 拿来当例子写（不放进反引号）会报一条
`missing-id` 或 `unparsed-citation` 红行，两种都不会静默消失。这是有意的方向——宁可让一个示例红，
也不让一条真引用绿；要举例就放进反引号 span 里或放进围栏/注释里（那两处不是路由，会被数出来）。
引用 token 的 id 按上面那条 id 规则比较，所以把整行标题写进 `::` 后面的引用（id 里带空格）会报
`missing-id`；这条判的是路由写没写出一个 id，不是散文。

反引号边界还可能悄悄丢一条引用（span 抽取写错、span 未闭合等），所以每次运行都打一行自检
`citation tokens seen: N, matched: M`：N 是原文里出现过的引用形状（数 `docs/…::` 形状，与 token 抽取
无关），M 是 token 抽取真正拿到手的引用数，两者不等即 `MISMATCH` 并判失败。被围栏/注释遮蔽掉的
形状不计入 N 的比较（它们不是路由），但会单独印出来，读者知道有多少形状被当成非正文跳过了。

空扫描不算通过：一个看不见自己输入的检查必须红，而不是绿。三个路由文件缺任何一个都是外部阻断
（exit 2 + `BLOCKED:` 行），不是通过也不是失败。

    python3 checks/router_refs.py                  # 仓库根由脚本自身位置推出
    python3 checks/router_refs.py --root /tmp/x    # 负控用临时树，语义完全相同

退出码：0 全部解析且扫描非空；1 有无法解析的引用/路径、读不成引用的 `docs/…::` 形状、路由器里
未闭合的围栏/注释、扫描为空，或自检不等（引用掉出分母）；2 路由文件缺失。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROUTERS = ("STATUS.md", "FINDINGS.md", "README.md")

# 裸文本（不在反引号 span 里）的 token 边界：空白、反引号、引号、括号、竖线、`*` 与中日文标点
# 都截断。全角冒号 `：` 一并截断，半角 `:` 留着——`::` 要用它。反引号 span 里的 token 不走这条
# 正则，它是整个 span 内容（空格算在内）。
_BARE_TAIL = r"[^\s`'\"()\[\]{}|*，。、；：！？【】（）「」“”]+"
# `::` 前的空白可写可不写：`docs/X.md::id` 与 `docs/X.md ::id` 都是引用，都会被解析并按 id 判。
CITATION_RE = re.compile(r"docs/" + _BARE_TAIL + r"?[ \t]*::[A-Za-z0-9_.\-]+")
PATH_RE = re.compile(r"docs/" + _BARE_TAIL)
# 分母只看 `::` 这个形状，不看它后面有没有 id：id 缺失正是要被抓到的形态。
MARK_RE = re.compile(r"::")
TEMPLATE_MARKS = ("<", ">")

HEADING_RE = re.compile(r"^(#{2,})[ \t]+(.+)$")
# 围栏：行首最多 3 格缩进，3 个以上的 ` 或 ~，后面是 info string（闭合围栏的 info string 为空）。
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def mask_non_route(text):
    """把围栏代码块与 HTML 注释换成等长空白，换行留住（行号与列偏移不变）。

    返回 (遮蔽后的文本, 遮蔽跑到文件尾时的起始行号或 None)。判 id 与判引用都用遮蔽后的文本：
    围栏里的是示例代码，注释里的是给人看的备注，两者都不是路由正文。

    `<!--` 只有在**不在行内反引号 span 里**时才是注释开标记：写在反引号里的 `` `<!--` `` 是行内
    代码，把它当注释会把后面整段正文吞掉。

    遮蔽跑到文件尾（未闭合的围栏或 `<!--`）在文档一侧是安全失败：id 少算，引用判 `missing-id`。
    在路由器一侧它不是：被遮蔽的引用同时掉出分母与抽取，于是自洽地绿。所以这里把起始行号交出去，
    由 `scan` 判 `unterminated-mask` 红行。
    """
    out = list(text)
    n = len(text)

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    fence = None                       # 打开围栏的 (字符, 长度)，例如 ("`", 3)
    fence_line = None
    comment_open = False
    comment_line = None
    i = 0
    lineno = 0
    while i < n:
        eol = text.find("\n", i)
        eol = n if eol < 0 else eol
        lineno += 1
        if fence is not None:
            blank(i, eol)
            m = FENCE_RE.match(text[i:eol])
            if (m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1]
                    and not m.group(2).strip()):
                fence = None
            i = eol + 1
            continue
        started_open = comment_open
        spans = code_spans(text[i:eol])       # 行内代码里的 `<!--` 不是注释开标记
        j = i
        while j < eol:
            if comment_open:
                c = text.find("-->", j, eol)
                if c < 0:
                    blank(j, eol)
                    break
                blank(j, c + 3)
                comment_open = False
                j = c + 3
            else:
                c = text.find("<!--", j, eol)
                if c < 0:
                    break
                if any(a <= c - i < b for a, b, _, _ in spans):
                    j = c + 4            # 行内代码：跳过这个开标记，继续找下一个
                    continue
                comment_open = True
                comment_line = lineno
                blank(c, c + 4)
                j = c + 4
        if not started_open and not comment_open:
            m = FENCE_RE.match(text[i:eol])
            if m and (m.group(1)[0] != "`" or "`" not in m.group(2)):
                fence = (m.group(1)[0], len(m.group(1)))
                fence_line = lineno
                blank(i, eol)
        i = eol + 1
    open_at = fence_line if fence is not None else (comment_line if comment_open else None)
    return "".join(out), open_at


def ids_in_md(text):
    """二级及更深 ATX 标题的第一个空白分隔 token；围栏与注释里的标题不算 id。"""
    ids = set()
    for line in mask_non_route(text)[0].split("\n"):
        m = HEADING_RE.match(line)
        if m:
            parts = m.group(2).split()
            if parts:
                ids.add(parts[0])
    return ids


def ids_in_yaml(text):
    """第 0 列的顶层键 `<id>:`。"""
    ids = set()
    for line in text.split("\n"):
        if not line or line[0] in " \t#-":
            continue
        head, sep, _ = line.partition(":")
        if sep:
            ids.add(head)
    return ids


def code_spans(line):
    """同一行内反引号 span 的 (start, end, content_start, content_end)。

    开闭反引号等长才算一对；行尾未闭合的反引号不成为 span，那段文本退回裸文本边界，
    与没有这条规则时逐字相同。
    """
    spans = []
    i, n = 0, len(line)
    while i < n:
        if line[i] != "`":
            i += 1
            continue
        j = i
        while j < n and line[j] == "`":
            j += 1
        ticks, k, closed = j - i, j, -1
        while k < n:
            if line[k] != "`":
                k += 1
                continue
            m = k
            while m < n and line[m] == "`":
                m += 1
            if m - k == ticks:
                closed = k
                break
            k = m
        if closed < 0:
            i = j                      # 未闭合：当普通文本，不收 span
            continue
        spans.append((i, closed + ticks, j, closed))
        i = closed + ticks
    return spans


def _blank(text, a, b):
    """把 text[a:b] 换成等长空白：保住长度与偏移，span 里的字符不再被裸文本正则看见。"""
    return text[:a] + " " * (b - a) + text[b:]


def _split_citation(token):
    """`path[ ]::id` → (path, id)；path 与 id 两端的空白与 id 的句末标点去掉。"""
    path, _, node_id = token.partition("::")
    return path.strip(), node_id.strip().rstrip(".,;")


def tokens_in_line(line):
    """一行里的 (kind, token, path, node_id)。

    反引号 span 里的 `docs/...` 整段是一个 token（空格算在内）；span 之外的文本仍按空白与标点
    截断，引用优先，余下的才算路径 token。

    span 里只有一段 `docs/` 且它就从 span 开头起算时，span 才是 token；span 里还有别的东西
    （命令行 `` `python3 docs/check_docs.py` ``、一段里两个 `docs/`）则退回裸文本边界，
    那段 `docs/...` 仍会被找到。
    """
    found = []
    masked = line
    for start, end, cstart, cend in code_spans(line):
        token = line[cstart:cend].strip()
        if not (token.startswith("docs/") and token.count("docs/") == 1):
            continue                   # 不是「整眼就是一个 docs 路径」的 span：留给裸文本正则
        masked = _blank(masked, start, end)
        if "::" in token:
            path, node_id = _split_citation(token)
            found.append(("citation", token, path, node_id))
        else:
            found.append(("path", token, token, None))

    spans = []
    for m in CITATION_RE.finditer(masked):
        token = m.group(0)
        path, node_id = _split_citation(token)
        found.append(("citation", token, path, node_id))
        spans.append((m.start(), m.end()))
    for m in PATH_RE.finditer(masked):
        if any(a <= m.start() < b for a, b in spans):
            continue
        token = m.group(0).rstrip(".,;:")
        if "::" in token or not token:
            continue
        found.append(("path", token, token, None))
    return found


def citation_mark_positions(line):
    """这一行里 `docs/…::` 形状的列位置——自检的分母，独立于 token 抽取。

    规则不看 `::` 后面的 id（那就和抽取器一起瞎了）：`::` 与同一行内它前面最近的 `docs/` 之间没有
    反引号（反引号是 token 边界），就算一条形状——`::` 前有没有空白不改变这个判断，所以
    `…/RESULT.md ::ghost` 也留在分母里。`::` 后面是什么同样不改变它：`…/RESULT.md::` 换行接 id、
    `…/RESULT.md:: resdead` 都在分母里。散文里孤立的 `` `::` `` 不算，因为它与前面 `docs/` 之间隔着
    反引号；同一行里没有 `docs/` 的 `::` 也不算。STATUS.md:3 与 FINDINGS.md:3 那两处
    「`::` 后面是节点 id」正是被这两条挡掉的（前者靠反引号，后者靠同一行没有 `docs/`），不是碰巧。
    """
    positions = []
    prev = 0
    for m in MARK_RE.finditer(line):
        pos = m.start()
        start = line.rfind("docs/", prev, pos)
        if start >= 0 and "`" not in line[start:pos]:
            positions.append(pos)
        prev = m.end()
    return positions


def _mark_snippet(line, pos):
    """把 `::` 前后黏着的那个 token 印出来，读的人一眼看到是哪一条没读成引用。"""
    a = pos
    while a > 0 and not line[a - 1].isspace() and line[a - 1] not in "`|":
        a -= 1
    b = pos + 2
    while b < len(line) and not line[b].isspace() and line[b] not in "`|":
        b += 1
    return line[a:b]


def scan(root):
    """扫三个路由文件。

    返回 dict：citations / paths / skipped（模板）、marks_raw（原文里的 `docs/…::` 形状数）、
    marks_route（遮蔽掉围栏与注释后仍在正文里的形状数）、matched（token 抽取拿到手的引用数）、
    unparsed（留在正文里却没读成引用的形状，逐行一条）。
    """
    citations, paths, unparsed, unterminated = [], [], [], []
    skipped = 0
    marks_raw = marks_route = matched = 0
    for name in ROUTERS:
        text = (root / name).read_text(encoding="utf-8")
        visible, open_at = mask_non_route(text)
        if open_at is not None:
            # 路由器里遮蔽跑到文件尾：后面每条引用都会同时掉出分母与抽取，只能判红。
            unterminated.append((name, open_at))
        for lineno, (raw, line) in enumerate(zip(text.split("\n"),
                                                visible.split("\n")), 1):
            marks = citation_mark_positions(line)
            marks_raw += len(citation_mark_positions(raw))
            marks_route += len(marks)
            cites, covered = [], set()
            cursor = 0
            for kind, token, path, node_id in tokens_in_line(line):
                if kind == "citation":
                    matched += 1
                    cites.append(token)
                    at = line.find(token, cursor)
                    if at >= 0:
                        covered.update(range(at, at + len(token)))
                        cursor = at + len(token)
                    if not node_id:
                        # `docs/…::` 后面没有 id：形状在，引用读不成，必须可见。
                        inner = token.find("::")
                        pos = at + inner if (at >= 0 and inner >= 0) else -1
                        unparsed.append((name, lineno,
                                         _mark_snippet(line, pos) if pos >= 0 else token))
                        continue
                if any(mark in token for mark in TEMPLATE_MARKS):
                    skipped += 1          # 模板写的是形状，不是文件
                    continue
                (citations if kind == "citation" else paths).append(
                    (name, lineno, token, path, node_id))
            if len(marks) > len(cites):
                # 抽取器拿到的引用比正文里的形状少：逐条点名，而不是只留一行统计。
                for pos in marks:
                    if pos in covered or (pos + 1) in covered:
                        continue
                    unparsed.append((name, lineno, _mark_snippet(line, pos)))
    return {
        "citations": citations, "paths": paths, "skipped": skipped,
        "marks_raw": marks_raw, "marks_route": marks_route, "matched": matched,
        "unparsed": unparsed, "unterminated": unterminated,
    }


class Resolver:
    """同一文件只读一次，id 集合缓存复用。"""

    def __init__(self, root):
        self.root = root
        self._cache = {}

    def ids(self, rel):
        """返回 id 集合；文件缺失或后缀不认识时返回 None。"""
        if rel not in self._cache:
            path = self.root / rel
            if not path.is_file():
                self._cache[rel] = None
            elif rel.endswith(".md"):
                self._cache[rel] = ids_in_md(path.read_text(encoding="utf-8", errors="replace"))
            elif rel.endswith((".yaml", ".yml")):
                self._cache[rel] = ids_in_yaml(path.read_text(encoding="utf-8", errors="replace"))
            else:
                self._cache[rel] = None
        return self._cache[rel]


def main(argv):
    ap = argparse.ArgumentParser(add_help=True, description=__doc__)
    ap.add_argument("--root", default=str(REPO),
                    help="要检查的仓库根（默认：本脚本所在仓库）")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    missing_routers = [n for n in ROUTERS if not (root / n).is_file()]
    if missing_routers:
        print("BLOCKED: 路由文件缺失 " + ", ".join(str(root / n) for n in missing_routers))
        return 2

    result = scan(root)
    citations, paths = result["citations"], result["paths"]
    resolver = Resolver(root)

    problems = []
    cites_ok = 0
    for name, lineno, token, rel, node_id in citations:
        ids = resolver.ids(rel)
        if ids is None:
            problems.append((name, lineno, token, "missing-file"))
        elif node_id not in ids:
            problems.append((name, lineno, token, "missing-id"))
        else:
            cites_ok += 1
    paths_ok = 0
    for name, lineno, token, rel, _ in paths:
        if (root / rel).exists():
            paths_ok += 1
        else:
            problems.append((name, lineno, token, "missing-file"))
    problems.extend((name, lineno, token, "unparsed-citation")
                    for name, lineno, token in result["unparsed"])
    problems.extend((name, lineno, "`<!--` / fence", "unterminated-mask")
                    for name, lineno in result["unterminated"])
    problems.sort(key=lambda p: (p[0], p[1]))

    for name, lineno, token, reason in problems:
        print(f"{name}:{lineno}  {token}  {reason}")

    # 空扫描不是通过：看不见输入的检查必须说出来，而不是绿。
    vacuous = []
    if not any(c[0] == "STATUS.md" for c in citations):
        vacuous.append("STATUS.md 里的引用")
    if not any(c[0] == "FINDINGS.md" for c in citations):
        vacuous.append("FINDINGS.md 里的引用")
    if not paths:
        vacuous.append("路径 token")
    if vacuous:
        print("VACUOUS: 一条都没有扫到 —— " + "、".join(vacuous)
              + "；看不见输入的检查不判绿")

    if result["skipped"]:
        print(f"skipped {result['skipped']} template token(s) containing '<'/'>' (shape, not a file)")

    # 自检：正文里的引用形状（N）必须被 token 抽取全部拿到（M 含模板引用）。不等就是又有一条引用
    # 悄悄掉出分母，而那正是这个脚本要防的失败形态，所以判红而不是只打一行提示。
    raw, route, matched = result["marks_raw"], result["marks_route"], result["matched"]
    ignored = raw - route
    mismatch = route != matched
    print(f"citation tokens seen: {route}, matched: {matched}"
          + (f"; {ignored} more inside fenced code / HTML comments (not routes)" if ignored else "")
          + ("  MISMATCH: 有引用没进 token 抽取" if mismatch else ""))
    print(f"{cites_ok}/{len(citations)} citations resolved, "
          f"{paths_ok}/{len(paths)} path tokens resolved")

    return 1 if (problems or vacuous or mismatch) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
