from django.db import migrations, models


def convert_blocked_to_rejected(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    UserProfile.objects.filter(approval_status="blocked").update(
        approval_status="rejected",
        rejection_reason="Account access was rejected.",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_userprofile_approval_status"),
    ]

    operations = [
        migrations.RunPython(convert_blocked_to_rejected, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="userprofile",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
    ]
