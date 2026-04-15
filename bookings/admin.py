from django.contrib import admin
from .models import Booking, CancelledBooking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "room",
        "created_by",
        "arrival_at",
        "departure_at",
        "status",
        "created_at",
    ]

    list_filter = [
        "status",
        "arrival_at",
        "departure_at",
    ]

    search_fields = [
        "created_by__username",
        "room__prefix",
        "room__number",
    ]

    readonly_fields = [
        "created_at",
    ]

    ordering = ["-created_at"]


@admin.register(CancelledBooking)
class CancelledBookingAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "room_name",
        "cancelled_by",
        "arrival_at",
        "departure_at",
        "cancelled_at",
    ]

    list_filter = [
        "cancelled_at",
    ]

    search_fields = [
        "room_name",
        "cancelled_by__username",
    ]

    ordering = ["-cancelled_at"]