#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`effects.py` 的负控：把清单里的一对分数改成相等，「可分辨数」或「翻转数」必须跟着变、并点名。

两处改动，每次只改一个 byte 级别的量（受控集本身不动，动的是分数）：

  1. baseline：对真清单跑一遍，退出 0；记下 `resolvable` / `flips` 两个计数。
  2. **削平一格**：取清单里第一条 `resolvable` 的受控格，把它的两个分数改成相等。那一格必须
     从可分辨变成不可分辨（`resolvable` −1），且该格 id 在改后的结果里 delta=0 且不可分辨。
  3. **削平一档**：取第一组有可读翻转（两档位宽 handicap 相差 ≤ 半档）的交互组，把它高档那一侧
     的分数改成与该组低档相等。该组的翻转必须消失（`flips` −1），并点名组与档。
  4. 真清单 `analysis/pairs.json` 前后字节相同（负控不改被审对象）。

退出码：0 全部成立；1 有断言不成立（打印是哪一条，并打印前后两份计数）。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EFFECTS = HERE / "effects.py"
LEDGER = HERE / "pairs.json"

SUMMARY_RE = re.compile(r"^SUMMARY (.*)$", re.M)

results: list[tuple[bool, str]] = []


def check(cond: bool, what: str, detail: str = "") -> bool:
    results.append((bool(cond), what))
    print(f"  {'ok  ' if cond else 'FAIL'} {what}" + (f" — {detail}" if detail and not cond else ""))
    return bool(cond)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_effects(ledger: Path, out: Path) -> tuple[dict, dict | None]:
    proc = subprocess.run([sys.executable, str(EFFECTS), "--ledger", str(ledger),
                           "--out", str(out), "--quiet"], capture_output=True, text=True)
    m = SUMMARY_RE.search(proc.stdout)
    summary = dict(kv.split("=", 1) for kv in (m.group(1).split() if m else []))
    summary["rc"] = str(proc.returncode)
    summary["_stderr"] = proc.stderr
    doc = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
    return summary, doc


def main() -> int:
    ledger_before = sha256(LEDGER)
    tmp = Path(tempfile.mkdtemp(prefix="a15-effects-nc-"))
    try:
        base_sum, base_doc = run_effects(LEDGER, tmp / "base.json")
        print(f"[1] baseline: rc={base_sum['rc']} "
              f"resolvable={base_sum.get('resolvable')} flips={base_sum.get('flips')}")
        check(base_sum["rc"] == "0", "unmodified run exits 0", base_sum["_stderr"][-400:])
        check(base_doc is not None and base_doc["cells"], "unmodified run analyses a non-empty cell set")
        if base_doc is None or not base_doc["cells"]:
            return 1

        print(f"BASELINE_SHA256 {sha256(tmp / 'base.json')}")

        # ---- 2. equalise one resolvable cell ------------------------------------
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        target = next(c for c in base_doc["cells"] if c["resolvable"])
        entry = next(p for p in doc["cells"] if p["id"] == target["id"])
        print(f"[2] equalising cell {entry['id']} ({target['bench']} {target['family_a']} vs "
              f"{target['family_b']}): score_a={entry['score_a']} → score_b was {entry['score_b']}")
        entry["score_b"] = entry["score_a"]
        mut = tmp / "cell.json"
        mut.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        sum1, doc1 = run_effects(mut, tmp / "cell-out.json")
        r0, r1 = int(base_sum["resolvable"]), int(sum1["resolvable"])
        print(f"    resolvable {r0} → {r1}; flips {base_sum['flips']} → {sum1['flips']}")
        check(sum1["rc"] == "0", "mutated run still exits 0", sum1["_stderr"][-400:])
        check(r1 < r0, "the resolvable count drops after equalising a resolvable pair",
              f"{r0} → {r1}")
        after = next((c for c in (doc1 or {}).get("cells", []) if c["id"] == entry["id"]), None)
        check(after is not None and after["delta_pp"] == 0 and after["resolvable"] is False,
              f"cell {entry['id']} is named in the new result as delta=0 and not resolvable",
              json.dumps(after)[:300] if after else "cell vanished")
        check((r1 != r0) or (sum1["flips"] != base_sum["flips"]),
              "at least one of {resolvable, flips} changed (this control's whole point)")

        # ---- 3. kill one readable flip ------------------------------------------
        group = next(g for g in base_doc["interaction"] if g["flips_readable"] >= 1)
        lo = group["levels"][0]
        hi = next(g for g in group["levels"] if g["sign"] is not None
                  and lo["sign"] is not None and g["sign"] * lo["sign"] < 0)
        print(f"[3] killing the flip in {group['bench']} {group['family_a']} vs {group['family_b']}: "
              f"level {lo['ids']} ({lo['delta_pp']:+.1f}pp) → level {hi['ids']} ({hi['delta_pp']:+.1f}pp)")
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        for cell_id in hi["ids"]:
            p = next(p for p in doc["cells"] if p["id"] == cell_id)
            p["score_b"] = p["score_a"]
        mut2 = tmp / "flip.json"
        mut2.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        sum2, doc2 = run_effects(mut2, tmp / "flip-out.json")
        print(f"    flips {base_sum['flips']} → {sum2['flips']}; "
              f"resolvable {base_sum['resolvable']} → {sum2['resolvable']}")
        check(sum2["rc"] == "0", "mutated run still exits 0", sum2["_stderr"][-400:])
        f0, f1 = int(base_sum["flips"]), int(sum2["flips"])
        check(f1 < f0, "the flip counter drops after flattening one quant level", f"{f0} → {f1}")
        g_after = next((g for g in (doc2 or {}).get("interaction", [])
                        if (g["bench"], g["ctx_key"], g["family_a"], g["family_b"])
                        == (group["bench"], group["ctx_key"], group["family_a"], group["family_b"])
                        and g["n_params_a"] == group["n_params_a"]
                        and g["n_params_b"] == group["n_params_b"]), None)
        check(g_after is not None and g_after["flips"] == group["flips"] - 1,
              "that interaction group is named and loses exactly one flip",
              json.dumps(g_after)[:300] if g_after else "group vanished")

        # ---- 4. no pollution ----------------------------------------------------
        check(sha256(LEDGER) == ledger_before, "the real ledger is byte-identical before and after")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = [w for ok, w in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks green")
    if bad:
        print("NEGATIVE CONTROL FAILED: " + "; ".join(bad))
        return 1
    print("NEGATIVE CONTROL OK: flattening one cell lowers `resolvable`, flattening one quant level "
          "lowers `flips`, both are named, and the unmodified run is green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
