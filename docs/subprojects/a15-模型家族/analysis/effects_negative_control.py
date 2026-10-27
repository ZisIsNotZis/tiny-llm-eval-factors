#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`effects.py` 的负控：把清单里的一对分数改成相等，「可分辨数」或「翻转数」必须跟着变、并点名。

家族结论只活在「家族层 + bpw_matched」这个子集上（见 `effects.py` 头部），所以两处改动都打在那里：

  1. baseline：对真清单跑一遍，退出 0；记下 `family_resolvable` / `flips` 两个计数。
  2. **削平一格**：取第一条「家族层 + bpw_matched + 可分辨」的格，把两个分数改成相等。那一格必须
     从可分辨变成不可分辨（`family_resolvable` −1），且该格 id 在改后的结果里 delta=0 且不可分辨。
  3. **削平一档**：取第一组有翻转的交互组（组内的档全是 bpw_matched），把它高档那一侧的分数改成与
     该组低档相等。该组的翻转必须消失（`flips` −1），并点名组与档。若未改动的结果里**没有**翻转可杀，
     本控制直接判红并说明（翻转计数无法被行使，不是通过）。
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
        print(f"[1] baseline: rc={base_sum['rc']} family_resolvable={base_sum.get('family_resolvable')} "
              f"flips={base_sum.get('flips')}")
        check(base_sum["rc"] == "0", "unmodified run exits 0", base_sum["_stderr"][-400:])
        check(base_doc is not None and base_doc["cells"], "unmodified run analyses a non-empty cell set")
        if base_doc is None or not base_doc["cells"]:
            return 1
        print(f"BASELINE_SHA256 {sha256(tmp / 'base.json')}")

        claim_cells = [c for c in base_doc["cells"]
                       if c["bpw_matched"] and not c["same_n_params"]]
        check(bool(claim_cells), "the family claim has at least one bpw_matched cell",
              f"cells={len(base_doc['cells'])}")

        # ---- 2. equalise one resolvable family cell ------------------------------
        target = next((c for c in claim_cells if c["resolvable"]), None)
        check(target is not None, "there is a resolvable family cell at matched bpw to flatten")
        if target is None:
            return 1
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        entry = next(p for p in doc["cells"] if p["id"] == target["id"])
        print(f"[2] equalising {entry['id']} ({target['bench']} {target['family_a']} vs "
              f"{target['family_b']}, {target['bpw_mean']:.2f} bpw): "
              f"score_a={entry['score_a']} → score_b was {entry['score_b']}")
        entry["score_b"] = entry["score_a"]
        mut = tmp / "cell.json"
        mut.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        sum1, doc1 = run_effects(mut, tmp / "cell-out.json")
        r0, r1 = int(base_sum["family_resolvable"]), int(sum1["family_resolvable"])
        print(f"    family_resolvable {r0} → {r1}; flips {base_sum['flips']} → {sum1['flips']}")
        check(sum1["rc"] == "0", "mutated run still exits 0", sum1["_stderr"][-400:])
        check(r1 < r0, "the resolvable count drops after equalising a resolvable pair",
              f"{r0} → {r1}")
        after = next((c for c in (doc1 or {}).get("cells", []) if c["id"] == entry["id"]), None)
        check(after is not None and after["delta_pp"] == 0 and after["resolvable"] is False,
              f"cell {entry['id']} is named in the new result as delta=0 and not resolvable",
              json.dumps(after)[:300] if after else "cell vanished")
        check((r1 != r0) or (sum1["flips"] != base_sum["flips"]),
              "at least one of {family_resolvable, flips} changed (this control's whole point)")

        # ---- 3. kill one flip ---------------------------------------------------
        group = next((g for g in base_doc["interaction"] if g["flips"] >= 1), None)
        check(group is not None, "the unmodified run carries at least one sign flip to kill")
        if group is None:
            return 1
        levels = group["levels"]
        lo = levels[0]
        hi = next((l for l in levels if l["sign"] is not None and lo["sign"] is not None
                   and l["sign"] * lo["sign"] < 0), None)
        if hi is None:
            print("  FAIL no opposite-sign level found inside the flagged group")
            return 1
        print(f"[3] killing the flip in {group['bench']} {group['family_a']} vs "
              f"{group['family_b']}: level {lo['ids']} ({lo['delta_pp']:+.1f}pp) → "
              f"level {hi['ids']} ({hi['delta_pp']:+.1f}pp)")
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        for cell_id in hi["ids"]:
            p = next(p for p in doc["cells"] if p["id"] == cell_id)
            p["score_b"] = p["score_a"]
        mut2 = tmp / "flip.json"
        mut2.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        sum2, doc2 = run_effects(mut2, tmp / "flip-out.json")
        print(f"    flips {base_sum['flips']} → {sum2['flips']}; "
              f"family_resolvable {base_sum['family_resolvable']} → {sum2['family_resolvable']}")
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
    print("NEGATIVE CONTROL OK: flattening one family cell lowers `family_resolvable`, flattening "
          "one quant level lowers `flips`, both are named, and the unmodified run is green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
