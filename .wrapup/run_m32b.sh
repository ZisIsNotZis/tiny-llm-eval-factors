#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# m32b — repaired Ternary-Bonsai-27B BFCL multi-turn panel (QUEUE #6).
#
# Thin entry point so the corrected re-run does not clobber `run_m32.sh`, which
# QUEUE.md (#6) and the concurrent QUEUE_DRIVER workstream still reference. The
# implementation is the single shared script; this only redirects its log to
# m32b.log. See run_m32.sh for the full diagnosis of the previous null.
#
# Runs the tool-call preflight first, then multi_turn_base and
# multi_turn_long_context. Summary: m32_summary.jsonl (unchanged shape).
#
# Must run under the GPU flock:
#   bash gpu_locked.sh bash run_m32b.sh
M32_LOG=${REPO_ROOT}/.wrapup/m32b.log exec bash ${REPO_ROOT}/.wrapup/run_m32.sh
