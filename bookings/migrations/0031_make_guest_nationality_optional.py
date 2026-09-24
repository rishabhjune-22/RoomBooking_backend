from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0030_booking_guest_nationality"),
    ]

    operations = [
        migrations.AlterField(
            model_name="booking",
            name="visitor_nationality",
            field=models.CharField(
                blank=True,
                choices=[("indian", "Indian"), ("foreigner", "Foreigner")],
                default="",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="bookingrequest",
            name="visitor_nationality",
            field=models.CharField(
                blank=True,
                choices=[("indian", "Indian"), ("foreigner", "Foreigner")],
                default="",
                max_length=20,
            ),
        ),
    ]
