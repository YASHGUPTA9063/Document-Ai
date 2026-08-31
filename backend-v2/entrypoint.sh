#!/bin/sh
set -e

# One image, three roles. The role is whatever command was passed:
#   uvicorn main:app ...        the API
#   arq worker.WorkerSettings   the dispatcher
#   python workflow_worker.py   the Mistral Studio workflow worker
#
# Everything below is shared setup that has to happen as root before dropping
# to appuser.

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
    /app/storage/splits \
    /app/storage/.cache \
    /app/storage/.cache/huggingface
do
    mkdir -p "$dir"
    chown appuser:appuser "$dir"
done

# Alembic is the only thing that creates or alters schema — init_db() no longer
# emits DDL outside a local SQLite debug run. RUN_MIGRATIONS=false lets the
# dispatcher and workflow-worker skip it so three containers starting together
# don't race each other for the same lock; compose gives that job to the API.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] Applying database migrations..."
    gosu appuser alembic upgrade head
    echo "[entrypoint] Migrations applied."
else
    echo "[entrypoint] RUN_MIGRATIONS=false — skipping alembic."
fi

exec gosu appuser "$@"
