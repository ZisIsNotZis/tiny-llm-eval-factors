#!/bin/bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根：脚本按自身位置定位，不再写死绝对路径
# axes_dl_mirror.sh -- fetch the missing NATIVE (non-QAT) gemma-4 UD-Q4_K_XL controls for
# the QAT axis (1.6) and the DiffusionGemma AR control (axis 7).
#
# Within-repo recipe: "download only missing files, verify byte sizes after download".
#
# Transport note: `hf download` was tried first (per task), but from this host
# huggingface.co resolves to a poisoned address and hf-mirror.com hangs, so the only
# working path for these repos is ModelScope -- the SAME path the study already used to
# acquire the native gemma files (.wrapup/dl_fam.sh).  Filenames + repo ids are identical
# on both hubs.  Expected byte sizes come from the HF API (verified against ModelScope).
#
# Detached + idempotent: retries each file until its size matches, then symlinks
# /home/z/hf/<name> and writes .wrapup/dl_ready/<name>.ready.
set -u
W=${REPO_ROOT}/.wrapup
MS=$W/msenv/bin/modelscope
DST=/home/z/hf/mscache/unsloth
H=/home/z/hf
LOG=$W/axes_dl.log
mkdir -p "$W/dl_ready" "$DST"
echo "=== axes_dl(mirror) start $(date -Is) ===" >> "$LOG"

# repo|file|expected_bytes
FILES=(
 "unsloth/gemma-4-E2B-it-GGUF|gemma-4-E2B-it-UD-Q4_K_XL.gguf|3184496736"
 "unsloth/gemma-4-E4B-it-GGUF|gemma-4-E4B-it-UD-Q4_K_XL.gguf|5126306944"
 "unsloth/gemma-4-12B-it-GGUF|gemma-4-12b-it-UD-Q4_K_XL.gguf|7366423360"
 "unsloth/gemma-4-26B-A4B-it-GGUF|gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf|17010980576"
 "unsloth/gemma-4-31B-it-GGUF|gemma-4-31B-it-UD-Q4_K_XL.gguf|18822970304"
)

dl_one() {  # repo file want
  local repo="$1" file="$2" want="$3" dir="$DST/${repo##*/}" got attempt src
  mkdir -p "$dir"
  for attempt in $(seq 1 8); do
    if [ -f "$dir/$file" ] && [ "$(stat -c%s "$dir/$file")" = "$want" ]; then
      ln -sfn "$dir/$file" "$H/$file"
      echo "$dir/$file" > "$W/dl_ready/$file.ready"
      echo "[$(date +%H:%M:%S)] OK $file size=$(stat -c%s "$dir/$file") (try $attempt)" >> "$LOG"
      return 0
    fi
    echo "[$(date +%H:%M:%S)] START $file (try $attempt)" >> "$LOG"
    $MS download --model "$repo" "$file" --local_dir "$dir" >> "$LOG" 2>&1
    # modelscope may nest the file under a snapshot dir; normalise to $dir/$file
    src=$(find "$dir" -name "$file" -size +1M -print -quit 2>/dev/null)
    if [ -n "$src" ] && [ "$src" != "$dir/$file" ]; then mv -f "$src" "$dir/$file" 2>/dev/null; fi
    got=$( [ -f "$dir/$file" ] && stat -c%s "$dir/$file" || echo 0 )
    echo "[$(date +%H:%M:%S)] try $attempt got=$got want=$want" >> "$LOG"
    [ "$got" = "$want" ] && continue
    sleep 15
  done
  got=$( [ -f "$dir/$file" ] && stat -c%s "$dir/$file" || echo 0 )
  echo "[$(date +%H:%M:%S)] FAIL $file got=$got want=$want" >> "$LOG"
  return 1
}

rc=0
for spec in "${FILES[@]}"; do
  IFS='|' read -r repo file want <<< "$spec"
  dl_one "$repo" "$file" "$want" || rc=1
done
echo "=== axes_dl(mirror) end rc=$rc $(date -Is) ===" >> "$LOG"
exit $rc
