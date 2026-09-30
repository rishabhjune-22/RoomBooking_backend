from django.db import migrations


def remove_duplicate_workflow_notifications(apps, schema_editor):
    WorkflowNotification = apps.get_model("accounts", "WorkflowNotification")
    legacy_rows = WorkflowNotification.objects.filter(
        event_key__regex=r"^(booking-request:[0-9]+:pending:[0-9]+|my-request:|my-request-deleted:)"
    ).order_by("id")

    for notification in legacy_rows.iterator():
        if not notification.related_object_id:
            continue
        matching_event_exists = (
            WorkflowNotification.objects
            .filter(
                user_id=notification.user_id,
                category=notification.category,
                related_object_type=notification.related_object_type,
                related_object_id=notification.related_object_id,
            )
            .exclude(pk=notification.pk)
            .exclude(event_key=notification.event_key)
            .exists()
        )
        if matching_event_exists:
            notification.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_remove_notification_email_fields"),
    ]

    operations = [
        migrations.RunPython(
            remove_duplicate_workflow_notifications,
            migrations.RunPython.noop,
        ),
    ]
