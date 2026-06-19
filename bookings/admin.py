from django.contrib import admin
from .models import Booking, BookingIdempotencyRecord


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
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
