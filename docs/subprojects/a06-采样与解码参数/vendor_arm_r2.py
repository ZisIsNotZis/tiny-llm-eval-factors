#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R2 of the a06 vendor arm: the three sampling-sensitive standard columns
(GSM8K, IFEval, and MMLU as a positive control), run through i02's
`variant_panel.py` with i02's `vendor-recommended` row only.

Why a wrapper instead of editing `.wrapup/variant_panel.py`: that file is i02's.
This keeps the panel's code untouched and still runs one arm, which is what the
GPU budget buys.  The panel takes the GPU flock itself (`fcntl.flock` on
`/tmp/llama_gpu.lock`), so this must be launched directly, not under
`gpu_locked.sh` -- a second flock on the same lock would make the panel abort.

Run from the repository root:

    python3 "docs/subprojects/a06-采样与解码参数/vendor_arm_r2.py" --model /home/z/hf/Qwen3.5-2B-UD-Q3_K_XL.gguf --tag m165-vendor

Exit status: the panel's own (0 ok, 3 lock held), plus 2 when the vendor arm is
not present in the panel's AXES (i02's arm not merged, or renamed).
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
PANEL = os.path.join(ROOT, ".wrapup", "variant_panel.py")
ARM = "vendor-recommended"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", default="m165-vendor")
    ap.add_argument("--limit", default="50")
    args = ap.parse_args(argv)

    if not os.path.exists(PANEL):
        print(f"UNMEASURED: no panel script at {PANEL}", file=sys.stderr)
        return 2
    spec = importlib.util.spec_from_file_location("variant_panel", PANEL)
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)

    rows = [r for r in vp.AXES["sampling"] if r[0] == ARM]
    if not rows:
        print(f"UNMEASURED: {ARM} is not in AXES['sampling'] -- i02's arm is not "
              f"merged or was renamed; refusing to run a different question",
              file=sys.stderr)
        return 2
    print(f"running only {ARM}: sampling={rows[0][2]}", flush=True)
    vp.AXES["sampling"] = rows

    sys.argv = ["variant_panel.py", "--model", args.model, "--tag", args.tag,
                "--axis", "sampling", "--limit", args.limit]
    return vp.main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
