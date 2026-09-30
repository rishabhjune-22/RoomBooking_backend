from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_auto_approve_pending_requesters"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkflowNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("booking_requests", "Booking requests"), ("requester_accounts", "Requester accounts"), ("admin_accounts", "Admin accounts"), ("my_requests", "My requests")], db_index=True, max_length=40)),
                ("event_key", models.CharField(max_length=180)),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField()),
                ("target_view", models.CharField(blank=True, default="", max_length=40)),
                ("related_object_type", models.CharField(blank=True, default="", max_length=50)),
                ("related_object_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("read_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("emailed_at", models.DateTimeField(blank=True, null=True)),
                ("email_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workflow_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="workflownotification",
            constraint=models.UniqueConstraint(fields=("user", "event_key"), name="unique_workflow_notification_event_per_user"),
        ),
        migrations.AddIndex(
            model_name="workflownotification",
            index=models.Index(fields=["user", "read_at", "created_at"], name="accounts_wo_user_id_401654_idx"),
        ),
        migrations.AddIndex(
            model_name="workflownotification",
            index=models.Index(fields=["user", "category", "created_at"], name="accounts_wo_user_id_6d521d_idx"),
        ),
    ]
