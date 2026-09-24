from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0032_remove_attender_general_shift"),
    ]

    operations = [
        migrations.RenameField(
            model_name="booking",
            old_name="attender_day_shift",
            new_name="attender_evening_shift",
        ),
        migrations.RenameField(
            model_name="bookingrequest",
            old_name="attender_day_shift",
            new_name="attender_evening_shift",
        ),
    ]
