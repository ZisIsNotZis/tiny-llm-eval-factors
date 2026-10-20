#!/bin/bash
# i01 WP6 — slot-reproducibility adjudication for plan15's cell.
#
# Question: the same cell (`q38-27b-q3 py chat`, protocol mpl-chat-nothink-greedy-768)
# is recorded at 131/161 (m26, old postprocess), 139/161 (re-score of m26 samples
# with the fixed postprocess, RESULT.md::res20) and 145/161 (m161, fresh
# generation).  131->139 is explained by the scoring defect; the remaining
# 139->145 = 6 problems can only come from the generation side, with two candidate
# causes: (a) m161 used the rebuilt prompt set in .wrapup/prompts, m26 used the
# deleted /tmp/MultiPL-E/prompts; (b) both runs were multi-slot servers and greedy
# decoding across a batch is not guaranteed bit-reproducible.
#
# The deleted prompt set cannot be recovered, so this run separates the variable
# that is still controllable -- the number of server slots -- and leaves (a)
# recorded as unmeasurable unless every arm here is identical.
#
# Arms (pinned prompt set, chat, thinking off, greedy, 768 tokens, 2048 ctx per
# slot -- the protocol every recorded chat cell used):
#   np1  : one server started with -np 1, two independent generation passes
#   np4  : one server started with -np 4, two independent generation passes
#   np4b : a SECOND server started with -np 4, one pass (cross-instance check)
#
# The recorded cells ran without an explicit -np: this llama-server build defaults
# to -np auto and reported `n_slots = 4, n_ctx_slot = 2048`, which is why np4 is
# the production arm and why -c is scaled per arm (with an explicit -np, -c is the
# TOTAL; with auto it behaves as the per-slot size).
#
# Each arm takes the GPU flock for itself, through slot_repro_arm.sh, so a panel
# queued behind this subproject can start between two arms instead of waiting out
# the whole experiment.
#
# Run:  bash "docs/subprojects/i01-判分与基准有效性/audits/slot_repro_run.sh" [arms...]
# Adjudicate:  python3 "docs/subprojects/i01-判分与基准有效性/audits/slot_repro_compare.py"
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
cd "$REPO" || exit 1

ARMS=${*:-"np1 np4 np4b"}
LOCK="$REPO/.wrapup/gpu_locked.sh"
for arm in $ARMS; do
  echo "[i01-slot] === dispatching arm=$arm under the GPU flock $(date +%H:%M:%S) ==="
  bash "$LOCK" bash "$HERE/slot_repro_arm.sh" "$arm" || {
    rc=$?
    echo "[i01-slot] arm=$arm failed rc=$rc (a failed arm is unmeasured, not a pass)" >&2
    exit "$rc"
  }
done
echo "[i01-slot] all arms done $(date +%H:%M:%S)"
echo "[i01-slot] adjudicate: python3 \"docs/subprojects/i01-判分与基准有效性/audits/slot_repro_compare.py\""
