# Deployment

## Prerequisites

- Python 3.13
- MySQL 8+
- Redis 7+
- A reverse proxy providing HTTPS
- A dedicated `roombooking` operating-system user

## Install

```bash
python3.13 -m venv venv
./venv/bin/pip install --requirement requirements.txt
cp .env.example .env
./venv/bin/python manage.py migrate
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py check --deploy
```

Set every value in `.env` before starting production. Keep the Google service-account JSON outside the repository and grant the service user read access only when sheet synchronization is enabled.

Production and staging startup fail if `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, or `DB_PASSWORD` is missing. The Android release must be built with the matching HTTPS API endpoint:

```bash
./gradlew assembleRelease \
  -PROOM_BOOKING_API_BASE_URL=https://booking.internal.example/
```

## Staging Check

Use staging as a production-like environment with separate database, sheet, and secrets:

```bash
cp .env.staging.example .env
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py migrate --check
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py check --deploy
curl -fsS https://staging-booking.internal.example/health/
```

Run an Android smoke test against the staging HTTPS base URL before production:

- create booking
- edit booking
- delete booking
- retry create/delete with the same `Idempotency-Key`
- confirm rate-limit errors are visible to the app

## Services

Copy the files in `deployment/` to `/etc/systemd/system/`, adjusting paths and users if the application is not installed at `/opt/room-booking`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now room-booking-web.service
sudo systemctl enable --now room-booking-celery.service
sudo systemctl enable --now room-booking-expiry.timer
sudo systemctl enable --now room-booking-backup.timer
```

Gunicorn listens on `127.0.0.1:8000` by default. Proxy API traffic to that address and serve `staticfiles/` from the reverse proxy.

The expiry timer runs `manage.py expire_bookings` every minute. The command is transactional and idempotent, so retrying it is safe.

Google Sheet synchronization is handled by Celery through Redis. Booking create, update, and delete events enqueue `bookings.tasks.sync_google_sheet_calendar` after the database transaction commits. Keep `room-booking-celery.service` running alongside the web service, and set `CELERY_BROKER_URL` if Redis is not on `127.0.0.1:6379/0`.

## Reverse Proxy

Use `deployment/nginx-room-booking.conf` as the starting point for TLS termination. Replace `booking.internal.example` and certificate paths, then run `nginx -t` before reload.

The proxy forwards `X-Request-ID`; Django returns the same value in the response. This makes Android reports, API logs, and reverse-proxy logs joinable.

## Logging And Crash Reporting

Production and staging default to JSON logs on stdout/stderr for journald or container log collection. Set:

```bash
DJANGO_LOG_LEVEL=INFO
DJANGO_LOG_FORMAT=json
```

Set `SENTRY_DSN` to enable Sentry for Django and Celery crashes. Leave `SENTRY_TRACES_SAMPLE_RATE=0` unless you intentionally want performance tracing.

## Admin

Admin is disabled by default in production-like environments:

```bash
DJANGO_ADMIN_ENABLED=false
```

If you need it, enable it behind VPN or reverse-proxy access controls and use a non-default path:

```bash
DJANGO_ADMIN_ENABLED=true
DJANGO_ADMIN_PATH=private-admin-console/
```

Startup fails if admin is enabled at `/admin/` in staging or production.

## Backups

The backup timer writes compressed MySQL dumps to `BACKUP_DIR` and deletes old dumps after `BACKUP_RETENTION_DAYS`:

```bash
sudo systemctl start room-booking-backup.service
sudo journalctl -u room-booking-backup.service --no-pager
```

Manual backup:

```bash
ENV_FILE=/opt/room-booking/.env ./deployment/backup-mysql.sh
```

Restore requires an explicit confirmation prompt:

```bash
ENV_FILE=/opt/room-booking/.env ./deployment/restore-mysql.sh /var/backups/room-booking/room_booking_20260101T021500Z.sql.gz
```

## Release Check

```bash
./venv/bin/python manage.py test
./venv/bin/python manage.py migrate --check
./venv/bin/python manage.py check --deploy
```
