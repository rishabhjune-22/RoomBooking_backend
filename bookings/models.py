from django.conf import settings
from django.db import models
from hostels.models import Room


class Booking(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    arrival_at = models.DateTimeField(db_index=True)
    departure_at = models.DateTimeField(db_index=True)

    encrypted_payload = models.TextField()
    payload_nonce = models.TextField()
    payload_version = models.PositiveIntegerField(default=1)

    requestee_name = models.CharField(max_length=100)
    requestee_designation = models.CharField(max_length=100)
    requestee_department = models.CharField(max_length=100)
    requestee_mobile = models.CharField(max_length=20)

    logistics_name = models.CharField(max_length=100)
    logistics_designation = models.CharField(max_length=100)
    logistics_mobile = models.CharField(max_length=20)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"Booking #{self.id} - {self.room}"

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room", "status", "arrival_at", "departure_at"]),
            models.Index(fields=["created_by", "status"]),
        ]


class CancelledBooking(models.Model):
    original_booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="cancellation_records",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="cancelled_bookings",
    )
    cancelled_at = models.DateTimeField(auto_now_add=True)
    cancellation_reason = models.TextField(blank=True, null=True)

    room_name = models.CharField(max_length=100)
    arrival_at = models.DateTimeField()
    departure_at = models.DateTimeField()

    encrypted_payload = models.TextField()
    payload_nonce = models.TextField()
    payload_version = models.PositiveIntegerField(default=1)

    requestee_name = models.CharField(max_length=100)
    requestee_designation = models.CharField(max_length=100)
    requestee_department = models.CharField(max_length=100)
    requestee_mobile = models.CharField(max_length=20)

    logistics_name = models.CharField(max_length=100)
    logistics_designation = models.CharField(max_length=100)
    logistics_mobile = models.CharField(max_length=20)

    def __str__(self):
        return f"Cancelled Booking #{self.id} - {self.room_name}"

    class Meta:
        ordering = ["-cancelled_at"]