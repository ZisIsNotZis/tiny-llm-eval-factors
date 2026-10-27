#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`pairs.py` 的负控：改动必须把对应的受控对打掉、并点名，未改动的运行必须绿。

三件事，逐条打印 `ok` / `FAIL`：

  1. baseline：对真库跑一遍，受控集非空、退出 0（看不见输入的检查不算通过）。
  2. 身份栏：把库里某条受控对的一行 `temp` 改掉（在**副本**上改，真库只以 `mode=ro` 打开），
     该对必须从受控集消失，并以 `identity_mismatch:` 点名 `temp`，退出码 0（清单本身仍然有效）。
  3. 尺寸：把 fixture 副本里同一个模型文件的 `n_params` 改成使尺寸差 = 11%，该对必须消失并以
     `size_gt_10pct` 点名；脚本打印它重算出来的尺寸差，不写死。
  4. 缺真值：把 fixture 副本里那个模型文件整条删掉，该对必须消失并以 `no_truth` 点名。
  5. 真库与真 fixture 的字节哈希前后相同（负控没有污染被审对象）。

退出码：0 全部成立；1 有断言不成立（并指出是哪一条）。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PAIRS = HERE / "pairs.py"
DB = REPO / "experiments.sqlite"
TRUTH = REPO / "docs/subprojects/a02-模型规模/analysis/fixtures/gguf_truth.json"

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


def run_pairs(db: Path, truth: Path, out: Path, quiet: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PAIRS), "--db", str(db), "--truth", str(truth), "--out", str(out)],
        capture_output=True, text=True,
    )


def decode_excluded(ledger: dict) -> list[dict]:
    """`excluded` 是按列存的（列序 `columns.excluded`，字符串是 `strings` 的下标）。"""
    cols = ledger["columns"]["excluded"]
    pool = ledger["strings"]
    out = []
    for row in ledger["excluded"]:
        e = {}
        for k, v in zip(cols, row):
            e[k] = pool[v] if isinstance(v, int) and k != "size_delta" else v
        out.append(e)
    return out


def pair_key(entry: dict) -> tuple:
    """一格的身份 = 基准 + 两个模型文件 + 15 个身份栏（清单里 `ctx` 按 `ctx_columns` 列序存）。"""
    return (entry["bench"], entry["model_a"], entry["model_b"], json.dumps(entry["ctx"]))


def main() -> int:
    db_before, truth_before = sha256(DB), sha256(TRUTH)
    tmp = Path(tempfile.mkdtemp(prefix="a15-pairs-nc-"))
    try:
        # ---- 1. baseline ---------------------------------------------------------
        base_out = tmp / "base.json"
        base = run_pairs(DB, TRUTH, base_out)
        print(f"[1] baseline (unmodified db): rc={base.returncode}")
        check(base.returncode == 0, "unmodified run exits 0", base.stderr[-400:])
        ledger = json.loads(base_out.read_text(encoding="utf-8")) if base_out.is_file() else {}
        pairs = ledger.get("cells", [])
        check(bool(pairs), "unmodified run yields a non-empty controlled set",
              f"cells={len(pairs)}")
        check(ledger.get("counts", {}).get("label_matched_cells") == len(pairs),
              "the printed label_matched count equals the number of cells")
        if not pairs:
            return 1
        print(f"BASELINE_SHA256 {sha256(base_out)}")
        # 拿第一条**家族层**的格（不同家族、实测参数量不同）：家族计数才是本清单要保的东西。
        fam_cells = [p for p in pairs if not p["same_n_params"]]
        check(bool(fam_cells), "the ledger carries at least one family-tier cell",
              f"cells={len(pairs)}")
        if not fam_cells:
            return 1
        target = fam_cells[0]
        key = pair_key(target)
        ctx = dict(zip(ledger["ctx_columns"], target["ctx"]))
        print(f"    target pair: {target['id']} {target['bench']} "
              f"{target['model_a']} vs {target['model_b']} (temp={ctx['temp']})")

        # ---- 2. identity column ------------------------------------------------
        db_copy = tmp / "mutated.sqlite"
        src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        dst = sqlite3.connect(db_copy)
        with dst:
            src.backup(dst)
        src.close()
        new_temp = "9.75" if ctx["temp"] != "9.75" else "9.5"
        rows = 0
        with dst:
            cur = dst.execute(
                "UPDATE experiments SET temp=? WHERE model=? AND _bench=?"
                " AND protocol IS ? AND temp IS ? AND n_items IS ?",
                (new_temp, target["model_b"], target["bench"], ctx["protocol"],
                 ctx["temp"], ctx["n_items"]),
            )
            rows = cur.rowcount
        dst.close()
        check(rows >= 1, f"mutation touched a row (temp {ctx['temp']} → {new_temp})",
              f"rowcount={rows}")
        mut_out = tmp / "mutated.json"
        mut = run_pairs(db_copy, TRUTH, mut_out)
        mut_ledger = json.loads(mut_out.read_text(encoding="utf-8"))
        still = [p for p in mut_ledger["cells"] if pair_key(p) == key]
        check(mut.returncode == 0, "mutated run still exits 0 (inventory is valid)", mut.stderr[-400:])
        check(not still, "the pair with the altered identity column left the controlled set",
              f"still present as {[p['id'] for p in still]}")
        named = [e for e in decode_excluded(mut_ledger)
                 if (e["bench"], e["model_a"], e["model_b"]) == (target["bench"],
                                                                target["model_a"],
                                                                target["model_b"])
                 and e["reason"].startswith("identity_mismatch:")
                 and "temp" in e["reason"]]
        check(bool(named), "it is named in `excluded` with identity_mismatch:…temp…",
              f"reasons seen: {sorted({e['reason'] for e in decode_excluded(mut_ledger)})[:6]}")
        if named:
            print(f"    excluded entry: {named[0]['reason']} "
                  f"(size_delta={named[0].get('size_delta')})")

        # ---- 3. size delta forced to 11% ---------------------------------------
        truth_copy = tmp / "truth.json"
        doc = json.loads(TRUTH.read_text(encoding="utf-8"))
        na = doc["models"][target["model_a"]]["n_params"]
        old = doc["models"][target["model_b"]]["n_params"]
        # |na - nb| / max(na, nb) = 0.11 且 nb > na  ⇒  nb = na / 0.89
        doc["models"][target["model_b"]]["n_params"] = int(round(na / (1.0 - 0.11)))
        nb = doc["models"][target["model_b"]]["n_params"]
        forced = abs(na - nb) / max(na, nb)
        truth_copy.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        print(f"[3] size mutation: n_params[{target['model_b']}] {old} → {nb} "
              f"(recomputed size_delta = {forced:.4f})")
        check(forced > ledger["size_tolerance"], "the forced delta really exceeds the 10% criterion",
              f"{forced:.4f}")
        size_out = tmp / "size.json"
        sz = run_pairs(DB, truth_copy, size_out)
        sz_ledger = json.loads(size_out.read_text(encoding="utf-8"))
        still = [p for p in sz_ledger["cells"] if pair_key(p) == key]
        check(sz.returncode == 0, "size-mutated run still exits 0", sz.stderr[-400:])
        check(not still, "the pair with an 11% size delta left the controlled set",
              f"still present as {[p['id'] for p in still]}")
        named = [e for e in decode_excluded(sz_ledger)
                 if (e["bench"], e["model_a"], e["model_b"]) == (target["bench"],
                                                                target["model_a"],
                                                                target["model_b"])
                 and e["reason"] == "size_gt_10pct"]
        check(bool(named), "it is named in `excluded` with size_gt_10pct",
              str(sorted({e["reason"] for e in decode_excluded(sz_ledger)})[:6]))
        if named:
            print(f"    excluded entry: {named[0]['reason']} "
                  f"(size_delta={named[0].get('size_delta')})")
        # 参照：只改真值不会改变候选集（候选只看库，不看真值），只会改变哪些候选成为受控格。
        check(sz_ledger["counts"]["candidates"] == ledger["counts"]["candidates"],
              "a truth mutation does not change the candidate set",
              f"{ledger['counts']['candidates']} → {sz_ledger['counts']['candidates']}")
        # 定义检查（不是快照常量）：清单里每一格的尺寸差都必须 ≤ 容差。
        tol = ledger["size_tolerance"]
        over = [p["id"] for p in sz_ledger["cells"] if p["size_delta"] > tol]
        check(not over, f"every controlled cell (both runs) obeys size_delta <= {tol}",
              f"offenders: {over[:5]}")
        over_base = [p["id"] for p in ledger["cells"] if p["size_delta"] > tol]
        check(not over_base, "the unmodified inventory obeys the same definition",
              f"offenders: {over_base[:5]}")

        # ---- 4. missing truth ---------------------------------------------------
        truth_none = tmp / "truth-empty.json"
        doc = json.loads(TRUTH.read_text(encoding="utf-8"))
        del doc["models"][target["model_b"]]
        truth_none.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        print(f"[4] truth mutation: {target['model_b']} removed from the fixture")
        nt_out = tmp / "notruth.json"
        nt = run_pairs(DB, truth_none, nt_out)
        nt_ledger = json.loads(nt_out.read_text(encoding="utf-8"))
        still = [p for p in nt_ledger["cells"] if pair_key(p) == key]
        check(nt.returncode == 0, "missing-truth run still exits 0", nt.stderr[-400:])
        check(not still, "the pair whose model has no truth left the controlled set",
              f"still present as {[p['id'] for p in still]}")
        named = [e for e in decode_excluded(nt_ledger)
                 if (e["bench"], e["model_a"], e["model_b"]) == (target["bench"],
                                                                target["model_a"],
                                                                target["model_b"])
                 and e["reason"] == "no_truth"]
        check(bool(named), "it is named in `excluded` with no_truth",
              str(sorted({e["reason"] for e in decode_excluded(nt_ledger)})[:6]))

        # ---- 5. no pollution ---------------------------------------------------
        check(sha256(DB) == db_before, "the real database is byte-identical before and after")
        check(sha256(TRUTH) == truth_before, "the real truth fixture is byte-identical before and after")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = [w for ok, w in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks green")
    if bad:
        print("NEGATIVE CONTROL FAILED: " + "; ".join(bad))
        return 1
    print("NEGATIVE CONTROL OK: the inventory loses the mutated pair and names the reason; "
          "the unmodified run is green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
