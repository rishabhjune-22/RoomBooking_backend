#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
    echo "Usage: ENV_FILE=/opt/room-booking/.env $0 /path/to/backup.sql.gz" >&2
    exit 1
fi

backup_file="$1"
ENV_FILE="${ENV_FILE:-/opt/room-booking/.env}"

if [[ ! -r "${backup_file}" ]]; then
    echo "Backup file is not readable: ${backup_file}" >&2
    exit 1
fi

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

echo "This will replace data in ${DB_NAME} on ${DB_HOST}:${DB_PORT}."
read -r -p "Type RESTORE to continue: " confirmation

if [[ "${confirmation}" != "RESTORE" ]]; then
    echo "Restore cancelled." >&2
    exit 1
fi

gunzip -c "${backup_file}" | MYSQL_PWD="${DB_PASSWORD}" mysql \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --user="${DB_USER}" \
    "${DB_NAME}"
