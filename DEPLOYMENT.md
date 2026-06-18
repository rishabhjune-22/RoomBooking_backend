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

Production startup fails if `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, or `DB_PASSWORD` is missing. The Android release must be built with the matching HTTPS API endpoint:

```bash
./gradlew assembleRelease \
  -PROOM_BOOKING_API_BASE_URL=https://booking.internal.example/
```

## Services

Copy the files in `deployment/` to `/etc/systemd/system/`, adjusting paths and users if the application is not installed at `/opt/room-booking`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now room-booking-web.service
sudo systemctl enable --now room-booking-celery.service
sudo systemctl enable --now room-booking-expiry.timer
```

Gunicorn listens on `127.0.0.1:8000` by default. Proxy API traffic to that address and serve `staticfiles/` from the reverse proxy.

The expiry timer runs `manage.py expire_bookings` every minute. The command is transactional and idempotent, so retrying it is safe.

Google Sheet synchronization is handled by Celery through Redis. Booking create, update, and delete events enqueue `bookings.tasks.sync_google_sheet_calendar` after the database transaction commits. Keep `room-booking-celery.service` running alongside the web service, and set `CELERY_BROKER_URL` if Redis is not on `127.0.0.1:6379/0`.

## Release Check

```bash
./venv/bin/python manage.py test
./venv/bin/python manage.py migrate --check
./venv/bin/python manage.py check --deploy
```
