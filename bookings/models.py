from django.conf import settings
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

    BUDGET_HEAD_INDIVIDUAL = "individual"
    BUDGET_HEAD_INSTITUTE = "institute_head"
    BUDGET_HEAD_PROJECT = "project_head"

    BUDGET_HEAD_CHOICES = [
        (BUDGET_HEAD_INDIVIDUAL, "Individual"),
        (BUDGET_HEAD_INSTITUTE, "Institute Head"),
        (BUDGET_HEAD_PROJECT, "Project Head"),
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

    budget_head_type = models.CharField(
        max_length=30,
        choices=BUDGET_HEAD_CHOICES,
        blank=True,
        default="",
    )
    budget_head_value = models.CharField(max_length=100, blank=True, default="")
    budget_head_name = models.CharField(max_length=100, blank=True, default="")
    budget_head_department_name = models.CharField(max_length=100, blank=True, default="")
    budget_head_project_code = models.CharField(max_length=100, blank=True, default="")

    requestor_name = models.CharField(max_length=100, blank=True, default="")

    requestor_designation = models.CharField(max_length=100, blank=True, default="")
    requestor_department = models.CharField(max_length=100, blank=True, default="")
    requestor_mobile = models.CharField(max_length=20, blank=True, default="")

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
    attender_morning_shift = models.BooleanField(default=False)  # 7 AM - 3 PM
    attender_day_shift = models.BooleanField(default=False)      # 3 PM - 11 PM

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
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_bookings",
    )
    created_by_name = models.CharField(max_length=100, blank=True, default="")
    def __str__(self):
        return f"Booking #{self.id} - {self.room}"

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room", "status", "arrival_at", "departure_at"]),
        ]


class BookingEditHistory(models.Model):
    booking = models.ForeignKey(
        Booking,
        related_name="edit_history",
        on_delete=models.CASCADE,
    )
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="booking_edits",
    )
    edited_by_name = models.CharField(max_length=255, blank=True, default="")
    edited_by_email = models.EmailField(blank=True, default="")
    field_name = models.CharField(max_length=100)
    field_label = models.CharField(max_length=150)
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    edited_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.booking_id} {self.field_name} edited at {self.edited_at}"

    class Meta:
        ordering = ["-edited_at", "-id"]
        indexes = [
            models.Index(fields=["booking", "edited_at"]),
        ]


class BookingRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CORRECTION_REQUIRED = "correction_required"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CORRECTION_REQUIRED, "Correction Required"),
    ]

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="booking_requests",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="reviewed_booking_requests",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    admin_remarks = models.TextField(blank=True, default="")
    approved_booking = models.OneToOneField(
        Booking,
        related_name="source_request",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deleted_booking_requests",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    deleted_by_name = models.CharField(max_length=255, blank=True, default="")
    deleted_by_role = models.CharField(max_length=30, blank=True, default="")
    delete_reason = models.TextField(blank=True, default="")

    arrival_at = models.DateTimeField(db_index=True)
    departure_at = models.DateTimeField(db_index=True)
    preferred_prefix = models.CharField(max_length=50, blank=True, default="")
    preferred_room = models.ForeignKey(
        Room,
        related_name="preferred_booking_requests",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    room_preference_note = models.TextField(blank=True, default="")

    visitor_name = models.CharField(max_length=100)
    visitor_category = models.CharField(
        max_length=50,
        choices=Booking.VISITOR_CATEGORY_CHOICES,
        blank=True,
        default="",
    )
    visitor_designation = models.CharField(max_length=100, blank=True, default="")
    visitor_organisation = models.CharField(max_length=100, blank=True, default="")
    visitor_gender = models.CharField(max_length=20, blank=True, default="")
    visitor_address = models.TextField(blank=True, default="")
    visitor_mobile = models.CharField(max_length=20, blank=True, default="")
    visitor_email = models.EmailField(blank=True, default="")
    purpose_of_visit = models.TextField(blank=True, default="")

    attender_required = models.BooleanField(default=False)
    attender_count_per_day = models.PositiveIntegerField(default=0)
    attender_general_shift = models.BooleanField(default=False)
    attender_morning_shift = models.BooleanField(default=False)
    attender_day_shift = models.BooleanField(default=False)

    requestor_name = models.CharField(max_length=100, blank=True, default="")
    requestor_designation = models.CharField(max_length=100, blank=True, default="")
    requestor_department = models.CharField(max_length=100, blank=True, default="")
    requestor_mobile = models.CharField(max_length=20, blank=True, default="")
    requestor_email = models.EmailField(blank=True, default="")

    def __str__(self):
        return f"Request #{self.id} {self.status}"

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["requester", "status", "requested_at"]),
            models.Index(fields=["status", "requested_at"]),
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
