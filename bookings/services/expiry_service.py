from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from bookings.services.google_sheet_sync import request_calendar_sync


def expire_due_bookings(now=None, batch_size=500):
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    cutoff = now or timezone.now()
    expired_count = 0

    while True:
        with transaction.atomic():
            bookings = list(
                Booking.objects
                .select_for_update()
                .select_related("room")
                .filter(
                    status=Booking.STATUS_ACTIVE,
                    departure_at__lt=cutoff,
                )
                .order_by("pk")[:batch_size]
            )

            if not bookings:
                break

            for booking in bookings:
                booking.status = Booking.STATUS_EXPIRED

            Booking.objects.bulk_update(bookings, ["status"])
            expired_count += len(bookings)

    if expired_count:
        transaction.on_commit(request_calendar_sync)

    return expired_count
