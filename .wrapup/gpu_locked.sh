#!/bin/bash
# Serialise GPU use across parallel workers. Usage: bash gpu_locked.sh <cmd...>
exec flock -w 21600 /tmp/llama_gpu.lock "$@"
