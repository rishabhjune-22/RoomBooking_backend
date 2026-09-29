from django.db import migrations
from django.utils import timezone


def approve_pending_requesters(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    pending_profiles = UserProfile.objects.filter(
        role="requester",
        approval_status="pending",
    )
    user_ids = list(pending_profiles.values_list("user_id", flat=True))
    pending_profiles.update(
        approval_status="approved",
        approved_at=timezone.now(),
        rejection_reason="",
    )
    if user_ids:
        User = apps.get_model("auth", "User")
        User.objects.filter(pk__in=user_ids).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_remove_blocked_approval_status")]

    operations = [migrations.RunPython(approve_pending_requesters, migrations.RunPython.noop)]
