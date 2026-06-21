#!/usr/bin/env bash
# Disaster-recovery drill: pull the latest production backup from S3, restore
# it into a scratch Postgres instance, and run sanity queries to confirm the
# dump is restorable end-to-end.
#
# Run on a schedule (weekly) — a backup that never gets restored is not a
# backup. If this script fails, page operator: the actual prod backup is
# probably broken too.
#
# Required env vars:
#   S3_BUCKET       - bucket where backup.sh wrote dumps
#   SCRATCH_DB_URL  - throwaway Postgres connection string the drill restores into
#   AWS_REGION      - AWS region (default us-east-1)
#
# Optional:
#   BACKUP_KEY      - explicit s3 key to restore (default = newest in backups/)
#   MIN_ROWS_USERS  - minimum expected row count in users table (default 1)

set -euo pipefail

: "${S3_BUCKET:?}"
: "${SCRATCH_DB_URL:?}"
: "${AWS_REGION:=us-east-1}"
: "${MIN_ROWS_USERS:=1}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TMPDIR=$(mktemp -d)
trap 'rm -rf "${TMPDIR}"' EXIT

if [[ -z "${BACKUP_KEY:-}" ]]; then
  BACKUP_KEY=$(
    aws s3api list-objects-v2 \
      --bucket "${S3_BUCKET}" \
      --prefix backups/ \
      --region "${AWS_REGION}" \
      --query 'reverse(sort_by(Contents,&LastModified))[0].Key' \
      --output text
  )
  if [[ -z "${BACKUP_KEY}" || "${BACKUP_KEY}" == "None" ]]; then
    echo "[${TIMESTAMP}] FAIL: no backups found in s3://${S3_BUCKET}/backups/" >&2
    exit 2
  fi
fi

echo "[${TIMESTAMP}] Drill: restoring s3://${S3_BUCKET}/${BACKUP_KEY}"

DUMP_GZ="${TMPDIR}/dump.gz"
DUMP="${TMPDIR}/dump.pgdump"

aws s3 cp \
  "s3://${S3_BUCKET}/${BACKUP_KEY}" \
  "${DUMP_GZ}" \
  --region "${AWS_REGION}"

gunzip -c "${DUMP_GZ}" > "${DUMP}"
echo "  Dump size: $(stat -c%s "${DUMP}" 2>/dev/null || stat -f%z "${DUMP}") bytes"

# Wipe scratch schema so the drill always starts from zero — a successful
# restore is meaningless if it just no-ops on top of existing data.
psql "${SCRATCH_DB_URL}" -v ON_ERROR_STOP=1 -c \
  "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

# pg_restore against the scratch DB. --no-owner / --no-privileges keep the
# restore independent of the prod role layout.
pg_restore \
  --dbname="${SCRATCH_DB_URL}" \
  --no-owner \
  --no-privileges \
  --clean --if-exists \
  --exit-on-error \
  --jobs=4 \
  "${DUMP}"

echo "  Restore completed — running sanity queries"

# Sanity: critical tables present, users table populated, RLS still on.
USERS_COUNT=$(psql "${SCRATCH_DB_URL}" -At -c "SELECT count(*) FROM public.users;")
BUSINESSES_COUNT=$(psql "${SCRATCH_DB_URL}" -At -c "SELECT count(*) FROM public.businesses;")
RLS_USERS=$(psql "${SCRATCH_DB_URL}" -At -c \
  "SELECT relrowsecurity FROM pg_class WHERE relname='users' AND relnamespace='public'::regnamespace;")

echo "  users rows:      ${USERS_COUNT}"
echo "  businesses rows: ${BUSINESSES_COUNT}"
echo "  users RLS on:    ${RLS_USERS}"

if [[ "${USERS_COUNT}" -lt "${MIN_ROWS_USERS}" ]]; then
  echo "FAIL: users table has fewer rows than MIN_ROWS_USERS (${USERS_COUNT} < ${MIN_ROWS_USERS})" >&2
  exit 3
fi

if [[ "${RLS_USERS}" != "t" ]]; then
  echo "FAIL: RLS not enabled on users after restore" >&2
  exit 4
fi

echo "[${TIMESTAMP}] PASS — backup ${BACKUP_KEY} restores cleanly"
