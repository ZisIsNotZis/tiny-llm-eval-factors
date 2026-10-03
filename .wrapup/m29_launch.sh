#!/bin/bash
# Launcher: wait for m24 to finish, then run m29 under the GPU lock.
while pgrep -f "[r]un_m24.sh" >/dev/null 2>&1; do sleep 30; done
exec bash /home/z/hf/research/.wrapup/gpu_locked.sh bash /home/z/hf/research/.wrapup/run_m29.sh
