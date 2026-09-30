from django.db import transaction

from .models import UserProfile, WorkflowNotification
from .roles import APPROVAL_APPROVED, ROLE_ADMIN, ROLE_SUPERADMIN


def approved_admin_users():
    return [
        profile.user
        for profile in UserProfile.objects.select_related("user").filter(
            role__in=[ROLE_ADMIN, ROLE_SUPERADMIN],
            approval_status=APPROVAL_APPROVED,
            user__is_active=True,
        )
    ]


def create_notification(
    *, user, category, event_key, title, message, target_view,
    related_object_type="", related_object_id=None,
):
    notification, created = WorkflowNotification.objects.get_or_create(
        user=user,
        event_key=event_key,
        defaults={
            "category": category,
            "title": title,
            "message": message,
            "target_view": target_view,
            "related_object_type": related_object_type,
            "related_object_id": related_object_id,
        },
    )
    return notification, created


def notify_users_after_commit(users, **notification):
    recipient_ids = list(dict.fromkeys(user.pk for user in users if user and user.pk))
    if not recipient_ids:
        return

    def deliver():
        user_model = UserProfile._meta.get_field("user").remote_field.model
        for user in user_model.objects.filter(pk__in=recipient_ids, is_active=True):
            create_notification(user=user, **notification)

    transaction.on_commit(deliver)
