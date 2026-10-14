#!/usr/bin/env python3
"""Three-axis readout for the AXES campaign (QAT, GSQ-RCO, DiffusionGemma).

Reads ONLY canonical-protocol rows from experiments.sqlite (the same benchmark/protocol
table bpw_sensitivity.py uses) for the AXES tags and prints the paired comparisons the
axes are built on:

  1.6 QAT     gemma-4-<size>-it-qat-UD-Q?_K_XL  vs  same size native UD-Q?_K_XL.  QAT is the
              only varied factor: size and the UD-Q?_K_XL recipe are held fixed.  The Q2
              native controls for E2B/E4B were already measured canonically (m119/m121), so
              they are reused rather than re-run.
  1.5 GSQ-RCO gemma-style GSQ-RCO quants vs the standard Qwen3.8-27B quants.  m91 (UD-Q2_K_XL)
              and m100 (UD-Q3_K_XL) were already measured; m152 (UD-IQ4_XS) is new.
  7   Diffusion  GATE-FAIL: no local llama.cpp runtime accepts the 'diffusion-gemma'
              architecture, so there is no diffusion-side number.  The autoregressive side is
              m145 (gemma-4-26B-A4B native UD-Q4_K_XL).  Reported as a gate failure, never as
              a value.

A cell absent from the DB prints `pending` (the campaign drains a model at a time); the script
never fabricates a number.  Run: python3 .wrapup/axes_analysis.py
"""
from __future__ import annotations

import sqlite3

DB = "experiments.sqlite"

# canonical (benchmark, protocol) cells -- mirrors bpw_sensitivity.BENCH
CANON = [
    ("humaneval-plus", "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mbpp-plus", "evalplus-0.3.1-openai-chat-greedy-plus"),
    ("mmlu", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("arc_challenge", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("truthfulqa_mc2", "lmeval-0.4.13-gguf-shim-reasoning-off"),
    ("gsm8k", "lmeval-0.4.13-chat-reasoning-off"),
    ("ifeval", "lmeval-0.4.13-chat-reasoning-off"),
]
BENCH = [b for b, _ in CANON]

# axis 1.6 -- (treatment tag, control tag, label); Y = the QAT bit is the only difference
QAT_PAIRS = [
    ("m140-qat-gemma12b-q4", "m141-native-gemma12b-q4", "gemma-4-12B-it  UD-Q4_K_XL"),
    ("m142-qat-gemma31b-q4", "m143-native-gemma31b-q4", "gemma-4-31B-it  UD-Q4_K_XL"),
    ("m144-qat-gemma26b-a4b-q4", "m145-native-gemma26b-a4b-q4", "gemma-4-26B-A4B-it UD-Q4_K_XL"),
    ("m147-qat-gemma-e2b-q4", "m148-native-gemma-e2b-q4", "gemma-4-E2B-it  UD-Q4_K_XL"),
    ("m146-qat-gemma-e2b-q2", "m119-gemma-e2b-q2kxl", "gemma-4-E2B-it  UD-Q2_K_XL"),
    ("m155-qat-gemma-e4b-q4", "m156-native-gemma-e4b-q4", "gemma-4-E4B-it  UD-Q4_K_XL"),
    ("m149-qat-gemma-e4b-q2", "m121-gemma-e4b-q2kxl", "gemma-4-E4B-it  UD-Q2_K_XL"),
]

# axis 1.5 -- GSQ-RCO treatments and the standard Qwen3.8-27B quant controls
GSQ_TAGS = [
    ("m150-qwen38-gsqrco-iq3xxs", "GSQ-RCO IQ3_XXS"),
    ("m151-qwen38-gsqrco-iq3s", "GSQ-RCO IQ3_S"),
    ("m91-qwen38-27b-q2kxl", "native UD-Q2_K_XL"),
    ("m100-qwen38-27b-q3kxl", "native UD-Q3_K_XL"),
    ("m152-qwen38-27b-iq4xs", "native UD-IQ4_XS"),
]


def load():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT run_tag,_bench,_score,protocol,reasoning FROM experiments "
        "WHERE protocol IS NOT NULL").fetchall()
    canon = set(CANON)
    data = {}
    for tag, bench, score, proto, reasoning in rows:
        if (bench, proto) not in canon or score is None:
            continue
        if bench == "gsm8k" and reasoning == "on":
            continue
        data.setdefault(tag, {})[bench] = score
    return data


def cell(data, tag, bench):
    v = data.get(tag, {}).get(bench)
    return f"{v:.4f}" if isinstance(v, (int, float)) else "pending"


def print_pair_table(data, pairs, title):
    print("\n" + "=" * 108)
    print(title)
    print("=" * 108)
    hdr = f"{'model':28s} " + " ".join(f"{b[:11]:>11s}" for b in BENCH)
    print(hdr)
    for treat, ctrl, label in pairs:
        # a pair with no control measured yet (e.g. m143/m145 still downloading) shows pending
        print(f"{label:28s} " + " ".join(
            f"{cell(data, ctrl, b):>11s}" for b in BENCH) + "  <- native")
        print(f"{'  ' + treat:28s} " + " ".join(
            f"{cell(data, treat, b):>11s}" for b in BENCH) + "  <- QAT")
        deltas = []
        for b in BENCH:
            t = data.get(treat, {}).get(b)
            c = data.get(ctrl, {}).get(b)
            deltas.append(f"{t - c:+.4f}" if isinstance(t, (int, float))
                          and isinstance(c, (int, float)) else "pending")
        print(f"{'  delta (qat-native)':28s} " + " ".join(f"{d:>11s}" for d in deltas))


def main():
    data = load()
    print_pair_table(data, QAT_PAIRS,
                     "AXIS 1.6  QAT vs NATIVE, same size + same UD-Q?_K_XL recipe "
                     "(positive = qat scores higher)")

    print("\n" + "=" * 108)
    print("AXIS 1.5  GSQ-RCO quantisation vs standard Qwen3.8-27B quants")
    print("=" * 108)
    print(f"{'quant':28s} " + " ".join(f"{b[:11]:>11s}" for b in BENCH))
    for tag, label in GSQ_TAGS:
        print(f"{label:28s} " + " ".join(
            f"{cell(data, tag, b):>11s}" for b in BENCH))
    print(f"\n{'note':28s} GSQ-RCO is not paired 1:1 with a native quant; the standard "
          "Q2/Q3/IQ4_XS rows bracket it in bpw.")

    print("\n" + "=" * 108)
    print("AXIS 7  DiffusionGemma vs same-size autoregressive gemma-4-26B-A4B")
    print("=" * 108)
    print("  treatment m154-diffusiongemma-26b-a4b-q4km: GATE-FAIL "
          "(runtime rejects architecture 'diffusion-gemma')")
    print("  control   m145-native-gemma26b-a4b-q4:       " + " ".join(
        f"{b}={cell(data, 'm145-native-gemma26b-a4b-q4', b)}" for b in BENCH))
    print("  -> no axis-7 comparison exists until a runtime supports the diffusion architecture.")


if __name__ == "__main__":
    main()
