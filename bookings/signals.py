import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from bookings.models import Booking, BookingChargeSheet
from bookings.services.google_sheet_sync import request_calendar_sync


logger = logging.getLogger(__name__)


def schedule_calendar_sync_after_commit():
    transaction.on_commit(request_calendar_sync)


@receiver(post_save, sender=Booking)
def booking_saved(sender, instance, **kwargs):
    defaults = {
        "requestor_name": instance.requestor_name or "",
        "guest_name": instance.visitor_name or "",
        "purpose_event": instance.purpose_of_visit or "",
        "room_charges_amount": instance.room_charges_amount or 0,
        "attender_charges_amount": instance.attender_charges_amount or 0,
        "budget_head_name": (
            instance.budget_head_name
            or instance.budget_head_department_name
            or instance.budget_head_project_code
            or instance.budget_head_value
            or ""
        ),
    }
    sheet_row, created = BookingChargeSheet.objects.get_or_create(
        booking=instance,
        defaults=defaults,
    )
    if not created:
        changed_fields = []
        for field_name, value in defaults.items():
            if getattr(sheet_row, field_name) != value:
                setattr(sheet_row, field_name, value)
                changed_fields.append(field_name)
        if changed_fields:
            sheet_row.save(update_fields=[*changed_fields, "updated_at"])
    schedule_calendar_sync_after_commit()


@receiver(post_delete, sender=Booking)
def booking_deleted(sender, instance, **kwargs):
    logger.info(
        "booking_delete_signal booking_id=%s visitor_name=%s",
        instance.id,
        instance.visitor_name,
    )
    schedule_calendar_sync_after_commit()
