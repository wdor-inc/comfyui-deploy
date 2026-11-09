#!/bin/sh
set -eu
snapshot=$1
repo=$2
rev=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["comfyui"])' "$snapshot")
git -C "$repo" -c advice.detachedHead=false checkout -q "$rev"
