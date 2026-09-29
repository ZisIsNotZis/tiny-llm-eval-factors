#!/bin/bash
# Recreate ~/hf/<basename>.gguf symlinks pointing at the HF-cache snapshot files,
# which is the layout exp.py expects (HF_ROOT/<model>).
cd /home/z/hf
n=0; skip=0
while IFS= read -r f; do
  base=$(basename "$f")
  if [ -e "$base" ] || [ -L "$base" ]; then skip=$((skip+1)); continue; fi
  ln -s "$f" "$base" && n=$((n+1))
done < <(find "$PWD"/models--*/snapshots/*/ -maxdepth 1 -name "*.gguf" \( -type f -o -xtype f \) 2>/dev/null | sort)
echo "linked=$n skipped=$skip"
