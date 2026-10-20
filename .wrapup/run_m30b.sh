#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# m30b — repaired KV-quant x INPUT-length grid (QUEUE #4).
#
# Thin entry point so the corrected re-run does not clobber `run_m30.sh`, which
# QUEUE.md (#4) and the concurrent QUEUE_DRIVER workstream still reference. The
# implementation is the single shared script; this only redirects its log to
# m30b.log. See run_m30.sh for why the previous grid was a null by construction
# (short prompts) and how the INPUT is now padded to the target context.
#
# Summary: m30_summary.jsonl (same shape, plus the `prompt_tokens` field).
#
# Must run under the GPU flock:
#   bash gpu_locked.sh bash run_m30b.sh
M30_LOG=${REPO_ROOT}/.wrapup/m30b.log exec bash ${REPO_ROOT}/.wrapup/run_m30.sh
