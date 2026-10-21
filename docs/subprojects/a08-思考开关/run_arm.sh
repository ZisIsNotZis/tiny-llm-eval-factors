#!/bin/bash
# a08 思考开关：一次调用 = 一条臂，锁等待有上限，等锁这件事本身要看得见。
#
# 为什么：2026-10-21 用 `bash .wrapup/gpu_locked.sh python3 run_thinking_arms.py` 一次串六条臂，
# 结果是 `flock -w 21600` 在 `a06` 的厂商臂后面静默排队 27 分钟 —— 没有输出、没有产物、
# 也没有反悔的机会，还挡住了后面的队列。所以：
#   * 锁等待上限默认 600 s，超时用 flock 的 `-E 75` 退出码辨认，并 exit 2 打印「没拿到锁」；
#   * 等锁前先打一行（含当前持锁 pid），拿到锁后的第一行输出来自 python 的
#     `[arm <tag>] starting server …`，所以日志里能读出「在等 / 已拿到 / 起服」三段；
#   * 每次只跑 --arm 指定的那一条臂，跑完立刻释放。
#
# 用法：
#   bash "docs/subprojects/a08-思考开关/run_arm.sh" --probe
#   bash "docs/subprojects/a08-思考开关/run_arm.sh" a08-gsm8k-off-4096
#   A08_LOCK_WAIT=1800 bash "docs/subprojects/a08-思考开关/run_arm.sh" a08-ifeval-on-25
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
WAIT="${A08_LOCK_WAIT:-600}"
LOCK=/tmp/llama_gpu.lock

# `--list` 不碰 GPU，不该去排锁
for a in "$@"; do
    if [ "$a" = "--list" ]; then
        cd "$REPO" || exit 2
        exec python3 "$HERE/run_thinking_arms.py" --list
    fi
done

# 排锁之前先证明前提存在：模型路径错的时候不该占着锁排队
if ! python3 "$HERE/run_thinking_arms.py" --check-model; then
    echo "[a08] $(date +%H:%M:%S) PREFLIGHT FAILED: 模型路径不存在，未排锁、未起服" >&2
    exit 1
fi
holders="$(fuser "$LOCK" 2>/dev/null | tr -d ' ')"
echo "[a08] $(date +%H:%M:%S) requesting $LOCK (max ${WAIT}s; holders: ${holders:-none})" >&2
cd "$REPO" || exit 2
flock -w "$WAIT" -E 75 "$LOCK" python3 "$HERE/run_thinking_arms.py" "$@"
rc=$?
if [ "$rc" -eq 75 ]; then
    echo "[a08] $(date +%H:%M:%S) LOCK TIMEOUT after ${WAIT}s (holders: ${holders:-none}) -- 没拿到锁，未起服" >&2
    exit 2
fi
echo "[a08] $(date +%H:%M:%S) arm done rc=$rc" >&2
exit "$rc"
