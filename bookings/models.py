from django.db import models
from hostels.models import Room


class Booking(models.Model):

    CHARGE_STATUS_YES = "yes"
    CHARGE_STATUS_NO = "no"
    CHARGE_STATUS_WAIVED_OFF = "waived_off"

    CHARGE_STATUS_CHOICES = [
        (CHARGE_STATUS_YES, "Yes"),
        (CHARGE_STATUS_NO, "No"),
        (CHARGE_STATUS_WAIVED_OFF, "Waived Off"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
    ]

    VISITOR_CATEGORY_INSTITUTE = "institute_guest"
    VISITOR_CATEGORY_CONFERENCE = "conference_workshop_guest"
    VISITOR_CATEGORY_OTHER = "other_guest"

    VISITOR_CATEGORY_CHOICES = [
        (VISITOR_CATEGORY_INSTITUTE, "Institute Guest"),
        (VISITOR_CATEGORY_CONFERENCE, "Conference/Workshop Guest"),
        (VISITOR_CATEGORY_OTHER, "Other Guest"),
    ]


    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    arrival_at = models.DateTimeField(db_index=True)
    departure_at = models.DateTimeField(db_index=True)

    visitor_name = models.CharField(max_length=100)
    visitor_category = models.CharField(
        max_length=50,
        choices=VISITOR_CATEGORY_CHOICES,
        blank=True,
        default=""
    )
    visitor_designation = models.CharField(max_length=100, blank=True, default="")
    visitor_organisation = models.CharField(max_length=100, blank=True, default="")
    visitor_gender = models.CharField(max_length=20, blank=True, default="")
    visitor_address = models.TextField(blank=True, default="")
    visitor_mobile = models.CharField(max_length=20, blank=True, default="")
    visitor_email = models.EmailField(blank=True, default="")
    purpose_of_visit = models.TextField(blank=True, default="")

    requestee_name = models.CharField(max_length=100, blank=True, default="")

    requestee_designation = models.CharField(max_length=100, blank=True, default="")
    requestee_department = models.CharField(max_length=100, blank=True, default="")
    requestee_mobile = models.CharField(max_length=20, blank=True, default="")

    logistics_name = models.CharField(max_length=100, blank=True, default="")
    logistics_designation = models.CharField(max_length=100, blank=True, default="")
    logistics_mobile = models.CharField(max_length=20, blank=True, default="")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    attender_required = models.BooleanField(default=False)

    attender_count_per_day = models.PositiveIntegerField(default=0)

    attender_general_shift = models.BooleanField(default=False)  # 9 AM - 5 PM
    attender_morning_shift = models.BooleanField(default=False)  # 6 AM - 2 PM
    attender_day_shift = models.BooleanField(default=False)      # 2 PM - 10 PM
    attender_night_shift = models.BooleanField(default=False)    # 10 PM - 6 AM

    room_charges_status = models.CharField(
        max_length=20,
        choices=CHARGE_STATUS_CHOICES,
        default=CHARGE_STATUS_NO,
    )
    attender_charges_status = models.CharField(
        max_length=20,
        choices=CHARGE_STATUS_CHOICES,
        default=CHARGE_STATUS_NO,
    )
    room_charges_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    attender_charges_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)



    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by_name = models.CharField(max_length=100, blank=True, default="")
    def __str__(self):
        return f"Booking #{self.id} - {self.room}"

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room", "status", "arrival_at", "departure_at"]),
        ]


class BookingIdempotencyRecord(models.Model):
    ACTION_CREATE = "booking_create"
    ACTION_DELETE = "booking_delete"

    ACTION_CHOICES = [
        (ACTION_CREATE, "Booking create"),
        (ACTION_DELETE, "Booking delete"),
    ]

    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    booking_id = models.PositiveIntegerField(blank=True, null=True)
    response_status = models.PositiveSmallIntegerField(blank=True, null=True)
    response_body = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["action", "key"],
                name="unique_booking_idempotency_key",
            ),
        ]
        indexes = [
            models.Index(fields=["action", "created_at"]),
        ]
