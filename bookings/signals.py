import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from bookings.models import Booking
from bookings.services.google_sheet_sync import request_calendar_sync


logger = logging.getLogger(__name__)


def schedule_calendar_sync_after_commit():
    transaction.on_commit(request_calendar_sync)


@receiver(post_save, sender=Booking)
def booking_saved(sender, instance, **kwargs):
    schedule_calendar_sync_after_commit()


@receiver(post_delete, sender=Booking)
def booking_deleted(sender, instance, **kwargs):
    logger.info(
        "booking_delete_signal booking_id=%s visitor_name=%s",
        instance.id,
        instance.visitor_name,
    )
    schedule_calendar_sync_after_commit()
