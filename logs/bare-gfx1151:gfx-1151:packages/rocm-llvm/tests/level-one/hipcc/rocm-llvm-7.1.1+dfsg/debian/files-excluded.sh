#!/usr/bin/env bash

# This script lists the files to be excluded except the "amd" directory from upstream source

# Usage: ./debian/files-excluded.sh path/to/upstream/llvm-project
find $1 -mindepth 1 -maxdepth 1 \( ! -name "amd" \) | sed "s|^$1/||" | sort

