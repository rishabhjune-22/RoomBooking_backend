# Generated manually to remove the retired attender option.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0031_make_guest_nationality_optional"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="booking",
            name="attender_general_shift",
        ),
        migrations.RemoveField(
            model_name="bookingrequest",
            name="attender_general_shift",
        ),
    ]
