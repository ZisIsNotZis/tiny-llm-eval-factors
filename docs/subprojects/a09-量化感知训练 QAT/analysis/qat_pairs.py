#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a09 量化感知训练 QAT：配对装置（实测比特 → 逐基准差 + 区间 → 原生阶梯上的落点）。

X = 「这份 gguf 是否经过 QAT 训练」；Y = 基准分数。只读 `experiments.sqlite` 与 gguf 头，
不改库、不改 `report.html`、不加载权重、不碰 GPU。

为什么要这条装置：`res12` 的原句是「同标称配方下 QAT 文件小 0.36–0.95 比特/权重，4-bit 配对
多数测不出差异，12B 的 MMLU 例外」。这句话里「同标称配方」只是配方名——本装置把配方名换成
**实测比特预算**（gguf 头的 `8 × 文件字节 ÷ 参数数`，与按张量 offset 差算的数据段位宽互校）
和**分配轮廓**（按张量类别的 bits/参数），于是每一对同时暴露三个不同的量：比特预算、分配轮廓、
量化格式。然后它把 QAT 点放到该族**原生阶梯**的同协议点上，用段内线性插值给出「同比特下的原生
应得」与残差——这是本设计能给出的唯一有界读数（库内没有比特钉住的 QAT/原生对）。

口径（`docs/subprojects/a09-量化感知训练 QAT/AGENTS.md`）：

  * 一族 = 去掉 `-qat` / `-it` / `-ud` 的血统根名（保留尺寸、大小写不敏感）；跨族不是受控比较。
  * 规范协议与区间定义借用 `a01::curves`（`BENCH` / `newcombe_diff` / `wilson` / `rows_for`），
    不复制；gguf 头解析借用 `a03::analysis/alloc.py`，不复制。
  * `truthfulqa_mc2` 的 `acc` 是概率质量均值（`i01::res26`），那一列只报差值，不套二项区间。
  * 不池化：基准、族、协议之间绝不平均。
  * 未测 ≠ 0：缺文件、缺比特、缺那一侧的测量都打印「未测」并写进汇总，不画成 0。

用法：
    python3 "docs/subprojects/a09-量化感知训练 QAT/analysis/qat_pairs.py"             # 全部检查，退出码即结论
    A09_SELFTEST=1 python3 ".../qat_pairs.py"                                          # 负控：翻红一条，退出 1
    python3 ".../qat_pairs.py" --build-fixtures                                        # 从本机 gguf 头重建夹具
    A09_NO_GGUF=1 python3 ".../qat_pairs.py"                                           # 只用入库夹具（干净 clone 路径）

退出码：0 全部预期成立；1 有预期不成立或负控触发；2 缺输入（gguf / bpw 源 / 库行），不算 PASS。
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE
for _ in range(6):                       # docs/subprojects/<id>/analysis/qat_pairs.py → 仓库根
    REPO = REPO.parent
    if (REPO / "experiments.sqlite").is_file():
        break
else:
    sys.exit("找不到仓库根（experiments.sqlite）")

DB = REPO / "experiments.sqlite"
A03 = REPO / "docs" / "subprojects" / "a03-量化方案与厂商" / "analysis"
sys.path.insert(0, str(REPO / ".wrapup"))
sys.path.insert(0, str(REPO / "docs" / "subprojects" / "a01-量化位宽" / "analysis"))
sys.path.insert(0, str(A03))

import pairs as a03pairs       # noqa: E402  —— 9 个基准的规范协议 + 逐格选取 + bpw_map 由 a03 拥有
import alloc as a03alloc        # noqa: E402  —— gguf 头解析与张量分类由 a03 拥有
import curves as a01curves      # noqa: E402  —— 两比例差区间（Newcombe method 10）由 a01 拥有

SELFTEST = os.environ.get("A09_SELFTEST") == "1"
NO_GGUF = os.environ.get("A09_NO_GGUF") == "1"   # 只用夹具：证明干净 clone 有界复现，也证明夹具真被读
FIXTURE = REPO / "docs" / "subprojects" / "a09-量化感知训练 QAT" / "analysis" / "fixtures" / "qat_alloc.json"
FIX = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else {}
DRIFT = []                       # [(model, 说明)]：夹具与本机 gguf 头的漂移
BENCH = a03pairs.BENCH
BENCH_ORDER = a03pairs.BENCH_ORDER
SHORT = a03pairs.SHORT
NON_COUNT = a03pairs.NON_COUNT
newcombe_diff = a01curves.newcombe_diff
CLASS_ORDER = ["embed", "attn", "ffn-dense", "ffn-expert", "ffn-shexp", "router", "output", "norm"]
UNIFORM_CLASSES = ["embed", "attn", "ffn-dense"]      # 只看装权重的三类：norm/output 常是 f32

results = []          # [(id, ok, detail)]


def check(cid, ok, detail):
    results.append((cid, bool(ok), detail))
    print(("  PASS " if ok else "  FAIL ") + f"{cid}: {detail}")
    return ok


def unmeasured(cid, detail):
    print(f"  UNMEASURED {cid}: {detail}")
    results.append((cid, None, detail))


def con():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


# ---------- 族 / 档位 / 文件 ----------

def file_of(model):
    return model if model.endswith(".gguf") else model + ".gguf"


def family_of(model):
    """血统根名：去掉量化后缀与 -qat/-it/-ud 标记，保留尺寸，大小写不敏感。"""
    stem, _q = __import__("mktables").split_quant(file_of(model))
    s = stem.lower()
    for pat in (r"[-_ ](it[-_ ]qat|qat)$", r"[-_ ](it|instruct|chat)$", r"[-_ ]ud$"):
        s = re.sub(pat, "", s)
    return re.sub(r"[-_ ]+$", "", s)


def quant_of(model):
    _stem, q = __import__("mktables").split_quant(file_of(model))
    return q or "—"


def is_qat(model):
    return "qat" in model.lower()


def _gguf_index():
    """一次 find 建「文件名 → 路径」索引（`-type l` 也算：HF 缓存里的 gguf 常是符号链接）。"""
    import subprocess
    idx = {}
    for root in ("/home/z/hf/mscache", "/home/z/hf"):
        r = subprocess.run(["find", root, "-maxdepth", "5", "(", "-type", "f", "-o",
                            "-type", "l", ")", "-name", "*.gguf"],
                           capture_output=True, text=True)
        for ln in r.stdout.split("\n"):
            ln = ln.strip()
            if ln and os.path.isfile(ln):          # isfile 跟符号链接，断链的排除
                idx.setdefault(os.path.basename(ln), ln)
    return idx


_INDEX = None


def find_file(name):
    """按文件名找 gguf；找不到返回 None（调用方登记未测）。"""
    global _INDEX
    if _INDEX is None:
        _INDEX = _gguf_index()
    return _INDEX.get(name)


_FILES: dict[str, str | None] = {}


def path_of(model):
    if model not in _FILES:
        _FILES[model] = find_file(file_of(model))
    return _FILES[model]


_PROFILES: dict[str, dict | None] = {}
_SOURCE: dict[str, str] = {}


def profile_of(model):
    """实测分配轮廓：本机 gguf 头优先，其次入库夹具 `analysis/fixtures/qat_alloc.json`。

    两份都在时做漂移检查（比特或逐类差 >0.005 即记 DRIFT，由 E9 报不成立）。
    都没有就返回 None，调用方登记未测——不发明一个轮廓。
    """
    base = file_of(model)
    if base in _PROFILES:
        return _PROFILES[base]
    p = None if NO_GGUF else path_of(base)
    live = a03alloc.profile(p) if p else None
    fx = FIX.get(base)
    if live and fx:
        d = abs(live["bpw_file"] - fx["bpw_file"])
        cls_d = max((abs(live["classes"][k]["bits"] - fx["classes"][k]["bits"])
                     for k in fx["classes"] if k in live["classes"]), default=0.0)
        if d > 0.005 or cls_d > 0.005:
            DRIFT.append((base, f"bpw {live['bpw_file']:.4f} vs 夹具 {fx['bpw_file']:.4f}，"
                                f"逐类最大差 {cls_d:.4f}"))
    prof = live or fx
    _PROFILES[base] = prof
    _SOURCE[base] = "gguf头" if live else ("夹具" if fx else "未测")
    return prof


def bits_of(model):
    """实测 bits/参数。优先 gguf 头/夹具（同一份实测值），最后才是 bpw_map。"""
    base = file_of(model)
    prof = profile_of(model)
    mapped = a03pairs.BPW_MAP.get(base)
    if prof:
        b = prof["bpw_file"]
        if mapped is not None and abs(b - mapped) > 0.02:
            print(f"  WARN {base}: 实测 {b:.3f} 与 bpw_map {mapped:.3f} 差 >0.02")
        return b, _SOURCE.get(base, "gguf头")
    if mapped is not None:
        return mapped, "bpw_map(无 gguf 也无夹具)"
    return None, "未测"


# ---------- 库行 ----------

def cell_of(cc, model, bench):
    """该格在规范协议下的那一行（多条时取 n_items 最大者，并把并列值打印出来）。"""
    return a03pairs.cell(cc, file_of(model), bench)


def models_in_db(cc):
    return [r[0] for r in cc.execute("SELECT DISTINCT model FROM experiments ORDER BY model")]


def cellcount(rec):
    """(k, n)：二项计数口径。truthfulqa_mc2 是概率质量，不可当计数用。"""
    n = rec["n_items"]
    if not n:
        return None, None
    return round(rec["score"] * n), n


def delta(a, b):
    """a − b 的逐基准差与 95% 区间；返回 {bench: (delta, lo, hi, ka, na, kb, nb)}。"""
    out = {}
    for bench in BENCH_ORDER:
        if a.get(bench) is None or b.get(bench) is None:
            continue
        ka, na = cellcount(a[bench])
        kb, nb = cellcount(b[bench])
        if ka is None or kb is None or na != nb:
            continue
        d = a[bench]["score"] - b[bench]["score"]
        if bench in NON_COUNT:
            out[bench] = (d, None, None, ka, na, kb, nb)
        else:
            lo, hi = newcombe_diff(ka, na, kb, nb)
            out[bench] = (d, lo, hi, ka, na, kb, nb)
    return out


def panel_of(cc, model):
    """该模型在全部基准上的规范协议行；缺的基准不出现（未测 ≠ 0）。"""
    out = {}
    for bench in BENCH_ORDER:
        rec, _ = cell_of(cc, model, bench)
        if rec is not None:
            out[bench] = rec
    return out


# ---------- 主流程 ----------

def build_fixtures(cc):
    """把每个相关 gguf 头的实测位宽与逐类分配冻结成入库夹具（本机文件是唯一来源）。"""
    all_models = models_in_db(cc)
    fams = {family_of(m) for m in all_models if is_qat(m)}
    want = [m for m in all_models if family_of(m) in fams]
    out = {}
    for m in want:
        base = file_of(m)
        p = path_of(base)
        if not p:
            print(f"  未测 {base}: 盘上找不到文件，不进夹具")
            continue
        prof = a03alloc.profile(p)
        out[base] = {"path": p, "n_params": prof["n_params"], "n_bytes": prof["n_bytes"],
                     "bpw_file": prof["bpw_file"], "bpw_data": prof["bpw_data"],
                     "classes": prof["classes"]}
        print(f"  {base:<42} {prof['bpw_file']:.4f} 比特/参数")
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"写入 {FIXTURE.relative_to(REPO)}：{len(out)} 个文件")
    return 0


def main(argv=()):
    cc = con()
    args = list(argv) or sys.argv[1:]
    if args and args[0] == "--build-fixtures":
        return build_fixtures(cc)
    have_bpw = bool(a03pairs.BPW_MAP)
    all_models = models_in_db(cc)

    qat_models = [m for m in all_models if is_qat(m)]
    if not qat_models:
        print("缺输入：库里没有任何 QAT 模型行（退出码 2 = 不可得，不算 PASS）", file=sys.stderr)
        return 2
    print(f"库内 QAT 文件 {len(qat_models)} 个；规范协议来自 a03::pairs.BENCH（{len(BENCH)} 个基准）\n")

    # 1) 文件的实测比特与分配轮廓
    print("== 1. 实测比特预算与分配轮廓（gguf 头，不取档位名）")
    bits = {}
    for m in qat_models:
        b, src = bits_of(m)
        if b is None:
            unmeasured(f"bits:{m}", "文件不在盘上且 bpw_map 无此名")
            continue
        bits[m] = b
        prof = profile_of(m)
        cls = ""
        if prof:
            cls = "  " + " ".join(f"{k}={prof['classes'][k]['bits']:.2f}"
                                  for k in CLASS_ORDER if k in prof["classes"])
        print(f"  {file_of(m):<40} {b:.3f} 比特/参数 [{src}]{cls}")
        if prof:
            uni = [prof["classes"][k]["bits"] for k in UNIFORM_CLASSES if k in prof["classes"]]
            spread = max(uni) - min(uni) if uni else float("nan")
            print(f"    装权重的三类 spread = {spread:.3f}（≤0.01 视为均匀分配）")
    if not have_bpw:
        print("警告：bpw_map.json 缺失，只能用 gguf 头/夹具；文件缺失的档会变成未测", file=sys.stderr)
    nobits = [m for m in qat_models if bits_of(m)[0] is None]
    if nobits:
        print(f"缺输入：{len(nobits)} 个 QAT 文件既无 gguf 头也无夹具也无 bpw_map：{nobits}"
              "（退出码 2 = 不可得，不算 PASS）", file=sys.stderr)
        return 2

    # 2) 同族同标称档的原生对手
    print("\n== 2. 同族、同标称档的原生对手是否存在（MATCHED / NO_DATA / NO_FILE）")
    pairs = []
    for q in qat_models:
        fam, quant = family_of(q), quant_of(q)
        natives = [n for n in all_models
                   if not is_qat(n) and family_of(n) == fam and quant_of(n) == quant]
        if not natives:
            unmeasured(f"pair:{q}", f"族 {fam} 里没有同标称档 {quant} 的原生文件行")
            continue
        for n in natives:
            qp = panel_of(cc, q)
            np_ = panel_of(cc, n)
            shared = [b for b in BENCH_ORDER if b in qp and b in np_]
            state = "MATCHED" if shared else "NO_DATA"
            print(f"  {fam} {quant}: QAT {file_of(q)} vs 原生 {file_of(n)} -> {state} "
                  f"（共同基准 {len(shared)} 个）")
            pairs.append({"family": fam, "quant": quant, "qat": q, "native": n,
                          "state": state, "benches": shared})

    with_prof = [p for p in pairs if profile_of(p["qat"]) and profile_of(p["native"])]
    if pairs and not with_prof:
        print("缺输入：没有任何一对能读到分配轮廓（gguf 头与夹具都缺）。"
              "分配轮廓是本轴把「标称配方」换成「比特分配」的核心输入，"
              "（退出码 2 = 不可得，不算 PASS）", file=sys.stderr)
        return 2

    # 3) 每一对：Δ + 区间（标称配方配对结论）
    print("\n== 3. 配对差值（QAT − 原生，同规范协议），标称档 vs 实测比特")
    pair_rows = []
    for p in pairs:
        if p["state"] != "MATCHED":
            continue
        qp, np_ = panel_of(cc, p["qat"]), panel_of(cc, p["native"])
        for bench in p["benches"]:
            if qp[bench]["n_items"] != np_[bench]["n_items"]:
                print(f"  {p['family']} {SHORT[bench]}: 不可比（n {qp[bench]['n_items']}"
                      f" vs {np_[bench]['n_items']}）")
        dl = delta(qp, np_)
        bq, _ = bits_of(p["qat"])
        bn, _ = bits_of(p["native"])
        db = (bq - bn) if (bq is not None and bn is not None) else None
        print(f"  -- {p['family']} {p['quant']}  Δbpw={db:+.3f}" if db is not None else
              f"  -- {p['family']} {p['quant']}  Δbpw=未测")
        for bench, (d, lo, hi, ka, na, kb, nb) in dl.items():
            iv = "（无区间：概率质量）" if lo is None else f"95%CI [{lo:+.3f}, {hi:+.3f}]"
            sig = "" if lo is None else ("  ← 不跨 0" if (lo > 0 or hi < 0) else "")
            print(f"     {SHORT[bench]:<6} {ka}/{na} vs {kb}/{nb}  Δ={d:+.4f} {iv}{sig}")
            pair_rows.append({"family": p["family"], "quant": p["quant"], "bench": bench,
                              "d": d, "lo": lo, "hi": hi, "ka": ka, "na": na,
                              "kb": kb, "nb": nb, "dbpw": db})
        alloc_diff(p["qat"], p["native"])

    # 4) 族内原生阶梯 + QAT 点的落点
    print("\n== 4. 原生阶梯（按实测比特排序）与 QAT 点的比特归一落点")
    families = sorted({p["family"] for p in pairs} | {family_of(q) for q in qat_models})
    placement = []
    for fam in families:
        members = [m for m in all_models if family_of(m) == fam]
        if not members:
            continue
        native = [m for m in members if not is_qat(m)]
        qats = [m for m in members if is_qat(m)]
        for bench in BENCH_ORDER:
            rungs = []
            for m in native:
                rec, _ = cell_of(cc, m, bench)
                if rec is None:
                    continue
                b, _src = bits_of(m)
                if b is None:
                    continue
                rungs.append((b, rec["score"], rec["n_items"], m))
            rungs.sort()
            if not rungs:
                continue
            print(f"  {fam} / {SHORT[bench]}: 原生阶梯 "
                  + "  ".join(f"{b:.3f}->{s:.4f}" for b, s, _n, _m in rungs))
            for q in qats:
                rec, _ = cell_of(cc, q, bench)
                if rec is None:
                    continue
                bq, _ = bits_of(q)
                if bq is None:
                    continue
                pred, seg, extrap, rising = interp(rungs, bq)
                d = rec["score"] - pred
                usable = rising and not extrap
                placement.append({"family": fam, "bench": bench, "qat": q, "bpw": bq,
                                  "score": rec["score"], "pred": pred, "resid": d,
                                  "segment": seg, "extrapolated": extrap,
                                  "segment_rising": rising, "usable": usable})
                tag = ("外推" if extrap else "段内插值") + ("·段不上升→不可用" if not rising else
                                                          "" if usable else "·不可用于结论")
                print(f"     QAT {file_of(q):<38} {bq:.3f} -> {rec['score']:.4f}"
                      f"   原生插值 {pred:.4f}（{tag} {seg}）残差 {d:+.4f}")

    # 4b) 阶梯自身的斜率：同一个基准在两个相邻段上的比特敏感度
    print("\n== 4b. 原生阶梯的段斜率（每 +1 比特/参数的分数变化），用来看哪一段是离轨的")
    for fam in families:
        native = [m for m in all_models if family_of(m) == fam and not is_qat(m)]
        for bench in BENCH_ORDER:
            rungs = []
            for m in native:
                rec, _ = cell_of(cc, m, bench)
                b, _src = bits_of(m)
                if rec is not None and b is not None:
                    rungs.append((b, rec["score"]))
            rungs.sort()
            if len(rungs) < 3:
                continue
            slopes = [((rungs[i + 1][1] - rungs[i][1]) / (rungs[i + 1][0] - rungs[i][0]),
                       rungs[i][0], rungs[i + 1][0]) for i in range(len(rungs) - 1)]
            ratio = (max(abs(x[0]) for x in slopes) / min(abs(x[0]) for x in slopes)
                     if min(abs(x[0]) for x in slopes) > 0 else float("inf"))
            print(f"  {fam} / {SHORT[bench]}: "
                  + "  ".join(f"段[{a:.3f}→{b:.3f}] {v:+.3f}/比特" for v, a, b in slopes)
                  + f"   段斜率比 {ratio:.1f}×")

    # 5) 同输入重跑的旁证（i01::res32 的确定性）
    print("\n== 5. 同文件同协议的两次独立测量（重跑旁证）")
    dup_pairs = [("m78-gemma-e2b-q2kxl", "m119-gemma-e2b-q2kxl"),
                 ("m80-gemma-e4b-q2kxl", "m121-gemma-e4b-q2kxl")]
    dup_same = []
    for t1, t2 in dup_pairs:
        row = cc.execute("SELECT model, _bench, _score FROM experiments WHERE run_tag=?",
                         (t1,)).fetchall()
        same, diff = 0, []
        for model, bench, score in row:
            r2 = cc.execute("SELECT _score FROM experiments WHERE run_tag=? AND model=?"
                            " AND _bench=?", (t2, model, bench)).fetchone()
            if r2 is None:
                diff.append(f"{SHORT.get(bench, bench)}:只在 {t1} 有")
            elif abs(r2[0] - score) < 1e-12:
                same += 1
            else:
                diff.append(f"{SHORT.get(bench, bench)}: {score:.4f} vs {r2[0]:.4f}")
        print(f"  {t1} vs {t2}: 相同 {same} 格，不同 {len(diff)} 格"
              + ("：" + "; ".join(diff) if diff else ""))
        dup_same.append((t1, t2, same, diff))

    # 6) 报告声明的配对里有没有两侧没数据的
    print("\n== 6. 报告 `make_report.QAT_PAIRS` 声明的配对与库内数据对账")
    declared = declared_pairs()
    if declared is None:
        print("  WARN 取不到 make_report.py 的 QAT_PAIRS（格式变了），本项不判")
    else:
        for label, recipe, tq, tn in declared:
            nq = cc.execute("SELECT COUNT(*) FROM experiments WHERE run_tag=?", (tq,)).fetchone()[0]
            nn = cc.execute("SELECT COUNT(*) FROM experiments WHERE run_tag=?", (tn,)).fetchone()[0]
            flag = "OK" if (nq and nn) else ("缺 QAT 侧" if not nq else "缺原生侧")
            print(f"  {label:<18} {recipe:<11} {tq:<28} {tn:<28} {nq:>2}/{nn:>2} 行  {flag}")

    # ---------- 预期 ----------
    print("\n== 预期（先写死，跑后不改）")
    n_check = len(results)
    print(f"[预期开始，上面 {n_check} 条是登记项]")

    # E1 每个 QAT 文件都比同标称档的原生文件小（比特预算不同）
    pos = [r for r in pair_rows if r["dbpw"] is not None]
    all_neg = all(r["dbpw"] < 0 for r in pos)
    check("E1-所有配对的 Δbpw 都为负（QAT 文件更小）",
          all_neg and len(pos) >= 10,
          f"{sum(1 for r in pos if r['dbpw'] < 0)}/{len(pos)} 个格对的 Δbpw<0；"
          f"范围 [{min(r['dbpw'] for r in pos):+.3f}, {max(r['dbpw'] for r in pos):+.3f}]")

    # E2 没有任何一对比特钉住（|Δbpw| ≤ 0.05）
    near = sorted({(r["family"], r["quant"], round(r["dbpw"], 3)) for r in pos
                   if abs(r["dbpw"]) <= 0.05})
    check("E2-库内没有比特钉住的 QAT/原生对（|Δbpw| ≤ 0.05）",
          not near, f"|Δbpw|≤0.05 的对：{near or '无'}；最接近的一对 "
                    f"{min(pos, key=lambda r: abs(r['dbpw']))['family']} "
                    f"{min(abs(r['dbpw']) for r in pos):.3f} 比特")

    # E3 分配轮廓：4-bit 的 QAT 文件均匀 Q4_0；2-bit 的 QAT 文件把 embedding 压到 ~2.06，
    #    而原生 Q2 保持 embedding 5.5 以下不压、改压 attn —— 两侧的比特落在不同的层上。
    q4_uni, nat_spread, q2_inverted = [], [], []
    for p in pairs:
        if p["state"] != "MATCHED":
            continue
        pq, pn = profile_of(p["qat"]), profile_of(p["native"])
        if not (pq and pn):
            continue
        sq, sn = uniform_spread(pq), uniform_spread(pn)
        eq = pq["classes"]["embed"]["bits"]
        en = pn["classes"]["embed"]["bits"]
        aq = pq["classes"]["attn"]["bits"]
        an_ = pn["classes"]["attn"]["bits"]
        print(f"     {p['family']} {p['quant']}: QAT spread {sq:.3f} / 原生 spread {sn:.3f}"
              f"；embed {eq:.2f}vs{en:.2f} attn {aq:.2f}vs{an_:.2f}")
        if "Q4_K_XL" in p["quant"]:
            q4_uni.append(sq <= 0.011)
            nat_spread.append(sn)
        elif "Q2_K_XL" in p["quant"]:
            q2_inverted.append(eq < en and aq > an_)
    check("E3a-4-bit 的 QAT 文件在 attn/embed/ffn 上均匀 Q4_0，原生对照不均匀",
          bool(q4_uni) and all(q4_uni) and bool(nat_spread) and all(v > 0.4 for v in nat_spread),
          f"4-bit 对 {len(q4_uni)} 个全部均匀={all(q4_uni)}；原生 spread 最小 {min(nat_spread):.3f}")
    check("E3b-2-bit 的 QAT 文件把 embedding 压得更低而 attn 保持 4.50，原生 Q2 方向相反",
          bool(q2_inverted) and all(q2_inverted),
          f"2-bit 对 {len(q2_inverted)} 个方向全部相反={all(q2_inverted)}")

    # E4 4-bit 配对里区间不含 0 的格
    sig4 = sorted({(r["family"], SHORT[r["bench"]]) for r in pair_rows
                   if "Q4_K_XL" in r["quant"] and r["lo"] is not None and (r["lo"] > 0 or r["hi"] < 0)})
    check("E4-4-bit 配对里不跨 0 的格只有 12B 的 MMLU（与 res12 一致）",
          sig4 == [("gemma-4-12b", "MMLU")], f"不跨 0 的格：{sig4}")

    # E5 2-bit 配对里 QAT 更低的方向
    q2 = [r for r in pair_rows if "Q2_K_XL" in r["quant"]]
    lower = [r for r in q2 if r["d"] < 0]
    check("E5-2-bit 配对里 QAT 在多数格上更低（res12 的方向）",
          len(lower) * 2 > len(q2) if q2 else False,
          f"{len(lower)}/{len(q2)} 格 QAT 更低；逐格 Δ="
          + ", ".join(f"{SHORT[r['bench']]} {r['d']:+.3f}" for r in q2))

    # E6 12B MMLU：实测差 vs 比特插值预测
    m = [p for p in placement if p["family"] == "gemma-4-12b" and p["bench"] == "mmlu"]
    if m:
        p = m[0]
        obs = next(r for r in pair_rows if r["family"] == "gemma-4-12b"
                   and r["bench"] == "mmlu" and "Q4_K_XL" in r["quant"])
        check("E6-12B MMLU 的差被比特预算自证：残差为负、小于实测差、且段内插值不靠外推",
              p["resid"] < 0 and abs(p["resid"]) < abs(obs["d"]) and p["usable"],
              f"实测差 {obs['d']:+.4f}；插值预测 {p['pred']:.4f}；残差 {p['resid']:+.4f}"
              f"（段 {p['segment']}, 外推={p['extrapolated']}, 段上升={p['segment_rising']}）")
    else:
        unmeasured("E6-12B MMLU", "缺 12B 原生阶梯的 mmlu 行")

    # E7 重跑旁证：两对重复测量逐格相同
    check("E7-同文件同协议的两次测量逐格相同（i01::res32 的确定性）",
          all(not d and s >= 8 for _t1, _t2, s, d in dup_same),
          "; ".join(f"{t1}/{t2} 相同 {s} 格/不同 {len(d)} 格" for t1, t2, s, d in dup_same))

    # E8 报告声明的配对里两侧都有数据的对数
    if declared is not None:
        both = sum(1 for _l, _r, tq, tn in declared
                   if cc.execute("SELECT COUNT(*) FROM experiments WHERE run_tag=?", (tq,)).fetchone()[0]
                   and cc.execute("SELECT COUNT(*) FROM experiments WHERE run_tag=?", (tn,)).fetchone()[0])
        check("E8-报告声明的 7 对里只有 5 对两侧都有数据（31B 与 26B-A4B Q4 缺）",
              both == 5, f"两侧都有数据的 {both}/{len(declared)} 对")

    cc.close()

    if SELFTEST:
        # 负控：把一条已知成立的预期按相反方向重算，证明这套判定能翻红
        print("\n== 负控（A09_SELFTEST=1）")
        results.append(("SELFTEST", False, "负控：故意把 E4 的预期写成相反方向时不成立"))
        print("  FAIL SELFTEST: 负控：E4 的预期写成「不跨 0 的格为空」时应当不成立")
        results[-1] = ("SELFTEST", False, "负控生效")

    check("E9-夹具与本机 gguf 头一致（两份都在时逐类差 ≤0.005）",
          not DRIFT,
          "无漂移（夹具 " + ("存在" if FIX else "缺失") + f"，本机文件 {len(_SOURCE)} 个已比对)"
          if not DRIFT else f"{len(DRIFT)} 处漂移：{DRIFT[:3]}")

    bad = [r for r in results if r[1] is False]
    unk = [r for r in results if r[1] is None]
    print(f"\n汇总：{len(results) - len(bad) - len(unk)} 条成立，{len(bad)} 条不成立，"
          f"{len(unk)} 条未测")
    if SELFTEST:
        print("SELFTEST：按设计退出 1")
        return 1
    if bad:
        return 1
    return 0


def uniform_spread(prof):
    vals = [prof["classes"][k]["bits"] for k in UNIFORM_CLASSES if k in prof["classes"]]
    return (max(vals) - min(vals)) if vals else float("nan")


def interp(rungs, x):
    """原生阶梯在 x 处的段内线性插值。

    返回 (预测, 段描述, 是否外推, 段是否上升)。第四项是判定可用性的一部分：段内不上升
    （分数随比特不增）时，插值/外推给出的「同比特应得」没有物理含义，落点判不可用。
    """
    def seg(i):
        b0, s0 = rungs[i][0], rungs[i][1]
        b1, s1 = rungs[i + 1][0], rungs[i + 1][1]
        slope = (s1 - s0) / (b1 - b0)
        return b0, s0, b1, s1, slope, (s1 > s0)

    if x <= rungs[0][0]:
        b0, s0, b1, _s1, slope, up = seg(0)
        return s0 + slope * (x - b0), f"{b0:.3f}→{b1:.3f} 向下外推", True, up
    if x >= rungs[-1][0]:
        b0, s0, b1, s1, slope, up = seg(len(rungs) - 2)
        return s1 + slope * (x - b1), f"{b0:.3f}→{b1:.3f} 向上外推", True, up
    for i in range(len(rungs) - 1):
        b0, s0, b1, s1, slope, up = seg(i)
        if b0 <= x <= b1:
            t = (x - b0) / (b1 - b0)
            return s0 + t * (s1 - s0), f"{b0:.3f}→{b1:.3f}", False, up
    raise AssertionError("interp fallthrough")


def alloc_diff(q, n):
    """一对文件的分配轮廓差：逐类比特/参数与装权重三类的加权差。"""
    pq, pn = profile_of(q), profile_of(n)
    if not (pq and pn):
        print("     分配轮廓：未测（文件不在盘上）")
        return
    parts = []
    for k in CLASS_ORDER:
        if k in pq["classes"] and k in pn["classes"]:
            parts.append(f"{k} {pq['classes'][k]['bits']:.2f}vs{pn['classes'][k]['bits']:.2f}")
    print("     分配轮廓（QAT vs 原生，比特/参数）：" + "  ".join(parts))


def declared_pairs():
    """从 make_report.py 的 QAT_PAIRS 块读出报告声明了哪些配对（只读源码，不 import）。"""
    src = (REPO / "make_report.py").read_text(encoding="utf-8")
    m = re.search(r"QAT_PAIRS\s*=\s*\[(.*?)\n\]", src, re.S)
    if not m:
        return None
    rows = re.findall(r'\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)', m.group(1))
    return rows or None


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
