from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_SUPERADMIN = "superadmin"
    ROLE_ADMIN = "admin"
    ROLE_REQUESTER = "requester"

    ROLE_CHOICES = [
        (ROLE_SUPERADMIN, "Superadmin"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_REQUESTER, "Requester"),
    ]

    APPROVAL_PENDING = "pending"
    APPROVAL_APPROVED = "approved"
    APPROVAL_REJECTED = "rejected"

    APPROVAL_STATUS_CHOICES = [
        (APPROVAL_PENDING, "Pending"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="profile",
        on_delete=models.CASCADE,
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_ADMIN,
        db_index=True,
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default=APPROVAL_PENDING,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_profiles",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    designation = models.CharField(max_length=100, blank=True, default="")
    department = models.CharField(max_length=100, blank=True, default="")
    mobile = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user_id} {self.role}"


class WorkflowNotification(models.Model):
    CATEGORY_BOOKING_REQUESTS = "booking_requests"
    CATEGORY_REQUESTER_ACCOUNTS = "requester_accounts"
    CATEGORY_ADMIN_ACCOUNTS = "admin_accounts"
    CATEGORY_MY_REQUESTS = "my_requests"

    CATEGORY_CHOICES = [
        (CATEGORY_BOOKING_REQUESTS, "Booking requests"),
        (CATEGORY_REQUESTER_ACCOUNTS, "Requester accounts"),
        (CATEGORY_ADMIN_ACCOUNTS, "Admin accounts"),
        (CATEGORY_MY_REQUESTS, "My requests"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="workflow_notifications",
        on_delete=models.CASCADE,
    )
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, db_index=True)
    event_key = models.CharField(max_length=180)
    title = models.CharField(max_length=180)
    message = models.TextField()
    target_view = models.CharField(max_length=40, blank=True, default="")
    related_object_type = models.CharField(max_length=50, blank=True, default="")
    related_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event_key"],
                name="unique_workflow_notification_event_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "read_at", "created_at"]),
            models.Index(fields=["user", "category", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user_id} {self.category}: {self.title}"
