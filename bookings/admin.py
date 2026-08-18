from django.contrib import admin
from .models import (
    Booking,
    BookingChargeSheet,
    BookingEditHistory,
    BookingIdempotencyRecord,
    BookingRequest,
)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking_reference_number",
        "room",
        "visitor_name",
        "arrival_at",
        "departure_at",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "room",
        "arrival_at",
        "created_at",
    )

    search_fields = (
        "visitor_name",
        "visitor_mobile",
        "visitor_email",
        "budget_head_value",
        "budget_head_name",
        "budget_head_department_name",
        "budget_head_project_code",
        "requestor_name",
        "room__prefix",
        "room__number",
    )

    ordering = ("-created_at",)


@admin.register(BookingIdempotencyRecord)
class BookingIdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "action",
        "key",
        "booking_id",
        "response_status",
        "created_at",
    )
    list_filter = ("action", "response_status", "created_at")
    search_fields = ("key", "booking_id")
    readonly_fields = (
        "action",
        "key",
        "request_hash",
        "booking_id",
        "response_status",
        "response_body",
        "created_at",
        "updated_at",
    )


@admin.register(BookingChargeSheet)
class BookingChargeSheetAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "requestor_name",
        "guest_name",
        "room_charges_amount",
        "attender_charges_amount",
        "payment_received_date",
        "budget_head_name",
        "updated_at",
    )
    list_filter = (
        "booking__room__prefix",
        "payment_received_date",
        "updated_at",
    )
    search_fields = (
        "booking__id",
        "booking__visitor_name",
        "booking__requestor_name",
        "booking__room__prefix",
        "booking__room__number",
        "requestor_name",
        "guest_name",
        "purpose_event",
        "budget_head_name",
    )
    readonly_fields = ("booking", "created_at", "updated_at")
    ordering = ("booking__departure_at", "id")


@admin.register(BookingEditHistory)
class BookingEditHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "field_label",
        "edited_by_name",
        "edited_by_email",
        "edited_at",
    )
    list_filter = ("field_name", "edited_at")
    search_fields = (
        "booking__visitor_name",
        "booking__room__prefix",
        "booking__room__number",
        "edited_by_name",
        "edited_by_email",
        "field_label",
        "old_value",
        "new_value",
    )
    readonly_fields = (
        "booking",
        "edited_by",
        "edited_by_name",
        "edited_by_email",
        "field_name",
        "field_label",
        "old_value",
        "new_value",
        "edited_at",
    )
    ordering = ("-edited_at", "-id")


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "requester",
        "status",
        "preferred_prefix",
        "preferred_room",
        "arrival_at",
        "departure_at",
        "requested_at",
        "reviewed_by",
    )
    list_filter = ("status", "preferred_prefix", "requested_at", "reviewed_at")
    search_fields = (
        "requester__email",
        "requester__first_name",
        "visitor_name",
        "requestor_name",
        "preferred_prefix",
        "preferred_room__number",
        "admin_remarks",
    )
    readonly_fields = ("requested_at", "reviewed_at", "reviewed_by", "approved_booking")
    ordering = ("-requested_at",)
