import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import WorkflowNotification
from accounts.notification_service import approved_admin_users, notify_users_after_commit
from bookings.models import Booking, BookingChargeSheet, BookingRequest
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
        "remarks": instance.remarks or "",
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


@receiver(pre_save, sender=BookingRequest)
def remember_booking_request_notification_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._notification_previous_state = None
        return
    instance._notification_previous_state = (
        BookingRequest.objects.filter(pk=instance.pk)
        .values("status", "is_deleted", "reviewed_at")
        .first()
    )


def booking_request_schedule_text(booking_request):
    arrival = timezone.localtime(booking_request.arrival_at).strftime("%d %b %Y, %I:%M %p")
    departure = timezone.localtime(booking_request.departure_at).strftime("%d %b %Y, %I:%M %p")
    return f"{arrival} to {departure}"


@receiver(post_save, sender=BookingRequest)
def booking_request_saved_notification(sender, instance, created, **kwargs):
    previous = getattr(instance, "_notification_previous_state", None)
    previous_status = previous.get("status") if previous else None
    previous_deleted = previous.get("is_deleted") if previous else False
    schedule = booking_request_schedule_text(instance)

    if instance.is_deleted and not previous_deleted:
        WorkflowNotification.objects.filter(
            category=WorkflowNotification.CATEGORY_BOOKING_REQUESTS,
            related_object_type="booking_request",
            related_object_id=instance.pk,
        ).delete()
        if instance.deleted_by_id and instance.deleted_by_id != instance.requester_id:
            notify_users_after_commit(
                [instance.requester],
                category=WorkflowNotification.CATEGORY_MY_REQUESTS,
                event_key=f"booking-request:{instance.pk}:deleted:{instance.deleted_at.isoformat() if instance.deleted_at else 'deleted'}",
                title="Booking request deleted",
                message=f"Your request for {instance.visitor_name or 'the visitor'} ({schedule}) was deleted. Remarks: {instance.delete_reason or 'No remarks provided.'}",
                target_view="myRequests",
                related_object_type="booking_request",
                related_object_id=instance.pk,
            )
        return

    submitted = created and instance.status == BookingRequest.STATUS_PENDING
    resubmitted = previous_status == BookingRequest.STATUS_CORRECTION_REQUIRED and instance.status == BookingRequest.STATUS_PENDING
    if submitted or resubmitted:
        action = "resubmitted" if resubmitted else "submitted"
        requester_name = instance.requester.get_full_name() or instance.requester.email or instance.requester.username
        marker = instance.requested_at.isoformat() if submitted and instance.requested_at else timezone.now().isoformat()
        notify_users_after_commit(
            approved_admin_users(),
            category=WorkflowNotification.CATEGORY_BOOKING_REQUESTS,
            event_key=f"booking-request:{instance.pk}:{action}:{marker}",
            title=f"Booking request {action}",
            message=f"{requester_name} {action} a request for {instance.visitor_name or 'a visitor'} ({schedule}).",
            target_view="bookingRequests",
            related_object_type="booking_request",
            related_object_id=instance.pk,
        )

    reviewed_statuses = {
        BookingRequest.STATUS_APPROVED: "approved",
        BookingRequest.STATUS_REJECTED: "rejected",
        BookingRequest.STATUS_CORRECTION_REQUIRED: "sent back for correction",
    }
    if instance.status != previous_status and instance.status in reviewed_statuses:
        marker = instance.reviewed_at.isoformat() if instance.reviewed_at else timezone.now().isoformat()
        status_text = reviewed_statuses[instance.status]
        notify_users_after_commit(
            [instance.requester],
            category=WorkflowNotification.CATEGORY_MY_REQUESTS,
            event_key=f"booking-request:{instance.pk}:{instance.status}:{marker}",
            title=f"Booking request {status_text}",
            message=f"Your request for {instance.visitor_name or 'the visitor'} ({schedule}) was {status_text}. Remarks: {instance.admin_remarks or 'No remarks provided.'}",
            target_view="myRequests",
            related_object_type="booking_request",
            related_object_id=instance.pk,
        )
