#!/bin/sh
set -e

# Docker seeds a named volume's ownership from the image directory it covers.
# /app/data has no counterpart in the image history of already-deployed volumes,
# so the daemon created those mountpoints as root:root — and the app runs as
# appuser (uid 1000), which then can't create the SQLite file:
#   sqlite3.OperationalError: unable to open database file
#
# We start as root purely to repair that, then drop privileges. This runs on
# every boot, so volumes created before the fix are corrected in place; no
# `docker volume rm` needed.
for dir in \
    /app/data \
    /app/storage \
    /app/storage/crops \
    /app/storage/ocr_blocks \
    /app/storage/.cache \
    /app/storage/.cache/huggingface
do
    mkdir -p "$dir"
    chown appuser:appuser "$dir"
done

exec gosu appuser "$@"
