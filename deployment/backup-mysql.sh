#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/room-booking/.env}"

if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

: "${DB_NAME:?DB_NAME is required}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/room-booking}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

umask 077
mkdir -p "${BACKUP_DIR}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${BACKUP_DIR}/${DB_NAME}_${timestamp}.sql.gz"

MYSQL_PWD="${DB_PASSWORD}" mysqldump \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --user="${DB_USER}" \
    --no-tablespaces \
    --single-transaction \
    --quick \
    --routines \
    --triggers \
    --events \
    "${DB_NAME}" | gzip -c >"${backup_file}"

find "${BACKUP_DIR}" \
    -type f \
    -name "${DB_NAME}_*.sql.gz" \
    -mtime "+${BACKUP_RETENTION_DAYS}" \
    -delete

printf '%s\n' "${backup_file}"
