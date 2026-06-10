#!/usr/bin/env bash
# Daily database backup: pg_dump → gzip → S3 (30-day retention enforced by S3 lifecycle).
# Run as a scheduled ECS task or cron job on a bastion host.
#
# Required env vars:
#   DATABASE_URL  - PostgreSQL connection string (from Secrets Manager in ECS)
#   S3_BUCKET     - backup destination bucket
#   AWS_REGION    - AWS region
#
# The S3 bucket should have a lifecycle rule deleting objects after 30 days.

set -euo pipefail

: "${DATABASE_URL:?}"
: "${S3_BUCKET:?}"
: "${AWS_REGION:=us-east-1}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
FILENAME="whatsagent-db-${TIMESTAMP}.dump.gz"
TMPFILE="/tmp/${FILENAME}"

echo "[${TIMESTAMP}] Starting backup → s3://${S3_BUCKET}/backups/${FILENAME}"

pg_dump \
  --no-owner \
  --no-privileges \
  --format=custom \
  "${DATABASE_URL}" \
  | gzip -9 > "${TMPFILE}"

BYTES=$(stat -c%s "${TMPFILE}")
echo "  Dump size: ${BYTES} bytes"

aws s3 cp \
  "${TMPFILE}" \
  "s3://${S3_BUCKET}/backups/${FILENAME}" \
  --region "${AWS_REGION}" \
  --storage-class STANDARD_IA \
  --server-side-encryption AES256

rm -f "${TMPFILE}"
echo "  Done: s3://${S3_BUCKET}/backups/${FILENAME}"
