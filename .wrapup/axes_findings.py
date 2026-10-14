#!/usr/bin/env python3
"""Controlled-variable findings for the three NEW axes (1.6, 1.5, 7).

Reads ONLY canonical-protocol cells from experiments.sqlite (the same protocol table
bpw_sensitivity.py uses) and computes, per axis, per benchmark:

    delta = treatment - control           (score points)
    SE    = sqrt(p_t(1-p_t)/n_t + p_c(1-p_c)/n_c)     item-level (a benchmark item is a Bernoulli)
    CI    = delta +/- 1.96*SE

Axes
----
1.6 QAT vs native.  gemma-4-<size>-it-qat-UD-Q?_K_XL (treatment) vs the SAME size native
    UD-Q?_K_XL (control).  The nominal recipe is held fixed; effective bpw is NOT identical
    (QAT weights compress to fewer bytes), so bpw_t/bpw_c are printed next to every pair.
    Q2 natives for E2B/E4B were measured earlier (m119/m121) and reused, not re-run.

1.5 GSQ-RCO vs the standard Qwen3.8-27B quants.  The two GSQ-RCO quants sit between the
    native UD-Q2_K_XL / UD-Q3_K_XL ladder points in effective bpw, so the controlled
    comparison is (a) against the nearest native quant and (b) against the native score
    linearly interpolated to the GSQ quant's own bpw across the native ladder.

7   DiffusionGemma.  GATE-FAIL: no local llama.cpp runtime accepts 'diffusion-gemma', so
    there is no diffusion-side measurement.  Reported as a gate failure, never a value.

A cell absent from the DB prints `pending` (the campaign drains a model at a time); the
script never fabricates a number.  Emits human tables and .wrapup/axes_findings.json.
Run: python3 .wrapup/axes_findings.py
"""
from __future__ import annotations

import json
import math
import sqlite3

DB = "experiments.sqlite"
BPW = json.load(open(".wrapup/bpw_map.json"))
Z = 1.96

# canonical (benchmark, protocol) cells -- mirrors bpw_sensitivity.BENCH
CANON = {
    ("humaneval-plus", "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mbpp-plus", "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mmlu", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("arc_challenge", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("truthfulqa_mc2", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("gsm8k", "lmeval-0.4.13-chat-reasoning-off"),
    ("ifeval", "lmeval-0.4.13-chat-reasoning-off"),
}
BENCH = ["humaneval-plus", "mbpp-plus", "mmlu", "arc_challenge",
         "truthfulqa_mc2", "gsm8k", "ifeval"]

# axis 1.6 -- (treatment tag, control tag, label, nominal_recipe)
QAT_PAIRS = [
    ("m140-qat-gemma12b-q4", "m141-native-gemma12b-q4", "gemma-4-12B-it", "UD-Q4_K_XL"),
    ("m142-qat-gemma31b-q4", "m143-native-gemma31b-q4", "gemma-4-31B-it", "UD-Q4_K_XL"),
    ("m144-qat-gemma26b-a4b-q4", "m145-native-gemma26b-a4b-q4", "gemma-4-26B-A4B-it", "UD-Q4_K_XL"),
    ("m147-qat-gemma-e2b-q4", "m148-native-gemma-e2b-q4", "gemma-4-E2B-it", "UD-Q4_K_XL"),
    ("m146-qat-gemma-e2b-q2", "m119-gemma-e2b-q2kxl", "gemma-4-E2B-it", "UD-Q2_K_XL"),
    ("m155-qat-gemma-e4b-q4", "m156-native-gemma-e4b-q4", "gemma-4-E4B-it", "UD-Q4_K_XL"),
    ("m149-qat-gemma-e4b-q2", "m121-gemma-e4b-q2kxl", "gemma-4-E4B-it", "UD-Q2_K_XL"),
]

# axis 1.5 -- GSQ-RCO treatments and the standard Qwen3.8-27B quant ladder (controls)
GSQ_TAGS = [
    ("m150-qwen38-gsqrco-iq3xxs", "GSQ-RCO IQ3_XXS"),
    ("m151-qwen38-gsqrco-iq3s", "GSQ-RCO IQ3_S"),
]
NATIVE_TAGS = [
    ("m91-qwen38-27b-q2kxl", "native UD-Q2_K_XL"),
    ("m100-qwen38-27b-q3kxl", "native UD-Q3_K_XL"),
    ("m152-qwen38-27b-iq4xs", "native UD-IQ4_XS"),
]

# tag -> logical gguf basename (for bpw lookup); mirrors migrate_db.AXES_TAG_MODELS
TAG_MODEL = {
    "m140-qat-gemma12b-q4": "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
    "m141-native-gemma12b-q4": "gemma-4-12b-it-UD-Q4_K_XL.gguf",
    "m142-qat-gemma31b-q4": "gemma-4-31B-it-qat-UD-Q4_K_XL.gguf",
    "m143-native-gemma31b-q4": "gemma-4-31B-it-UD-Q4_K_XL.gguf",
    "m144-qat-gemma26b-a4b-q4": "gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf",
    "m145-native-gemma26b-a4b-q4": "gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf",
    "m146-qat-gemma-e2b-q2": "gemma-4-E2B-it-qat-UD-Q2_K_XL.gguf",
    "m147-qat-gemma-e2b-q4": "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf",
    "m148-native-gemma-e2b-q4": "gemma-4-E2B-it-UD-Q4_K_XL.gguf",
    "m149-qat-gemma-e4b-q2": "gemma-4-E4B-it-qat-UD-Q2_K_XL.gguf",
    "m150-qwen38-gsqrco-iq3xxs": "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf",
    "m151-qwen38-gsqrco-iq3s": "Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf",
    "m152-qwen38-27b-iq4xs": "Qwen3.8-27B-UD-IQ4_XS.gguf",
    "m155-qat-gemma-e4b-q4": "gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf",
    "m156-native-gemma-e4b-q4": "gemma-4-E4B-it-UD-Q4_K_XL.gguf",
}
# m119/m121 are already-canonical Q2 natives (not in AXES_TAG_MODELS)
TAG_MODEL["m119-gemma-e2b-q2kxl"] = "gemma-4-E2B-it-UD-Q2_K_XL.gguf"
TAG_MODEL["m121-gemma-e4b-q2kxl"] = "gemma-4-E4B-it-UD-Q2_K_XL.gguf"
TAG_MODEL["m91-qwen38-27b-q2kxl"] = "Qwen3.8-27B-UD-Q2_K_XL.gguf"
TAG_MODEL["m100-qwen38-27b-q3kxl"] = "Qwen3.8-27B-UD-Q3_K_XL.gguf"


def load():
    """tag -> bench -> (score, n_items) for canonical cells only."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT run_tag,_bench,_score,protocol,reasoning,n_items FROM experiments "
        "WHERE protocol IS NOT NULL AND run_tag IS NOT NULL").fetchall()
    data = {}
    for tag, bench, score, proto, reasoning, n in rows:
        if (bench, proto) not in CANON or score is None:
            continue
        if bench == "gsm8k" and reasoning == "on":
            continue
        data.setdefault(tag, {})[bench] = (score, n)
    return data


def cell(data, tag, bench):
    return data.get(tag, {}).get(bench)


def delta_ci(dt, dc):
    """Item-level delta with 95% CI.  None if either side is pending."""
    if dt is None or dc is None:
        return None
    pt, nt = dt
    pc, nc = dc
    d = pt - pc
    se = math.sqrt(pt * (1 - pt) / nt + pc * (1 - pc) / nc)
    return {"delta": d, "se": se, "ci_lo": d - Z * se, "ci_hi": d + Z * se,
            "n_t": nt, "n_c": nc}


def pool(deltas):
    """Inverse-variance pooled delta across pairs; None if no pair is complete."""
    ds = [x for x in deltas if x]
    if not ds:
        return None
    w = [1.0 / x["se"] ** 2 for x in ds]
    mean = sum(wi * x["delta"] for wi, x in zip(w, ds)) / sum(w)
    se = math.sqrt(1.0 / sum(w))
    return {"delta": mean, "se": se, "ci_lo": mean - Z * se, "ci_hi": mean + Z * se,
            "n_pairs": len(ds)}


def fmt(x, nd=4):
    return "pending" if x is None else f"{x:+.{nd}f}"


def axis_qat(data):
    print("=" * 112)
    print("AXIS 1.6  QAT vs NATIVE at the same nominal UD-Q?_K_XL recipe "
          "(delta = qat - native, +favours QAT)")
    print("=" * 112)
    out = {}
    per_pair = []
    for tt, ct, label, recipe in QAT_PAIRS:
        bt = BPW.get(TAG_MODEL.get(tt, ""))
        bc = BPW.get(TAG_MODEL.get(ct, ""))
        ds = {b: delta_ci(cell(data, tt, b), cell(data, ct, b)) for b in BENCH}
        complete = sum(1 for v in ds.values() if v)
        bpw_note = (f"bpw qat={bt:.3f} native={bc:.3f} (d={bt - bc:+.3f})"
                    if bt and bc else "bpw n/a")
        print(f"\n{label}  {recipe}   {bpw_note}   [{complete}/7 benches]")
        print(f"  {'bench':16s} {'qat-native':>11s} {'95% CI':>22s} {'n_t/n_c':>10s}")
        for b in BENCH:
            v = ds[b]
            if v:
                print(f"  {b:16s} {v['delta']:+11.4f} "
                      f"[{v['ci_lo']:+.4f},{v['ci_hi']:+.4f}] {v['n_t']:>4d}/{v['n_c']:<5d}")
            else:
                print(f"  {b:16s} {'pending':>11s}")
        per_pair.append({"label": label, "recipe": recipe, "tags": [tt, ct],
                         "bpw_qat": bt, "bpw_native": bc, "deltas": ds})

    print("\n" + "-" * 112)
    print("POOLED per benchmark (inverse-variance over complete pairs)")
    print("-" * 112)
    print(f"  {'bench':16s} {'mean delta':>11s} {'95% CI':>24s} {'pairs':>6s}")
    pooled = {}
    for b in BENCH:
        p = pool([pp["deltas"][b] for pp in per_pair])
        pooled[b] = p
        if p:
            print(f"  {b:16s} {p['delta']:+11.4f} "
                  f"[{p['ci_lo']:+.4f},{p['ci_hi']:+.4f}] {p['n_pairs']:>6d}")
        else:
            print(f"  {b:16s} {'pending':>11s}")
    out["pairs"] = [{"label": pp["label"], "recipe": pp["recipe"], "tags": pp["tags"],
                     "bpw_qat": pp["bpw_qat"], "bpw_native": pp["bpw_native"],
                     "deltas": {b: pp["deltas"][b] for b in BENCH}}
                    for pp in per_pair]
    out["pooled"] = pooled
    # Q4-only and Q2-only pooled verdicts
    q4 = [pp for pp in per_pair if pp["recipe"] == "UD-Q4_K_XL"]
    q2 = [pp for pp in per_pair if pp["recipe"] == "UD-Q2_K_XL"]
    for name, sub in (("UD-Q4_K_XL (5 pairs)", q4), ("UD-Q2_K_XL (2 pairs)", q2)):
        allp = [sub[i]["deltas"][b] for i in range(len(sub)) for b in BENCH]
        p = pool(allp)
        print(f"\n  overall {name}: pooled delta over all benchmark cells "
              + (f"{p['delta']:+.4f} [{p['ci_lo']:+.4f},{p['ci_hi']:+.4f}] "
                 f"(n={p['n_pairs']} cells)" if p else "pending"))
        out.setdefault("overall", {})[name] = p
    return out


def axis_gsq(data):
    print("\n" + "=" * 112)
    print("AXIS 1.5  GSQ-RCO vs the standard Qwen3.8-27B quant ladder "
          "(delta = gsq - native)")
    print("=" * 112)
    native = []
    for tag, label in NATIVE_TAGS:
        bpw = BPW.get(TAG_MODEL[tag])
        native.append((bpw, label, tag))
    native.sort()
    print("  native ladder: " + "  ".join(f"{lbl}@{bpw:.3f}" for bpw, lbl, _ in native))
    out = {"native_ladder": [{"label": lbl, "tag": tag, "bpw": bpw}
                             for bpw, lbl, tag in native], "quants": {}}
    for tag, label in GSQ_TAGS:
        gbpw = BPW.get(TAG_MODEL[tag])
        # nearest native by bpw
        near_bpw, near_lbl, near_tag = min(native, key=lambda x: abs(x[0] - gbpw))
        # bracketing natives for linear interpolation of the native score at gbpw
        lo = max((x for x in native if x[0] <= gbpw), default=None)
        hi = min((x for x in native if x[0] >= gbpw), default=None)
        print(f"\n{label}  effective bpw {gbpw:.3f}   nearest native {near_lbl}"
              f"@{near_bpw:.3f} (d={gbpw - near_bpw:+.3f})")
        if lo and hi and lo[0] != hi[0]:
            print(f"  interpolating native ladder between {lo[1]}@{lo[0]:.3f} "
                  f"and {hi[1]}@{hi[0]:.3f}")
        print(f"  {'bench':16s} {'gsq':>8s} {'near-native':>12s} "
              f"{'d(nearest)':>24s} {'d(interp)':>24s}")
        rows = {}
        for b in BENCH:
            g = cell(data, tag, b)
            c = cell(data, near_tag, b)
            if g is None or c is None:
                print(f"  {b:16s} {'pending':>8s}")
                rows[b] = None
                continue
            v = delta_ci(g, c)
            # interpolated native score at gbpw -> need n at the bracket for SE; use
            # the nearest native's n for the SE (the interpolated point has no own n)
            if lo and hi and lo[0] != hi[0]:
                sl = cell(data, lo[2], b)
                sh = cell(data, hi[2], b)
                if sl is None or sh is None:
                    v_int = None
                else:
                    frac = (gbpw - lo[0]) / (hi[0] - lo[0])
                    pred = sl[0] + frac * (sh[0] - sl[0])
                    d = g[0] - pred
                    se = math.sqrt(g[0] * (1 - g[0]) / g[1] + c[0] * (1 - c[0]) / c[1])
                    v_int = {"delta": d, "ci_lo": d - Z * se, "ci_hi": d + Z * se,
                             "se": se, "pred_native": pred}
            else:
                v_int = None
            print(f"  {b:16s} {g[0]:8.4f} {c[0]:12.4f} "
                  f"[{v['ci_lo']:+.4f},{v['ci_hi']:+.4f}] "
                  + (f"[{v_int['ci_lo']:+.4f},{v_int['ci_hi']:+.4f}]"
                     if v_int else f"{'n/a':>24s}"))
            rows[b] = {"gsq": g[0], "native_nearest": c[0], "nearest": v,
                       "interp": v_int, "bpw_gsq": gbpw, "bpw_native": near_bpw,
                       "nearest_label": near_lbl}
        out["quants"][label] = rows
    return out


def axis_diffusion(data):
    print("\n" + "=" * 112)
    print("AXIS 7  DiffusionGemma vs same-size autoregressive gemma-4-26B-A4B")
    print("=" * 112)
    print("  treatment m154-diffusiongemma-26b-a4b-q4km: GATE-FAIL -- no local llama.cpp")
    print("            runtime accepts architecture 'diffusion-gemma' (gate log)")
    ctrl = {b: cell(data, "m145-native-gemma26b-a4b-q4", b) for b in BENCH}
    print("  control   m145-native-gemma26b-a4b-q4 (autoregressive): "
          + "  ".join(f"{b}={ctrl[b][0]:.4f}" if ctrl[b] else f"{b}=pending" for b in BENCH))
    print("  -> no axis-7 comparison exists until a runtime supports the diffusion arch.")
    return {"treatment": "GATE-FAIL: diffusion-gemma architecture unsupported",
            "control": {b: (ctrl[b][0] if ctrl[b] else None) for b in BENCH}}


def main():
    data = load()
    res = {"axis_1_6_qat": axis_qat(data),
           "axis_1_5_gsq_rco": axis_gsq(data),
           "axis_7_diffusion": axis_diffusion(data)}
    json.dump(res, open(".wrapup/axes_findings.json", "w"), indent=1)
    print("\nwrote .wrapup/axes_findings.json")


if __name__ == "__main__":
    main()
