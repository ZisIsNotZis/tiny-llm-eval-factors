#!/bin/bash
# B1 recon: re-download Ternary-Bonsai-27B-Q2_0.gguf from ModelScope to a FRESH dir and
# compare sha256 to the on-disk copy, to test the "truncated download" hypothesis.
set -u
MS=/home/z/hf/research/.wrapup/msenv/bin/modelscope
DST=/home/z/hf/research/.wrapup/bonsai_redl
LOG=/home/z/hf/research/.wrapup/bonsai_redl.log
echo "[$(date +%H:%M:%S)] START redownload" >> "$LOG"
$MS download --model prism-ml/Ternary-Bonsai-27B-gguf Ternary-Bonsai-27B-Q2_0.gguf --local_dir "$DST" >> "$LOG" 2>&1
NEW=$(find "$DST" -name Ternary-Bonsai-27B-Q2_0.gguf | head -1)
OLD=/home/z/hf/models--prism-ml--Ternary-Bonsai-27B-gguf/blobs/868c11714cf8fe47f5ec9eeb2be0ab1a337112886f92ee0ede6b855c4fa31757
echo "[$(date +%H:%M:%S)] size new=$(stat -c%s "$NEW" 2>/dev/null) old=$(stat -c%s "$OLD" 2>/dev/null)" >> "$LOG"
echo "[$(date +%H:%M:%S)] sha new=$(sha256sum "$NEW" 2>/dev/null | cut -d' ' -f1)" >> "$LOG"
echo "[$(date +%H:%M:%S)] sha old=$(sha256sum "$OLD" 2>/dev/null | cut -d' ' -f1)" >> "$LOG"
echo "[$(date +%H:%M:%S)] DONE" >> "$LOG"
