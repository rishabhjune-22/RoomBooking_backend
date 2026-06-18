from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0014_rename_requestee_to_requestor"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="booking",
            name="attender_night_shift",
        ),
    ]
