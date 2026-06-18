from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0013_booking_idempotency_record"),
    ]

    operations = [
        migrations.RenameField(
            model_name="booking",
            old_name="requestee_name",
            new_name="requestor_name",
        ),
        migrations.RenameField(
            model_name="booking",
            old_name="requestee_designation",
            new_name="requestor_designation",
        ),
        migrations.RenameField(
            model_name="booking",
            old_name="requestee_department",
            new_name="requestor_department",
        ),
        migrations.RenameField(
            model_name="booking",
            old_name="requestee_mobile",
            new_name="requestor_mobile",
        ),
    ]
