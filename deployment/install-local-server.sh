#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/opt/room-booking"
SERVICE_USER="roombooking"
SERVICE_GROUP="roombooking"
SERVER_IP="${SERVER_IP:-192.168.1.19}"
DB_PASSWORD="${DB_PASSWORD:-}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi

if [[ -z "${DB_PASSWORD}" ]]; then
    echo "Set DB_PASSWORD to the existing MySQL roomuser password before installing." >&2
    exit 1
fi

if ! getent passwd "${SERVICE_USER}" >/dev/null; then
    useradd --system --home "${INSTALL_DIR}" --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" "${INSTALL_DIR}"

rsync -a --delete \
    --exclude='.git/' \
    --exclude='.env' \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='roombooking-*.json' \
    --exclude='test_sheets.py' \
    --exclude='staticfiles/' \
    "${SOURCE_DIR}/" "${INSTALL_DIR}/"

python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --requirement "${INSTALL_DIR}/requirements.txt"

if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
    secret_key="$(openssl rand -base64 48 | tr -d '\n')"
    cat >"${INSTALL_DIR}/.env" <<EOF
DJANGO_ENVIRONMENT=production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=${secret_key}
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,${SERVER_IP}
DJANGO_CSRF_TRUSTED_ORIGINS=
DJANGO_SECURE_SSL_REDIRECT=false
DJANGO_SESSION_COOKIE_SECURE=false
DJANGO_CSRF_COOKIE_SECURE=false
DJANGO_SECURE_HSTS_SECONDS=0
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=false
DJANGO_SECURE_HSTS_PRELOAD=false

DB_NAME=room_booking
DB_USER=roomuser
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=127.0.0.1
DB_PORT=3306

GUNICORN_BIND=127.0.0.1:8000
GUNICORN_WORKERS=3
GUNICORN_TIMEOUT=30

CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=
CELERY_TASK_SOFT_TIME_LIMIT=240
CELERY_TASK_TIME_LIMIT=300
EOF
fi

chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_DIR}"
chmod 600 "${INSTALL_DIR}/.env"

set -a
source "${INSTALL_DIR}/.env"
set +a

runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/venv/bin/python" "${INSTALL_DIR}/manage.py" migrate
runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/venv/bin/python" "${INSTALL_DIR}/manage.py" collectstatic --noinput

install -m 644 "${INSTALL_DIR}/deployment/room-booking-web.service" /etc/systemd/system/
install -m 644 "${INSTALL_DIR}/deployment/room-booking-celery.service" /etc/systemd/system/
install -m 644 "${INSTALL_DIR}/deployment/room-booking-expiry.service" /etc/systemd/system/
install -m 644 "${INSTALL_DIR}/deployment/room-booking-expiry.timer" /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now room-booking-web.service
systemctl enable --now room-booking-celery.service
systemctl enable --now room-booking-expiry.timer

systemctl --no-pager --full status room-booking-web.service
systemctl --no-pager --full status room-booking-celery.service
systemctl --no-pager --full status room-booking-expiry.timer
