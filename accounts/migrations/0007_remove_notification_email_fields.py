from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_workflownotification"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="workflownotification",
            name="email_error",
        ),
        migrations.RemoveField(
            model_name="workflownotification",
            name="emailed_at",
        ),
    ]
