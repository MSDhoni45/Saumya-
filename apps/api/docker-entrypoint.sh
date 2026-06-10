#!/bin/sh
# Container entrypoint: optionally run DB migrations, then exec the service command.
#
# RUN_MIGRATIONS=1 is set only on the API service (compose + ECS task def) so
# a rolling deploy runs migrations once per deploy from the API containers —
# workers and beat skip straight to their command. The migration runner takes
# a Postgres advisory lock, so concurrent API containers are safe.
set -e

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    echo "[entrypoint] Running database migrations..."
    python -m app.db.migrate
    echo "[entrypoint] Migrations complete."
fi

exec "$@"
