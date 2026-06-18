from django.db import migrations, models


CHARGE_CHOICES = [("yes", "Yes"), ("no", "No"), ("waived_off", "Waived Off")]


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0007_alter_booking_requestee_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="room_charges_status",
            field=models.CharField(choices=CHARGE_CHOICES, default="no", max_length=20),
        ),
        migrations.AddField(
            model_name="booking",
            name="attender_charges_status",
            field=models.CharField(choices=CHARGE_CHOICES, default="no", max_length=20),
        ),
        migrations.AddField(
            model_name="cancelledbooking",
            name="room_charges_status",
            field=models.CharField(choices=CHARGE_CHOICES, default="no", max_length=20),
        ),
        migrations.AddField(
            model_name="cancelledbooking",
            name="attender_charges_status",
            field=models.CharField(choices=CHARGE_CHOICES, default="no", max_length=20),
        ),
    ]
